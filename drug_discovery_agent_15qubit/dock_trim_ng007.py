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
WORK_DIR = Path('trim_docking')
WORK_DIR.mkdir(exist_ok=True)

# NG-007 was -9.93 @ MW=576 (spiro-THF + naphthalene)
# Goal: keep spiro-THF, trim MW to <500, push past -10.0
# Strategy: shrink benzyl substituents, swap naphthalene for indole/isoquinoline

TRIMMED = {
    # NG-007 reference
    'NG-007':    'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c2ccc3ccccc3c2',
    # Trim: remove hydroxyl chain, direct spiro-THF on naphthalene
    'TRIM-001':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](C[C@@H]2CCCO2)c2ccc3ccccc3c2',
    # Trim: shorter linker to spiro-THF
    'TRIM-002':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](CC1CCCO1)c1ccc2ccccc2c1',
    # Trim: isoquinoline + spiro-THF (lighter core)
    'TRIM-003':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](CC1CCCO1)c1ccc2cccnc2c1',
    # Trim: naphthalene + metaF benzyl (no THF, just fluorine optimization)
    'TRIM-004':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3ccccc3c2',
    # Trim: isoquinoline + 35diF benzyl
    'TRIM-005':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c2ccc3cccnc3c2',
    # Trim: naphthalene + bis-THF but shorter warhead
    'TRIM-006':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](C[C@@H]1OCC2OCCO2)c2ccc3ccccc3c2',
    # Trim: indole core (smaller) + spiro-THF
    'TRIM-007':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](CC1CCCO1)c1ccc2[nH]ccc2c1',
    # Trim: naphthalene + CF3 (your top scorer combo)
    'TRIM-008':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(C(F)(F)F)c2)c2ccc3ccccc3c2',
    # Trim: isoquinoline + spiro-THF + metaF
    'TRIM-009':  'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c2ccc3cccnc3c2',
    # Trim: pure naphthalene diketo no amide linker
    'TRIM-010':  'Cc1cnc(C(=O)C(=O)O)cc1c1ccc2ccccc2c1',
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
print('Trimmed NG-007 Variants - Target: -10.0 kcal/mol')
print('='*60)
for name, smiles in TRIMMED.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = round(Descriptors.MolWt(mol)) if mol else 0
    print(f'[{name}] MW={mw}')
    sdf = smiles_to_sdf(name, smiles)
    if sdf:
        aff, all_aff, cnn = dock(name, sdf)
        results[name] = {'smiles': smiles, 'mw': mw, 'affinity': aff, 'all_affinities': all_aff, 'cnn_scores': cnn}
        if aff:
            tag = 'TARGET HIT' if aff <= -10.0 else 'CLOSE' if aff <= -9.5 else 'GOOD' if aff <= -8.5 else 'MODERATE'
            print(f'  Affinity: {aff:.2f} kcal/mol  MW={mw}  [{tag}]')
        else:
            print('  No poses')
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
    tag = 'TARGET HIT' if aff <= -10.0 else 'CLOSE' if aff <= -9.5 else 'GOOD' if aff <= -8.5 else 'MODERATE'
    print(f'{name:<12} {aff:.2f} kcal/mol  MW={data["mw"]}  [{tag}]')
print('-'*60)
print('NG-007 baseline: -9.93 @ MW=576')
print('Target: -10.0 with MW<500')

with open(WORK_DIR / 'trim_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print('Saved: trim_docking/trim_results.json')
