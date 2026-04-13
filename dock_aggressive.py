# -*- coding: utf-8 -*-
"""
Dock the most aggressive analog to reach -7.0 kcal/mol
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
        print(f"Error: {e}")
    return False

# Load aggressive analogs
with open("aggressive_analogs.json", 'r') as f:
    analogs = json.load(f)

# Pick the best candidate (CURE_3G_005 with sulfonamide)
best = [a for a in analogs if 'CURE_3G_005' in a['name']][0]

print("="*80)
print(f"DOCKING AGGRESSIVE ANALOG: {best['name']}")
print("="*80)
print(f"Modification: {best['modification']}")
print(f"Description: {best['description']}")
print(f"SMILES: {best['smiles']}")
print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"Target: -7.0 kcal/mol")
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

print("  Running AutoDock Vina (1-2 minutes)...")
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
    
    print(f"\nImprovement Path:")
    print(f"  Original (CURE_070):        -4.05 kcal/mol")
    print(f"  First Gen (CURE_076):       -4.27 kcal/mol")
    print(f"  Second Gen (CURE_2G_001):   -4.25 kcal/mol")
    print(f"  Aggressive ({best['name']}): {best_affinity:.3f} kcal/mol")
    print(f"  Total improvement: {best_affinity - (-4.05):.2f} kcal/mol")
    
    print("\n" + "-"*80)
    if best_affinity < -7:
        print("✓✓✓ EXCELLENT! Reached drug candidate range!")
        print("  This molecule has strong potential for HIV treatment!")
    elif best_affinity < -6:
        print("✓✓ GOOD! Very close to drug candidate range!")
        print("  Minor optimization needed")
    elif best_affinity < -5:
        print("✓ MODERATE! Consistent improvement, continue optimization")
    else:
        print("⚠️ Continue with even stronger modifications")
    
    # Save
    with open(f"{best['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {best['name']}_result.pdbqt")

print("="*80)
