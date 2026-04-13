# -*- coding: utf-8 -*-
"""
Generate optimized analogs of HIV_CURE_070 to improve binding affinity
Target: -7.0 kcal/mol (HIV drug range)
"""

import json
from rdkit import Chem
from rdkit.Chem import Descriptors

# Base molecule
BASE_SMILES = "C1CCCCC1C(=O)OOCC(=O)O"

def calculate_properties(smiles):
    """Calculate molecular properties"""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    return {
        'mw': Descriptors.MolWt(mol),
        'logp': Descriptors.MolLogP(mol),
        'hbd': Descriptors.NumHDonors(mol),
        'hba': Descriptors.NumHAcceptors(mol)
    }

def predict_affinity(smiles, base_affinity=-4.05):
    """Predict improved affinity based on modifications"""
    props = calculate_properties(smiles)
    if not props:
        return base_affinity
    
    improvement = 0
    
    # Aromatic rings add pi-stacking
    if 'c1' in smiles:
        improvement += 0.7
    
    # Halogens add H-bonding
    if 'F' in smiles or 'Cl' in smiles:
        improvement += 0.4
    
    # Extended chain adds hydrophobic interactions
    if len(smiles) > 30:
        improvement += 0.3
    
    # Optimal LogP improves binding
    if 2 < props['logp'] < 4:
        improvement += 0.3
    
    # Additional hydrogen bond donors
    if props['hbd'] > 1:
        improvement += 0.2
    
    return base_affinity + improvement

# Generate optimized analogs
analogs = [
    {'name': 'CURE_070', 'smiles': BASE_SMILES, 'modification': 'Original'},
    {'name': 'CURE_071', 'smiles': 'c1ccccc1C(=O)OOCC(=O)O', 'modification': 'Aromatic'},
    {'name': 'CURE_072', 'smiles': 'C1CCCCC1C(=O)OOCC(=O)CF', 'modification': 'Fluorine'},
    {'name': 'CURE_073', 'smiles': 'C1CCCCC1C(=O)OOCC(=O)CCC', 'modification': 'Extended chain'},
    {'name': 'CURE_074', 'smiles': 'c1ccccc1C(=O)OOCC(=O)CF', 'modification': 'Aromatic + Fluorine'},
    {'name': 'CURE_075', 'smiles': 'c1ccccc1C(=O)OOCC(=O)CCC', 'modification': 'Aromatic + Extended'},
    {'name': 'CURE_076', 'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCF', 'modification': 'Aromatic + Extended + Fluorine'},
    {'name': 'CURE_077', 'smiles': 'COc1ccccc1C(=O)OOCC(=O)O', 'modification': 'Methoxy'},
    {'name': 'CURE_078', 'smiles': 'C1CCCCC1C(=O)OOCC(=O)NCC', 'modification': 'Amide'},
    {'name': 'CURE_079', 'smiles': 'c1ccccc1C(=O)OOCC(=O)CCCF', 'modification': 'Optimized'},
]

print("="*80)
print("GENERATING OPTIMIZED ANALOGS")
print("="*80)

# Calculate properties and predicted affinities
for a in analogs:
    a['predicted_affinity'] = predict_affinity(a['smiles'])
    props = calculate_properties(a['smiles'])
    if props:
        a['mw'] = props['mw']
        a['logp'] = props['logp']
    else:
        a['mw'] = 0
        a['logp'] = 0

# Sort by predicted affinity
analogs.sort(key=lambda x: x['predicted_affinity'])

print(f"\n{'Name':<12} {'Modification':<30} {'Predicted':<12} {'MW':<8} {'LogP':<8}")
print("-"*75)

for a in analogs:
    print(f"{a['name']:<12} {a['modification'][:28]:<30} {a['predicted_affinity']:<12.2f} {a['mw']:<8.0f} {a['logp']:<8.2f}")

# Best candidate
best = analogs[0]
print("\n" + "="*80)
print("BEST OPTIMIZED CANDIDATE")
print("="*80)
print(f"Name: {best['name']}")
print(f"SMILES: {best['smiles']}")
print(f"Predicted Affinity: {best['predicted_affinity']:.2f} kcal/mol")
print(f"Improvement: {best['predicted_affinity'] - (-4.05):.2f} kcal/mol")
print(f"Target: -7.0 kcal/mol")
print(f"Gap to target: {best['predicted_affinity'] - (-7.0):.2f} kcal/mol")

if best['predicted_affinity'] < -7:
    print("\n✓ This analog reaches the strong binder threshold!")
else:
    print(f"\nNeed {abs(best['predicted_affinity'] - (-7.0)):.2f} kcal/mol more improvement")

# Save analogs
with open("optimized_analogs.json", "w") as f:
    json.dump(analogs, f, indent=2)

print("\nSaved to: optimized_analogs.json")
print("="*80)
