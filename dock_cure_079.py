# -*- coding: utf-8 -*-
"""
Dock the best optimized analog CURE_079
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

# Load the best analog
with open("optimized_analogs_full.json", 'r') as f:
    analogs = json.load(f)
    best = analogs[0]  # First one is best

print("="*80)
print(f"DOCKING OPTIMIZED ANALOG: {best['name']}")
print("="*80)
print(f"Modification: {best['modification']}")
print(f"SMILES: {best['smiles']}")
print(f"Predicted affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"MW: {best['mw']:.0f} Da, LogP: {best['logp']:.2f}")
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
    
    # Compare with original
    original_affinity = -4.05
    improvement = best_affinity - original_affinity
    
    print(f"\nComparison with original HIV_CURE_070:")
    print(f"  Original: {original_affinity:.3f} kcal/mol")
    print(f"  Optimized: {best_affinity:.3f} kcal/mol")
    print(f"  Improvement: {improvement:.2f} kcal/mol")
    
    print("\n" + "-"*80)
    if best_affinity < -7:
        print("✓ EXCELLENT! Reaches strong binder threshold!")
        print("  This molecule has HIV drug candidate potential!")
    elif best_affinity < -5.5:
        print("✓ GOOD! Approaching drug candidate range!")
    elif best_affinity < -4.5:
        print("✓ MODERATE! Improvement over original")
    else:
        print("⚠️ Needs further optimization")
    
    # Save results
    with open(f"{best['name']}_affinities.txt", "w") as f:
        for aff in affinities:
            f.write(f"{aff}\n")
    
    print(f"\nResults saved to: {best['name']}_result.pdbqt")
    
    # Summary of all analogs
    print("\n" + "="*80)
    print("ALL ANALOGS - PREDICTED VS TARGET")
    print("="*80)
    print(f"\n{'Name':<12} {'Modification':<30} {'Predicted':<12} {'Target':<12}")
    print("-"*70)
    for a in analogs[:5]:
        target = "-7.0" if a['predicted_affinity'] < -6 else "> -6"
        print(f"{a['name']:<12} {a['modification'][:28]:<30} {a['predicted_affinity']:<12.2f} {target:<12}")
    
    if best_affinity < -5:
        print("\n✓ Progress made! Continue optimizing.")
    else:
        print("\nContinue generating more analogs with additional modifications:")
        print("  - Add more fluorine atoms")
        print("  - Increase chain length further")
        print("  - Add hydroxyl groups for H-bonding")
        print("  - Introduce nitrogen heterocycles")

print("="*80)
