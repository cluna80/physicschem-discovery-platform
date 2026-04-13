# -*- coding: utf-8 -*-
import subprocess

print("Analyzing HIV-1 Protease structure...")
print("="*60)

# Check the PDB file for bound ligand
result = subprocess.run(["grep", "HETATM", "hiv_protease.pdb"], capture_output=True, text=True)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    print(f"Found bound ligand in structure")
    
    # Show first few atoms of the ligand
    for line in lines[:5]:
        x = float(line[30:38].strip())
        y = float(line[38:46].strip())
        z = float(line[46:54].strip())
        print(f"  Atom at: ({x:.1f}, {y:.1f}, {z:.1f})")
    
    # Calculate center
    x_coords = []
    y_coords = []
    z_coords = []
    for line in lines:
        try:
            x_coords.append(float(line[30:38].strip()))
            y_coords.append(float(line[38:46].strip()))
            z_coords.append(float(line[46:54].strip()))
        except:
            pass
    
    if x_coords:
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        center_z = sum(z_coords) / len(z_coords)
        
        print(f"\nCORRECT BINDING SITE CENTER:")
        print(f"  Center: ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
        
        # Update the binding site file
        with open("hiv_binding_site_correct.txt", "w") as f:
            f.write(f"{center_x},{center_y},{center_z}")
        
        print("\nCorrect binding site saved to: hiv_binding_site_correct.txt")
else:
    print("No bound ligand found in structure")
    print("Using literature values: HIV protease active site at (15, 53, 17)")

print("\n" + "="*60)
