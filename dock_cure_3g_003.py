# -*- coding: utf-8 -*-
"""
Dock CURE_3G_003 - Multiple fluorines on aromatic
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

# CURE_3G_003 details
analog = {
    'name': 'CURE_3G_003',
    'smiles': 'c1cc(F)c(F)c(F)c1C(=O)OOCC(=O)CCCF',
    'modification': 'Multiple fluorines on aromatic',
    'description': 'Stronger pi-stacking with electron withdrawal',
    'predicted_affinity': -3.97,
    'mw': 294,
    'logp': 2.51
}

print("="*80)
print(f"DOCKING AGGRESSIVE ANALOG: {analog['name']}")
print("="*80)
print(f"Modification: {analog['modification']}")
print(f"Description: {analog['description']}")
print(f"SMILES: {analog['smiles']}")
print(f"Predicted affinity: {analog['predicted_affinity']:.2f} kcal/mol")
print(f"MW: {analog['mw']} Da, LogP: {analog['logp']:.2f}")
print(f"Target: -7.0 kcal/mol (HIV drug range)")
print("-"*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

# Convert to PDBQT
print("\n[1/2] Converting to 3D PDBQT...")
ligand_file = f"{analog['name']}.pdbqt"
if smiles_to_pdbqt(analog['smiles'], ligand_file):
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
    "--out", f"{analog['name']}_result.pdbqt",
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
    print(f"Predicted affinity: {analog['predicted_affinity']:.2f} kcal/mol")
    
    # Complete progress summary
    print("\n" + "="*80)
    print("COMPLETE OPTIMIZATION PROGRESS")
    print("="*80)
    
    progress = [
        ('Original', 'CURE_070', -4.05),
        ('First Gen', 'CURE_076', -4.27),
        ('Second Gen', 'CURE_2G_001', -4.25),
        ('Aggressive', analog['name'], best_affinity),
    ]
    
    print(f"\n{'Generation':<15} {'Molecule':<15} {'Affinity':<12} {'Improvement':<12}")
    print("-"*55)
    
    base = progress[0][2]
    for gen, name, aff in progress:
        improvement = aff - base
        print(f"{gen:<15} {name:<15} {aff:<12.3f} {improvement:<+12.2f}")
    
    print(f"\nTotal improvement: {best_affinity - base:.2f} kcal/mol")
    print(f"Remaining to -7.0: {best_affinity - (-7.0):.2f} kcal/mol")
    
    print("\n" + "-"*80)
    if best_affinity < -7:
        print("✓✓✓ EXCELLENT! Reached drug candidate range!")
        print("  This molecule has strong potential for HIV treatment!")
    elif best_affinity < -6:
        print("✓✓ GOOD! Very close to drug candidate range!")
        print("  Minor optimization needed")
    elif best_affinity < -5:
        print("✓ MODERATE! Solid improvement over original")
        print("  Continue with more aggressive modifications")
    elif best_affinity < -4.5:
        print("✓ Minor improvement achieved")
    else:
        print("⚠️ Need stronger modifications")
    
    # Save results
    with open(f"{analog['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {analog['name']}_result.pdbqt")
    
    # Recommendations for next generation
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR NEXT GENERATION")
    print("="*80)
    print("""
Based on this result, consider:
1. Add amide groups for stronger H-bonding with Asp25
2. Increase chain length further for hydrophobic packing
3. Add hydroxyl groups to mimic HIV drugs
4. Incorporate known HIV drug scaffolds (hydroxyethylamine)
5. Use molecular dynamics to optimize binding pose
""")

print("="*80)
