# Load and visualize compound
load compound_3d.pdb, compound

# Clean display
bg_color black
hide everything

# Show multiple representations
show sticks, compound
show spheres, compound
set sphere_scale, 0.3, compound

# Color by element (standard CPK)
util.cbag compound

# Highlight key groups
# Naphthalene core = yellow
select naphthalene, compound and (resn UNL) and (name C1 or name C2 or name C3 or name C4 or name C5 or name C6 or name C7 or name C8 or name C9 or name C10)
# Fluorine = cyan
select fluorine, compound and name F*
color cyan, fluorine
set sphere_scale, 0.5, fluorine

# Hydroxyl and amide oxygens = red
select oxygens, compound and name O*
color red, oxygens

# Nitrogens = blue
select nitrogens, compound and name N*
color blue, nitrogens

# bis-THF oxygens = orange
select thf_oxygens, compound and (name O3 or name O4 or name O5)
color orange, thf_oxygens

# Orient and zoom
orient compound
zoom compound, 3

# Nice rendering
set stick_radius, 0.15
set ray_shadows, 1
set ambient, 0.4
set direct, 0.6
set specular, 0.3

# Labels off for clean view
set label_size, 0

# Render and save
ray 1920, 1080
png compound_3d_view.png, dpi=300

save compound_session.pse

print "Done! Open compound_session.pse in PyMOL"
