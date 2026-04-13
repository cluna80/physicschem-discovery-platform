# -*- coding: utf-8 -*-
import subprocess
import os
from docking_agent import DockingAgent

# Convert SMILES to PDBQT first
print("Converting SMILES to PDBQT...")
smiles_files = ["gefitinib_like.smi", "erlotinib_like.smi", "simple_quinazoline.smi"]
ligands = []

for smi in smiles_files:
    if os.path.exists(smi):
        pdbqt = smi.replace('.smi', '.pdbqt')
        subprocess.run(["obabel", smi, "-O", pdbqt, "-xh"], capture_output=True)
        ligands.append(pdbqt)
        print(f"  Created {pdbqt}")

# Initialize agent
agent = DockingAgent()

# Binding site
binding_site = {'center': (40.0, 30.0, 35.0), 'size': 25}

print("\n" + "="*60)
print("Batch Docking EGFR Inhibitors")
print("="*60)

# Dock each ligand
results = []
for ligand in ligands:
    print(f"\nDocking {ligand}...")
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
        print(f"  -> Failed: {result.get('error', 'Unknown')}")

# Sort by best affinity (most negative first)
results.sort(key=lambda x: x[1])

print("\n" + "="*60)
print("Results (best to worst):")
print("="*60)
for ligand, affinity, strength in results:
    print(f"{ligand:25} {affinity:8.2f} kcal/mol  ({strength})")
