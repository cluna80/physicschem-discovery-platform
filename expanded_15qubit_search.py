#!/usr/bin/env python3
"""
EXPANDED 15-QUBIT GUIDED SEARCH
Combining existing fragments with new discoveries
"""

import json
import numpy as np
import random
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem

print("="*80)
print("🧬 EXPANDED 15-QUBIT GUIDED SEARCH")
print("Combining existing fragments with new discoveries")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# Expanded fragment library
FRAGMENTS = {
    "cores": [
        {"name": "Naphthalene", "smiles": "c1ccc2ccccc2c1", "score": 0.90},
        {"name": "Isoquinoline", "smiles": "c1ccc2cccnc2c1", "score": 0.85},
        {"name": "Indole", "smiles": "c1ccc2[nH]ccc2c1", "score": 0.70},
        {"name": "Quinazoline", "smiles": "c1ccc2c(c1)ncnc2", "score": 0.82},  # NEW
    ],
    "p1": [
        {"name": "meta-F", "smiles": "Cc1cccc(F)c1", "score": 0.95},
        {"name": "3,5-diF", "smiles": "Cc1cc(F)cc(F)c1", "score": 0.88},
        {"name": "meta-CF3", "smiles": "Cc1cccc(C(F)(F)F)c1", "score": 0.74},
        {"name": "meta-Cl", "smiles": "Cc1cccc(Cl)c1", "score": 0.82},
        {"name": "tert-Butyl", "smiles": "Cc1cccc(C(C)(C)C)c1", "score": 0.80},  # NEW
        {"name": "Trifluoromethoxy", "smiles": "Cc1cccc(OC(F)(F)F)c1", "score": 0.78},  # NEW
    ],
    "p2": [
        {"name": "bis-THF", "smiles": "[C@@H]1CO[C@@H]2OCCO[C@H]21", "score": 0.92},
        {"name": "spiro-THF", "smiles": "[C@@H]1CO[C@@H]2CCCO[C@H]21", "score": 0.85},
        {"name": "Piperazine", "smiles": "C1CNCCN1", "score": 0.72},  # NEW
    ],
    "linkers": [
        {"name": "Amide", "smiles": "C(=O)N", "score": 0.90},
        {"name": "Reverse amide", "smiles": "NC(=O)", "score": 0.82},
        {"name": "Thioamide", "smiles": "C(=S)N", "score": 0.70},  # NEW
    ],
    "stereo": [
        {"config": "[C@H]", "name": "R", "score": 0.75},
        {"config": "[C@@H]", "name": "S", "score": 0.88},
    ]
}

total_combos = len(FRAGMENTS["cores"]) * len(FRAGMENTS["p1"]) * len(FRAGMENTS["p2"]) * len(FRAGMENTS["linkers"]) * len(FRAGMENTS["stereo"])
print(f"\n📊 Expanded Search Space: {total_combos} combinations")
print(f"   Cores: {len(FRAGMENTS['cores'])}")
print(f"   P1: {len(FRAGMENTS['p1'])}")
print(f"   P2: {len(FRAGMENTS['p2'])}")
print(f"   Linkers: {len(FRAGMENTS['linkers'])}")
print(f"   Stereo: {len(FRAGMENTS['stereo'])}")

# Generate all combinations
combinations = []
for core in FRAGMENTS["cores"]:
    for p1 in FRAGMENTS["p1"]:
        for p2 in FRAGMENTS["p2"]:
            for linker in FRAGMENTS["linkers"]:
                for stereo in FRAGMENTS["stereo"]:
                    # Calculate combined score
                    score = core['score'] * 0.35 + p1['score'] * 0.3 + p2['score'] * 0.2 + linker['score'] * 0.1 + stereo['score'] * 0.05
                    
                    combinations.append({
                        "core": core,
                        "p1": p1,
                        "p2": p2,
                        "linker": linker,
                        "stereo": stereo,
                        "combined_score": score
                    })

# Sort by score
combinations.sort(key=lambda x: x['combined_score'], reverse=True)

print(f"\n🏆 TOP 20 COMBINATIONS (by fragment scores):")

for i, combo in enumerate(combinations[:20], 1):
    print(f"{i:2}. {combo['core']['name']:12} + {combo['p1']['name']:12} + {combo['p2']['name']:12} + {combo['linker']['name']:12} + {combo['stereo']['name']:3} = {combo['combined_score']:.3f}")

# Build SMILES for top 20
print(f"\n🔬 Generating SMILES for top 20 combinations...")

top_compounds = []
for i, combo in enumerate(combinations[:20], 1):
    core_smiles = combo['core']['smiles']
    p1_smiles = combo['p1']['smiles'].replace("Cc1", "c1")
    linker_smiles = combo['linker']['smiles']
    p2_smiles = combo['p2']['smiles']
    stereo_config = combo['stereo']['config']
    
    smiles = f"{core_smiles}C(=O)N{stereo_config}(Cc1{p1_smiles[1:]}){stereo_config}(O)CNC(=O){p2_smiles}"
    
    top_compounds.append({
        "rank": i,
        "core": combo['core']['name'],
        "p1": combo['p1']['name'],
        "p2": combo['p2']['name'],
        "linker": combo['linker']['name'],
        "stereo": combo['stereo']['name'],
        "combined_score": combo['combined_score'],
        "smiles": smiles
    })

# Save results
with open("expanded_candidates.json", "w") as f:
    json.dump(top_compounds, f, indent=2)

with open("expanded_smiles.txt", "w") as f:
    for c in top_compounds:
        f.write(f"{c['smiles']}\n")

print(f"\n✅ Saved {len(top_compounds)} candidates to expanded_candidates.json")
print(f"✅ Saved SMILES to expanded_smiles.txt")

print("\n" + "="*80)
print("🚀 NEXT STEP: Dock these candidates with Gnina")
print("   python3 dock_expanded_candidates.py")
print("="*80)

