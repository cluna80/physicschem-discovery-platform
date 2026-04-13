# -*- coding: utf-8 -*-
"""
Dock the best P2' substituent found by 4-qubit quantum search
"""

import json
import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, QED
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

# Load quantum results
with open("p2_quantum_results.json", 'r') as f:
    quantum_results = json.load(f)

best = quantum_results[0]  # Top quantum-recommended

# Base scaffold with best P2' substitution
BASE_SCAFFOLD = "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

# Replace with best substituent
if best['name'] == "SO2NH2":
    ULTRA_SMILES = "O=S(=O)(N)c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"
elif best['name'] == "OH":
    ULTRA_SMILES = "Oc1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"
elif best['name'] == "NH2":
    ULTRA_SMILES = "Nc1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"
else:
    # Default to sulfonamide if not matched
    ULTRA_SMILES = "O=S(=O)(N)c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*80)
print(f"DOCKING QUANTUM-SELECTED P2' SUBSTITUENT: {best['name']}")
print(f"Quantum probability: {best.get('quantum_prob', 0):.3f}")
print(f"Predicted boost: +{best['predicted_boost']:.1f} kcal/mol")
print("="*80)

# Convert to PDBQT
ligand_file = f"ULTRA_QUANTUM_{best['name']}.pdbqt"
if to_pdbqt(ULTRA_SMILES, ligand_file.replace('.pdbqt', '')):
    print("✓ PDBQT generated")
    
    # Dock
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
        "--out", f"ULTRA_QUANTUM_{best['name']}_result.pdbqt",
        "--num_modes", "9",
        "--exhaustiveness", "16",
        "--cpu", "6"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse affinity
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
        print(f"\n✓ Best affinity: {best_aff:.3f} kcal/mol")
        print(f"Predicted: {BASE_AFFINITY + best['predicted_boost']:.3f} kcal/mol")
        print(f"Gap to -9.0: {best_aff - (-9.0):.2f} kcal/mol")
        
        if best_aff < -8.5:
            print("\n★★★ EXCELLENT! Approaching Darunavir-level!")
        if best_aff < -9:
            print("\n★★★★ REACHED -9.0! Drug candidate!")
        if best_aff < -10:
            print("\n★★★★★ BEYOND DARUNAVIR!")
    else:
        print("Docking failed")
else:
    print("PDBQT generation failed")
