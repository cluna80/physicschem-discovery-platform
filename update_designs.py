# -*- coding: utf-8 -*-
"""
Updated DESIGNS for cure_dock_quantum.py
CURE_15G series - P1' pocket filling + stereochemistry variants
"""

# Copy this into your cure_dock_quantum.py DESIGNS section

DESIGNS = [
    {
        "name": "CURE_15G_001",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "note": "Baseline reconfirm 15G",
        "target": "Confirm baseline affinity"
    },
    {
        "name": "CURE_15G_002",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CN(C)C(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "note": "N-methyl linker — fills P1' with methyl",
        "target": "+0.2-0.4 kcal/mol improvement"
    },
    {
        "name": "CURE_15G_003",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "note": "Extend box size 30 — check if compound escapes box",
        "target": "Same as baseline, verify docking box"
    },
    {
        "name": "CURE_15G_004",
        "smiles": "FC(F)(F)c1cccc(C[C@@H](NC(=O)c2ccc3cc(C(=O)N[C@@H](Cc4cccc(F)c4)[C@@H](O)CNC(=O)[C@@H]5CO[C@@H]6OCCO[C@@H]56)ccc3c2)CC(=O)O)c1",
        "note": "Skip — too large, MW > 600",
        "skip": True
    },
    {
        "name": "CURE_15G_005",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@H]4CO[C@H]5OCCO[C@@H]45)ccc2c1",
        "note": "All R bis-THF stereo variant",
        "target": "Test opposite stereochemistry"
    },
]

BASELINE = {"name": "CURE_13G_001", "affinity": -7.333}

print("="*80)
print("CURE_15G DESIGNS READY")
print("="*80)
print(f"Baseline: {BASELINE['name']} at {BASELINE['affinity']:.3f} kcal/mol")
print(f"Target: -9.0 kcal/mol")
print(f"Gap to close: {BASELINE['affinity'] - (-9.0):.2f} kcal/mol")
print("-"*80)

for d in DESIGNS:
    if not d.get('skip', False):
        print(f"\n{d['name']}:")
        print(f"  SMILES: {d['smiles'][:80]}...")
        print(f"  Note: {d['note']}")
        if 'target' in d:
            print(f"  Expected: {d['target']}")

print("\n" + "="*80)
print("TO RUN: python cure_dock_quantum.py --quantum")
print("This will dock all CURE_15G compounds with quantum prioritization")
print("="*80)

# Save to file for reference
import json
with open("cure_15g_designs.json", "w") as f:
    json.dump(DESIGNS, f, indent=2)

print("\nSaved: cure_15g_designs.json")
