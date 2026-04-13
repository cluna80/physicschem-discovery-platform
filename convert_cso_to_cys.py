#!/usr/bin/env python3
"""
Convert CSO (cysteine sulfonic acid) to CYS (cysteine) for force field compatibility.
Also handles other potential non-standard residues.
"""

import os
import re

print("="*60)
print("Fixing Non-Standard Residues in HIV Protease")
print("="*60)

# Read the original PDB
with open("hiv_protease_fixed.pdb", "r") as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines from hiv_protease_fixed.pdb")

# Count occurrences
cso_count = sum(1 for line in lines if " CSO " in line)
print(f"Found {cso_count} CSO residues")

# Replace CSO with CYS
fixed_lines = []
for line in lines:
    if line.startswith(("ATOM", "HETATM")):
        # Check residue name at columns 17-20
        res_name = line[17:20]
        if res_name == "CSO":
            # Replace with CYS
            new_line = line[:17] + "CYS" + line[20:]
            fixed_lines.append(new_line)
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# Write fixed file
with open("hiv_protease_fixed_residues.pdb", "w") as f:
    f.writelines(fixed_lines)

print(f"✅ Created: hiv_protease_fixed_residues.pdb with CSO -> CYS")

# Also create a version with only standard residues for GROMACS
print("\nCreating simplified version for testing...")
with open("hiv_protease_simple.pdb", "w") as f:
    for line in fixed_lines:
        if line.startswith("ATOM"):
            f.write(line)
    f.write("END\n")

print("✅ Created: hiv_protease_simple.pdb (ATOM records only)")
