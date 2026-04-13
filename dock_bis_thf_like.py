# -*- coding: utf-8 -*-
"""
Dock bis-THF-like molecule to reach -7 to -8 kcal/mol
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

# Bis-THF-like molecule (simplified but captures key features)
BIS_THF_LIKE = {
    'name': 'CURE_5G_BIS_THF',
    'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1O',
    'description': 'Bis-THF mimic with THF ring and hydroxyl',
    'expected_boost': 1.8
}

current_affinity = -5.365
predicted = current_affinity + BIS_THF_LIKE['expected_boost']

print("="*80)
print(f"DOCKING BIS-THF-LIKE CANDIDATE: {BIS_THF_LIKE['name']}")
print("="*80)
print(f"Description: {BIS_THF_LIKE['description']}")
print(f"Expected boost: +{BIS_THF_LIKE['expected_boost']:.1f} kcal/mol")
print(f"Predicted affinity: {predicted:.3f} kcal/mol")
print(f"Target: -9.0 kcal/mol")
print(f"Gap to target: {predicted - (-9.0):.2f} kcal/mol")
print(f"SMILES: {BIS_THF_LIKE['smiles']}")
print("-"*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = f"{BIS_THF_LIKE['name']}.pdbqt"
if smiles_to_pdbqt(BIS_THF_LIKE['smiles'], ligand_file):
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
    "--out", f"{BIS_THF_LIKE['name']}_result.pdbqt",
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
    print(f"Predicted: {predicted:.3f} kcal/mol")
    
    print("\n" + "="*80)
    print("PROGRESS TO -9 kcal/mol")
    print("="*80)
    print(f"CURE_070:           -4.591 kcal/mol")
    print(f"CURE_4G_003:        -5.365 kcal/mol")
    print(f"{BIS_THF_LIKE['name']}: {best_affinity:.3f} kcal/mol")
    print(f"Target:            -9.000 kcal/mol")
    
    improvement = best_affinity - (-5.365)
    remaining = best_affinity - (-9.0)
    print(f"\nImprovement: {improvement:+.2f} kcal/mol")
    print(f"Remaining to -9.0: {remaining:.2f} kcal/mol")
    
    print("\n" + "-"*80)
    if best_affinity < -8:
        print("✓✓✓ EXCELLENT! Approaching drug candidate range!")
        print(f"  Need {abs(remaining):.2f} kcal/mol more to reach -9.0")
    elif best_affinity < -7:
        print("✓✓ GOOD! Strong binder achieved!")
        print(f"  Need {abs(remaining):.2f} kcal/mol more to reach -9.0")
    elif best_affinity < -6:
        print("✓ MODERATE! Need full bis-THF for Darunavir potency")
    elif best_affinity < -5.5:
        print("✓ Minor improvement")
    else:
        print("⚠️ Need stronger modifications")
    
    # Save results
    with open(f"{BIS_THF_LIKE['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {BIS_THF_LIKE['name']}_result.pdbqt")
    
    # Next steps based on result
    print("\n" + "="*80)
    print("NEXT STEPS BASED ON RESULT")
    print("="*80)
    if best_affinity < -7:
        print("""
1. ✓ Bis-THF-like group working! Add actual bis-THF
2. Optimize the THF stereochemistry (Darunavir uses specific chiral centers)
3. Add sulfonamide for additional H-bonding
4. Further optimize P1/P2 groups

PREDICTED NEXT GENERATION:
   Add full bis-THF + sulfonamide → -8.5 to -9.5 kcal/mol
""")
    elif best_affinity < -6:
        print("""
1. Need actual bis-THF (not just THF ring)
2. Add both THF rings connected properly
3. Optimize linker length between THF and core

PREDICTED IMPROVEMENT:
   Full bis-THF → additional 1.0-1.5 kcal/mol
   Target: -7.5 to -8.0 kcal/mol
""")
    else:
        print("""
1. Simplify design further
2. Use known working scaffolds
3. Consider alternative approaches
""")

print("="*80)
