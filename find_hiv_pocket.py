# -*- coding: utf-8 -*-
import subprocess

print("Finding HIV-1 Protease binding pocket...")
print("="*60)

# Look for ligand atoms (HETATM) in the PDB file
result = subprocess.run(["grep", "^HETATM", "hiv_protease.pdb"], capture_output=True, text=True)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    
    # Filter only lines with valid coordinates
    valid_lines = []
    for line in lines:
        try:
            # Try to extract coordinates
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            valid_lines.append(line)
        except:
            continue
    
    print(f"Found {len(valid_lines)} ligand atoms\n")
    
    # Calculate center
    x_coords = []
    y_coords = []
    z_coords = []
    
    for line in valid_lines:
        x = float(line[30:38].strip())
        y = float(line[38:46].strip())
        z = float(line[46:54].strip())
        x_coords.append(x)
        y_coords.append(y)
        z_coords.append(z)
    
    if x_coords:
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        center_z = sum(z_coords) / len(z_coords)
        
        print(f"CORRECT BINDING POCKET CENTER:")
        print(f"  Center: ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
        print(f"  Based on {len(x_coords)} ligand atoms")
        
        # Save correct coordinates
        with open("hiv_binding_site.txt", "w") as f:
            f.write(f"{center_x},{center_y},{center_z}")
        
        print("\nUpdated binding site saved to: hiv_binding_site.txt")
else:
    print("No ligand found. Using literature values for HIV protease active site")
    # Literature coordinates for HIV protease active site
    center = (15.0, 53.0, 17.0)
    with open("hiv_binding_site.txt", "w") as f:
        f.write(f"{center[0]},{center[1]},{center[2]}")
    print(f"Using literature coordinates: ({center[0]}, {center[1]}, {center[2]})")

print("\n" + "="*60)
