# PyMOL script to visualize CURE_17G_002 and optimized analogs
# Run: pymol view_compounds.pml

# Load CURE_17G_002 (current lead)
load ../protein_ligand_md/clean_run/md.gro
load ../protein_ligand_md/clean_run/ligand.pdb

# Create a session
as cartoon
color blue, ss h
color red, ss s
color green, ss l

# Show ligand as sticks
show sticks, ligand
color yellow, ligand
set_bond stick_radius, 0.2, ligand

# Show active site residues
select active_site, resi 25
show sticks, active_site
color orange, active_site

# Center on active site
center active_site

# Create nice view
set ray_shadows, 0
set ambient, 0.3
set direct, 0.8
set specular, 0.5

# Save image
png cure_17g_002_binding.png, width=2400, dpi=300, ray=1

# Show surface
show surface, polymer
set transparency, 0.5, polymer

# Save session
save optimization_view.pse

print("View created! Check cure_17g_002_binding.png")
