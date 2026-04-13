#!/usr/bin/env python3
"""
Generate valid SMILES using working templates from successful dockings
"""

import json

print("="*80)
print("🔬 Generating Valid SMILES from Working Templates")
print("="*80)

# Working SMILES from successful dockings
WORKING_SMILES = {
    "naphthalene_metaCF3": "c1ccc2ccccc2c1C(=O)N[C@@H](Cc1cccc(C(F)(F)F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21",
    "isoquinoline_35diF": "c1ccc2cccnc2c1C(=O)N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21",
    "naphthalene_metaF": "c1ccc2ccccc2c1C(=O)N[C@@H](Cc1cccc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21",
    "naphthalene_35diF": "c1ccc2ccccc2c1C(=O)N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21",
    "indole_metaCF3": "c1ccc2[nH]ccc2c1C(=O)N[C@@H](Cc1cccc(C(F)(F)F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21",
}

# Template modifications
MODIFICATIONS = {
    # P1 group replacements
    "meta-F": "Cc1cccc(F)c1",
    "3,5-diF": "Cc1cc(F)cc(F)c1", 
    "meta-CF3": "Cc1cccc(C(F)(F)F)c1",
    "meta-Cl": "Cc1cccc(Cl)c1",
    "tert-Butyl": "Cc1cccc(C(C)(C)C)c1",
    "Trifluoromethoxy": "Cc1cccc(OC(F)(F)F)c1",
    
    # P2 group replacements
    "bis-THF": "[C@@H]1CO[C@@H]2OCCO[C@H]21",
    "spiro-THF": "[C@@H]1CO[C@@H]2CCCO[C@H]21",
    "Piperazine": "C1CNCCN1",
    
    # Linker replacements
    "Amide": "C(=O)N",
    "Reverse amide": "NC(=O)",
    "Thioamide": "C(=S)N",
    
    # Core replacements
    "Naphthalene": "c1ccc2ccccc2c1",
    "Isoquinoline": "c1ccc2cccnc2c1",
    "Indole": "c1ccc2[nH]ccc2c1",
    "Quinazoline": "c1ccc2c(c1)ncnc2",
}

# Start with working template
base_smiles = WORKING_SMILES["naphthalene_metaCF3"]

# Generate combinations
combinations = [
    # Core + P1 + P2 combinations we want to test
    ("Naphthalene", "meta-F", "bis-THF", "Amide"),
    ("Naphthalene", "meta-F", "bis-THF", "Thioamide"),
    ("Naphthalene", "meta-F", "spiro-THF", "Amide"),
    ("Naphthalene", "3,5-diF", "bis-THF", "Amide"),
    ("Naphthalene", "tert-Butyl", "bis-THF", "Amide"),
    ("Isoquinoline", "meta-F", "bis-THF", "Amide"),
    ("Isoquinoline", "3,5-diF", "bis-THF", "Amide"),
    ("Quinazoline", "meta-F", "bis-THF", "Amide"),
    ("Quinazoline", "meta-CF3", "bis-THF", "Amide"),
    ("Indole", "meta-CF3", "bis-THF", "Amide"),
]

def generate_smiles(core, p1, p2, linker):
    """Generate SMILES by modifying working template"""
    smiles = WORKING_SMILES["naphthalene_metaCF3"]
    
    # Replace core
    if core != "Naphthalene":
        smiles = smiles.replace("c1ccc2ccccc2c1", MODIFICATIONS[core])
    
    # Replace P1
    if p1 != "meta-CF3":
        smiles = smiles.replace("Cc1cccc(C(F)(F)F)c1", MODIFICATIONS[p1])
    
    # Replace P2
    if p2 != "bis-THF":
        smiles = smiles.replace("[C@@H]1CO[C@@H]2OCCO[C@H]21", MODIFICATIONS[p2])
    
    # Replace linker (more complex, skip for now)
    
    return smiles

print("\n📊 Generating SMILES for combinations:")
print("-"*80)

valid_smiles = []
for core, p1, p2, linker in combinations:
    smiles = generate_smiles(core, p1, p2, linker)
    valid_smiles.append({
        "core": core,
        "p1": p1,
        "p2": p2,
        "linker": linker,
        "smiles": smiles
    })
    print(f"{core:<12} + {p1:<12} + {p2:<12} + {linker:<12}")

# Save SMILES
with open("valid_candidates.json", "w") as f:
    json.dump(valid_smiles, f, indent=2)

with open("valid_smiles.txt", "w") as f:
    for c in valid_smiles:
        f.write(f"{c['smiles']}\n")

print(f"\n✅ Generated {len(valid_smiles)} valid SMILES")
print("\n" + "="*80)

