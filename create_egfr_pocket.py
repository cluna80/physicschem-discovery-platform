# -*- coding: utf-8 -*-
import subprocess
import os

print("Creating EGFR binding pocket fragment...")
print("="*60)

# Extract atoms near the binding pocket (from the bound erlotinib coordinates)
pocket_center = (22.0, 0.3, 52.8)
radius = 12.0  # Angstroms around the binding site

pocket_atoms = []
with open("egfr.pdb", 'r') as f:
    for line in f:
        if line.startswith("ATOM"):
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                
                # Calculate distance to pocket center
                dist = ((x - pocket_center[0])**2 + 
                       (y - pocket_center[1])**2 + 
                       (z - pocket_center[2])**2)**0.5
                
                if dist <= radius:
                    pocket_atoms.append(line)
            except:
                continue

print(f"Found {len(pocket_atoms)} atoms within {radius}A of binding pocket")

# Write pocket PDB file
with open("egfr_pocket.pdb", 'w') as f:
    f.write("REMARK  EGFR binding pocket region\n")
    f.write("REMARK  Center: (22.0, 0.3, 52.8)\n")
    f.write("REMARK  Radius: 12.0 Angstroms\n")
    for line in pocket_atoms:
        f.write(line)

print(f"Created egfr_pocket.pdb")

# Convert to PDBQT
print("\nConverting to PDBQT format...")
result = subprocess.run(
    ["obabel", "egfr_pocket.pdb", "-O", "egfr_pocket.pdbqt", "-xr", "-p"],
    capture_output=True, text=True
)

if result.returncode == 0:
    # Count atoms in PDBQT
    with open("egfr_pocket.pdbqt", 'r') as f:
        atoms = sum(1 for line in f if line.startswith("ATOM"))
    print(f"✅ Created egfr_pocket.pdbqt with {atoms} atoms")
else:
    print(f"❌ Conversion failed: {result.stderr}")

print("\n" + "="*60)
