#!/usr/bin/env python3
"""
Dock expanded fragment combinations with Gnina
Testing best combinations from expanded fragment library
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors, QED

print("="*80)
print("🔬 DOCKING EXPANDED FRAGMENT COMBINATIONS")
print("Testing best combinations from expanded fragment library")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load expanded candidates
try:
    with open("expanded_candidates.json", "r") as f:
        candidates = json.load(f)
    print(f"\n📊 Loaded {len(candidates)} expanded candidates")
except:
    print("❌ expanded_candidates.json not found")
    sys.exit(1)

# Find receptor
RECEPTOR = "resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "gnina_results/protein.pdbqt"
    if not os.path.exists(RECEPTOR):
        RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"

REF_LIGAND = "resistance_profiling/ligand_split_1.pdbqt"
if not os.path.exists(REF_LIGAND):
    REF_LIGAND = "gnina_results/CURE_17G_002_out.pdbqt"
    if not os.path.exists(REF_LIGAND):
        REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

print(f"Receptor: {RECEPTOR}")
print(f"Reference: {REF_LIGAND}")

os.makedirs("expanded_docking", exist_ok=True)

results = []
valid_count = 0

print(f"\n🔬 Docking {len(candidates)} expanded candidates...")
print("-"*80)

for i, cand in enumerate(candidates[:20]):
    print(f"\n[{i+1}/{len(candidates)}] {cand['core']} + {cand['p1']} + {cand['p2']} + {cand['linker']} ({cand['stereo']})")
    
    try:
        mol = Chem.MolFromSmiles(cand['smiles'])
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
        pdb_file = f"expanded_docking/cand_{i+1}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        # Convert to PDBQT
        pdbqt_file = f"expanded_docking/cand_{i+1}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True, timeout=30)
        
        if not os.path.exists(pdbqt_file) or os.path.getsize(pdbqt_file) == 0:
            print("   ❌ PDBQT conversion failed")
            continue
        
        # Run Gnina
        output_file = f"expanded_docking/cand_{i+1}_out.pdbqt"
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
                "core": cand['core'],
                "p1": cand['p1'],
                "p2": cand['p2'],
                "linker": cand['linker'],
                "stereo": cand['stereo'],
                "combined_score": cand.get('combined_score', 0),
                "vina": vina,
                "mw": mol_weight,
                "logp": logp,
                "qed": qed,
                "smiles": cand['smiles']
            })
        else:
            print("   ❌ No score")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Save results
with open("expanded_docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("🔬 EXPANDED FRAGMENT DOCKING RESULTS")
print("="*80)
print(f"\nValid SMILES: {valid_count}/{len(candidates[:20])}")
print(f"Successful dockings: {len(results)}")

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    
    print(f"\n{'Rank':<4} {'Core':<12} {'P1':<12} {'P2':<12} {'Linker':<12} {'Stereo':<5} {'Vina':<8} {'QED':<6}")
    print("-"*85)
    
    for i, r in enumerate(sorted_results[:15]):
        print(f"{i+1:<4} {r['core']:<12} {r['p1']:<12} {r['p2']:<12} {r['linker']:<12} {r['stereo']:<5} {r['vina']:<8.2f} {r['qed']:<6.3f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST EXPANDED CANDIDATE: {best['core']} + {best['p1']} + {best['p2']} + {best['linker']} ({best['stereo']})")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    print(f"   QED: {best['qed']:.3f}")
    
    # Compare with previous best
    print("\n" + "="*80)
    print("📊 COMPARISON")
    print("="*80)
    print(f"\n{'Compound':<25} {'Vina (kcal/mol)':<15} {'Improvement':<12}")
    print("-"*55)
    print(f"{'CURE_17G_002':<25} {'-11.180':<15} {'Baseline':<12}")
    print(f"{'naphthalene_metaCF3':<25} {'-11.357':<15} {'+0.177':<12}")
    print(f"{'Best Expanded':<25} {best['vina']:<15.2f} {best['vina'] + 11.357:+.3f}")

    if best['vina'] < -11.357:
        print(f"\n✅ NEW LEAD! Beats previous best by {abs(best['vina'] + 11.357):.3f} kcal/mol!")
    elif best['vina'] < -11.18:
        print(f"\n✅ Beats CURE_17G_002 by {abs(best['vina'] + 11.18):.3f} kcal/mol")
    else:
        print(f"\n📈 Gap to beat: {best['vina'] + 11.357:.3f} kcal/mol")
else:
    print("\n❌ No successful dockings")

print("\n" + "="*80)

