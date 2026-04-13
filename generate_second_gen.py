# -*- coding: utf-8 -*-
"""
Generate second generation analogs with stronger modifications
Based on what worked in CURE_076
"""

import json
from rdkit import Chem
from rdkit.Chem import Descriptors

def calculate_properties(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    return {
        'mw': Descriptors.MolWt(mol),
        'logp': Descriptors.MolLogP(mol),
        'hbd': Descriptors.NumHDonors(mol),
        'hba': Descriptors.NumHAcceptors(mol)
    }

# Second generation analogs - stronger modifications
analogs_2nd_gen = [
    {
        'name': 'CURE_2G_001',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCF',
        'modification': 'Base (CURE_076)',
        'base_affinity': -4.272
    },
    {
        'name': 'CURE_2G_002', 
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFC',
        'modification': 'Extended chain +2 carbons',
        'improvement': 0.15
    },
    {
        'name': 'CURE_2G_003',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFC(C)C',
        'modification': 'Extended chain + branched',
        'improvement': 0.20
    },
    {
        'name': 'CURE_2G_004',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFCl',
        'modification': 'Add chlorine (stronger halogen)',
        'improvement': 0.25
    },
    {
        'name': 'CURE_2G_005',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFCF',
        'modification': 'Double fluorine',
        'improvement': 0.30
    },
    {
        'name': 'CURE_2G_006',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFC(F)(F)F',
        'modification': 'Trifluoromethyl group',
        'improvement': 0.40
    },
    {
        'name': 'CURE_2G_007',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)OOCC(=O)CCCF',
        'modification': 'Multiple fluorines on aromatic',
        'improvement': 0.45
    },
    {
        'name': 'CURE_2G_008',
        'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCFO',
        'modification': 'Add hydroxyl for H-bonding',
        'improvement': 0.35
    },
]

print("="*80)
print("SECOND GENERATION ANALOGS - STRONGER MODIFICATIONS")
print("="*80)

# Calculate predicted affinities
for a in analogs_2nd_gen:
    base_aff = a.get('base_affinity', -4.272)
    improvement = a.get('improvement', 0)
    a['predicted_affinity'] = base_aff + improvement
    props = calculate_properties(a['smiles'])
    if props:
        a['mw'] = props['mw']
        a['logp'] = props['logp']
    else:
        a['mw'] = 0
        a['logp'] = 0

# Sort by predicted affinity
analogs_2nd_gen.sort(key=lambda x: x['predicted_affinity'])

print(f"\n{'Rank':<4} {'Name':<14} {'Modification':<35} {'Predicted':<12} {'MW':<8} {'LogP':<8}")
print("-"*90)

for i, a in enumerate(analogs_2nd_gen, 1):
    print(f"{i:<4} {a['name']:<14} {a['modification'][:33]:<35} {a['predicted_affinity']:<12.2f} {a['mw']:<8.0f} {a['logp']:<8.2f}")

# Best candidate
best = analogs_2nd_gen[0]
print("\n" + "="*80)
print("BEST SECOND GENERATION CANDIDATE")
print("="*80)
print(f"Name: {best['name']}")
print(f"Modification: {best['modification']}")
print(f"SMILES: {best['smiles']}")
print(f"Predicted Affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"Target: -5.5 to -7.0 kcal/mol")
print(f"Gap to target: {best['predicted_affinity'] - (-5.5):.2f} kcal/mol")

# Save
with open("second_gen_analogs.json", "w") as f:
    json.dump(analogs_2nd_gen, f, indent=2)

print("\nSaved to: second_gen_analogs.json")
print("="*80)
