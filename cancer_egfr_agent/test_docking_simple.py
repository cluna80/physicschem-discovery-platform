# check_receptor.py
import os

print("="*70)
print("CHECKING EGFR RECEPTOR FILE")
print("="*70)

receptor = "egfr_receptor.pdbqt"

if not os.path.exists(receptor):
    print(f"\n✗ Receptor file not found: {receptor}")
    print("\nYou need to prepare the receptor first.")
    print("\nOption 1: Download and prepare 4HJO (for covalent inhibitors):")
    print("  wget https://files.rcsb.org/download/4HJO.pdb")
    print("  grep '^ATOM' 4HJO.pdb | grep ' A ' > 4HJO_clean.pdb")
    print("  obabel 4HJO_clean.pdb -O egfr_receptor.pdbqt -xr --partialcharge gasteiger")
    print("\nOption 2: Use 1M17 (your original target):")
    print("  wget https://files.rcsb.org/download/1M17.pdb")
    print("  grep '^ATOM' 1M17.pdb > 1M17_clean.pdb")
    print("  obabel 1M17_clean.pdb -O egfr_receptor.pdbqt -xr --partialcharge gasteiger")
    exit()

print(f"\n✓ Receptor file found: {receptor}")
print(f"  Size: {os.path.getsize(receptor)} bytes")

# Count atoms
with open(receptor, 'r') as f:
    lines = f.readlines()
    atoms = [l for l in lines if l.startswith('ATOM')]
    print(f"  Number of atoms: {len(atoms)}")

# Check key residues
key_residues = {
    "MET793": "Hinge binder",
    "CYS797": "Covalent target",
    "LYS745": "Catalytic lysine", 
    "ASP855": "DFG motif",
    "GLN791": "Gatekeeper"
}

print("\nKey residues present:")
found = False
for res, desc in key_residues.items():
    if any(res in line for line in lines):
        print(f"  ✓ {res} ({desc})")
        found = True
    else:
        print(f"  ✗ {res} ({desc}) - MISSING")

if not found:
    print("\n⚠ WARNING: No key EGFR residues found!")
    print("  Your receptor file may be corrupted or from wrong PDB.")
    print("  Please prepare a fresh receptor file using the commands above.")

# Check for water
waters = [l for l in lines if 'HOH' in l or 'WAT' in l]
if waters:
    print(f"\n⚠ Found {len(waters)} water molecules - should be removed for docking")

# Check for ligands
ligands = [l for l in lines if l.startswith('HETATM') and not ('HOH' in l or 'WAT' in l)]
if ligands:
    print(f"\n⚠ Found {len(ligands)} non-water HETATM records - should be removed")

print("\n" + "="*70)
print("RECOMMENDED RECEPTOR PREPARATION")
print("="*70)
print("""
For your molecules (with acrylamide warheads), use 4HJO:

  # Download
  wget https://files.rcsb.org/download/4HJO.pdb
  
  # Extract protein (chain A only)
  grep '^ATOM' 4HJO.pdb | grep ' A ' > 4HJO_protein.pdb
  
  # Remove water
  grep -v 'HOH' 4HJO_protein.pdb > 4HJO_dry.pdb
  
  # Convert to PDBQT
  obabel 4HJO_dry.pdb -O egfr_4hjo.pdbqt -xr --partialcharge gasteiger
  
  # Use box center (22.0, 0.5, 48.0) for docking
""")