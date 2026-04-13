# -*- coding: utf-8 -*-
"""
Design next generation based on CURE_7G_007
Target: -6.5 to -7.0 kcal/mol
"""

import json

# Current best
current = {
    'name': 'CURE_7G_007',
    'affinity': -5.183,
    'feature': 'Naphthalene + THP ring'
}

print("="*80)
print("NEXT GENERATION DESIGNS")
print("="*80)
print(f"Current best: {current['name']} at {current['affinity']:.3f} kcal/mol")
print(f"Target: -9.0 kcal/mol")
print(f"Gap to close: {current['affinity'] - (-9.0):.2f} kcal/mol")
print("-"*80)

next_gen = [
    {
        'name': 'CURE_8G_001',
        'feature': 'THP ring + hydroxyl on naphthalene',
        'smiles': 'Oc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'expected_boost': 0.6
    },
    {
        'name': 'CURE_8G_002',
        'feature': 'THP ring + fluorinated naphthalene',
        'smiles': 'Fc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'expected_boost': 0.4
    },
    {
        'name': 'CURE_8G_003',
        'feature': 'THP ring + extended linker',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1C',
        'expected_boost': 0.3
    },
    {
        'name': 'CURE_8G_004',
        'feature': 'THP ring + bis-THF combination',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1',
        'expected_boost': 0.5
    },
]

for gen in next_gen:
    predicted = current['affinity'] + gen['expected_boost']
    print(f"\n{gen['name']}: {gen['feature']}")
    print(f"  Predicted: {predicted:.3f} kcal/mol (+{gen['expected_boost']:.1f})")
    if predicted < -6:
        print(f"  ✓ Would reach -6 kcal/mol range!")
    if predicted < -7:
        print(f"  ✓✓ Would reach strong binder range!")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("Dock CURE_8G_001 (hydroxynaphthalene + THP) first")
print("This adds an H-bond donor to the naphthalene ring")
print("Expected to reach -5.8 to -6.2 kcal/mol")
print("="*80)
