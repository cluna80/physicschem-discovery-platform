# -*- coding: utf-8 -*-
"""
Complete re-evaluation of all best compounds using Meeko
Get consistent, reliable affinities for all
"""

import subprocess
import os
import json
from meeko_utils import smiles_to_pdbqt_meeko

# All your best compounds with correct SMILES
COMPOUNDS = [
    {
        'name': 'CURE_4G_003',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCF',
        'feature': 'Trifluorophenyl + amide core'
    },
    {
        'name': 'CURE_5G_002',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1',
        'feature': 'Naphthalene + THF ring'
    },
    {
        'name': 'CURE_6G_002',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1',
        'feature': 'Same as 5G_002? Check'
    },
    {
        'name': 'CURE_7G_007',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'Naphthalene + THP ring'
    },
    {
        'name': 'CURE_8G_001',
        'smiles': 'Oc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'Hydroxynaphthalene + THP'
    }
]

print("="*80)
print("COMPLETE REEVALUATION WITH MEEKO")
print("Getting consistent binding affinities for all candidates")
print("="*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print(f"Binding site: ({binding_site[0]:.3f}, {binding_site[1]:.3f}, {binding_site[2]:.3f})")
print("-"*80)

results = []

for comp in COMPOUNDS:
    print(f"\n{'='*80}")
    print(f"Compound: {comp['name']}")
    print(f"Feature: {comp['feature']}")
    print("-"*60)
    
    ligand_file = f"{comp['name']}_meeko.pdbqt"
    
    if smiles_to_pdbqt_meeko(comp['smiles'], ligand_file):
        print("  ✓ PDBQT generated")
        
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
            "--out", f"{comp['name']}_meeko_result.pdbqt",
            "--num_modes", "9",
            "--exhaustiveness", "16",
            "--cpu", "6"
        ]
        
        print("  Running AutoDock Vina...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse affinities
        affinities = []
        for line in result.stdout.split('\n'):
            if line.strip() and line.strip()[0].isdigit():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        affinities.append(float(parts[1]))
                    except:
                        continue
        
        if affinities:
            valid = [a for a in affinities if a < 5 and a > -20]
            best_aff = min(valid) if valid else affinities[0]
            
            results.append({
                'name': comp['name'],
                'feature': comp['feature'],
                'affinity': best_aff,
                'all_modes': affinities
            })
            print(f"\n  Binding Affinities:")
            for i, aff in enumerate(affinities[:5], 1):
                marker = "★" if aff == best_aff else " "
                print(f"    {marker} Mode {i}: {aff:.3f} kcal/mol")
            print(f"\n  ✓ Best affinity: {best_aff:.3f} kcal/mol")
        else:
            print("  ✗ No affinities parsed")
    else:
        print("  ✗ PDBQT generation failed")

# Sort results
results.sort(key=lambda x: x['affinity'])

print("\n" + "="*80)
print("FINAL RANKING (Consistent Meeko Results)")
print("="*80)
print(f"\n{'Rank':<6} {'Compound':<15} {'Feature':<40} {'Affinity':<12}")
print("-"*80)

for i, r in enumerate(results, 1):
    print(f"{i:<6} {r['name']:<15} {r['feature'][:38]:<40} {r['affinity']:<12.3f}")

if results:
    best = results[0]
    print("\n" + "="*80)
    print("BEST CANDIDATE (Meeko-Validated)")
    print("="*80)
    print(f"Compound: {best['name']}")
    print(f"Feature: {best['feature']}")
    print(f"Binding Affinity: {best['affinity']:.3f} kcal/mol")
    print(f"Gap to -9.0: {best['affinity'] - (-9.0):.2f} kcal/mol")
    
    # Save
    with open("meeko_reevaluation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nSaved: meeko_reevaluation.json")
    
    # Next steps
    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print(f"Your best validated compound is {best['name']} at {best['affinity']:.3f} kcal/mol")
    print(f"To reach -9.0, you need {abs(best['affinity'] - (-9.0)):.2f} kcal/mol improvement")
    print("\nOptimization strategy:")
    print("  1. Add hydrogen bond donors (hydroxyl, amide)")
    print("  2. Optimize ring size (THP vs THF)")
    print("  3. Add halogens for electron tuning")
    print("  4. Extend hydrophobic chains")

print("="*80)
