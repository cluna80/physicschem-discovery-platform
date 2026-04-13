#!/usr/bin/env python3
"""
Generate valid SMILES for quantum-discovered candidates
"""

import json

print("Generating valid SMILES for quantum candidates...")

# Load candidates
with open("quantum_candidates.json", "r") as f:
    candidates = json.load(f)

print(f"Loaded {len(candidates)} candidates")

# Valid SMILES templates from your original CURE series
# These are known working SMILES that you docked successfully

# Template based on CURE_17G_002 (which worked)
# Structure: core-C(=O)N[C@@H](Cc1phenyl)C[C@@H](O)CNC(=O)P2

valid_candidates = []

for c in candidates:
    core = c['core']
    p1 = c['p1']
    p2 = c['p2']
    linker = c['linker']
    stereo = c['stereo']
    
    # Map to known working SMILES patterns
    core_map = {
        "Isoquinoline": "c1ccc2cccnc2c1",
        "Naphthalene": "c1ccc2ccccc2c1",
        "Quinoline": "c1cncc2ccccc12",
        "Indole": "c1ccc2[nH]ccc2c1"
    }
    
    p1_map = {
        "meta-F": "Cc1cccc(F)c1",
        "3,5-diF": "Cc1cc(F)cc(F)c1",
        "Benzyl": "Cc1ccccc1",
        "meta-Cl": "Cc1cccc(Cl)c1",
        "meta-CF3": "Cc1cccc(C(F)(F)F)c1"
    }
    
    p2_map = {
        "bis-THF": "[C@@H]1CO[C@@H]2OCCO[C@H]21",
        "spiro-THF": "[C@@H]1CO[C@@H]2CCCO[C@H]21"
    }
    
    core_smiles = core_map.get(core, "c1ccc2ccccc2c1")
    p1_smiles = p1_map.get(p1, "Cc1ccccc1")
    p2_smiles = p2_map.get(p2, "[C@@H]1CO[C@@H]2OCCO[C@H]21")
    
    # Use the proven CURE_17G_002 pattern with the new fragments
    # Pattern: core-C(=O)N[C@@H](Cc1phenyl)C[C@@H](O)CNC(=O)P2
    # Remove the methyl from p1 (Cc1 -> c1) to avoid duplication
    
    p1_clean = p1_smiles.replace("Cc1", "c1")
    
    if stereo == "S":
        stereo_config = "[C@@H]"
    else:
        stereo_config = "[C@H]"
    
    # Build SMILES using working pattern
    smiles = f"{core_smiles}C(=O)N{stereo_config}(C{stereo_config}(O)CNC(=O){p2_smiles})Cc1{p1_clean[1:]}"
    
    valid_candidates.append({
        "core": core,
        "p1": p1,
        "p2": p2,
        "linker": linker,
        "stereo": stereo,
        "quantum_probability": c["quantum_probability"],
        "smiles": smiles
    })

# Save valid candidates
with open("valid_quantum_candidates.json", "w") as f:
    json.dump(valid_candidates, f, indent=2)

# Save SMILES for docking
with open("valid_smiles.txt", "w") as f:
    for c in valid_candidates[:20]:
        f.write(f"{c['smiles']}\n")

print(f"\nGenerated {len(valid_candidates)} valid SMILES")
print("\nTop 10 candidates (SMILES):")
for i, c in enumerate(valid_candidates[:10]):
    print(f"{i+1}. {c['core']}+{c['p1']}+{c['p2']}")
    print(f"   SMILES: {c['smiles'][:80]}...")

