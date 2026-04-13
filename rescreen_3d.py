# -*- coding: utf-8 -*-
import os
from egfr_docking_agent import EGFRDockingAgent

# Initialize agent
agent = EGFRDockingAgent()

# List of compounds with proper 3D coordinates
compounds = [
    "final_ligand.pdbqt",
    "gefitinib_like_3d.pdbqt",
    "erlotinib_like_3d.pdbqt",
    "inhibitor_3d.pdbqt"
]

# Check which exist
existing = [c for c in compounds if os.path.exists(c) and os.path.getsize(c) > 100]

print("="*70)
print("EGFR COMPOUND SCREENING (3D Ligands)")
print("="*70)
print(f"Screening {len(existing)} compounds\n")

# Run screening
results = agent.screen_compounds(existing)

print("\n" + "="*70)
print("SCREENING RESULTS (Best to Worst):")
print("="*70)

if results:
    for i, r in enumerate(results, 1):
        star = "BEST" if i == 1 else "    "
        print(f"{star} {i}. {r['ligand']:<35} {r['affinity']:>8.2f} kcal/mol  ({r['strength']})")
    
    print("\n" + "="*70)
    print(f"BEST CANDIDATE: {results[0]['ligand']}")
    print(f"Binding affinity: {results[0]['affinity']:.2f} kcal/mol")
    
    if results[0]['affinity'] < -7:
        print("Classification: STRONG binder - excellent drug candidate!")
    elif results[0]['affinity'] < -5:
        print("Classification: MODERATE binder - promising lead")
    elif results[0]['affinity'] < -3:
        print("Classification: WEAK binder - needs optimization")
    else:
        print("Classification: Very weak binder - not suitable")
    print("="*70)
else:
    print("No successful docking results")
    print("\nAvailable PDBQT files:")
    os.system("ls -la *.pdbqt | head -10")
