# -*- coding: utf-8 -*-
import os
from egfr_docking_agent import EGFRDockingAgent

# Initialize EGFR docking agent
agent = EGFRDockingAgent()

# List of compounds to screen
compounds = [
    "gefitinib_like.pdbqt",
    "erlotinib_like.pdbqt", 
    "inhibitor.pdbqt",
    "final_ligand.pdbqt"
]

# Check which compounds exist
existing_compounds = [c for c in compounds if os.path.exists(c)]
if not existing_compounds:
    print("No compound files found!")
    print("Available PDBQT files:")
    os.system("ls *.pdbqt | head -10")
else:
    print("="*70)
    print("EGFR COMPOUND SCREENING")
    print("="*70)
    print(f"Found {len(existing_compounds)} compounds to screen\n")
    
    # Run screening
    results = agent.screen_compounds(existing_compounds)
    
    print("\n" + "="*70)
    print("SCREENING RESULTS (Best to Worst):")
    print("="*70)
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['ligand']:<30} {result['affinity']:>8.2f} kcal/mol  ({result['strength']})")
    
    print("\n" + "="*70)
    print(f"Best candidate: {results[0]['ligand']}")
    print(f"Binding affinity: {results[0]['affinity']:.2f} kcal/mol")
    print("="*70)
