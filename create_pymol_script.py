# -*- coding: utf-8 -*-
"""
Create PyMOL script for viewing CURE_4G_003 in HIV protease binding site
"""

import os

# Create a more comprehensive PyMOL script
pymol_script = '''
# PyMOL script for visualizing HIV lead compound CURE_4G_003
# Run with: pymol visualize_cure.pml

# Load HIV protease structure (1HVR)
load hiv_protease.pdb, protease

# Load our lead compound
load CURE_4G_003_3d.pdb, ligand

# Hide everything initially
hide all

# Show protease as cartoon
show cartoon, protease
set cartoon_transparency, 0.3, protease

# Show ligand as sticks and spheres
show sticks, ligand
show spheres, ligand
set sphere_scale, 0.3, ligand

# Color settings
color grey90, protease
color red, ligand
color orange, elem F

# Highlight binding site residues
select active_site, (resid 25-30 or resid 48-53 or resid 82-85)
show sticks, active_site
color blue, active_site

# Show hydrogen bonds
distance hbonds, ligand, protease, 3.5, mode=2
set dash_color, yellow

# Zoom to binding site
zoom ligand

# Add labels
label ligand, "CURE_4G_003"
set label_color, white
set label_size, 14

# Ray tracing for publication quality
ray 1200, 800

# Save image
png cure_4g_003_binding_pose.png, width=1200, height=800, dpi=300

print("Binding pose saved to cure_4g_003_binding_pose.png")
'''

# Save script
with open("visualize_cure.pml", "w") as f:
    f.write(pymol_script)

print("="*80)
print("PYMOL VISUALIZATION READY")
print("="*80)
print("To view the binding pose in 3D:")
print("  pymol visualize_cure.pml")
print("")
print("If you don't have PyMOL, try:")
print("  1. Download PyMOL: https://pymol.org/")
print("  2. Or use Chimera: https://www.cgl.ucsf.edu/chimera/")
print("")
print("Files created:")
print("  • CURE_4G_003_2d.png - 2D structure (view now)")
print("  • CURE_4G_003_3d.pdb - 3D structure")
print("  • visualize_cure.pml - PyMOL script")
print("="*80)
