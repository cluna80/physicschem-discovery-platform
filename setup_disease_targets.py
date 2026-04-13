# -*- coding: utf-8 -*-
import subprocess
import os

def download_target(pdb_id, name):
    """Download protein structure from PDB"""
    print(f"Downloading {name} ({pdb_id})...")
    subprocess.run(["curl", "-k", "-o", f"{name}.pdb", 
                   f"https://files.rcsb.org/download/{pdb_id}.pdb"])
    return f"{name}.pdb"

def prepare_target(pdb_file, output_file):
    """Convert to PDBQT format"""
    print(f"Preparing {output_file}...")
    subprocess.run(["obabel", pdb_file, "-O", output_file, "-xr", "-p"],
                   capture_output=True)
    return output_file

# Key therapeutic targets
targets = [
    # HIV/AIDS targets
    ("1HVR", "hiv_protease", "HIV-1 Protease with inhibitor"),
    ("1RT1", "hiv_rt", "HIV-1 Reverse Transcriptase"),
    
    # Cancer targets  
    ("1M17", "egfr", "EGFR (already working)"),
    ("3PP0", "her2", "HER2 breast cancer target"),
    ("2GS6", "bcr_abl", "BCR-ABL leukemia target"),
]

print("="*70)
print("SETTING UP DISEASE TARGETS")
print("="*70)

for pdb_id, name, description in targets:
    print(f"\n{description}")
    pdb_file = download_target(pdb_id, name)
    prepare_target(pdb_file, f"{name}_target.pdbqt")
    
    # Count atoms
    if os.path.exists(f"{name}_target.pdbqt"):
        with open(f"{name}_target.pdbqt", 'r') as f:
            atoms = sum(1 for line in f if line.startswith("ATOM"))
        print(f"  -> {atoms} atoms ready for docking")
    else:
        print(f"  -> Failed to prepare {name}")

print("\n" + "="*70)
print("TARGETS READY!")
print("="*70)
