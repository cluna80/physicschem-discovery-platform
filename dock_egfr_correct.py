# -*- coding: utf-8 -*-
from docking_agent import DockingAgent

# EGFR binding site from the crystal structure
# Update these coordinates with what find_ligand_coords.py outputs
binding_site = {
    'center': (35.0, 15.0, 55.0),  # Approximate - REPLACE with actual values
    'size': 25
}

print("="*60)
print("EGFR Docking with Correct Binding Pocket")
print("="*60)
print(f"Using binding site: center={binding_site['center']}, size={binding_site['size']}")
print()

# Initialize agent
agent = DockingAgent()

# Test all ligands
ligands = ["simple_quinazoline.pdbqt", "gefitinib_like.pdbqt", 
           "erlotinib_like.pdbqt", "inhibitor.pdbqt"]

results = []

for ligand in ligands:
    print(f"Docking {ligand}...")
    result = agent.evaluate_compound(
        ligand_file=ligand,
        receptor_file="egfr.pdbqt",
        binding_site=binding_site,
        exhaustiveness=16
    )
    
    if result['success']:
        affinity = result['best_affinity']
        print(f"  -> Affinity: {affinity:.2f} kcal/mol")
        results.append((ligand, affinity, result['binding_strength']))
    else:
        print(f"  -> Failed: {result.get('error', 'No binding modes')}")

# Show results
if results:
    results.sort(key=lambda x: x[1])
    print("\n" + "="*60)
    print("Docking Results (best to worst):")
    print("="*60)
    for ligand, affinity, strength in results:
        print(f"{ligand:30} {affinity:8.2f} kcal/mol  ({strength})")
