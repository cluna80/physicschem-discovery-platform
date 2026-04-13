#!/usr/bin/env python3
"""
Dock new fragment combinations to find the best new building blocks
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
print("🔬 DOCKING NEW FRAGMENT COMBINATIONS")
print("Testing new cores, P1 groups, P2 groups, and linkers")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load test compounds
with open("test_compounds.json", "r") as f:
    compounds = json.load(f)

print(f"\n📊 Loaded {len(compounds)} test compounds")

# Find receptor
RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../gnina_results/protein.pdbqt"

REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

print(f"Receptor: {RECEPTOR}")

os.makedirs("docking_results", exist_ok=True)

results = []
valid_count = 0

print(f"\n🔬 Docking {len(compounds)} test compounds...")
print("-"*80)

for i, comp in enumerate(compounds):
    print(f"\n[{i+1}/{len(compounds)}] {comp['core']} + {comp['p1']} + {comp['p2']} + {comp['linker']}")
    
    try:
        mol = Chem.MolFromSmiles(comp['smiles'])
        if mol is None:
            print("   ❌ Invalid SMILES")
            continue
        
        valid_count += 1
        mol = Chem.AddHs(mol)
        
        # Generate 3D structure
        try:
            AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
            AllChem.MMFFOptimizeMolecule(mol)
        except:
            print("   ⚠️ 3D generation failed")
            continue
        
        # Calculate properties
        mol_weight = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        qed = QED.qed(mol)
        
        print(f"   MW: {mol_weight:.1f} | LogP: {logp:.2f} | QED: {qed:.3f}")
        
        # Save PDB
        pdb_file = f"docking_results/test_{i+1}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        # Convert to PDBQT
        pdbqt_file = f"docking_results/test_{i+1}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True, timeout=30)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            print("   ❌ PDBQT conversion failed")
            continue
        
        # Run Gnina
        output_file = f"docking_results/test_{i+1}_out.pdbqt"
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
                "id": i+1,
                "core": comp['core'],
                "p1": comp['p1'],
                "p2": comp['p2'],
                "linker": comp['linker'],
                "vina": vina,
                "mw": mol_weight,
                "logp": logp,
                "qed": qed,
                "smiles": comp['smiles']
            })
        else:
            print("   ❌ No score")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Save results
with open("fragment_docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("🔬 NEW FRAGMENT DOCKING RESULTS")
print("="*80)
print(f"\nValid SMILES: {valid_count}/{len(compounds)}")
print(f"Successful dockings: {len(results)}")

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    
    print(f"\n{'Rank':<4} {'Core':<15} {'P1':<12} {'P2':<12} {'Linker':<12} {'Vina':<8} {'QED':<6}")
    print("-"*85)
    
    for i, r in enumerate(sorted_results[:20]):
        print(f"{i+1:<4} {r['core']:<15} {r['p1']:<12} {r['p2']:<12} {r['linker']:<12} {r['vina']:<8.2f} {r['qed']:<6.3f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST NEW FRAGMENT COMBINATION: {best['core']} + {best['p1']} + {best['p2']} + {best['linker']}")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    print(f"   QED: {best['qed']:.3f}")
    
    # Compare to existing library
    print("\n" + "="*80)
    print("📊 COMPARISON: New Fragments vs Existing Library")
    print("="*80)
    print(f"\n{'Fragment Set':<20} {'Best Vina':<12} {'Compounds Tested':<15}")
    print("-"*55)
    print(f"{'Existing Library':<20} {'-11.357':<12} {'9':<15}")
    print(f"{'New Fragments':<20} {best['vina']:<12.2f} {len(results):<15}")
    
    if best['vina'] < -11.357:
        print(f"\n✅ NEW FRAGMENTS FOUND BETTER LEADS! by {abs(best['vina'] + 11.357):.2f} kcal/mol!")
        print(f"   Add these to your library:")
        print(f"   - Core: {best['core']}")
        print(f"   - P1: {best['p1']}")
        print(f"   - P2: {best['p2']}")
        print(f"   - Linker: {best['linker']}")
    else:
        print(f"\n📈 Best new fragment combination: {best['vina']:.2f} kcal/mol")
        print(f"   Gap to existing best: {best['vina'] + 11.357:.2f} kcal/mol")
        print(f"   Keep testing — some fragments may work better in combination with existing ones")
else:
    print("\n❌ No successful dockings")

print("\n" + "="*80)
print("🎯 RECOMMENDATIONS:")
print("="*80)
print("""
1. Add top-performing new fragments to your fragment library
2. Run a new 15-qubit guided search with the expanded library
3. Test combinations of new and existing fragments
4. Look for synergistic effects (e.g., new core + existing P1)
5. Discover compounds that beat -11.357!
""")
print("="*80)

