# -*- coding: utf-8 -*-
"""
Create 3D visualization of CURE_4G_003 from the PDB file
"""

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

# Parse the PDB file
def parse_pdb(filename):
    atoms = []
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('HETATM') or line.startswith('ATOM'):
                atom_type = line[12:16].strip()
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                atoms.append((atom_type, x, y, z))
    return atoms

# Save the coordinates to a file
coordinates = """
HETATM    1  C1  UNL     1      -5.133   0.615  -1.708  1.00  0.00           C  
HETATM    2  C2  UNL     1      -6.450   0.153  -1.631  1.00  0.00           C  
HETATM    3  C3  UNL     1      -6.873  -0.517  -0.489  1.00  0.00           C  
HETATM    4  F1  UNL     1      -8.135  -0.958  -0.418  1.00  0.00           F  
HETATM    5  C4  UNL     1      -5.997  -0.730   0.568  1.00  0.00           C  
HETATM    6  F2  UNL     1      -6.415  -1.378   1.666  1.00  0.00           F  
HETATM    7  C5  UNL     1      -4.686  -0.273   0.493  1.00  0.00           C  
HETATM    8  F3  UNL     1      -3.867  -0.501   1.533  1.00  0.00           F  
HETATM    9  C6  UNL     1      -4.236   0.404  -0.643  1.00  0.00           C  
HETATM   10  C7  UNL     1      -2.845   0.918  -0.786  1.00  0.00           C  
HETATM   11  O1  UNL     1      -2.518   1.500  -1.817  1.00  0.00           O  
HETATM   12  N1  UNL     1      -1.973   0.706   0.255  1.00  0.00           N  
HETATM   13  C8  UNL     1      -0.552   0.990   0.118  1.00  0.00           C  
HETATM   14  C9  UNL     1       0.138   1.011   1.487  1.00  0.00           C  
HETATM   15  O2  UNL     1      -0.039  -0.270   2.120  1.00  0.00           O  
HETATM   16  C10 UNL     1       1.635   1.323   1.369  1.00  0.00           C  
HETATM   17  N2  UNL     1       2.365   0.258   0.704  1.00  0.00           N  
HETATM   18  C11 UNL     1       3.684   0.427   0.344  1.00  0.00           C  
HETATM   19  O3  UNL     1       4.277   1.493   0.455  1.00  0.00           O  
HETATM   20  C12 UNL     1       4.308  -0.830  -0.227  1.00  0.00           C  
HETATM   21  C13 UNL     1       5.810  -0.669  -0.451  1.00  0.00           C  
HETATM   22  C14 UNL     1       6.417  -1.924  -1.047  1.00  0.00           C  
HETATM   23  F4  UNL     1       6.192  -2.968  -0.205  1.00  0.00           F  
"""

with open("CURE_4G_003_coords.pdb", "w") as f:
    f.write(coordinates)

print("="*80)
print("CURE_4G_003 - 3D STRUCTURE ANALYSIS")
print("="*80)

# Parse and analyze
atoms = parse_pdb("CURE_4G_003_coords.pdb")

# Count atoms by type
atom_counts = {}
for atom_type, x, y, z in atoms:
    atom_counts[atom_type] = atom_counts.get(atom_type, 0) + 1

print("\nAtom Composition:")
for atom, count in sorted(atom_counts.items()):
    print(f"  {atom}: {count}")

# Calculate molecular properties
print("\nMolecular Properties:")
print(f"  Total atoms: {len(atoms)}")
print(f"  Carbon atoms: {atom_counts.get('C', 0)}")
print(f"  Nitrogen atoms: {atom_counts.get('N', 0)}")
print(f"  Oxygen atoms: {atom_counts.get('O', 0)}")
print(f"  Fluorine atoms: {atom_counts.get('F', 0)}")

# Create 3D visualization
fig = plt.figure(figsize=(12, 10))
ax = fig.add_subplot(111, projection='3d')

# Color mapping
colors = {'C': 'gray', 'N': 'blue', 'O': 'red', 'F': 'green', 'H': 'lightgray'}

x_vals, y_vals, z_vals = [], [], []
color_list = []

for atom_type, x, y, z in atoms:
    x_vals.append(x)
    y_vals.append(y)
    z_vals.append(z)
    color_list.append(colors.get(atom_type, 'black'))

# Plot atoms
scatter = ax.scatter(x_vals, y_vals, z_vals, c=color_list, s=100, alpha=0.8, edgecolors='black')

# Add labels for key atoms
key_atoms = [
    (0, "C1 (Phenyl)", 'black'),
    (3, "F1", 'green'),
    (5, "F2", 'green'),
    (7, "F3", 'green'),
    (10, "Amide", 'red'),
    (14, "Hydroxy", 'red'),
    (22, "F4", 'green'),
]

for idx, label, color in key_atoms:
    if idx < len(atoms):
        ax.text(x_vals[idx], y_vals[idx], z_vals[idx], label, fontsize=8, color=color)

ax.set_xlabel('X (Angstroms)')
ax.set_ylabel('Y (Angstroms)')
ax.set_zlabel('Z (Angstroms)')
ax.set_title('CURE_4G_003 - 3D Structure\nHIV Lead Compound (Affinity: -5.365 kcal/mol)')

plt.tight_layout()
plt.savefig('cure_4g_003_3d_view.png', dpi=150, bbox_inches='tight')
plt.show()

print("\n" + "="*80)
print("3D Visualization saved to: cure_4g_003_3d_view.png")
print("="*80)
