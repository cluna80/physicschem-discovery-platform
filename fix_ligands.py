# -*- coding: utf-8 -*-
import subprocess
import os

def create_3d_ligand(smiles_file, pdbqt_output):
    """Create proper 3D ligand with coordinates"""
    
    # Step 1: Generate 3D coordinates with obabel
    print(f"Generating 3D structure for {smiles_file}...")
    
    # Convert SMILES to 3D PDB with energy minimization
    temp_pdb = smiles_file.replace('.smi', '_3d.pdb')
    cmd = ["obabel", smiles_file, "-O", temp_pdb, "--gen3d", "--best"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  Error: {result.stderr}")
        return False
    
    # Step 2: Convert to PDBQT
    cmd = ["obabel", temp_pdb, "-O", pdbqt_output, "-xh"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        # Verify coordinates are non-zero
        with open(pdbqt_output, 'r') as f:
            lines = f.readlines()
            has_coords = False
            for line in lines:
                if line.startswith("ATOM"):
                    x = float(line[30:38].strip())
                    y = float(line[38:46].strip())
                    z = float(line[46:54].strip())
                    if abs(x) > 0.1 or abs(y) > 0.1 or abs(z) > 0.1:
                        has_coords = True
                        break
            
            if has_coords:
                print(f"  Success: {pdbqt_output} has 3D coordinates")
                return True
            else:
                print(f"  Warning: {pdbqt_output} still has zero coordinates")
                return False
    else:
        print(f"  Error converting to PDBQT")
        return False

# List of ligands to fix
ligands = [
    "simple_quinazoline.smi",
    "gefitinib_like.smi", 
    "erlotinib_like.smi",
    "inhibitor.smi"
]

print("="*60)
print("Generating 3D Ligand Structures")
print("="*60)

for smi in ligands:
    if os.path.exists(smi):
        pdbqt = smi.replace('.smi', '.pdbqt')
        create_3d_ligand(smi, pdbqt)
    else:
        print(f"File not found: {smi}")

print("\n" + "="*60)
print("Done! Now ligands have proper 3D coordinates.")
