#!/usr/bin/env python3
import json
import subprocess
import os
import time

print("="*80)
print("🔬 DOCKING NEW FRAGMENT COMBINATIONS")
print("Testing: New cores (Quinazoline) + New P1 (tert-Butyl, Trifluoromethoxy)")
print("         + New P2 (Piperazine) + New Linker (Thioamide)")
print("="*80)

with open("valid_candidates.json", "r") as f:
    candidates = json.load(f)

print(f"\n📊 Loaded {len(candidates)} candidates from fragment discovery")
print("\nCandidates being tested:")
for i, c in enumerate(candidates):
    print(f"  {i+1}. {c['core']} + {c['p1']} + {c['p2']} + {c['linker']}")

RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

# Verify files exist
if not os.path.exists(RECEPTOR):
    print(f"\n❌ Receptor not found: {RECEPTOR}")
    exit(1)
if not os.path.exists(REF_LIGAND):
    print(f"❌ Reference not found: {REF_LIGAND}")
    exit(1)

print(f"\n✅ Receptor: {RECEPTOR}")
print(f"✅ Reference: {REF_LIGAND}")

os.makedirs("new_fragment_docking", exist_ok=True)

results = []

print(f"\n🔬 Docking {len(candidates)} candidates...")
print("-"*80)

for i, cand in enumerate(candidates):
    print(f"\n[{i+1}/{len(candidates)}] {cand['core']}+{cand['p1']}+{cand['p2']}")
    
    # Convert SMILES to PDBQT
    pdbqt_file = f"new_fragment_docking/cand_{i+1}.pdbqt"
    cmd = f"echo '{cand['smiles']}' | obabel -ismi -opdbqt -O {pdbqt_file} -p 7.4 2>/dev/null"
    subprocess.run(cmd, shell=True)
    
    if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
        print("   ❌ PDBQT conversion failed")
        continue
    
    # Run Gnina
    output_file = f"new_fragment_docking/cand_{i+1}_out.pdbqt"
    cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 6 --num_modes 3 --exhaustiveness 6 --cpu 6 -o {output_file} 2>/dev/null"
    
    try:
        subprocess.run(cmd, shell=True, timeout=180)
    except subprocess.TimeoutExpired:
        print("   ⏰ Timeout")
        continue
    
    # Extract score
    vina = None
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
        with open(output_file, 'r') as f:
            for line in f:
                if "REMARK Vina score:" in line:
                    vina = float(line.split(':')[1].strip().split()[0])
                    break
    
    if vina:
        print(f"   ✅ Vina: {vina:.2f} kcal/mol")
        results.append({
            "core": cand['core'],
            "p1": cand['p1'],
            "p2": cand['p2'],
            "linker": cand['linker'],
            "vina": vina
        })
    else:
        print("   ❌ No score")

# Save results
with open("new_fragment_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("📊 NEW FRAGMENT DOCKING RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    print(f"\n{'Rank':<4} {'Core':<12} {'P1':<12} {'P2':<12} {'Linker':<12} {'Vina':<8}")
    print("-"*70)
    for i, r in enumerate(sorted_results):
        print(f"{i+1:<4} {r['core']:<12} {r['p1']:<12} {r['p2']:<12} {r['linker']:<12} {r['vina']:<8.2f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST NEW FRAGMENT COMBINATION:")
    print(f"   {best['core']} + {best['p1']} + {best['p2']} + {best['linker']}")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    
    print(f"\n📊 COMPARISON:")
    print(f"   Current Best (naphthalene_metaCF3): -11.357 kcal/mol")
    print(f"   CURE_17G_002: -11.180 kcal/mol")
    
    if best['vina'] < -11.357:
        print(f"\n✅ NEW LEAD! Better by {abs(best['vina'] + 11.357):.3f} kcal/mol!")
    elif best['vina'] < -11.18:
        print(f"\n✅ Beats CURE_17G_002 by {abs(best['vina'] + 11.18):.3f} kcal/mol")
        print(f"   Gap to best: {best['vina'] + 11.357:.3f} kcal/mol")
    else:
        print(f"\n📈 Gap to best: {best['vina'] + 11.357:.3f} kcal/mol")
else:
    print("\n❌ No successful dockings")

print("="*80)
