# -*- coding: utf-8 -*-
import subprocess
import os

def fix_ligand(smiles_file, output_pdbqt):
    """Fix ligand by generating proper 3D coordinates"""
    if not os.path.exists(smiles_file):
        print(f"  {smiles_file} not found")
        return False
    
    # Generate 3D coordinates
    temp_pdb = smiles_file.replace('.smi', '_3d.pdb')
    cmd = ["obabel", smiles_file, "-O", temp_pdb, "--gen3d", "--best"]
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode == 0 and os.path.exists(temp_pdb):
        # Convert to PDBQT
        cmd = ["obabel", temp_pdb, "-O", output_pdbqt, "-xh"]
        subprocess.run(cmd, capture_output=True)
        
        # Verify
        with open(output_pdbqt, 'r') as f:
            content = f.read()
            if "ATOM" in content:
                print(f"  Fixed: {output_pdbqt}")
                return True
    
    print(f"  Failed to fix: {output_pdbqt}")
    return False

# Fix each compound
compounds = [
    ("gefitinib_like.smi", "gefitinib_like_fixed.pdbqt"),
    ("erlotinib_like.smi", "erlotinib_like_fixed.pdbqt"),
    ("inhibitor.smi", "inhibitor_fixed.pdbqt")
]

print("Fixing compound coordinates...")
print("="*50)

for smi, pdbqt in compounds:
    print(f"\nProcessing {smi} -> {pdbqt}")
    fix_ligand(smi, pdbqt)

print("\n" + "="*50)
print("Fixed compounds created:")
os.system("ls -la *fixed.pdbqt 2>/dev/null || echo 'No fixed files created'")
