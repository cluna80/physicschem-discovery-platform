# -*- coding: utf-8 -*-
# Create a simple test ligand positioned at the EGFR binding pocket

print("Creating simple test ligand at binding pocket...")

# Coordinates from the binding pocket center
center_x, center_y, center_z = 22.0, 0.3, 52.8

# Create a benzene ring (6 carbons) positioned at the binding site
ligand_content = f"""REMARK  Simple test ligand at EGFR binding pocket
ROOT
ATOM      1  C   LIG     1     {center_x:8.3f} {center_y:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      2  C   LIG     1     {center_x+1.4:8.3f} {center_y:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      3  C   LIG     1     {center_x+0.7:8.3f} {center_y+1.2:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      4  C   LIG     1     {center_x-0.7:8.3f} {center_y+1.2:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      5  C   LIG     1     {center_x-1.4:8.3f} {center_y:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      6  C   LIG     1     {center_x-0.7:8.3f} {center_y-1.2:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ATOM      7  C   LIG     1     {center_x+0.7:8.3f} {center_y-1.2:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 C
ENDROOT
BRANCH   1   8
ATOM      8  H   LIG     1     {center_x-0.9:8.3f} {center_y:8.3f} {center_z-0.9:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   1   8
BRANCH   2   9
ATOM      9  H   LIG     1     {center_x+2.3:8.3f} {center_y:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   2   9
BRANCH   3  10
ATOM     10  H   LIG     1     {center_x+1.2:8.3f} {center_y+2.0:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   3  10
BRANCH   4  11
ATOM     11  H   LIG     1     {center_x-1.2:8.3f} {center_y+2.0:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   4  11
BRANCH   5  12
ATOM     12  H   LIG     1     {center_x-2.3:8.3f} {center_y:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   5  12
BRANCH   6  13
ATOM     13  H   LIG     1     {center_x-1.2:8.3f} {center_y-2.0:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   6  13
BRANCH   7  14
ATOM     14  H   LIG     1     {center_x+1.2:8.3f} {center_y-2.0:8.3f} {center_z:8.3f}  1.00  0.00    +0.000 H
ENDBRANCH   7  14
TORSDOF 7
"""

with open("simple_test.pdbqt", "w") as f:
    f.write(ligand_content)

print("Created simple_test.pdbqt")
print(f"  Ligand centered at: ({center_x}, {center_y}, {center_z})")
print("  Contains benzene ring with hydrogens")

# Verify the file
with open("simple_test.pdbqt", 'r') as f:
    lines = f.readlines()
    atoms = [l for l in lines if l.startswith("ATOM")]
    print(f"  {len(atoms)} atoms with coordinates")
    if atoms:
        x = float(atoms[0][30:38].strip())
        y = float(atoms[0][38:46].strip())
        z = float(atoms[0][46:54].strip())
        print(f"  First atom at: ({x:.1f}, {y:.1f}, {z:.1f})")
