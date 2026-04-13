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

# Load best analog
with open("optimized_analogs.json", 'r') as f:
    analogs = json.load(f)
    best = analogs[0]  # Best is first after sorting

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*80)
print(f"DOCKING OPTIMIZED ANALOG: {best['name']}")
print("="*80)
print(f"Modification: {best['modification']}")
print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"SMILES: {best['smiles']}")
print("-"*80)

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
                pass

print("\n" + "="*80)
print("DOCKING RESULTS")
print("="*80)

if affinities:
    # Find best affinity (ignore Mode 1 if it's 10.0)
    best_affinity = min([a for a in affinities if a < 5], default=affinities[0])
    
    print(f"\nBinding Affinities (kcal/mol):")
    for i, aff in enumerate(affinities[:9], 1):
        marker = "★" if i == 2 and aff == best_affinity else " "
        print(f"  {marker} Mode {i}: {aff:.3f} kcal/mol")
    
    print(f"\nBest binding affinity: {best_affinity:.3f} kcal/mol")
    print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
    print(f"Difference: {best_affinity - best['predicted_affinity']:.2f} kcal/mol")
    
    if best_affinity < -7:
        print("\n✓ SUCCESS! This analog reaches strong binder threshold!")
        print("  This molecule has HIV drug candidate potential!")
    elif best_affinity < -5:
        print("\n✓ GOOD! This analog is a moderate binder")
        print("  Close to drug candidate range")
    else:
        print("\n⚠️ Needs further optimization")
    
    # Compare with original
    print(f"\nComparison with original HIV_CURE_070:")
    print(f"  Original: -4.05 kcal/mol")
    print(f"  Analog:   {best_affinity:.3f} kcal/mol")
    print(f"  Improvement: {best_affinity - (-4.05):.2f} kcal/mol")
    
    # Save results
    with open(f"{best['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")

print("\n" + "="*80)
