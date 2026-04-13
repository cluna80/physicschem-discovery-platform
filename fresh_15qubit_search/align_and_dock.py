#!/usr/bin/env python3
"""
Align and dock ligands using the original binding pose as reference
"""

import subprocess
import os
import json

print("="*80)
print("🔬 ALIGNING AND DOCKING LIGANDS")
print("="*80)

# Reference ligand (original CURE_17G_002)
REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"
if not os.path.exists(REF_LIGAND):
    REF_LIGAND = "docking_results/cand_1.pdbqt"

RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"

print(f"Receptor: {RECEPTOR}")
print(f"Reference: {REF_LIGAND}")

# Your working ligands from the fragment discovery
ligands = [
    ("naphthalene_35diF", "docking_results/naphthalene_35diF.pdbqt"),
    ("indole_metaCF3", "docking_results/indole_metaCF3.pdbqt"),
    ("isoquinoline_35diF", "docking_results/isoquinoline_35diF.pdbqt"),
    ("naphthalene_metaF", "docking_results/naphthalene_metaF.pdbqt"),
]

print("\n📊 Testing ligands:")
for name, path in ligands:
    if os.path.exists(path):
        print(f"   ✅ {name}: {path}")
    else:
        print(f"   ❌ {name}: not found")

print("\n" + "="*80)
print("🔬 DOCKING WITH AUTOCENTER")
print("="*80)

results = []

for name, pdbqt_file in ligands:
    if not os.path.exists(pdbqt_file):
        continue
    
    print(f"\n[{name}]")
    
    # Use the reference ligand for autobox
    output_file = f"aligned_{name}_out.pdbqt"
    
    # Run Gnina with the reference ligand as autobox
    cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 8 --num_modes 5 --exhaustiveness 8 --cpu 6 -o {output_file} 2>&1 | grep -E 'Vina|CNN|mode|affinity|-----' | head -20"
    
    subprocess.run(cmd, shell=True)
    
    # Extract score from output file
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if "REMARK Vina score:" in line:
                    vina = line.split(':')[1].strip().split()[0]
                    print(f"   ✅ Score: {vina} kcal/mol")
                    results.append({"name": name, "vina": float(vina)})
                    break
    else:
        print("   ❌ No output file")

print("\n" + "="*80)
print("📊 RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    print(f"\n{'Rank':<4} {'Compound':<20} {'Vina':<10}")
    print("-"*40)
    for i, r in enumerate(sorted_results):
        print(f"{i+1:<4} {r['name']:<20} {r['vina']:<10.2f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST: {best['name']} at {best['vina']:.2f} kcal/mol")
    print(f"\nReference: naphthalene_metaCF3 = -11.357 kcal/mol")
    if best['vina'] < -11.357:
        print(f"✅ NEW LEAD! Better by {abs(best['vina'] + 11.357):.3f} kcal/mol!")
else:
    print("\n❌ No successful dockings")

print("="*80)
