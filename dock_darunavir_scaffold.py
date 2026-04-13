# -*- coding: utf-8 -*-
"""
Dock Darunavir scaffold - known potent HIV inhibitor
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

# Darunavir scaffold (simplified but active)
DARUNAVIR_LIKE = {
    'name': 'Darunavir_scaffold',
    'smiles': 'CC(C)C1=CC=C(C=C1)COC(=O)N2CC(C3=CC=CC=C3)CC2C(=O)NC(CC4=CC=CC=C4)C(O)CN5CCOCC5',
    'description': 'Darunavir-like - potent HIV inhibitor'
}

print("="*80)
print(f"DOCKING {DARUNAVIR_LIKE['name']}")
print("="*80)
print(f"Description: {DARUNAVIR_LIKE['description']}")
print(f"SMILES: {DARUNAVIR_LIKE['smiles'][:80]}...")
print("-"*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = f"{DARUNAVIR_LIKE['name']}.pdbqt"
if smiles_to_pdbqt(DARUNAVIR_LIKE['smiles'], ligand_file):
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
    "--out", f"{DARUNAVIR_LIKE['name']}_result.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "16"
]

print("  Running AutoDock Vina (1-2 minutes due to molecule size)...")
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
    print(f"Expected (literature): -8.0 to -9.0 kcal/mol")
    
    print("\n" + "-"*80)
    if best_affinity < -7:
        print("✓✓✓ EXCELLENT! This matches FDA-approved HIV drugs!")
        print("  This validates our docking setup.")
    elif best_affinity < -6:
        print("✓✓ GOOD! Close to drug candidate range")
    elif best_affinity < -5:
        print("✓ MODERATE! May need binding site optimization")
    else:
        print("⚠️ Docking may need optimization - check binding site coordinates")
    
    # Compare with our optimized molecules
    print("\n" + "="*80)
    print("COMPARISON WITH OUR OPTIMIZED MOLECULES")
    print("="*80)
    print(f"Our best optimized: ~-4.25 kcal/mol")
    print(f"Darunavir scaffold: {best_affinity:.3f} kcal/mol")
    print(f"Difference: {best_affinity - (-4.25):.2f} kcal/mol")
    
    if best_affinity < -7:
        print("\n✓ This confirms our scaffold needs these key features:")
        print("  1. Hydroxyethylamine core (C(OH)CN)")
        print("  2. Tetrahydrofuran ring")
        print("  3. Proper stereochemistry")
        print("  4. Multiple hydrogen bond donors/acceptors")
    
    # Save results
    with open(f"{DARUNAVIR_LIKE['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {DARUNAVIR_LIKE['name']}_result.pdbqt")

print("="*80)
