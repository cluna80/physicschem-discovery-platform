# -*- coding: utf-8 -*-
"""
Complete Drug Discovery Pipeline
1. Download target protein
2. Extract binding pocket
3. Dock compounds
4. Rank results
"""
import os
import subprocess
from egfr_docking_agent import EGFRDockingAgent

def run_full_pipeline(target_pdb, ligand_files):
    """Run complete docking pipeline"""
    
    # Step 1: Download protein
    print(f"Downloading {target_pdb}...")
    subprocess.run(["curl", "-k", "-o", f"{target_pdb}.pdb", 
                   f"https://files.rcsb.org/download/{target_pdb}.pdb"])
    
    # Step 2: Convert to PDBQT
    print("Converting to PDBQT...")
    subprocess.run(["obabel", f"{target_pdb}.pdb", "-O", f"{target_pdb}.pdbqt", "-xr", "-p"])
    
    # Step 3: Create docking agent
    agent = EGFRDockingAgent(f"{target_pdb}.pdbqt")
    
    # Step 4: Screen compounds
    print("\nScreening compounds...")
    results = agent.screen_compounds(ligand_files)
    
    # Step 5: Display results
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    for r in results:
        print(f"{r['ligand']:<30} {r['affinity']:>8.2f} kcal/mol")
    
    return results

# Run for EGFR with your compounds
if __name__ == "__main__":
    ligands = ["final_ligand.pdbqt", "gefitinib_like.pdbqt", "erlotinib_like.pdbqt"]
    results = run_full_pipeline("1M17", ligands)
