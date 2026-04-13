# -*- coding: utf-8 -*-
"""
3D Visualization of CURE_4G_003 - Lead HIV Drug Candidate
"""

import os
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
from rdkit.Chem.Draw import IPythonConsole
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

# CURE_4G_003 details
LEAD = {
    'name': 'CURE_4G_003',
    'smiles': 'c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCF',
    'affinity': -5.365
}

print("="*80)
print("VISUALIZING HIV LEAD COMPOUND: CURE_4G_003")
print("="*80)
print(f"SMILES: {LEAD['smiles']}")
print(f"Binding Affinity: {LEAD['affinity']} kcal/mol")
print("-"*80)

# Create molecule object
mol = Chem.MolFromSmiles(LEAD['smiles'])
if not mol:
    print("Error: Could not create molecule")
    exit()

# Add hydrogens
mol = Chem.AddHs(mol)

# Generate 3D coordinates
print("\n[1/4] Generating 3D structure...")
AllChem.EmbedMolecule(mol, randomSeed=42)
AllChem.MMFFOptimizeMolecule(mol, maxIters=200)

# Save as PDB for external viewers
print("[2/4] Saving PDB file...")
pdb_file = "CURE_4G_003_3d.pdb"
Chem.MolToPDBFile(mol, pdb_file)
print(f"  Saved: {pdb_file}")

# Save as SDF for other viewers
print("[3/4] Saving SDF file...")
sdf_file = "CURE_4G_003_3d.sdf"
writer = Chem.SDWriter(sdf_file)
writer.write(mol)
writer.close()
print(f"  Saved: {sdf_file}")

# Generate 2D image
print("[4/4] Generating 2D representation...")
img = Draw.MolToImage(mol, size=(800, 600), kekulize=True)
img.save("CURE_4G_003_2d.png")
print(f"  Saved: CURE_4G_003_2d.png")

print("\n" + "="*80)
print("VISUALIZATION FILES CREATED")
print("="*80)
print(f"  • CURE_4G_003_2d.png - 2D structure (view now)")
print(f"  • CURE_4G_003_3d.pdb - 3D structure (for PyMOL, Chimera)")
print(f"  • CURE_4G_003_3d.sdf - 3D structure (for other viewers)")
print("\nTo view in PyMOL: pymol CURE_4G_003_3d.pdb")
print("To view in Chimera: chimera CURE_4G_003_3d.pdb")
print("="*80)

# Display 2D image (if in Jupyter/notebook environment)
try:
    from IPython.display import Image as IPyImage, display
    display(IPyImage("CURE_4G_003_2d.png"))
except:
    print("\n2D image saved. You can open it with any image viewer.")
    print(f"Location: {os.path.abspath('CURE_4G_003_2d.png')}")
