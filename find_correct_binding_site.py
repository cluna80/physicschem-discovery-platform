# -*- coding: utf-8 -*-
import subprocess

print("="*80)
print("FINDING CORRECT HIV-1 PROTEASE BINDING SITE")
print("="*80)

# Look for the bound inhibitor in the PDB file
result = subprocess.run(["grep", "^HETATM", "hiv_protease.pdb"], capture_output=True, text=True)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    
    # Filter for ligand atoms (not water, not ions)
    ligand_atoms = []
    for line in lines:
        # Skip water and common buffers
        if "HOH" in line or "WAT" in line:
            continue
        # Skip ions like Na+, Cl-
        if "NA" in line[12:16] or "CL" in line[12:16]:
            continue
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            ligand_atoms.append((x, y, z))
        except:
            continue
    
    print(f"\nFound {len(ligand_atoms)} ligand atoms in the structure")
    
    if ligand_atoms:
        center_x = sum(x for x, _, _ in ligand_atoms) / len(ligand_atoms)
        center_y = sum(y for _, y, _ in ligand_atoms) / len(ligand_atoms)
        center_z = sum(z for _, _, z in ligand_atoms) / len(ligand_atoms)
        
        print(f"\nCORRECT BINDING SITE CENTER:")
        print(f"  Center X: {center_x:.3f}")
        print(f"  Center Y: {center_y:.3f}")
        print(f"  Center Z: {center_z:.3f}")
        print(f"  Based on {len(ligand_atoms)} ligand atoms")
        
        # Show first few ligand atoms for verification
        print(f"\nFirst 5 ligand atom coordinates:")
        for i, (x, y, z) in enumerate(ligand_atoms[:5]):
            print(f"  Atom {i+1}: ({x:.2f}, {y:.2f}, {z:.2f})")
        
        # Update binding site file
        with open("hiv_binding_site_correct.txt", "w") as f:
            f.write(f"{center_x},{center_y},{center_z}")
        
        print(f"\n✓ Updated binding site saved to: hiv_binding_site_correct.txt")
        
        # Compare with current
        try:
            with open("hiv_binding_site.txt", 'r') as f:
                current = f.read().strip()
            print(f"\nCurrent binding site: {current}")
            print(f"Correct binding site: {center_x},{center_y},{center_z}")
            print(f"Difference: {abs(center_x - float(current.split(',')[0])):.1f} in X")
        except:
            pass
    else:
        print("\nNo valid ligand atoms found")
else:
    print("\nNo HETATM records found in PDB file")

print("="*80)
