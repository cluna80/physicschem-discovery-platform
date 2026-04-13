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

# SUPER SIMPLE - Based on OPT-013 success with 3x Fluorine
# No heavy P2 groups - just optimized fluorination patterns
# These are direct analogs of what worked in your best simple benzyls

SUPER_SIMPLE = {
    # Based on OPT-013 (3x Fluorine, -9.26) - optimize further
    'SIMPLE-001': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccc4ccccc4c3',  # 3F on benzyl, MW~492
    'SIMPLE-002': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccc(F)cc3',  # 3F benzyl + F-benzene, MW~460
    'SIMPLE-003': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccccc3',  # 3F benzyl + benzene, MW~442
    
    # Best from OPT-011 (2F, -9.10) - add more fluorine
    'SIMPLE-004': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc(F)cc3',  # 2F benzyl + F-benzene, MW~460
    'SIMPLE-005': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccccc3',  # 2F benzyl + benzene, MW~442
    
    # Direct naphthalene with different fluorination (based on OPT-016-020)
    'SIMPLE-006': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(F)ccc3c2',  # Fluoro-naphthalene, MW~352
    'SIMPLE-007': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(F)c(F)c(F)c3c2',  # TriF-naphthalene, MW~388
    'SIMPLE-008': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc2ccc3cc(C(F)(F)F)ccc3c2',  # CF3-naphthalene, MW~402
    
    # Hybrid: naphthalene + benzyl (best of both worlds)
    'SIMPLE-009': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)c(F)c(F)c2)c3ccc4ccccc4c3',  # Same as SIMPLE-001
    'SIMPLE-010': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@@H](Cc2cc(F)cc(F)c2)c3ccc4ccccc4c3',  # 2F benzyl + naphthalene, MW~474
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
print("🎯 SUPER SIMPLE OPTIMIZATION (Based on OPT-013 success)")
print("=" * 80)
print(f"\n{'Candidate':<12} {'MW':<6} {'Structure':<40}")
print("-" * 80)

results = {}
for name, smiles in SUPER_SIMPLE.items():
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        mw = round(Descriptors.MolWt(mol))
        
        # Determine structure type
        if 'C@@H' in smiles:
            struct = "Benzyl + "
            if 'c4ccc5ccccc5c4' in smiles:
                struct += "Naphthalene"
            elif 'c3ccc(F)cc3' in smiles:
                struct += "Fluorobenzene"
            else:
                struct += "Benzene"
        else:
            struct = "Direct naphthalene"
        
        print(f"{name:<12} {mw:<6} {struct:<40}")
        results[name] = {'smiles': smiles, 'mw': mw, 'structure': struct}
    else:
        print(f"{name:<12} {'INVALID':<6} {'Check SMILES':<40}")

print("\n" + "=" * 80)
print("🚀 Running docking simulations...")
print("=" * 80)

for name, data in results.items():
    print(f"\n[{name}] MW={data['mw']} | {data['structure']}")
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
            elif aff <= -9.0:
                tag = "📊 DECENT"
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
    elif aff <= -9.0:
        tag = "📊 DECENT"
    else:
        tag = "⚠️ MODERATE"
    
    print(f"{name:<12} {aff:>6.2f} kcal/mol  CNN={cnn_best:>6.3f}  MW={data['mw']:>3}  LE={le_score:>5.2f}  {tag}")

print("-" * 80)

# Save results
with open(WORK_DIR / 'super_simple_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved: nextgen_docking/super_simple_results.json")

# Highlight best candidate
if sorted_r:
    best_name, best_data = sorted_r[0]
    print(f"\n🏆 BEST SIMPLE CANDIDATE: {best_name}")
    print(f"   Affinity: {best_data['affinity']:.2f} kcal/mol")
    print(f"   MW: {best_data['mw']}")
    print(f"   Structure: {best_data['structure']}")
    
    if best_data['affinity'] < -9.93:
        print(f"\n🎉 SUCCESS! Beat NG-007 with simpler structure!")
        print(f"   → SMILES: {best_data['smiles']}")
    elif best_data['affinity'] <= -10.0:
        print(f"\n🔥 CLINICAL CANDIDATE ACHIEVED!")
    elif best_data['affinity'] > -9.0:
        print(f"\n📊 OPT-013 remains best simple at -9.26")
        print(f"   NG-007 still leads at -9.93")

print("\n" + "=" * 80)
print("💡 KEY INSIGHTS:")
print("=" * 80)
print("""
1. OPT-013 (3F benzyl + naphthalene): -9.26 @ MW=492
2. OPT-011 (2F benzyl + naphthalene): -9.10 @ MW=474  
3. NG-007 (spiro-THF + naphthalene): -9.93 @ MW=576
4. The spiro-THF adds ~0.7 kcal/mol but costs ~100 MW
5. Can we get -9.8+ with MW<480? That's the target!
""")

