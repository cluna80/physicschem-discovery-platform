# -*- coding: utf-8 -*-
"""
Dock compounds in order of REAL computed scores
Priority from quantum analysis with real properties
"""

import subprocess
import os
import json
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, QED

# Real-score prioritized compounds
PRIORITY_COMPOUNDS = [
    {
        "name": "CURE_7G_007",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1",
        "feature": "THP ring (6-membered O-ring)",
        "real_score": 2.335
    },
    {
        "name": "CURE_7G_008",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)CC(C)C)ccc2c1",
        "feature": "Isobutyl (low MW, high LogP)",
        "real_score": 2.326
    },
    {
        "name": "CURE_7G_005",
        "smiles": "c1cc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2cc1F",
        "feature": "Fluoronaphthyl",
        "real_score": 2.263
    },
    {
        "name": "CURE_7G_003",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "feature": "Naphthalene + bis-THF",
        "real_score": 2.1
    },
    {
        "name": "CURE_7G_001",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1",
        "feature": "Naphthalene + THF",
        "real_score": 2.153
    },
]

def smiles_to_pdbqt(smiles, output_file):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            
            pdb_file = output_file.replace('.pdbqt', '.pdb')
            Chem.MolToPDBFile(mol, pdb_file)
            
            result = subprocess.run(
                ["obabel", pdb_file, "-O", output_file, "-xh"],
                capture_output=True
            )
            
            if os.path.exists(pdb_file):
                os.remove(pdb_file)
            
            return result.returncode == 0
    except Exception as e:
        print(f"    Error: {e}")
    return False

def calculate_affinity(ligand_file, binding_site):
    cmd = [
        "./bin/vina.exe",
        "--receptor", "hiv_protease.pdbqt",
        "--ligand", ligand_file,
        "--center_x", str(binding_site[0]),
        "--center_y", str(binding_site[1]),
        "--center_z", str(binding_site[2]),
        "--size_x", "25",
        "--size_y", "25",
        "--size_z", "25",
        "--out", "temp_out.pdbqt",
        "--num_modes", "1",
        "--exhaustiveness", "16",
        "--cpu", "6"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    for line in result.stdout.split('\n'):
        if line.strip() and line.strip()[0].isdigit():
            parts = line.strip().split()
            if len(parts) >= 2:
                return float(parts[1])
    return None

print("="*80)
print("REAL-SCORE PRIORITY DOCKING")
print("Based on quantum analysis with real molecular properties")
print("="*80)

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

results = []
for comp in PRIORITY_COMPOUNDS:
    print(f"\n{'='*80}")
    print(f"Priority: {comp['name']}")
    print(f"Feature: {comp['feature']}")
    print(f"Real Score: {comp['real_score']:.3f}")
    print("-"*60)
    
    # Convert to PDBQT
    ligand_file = f"{comp['name']}.pdbqt"
    if smiles_to_pdbqt(comp['smiles'], ligand_file):
        print("  ✓ 3D structure generated")
        
        # Dock
        print("  Running AutoDock Vina...")
        affinity = calculate_affinity(ligand_file, binding_site)
        
        if affinity:
            results.append({
                'name': comp['name'],
                'feature': comp['feature'],
                'real_score': comp['real_score'],
                'affinity': affinity,
                'improvement': affinity - (-6.772)  # vs baseline
            })
            print(f"  ✓ Best affinity: {affinity:.3f} kcal/mol")
            
            # Status update
            if affinity < -7.5:
                print("    ★★★ EXCELLENT - Strong binder!")
            elif affinity < -7.0:
                print("    ★★ GOOD - Very promising!")
            elif affinity < -6.5:
                print("    ★ MODERATE - Solid improvement")
            else:
                print("    → Further optimization needed")
        else:
            print("  ✗ Docking failed")
    else:
        print("  ✗ Could not generate 3D structure")

# Sort by actual docking affinity
results.sort(key=lambda x: x['affinity'])

print("\n" + "="*80)
print("DOCKING RESULTS (Sorted by Actual Binding)")
print("="*80)
print(f"\n{'Rank':<6} {'Compound':<15} {'Feature':<28} {'Affinity':<12} {'Real Score':<12}")
print("-"*80)

for i, r in enumerate(results, 1):
    print(f"{i:<6} {r['name']:<15} {r['feature'][:26]:<28} {r['affinity']:<12.3f} {r['real_score']:<12.3f}")

if results:
    best = results[0]
    print("\n" + "="*80)
    print("BEST CANDIDATE")
    print("="*80)
    print(f"Compound: {best['name']}")
    print(f"Feature: {best['feature']}")
    print(f"Binding Affinity: {best['affinity']:.3f} kcal/mol")
    print(f"Real Score: {best['real_score']:.3f}")
    print(f"Gap to -9.0: {best['affinity'] - (-9.0):.2f} kcal/mol")
    
    if best['affinity'] < -8:
        print("\n✓✓✓ EXCELLENT! Approaching Darunavir potency!")
    elif best['affinity'] < -7.5:
        print("\n✓✓ VERY GOOD! Strong binder!")
    elif best['affinity'] < -7:
        print("\n✓ GOOD! Solid HIV inhibitor!")
    elif best['affinity'] < -6.5:
        print("\n✓ MODERATE! Good progress!")
    else:
        print("\n→ Needs further optimization")
    
    # Save results
    with open("real_priority_docking.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nSaved: real_priority_docking.json")

print("\n" + "="*80)
print("QUANTUM INSIGHT SUMMARY")
print("="*80)
print("""
The quantum analysis with real properties revealed:
1. CURE_7G_007 (THP ring) has the highest real score (2.335)
2. THP ring may fit better than THF in the S2 pocket
3. The isobutyl group (7G_008) offers good hydrophobic filling
4. Fluoronaphthyl (7G_005) tunes electron density optimally

Docking these first will validate the quantum predictions!
""")
print("="*80)
