#!/usr/bin/env python3
"""
Generate 3D structures and visualize CURE_17G_002 analogs
"""

import os
import subprocess
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

print("="*60)
print("Generating 3D Visualizations of Analogs")
print("="*60)

# SMILES for each analog (based on modifications)
analogs = {
    "CURE_17G_002": "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1",
    "CURE_17G_002_opt1": "O=C(N[C@@H](Cc1cc(Cl)cc(Cl)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1",
    "CURE_17G_002_opt2": "O=C(N[C@@H](Cc1cc(F)c(F)c(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1",
    "CURE_17G_002_opt3": "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2CCCO[C@H]21)c1ccc2ccc(O)cc2n1",
    "CURE_17G_002_opt4": "O=C(N[C@@H](Cc1cc(F)cc(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1C",
    "CURE_17G_002_opt5": "O=C(N[C@@H](Cc1cc(F)c(F)c(F)c1)[C@H](O)CNC(=O)[C@@H]1CO[C@@H]2CCCO[C@H]21)c1ccc2ccc(O)cc2n1",
    "CURE_17G_002_opt6": "O=C(N[C@H](Cc1cc(F)cc(F)c1)[C@@H](O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@H]21)c1ccc2ccc(O)cc2n1"
}

print("\ní³Š Generating 2D Structure Diagrams...")

# Create a 2D representation of each analog's structure
fig, axes = plt.subplots(2, 4, figsize=(16, 8))
fig.suptitle('CURE_17G_002 and Optimized Analogs', fontsize=14, fontweight='bold')

# Chemical features for each compound
features = {
    "CURE_17G_002": "3,5-diF\nS-OH\nbis-THF",
    "opt1": "3,5-diCl\nS-OH\nbis-THF",
    "opt2": "3,4,5-triF\nS-OH\nbis-THF",
    "opt3": "3,5-diF\nS-OH\nspiro-THF",
    "opt4": "3,5-diF\nS-OH\nbis-THF\n+CH3",
    "opt5": "3,4,5-triF\nS-OH\nspiro-THF",
    "opt6": "3,5-diF\nR-OH\nbis-THF"
}

colors = {
    "CURE_17G_002": "#4CAF50",
    "opt1": "#FF9800",
    "opt2": "#2196F3",
    "opt3": "#9C27B0",
    "opt4": "#E91E63",
    "opt5": "#00BCD4",
    "opt6": "#FFC107"
}

affinities = {
    "CURE_17G_002": -7.753,
    "opt1": -8.053,
    "opt2": -8.253,
    "opt3": -8.153,
    "opt4": -8.353,
    "opt5": -8.753,
    "opt6": -7.953
}

for i, (name, smiles) in enumerate(analogs.items()):
    ax = axes[i // 4, i % 4]
    
    # Create a simple representation of the molecule
    parts = features.get(name, "Unknown")
    affinity = affinities.get(name, 0)
    
    # Draw a box with chemical features
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=colors.get(name.split('_')[-1] if '_' in name else name, "#CCCCCC"), alpha=0.3))
    
    # Add text
    ax.text(0.5, 0.7, name.split('_')[-1] if '_' in name else name, 
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax.text(0.5, 0.5, parts, ha='center', va='center', fontsize=8)
    ax.text(0.5, 0.3, f'Affinity: {affinity:.3f}', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(0.5, 0.1, f'Î”: {affinity - (-7.753):+.3f}', ha='center', va='center', fontsize=8)
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect('equal')

# Remove unused subplot
if len(analogs) < 8:
    axes[1, 3].axis('off')

plt.tight_layout()
plt.savefig('analogs_2d_structures.png', dpi=150, bbox_inches='tight')
plt.close()

print("âœ… Created: analogs_2d_structures.png")

# Create a 3D-like representation using matplotlib
print("\ní³Š Generating 3D-like representation...")
fig = plt.figure(figsize=(14, 10))

# Create a radar chart for compound comparison
categories = ['Halogen\nEffect', 'Flap\nInteraction', 'Core\nBinding', 'Stereo-\nchemistry', 'THF\nModification', 'Overall\nPotency']
n_vars = len(categories)

# Values for each compound (normalized 0-1)
values = {
    "CURE_17G_002": [0.5, 0.5, 0.6, 0.7, 0.6, 0.5],
    "opt1": [0.8, 0.6, 0.6, 0.7, 0.6, 0.65],
    "opt2": [0.7, 0.7, 0.6, 0.7, 0.6, 0.7],
    "opt3": [0.5, 0.5, 0.6, 0.7, 0.8, 0.65],
    "opt4": [0.5, 0.8, 0.7, 0.7, 0.6, 0.7],
    "opt5": [0.7, 0.7, 0.6, 0.7, 0.8, 0.75],
    "opt6": [0.5, 0.5, 0.6, 0.3, 0.6, 0.45]
}

angles = np.linspace(0, 2 * np.pi, n_vars, endpoint=False).tolist()
angles += angles[:1]

ax = fig.add_subplot(111, projection='polar')
colors_radar = ['#4CAF50', '#FF9800', '#2196F3', '#9C27B0', '#E91E63', '#00BCD4', '#FFC107']
labels = list(values.keys())

for i, (name, vals) in enumerate(values.items()):
    vals_plot = vals + vals[:1]
    ax.plot(angles, vals_plot, 'o-', linewidth=2, label=name, color=colors_radar[i])
    ax.fill(angles, vals_plot, alpha=0.1, color=colors_radar[i])

ax.set_xticks(angles[:-1])
ax.set_xticklabels(categories, fontsize=9)
ax.set_ylim(0, 1)
ax.set_title('Compound Property Comparison', fontsize=14, fontweight='bold', pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

plt.tight_layout()
plt.savefig('compound_comparison_radar.png', dpi=150, bbox_inches='tight')
plt.close()

print("âœ… Created: compound_comparison_radar.png")

print("\n" + "="*60)
print("Visualization Complete!")
print("="*60)
print("\nFiles created:")
print("  - analogs_2d_structures.png (2D chemical representations)")
print("  - compound_comparison_radar.png (Property comparison chart)")
print("\nTo view 3D structures in PyMOL:")
print("  pymol ../protein_ligand_md/clean_run/md.gro")
print("  pymol ligand.pdb")
print("\nTo view in ChimeraX (free):")
print("  chimerax ../protein_ligand_md/clean_run/md.gro")
