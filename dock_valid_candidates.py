#!/usr/bin/env python3
"""
Dock valid candidates using working SMILES templates
"""

import subprocess
import json
import os
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors, QED

print("="*80)
print("🔬 DOCKING VALID CANDIDATES")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Load valid candidates
with open("valid_candidates.json", "r") as f:
    candidates = json.load(f)

print(f"\n📊 Loaded {len(candidates)} valid candidates")

# Find receptor
RECEPTOR = "resistance_profiling/docking_out/prot_WT.pdbqt"
if not os.path.exists(RECEPTOR):
    RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"

REF_LIGAND = "resistance_profiling/ligand_split_1.pdbqt"
if not os.path.exists(REF_LIGAND):
    REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

print(f"Receptor: {RECEPTOR}")

os.makedirs("docking_valid", exist_ok=True)

results = []

print(f"\n🔬 Docking {len(candidates)} candidates...")
print("-"*80)

for i, cand in enumerate(candidates):
    print(f"\n[{i+1}] {cand['core']} + {cand['p1']} + {cand['p2']} + {cand['linker']}")
    
    try:
        mol = Chem.MolFromSmiles(cand['smiles'])
        if mol is None:
            print("   ❌ Invalid SMILES")
            continue
        
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
        
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        qed = QED.qed(mol)
        
        print(f"   MW: {mw:.1f} | LogP: {logp:.2f} | QED: {qed:.3f}")
        
        pdb_file = f"docking_valid/cand_{i+1}.pdb"
        Chem.MolToPDBFile(mol, pdb_file)
        
        pdbqt_file = f"docking_valid/cand_{i+1}.pdbqt"
        subprocess.run(f"obabel {pdb_file} -O {pdbqt_file} -p 7.4 2>/dev/null", shell=True)
        
        output_file = f"docking_valid/cand_{i+1}_out.pdbqt"
        cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 6 --num_modes 3 --exhaustiveness 6 --cpu 6 -o {output_file} 2>/dev/null"
        
        subprocess.run(cmd, shell=True, timeout=180)
        
        vina = None
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, 'r') as f:
                for line in f:
                    if "REMARK Vina score:" in line:
                        vina = float(line.split(':')[1].strip().split()[0])
                        break
        
        if vina:
            print(f"   ✅ Vina: {vina:.2f} kcal/mol")
            results.append({
                "core": cand['core'],
                "p1": cand['p1'],
                "p2": cand['p2'],
                "linker": cand['linker'],
                "vina": vina,
                "qed": qed
            })
        else:
            print("   ❌ No score")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

# Save results
with open("valid_docking_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n" + "="*80)
print("RESULTS")
print("="*80)

if results:
    sorted_results = sorted(results, key=lambda x: x['vina'])
    
    print(f"\n{'Rank':<4} {'Core':<12} {'P1':<12} {'P2':<12} {'Linker':<12} {'Vina':<8} {'QED':<6}")
    print("-"*70)
    
    for i, r in enumerate(sorted_results):
        print(f"{i+1:<4} {r['core']:<12} {r['p1']:<12} {r['p2']:<12} {r['linker']:<12} {r['vina']:<8.2f} {r['qed']:<6.3f}")
    
    best = sorted_results[0]
    print(f"\n🏆 BEST CANDIDATE: {best['core']} + {best['p1']} + {best['p2']}")
    print(f"   Vina: {best['vina']:.2f} kcal/mol")
    print(f"   QED: {best['qed']:.3f}")
    
    # Compare to best existing
    print(f"\nReference:")
    print(f"   naphthalene_metaCF3: -11.357 kcal/mol")
    if best['vina'] < -11.357:
        print(f"\n✅ NEW LEAD! Better by {abs(best['vina'] + 11.357):.3f} kcal/mol!")
    else:
        print(f"\n📈 Gap to best: {best['vina'] + 11.357:.3f} kcal/mol")
else:
    print("\n❌ No successful dockings")

print("\n" + "="*80)

