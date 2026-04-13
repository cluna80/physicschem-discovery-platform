# -*- coding: utf-8 -*-
import subprocess
import os
from docking_agent import DockingAgent

# First, let's verify the PDBQT files
print("Verifying PDBQT files...")
for ligand in ["gefitinib_like.pdbqt", "erlotinib_like.pdbqt", "simple_quinazoline.pdbqt", "inhibitor.pdbqt"]:
    if os.path.exists(ligand):
        result = subprocess.run(["grep", "-c", "^ATOM", ligand], capture_output=True, text=True)
        atoms = int(result.stdout.strip() or 0)
        print(f"  {ligand}: {atoms} atoms")
    else:
        print(f"  {ligand}: NOT FOUND")

# Re-convert if needed
if not os.path.exists("gefitinib_like.pdbqt") or os.path.getsize("gefitinib_like.pdbqt") == 0:
    print("\nRe-converting ligands...")
    subprocess.run(["obabel", "gefitinib_like.smi", "-O", "gefitinib_like.pdbqt", "-xh"], capture_output=True)
    subprocess.run(["obabel", "erlotinib_like.smi", "-O", "erlotinib_like.pdbqt", "-xh"], capture_output=True)
    subprocess.run(["obabel", "simple_quinazoline.smi", "-O", "simple_quinazoline.pdbqt", "-xh"], capture_output=True)

# Initialize agent
agent = DockingAgent()

# Different binding site coordinates to try
binding_sites = [
    {'name': 'Center of mass', 'center': (40.0, 40.0, 40.0), 'size': 25},
    {'name': 'Extended pocket', 'center': (35.0, 45.0, 35.0), 'size': 30},
    {'name': 'ATP site', 'center': (45.0, 35.0, 45.0), 'size': 25},
]

# Test with the simple quinazoline first (likely to bind EGFR)
print("\n" + "="*70)
print("Docking Simple Quinazoline (EGFR inhibitor scaffold)")
print("="*70)

for site in binding_sites:
    print(f"\nTesting binding site: {site['name']}")
    print(f"  Center: {site['center']}, Size: {site['size']}")
    
    result = agent.evaluate_compound(
        ligand_file="simple_quinazoline.pdbqt",
        receptor_file="egfr.pdbqt",
        binding_site={'center': site['center'], 'size': site['size']},
        exhaustiveness=16
    )
    
    if result['success']:
        print(f"  -> Best affinity: {result['best_affinity']:.2f} kcal/mol")
        print(f"  -> Binding strength: {result['binding_strength']}")
    else:
        print(f"  -> Failed: {result.get('error', 'Unknown')}")

# Now dock all inhibitors with the best site
print("\n" + "="*70)
print("Batch Docking All EGFR Inhibitors")
print("="*70)

best_site = {'center': (40.0, 40.0, 40.0), 'size': 25}
ligands = ["simple_quinazoline.pdbqt", "gefitinib_like.pdbqt", "erlotinib_like.pdbqt", "inhibitor.pdbqt"]
results = []

for ligand in ligands:
    if os.path.exists(ligand) and os.path.getsize(ligand) > 0:
        print(f"\nDocking {ligand}...")
        result = agent.evaluate_compound(
            ligand_file=ligand,
            receptor_file="egfr.pdbqt",
            binding_site=best_site,
            exhaustiveness=16
        )
        
        if result['success']:
            affinity = result['best_affinity']
            print(f"  -> Affinity: {affinity:.2f} kcal/mol")
            results.append((ligand, affinity, result['binding_strength']))
        else:
            print(f"  -> Failed: No binding modes found")

# Show results
if results:
    results.sort(key=lambda x: x[1])  # Sort by best affinity (most negative first)
    print("\n" + "="*70)
    print("Docking Results (best to worst):")
    print("="*70)
    for ligand, affinity, strength in results:
        print(f"{ligand:30} {affinity:8.2f} kcal/mol  ({strength})")
else:
    print("\nNo successful docking results. Check if ligands have atoms.")
