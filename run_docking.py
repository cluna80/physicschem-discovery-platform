# -*- coding: utf-8 -*-
import subprocess
import os
from vina_wrapper import VinaDocker

# Initialize
vina = VinaDocker()
print("Starting molecular docking workflow")
print("=" * 50)

# Step 1: Download a sample protein and ligand
print("\nDownloading sample files...")
subprocess.run([
    "curl", "-o", "1iep.pdb",
    "https://files.rcsb.org/download/1IEP.pdb"
], capture_output=True)

# Step 2: Convert to PDBQT format
print("\nConverting files to PDBQT format...")

# Convert receptor (protein)
subprocess.run([
    "obabel", "1iep.pdb", "-O", "receptor.pdbqt",
    "-xr", "-p"
], capture_output=True)

# Create a simple test ligand
print("\nCreating test ligand...")
with open("ligand.pdb", "w") as f:
    f.write("""HETATM    1  C   LIG     1       4.500  15.500  7.000  1.00  0.00           C
HETATM    2  C   LIG     1       5.500  16.200  7.500  1.00  0.00           C
HETATM    3  C   LIG     1       6.500  15.500  8.000  1.00  0.00           C
HETATM    4  C   LIG     1       6.500  14.200  8.000  1.00  0.00           C
HETATM    5  C   LIG     1       5.500  13.500  7.500  1.00  0.00           C
HETATM    6  C   LIG     1       4.500  14.200  7.000  1.00  0.00           C
HETATM    7  H   LIG     1       3.500  15.000  6.500  1.00  0.00           H
HETATM    8  H   LIG     1       5.500  17.300  7.500  1.00  0.00           H
HETATM    9  H   LIG     1       7.500  16.000  8.400  1.00  0.00           H
HETATM   10  H   LIG     1       7.500  13.700  8.400  1.00  0.00           H
HETATM   11  H   LIG     1       5.500  12.400  7.500  1.00  0.00           H
HETATM   12  H   LIG     1       3.500  13.700  6.500  1.00  0.00           H
END""")

# Convert ligand
subprocess.run([
    "obabel", "ligand.pdb", "-O", "ligand.pdbqt", "-xh"
], capture_output=True)

# Check if files were created
if os.path.exists("receptor.pdbqt") and os.path.exists("ligand.pdbqt"):
    print("Files converted successfully")
else:
    print("File conversion failed")

# Step 3: Define docking parameters
center = (10.0, 15.0, 8.0)
size = (20.0, 20.0, 20.0)

print(f"\nDocking parameters:")
print(f"   Center: {center}")
print(f"   Box size: {size}")

# Step 4: Run docking
print("\nRunning molecular docking...")
print("   This may take a moment...\n")

result = vina.dock(
    receptor="receptor.pdbqt",
    ligand="ligand.pdbqt",
    center=center,
    size=size,
    output="docking_result.pdbqt",
    num_modes=5,
    exhaustiveness=8
)

if result and result['return_code'] == 0:
    print("\nDocking completed successfully!")
    print("\nBinding Affinities:")
    print("-" * 40)
    for affinity in result['affinities'][:5]:
        print(f"   {affinity}")
    
    for line in result['output'].split('\n'):
        if "mode" in line and "affinity" in line:
            print(f"\nBest binding mode: {line}")
            break
    
    print("\nResults saved to: docking_result.pdbqt")
else:
    print("\nDocking failed")
    if result:
        print(result['output'])

print("\nWorkflow complete!")
