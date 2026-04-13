# -*- coding: utf-8 -*-
import subprocess
import os

print("Creating proper receptor file...")
print("=" * 50)

# Download a small, well-structured protein (1HVR - HIV protease)
print("Downloading HIV protease (1HVR)...")
subprocess.run([
    "curl", "-s", "-o", "1hvr.pdb",
    "https://files.rcsb.org/download/1HVR.pdb"
])

# Convert to PDBQT with proper AutoDock4 atom types
print("Converting to PDBQT format...")
result = subprocess.run([
    "obabel", "1hvr.pdb", "-O", "receptor_correct.pdbqt",
    "-xr",  # Add AutoDock4 atom types
    "-p"    # Keep hydrogens (if present)
], capture_output=True, text=True)

if result.returncode == 0:
    print("✅ Receptor converted successfully!")
    
    # Check the file
    with open("receptor_correct.pdbqt", "r") as f:
        lines = f.readlines()
        atom_lines = [l for l in lines if l.startswith("ATOM")]
        print(f"   Atoms in receptor: {len(atom_lines)}")
        print(f"\nFirst few atoms:")
        for line in atom_lines[:5]:
            print(f"   {line.strip()}")
else:
    print("❌ Conversion failed:", result.stderr)

# Also create a better test ligand (a small drug-like molecule)
print("\n" + "=" * 50)
print("Creating a proper test ligand...")

with open("ligand_correct.pdb", "w") as f:
    f.write("""HETATM    1  C   LIG     1       0.000   0.000   0.000  1.00  0.00           C
HETATM    2  C   LIG     1       1.500   0.000   0.000  1.00  0.00           C
HETATM    3  C   LIG     1       2.250   1.299   0.000  1.00  0.00           C
HETATM    4  C   LIG     1       1.500   2.598   0.000  1.00  0.00           C
HETATM    5  C   LIG     1       0.000   2.598   0.000  1.00  0.00           C
HETATM    6  C   LIG     1      -0.750   1.299   0.000  1.00  0.00           C
HETATM    7  N   LIG     1       2.250  -0.866   0.000  1.00  0.00           N
HETATM    8  O   LIG     1       3.750   1.299   0.000  1.00  0.00           O
HETATM    9  C   LIG     1       2.250   3.897   0.000  1.00  0.00           C
HETATM   10  H   LIG     1      -1.500   1.299   0.000  1.00  0.00           H
HETATM   11  H   LIG     1       3.000  -0.866   1.000  1.00  0.00           H
HETATM   12  H   LIG     1       3.000  -0.866  -1.000  1.00  0.00           H
END""")

# Convert ligand to PDBQT
subprocess.run([
    "obabel", "ligand_correct.pdb", "-O", "ligand_correct.pdbqt", "-xh"
], capture_output=True)

print("✅ Ligand created and converted")

print("\n" + "=" * 50)
print("Files ready:")
print("  - receptor_correct.pdbqt")
print("  - ligand_correct.pdbqt")
