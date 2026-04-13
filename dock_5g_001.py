# -*- coding: utf-8 -*-
"""
Dock CURE_5G_001 - Adding THF-like group to CURE_4G_003
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

# CURE_5G_001 with THF-like group
CANDIDATE = {
    'name': 'CURE_5G_001',
    'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFCCOCCO',
    'predicted_boost': 0.6,
    'base_affinity': -5.365
}
CANDIDATE['predicted_affinity'] = CANDIDATE['base_affinity'] + CANDIDATE['predicted_boost']

print("="*80)
print(f"DOCKING {CANDIDATE['name']}")
print("="*80)
print(f"Modification: Adding THF-like ether group")
print(f"Predicted affinity: {CANDIDATE['predicted_affinity']:.3f} kcal/mol")
print(f"SMILES: {CANDIDATE['smiles']}")
print("-"*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = f"{CANDIDATE['name']}.pdbqt"
if smiles_to_pdbqt(CANDIDATE['smiles'], ligand_file):
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
    "--out", f"{CANDIDATE['name']}_result.pdbqt",
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
    print(f"Predicted affinity: {CANDIDATE['predicted_affinity']:.3f} kcal/mol")
    
    print("\n" + "="*80)
    print("FINAL PROGRESS TRACKER")
    print("="*80)
    print(f"CURE_070:          -4.591 kcal/mol")
    print(f"CURE_076:          -4.424 kcal/mol")
    print(f"CURE_3G_003:       -4.737 kcal/mol")
    print(f"CURE_4G_003:       -5.365 kcal/mol")
    print(f"{CANDIDATE['name']}: {best_affinity:.3f} kcal/mol")
    
    improvement = best_affinity - (-5.365)
    print(f"\nImprovement over CURE_4G_003: {improvement:+.2f} kcal/mol")
    print(f"Gap to -7.0: {best_affinity - (-7.0):.2f} kcal/mol")
    
    if best_affinity < -6:
        print("\n✓✓✓ EXCELLENT! This is approaching drug candidate range!")
    elif best_affinity < -5.8:
        print("\n✓✓ GOOD! Significant improvement!")
    elif best_affinity < -5.5:
        print("\n✓ MODERATE! Solid progress")
    else:
        print("\n⚠️ Need further optimization")
    
    # Save
    with open(f"{CANDIDATE['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {CANDIDATE['name']}_result.pdbqt")

print("="*80)
