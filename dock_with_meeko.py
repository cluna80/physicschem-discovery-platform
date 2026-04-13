# -*- coding: utf-8 -*-
"""
Dock HIV candidates using Meeko for proper PDBQT generation
No Mode 1 +10.000 issues!
"""

import subprocess
import os
import json
from meeko_utils import smiles_to_pdbqt_meeko

# Your best candidate from quantum analysis
CANDIDATES = [
    {
        'name': 'CURE_8G_001',
        'smiles': 'Oc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'THP ring + hydroxyl on naphthalene',
        'expected_boost': 0.6
    },
    {
        'name': 'CURE_7G_007',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'THP ring (baseline)',
        'expected_boost': 0
    }
]

def dock_meeko(ligand_file, binding_site, output_file):
    """Run Vina docking with Meeko-prepared ligand"""
    cmd = [
        "./bin/vina.exe",
        "--receptor", "hiv_protease.pdbqt",
        "--ligand", ligand_file,
        "--center_x", str(binding_site[0]),
        "--center_y", str(binding_site[1]),
        "--center_z", str(binding_site[2]),
        "--size_x", "20",
        "--size_y", "20",
        "--size_z", "20",
        "--out", output_file,
        "--num_modes", "9",
        "--exhaustiveness", "16",
        "--cpu", "6"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse affinities (should be clean with Meeko!)
    affinities = []
    for line in result.stdout.split('\n'):
        line = line.strip()
        if line and line[0].isdigit():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    affinities.append(float(parts[1]))
                except:
                    continue
    
    return affinities, result.stdout

print("="*80)
print("DOCKING WITH MEEKO (No obabel issues!)")
print("="*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print(f"Binding site: ({binding_site[0]:.3f}, {binding_site[1]:.3f}, {binding_site[2]:.3f})")
print("-"*80)

results = []

for cand in CANDIDATES:
    print(f"\n{'='*80}")
    print(f"Compound: {cand['name']}")
    print(f"Feature: {cand['feature']}")
    print("-"*60)
    
    ligand_file = f"{cand['name']}_meeko.pdbqt"
    
    print("  Converting to PDBQT with Meeko...")
    if smiles_to_pdbqt_meeko(cand['smiles'], ligand_file):
        print("  ✓ PDBQT generated successfully")
        
        print("  Running AutoDock Vina...")
        affinities, output = dock_meeko(ligand_file, binding_site, f"{cand['name']}_meeko_result.pdbqt")
        
        if affinities:
            # Filter valid affinities (negative values, not 10.000)
            valid = [a for a in affinities if a < 5 and a > -20]
            
            if valid:
                best_aff = min(valid)
                results.append({
                    'name': cand['name'],
                    'feature': cand['feature'],
                    'affinity': best_aff,
                    'all_modes': affinities
                })
                print(f"\n  Binding Affinities (Meeko-generated ligand):")
                for i, aff in enumerate(affinities[:5], 1):
                    marker = "★" if aff == best_aff else " "
                    print(f"    {marker} Mode {i}: {aff:.3f} kcal/mol")
                print(f"\n  ✓ Best affinity: {best_aff:.3f} kcal/mol")
            else:
                print(f"  ✗ No valid affinities (all >5)")
        else:
            print("  ✗ No affinities parsed")
    else:
        print("  ✗ Meeko conversion failed")

# Sort results
results.sort(key=lambda x: x['affinity'])

print("\n" + "="*80)
print("FINAL RESULTS (Meeko - No Mode 1 Issues)")
print("="*80)
print(f"\n{'Rank':<6} {'Compound':<15} {'Feature':<35} {'Affinity':<12}")
print("-"*80)

for i, r in enumerate(results, 1):
    print(f"{i:<6} {r['name']:<15} {r['feature'][:33]:<35} {r['affinity']:<12.3f}")

if results:
    best = results[0]
    print("\n" + "="*80)
    print("BEST CANDIDATE")
    print("="*80)
    print(f"Compound: {best['name']}")
    print(f"Feature: {best['feature']}")
    print(f"Binding Affinity: {best['affinity']:.3f} kcal/mol")
    print(f"Gap to -9.0: {best['affinity'] - (-9.0):.2f} kcal/mol")
    
    # Compare with previous
    if len(results) > 1:
        baseline = results[-1]['affinity'] if results[-1]['name'] == 'CURE_7G_007' else None
        if baseline:
            improvement = best['affinity'] - baseline
            print(f"\nImprovement over baseline: {improvement:+.2f} kcal/mol")
    
    # Save results
    with open("meeko_docking_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nSaved: meeko_docking_results.json")

print("\n" + "="*80)
