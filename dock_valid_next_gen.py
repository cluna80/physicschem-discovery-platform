# -*- coding: utf-8 -*-
"""
Dock the best valid next-generation HIV drug candidate
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

# Load valid candidates
with open("valid_next_gen_candidates.json", 'r') as f:
    candidates = json.load(f)

if not candidates:
    print("No valid candidates found")
    exit()

best = candidates[0]

print("="*80)
print(f"DOCKING NEXT GENERATION: {best['name']}")
print("="*80)
print(f"Description: {best['description']}")
print(f"Predicted affinity: {best['predicted_affinity']:.3f} kcal/mol")
print(f"SMILES: {best['smiles']}")
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
    "--size_x", "25",
    "--size_y", "25",
    "--size_z", "25",
    "--out", f"{best['name']}_result.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "12",
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
                pass

print("\n" + "="*80)
print("DOCKING RESULTS")
print("="*80)

if affinities:
    valid = [a for a in affinities if a < 5]
    best_affinity = min(valid) if valid else affinities[0]
    
    print(f"\nBinding Affinities (kcal/mol):")
    for i, aff in enumerate(affinities[:9], 1):
        marker = "★" if aff == best_affinity else " "
        print(f"  {marker} Mode {i}: {aff:.3f} kcal/mol")
    
    print(f"\nBest binding affinity: {best_affinity:.3f} kcal/mol")
    
    print("\n" + "="*80)
    print("PROGRESS TO DRUG CANDIDATE")
    print("="*80)
    print(f"CURE_3G_003 (best so far): -4.737 kcal/mol")
    print(f"This candidate: {best_affinity:.3f} kcal/mol")
    print(f"Improvement: {best_affinity - (-4.737):.2f} kcal/mol")
    print(f"Gap to -7.0: {best_affinity - (-7.0):.2f} kcal/mol")
    
    if best_affinity < -7:
        print("\n✓✓✓ SUCCESS! Reached drug candidate range!")
        print("  This molecule has strong potential for HIV treatment!")
    elif best_affinity < -6:
        print("\n✓✓ GOOD! Very close to drug candidate range!")
    elif best_affinity < -5:
        print("\n✓ MODERATE! Solid improvement!")
    else:
        print("\n⚠️ Further optimization needed")
    
    with open(f"{best['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {best['name']}_result.pdbqt")

print("="*80)
