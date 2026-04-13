#!/usr/bin/env python3
"""
Dock valid quantum candidates with Gnina
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem

print("="*80)
print("DOCKING VALID QUANTUM CANDIDATES")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load valid candidates
with open("valid_quantum_candidates.json", "r") as f:
    candidates = json.load(f)

print(f"\nLoaded {len(candidates)} valid candidates")

# Find receptor
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"
if not os.path.exists(RECEPTOR):
    print("Error: Receptor not found")
    sys.exit(1)

print(f"Receptor: {RECEPTOR}")

os.makedirs("docking_results", exist_ok=True)

results = []

print(f"\nDocking top {min(15, len(candidates))} candidates...")
print("-"*60)

for i, cand in enumerate(candidates[:15]):
    print(f"\n[{i+1}] {cand['core']} + {cand['p1']} + {cand['p2']}")
    
    try:
        # Generate 3D structure
        mol = Chem.MolFromSmiles(cand['smiles'])
        if mol is None:
            print("   Invalid SMILES")
            continue
        
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
        
        # Save PDB
        pdb_file = f"docking_results/cand_{i+1}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        # Convert to PDBQT
        pdbqt_file = f"docking_results/cand_{i+1}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            print("   PDBQT conversion failed")
            continue
        
        # Run Gnina
        output_file = f"docking_results/cand_{i+1}_out.pdbqt"
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand ../resistance_profiling/ligand_split_1.pdbqt --autobox_add 8 --num_modes 3 --exhaustiveness 12 --cnn_scoring rescore -o {output_file} 2>/dev/null"
        
        subprocess.run(cmd, shell=True, timeout=120)
        
        # Parse result
        vina = None
        cnn = None
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                for line in f:
                    if "REMARK Vina score:" in line:
                        vina = float(line.split(':')[1].strip().split()[0])
                    if "REMARK CNNscore:" in line:
                        cnn = float(line.split(':')[1].strip().split()[0])
        
        if vina:
            print(f"   Vina: {vina:.2f} kcal/mol | CNN: {cnn:.4f}")
            results.append({
                "candidate": i+1,
                "core": cand['core'],
                "p1": cand['p1'],
                "p2": cand['p2'],
                "vina": vina,
                "cnn": cnn,
                "quantum_prob": cand['quantum_probability'],
                "smiles": cand['smiles']
            })
        else:
            print("   No score")
            
    except Exception as e:
        print(f"   Error: {e}")

# Save results
with open("docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    print(f"\n{'Rank':<4} {'Core':<12} {'P1':<12} {'Vina':<10} {'CNN':<10}")
    print("-"*55)
    for i, r in enumerate(sorted_results[:10]):
        print(f"{i+1:<4} {r['core']:<12} {r['p1']:<12} {r['vina']:<10.2f} {r['cnn']:<10.4f}")
    
    best = sorted_results[0]
    print(f"\nBEST CANDIDATE: {best['core']} + {best['p1']}")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    print(f"   CNN: {best['cnn']:.4f}")
else:
    print("\nNo results")

print("\n" + "="*80)

