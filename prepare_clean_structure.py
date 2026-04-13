#!/usr/bin/env python3
"""
Prepare a clean HIV protease structure from PDB file
Removes ligands, waters, and keeps only protein
"""

import os

print("="*60)
print("Preparing Clean HIV Protease Structure")
print("="*60)

# Read the downloaded PDB
if not os.path.exists("hiv_protease_clean.pdb"):
    print("Error: hiv_protease_clean.pdb not found!")
    print("Downloading from PDB...")
    os.system("wget https://files.rcsb.org/download/1HHP.pdb -O hiv_protease_clean.pdb")

# Read and clean
with open("hiv_protease_clean.pdb", "r") as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines")

# Keep only protein ATOM records and remove ligands/waters
protein_lines = []
for line in lines:
    if line.startswith("ATOM"):
        # Check if it's a protein atom (not ligand or water)
        res_name = line[17:20].strip()
        if res_name in ["HOH", "WAT"]:
            continue
        # Keep all standard amino acids
        protein_lines.append(line)

print(f"Kept {len(protein_lines)} protein atoms")

# Add TER and END
protein_lines.append("TER\n")
protein_lines.append("END\n")

# Save cleaned structure
with open("hiv_protease_clean_fixed.pdb", "w") as f:
    f.writelines(protein_lines)

print("✅ Created: hiv_protease_clean_fixed.pdb")

# Count residues
residues = set()
for line in protein_lines:
    if line.startswith("ATOM"):
        res_id = line[22:26].strip()
        res_name = line[17:20].strip()
        residues.add(f"{res_id}_{res_name}")

print(f"Contains {len(residues)} unique residues")
print("\nFirst few residues:")
for i, res in enumerate(sorted(residues)[:10]):
    print(f"  {res}")
