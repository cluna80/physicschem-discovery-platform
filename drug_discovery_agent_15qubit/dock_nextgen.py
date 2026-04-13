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
WORK_DIR = Path('nextgen_docking')
WORK_DIR.mkdir(exist_ok=True)

# HYB-001 was best: naphthalene + diketo warhead = -9.09
# Now add bis-THF and spiro-THF P2 groups that drove -11.x scores
NEXTGEN = {
    'HYB-001':     'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1',
    'NG-001':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3ccccc3c2',
    'NG-002':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c2ccc3ccccc3c2',
    'NG-003':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(C(F)(F)F)c2)c2ccc3ccccc3c2',
    'NG-004':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3cccnc3c2',
    'NG-005':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c2ccc3cccnc3c2',
    'NG-006':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3OCCO[C@H]23)c2ccc3ccccc3c2',
    'NG-007':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c2ccc3ccccc3c2',
    'NG-008':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3OCCO[C@H]23)c2ccc3cccnc3c2',
    'NG-009':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c2ccc3cccnc3c2',
    'NG-010':      'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2cc3ccccc3cc2',
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
        affinities, cnn_scores = [], []
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
        print('  Error:', e)
        return None, [], []

results = {}
print('Next-Gen Hybrid Docking - GPU')
print('='*60)
for name, smiles in NEXTGEN.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    print(f'[{name}] MW={mw}')
    sdf = smiles_to_sdf(name, smiles)
    if sdf:
        aff, all_aff, cnn = dock(name, sdf)
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': aff, 'all_affinities': all_aff, 'cnn_scores': cnn}
        if aff:
            tag = 'EXCELLENT' if aff <= -10.0 else 'GOOD' if aff <= -8.5 else 'MODERATE'
            cnn_best = max(cnn) if cnn else 0
            print(f'  Affinity: {aff:.2f} | CNN: {cnn_best:.3f} [{tag}]')
        else:
            print('  No poses - check gnina output')

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

with open(WORK_DIR / 'nextgen_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Saved: nextgen_docking/nextgen_results.json')