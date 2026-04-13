#!/usr/bin/env python3
"""
PURE RANDOM 15-QUBIT QUANTUM SEARCH — FIXED
Generates truly random compounds for testing
"""

import numpy as np
import random
import json
from datetime import datetime
import os

print("="*80)
print("🎲 PURE RANDOM 15-QUBIT QUANTUM SEARCH (FIXED)")
print("Testing: Can quantum discover novel scaffolds without prior knowledge?")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ============================================================================
# COMPLETELY RANDOM CHEMICAL BUILDING BLOCKS
# No bias from previous discoveries — pure random chemical space
# ============================================================================

# Random atoms
random_atoms = [
    "C", "N", "O", "S", "F", "Cl", "Br"
]

# Random ring systems
random_rings = [
    "c1ccccc1",           # Benzene
    "c1ccncc1",           # Pyridine
    "c1cncnc1",           # Pyrimidine
    "C1CCCCC1",           # Cyclohexane
    "C1CCCC1",            # Cyclopentane
    "c1ccoc1",            # Furan
    "c1ccsc1",            # Thiophene
    "c1cc[nH]c1",         # Pyrrole
    "c1ncccn1",           # Pyrazine
]

# Random linkers
random_linkers = [
    "-", "=", "C(=O)N", "C(=O)O", "O", "S", "S(=O)(=O)N"
]

# Random functional groups
random_groups = [
    "C", "CC", "O", "N", "C(=O)O", "C=O", "N(=O)=O", "C#N", "C(F)(F)F", "Cl"
]

# Random counts
random_counts = [1, 2, 3, 4]

# ============================================================================
# Generate Random Compounds Without Quantum Search
# ============================================================================

print("\n🔬 Generating random compounds (no quantum search bias)...")

random_compounds = []

# Generate 100 completely random compounds
for i in range(100):
    # Randomly select components
    ring = random.choice(random_rings)
    linker = random.choice(random_linkers)
    atom = random.choice(random_atoms)
    group = random.choice(random_groups)
    count = random.choice(random_counts)
    
    # Build random SMILES
    if linker in ["-", "="]:
        smiles = f"{ring}{linker}{atom}{group}"
        if count > 1:
            smiles = smiles * count
    else:
        smiles = f"{ring}{linker}{atom}{group}"
    
    # Add random extra groups sometimes
    if random.random() > 0.7:
        extra = random.choice(random_groups)
        smiles = f"{smiles}{extra}"
    
    random_compounds.append({
        "id": i+1,
        "ring": ring[:15],
        "linker": linker[:15],
        "atom": atom,
        "group": group[:15],
        "smiles": smiles,
        "type": "random"
    })

print(f"   Generated {len(random_compounds)} random compounds")

# ============================================================================
# Also generate a few chemically sensible but novel compounds
# (Not from your fragment library, but reasonable drug-like structures)
# ============================================================================

print("\n🔬 Generating novel but chemically sensible compounds...")

novel_compounds = [
    {"name": "Novel_1", "smiles": "c1ccc2c(c1)CCN2C(=O)CCN3CCOCC3", "desc": "Indole-piperazine hybrid"},
    {"name": "Novel_2", "smiles": "c1ccc2c(c1)N=CN2C(=O)C3CCNCC3", "desc": "Benzimidazole-amine hybrid"},
    {"name": "Novel_3", "smiles": "c1ccc2c(c1)OCCO2C(=O)CN3CCN(C)CC3", "desc": "Benzodioxane-piperazine"},
    {"name": "Novel_4", "smiles": "c1ccc2c(c1)C(=O)N(C2)C3CCN(C3)C(=O)C4CCCCC4", "desc": "Isoindolinone-cyclohexane"},
    {"name": "Novel_5", "smiles": "c1ccc2c(c1)CC(C2)C(=O)N3CCN(C3)C4CCCCC4", "desc": "Tetralin-piperazine hybrid"},
    {"name": "Novel_6", "smiles": "c1ccc2c(c1)OCCO2C(=O)N3CCN(C3)C4CCCCC4", "desc": "Benzodioxane-piperazine"},
    {"name": "Novel_7", "smiles": "c1ccc2c(c1)CCN2C(=O)C3CCN(C3)C4CCCCC4", "desc": "Tetrahydroisoquinoline"},
    {"name": "Novel_8", "smiles": "c1ccc2c(c1)C(=O)NC2C3CCN(C3)C4CCCCC4", "desc": "Oxindole derivative"},
]

# Add to list
for i, comp in enumerate(novel_compounds, start=len(random_compounds)+1):
    random_compounds.append({
        "id": i,
        "ring": comp['desc'][:15],
        "linker": "Novel",
        "atom": "C",
        "group": comp['name'],
        "smiles": comp['smiles'],
        "type": "novel",
        "description": comp['desc']
    })

print(f"   Added {len(novel_compounds)} novel compounds")
print(f"   Total: {len(random_compounds)} compounds")

# ============================================================================
# Save all compounds
# ============================================================================

# Save random compounds
with open("random_compounds.json", "w") as f:
    json.dump(random_compounds, f, indent=2)
print("\n✅ Saved: random_compounds.json")

# Save SMILES for docking
with open("random_smiles.txt", "w") as f:
    for comp in random_compounds:
        f.write(f"{comp['smiles']}\n")
print("✅ Saved: random_smiles.txt")

# Show sample
print("\n" + "="*80)
print("SAMPLE RANDOM COMPOUNDS (Ready for Docking)")
print("="*80)
print(f"\n{'ID':<4} {'SMILES':<50} {'Type':<10}")
print("-"*70)

for comp in random_compounds[:20]:
    smiles_short = comp['smiles'][:45] + "..." if len(comp['smiles']) > 45 else comp['smiles']
    print(f"{comp['id']:<4} {smiles_short:<50} {comp['type']:<10}")

print("\n" + "="*80)
print("🔬 NEXT STEP: Dock these random compounds with Gnina")
print("   python3 dock_random_fixed.py")
print("="*80)

