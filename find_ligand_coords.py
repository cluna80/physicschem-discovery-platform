# -*- coding: utf-8 -*-
import subprocess

print("Finding bound erlotinib coordinates in EGFR structure...")
print("="*60)

# Extract the bound ligand (AQ4) from the PDB file
result = subprocess.run(["grep", "AQ4", "egfr.pdb"], capture_output=True, text=True)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    print(f"Found {len(lines)} atoms of bound ligand\n")
    
    # Calculate center of mass
    x_coords = []
    y_coords = []
    z_coords = []
    
    for line in lines:
        if "ATOM" in line or "HETATM" in line:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            x_coords.append(x)
            y_coords.append(y)
            z_coords.append(z)
            print(f"  {line[12:16].strip()} {line[17:20].strip()} {line[22:26].strip()}: x={x:.2f}, y={y:.2f}, z={z:.2f}")
    
    if x_coords:
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        center_z = sum(z_coords) / len(z_coords)
        
        print(f"\n" + "="*60)
        print(f"BOUND LIGAND CENTER OF MASS:")
        print(f"  Center: ({center_x:.2f}, {center_y:.2f}, {center_z:.2f})")
        
        # Determine box size that covers the ligand
        size_x = max(x_coords) - min(x_coords) + 5
        size_y = max(y_coords) - min(y_coords) + 5
        size_z = max(z_coords) - min(z_coords) + 5
        
        print(f"  Suggested box size: ({size_x:.1f}, {size_y:.1f}, {size_z:.1f})")
        print(f"  Or a cube: {max(size_x, size_y, size_z):.1f}")
        
        print(f"\nUse these coordinates for docking:")
        print(f"  center = ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
        print(f"  size = {max(size_x, size_y, size_z):.1f}")
else:
    print("No bound ligand found in structure")
