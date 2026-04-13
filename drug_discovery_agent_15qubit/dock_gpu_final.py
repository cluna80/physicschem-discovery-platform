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
WORK_DIR = Path('gpu_final_docking')
WORK_DIR.mkdir(exist_ok=True)

CANDIDATES = {
    'HIV-022':   'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1',
    'HIV-020':   'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1',
    'HYB-001':   'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1',
    'HYB-003':   'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ccccc2c1Cc1cccc(C(F)(F)F)c1',
    'HYB-005':   'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1',
    'NG-001':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3ccccc3c2',
    'NG-002':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c2ccc3ccccc3c2',
    'NG-003':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(C(F)(F)F)c2)c2ccc3ccccc3c2',
    'NG-004':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3cccnc3c2',
    'NG-005':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c2ccc3cccnc3c2',
    'TRIM-002':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](CC1CCCO1)c1ccc2ccccc2c1',
    'TRIM-003':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](CC1CCCO1)c1ccc2cccnc2c1',
    'TRIM-008':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(C(F)(F)F)c2)c2ccc3ccccc3c2',
    'TRIM-009':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3cccnc3c2',
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
            # Parse: mode | vina_aff | intramol | cnn_pose | cnn_aff
            if len(parts) == 5 and parts[0].lstrip('-').isdigit():
                try:
                    affinities.append(float(parts[1]))
                    cnn_pose.append(float(parts[3]))
                    cnn_aff.append(float(parts[4]))
                except:
                    pass
        if affinities:
            best_idx = affinities.index(min(affinities))
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
print('GPU Docking - GTX 1660 Ti - CNN Affinity Scoring')
print('='*65)
print(f'{"Name":<12} {"Vina":>7} {"CNN_pose":>9} {"CNN_aff":>9} {"MW":>5}  Status')
print('-'*65)

for name, smiles in CANDIDATES.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    sdf = smiles_to_sdf(name, smiles)
    if sdf:
        r = dock(name, sdf)
        if r:
            results[name] = {'smiles': smiles, 'mw': mw, **r}
            tag = 'EXCELLENT' if r['vina_best'] <= -10.0 else 'GOOD' if r['vina_best'] <= -8.5 else 'OK'
            print(f'{name:<12} {r["vina_best"]:>7.2f} {r["cnn_pose_best"]:>9.3f} {r["cnn_aff_best"]:>9.3f} {mw:>5}  [{tag}]')
        else:
            print(f'{name:<12} {"NO POSES":>7}')
    else:
        print(f'{name:<12} {"BAD SMILES":>7}')

print()
print('='*65)
print('RANKED BY VINA AFFINITY')
print('='*65)
sorted_r = sorted(
    [(n, d) for n, d in results.items()],
    key=lambda x: x[1]['vina_best']
)
for name, data in sorted_r:
    tag = 'EXCELLENT' if data['vina_best'] <= -10.0 else 'GOOD' if data['vina_best'] <= -8.5 else 'OK'
    print(f'{name:<12} Vina={data["vina_best"]:.2f}  CNN_aff={data["cnn_aff_best"]:.3f}  MW={data["mw"]}  [{tag}]')

print()
print('RANKED BY CNN AFFINITY (more reliable)')
print('='*65)
sorted_cnn = sorted(
    [(n, d) for n, d in results.items()],
    key=lambda x: x[1]['cnn_aff_best'], reverse=True
)
for name, data in sorted_cnn:
    print(f'{name:<12} CNN_aff={data["cnn_aff_best"]:.3f}  Vina={data["vina_best"]:.2f}  MW={data["mw"]}')

with open(WORK_DIR / 'gpu_final_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print()
print('Saved: gpu_final_docking/gpu_final_results.json')
