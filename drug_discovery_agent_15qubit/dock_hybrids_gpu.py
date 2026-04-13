import sys, json, subprocess
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

try:
    from meeko import MoleculePreparation, PDBQTWriterLegacy
except ImportError as e:
    print('Missing dep:', e)
    sys.exit(1)

GNINA = str(Path.home() / 'gnina')
RECEPTOR = 'whitepaper_docking/3L2T_receptor.pdbqt'
BOX_CENTER = [-38.5, 30.5, -20.8]
BOX_SIZE = [25.0, 25.0, 25.0]
WORK_DIR = Path('hybrid_docking')
WORK_DIR.mkdir(exist_ok=True)

HYBRIDS = {
    'HIV-022':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1',
    'HIV-020':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1',
    'HIV-010':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1',
    'HYB-001':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1',
    'HYB-002':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1Cc1cccc(F)c1',
    'HYB-003':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1Cc1cccc(C(F)(F)F)c1',
    'HYB-004':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1',
    'HYB-005':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1',
    'HYB-006':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1OCC1CC1',
    'HYB-007':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1OC1CCCO1',
    'HYB-008':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cccc(C(F)(F)F)c1',
    'HYB-009':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1OCC1CC1',
    'HYB-010':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1cc2ccccc2cc1Cc1cccc(F)c1',
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

def dock_gnina(name, sdf):
    out = str(WORK_DIR / f'{name}_out.sdf')
    log = str(WORK_DIR / f'{name}_log.txt')
    cmd = [
        GNINA,
        '-r', RECEPTOR,
        '-l', sdf,
        '-o', out,
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        with open(log, 'w') as f:
            f.write(result.stdout)
            f.write(result.stderr)
        affinities = []
        cnn_scores = []
        for line in result.stdout.split('\n'):
            parts = line.split()
            if len(parts) >= 3 and parts[0].lstrip('-').isdigit():
                try:
                    affinities.append(float(parts[1]))
                    cnn_scores.append(float(parts[2]))
                except:
                    pass
        if affinities:
            return min(affinities), affinities, cnn_scores
        return None, [], []
    except Exception as e:
        print('  Gnina error:', e)
        return None, [], []

results = {}
print('GPU Docking with Gnina - GTX 1660 Ti')
print('='*60)
for name, smiles in HYBRIDS.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    print(f'[{name}] MW={mw}')
    sdf = smiles_to_sdf(name, smiles)
    if sdf:
        aff, all_aff, cnn = dock_gnina(name, sdf)
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': aff, 'all_affinities': all_aff, 'cnn_scores': cnn}
        if aff:
            tag = 'EXCELLENT' if aff <= -10.0 else 'GOOD' if aff <= -8.5 else 'MODERATE'
            cnn_best = max(cnn) if cnn else 0
            print(f'  Affinity: {aff:.2f} kcal/mol | CNN: {cnn_best:.3f} [{tag}]')
        else:
            print('  No poses found - check log')
    else:
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': None, 'all_affinities': [], 'cnn_scores': []}

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
    cnn_best = max(data['cnn_scores']) if data['cnn_scores'] else 0
    tag = 'EXCELLENT' if aff <= -10.0 else 'GOOD' if aff <= -8.5 else 'MODERATE'
    print(f'{name:<12} {aff:.2f} kcal/mol  CNN={cnn_best:.3f}  MW={data["mw"]}  [{tag}]')
print('-'*60)
print('Target: -10.0 or better')

with open(WORK_DIR / 'hybrid_gnina_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Saved: hybrid_docking/hybrid_gnina_results.json')