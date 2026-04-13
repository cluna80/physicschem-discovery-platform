# -*- coding: utf-8 -*-
import os
from egfr_docking_agent import EGFRDockingAgent

# Initialize agent
agent = EGFRDockingAgent()

# List of compounds (including fixed ones)
compounds = [
    "final_ligand.pdbqt",
    "gefitinib_like_fixed.pdbqt",
    "erlotinib_like_fixed.pdbqt",
    "inhibitor_fixed.pdbqt"
]

# Check which exist
existing = [c for c in compounds if os.path.exists(c)]

print("="*70)
print("EGFR COMPOUND RE-SCREENING")
print("="*70)
print(f"Screening {len(existing)} compounds\n")

# Run screening
results = agent.screen_compounds(existing)

print("\n" + "="*70)
print("FINAL SCREENING RESULTS (Best to Worst):")
print("="*70)

if results:
    for i, r in enumerate(results, 1):
        star = "*" if i == 1 else " "
        print(f"{star} {i}. {r['ligand']:<35} {r['affinity']:>8.2f} kcal/mol  ({r['strength']})")
    
    print("\n" + "="*70)
    print(f"BEST CANDIDATE: {results[0]['ligand']}")
    print(f"Binding affinity: {results[0]['affinity']:.2f} kcal/mol")
    
    if results[0]['affinity'] < -7:
        print("Classification: STRONG binder - excellent drug candidate!")
    elif results[0]['affinity'] < -5:
        print("Classification: MODERATE binder - promising lead")
    else:
        print("Classification: Weak binder - needs optimization")
    print("="*70)
else:
    print("No successful docking results")
