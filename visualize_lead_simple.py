# -*- coding: utf-8 -*-
"""
Simple 3D Visualization of CURE_4G_003 - Lead HIV Drug Candidate
No IPython required
"""

import os
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
import matplotlib.pyplot as plt

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

print("\n[1/4] Molecule created successfully!")

# Generate 3D coordinates
print("[2/4] Generating 3D structure...")
mol = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol, randomSeed=42)
AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
print("  3D structure generated!")

# Save as PDB for external viewers
print("[3/4] Saving 3D files...")
pdb_file = "CURE_4G_003_3d.pdb"
Chem.MolToPDBFile(mol, pdb_file)
print(f"  Saved: {pdb_file}")

# Save as SDF for other viewers
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

# Also create a labeled version
from rdkit.Chem import Draw
img_labeled = Draw.MolToImage(mol, size=(800, 600), kekulize=True, wedgeBonds=True)
img_labeled.save("CURE_4G_003_2d_labeled.png")
print(f"  Saved: CURE_4G_003_2d_labeled.png")

print("\n" + "="*80)
print("VISUALIZATION FILES CREATED")
print("="*80)
print("  • CURE_4G_003_2d.png - 2D structure")
print("  • CURE_4G_003_2d_labeled.png - 2D with stereochemistry")
print("  • CURE_4G_003_3d.pdb - 3D structure (PyMOL, Chimera)")
print("  • CURE_4G_003_3d.sdf - 3D structure (other viewers)")
print("")
print(f"Location: {os.path.abspath('.')}")
print("="*80)

# Display image if possible
try:
    import matplotlib.pyplot as plt
    img = plt.imread("CURE_4G_003_2d.png")
    plt.figure(figsize=(10, 8))
    plt.imshow(img)
    plt.axis('off')
    plt.title(f"CURE_4G_003 - HIV Lead Compound\nAffinity: {LEAD['affinity']} kcal/mol")
    plt.tight_layout()
    plt.savefig("CURE_4G_003_preview.png", dpi=150, bbox_inches='tight')
    plt.show()
    print("\nPreview saved: CURE_4G_003_preview.png")
except:
    print("\nTo view the image, open CURE_4G_003_2d.png with any image viewer.")
