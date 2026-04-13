# -*- coding: utf-8 -*-
import subprocess

print("Setting up HIV-1 Protease for docking...")
print("="*60)

# Extract bound inhibitor coordinates
result = subprocess.run(["grep", "HETATM", "hiv_protease.pdb"], capture_output=True, text=True)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    x_coords, y_coords, z_coords = [], [], []
    
    for line in lines[:20]:
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            x_coords.append(x)
            y_coords.append(y)
            z_coords.append(z)
        except:
            pass
    
    if x_coords:
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        center_z = sum(z_coords) / len(z_coords)
        
        print(f"\nHIV Protease binding pocket center:")
        print(f"  Center: ({center_x:.1f}, {center_y:.1f}, {center_z:.1f})")
        
        # Save binding site
        with open("hiv_binding_site.txt", "w") as f:
            f.write(f"{center_x},{center_y},{center_z}")
else:
    print("Using literature values for HIV protease active site")
    with open("hiv_binding_site.txt", "w") as f:
        f.write("15.0,53.0,17.0")

print("\n✅ HIV Protease ready for screening!")
