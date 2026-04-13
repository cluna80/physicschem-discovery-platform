# -*- coding: utf-8 -*-
"""
Dock the sulfonamide (SO2NH2) P2' substituent
Expected: -8.233 kcal/mol (baseline -0.9)
"""

import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem
from meeko import MoleculePreparation, PDBQTWriterLegacy

def to_pdbqt(smiles, name):
    path = f"{name}.pdbqt"
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
            AllChem.MMFFOptimizeMolecule(mol)
            prep = MoleculePreparation()
            setups = prep.prepare(mol)
            pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
            with open(path, 'w') as f:
                f.write(pdbqt_str)
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

# Sulfonamide version (SO2NH2 on naphthalene)
SULFONAMIDE_SMILES = "O=S(=O)(N)c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*80)
print("DOCKING SULFONAMIDE P2' SUBSTITUENT")
print(f"Baseline: -7.333 kcal/mol")
print(f"Biochemical boost: -0.9 kcal/mol")
print(f"Expected affinity: -8.233 kcal/mol")
print(f"Gap to -9.0: 0.767 kcal/mol")
print("="*80)

# Convert to PDBQT
ligand_file = "P2_SO2NH2.pdbqt"
if to_pdbqt(SULFONAMIDE_SMILES, ligand_file.replace('.pdbqt', '')):
    print("✓ PDBQT generated")
    
    cmd = [
        "./bin/vina.exe",
        "--receptor", "hiv_protease.pdbqt",
        "--ligand", ligand_file,
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", "25",
        "--size_y", "25",
        "--size_z", "25",
        "--out", "P2_SO2NH2_result.pdbqt",
        "--num_modes", "9",
        "--exhaustiveness", "16",
        "--cpu", "6"
    ]
    
    print("\nRunning AutoDock Vina...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    affinities = []
    for line in result.stdout.split('\n'):
        s = line.strip()
        if s and s[0].isdigit():
            parts = s.split()
            if len(parts) >= 2:
                try:
                    aff = float(parts[1])
                    if aff < 5:
                        affinities.append(aff)
                except:
                    pass
    
    if affinities:
        best_aff = min(affinities)
        print(f"\n{'='*80}")
        print("DOCKING RESULTS")
        print(f"{'='*80}")
        print(f"Best binding affinity: {best_aff:.3f} kcal/mol")
        print(f"Expected: -8.233 kcal/mol")
        print(f"Difference: {best_aff - (-8.233):.2f} kcal/mol")
        print(f"Improvement from baseline: {best_aff - (-7.333):+.2f} kcal/mol")
        print(f"Gap to -9.0: {best_aff - (-9.0):.2f} kcal/mol")
        
        print(f"\n{'='*80}")
        if best_aff < -9:
            print("★★★★★ REACHED -9.0! DRUG CANDIDATE!")
        elif best_aff < -8.5:
            print("★★★★ Excellent! Very close to -9.0!")
        elif best_aff < -8:
            print("★★★ Good! Within 1.0 kcal/mol of -9.0!")
        elif best_aff < -7.8:
            print("★★ Solid improvement!")
        else:
            print("★ Moderate improvement")
        print(f"{'='*80}")
        
        # Show all binding modes
        print("\nAll binding modes (kcal/mol):")
        for i, aff in enumerate(affinities[:9], 1):
            marker = "→" if aff == best_aff else "  "
            print(f"  {marker} Mode {i}: {aff:.3f}")
    else:
        print("Docking failed")
else:
    print("PDBQT generation failed")
