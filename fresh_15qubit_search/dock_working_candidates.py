#!/usr/bin/env python3
"""
Dock quantum candidates using working SMILES template from CURE_17G_002
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem

print("="*80)
print("DOCKING QUANTUM CANDIDATES - Using Working SMILES Template")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# The working SMILES from CURE_17G_002
BASE_SMILES = "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1"

print(f"\nBase SMILES (CURE_17G_002): {BASE_SMILES[:80]}...")

# Quantum candidates from search
quantum_candidates = [
    # Top 10 from quantum search
    {"core": "Isoquinoline", "p1": "meta-Cl", "p2": "spiro-THF"},
    {"core": "Indole", "p1": "meta-CF3", "p2": "bis-THF"},
    {"core": "Indole", "p1": "Benzyl", "p2": "bis-THF"},
    {"core": "Naphthalene", "p1": "3,5-diF", "p2": "bis-THF"},
    {"core": "Isoquinoline", "p1": "3,5-diF", "p2": "bis-THF"},
    {"core": "Naphthalene", "p1": "meta-CF3", "p2": "bis-THF"},
    {"core": "Indole", "p1": "Benzyl", "p2": "spiro-THF"},
    {"core": "Naphthalene", "p1": "meta-F", "p2": "bis-THF"},
]

# Define modifications to the base SMILES
modifications = {
    # Core modifications (isoquinoline, naphthalene, indole)
    "Isoquinoline": {
        "replace": "c1ccc2ccc(O)cc2n1",
        "with": "c1ccc2cccnc2c1"
    },
    "Naphthalene": {
        "replace": "c1ccc2ccc(O)cc2n1", 
        "with": "c1ccc2ccccc2c1"
    },
    "Indole": {
        "replace": "c1ccc2ccc(O)cc2n1",
        "with": "c1ccc2[nH]ccc2c1"
    },
    # P1 modifications (the fluorine pattern)
    "meta-F": {
        "replace": "Cc1cc(F)cc(F)c1",
        "with": "Cc1cccc(F)c1"
    },
    "3,5-diF": {
        "replace": "Cc1cc(F)cc(F)c1",
        "with": "Cc1cc(F)cc(F)c1"  # same as base
    },
    "Benzyl": {
        "replace": "Cc1cc(F)cc(F)c1",
        "with": "Cc1ccccc1"
    },
    "meta-Cl": {
        "replace": "Cc1cc(F)cc(F)c1",
        "with": "Cc1cccc(Cl)c1"
    },
    "meta-CF3": {
        "replace": "Cc1cc(F)cc(F)c1",
        "with": "Cc1cccc(C(F)(F)F)c1"
    },
    # P2 modifications
    "spiro-THF": {
        "replace": "[C@@H]1CO[C@@H]2OCCO[C@H]21",
        "with": "[C@@H]1CO[C@@H]2CCCO[C@H]21"
    }
}

print("\nGenerating modified SMILES...")
smiles_list = []

for i, cand in enumerate(quantum_candidates):
    smiles = BASE_SMILES
    
    # Apply core modification
    if cand["core"] in modifications:
        mod = modifications[cand["core"]]
        smiles = smiles.replace(mod["replace"], mod["with"])
    
    # Apply P1 modification
    if cand["p1"] in modifications:
        mod = modifications[cand["p1"]]
        smiles = smiles.replace(mod["replace"], mod["with"])
    
    # Apply P2 modification
    if cand["p2"] in modifications:
        mod = modifications[cand["p2"]]
        smiles = smiles.replace(mod["replace"], mod["with"])
    
    smiles_list.append({
        "index": i+1,
        "core": cand["core"],
        "p1": cand["p1"], 
        "p2": cand["p2"],
        "smiles": smiles
    })
    
    print(f"{i+1}. {cand['core']}+{cand['p1']}+{cand['p2']}")

# Save SMILES
with open("candidate_smiles.txt", "w") as f:
    for s in smiles_list:
        f.write(f"{s['smiles']}\n")

print(f"\nSaved {len(smiles_list)} SMILES to candidate_smiles.txt")

# Find receptor
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"
if not os.path.exists(RECEPTOR):
    print("Error: Receptor not found")
    sys.exit(1)

print(f"\nReceptor: {RECEPTOR}")

os.makedirs("docking_results", exist_ok=True)

results = []

print(f"\nDocking {len(smiles_list)} candidates...")
print("-"*60)

for cand in smiles_list:
    print(f"\n[{cand['index']}] {cand['core']}+{cand['p1']}+{cand['p2']}")
    
    try:
        mol = Chem.MolFromSmiles(cand['smiles'])
        if mol is None:
            print("   Invalid SMILES")
            continue
        
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
        
        pdb_file = f"docking_results/cand_{cand['index']}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        pdbqt_file = f"docking_results/cand_{cand['index']}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            print("   PDBQT conversion failed")
            continue
        
        output_file = f"docking_results/cand_{cand['index']}_out.pdbqt"
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand ../resistance_profiling/ligand_split_1.pdbqt --autobox_add 8 --num_modes 3 --exhaustiveness 12 --cnn_scoring rescore -o {output_file} 2>/dev/null"
        
        subprocess.run(cmd, shell=True, timeout=120)
        
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
            print(f"   Vina: {vina:.2f} kcal/mol | CNN: {cnn:.4f}")
            results.append({
                "candidate": cand['index'],
                "core": cand['core'],
                "p1": cand['p1'],
                "p2": cand['p2'],
                "vina": vina,
                "cnn": cnn
            })
        else:
            print("   No score")
            
    except Exception as e:
        print(f"   Error: {e}")

# Save results
with open("docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("DOCKING RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    print(f"\n{'Rank':<4} {'Core':<12} {'P1':<12} {'P2':<12} {'Vina':<10} {'CNN':<10}")
    print("-"*65)
    for i, r in enumerate(sorted_results):
        print(f"{i+1:<4} {r['core']:<12} {r['p1']:<12} {r['p2']:<12} {r['vina']:<10.2f} {r['cnn']:<10.4f}")
    
    best = sorted_results[0]
    print(f"\nBEST CANDIDATE: {best['core']} + {best['p1']} + {best['p2']}")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    print(f"   CNN: {best['cnn']:.4f}")
else:
    print("\nNo successful docking results")

print("\n" + "="*80)

