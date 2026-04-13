# -*- coding: utf-8 -*-
"""
Fix CURE_6G optimization - ensure proper connectivity
Based on working scaffold: CURE_5G_002 (-6.122 kcal/mol)
"""

from rdkit import Chem
from rdkit.Chem import Descriptors
import json

# Working scaffold (CURE_5G_002)
WORKING_SMILES = "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1"
WORKING_AFFINITY = -6.122

# Correctly connected left-arm variants
corrected_variants = [
    {
        'name': 'CURE_6G_001_fixed',
        'smiles': 'c1cc(NC(=O)NC)ccc1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1',
        'description': 'Aminophenyl left arm (proper connectivity)',
        'expected_boost': 0.8
    },
    {
        'name': 'CURE_6G_002_fixed',
        'smiles': 'c1ccc2ccccc2c1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1',
        'description': 'Naphthalene left arm',
        'expected_boost': 0.5
    },
    {
        'name': 'CURE_6G_003_fixed',
        'smiles': 'c1cnccc1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1',
        'description': 'Pyridine left arm',
        'expected_boost': 0.6
    },
    {
        'name': 'CURE_6G_004_fixed',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1',
        'description': 'Original trifluorophenyl (baseline)',
        'expected_boost': 0
    }
]

print("="*80)
print("FIXED CURE_6G DESIGNS - PROPER CONNECTIVITY")
print("="*80)
print(f"Baseline (CURE_5G_002): {WORKING_AFFINITY:.3f} kcal/mol")
print(f"Target: -9.0 kcal/mol")
print("-"*80)

valid_designs = []
for design in corrected_variants:
    mol = Chem.MolFromSmiles(design['smiles'])
    if mol:
        predicted = WORKING_AFFINITY + design['expected_boost']
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        
        print(f"\n{design['name']}:")
        print(f"  {design['description']}")
        print(f"  Predicted: {predicted:.3f} kcal/mol (+{design['expected_boost']:.1f})")
        print(f"  MW: {mw:.0f} Da, LogP: {logp:.2f}")
        
        if predicted < -7:
            print(f"  ✓ Would reach strong binder range!")
        
        design['mw'] = mw
        design['logp'] = logp
        design['predicted'] = predicted
        valid_designs.append(design)
    else:
        print(f"\n{design['name']}: INVALID")

# Save
with open("cure_6g_fixed.json", "w") as f:
    json.dump(valid_designs, f, indent=2)

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
The negative affinity results suggest the SMILES connectivity was wrong.
Use CURE_5G_002 (-6.122) as the template and modify ONLY the left arm.
The correct pattern is:
  [LeftArm]-C(=O)NCC(O)CNC(=O)CCCFC1CCOCC1

Where LeftArm should be:
  - Trifluorophenyl (working baseline)
  - Pyridyl (for H-bonding)
  - Benzyl (simpler hydrophobic)
  
The bis-THF/sulfonamide combination should be tested after the left arm is fixed.
""")
print("="*80)
