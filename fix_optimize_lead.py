# -*- coding: utf-8 -*-
"""
Correct optimized analogs of CURE_4G_003
Target: -7.0 kcal/mol
"""

import json

# Current lead
LEAD_SMILES = "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCF"
CURRENT_AFFINITY = -5.365

# Suggested modifications (with correct addition)
optimizations = [
    {
        'name': 'CURE_5G_001',
        'modification': 'Add THF ring',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFCCOCCO',
        'expected_boost': 0.6
    },
    {
        'name': 'CURE_5G_002',
        'modification': 'Add sulfonamide-like group',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCFS(=O)(=O)N',
        'expected_boost': 0.5
    },
    {
        'name': 'CURE_5G_003',
        'modification': 'Extended chain + more fluorines',
        'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCCF',
        'expected_boost': 0.4
    }
]

print("="*80)
print("CORRECTED OPTIMIZED ANALOGS")
print("="*80)
print(f"Current lead: {CURRENT_AFFINITY:.3f} kcal/mol")
print(f"Target: -7.0 kcal/mol")
print(f"Gap to close: {abs(CURRENT_AFFINITY - (-7.0)):.2f} kcal/mol")
print("-"*80)

for opt in optimizations:
    predicted = CURRENT_AFFINITY + opt['expected_boost']
    status = "✓ TARGET" if predicted < -7 else "→ PROGRESS"
    print(f"\n{opt['name']}: {opt['modification']}")
    print(f"  Predicted: {predicted:.3f} kcal/mol")
    print(f"  Improvement: +{opt['expected_boost']:.1f} kcal/mol")
    print(f"  Status: {status}")

# Best candidate
best = max(optimizations, key=lambda x: x['expected_boost'])
best_pred = CURRENT_AFFINITY + best['expected_boost']

print("\n" + "="*80)
print("BEST NEXT CANDIDATE")
print("="*80)
print(f"Name: {best['name']}")
print(f"Modification: {best['modification']}")
print(f"Predicted Affinity: {best_pred:.3f} kcal/mol")
print(f"Gap to -7.0: {best_pred - (-7.0):.2f} kcal/mol")

if best_pred < -6.5:
    print("\n✓ This candidate would be very close to drug candidate range!")
elif best_pred < -6:
    print("\n✓ Good improvement, one more iteration needed")

# Save
with open("corrected_optimizations.json", "w") as f:
    json.dump(optimizations, f, indent=2)

print("\nSaved to: corrected_optimizations.json")
print("="*80)
