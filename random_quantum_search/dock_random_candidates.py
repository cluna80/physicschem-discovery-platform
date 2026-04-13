#!/usr/bin/env python3
"""
Dock random quantum candidates with Gnina
Testing if random quantum search can find novel compounds without prior knowledge
"""

import subprocess
import json
import os
import time
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors, QED

print("="*80)
print("🔬 DOCKING RANDOM QUANTUM CANDIDATES")
print("Testing: Can random quantum search discover novel active compounds?")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load random candidates
try:
    with open("random_quantum_candidates.json", "r") as f:
        candidates = json.load(f)
    print(f"\n📊 Loaded {len(candidates)} random quantum candidates")
except:
    print("❌ No candidates found. Run pure_random_15qubit_search.py first")
    exit(1)

# Find receptor
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"

REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

print(f"Receptor: {RECEPTOR}")
print(f"Reference: {REF_LIGAND}")

os.makedirs("docking_results", exist_ok=True)

results = []
valid_smiles_count = 0

print(f"\n🔬 Docking top {min(30, len(candidates))} random candidates...")
print("-"*70)

for i, cand in enumerate(candidates[:30]):
    print(f"\n[{i+1}] Random: {cand['ring']} + {cand['linker']} + {cand['atom']} + {cand['group']}")
    
    try:
        mol = Chem.MolFromSmiles(cand['smiles'])
        if mol is None:
            print("   ❌ Invalid SMILES")
            continue
        
        valid_smiles_count += 1
        mol = Chem.AddHs(mol)
        
        # Try to generate 3D structure
        try:
            AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
            AllChem.MMFFOptimizeMolecule(mol)
        except:
            print("   ⚠️ 3D generation failed")
            continue
        
        # Calculate basic properties
        mol_weight = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        qed = QED.qed(mol)
        
        print(f"   MW: {mol_weight:.1f} | LogP: {logp:.2f} | QED: {qed:.3f}")
        
        # Save PDB
        pdb_file = f"docking_results/random_{i+1}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        # Convert to PDBQT
        pdbqt_file = f"docking_results/random_{i+1}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True, timeout=30)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            print("   ❌ PDBQT conversion failed")
            continue
        
        # Run Gnina
        output_file = f"docking_results/random_{i+1}_out.pdbqt"
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 6 --num_modes 3 --exhaustiveness 6 --cpu 6 -o {output_file} 2>/dev/null"
        
        try:
            subprocess.run(cmd, shell=True, timeout=180)
        except subprocess.TimeoutExpired:
            print("   ⏰ Timeout")
            continue
        
        # Extract score
        vina = None
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, 'r') as f:
                content = f.read()
                for line in content.split('\n'):
                    if "REMARK Vina score:" in line:
                        vina = float(line.split(':')[1].strip().split()[0])
                        break
        
        if vina:
            print(f"   ✅ Vina: {vina:.2f} kcal/mol")
            results.append({
                "candidate": i+1,
                "ring": cand['ring'],
                "linker": cand['linker'],
                "atom": cand['atom'],
                "group": cand['group'],
                "vina": vina,
                "smiles": cand['smiles'],
                "mw": mol_weight,
                "logp": logp,
                "qed": qed
            })
        else:
            print("   ❌ No score")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Save results
with open("random_docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("🎲 RANDOM QUANTUM SEARCH RESULTS")
print("="*80)
print(f"\nValid SMILES: {valid_smiles_count}/{len(candidates[:30])}")
print(f"Successful dockings: {len(results)}")

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    
    print(f"\n{'Rank':<4} {'Ring':<12} {'Linker':<12} {'Atom':<8} {'Group':<12} {'Vina':<8} {'QED':<6}")
    print("-"*75)
    
    for i, r in enumerate(sorted_results[:15]):
        print(f"{i+1:<4} {r['ring']:<12} {r['linker']:<12} {r['atom']:<8} {r['group']:<12} {r['vina']:<8.2f} {r['qed']:<6.3f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST RANDOM CANDIDATE: {best['vina']:.2f} kcal/mol")
    print(f"   Structure: {best['ring']} + {best['linker']} + {best['atom']} + {best['group']}")
    
    # Compare with guided search results
    print("\n" + "="*80)
    print("📊 COMPARISON: Random vs Guided Quantum Search")
    print("="*80)
    print(f"\n{'Search Type':<20} {'Best Vina':<12} {'Discovery Rate':<15}")
    print("-"*50)
    print(f"{'Guided Search':<20} {'-11.357':<12} {'3 leads > -11.18':<15}")
    print(f"{'Random Search':<20} {best['vina']:<12.2f} {len([r for r in results if r['vina'] < -9.0]):<15}")
    
    if best['vina'] < -11.0:
        print("\n✅ Random search found a promising compound!")
        print(f"   Best random candidate: {best['vina']:.2f} kcal/mol")
        print(f"   This is within 0.36 kcal/mol of guided search's best!")
    else:
        print("\n⚠️ Random search did not match guided search performance")
        print(f"   Gap to guided best: {best['vina'] + 11.357:.2f} kcal/mol")
        print(f"   Guided search's fragment library was essential for success")
else:
    print("\n❌ No successful dockings from random search")
    print("\nThis suggests that GUIDED quantum search (with prior fragment knowledge)")
    print("is essential for discovering high-affinity compounds.")

print("\n" + "="*80)
print("🎯 CONCLUSION:")
print("="*80)
print("\nThe Random Quantum Search tests whether Grover's algorithm can discover")
print("novel drug candidates without any prior chemical knowledge.")
print("\nIf successful, it would suggest quantum can explore entirely new chemical space.")
print("If less successful, it validates that guided search (building on prior discoveries)")
print("is the optimal approach for quantum drug discovery.")
print("\n" + "="*80)

