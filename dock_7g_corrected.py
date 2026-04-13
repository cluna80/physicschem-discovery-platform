# -*- coding: utf-8 -*-
"""
Dock top CURE_7G candidates with corrected binding site
"""

import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem
import json

def smiles_to_pdbqt(smiles, output_file):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            
            pdb_file = output_file.replace('.pdbqt', '.pdb')
            Chem.MolToPDBFile(mol, pdb_file)
            
            result = subprocess.run(
                ["obabel", pdb_file, "-O", output_file, "-xh"],
                capture_output=True
            )
            
            if os.path.exists(pdb_file):
                os.remove(pdb_file)
            
            return result.returncode == 0
    except Exception as e:
        print(f"  Error: {e}")
    return False

# Load corrected binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Top candidates from quantum analysis
CANDIDATES = [
    {
        "name": "CURE_7G_007",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1",
        "feature": "THP ring (6-membered O-ring)",
        "real_score": 2.335
    },
    {
        "name": "CURE_7G_008",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)CC(C)C)ccc2c1",
        "feature": "Isobutyl (low MW, high LogP)",
        "real_score": 2.326
    },
    {
        "name": "CURE_7G_005",
        "smiles": "c1cc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2cc1F",
        "feature": "Fluoronaphthyl",
        "real_score": 2.263
    },
    {
        "name": "CURE_7G_003",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "feature": "Naphthalene + bis-THF",
        "real_score": 2.1
    },
]

print("="*80)
print("DOCKING TOP CURE_7G CANDIDATES (Corrected Site)")
print(f"Binding site: ({binding_site[0]:.3f}, {binding_site[1]:.3f}, {binding_site[2]:.3f})")
print("="*80)

results = []

for comp in CANDIDATES:
    print(f"\n{'='*80}")
    print(f"Compound: {comp['name']}")
    print(f"Feature: {comp['feature']}")
    print(f"Real Score: {comp['real_score']:.3f}")
    print("-"*60)
    
    ligand_file = f"{comp['name']}_corrected.pdbqt"
    
    if smiles_to_pdbqt(comp['smiles'], ligand_file):
        print("  ✓ 3D structure generated")
        
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
            "--out", f"{comp['name']}_corrected_result.pdbqt",
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
            valid = [a for a in affinities if a < 5]
            best_aff = min(valid) if valid else affinities[0]
            results.append({
                'name': comp['name'],
                'feature': comp['feature'],
                'real_score': comp['real_score'],
                'affinity': best_aff,
                'all_modes': affinities
            })
            print(f"\n  Binding Affinities:")
            for i, aff in enumerate(affinities[:5], 1):
                print(f"    Mode {i}: {aff:.3f} kcal/mol")
            print(f"\n  ✓ Best affinity: {best_aff:.3f} kcal/mol")
            
            if best_aff < -7.5:
                print("    ★★★ EXCELLENT! Very strong binder!")
            elif best_aff < -7:
                print("    ★★ GOOD! Strong binder!")
            elif best_aff < -6.5:
                print("    ★ MODERATE! Solid improvement!")
            elif best_aff < -6:
                print("    → Good progress")
            else:
                print("    → Needs further optimization")
        else:
            print("  ✗ Docking failed")
    else:
        print("  ✗ Could not generate 3D structure")

# Sort results by affinity
results.sort(key=lambda x: x['affinity'])

print("\n" + "="*80)
print("FINAL RANKING (Best to Worst)")
print("="*80)
print(f"\n{'Rank':<6} {'Compound':<15} {'Feature':<30} {'Affinity':<12} {'Real Score':<12}")
print("-"*80)

for i, r in enumerate(results, 1):
    print(f"{i:<6} {r['name']:<15} {r['feature'][:28]:<30} {r['affinity']:<12.3f} {r['real_score']:<12.3f}")

if results:
    best = results[0]
    print("\n" + "="*80)
    print("BEST CANDIDATE")
    print("="*80)
    print(f"Compound: {best['name']}")
    print(f"Feature: {best['feature']}")
    print(f"Binding Affinity: {best['affinity']:.3f} kcal/mol")
    print(f"Real Score: {best['real_score']:.3f}")
    print(f"Gap to -9.0: {best['affinity'] - (-9.0):.2f} kcal/mol")
    
    # Compare with CURE_4G_003
    print(f"\nComparison with baseline (CURE_4G_003):")
    print(f"  CURE_4G_003: -4.827 kcal/mol")
    print(f"  {best['name']}: {best['affinity']:.3f} kcal/mol")
    print(f"  Improvement: {best['affinity'] - (-4.827):+.2f} kcal/mol")
    
    if best['affinity'] < -7.5:
        print("\n✓✓✓ EXCELLENT! Strong HIV inhibitor candidate!")
    elif best['affinity'] < -7:
        print("\n✓✓ GOOD! Very promising!")
    elif best['affinity'] < -6.5:
        print("\n✓ MODERATE! Solid improvement!")
    else:
        print("\n→ Further optimization needed")
    
    # Save results
    with open("cure_7g_corrected_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nSaved: cure_7g_corrected_results.json")

print("\n" + "="*80)
