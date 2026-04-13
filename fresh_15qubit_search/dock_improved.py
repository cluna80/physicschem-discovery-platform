#!/usr/bin/env python3
"""
Improved docking for quantum candidates - with proper timeout handling
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem
import concurrent.futures

print("="*80)
print("IMPROVED DOCKING - Quantum Candidates")
print("="*80)
print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Working SMILES from CURE_17G_002
BASE_SMILES = "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1"

# Quantum candidates from search
candidates = [
    ("isoquinoline_metaCl_spiroTHF", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2cccnc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(Cl)c1")
               .replace("[C@@H]1CO[C@@H]2OCCO[C@H]21", "[C@@H]1CO[C@@H]2CCCO[C@H]21")),
    
    ("indole_metaCF3", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2[nH]ccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(C(F)(F)F)c1")),
    
    ("indole_benzyl", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2[nH]ccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1ccccc1")),
    
    ("naphthalene_35diF", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2ccccc2c1")),
    
    ("isoquinoline_35diF", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2cccnc2c1")),
    
    ("naphthalene_metaCF3", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2ccccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(C(F)(F)F)c1")),
    
    ("indole_benzyl_spiroTHF", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2[nH]ccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1ccccc1")
               .replace("[C@@H]1CO[C@@H]2OCCO[C@H]21", "[C@@H]1CO[C@@H]2CCCO[C@H]21")),
    
    ("naphthalene_metaF", 
     BASE_SMILES.replace("c1ccc2ccc(O)cc2n1", "c1ccc2ccccc2c1")
               .replace("Cc1cc(F)cc(F)c1", "Cc1cccc(F)c1")),
]

# Find receptor and reference
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"

REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"
if not os.path.exists(REF_LIGAND):
    REF_LIGAND = "../gnina_results/CURE_17G_002_out.pdbqt"

print(f"\nReceptor: {RECEPTOR}")
print(f"Reference: {REF_LIGAND}")
print(f"Candidates: {len(candidates)}")

os.makedirs("docking_results", exist_ok=True)

def dock_candidate(name, smiles):
    """Dock a single candidate with proper timeout"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Docking {name}...")
    
    try:
        # Generate 3D structure
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {"name": name, "error": "Invalid SMILES", "vina": None}
        
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
        
        # Save files
        pdb_file = f"docking_results/{name}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        pdbqt_file = f"docking_results/{name}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", 
                      shell=True, timeout=30)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            return {"name": name, "error": "PDBQT conversion failed", "vina": None}
        
        # Run Gnina with optimized settings
        output_file = f"docking_results/{name}_out.pdbqt"
        
        cmd = [
            '../gnina_cu11', '--no_gpu',
            '-r', RECEPTOR,
            '-l', pdbqt_file,
            '--autobox_ligand', REF_LIGAND,
            '--autobox_add', '6',
            '--num_modes', '5',
            '--exhaustiveness', '6',
            '--cpu', '6',
            '-o', output_file
        ]
        
        # Run with longer timeout (5 minutes)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        # Parse output
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
            print(f"   ✓ {name}: Vina={vina:.2f} CNN={cnn:.4f}")
            return {"name": name, "vina": vina, "cnn": cnn, "error": None}
        else:
            # Check stdout for scores
            for line in result.stdout.split('\n'):
                if 'mode' in line.lower() and 'affinity' in line.lower():
                    print(f"   → {name}: {line.strip()}")
            return {"name": name, "error": "No score in output", "vina": None}
            
    except subprocess.TimeoutExpired:
        print(f"   ✗ {name}: TIMEOUT after 300s")
        return {"name": name, "error": "Timeout", "vina": None}
    except Exception as e:
        print(f"   ✗ {name}: Error - {e}")
        return {"name": name, "error": str(e), "vina": None}

# Run sequentially to avoid CPU contention
results = []
for name, smiles in candidates:
    result = dock_candidate(name, smiles)
    results.append(result)

# Save results
with open("docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Print summary
print("\n" + "="*80)
print("DOCKING RESULTS SUMMARY")
print("="*80)

valid_results = [r for r in results if r.get('vina') is not None]
if valid_results:
    sorted_results = sorted(valid_results, key=lambda x: x['vina'])
    print(f"\n{'Rank':<4} {'Candidate':<30} {'Vina (kcal/mol)':<15} {'CNN Score':<10}")
    print("-"*65)
    for i, r in enumerate(sorted_results):
        print(f"{i+1:<4} {r['name']:<30} {r['vina']:<15.2f} {r.get('cnn', 0):<10.4f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST CANDIDATE: {best['name']}")
    print(f"   Vina Affinity: {best['vina']:.2f} kcal/mol")
    print(f"   CNN Score: {best.get('cnn', 0):.4f}")
    
    # Compare to reference
    print(f"\nReference (CURE_17G_002): -11.18 kcal/mol")
    if best['vina'] < -11.18:
        print(f"✅ BETTER than CURE_17G_002 by {abs(best['vina'] - 11.18):.2f} kcal/mol!")
    else:
        print(f"📈 Improvement needed: {best['vina'] - 11.18:.2f} kcal/mol")
else:
    print("\n❌ No successful docking results")
    
    # Show errors
    print("\nErrors:")
    for r in results:
        if r.get('error'):
            print(f"   {r['name']}: {r['error']}")

print("\n" + "="*80)
print("Complete! Check docking_results.json for full data")
print("="*80)

