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

# LIGHTWEIGHT SPIRO-THF CANDIDATES (MW < 500)
SPIRO_LIGHT = {
    # Strategy 1: Fluorobenzene variants (best from OPT-011/013)
    'SPIRO-001': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c4ccc(F)cc4',  # MonoF, MW~480
    'SPIRO-002': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c4cc(F)cc(F)c4',  # DiF, MW~498
    'SPIRO-003': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c4cc(F)c(F)c(F)c4',  # TriF, MW~516 (slightly over)
    
    # Strategy 2: Pyridine variants (better solubility)
    'SPIRO-004': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c4ccncc4',  # Pyridine, MW~463
    'SPIRO-005': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCCO[C@H]23)c4cc(F)cnc4',  # Fluoropyridine, MW~481
    
    # Strategy 3: Smaller spiro ring (reduce MW further)
    'SPIRO-006': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCOC3)c4ccc(F)cc4',  # Small spiro + F, MW~466
    'SPIRO-007': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCOC3)c4cc(F)cc(F)c4',  # Small spiro + DiF, MW~484
    'SPIRO-008': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)[C@@H]2CO[C@@H]3CCOC3)c4ccncc4',  # Small spiro + pyridine, MW~449
}

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
print("🎯 LIGHTWEIGHT SPIRO-THF OPTIMIZATION (Target: Beat -9.93)")
print("=" * 80)
print(f"\n{'Candidate':<12} {'MW':<6} {'Aromatic':<20} {'Spiro Type':<15}")
print("-" * 80)

results = {}
for name, smiles in SPIRO_LIGHT.items():
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        mw = round(Descriptors.MolWt(mol))
        
        # Determine aromatic type
        if smiles.count('F') == 1 and 'ccc(F)cc' in smiles:
            aromatic = "MonoFluorobenzene"
        elif smiles.count('F') == 2:
            aromatic = "DiFluorobenzene"
        elif smiles.count('F') == 3:
            aromatic = "TriFluorobenzene"
        elif 'ccncc' in smiles and 'F' in smiles:
            aromatic = "Fluoropyridine"
        elif 'ccncc' in smiles:
            aromatic = "Pyridine"
        else:
            aromatic = "Other"
        
        # Spiro type
        if 'CCCO[C@H]' in smiles:
            spiro_type = "Full spiro-THF"
        else:
            spiro_type = "Small spiro"
        
        print(f"{name:<12} {mw:<6} {aromatic:<20} {spiro_type:<15}")
        results[name] = {'smiles': smiles, 'mw': mw, 'aromatic': aromatic, 'spiro_type': spiro_type}
    else:
        print(f"{name:<12} {'INVALID':<6} {'Check SMILES':<20} {'-':<15}")

print("\n" + "=" * 80)
print("🚀 Running docking simulations...")
print("=" * 80)

for name, data in results.items():
    print(f"\n[{name}] MW={data['mw']} | {data['aromatic']} | {data['spiro_type']}")
    sdf = smiles_to_sdf(name, data['smiles'])
    if sdf:
        aff, all_aff, cnn = dock(name, sdf)
        data['affinity'] = aff
        data['cnn_scores'] = cnn
        if aff:
            if aff <= -10.0:
                tag = "🔥 CLINICAL"
            elif aff <= -9.93:
                tag = "✅ BEATS NG-007!"
            elif aff <= -9.5:
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
    elif aff <= -9.93:
        tag = "✅ BEATS NG-007!"
    elif aff <= -9.5:
        tag = "👍 GOOD"
    else:
        tag = "⚠️ MODERATE"
    
    print(f"{name:<12} {aff:>6.2f} kcal/mol  CNN={cnn_best:>6.3f}  MW={data['mw']:>3}  LE={le_score:>5.2f}  {tag}")

print("-" * 80)

# Save results (FIXED JSON)
with open(WORK_DIR / 'spiro_light_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved: nextgen_docking/spiro_light_results.json")

# Highlight best candidate
if sorted_r:
    best_name, best_data = sorted_r[0]
    print(f"\n🏆 BEST SPIRO-THF CANDIDATE: {best_name}")
    print(f"   Affinity: {best_data['affinity']:.2f} kcal/mol")
    print(f"   MW: {best_data['mw']}")
    print(f"   Aromatic: {best_data['aromatic']}")
    print(f"   Spiro Type: {best_data['spiro_type']}")
    
    if best_data['affinity'] < -9.93:
        print(f"\n🎉 CLINICAL CANDIDATE! BEAT NG-007!")
        print(f"   → SMILES: {best_data['smiles']}")
        print(f"   → File provisional patent immediately")
    elif best_data['affinity'] <= -10.0:
        print(f"\n🔥 EXCELLENT! Clinical candidate territory!")
    else:
        print(f"\n✅ Good candidate, continue optimization")

