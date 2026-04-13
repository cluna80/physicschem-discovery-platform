import sys, json
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

try:
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from vina import Vina
except ImportError as e:
    print('Missing dep:', e)
    sys.exit(1)

# Warhead from HIV-022/020/010 (pyridine diketo acid + amide)
# Tail swapped to naphthalene/isoquinoline cores from winning series
HYBRIDS = {
    # Original leads
    'HIV-022': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1',
    'HIV-020': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1',
    'HIV-010': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1',
    # Hybrids: diketo warhead + naphthalene tail (your -11.2 winner)
    'HYB-001': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1Cc1ccc2ccccc2c1',
    'HYB-002': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1',
    # Warhead + naphthalene + metaF (your best CNN score combo)
    'HYB-003': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1Cc1cccc(F)c1',
    # Warhead + naphthalene + metaCF3
    'HYB-004': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1Cc1cccc(C(F)(F)F)c1',
    # Warhead + isoquinoline tail (your -11.3 winner)
    'HYB-005': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1',
    # Warhead + isoquinoline + 35diF
    'HYB-006': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1',
    # Warhead + cyclopropyl ether from HIV-022 + naphthalene
    'HYB-007': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1OCC1CC1',
    # Warhead + naphthalene + spiroTHF (your best CNN combo)
    'HYB-008': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1OC1CCCO1',
    # Direct naphthalene no linker
    'HYB-009': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)c1ccc2ccccc2c1',
    # Isoquinoline + metaCF3 benzyl
    'HYB-010': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cccc(C(F)(F)F)c1',
}

WORK_DIR = Path('hybrid_docking')
WORK_DIR.mkdir(exist_ok=True)

RECEPTOR_PDBQT = 'whitepaper_docking/3L2T_receptor.pdbqt'
BOX_CENTER = [-38.5, 30.5, -20.8]
BOX_SIZE = [25.0, 25.0, 25.0]

def smiles_to_pdbqt(name, smiles):
    out = WORK_DIR / f'{name}.pdbqt'
    if out.exists():
        return str(out)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print('  Invalid SMILES:', name, smiles)
        return None
    mol = Chem.AddHs(mol)
    res = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if res != 0:
        AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    try:
        prep = MoleculePreparation()
        mol_setups = prep.prepare(mol)
        pdbqt_string, is_ok, error = PDBQTWriterLegacy.write_string(mol_setups[0])
        if not is_ok:
            print('  PDBQT error:', error)
            return None
        with open(out, 'w') as f:
            f.write(pdbqt_string)
        return str(out)
    except Exception as e:
        print('  Meeko error:', name, e)
        return None

def dock(name, pdbqt):
    out = WORK_DIR / f'{name}_docked.pdbqt'
    try:
        v = Vina(sf_name='vina', verbosity=0)
        v.set_receptor(RECEPTOR_PDBQT)
        v.set_ligand_from_file(pdbqt)
        v.compute_vina_maps(center=BOX_CENTER, box_size=BOX_SIZE)
        v.dock(exhaustiveness=32, n_poses=5)
        v.write_poses(str(out), n_poses=5, overwrite=True)
        energies = v.energies(n_poses=5)
        best = float(energies[0][0])
        all_poses = [float(e[0]) for e in energies]
        return best, all_poses
    except Exception as e:
        print('  Docking failed:', name, e)
        return None, None

results = {}
print('Running hybrid docking...')
print('='*60)
for name, smiles in HYBRIDS.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    print(f'[{name}] MW={mw}')
    pdbqt = smiles_to_pdbqt(name, smiles)
    if pdbqt:
        aff, poses = dock(name, pdbqt)
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': aff, 'all_poses': poses or []}
        if aff:
            tag = 'EXCELLENT' if aff <= -10.0 else 'GOOD' if aff <= -8.5 else 'MODERATE'
            print(f'  Affinity: {aff:.2f} kcal/mol [{tag}]')
    else:
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': None, 'all_poses': []}
        print('  SKIPPED - invalid structure')

print()
print('='*60)
print('FINAL RANKINGS')
print('='*60)
sorted_r = sorted(
    [(n, d) for n, d in results.items() if d['affinity'] is not None],
    key=lambda x: x[1]['affinity']
)
for name, data in sorted_r:
    aff = data['affinity']
    tag = 'EXCELLENT' if aff <= -10.0 else 'GOOD' if aff <= -8.5 else 'MODERATE'
    print(f'{name:<12} {aff:.2f} kcal/mol  MW={data["mw"]}  [{tag}]')
print('-'*60)
print('Target: -10.0 or better')

out_json = WORK_DIR / 'hybrid_results.json'
with open(out_json, 'w') as f:
    json.dump(results, f, indent=2)
print('Saved:', out_json)