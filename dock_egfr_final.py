# -*- coding: utf-8 -*-
from docking_agent import DockingAgent
import subprocess
import os

# CORRECT binding pocket from crystal structure analysis
binding_site = {
    'center': (22.0, 0.3, 52.8),  # From bound erlotinib coordinates
    'size': 21  # Box size to cover the pocket
}

print("="*70)
print("EGFR Docking with Crystal Structure Binding Pocket")
print("="*70)
print(f"Binding site center: {binding_site['center']}")
print(f"Box size: {binding_site['size']} Angstroms")
print()

# First, verify ligands have proper coordinates
print("Verifying ligand 3D coordinates:")
ligands = ["simple_quinazoline.pdbqt", "gefitinib_like.pdbqt", 
           "erlotinib_like.pdbqt", "inhibitor.pdbqt"]

valid_ligands = []
for ligand in ligands:
    if os.path.exists(ligand) and os.path.getsize(ligand) > 0:
        with open(ligand, 'r') as f:
            lines = f.readlines()
            has_coords = False
            for line in lines:
                if line.startswith("ATOM"):
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    if abs(x) > 0.1 or abs(y) > 0.1 or abs(z) > 0.1:
                        has_coords = True
                        print(f"  {ligand}: GOOD (coords: {x:.1f}, {y:.1f}, {z:.1f})")
                        valid_ligands.append(ligand)
                        break
            if not has_coords:
                print(f"  {ligand}: BAD (zero coordinates - skipping)")
    else:
        print(f"  {ligand}: NOT FOUND")

if not valid_ligands:
    print("\nNo valid ligands found! Please run fix_ligands_correct.py first.")
    exit()

# Initialize agent
agent = DockingAgent()

# Dock each valid ligand
print("\n" + "="*70)
print("Running Docking Calculations")
print("="*70)

results = []
for ligand in valid_ligands:
    print(f"\nDocking {ligand}...")
    result = agent.evaluate_compound(
        ligand_file=ligand,
        receptor_file="egfr.pdbqt",
        binding_site=binding_site,
        exhaustiveness=16,
        num_modes=9
    )
    
    if result['success']:
        affinity = result['best_affinity']
        print(f"  -> Best affinity: {affinity:.2f} kcal/mol")
        print(f"  -> Binding strength: {result['binding_strength']}")
        results.append((ligand, affinity, result['binding_strength']))
        
        # Show top 3 binding modes
        print(f"  -> Top 3 binding modes:")
        for mode in result['all_modes'][:3]:
            print(f"       Mode {mode['mode']}: {mode['affinity']:.2f} kcal/mol")
    else:
        print(f"  -> Failed: {result.get('error', 'Unknown error')}")

# Summary
if results:
    results.sort(key=lambda x: x[1])
    print("\n" + "="*70)
    print("DOCKING SUMMARY (Best to Worst)")
    print("="*70)
    print(f"{'Ligand':<30} {'Affinity (kcal/mol)':<20} {'Strength':<25}")
    print("-"*70)
    for ligand, affinity, strength in results:
        print(f"{ligand:<30} {affinity:>8.2f} kcal/mol      {strength:<25}")
    
    print("\n" + "="*70)
    print("Best candidate: {}".format(results[0][0]))
    print("Binding affinity: {:.2f} kcal/mol".format(results[0][1]))
    print("="*70)
else:
    print("\nNo successful docking results.")
