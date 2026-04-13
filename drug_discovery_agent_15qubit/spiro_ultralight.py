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

# TRULY LIGHTWEIGHT - Simplified spiro-like structures (MW < 480)
# Based on the insight that NG-007's spiro-THF gave -9.93 but was heavy
# Now we use smaller P2 mimetics

ULTRALIGHT = {
    # Strategy: Replace spiro-THF with smaller cyclic ethers
    'ULTRA-001': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2COCCO2)c3ccc(F)cc3',  # Dioxolane, MW~445
    'ULTRA-002': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2COCCO2)c3cc(F)cc(F)c3',  # Dioxolane + DiF, MW~463
    'ULTRA-003': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2COCCO2)c3cc(F)c(F)c(F)c3',  # Dioxolane + TriF, MW~481
    
    # Strategy: Tetrahydrofuran (THF) - lighter than spiro
    'ULTRA-004': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2CCCO2)c3ccc(F)cc3',  # THF, MW~429
    'ULTRA-005': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2CCCO2)c3cc(F)cc(F)c3',  # THF + DiF, MW~447
    'ULTRA-006': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2CCCO2)c3cc(F)c(F)c(F)c3',  # THF + TriF, MW~465
    
    # Strategy: Minimal - just hydroxyethyl (no P2 ring)
    'ULTRA-007': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)CCO)c3ccc(F)cc3',  # No ring, MW~417
    'ULTRA-008': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)CCO)c3cc(F)cc(F)c3',  # No ring + DiF, MW~435
    
    # Strategy: Keep naphthalene but use smaller P2 (based on OPT-013's success)
    'ULTRA-009': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2CCCO2)c3ccc4ccccc4c3',  # THF + naphthalene, MW~479
    'ULTRA-010': 'Cc1cnc(C(=O)C(=O)O)cc1C(=O)N[C@H](C[C@@H](O)CNC(=O)C2COCCO2)c3ccc4ccccc4c3',  # Dioxolane + naphthalene, MW~495
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
print("🎯 ULTRALIGHT OPTIMIZATION (MW < 480, Target: Beat -9.93)")
print("=" * 80)
print(f"\n{'Candidate':<12} {'MW':<6} {'P2 Group':<20} {'Aromatic':<15}")
print("-" * 80)

results = {}
for name, smiles in ULTRALIGHT.items():
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        mw = round(Descriptors.MolWt(mol))
        
        # Determine P2 group
        if 'COCCO' in smiles:
            p2 = "Dioxolane"
        elif 'CCCO' in smiles:
            p2 = "THF"
        else:
            p2 = "Hydroxyethyl"
        
        # Determine aromatic
        if 'c4ccc5ccccc5c4' in smiles:
            aromatic = "Naphthalene"
        elif 'c(F)cc(F)c' in smiles or 'cc(F)cc(F)c' in smiles:
            if smiles.count('F') == 2:
                aromatic = "DiFluorobenzene"
            elif smiles.count('F') == 3:
                aromatic = "TriFluorobenzene"
            else:
                aromatic = "Fluorobenzene"
        else:
            aromatic = "Fluorobenzene"
        
        print(f"{name:<12} {mw:<6} {p2:<20} {aromatic:<15}")
        results[name] = {'smiles': smiles, 'mw': mw, 'p2_group': p2, 'aromatic': aromatic}
    else:
        print(f"{name:<12} {'INVALID':<6} {'Check SMILES':<20} {'-':<15}")

print("\n" + "=" * 80)
print("🚀 Running docking simulations...")
print("=" * 80)

for name, data in results.items():
    print(f"\n[{name}] MW={data['mw']} | P2={data['p2_group']} | {data['aromatic']}")
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
with open(WORK_DIR / 'ultralight_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved: nextgen_docking/ultralight_results.json")

# Highlight best candidate
if sorted_r:
    best_name, best_data = sorted_r[0]
    print(f"\n🏆 BEST ULTRALIGHT CANDIDATE: {best_name}")
    print(f"   Affinity: {best_data['affinity']:.2f} kcal/mol")
    print(f"   MW: {best_data['mw']}")
    print(f"   P2 Group: {best_data['p2_group']}")
    print(f"   Aromatic: {best_data['aromatic']}")
    
    if best_data['affinity'] < -9.93:
        print(f"\n🎉 SUCCESS! Beat NG-007 with lower MW!")
        print(f"   → SMILES: {best_data['smiles']}")
    elif best_data['affinity'] <= -10.0:
        print(f"\n🔥 CLINICAL CANDIDATE ACHIEVED!")
    else:
        print(f"\n📊 NG-007 remains best at -9.93")

print("\n" + "=" * 80)
print("💡 KEY INSIGHTS FROM THIS ROUND:")
print("=" * 80)
print("""
1. OPT-013 proved 3x Fluorine is better than 2x (-9.26 vs -9.10)
2. Simple benzyls (OPT-013) max out around -9.3 without P2 groups
3. NG-007's spiro-THF gives -9.93 but MW=576 is too heavy
4. ULTRA candidates test lighter P2 groups (THF, Dioxolane) at MW<480
5. Target: Find P2 mimetic that gives -9.9+ at MW<450
""")

