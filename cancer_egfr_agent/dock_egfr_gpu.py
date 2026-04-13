import json, subprocess
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

GNINA = str(Path.home() / 'gnina')
RECEPTOR = 'structures/1M17_receptor.pdbqt'
BOX_CENTER = [22.01, 0.25, 52.79]
BOX_SIZE = [25.0, 25.0, 25.0]
WORK_DIR = Path('docking_results')
WORK_DIR.mkdir(exist_ok=True)

# All 29 candidates + Erlotinib reference
CANDIDATES = {
    "Erlotinib":  "CCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCC",
    "ERL-001": "CCOc1cc2ncnc(Nc3cccc(Cl)c3)c2cc1OCC#C",
    "ERL-002": "CCOc1cc2ncnc(Nc3ccc(F)cc3)c2cc1OCC",
    "ERL-003": "COc1cc2ncnc(Nc3cccc(Cl)c3)c2cc1OC",
    "ERL-004": "CCOc1cc2ncnc(Nc3ccc(Cl)c3F)c2cc1OCC#C",
    "ERL-005": "CCOc1cc2ncnc(Nc3cccc(C(F)(F)F)c3)c2cc1OCC",
    "GEF-001": "COc1cc2c(Nc3ccc(F)cc3Cl)ncnc2cc1OCCCN1CCOCC1",
    "GEF-002": "COc1cc2c(Nc3ccc(Cl)cc3)ncnc2cc1OCCCN1CCNCC1",
    "GEF-003": "COc1cc2c(Nc3cccc(Br)c3)ncnc2cc1OCCCN1CCOCC1",
    "GEF-004": "Fc1ccc(Nc2ncnc3cc(OC)c(OCCCN4CCOCC4)cc23)cc1",
    "GEF-005": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",
    "AFA-001": "CN(C)CCOc1cc2ncnc(Nc3ccc(F)cc3Cl)c2cc1OC(=O)C=C",
    "AFA-002": "COc1cc2ncnc(Nc3ccc(Cl)cc3F)c2cc1OCCN(C)CC=O",
    "AFA-003": "CN(C)CCOc1cc2ncnc(Nc3cccc(Cl)c3)c2cc1OCC=C",
    "OSI-001": "COc1cc(Nc2ncnc3cc(OC)c(N(C)CCN(C)C)cc23)ccc1NC(=O)C=C",
    "OSI-002": "CNc1cc(Nc2ncnc3ccc(OC)c(N4CCN(C)CC4)c23)ccc1",
    "OSI-003": "COc1cc2ncnc(Nc3ccnc(NCC)c3)c2cc1N1CCN(C)CC1",
    "NOV-001": "Clc1ccc(Nc2ncnc3ccc(N4CCNCC4)cc23)cc1",
    "NOV-002": "Fc1ccc(Nc2ncnc3ccc(N4CCN(C)CC4)cc23)c(F)c1",
    "NOV-003": "COc1ccc(Nc2ncnc3cc(OC)ccc23)cc1Cl",
    "NOV-004": "CCN1CCN(c2ccc(Nc3ncnc4ccccc34)cc2)CC1",
    "NOV-005": "Clc1cccc(Nc2ncnc3cc(OCC)c(OCC)cc23)c1",
    "LAP-001": "CS(=O)(=O)CCNCc1ccc(-c2ccc3ncnc(Nc4ccc(OCc5cccc(F)c5)c(Cl)c4)c3c2)cc1",
    "LAP-002": "Clc1ccc(Nc2ncnc3cc(-c4ccc(CNCC(=O)N5CCOCC5)cc4)ccc23)c(Cl)c1",
    "LAP-003": "O=C(Nc1ccc(Nc2ncnc3ccccc23)cc1)c1cccnc1",
    "IND-001": "CCc1nc2ccccc2n1Cc1ccc(Nc2ncnc3ccccc23)cc1",
    "IND-002": "COc1ccc(CNc2ncnc3[nH]ccc23)cc1Cl",
    "IND-003": "Fc1ccc(Nc2ncnc3[nH]cnc23)cc1",
    "THI-001": "CCOc1ccc(Nc2ncnc3sc(CC)cc23)cc1",
    "THI-002": "Clc1ccc(Nc2ncnc3cc(OC)ccc23)cc1F",
    "THI-003": "COc1ccc2ncnc(Nc3ccc(Cl)cc3F)c2c1",
}

def smiles_to_sdf(name, smiles):
    out = WORK_DIR / f'{name}.sdf'
    if out.exists():
        return str(out)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f'  Invalid SMILES: {name}')
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
            }
        return None
    except Exception as e:
        print(f'  Error: {e}')
        return None

results = {}
print('EGFR GPU Docking - GTX 1660 Ti')
print('Receptor: 1M17 | Erlotinib binding site')
print('='*65)
print(f'{"Name":<12} {"Vina":>7} {"CNN_pose":>9} {"CNN_aff":>9} {"MW":>5}')
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
            print(f'{name:<12} NO POSES')
    else:
        print(f'{name:<12} BAD SMILES')

print()
print('='*65)
print('RANKED BY VINA AFFINITY')
print('='*65)
sorted_vina = sorted(
    [(n, d) for n, d in results.items() if 'vina_best' in d],
    key=lambda x: x[1]['vina_best']
)
for name, data in sorted_vina:
    tag = 'EXCELLENT' if data['vina_best'] <= -10.0 else 'GOOD' if data['vina_best'] <= -8.5 else 'OK'
    print(f'{name:<12} Vina={data["vina_best"]:.2f}  CNN_aff={data["cnn_aff_best"]:.3f}  MW={data["mw"]}  [{tag}]')

print()
print('RANKED BY CNN AFFINITY')
print('='*65)
sorted_cnn = sorted(
    [(n, d) for n, d in results.items() if 'cnn_aff_best' in d],
    key=lambda x: x[1]['cnn_aff_best'], reverse=True
)
for name, data in sorted_cnn:
    print(f'{name:<12} CNN_aff={data["cnn_aff_best"]:.3f}  Vina={data["vina_best"]:.2f}  MW={data["mw"]}')

print(f'\nErlotinib reference: typically -9 to -11 kcal/mol vs EGFR')

with open('egfr_results/docking_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Saved: egfr_results/docking_results.json')
