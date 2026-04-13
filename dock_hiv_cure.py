# -*- coding: utf-8 -*-
"""
Docking the quantum-selected HIV_CURE_070 candidate into HIV-1 Protease
"""

import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem

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

# HIV_CURE_070 from quantum screening
CURE_MOLECULE = {
    'name': 'HIV_CURE_070',
    'smiles': 'C1CCCCC1C(=O)OOCC(=O)O',
}

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*80)
print("DOCKING HIV_CURE_070 INTO HIV-1 PROTEASE")
print("="*80)
print(f"\nMolecule: {CURE_MOLECULE['name']}")
print(f"SMILES: {CURE_MOLECULE['smiles']}")
print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")
print("-"*80)

# Step 1: Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = "hiv_cure_070.pdbqt"
if smiles_to_pdbqt(CURE_MOLECULE['smiles'], ligand_file):
    print(f"  Successfully created {ligand_file}")
else:
    print("  Error converting molecule")
    exit()

# Step 2: Run docking
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
    "--out", "cure_docking_result.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "16"
]

print("  Running AutoDock Vina (this may take 30-60 seconds)...")
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
    print(f"\nBinding Affinities (kcal/mol):")
    for i, aff in enumerate(affinities[:9], 1):
        print(f"  Mode {i}: {aff:.3f} kcal/mol")
    
    best_affinity = affinities[0]
    print(f"\nBest binding affinity: {best_affinity:.3f} kcal/mol")
    
    if best_affinity < -7:
        print("Classification: STRONG BINDER - Excellent candidate!")
    elif best_affinity < -5:
        print("Classification: MODERATE BINDER - Good starting point")
    elif best_affinity < -3:
        print("Classification: WEAK BINDER - Needs optimization")
    else:
        print("Classification: VERY WEAK BINDER")
    
    # Save results
    with open("cure_docking_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print("\nResults saved to: cure_docking_result.pdbqt")
    print("Affinities saved to: cure_docking_affinities.txt")
else:
    print("\nNo binding affinities found")
    print(result.stdout)

print("="*80)
