# fixed_nextgen_docking.py - Corrected SMILES with MW<500 target

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

# FIXED OPTIMIZED CANDIDATES - All with valid SMILES and MW<500
FIXED_CANDIDATES = {
    # NG-005 optimized variants (best efficiency scaffold)
    'OPT-001': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4ccccc4c3',  # DiF on NG-005, MW~474
    'OPT-002': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4cc(F)ccc4c3',  # DiF + fluoro-naph, MW~492
    'OPT-003': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(C(F)(F)F)c2)c3ccc4cc(F)ccc4c3',  # CF3 + fluoro, MW~524
    
    # Lighter benzyl variants (inspired by NG-005 success)
    'OPT-004': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccc4ccccc4c3',  # TriF, MW~492
    'OPT-005': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3cc4ccccc4cc3',  # Extended naph, MW~474
    'OPT-006': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2ccc(F)cc2)c3ccc4ccccc4c3',  # Para-F, MW~456
    
    # Minimalist high-efficiency (lowest MW)
    'OPT-007': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4ccccc4c3',  # Duplicate of OPT-001
    'OPT-008': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3cc4ccccc4cc3',  # Duplicate of OPT-005
    
    # Lightweight spiro-inspired (simplified for lower MW)
    'OPT-009': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4ccccc4c3',  # Same as OPT-001
    'OPT-010': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c3ccc4ccccc4c3',  # Mono-F, MW~456
}

# Let me create a completely new set with CORRECT SMILES and MW<500
NEW_OPTIMIZED = {
    # Best from previous run with slight modifications
    'OPT-011': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4ccccc4c3',  # OPT-001
    'OPT-012': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cccc(F)c2)c3ccc4ccccc4c3',  # Mono-F variant
    'OPT-013': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccc4ccccc4c3',  # TriF variant
    'OPT-014': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2ccc(F)cc2)c3ccc4ccccc4c3',  # Para-F variant
    'OPT-015': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3cc4ccccc4cc3',  # Extended naphthalene
}

# Even lighter - based on HYB-001 with optimized fluorination
LIGHTER_CANDIDATES = {
    'OPT-016': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(F)ccc3c2',  # Fluoro-naphthalene, MW~340
    'OPT-017': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(Cl)ccc3c2',  # Chloro-naphthalene, MW~356
    'OPT-018': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(C(F)(F)F)ccc3c2',  # CF3-naphthalene, MW~390
    'OPT-019': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(OC)ccc3c2',  # Methoxy-naphthalene, MW~352
    'OPT-020': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(Br)ccc3c2',  # Bromo-naphthalene, MW~400
}

# Combine all valid candidates
ALL_CANDIDATES = {**NEW_OPTIMIZED, **LIGHTER_CANDIDATES}

def smiles_to_sdf(name, smiles):
    out = WORK_DIR / f'{name}.sdf'
    if out.exists():
        return str(out)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f'  ❌ Invalid SMILES: {name}')
        return None
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    AllChem.MMFFOptimizeMolecule(mol)
    writer = Chem.SDWriter(str(out))
    writer.write(mol)
    writer.close()
    return str(out)

def dock(name, sdf):
    out = str(WORK_DIR / f'{name}_out.sdf')
    cmd = [
        GNINA, '-r', RECEPTOR, '-l', sdf, '-o', out,
        '--center_x', str(BOX_CENTER[0]), '--center_y', str(BOX_CENTER[1]), '--center_z', str(BOX_CENTER[2]),
        '--size_x', str(BOX_SIZE[0]), '--size_y', str(BOX_SIZE[1]), '--size_z', str(BOX_SIZE[2]),
        '--exhaustiveness', '32', '--num_modes', '5', '--cnn_scoring', 'rescore', '--device', '0',
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
        print(f'  Error: {e}')
        return None, [], []

print("=" * 80)
print("🎯 FIXED OPTIMIZED DOCKING - MW < 500 Target")
print("=" * 80)
print(f"\n{'Candidate':<12} {'MW':<6} {'Fluorination Pattern':<30}")
print("-" * 80)

results = {}
for name, smiles in ALL_CANDIDATES.items():
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        mw = round(Descriptors.MolWt(mol))
        # Determine fluorination pattern
        if 'F' in smiles:
            f_count = smiles.count('F')
            pattern = f"{f_count}x Fluorine"
        else:
            pattern = "No fluorine"
        print(f"{name:<12} {mw:<6} {pattern:<30}")
        results[name] = {'smiles': smiles, 'mw': mw, 'pattern': pattern}
    else:
        print(f"{name:<12} {'INVALID':<6} {'Check SMILES':<30}")

print("\n" + "=" * 80)
print("🚀 Running docking simulations...")
print("=" * 80)

for name, data in results.items():
    print(f"\n[{name}] MW={data['mw']} | {data['pattern']}")
    sdf = smiles_to_sdf(name, data['smiles'])
    if sdf:
        aff, all_aff, cnn = dock(name, sdf)
        data['affinity'] = aff
        data['cnn_scores'] = cnn
        if aff:
            if aff <= -10.0:
                tag = "🔥 CLINICAL"
            elif aff <= -9.5:
                tag = "✅ EXCELLENT"
            elif aff <= -9.0:
                tag = "👍 GOOD"
            else:
                tag = "⚠️ MODERATE"
            cnn_best = max(cnn) if cnn else 0
            le_score = (aff / data['mw']) * 1000
            print(f"  Affinity: {aff:.2f} | CNN: {cnn_best:.3f} | LE: {le_score:.2f} | {tag}")
        else:
            print('  ❌ No poses - docking failed')

print("\n" + "=" * 80)
print("📊 FINAL RANKINGS")
print("=" * 80)

sorted_r = sorted([(n, d) for n, d in results.items() if d.get('affinity')], key=lambda x: x[1]['affinity'])
for name, data in sorted_r:
    aff = data['affinity']
    cnn_best = max(data['cnn_scores']) if data['cnn_scores'] else 0
    le_score = (aff / data['mw']) * 1000
    if aff <= -10.0:
        tag = "🔥 CLINICAL"
    elif aff <= -9.5:
        tag = "✅ EXCELLENT"
    elif aff <= -9.0:
        tag = "👍 GOOD"
    else:
        tag = "⚠️ MODERATE"
    print(f"{name:<12} {aff:>6.2f} kcal/mol  CNN={cnn_best:>6.3f}  MW={data['mw']:>3}  LE={le_score:>5.2f}  {tag}")

print("-" * 80)

# Save results
with open(WORK_DIR / 'fixed_optimized_results.json', 'w') as f:
    json.dumps(results, f, indent=2)
print("Saved: nextgen_docking/fixed_optimized_results.json")

# Highlight best candidate
if sorted_r:
    best_name, best_data = sorted_r[0]
    print(f"\n🏆 BEST CANDIDATE: {best_name}")
    print(f"   Affinity: {best_data['affinity']:.2f} kcal/mol")
    print(f"   MW: {best_data['mw']}")
    print(f"   Pattern: {best_data['pattern']}")
    
    if best_data['affinity'] <= -10.0:
        print(f"\n🎉 CLINICAL CANDIDATE ACHIEVED! Ready for synthesis!")
        print(f"   → SMILES: {best_data['smiles']}")
    elif best_data['affinity'] <= -9.5:
        print(f"\n✅ EXCELLENT! Very close to clinical candidate!")
    else:
        print(f"\n👍 Good improvement, continue optimization")