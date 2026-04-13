#!/usr/bin/env python3
"""
Dock quantum-discovered candidates with Gnina
"""

import subprocess
import json
import os
import time
from datetime import datetime
import sys

print("="*80)
print("DOCKING QUANTUM-DISCOVERED CANDIDATES - Real Gnina Validation")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load quantum candidates
try:
    with open("quantum_candidates.json", "r") as f:
        candidates = json.load(f)
    print(f"\nLoaded {len(candidates)} quantum-discovered candidates")
except:
    print("Error: quantum_candidates.json not found")
    sys.exit(1)

# Find receptor file
RECEPTOR = None
possible_paths = [
    "../resistance_profiling/docking_out/prot_WT.pdbqt",
    "../gnina_results/protein.pdbqt",
    "../gnina_results/receptor.pdbqt"
]

for path in possible_paths:
    if os.path.exists(path):
        RECEPTOR = path
        break

if RECEPTOR is None:
    print("Error: Receptor file not found")
    sys.exit(1)

print(f"Receptor: {RECEPTOR}")

# Create output directory
os.makedirs("docking_results", exist_ok=True)

# Try to import rdkit
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    HAS_RDKIT = True
except:
    print("Warning: RDKit not available. Will use existing PDB files if present.")
    HAS_RDKIT = False

results = []

print(f"\nDocking top {min(20, len(candidates))} candidates...")
print("-"*60)

for i, candidate in enumerate(candidates[:20]):
    print(f"\n[{i+1}] {candidate['core']} + {candidate['p1']} + {candidate['p2']}")
    
    # Try to generate 3D structure if RDKit available
    pdb_file = f"docking_results/cand_{i+1}.pdb"
    pdbqt_file = f"docking_results/cand_{i+1}.pdbqt"
    
    if HAS_RDKIT:
        try:
            mol = Chem.MolFromSmiles(candidate['smiles'])
            if mol:
                mol = Chem.AddHs(mol)
                AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
                AllChem.MMFFOptimizeMolecule(mol)
                Chem.MolToPDBFile(mol, pdb_file)
                
                # Convert to PDBQT
                subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", 
                              shell=True, timeout=30)
            else:
                print("   Invalid SMILES, using placeholder")
                continue
        except Exception as e:
            print(f"   RDKit error: {e}")
            continue
    else:
        print("   RDKit not available, skipping")
        continue
    
    # Run Gnina docking
    if os.path.exists(pdbqt_file) and os.path.getsize(pdbqt_file) > 0:
        output_file = f"docking_results/cand_{i+1}_out.pdbqt"
        
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand ../resistance_profiling/ligand_split_1.pdbqt --autobox_add 8 --num_modes 3 --exhaustiveness 12 --cnn_scoring rescore -o {output_file} 2>/dev/null"
        
        try:
            subprocess.run(cmd, shell=True, timeout=120)
            
            # Parse result
            vina_score = None
            cnn_score = None
            
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if "REMARK Vina score:" in line:
                            parts = line.split(':')
                            if len(parts) > 1:
                                vina_score = float(parts[1].strip().split()[0])
                        if "REMARK CNNscore:" in line:
                            parts = line.split(':')
                            if len(parts) > 1:
                                cnn_score = float(parts[1].strip().split()[0])
            
            if vina_score is not None:
                print(f"   Vina: {vina_score:.2f} kcal/mol | CNN: {cnn_score:.4f}")
                results.append({
                    "rank": i+1,
                    "core": candidate['core'],
                    "p1": candidate['p1'],
                    "p2": candidate['p2'],
                    "linker": candidate['linker'],
                    "stereo": candidate['stereo'],
                    "quantum_probability": candidate['quantum_probability'],
                    "vina_affinity": vina_score,
                    "cnn_score": cnn_score,
                    "smiles": candidate['smiles']
                })
            else:
                print("   Docking failed - no score")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print("   PDBQT file not created")

# Save results
with open("docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("DOCKING RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina_affinity'])
    
    print(f"\n{'Rank':<4} {'Core':<15} {'P1':<12} {'Vina':<10} {'CNN':<10}")
    print("-"*55)
    
    for i, r in enumerate(sorted_results[:10]):
        print(f"{i+1:<4} {r['core']:<15} {r['p1']:<12} {r['vina_affinity']:<10.2f} {r['cnn_score']:<10.4f}")
    
    best = sorted_results[0]
    print(f"\nBEST CANDIDATE: {best['core']} + {best['p1']}")
    print(f"   Vina Affinity: {best['vina_affinity']:.2f} kcal/mol")
    print(f"   CNN Score: {best['cnn_score']:.4f}")
    print(f"   Quantum Probability: {best['quantum_probability']:.4f}")
else:
    print("\nNo successful docking results")

print("\n" + "="*80)
print("Complete! Results saved to docking_results.json")
print("="*80)

