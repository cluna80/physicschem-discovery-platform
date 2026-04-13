#!/usr/bin/env python3
"""
Simple docking for quantum candidates
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem

print("="*80)
print("SIMPLE DOCKING - Quantum Candidates")
print("="*80)
print(f"Start: {datetime.now().strftime('%H:%M:%S')}")
print("="*80)

# Working SMILES from CURE_17G_002
BASE_SMILES = "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1"

# Quantum candidates (simplified)
candidates = [
    ("isoquinoline_metaCl", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2cccnc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(Cl)c1")),
    ("indole_metaCF3",
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2[nH]ccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(C(F)(F)F)c1")),
    ("naphthalene_35diF",
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2ccccc2c1")),
]

# Find receptor
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"

print(f"\nReceptor: {RECEPTOR}")

os.makedirs("docking_results", exist_ok=True)

# Get reference ligand for autobox
REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"
if not os.path.exists(REF_LIGAND):
    REF_LIGAND = "../gnina_results/CURE_17G_002_out.pdbqt"

print(f"Reference: {REF_LIGAND}")

results = []

for name, smiles in candidates:
    print(f"\nDocking {name}...")
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print("   Invalid SMILES")
            continue
        
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
        
        pdb_file = f"docking_results/{name}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        pdbqt_file = f"docking_results/{name}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True)
        
        if not os.path.exists(pdbqt_file):
            print("   Conversion failed")
            continue
        
        output_file = f"docking_results/{name}_out.pdbqt"
        
        # Run with shorter exhaustiveness for speed
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 6 --num_modes 3 --exhaustiveness 8 -o {output_file} 2>&1 | tail -20"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        
        vina = None
        cnn = None
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                content = f.read()
                for line in content.split('\n'):
                    if "REMARK Vina score:" in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            vina = float(parts[1].strip().split()[0])
                    if "REMARK CNNscore:" in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            cnn = float(parts[1].strip().split()[0])
        
        if vina:
            print(f"   Vina: {vina:.2f} kcal/mol")
            results.append({"name": name, "vina": vina, "cnn": cnn})
        else:
            print("   No score")
            
    except Exception as e:
        print(f"   Error: {e}")

print("\n" + "="*80)
print("RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    for i, r in enumerate(sorted_results):
        print(f"{i+1}. {r['name']}: {r['vina']:.2f} kcal/mol (CNN: {r.get('cnn', 0):.4f})")
    
    best = sorted_results[0]
    print(f"\nBEST: {best['name']} at {best['vina']:.2f} kcal/mol")
else:
    print("No results")

print("="*80)

