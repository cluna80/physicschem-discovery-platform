import json, subprocess
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

GNINA = str(Path.home() / 'gnina')
RECEPTOR = 'whitepaper_docking/3L2T_receptor.pdbqt'
BOX_CENTER = [-38.5, 30.5, -20.8]
BOX_SIZE = [25.0, 25.0, 25.0]
WORK_DIR = Path('naphthalene_series_docking')
WORK_DIR.mkdir(exist_ok=True)

# Your top hits from fresh_15qubit_search - now on same receptor/box/scoring
SERIES = {
    'naph_metaF':      'c1ccc2ccccc2c1C(=O)N[C@@H](C[C@@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1cccc(F)c1',
    'naph_metaCF3':    'c1ccc2ccccc2c1C(=O)N[C@H](C[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1cccc(C(F)(F)F)c1',
    'naph_35diF':      'c1ccc2ccccc2c1C(=O)N[C@@H](C[C@@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1cc(F)cc(F)c1',
    'isoq_35diF':      'c1ccc2cccnc2c1C(=O)N[C@H](C[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1cc(F)cc(F)c1',
    'indole_metaCF3':  'c1ccc2[nH]ccc2c1C(=O)N[C@H](C[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1cccc(C(F)(F)F)c1',
    'isoq_metaCl':     'c1ccc2cccnc2c1C(=O)N[C@@H](C[C@@H](O)CNC(=O)[C@@H]1CO[C@@H]2CCCO[C@H]21)Cc1cccc(Cl)c1',
    'indole_benzyl':   'c1ccc2[nH]ccc2c1C(=O)N[C@@H](C[C@@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)Cc1ccccc1',
}

def smiles_to_sdf(name, smiles):
    out = WORK_DIR / f'{name}.sdf'
    if out.exists():
        return str(out)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print('  Invalid SMILES:', name)
        return None
    mol = Chem.AddHs(mol)
    res = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if res != 0:
        AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    writer = Chem.SDWriter(str(out))
    writer.write(mol)
    writer.close()
    return str(out)

def dock(name, sdf):
    out = str(WORK_DIR / f'{name}_out.sdf')
    cmd = [
        GNINA,
        '-r', RECEPTOR, '-l', sdf, '-o', out,
        '--center_x', str(BOX_CENTER[0]),
        '--center_y', str(BOX_CENTER[1]),
        '--center_z', str(BOX_CENTER[2]),
        '--size_x', str(BOX_SIZE[0]),
        '--size_y', str(BOX_SIZE[1]),
        '--size_z', str(BOX_SIZE[2]),
        '--exhaustiveness', '32',
        '--num_modes', '5',
        '--cnn_scoring', 'rescore',
        '--device', '0',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        affinities, cnn_pose, cnn_aff = [], [], []
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) == 5 and parts[0].lstrip('-').isdigit():
                try:
                    affinities.append(float(parts[1]))
                    cnn_pose.append(float(parts[3]))
                    cnn_aff.append(float(parts[4]))
                except:
                    pass
        if affinities:
            return {
                'vina_best': min(affinities),
                'cnn_pose_best': max(cnn_pose) if cnn_pose else 0,
                'cnn_aff_best': max(cnn_aff) if cnn_aff else 0,
                'all_vina': affinities,
                'all_cnn_aff': cnn_aff,
            }
        return None
    except Exception as e:
        print('  Error:', e)
        return None

results = {}
print('Naphthalene Series - Same Receptor/Box/CNN as GPU Final Run')
print('='*65)
print(f'{"Name":<18} {"Vina":>7} {"CNN_pose":>9} {"CNN_aff":>9} {"MW":>5}')
print('-'*65)

for name, smiles in SERIES.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    print(f'Docking {name} MW={mw}...')
    sdf = smiles_to_sdf(name, smiles)
    if sdf:
        r = dock(name, sdf)
        if r:
            results[name] = {'smiles': smiles, 'mw': mw, **r}
            print(f'{name:<18} {r["vina_best"]:>7.2f} {r["cnn_pose_best"]:>9.3f} {r["cnn_aff_best"]:>9.3f} {mw:>5}')
        else:
            print(f'{name:<18} NO POSES')
    else:
        print(f'{name:<18} BAD SMILES')

print()
print('='*65)
print('RANKED BY CNN AFFINITY')
print('='*65)
sorted_cnn = sorted(
    [(n, d) for n, d in results.items()],
    key=lambda x: x[1]['cnn_aff_best'], reverse=True
)
for name, data in sorted_cnn:
    print(f'{name:<18} CNN_aff={data["cnn_aff_best"]:.3f}  Vina={data["vina_best"]:.2f}  MW={data["mw"]}')

with open(WORK_DIR / 'naphthalene_series_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print()
print('Saved: naphthalene_series_docking/naphthalene_series_results.json')
