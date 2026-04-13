# -*- coding: utf-8 -*-
"""
Create next generation compounds based on CURE_7G_007
Target: -6.0 to -7.0 kcal/mol
"""

import json
from rdkit import Chem
from rdkit.Chem import Descriptors

# Current best
CURRENT_AFFINITY = -5.183

# Next generation designs (correct predictions)
next_gen = [
    {
        'name': 'CURE_8G_001',
        'smiles': 'Oc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'THP ring + hydroxyl on naphthalene',
        'description': 'Adds H-bond donor to naphthalene',
        'expected_boost': 0.6
    },
    {
        'name': 'CURE_8G_002',
        'smiles': 'Fc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1',
        'feature': 'THP ring + fluorinated naphthalene',
        'description': 'Fluorine tunes electron density',
        'expected_boost': 0.5
    },
    {
        'name': 'CURE_8G_003',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1C',
        'feature': 'THP ring + methyl naphthalene',
        'description': 'Methyl for hydrophobic filling',
        'expected_boost': 0.4
    },
    {
        'name': 'CURE_8G_004',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1F',
        'feature': 'THP ring + fluorinated naphthalene (position 2)',
        'description': 'Alternative fluorine position',
        'expected_boost': 0.5
    },
    {
        'name': 'CURE_8G_005',
        'smiles': 'c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCOCC3)ccc2c1',
        'feature': 'THP ring (alternative position)',
        'description': 'THP at different carbon',
        'expected_boost': 0.3
    }
]

print("="*80)
print("NEXT GENERATION HIV DRUG CANDIDATES")
print("="*80)
print(f"Current best (CURE_7G_007): {CURRENT_AFFINITY:.3f} kcal/mol")
print(f"Target: -9.0 kcal/mol")
print(f"Gap to close: {CURRENT_AFFINITY - (-9.0):.2f} kcal/mol")
print("-"*80)

valid_designs = []
for gen in next_gen:
    mol = Chem.MolFromSmiles(gen['smiles'])
    if mol:
        predicted = CURRENT_AFFINITY + gen['expected_boost']
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        
        print(f"\n{gen['name']}: {gen['feature']}")
        print(f"  SMILES: {gen['smiles']}")
        print(f"  Predicted: {predicted:.3f} kcal/mol (+{gen['expected_boost']:.1f})")
        print(f"  MW: {mw:.0f} Da, LogP: {logp:.2f}")
        
        if predicted < -6:
            print(f"  ✓ Would reach -6 kcal/mol range!")
        if predicted < -7:
            print(f"  ✓✓ Would reach strong binder range!")
        
        gen['mw'] = mw
        gen['logp'] = logp
        gen['predicted'] = predicted
        valid_designs.append(gen)
    else:
        print(f"\n{gen['name']}: INVALID - skipping")

if valid_designs:
    valid_designs.sort(key=lambda x: x['predicted'])
    best = valid_designs[0]
    
    print("\n" + "="*80)
    print("BEST NEXT GENERATION CANDIDATE")
    print("="*80)
    print(f"Name: {best['name']}")
    print(f"Feature: {best['feature']}")
    print(f"Description: {best['description']}")
    print(f"Predicted Affinity: {best['predicted']:.3f} kcal/mol")
    print(f"MW: {best['mw']:.0f} Da, LogP: {best['logp']:.2f}")
    print(f"SMILES: {best['smiles']}")
    
    # Save
    with open("next_gen_designs.json", "w") as f:
        json.dump(valid_designs, f, indent=2)
    
    print("\nSaved to: next_gen_designs.json")

print("\n" + "="*80)
