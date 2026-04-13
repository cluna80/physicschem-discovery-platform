# -*- coding: utf-8 -*-
"""
Systematic optimization to reach -9 kcal/mol
Target: Darunavir-level potency
"""

print("="*80)
print("PATH TO -9 kcal/mol - DARUNAVIR-LEVEL POTENCY")
print("="*80)

# Current lead
current = -5.365
target = -9.0
gap = target - current

print(f"\nCurrent CURE_4G_003: {current:.3f} kcal/mol")
print(f"Target: {target:.1f} kcal/mol")
print(f"Gap to close: {abs(gap):.2f} kcal/mol")
print(f"Improvement needed: {abs(gap):.1f}x current improvement")

print("\n" + "="*80)
print("OPTIMIZATION STRATEGY")
print("="*80)

improvements = [
    ("Add bis-THF (Darunavir core)", 2.0, "Water-mediated H-bonds with flap region"),
    ("Optimize P1/P2 groups", 0.8, "Hydrophobic interactions in S1/S2 pockets"),
    ("Add sulfonamide", 0.6, "Strong H-bond with Asp25/Asp25'"),
    ("Extend alkyl chain", 0.4, "Better pocket filling"),
    ("Optimize fluorine pattern", 0.3, "Electron withdrawal effects"),
]

total = 0
print(f"\n{'Modification':<35} {'Gain':<10} {'Cumulative':<12} {'Description'}")
print("-"*80)

for name, gain, desc in improvements:
    total += gain
    cumulative = current + total
    status = "✓ TARGET" if cumulative < -7 else "→ PROGRESS"
    if cumulative < -8:
        status = "✓✓ EXCELLENT"
    if cumulative < -9:
        status = "✓✓✓ REACHED!"
    print(f"{name:<35} +{gain:<9.1f} {cumulative:<12.3f} {status:<12} {desc}")

print("\n" + "="*80)
print("KEY FEATURE: BIS-THF GROUP")
print("="*80)
print("""
Darunavir's bis-THF (bis-tetrahydrofuran) group provides:
- Water-mediated hydrogen bonds to the flap region
- Optimal positioning in the S2 subsite
- Enhanced binding entropy
- 2-3 kcal/mol improvement over non-THF analogs

Structure:
    O
   / \\
  /   \\
 C     C
  \\   /
   \\ /
    O
    |
    R (connects to hydroxyethylamine)
""")
