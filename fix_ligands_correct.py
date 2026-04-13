# -*- coding: utf-8 -*-
import subprocess
import os

def create_3d_ligand_force(smiles_file, pdbqt_output):
    """Force creation of 3D coordinates using multiple methods"""
    
    print(f"\nGenerating 3D structure for {smiles_file}...")
    
    # Method 1: Try with explicit 3D generation
    temp_sdf = smiles_file.replace('.smi', '_temp.sdf')
    cmd = ["obabel", smiles_file, "-O", temp_sdf, "--gen3d", "--best", "--conformer", "--nconf=1"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"  Method 1 failed, trying alternative...")
        # Method 2: Use different force field
        cmd = ["obabel", smiles_file, "-O", temp_sdf, "--gen3d", "--ff=MMFF94", "--nconf=1"]
        result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0 and os.path.exists(temp_sdf) and os.path.getsize(temp_sdf) > 0:
        # Convert to PDBQT
        cmd = ["obabel", temp_sdf, "-O", pdbqt_output, "-xh"]
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Verify coordinates
        with open(pdbqt_output, 'r') as f:
            lines = f.readlines()
            has_coords = False
            for line in lines:
                if line.startswith("ATOM"):
                    try:
                        x = float(line[30:38].strip())
                        y = float(line[38:46].strip())
                        z = float(line[46:54].strip())
                        if abs(x) > 0.1 or abs(y) > 0.1 or abs(z) > 0.1:
                            has_coords = True
                            print(f"  Success! First atom at ({x:.2f}, {y:.2f}, {z:.2f})")
                            break
                    except:
                        pass
            
            if has_coords:
                # Count atoms
                atoms = sum(1 for l in lines if l.startswith("ATOM"))
                print(f"  {atoms} atoms with 3D coordinates")
                return True
            else:
                print(f"  Warning: Still zero coordinates")
                return False
    else:
        print(f"  Failed to generate 3D coordinates")
        return False

# List of ligands
ligands = ["simple_quinazoline.smi", "gefitinib_like.smi", "erlotinib_like.smi", "inhibitor.smi"]

print("="*60)
print("Generating 3D Ligand Structures (Method 2)")
print("="*60)

for smi in ligands:
    if os.path.exists(smi):
        pdbqt = smi.replace('.smi', '.pdbqt')
        create_3d_ligand_force(smi, pdbqt)
    else:
        print(f"File not found: {smi}")

print("\n" + "="*60)
print("Now using the correct binding pocket coordinates")
