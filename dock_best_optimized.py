# -*- coding: utf-8 -*-
"""
Dock the best optimized analog of HIV_CURE_070
"""

import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem
import json

def smiles_to_pdbqt(smiles, output_file):
    """Convert SMILES to 3D PDBQT"""
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
        print(f"Error: {e}")
    return False

# Load all analogs
with open("optimized_analogs.json", 'r') as f:
    all_analogs = json.load(f)

# Sort by predicted affinity (best first)
all_analogs.sort(key=lambda x: x['predicted_affinity'])

# Get the best one (should be CURE_079)
best = all_analogs[0]

print("="*80)
print("BEST OPTIMIZED ANALOG FROM QUANTUM SCREENING")
print("="*80)
print(f"Name: {best['name']}")
print(f"Modification: {best['modification']}")
print(f"SMILES: {best['smiles']}")
print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"Molecular Weight: {best['mw']:.0f} Da")
print(f"LogP: {best['logp']:.2f}")
print("-"*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = f"{best['name']}.pdbqt"
if smiles_to_pdbqt(best['smiles'], ligand_file):
    print(f"  Successfully created {ligand_file}")
else:
    print("  Error converting molecule")
    exit()

# Run docking
print("\n[2/2] Docking into HIV-1 Protease...")
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
    "--out", f"{best['name']}_result.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "16"
]

print("  Running AutoDock Vina (30-60 seconds)...")
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
                pass

print("\n" + "="*80)
print("DOCKING RESULTS")
print("="*80)

if affinities:
    # Find best affinity (ignore Mode 1 if it's 10.0)
    valid_affinities = [a for a in affinities if a < 5]
    if valid_affinities:
        best_affinity = min(valid_affinities)
    else:
        best_affinity = affinities[0]
    
    print(f"\nBinding Affinities (kcal/mol):")
    for i, aff in enumerate(affinities[:9], 1):
        marker = "★" if aff == best_affinity else " "
        print(f"  {marker} Mode {i}: {aff:.3f} kcal/mol")
    
    print(f"\nBest binding affinity: {best_affinity:.3f} kcal/mol")
    print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
    print(f"Difference: {best_affinity - best['predicted_affinity']:.2f} kcal/mol")
    
    # Compare with original
    original_affinity = -4.05
    improvement = best_affinity - original_affinity
    
    print(f"\nComparison with original HIV_CURE_070:")
    print(f"  Original: {original_affinity:.3f} kcal/mol")
    print(f"  Analog:   {best_affinity:.3f} kcal/mol")
    print(f"  Improvement: {improvement:.2f} kcal/mol")
    
    # Classification
    print("\n" + "-"*80)
    if best_affinity < -7:
        print("✓ EXCELLENT! This analog reaches strong binder threshold!")
        print("  This molecule has HIV drug candidate potential!")
    elif best_affinity < -5.5:
        print("✓ GOOD! This analog is approaching drug candidate range")
        print("  Close to HIV drug potency!")
    elif best_affinity < -4.5:
        print("✓ MODERATE! Improvement over original")
        print("  Further optimization needed")
    else:
        print("⚠️ Needs further optimization")
    
    # Save results
    with open(f"{best['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {best['name']}_result.pdbqt")
    
    # Also show all analogs for comparison
    print("\n" + "="*80)
    print("ALL ANALOGS - PREDICTED VS ACTUAL")
    print("="*80)
    print(f"\n{'Name':<12} {'Modification':<25} {'Predicted':<12} {'Actual':<12} {'Diff':<10}")
    print("-"*75)
    
    # Update the best analog with actual value
    best['actual_affinity'] = best_affinity
    
    for a in all_analogs[:5]:
        predicted = a['predicted_affinity']
        if a['name'] == best['name']:
            actual = best_affinity
            diff = actual - predicted
            marker = "★"
        else:
            actual = "Not docked"
            diff = "N/A"
            marker = " "
        print(f"{marker} {a['name']:<11} {a['modification'][:23]:<25} {predicted:<12.2f} {actual if isinstance(actual, float) else actual:<12} {diff if isinstance(diff, float) else diff:<10}")
    
else:
    print("\nNo binding affinities found")

print("="*80)
