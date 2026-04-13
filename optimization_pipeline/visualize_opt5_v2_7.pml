# ============================================================
# opt5_v2_7 Visualization in HIV Protease Active Site
# ============================================================

# Load protein
load ../gromacs_md_simulation/protein_ready.pdb, protein

# Load opt5_v2_7
load opt5_v2_7_pymol.pdb, opt5_v2_7

# Load original CURE_17G_002 for comparison
load ../hiv_protease_with_CURE_17G_002/ligand_best.pdb, CURE_17G_002

# ── Protein styling ──────────────────────────────────────────
hide everything, protein
show cartoon, protein
color slate, protein
set cartoon_transparency, 0.4

# ── Active site surface ──────────────────────────────────────
select active_site, protein and (resi 25+26+27+28+29+30+48+49+50+80+81+82+84) 
show surface, active_site
color white, active_site
set surface_transparency, 0.6

# ── opt5_v2_7 styling ────────────────────────────────────────
hide everything, opt5_v2_7
show sticks, opt5_v2_7
util.cbag opt5_v2_7
# Color CF3 group cyan to highlight the key modification
select cf3_group, opt5_v2_7 and (name F*)
color cyan, cf3_group
set stick_radius, 0.2, opt5_v2_7

# ── CURE_17G_002 for comparison (ghost) ─────────────────────
hide everything, CURE_17G_002
show lines, CURE_17G_002
color orange, CURE_17G_002
set line_width, 2, CURE_17G_002

# ── Key residues ─────────────────────────────────────────────
select catalytic, protein and (resi 25+26)
show sticks, catalytic
color red, catalytic
label catalytic and name CA, "%s%s" % (resn, resi)

select flap_region, protein and (resi 46+47+48+49+50+51+52+53+54)
show ribbon, flap_region
color yellow, flap_region

select resistance_sites, protein and (resi 30+48+50+82+84+90)
show sticks, resistance_sites
color magenta, resistance_sites

# ── Center view on ligand ────────────────────────────────────
center opt5_v2_7
zoom opt5_v2_7, 8
orient opt5_v2_7

# ── Distances to key residues ────────────────────────────────
distance d_ASP25A, opt5_v2_7 and (name O or name N), protein and (resi 25 and chain A and name OD1)
distance d_ASP25B, opt5_v2_7 and (name O or name N), protein and (resi 25 and chain B and name OD1)
color yellow, d_ASP25A
color yellow, d_ASP25B

# ── Ray trace settings ───────────────────────────────────────
set ray_shadows, 1
set ambient, 0.3
set direct, 0.7
set ray_trace_mode, 1
bg_color black

# ── Save session ─────────────────────────────────────────────
save opt5_v2_7_session.pse

# ── Render image ─────────────────────────────────────────────
ray 1920, 1080
png opt5_v2_7_active_site.png, dpi=300

print "✅ opt5_v2_7 visualization complete"
print "   opt5_v2_7_session.pse — open this in PyMOL"
print "   opt5_v2_7_active_site.png — rendered image"
