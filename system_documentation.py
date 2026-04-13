# -*- coding: utf-8 -*-
"""
AUTONOMOUS AI QUANTUM LAB - SYSTEM DOCUMENTATION
Drug Discovery Platform for HIV Cure Research

CORRECTIONS from original:
  - Best compound: CURE_13G_001 at -7.333 (not CURE_12G_001 at -7.29)
  - Darunavir Vina benchmark: ~-10.2 kcal/mol (not -8.8)
  - Gap to Darunavir: ~2.87 kcal/mol (not 1.51)
  - Quantum speedup: simulated on classical hardware (not real quantum hardware)
  - AutoDock Vina uses CPU, not GPU
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np

fig, ax = plt.subplots(1, 1, figsize=(20, 14))
ax.set_xlim(0, 20)
ax.set_ylim(0, 14)
ax.axis('off')

# Title
ax.text(10, 13.5, 'AUTONOMOUS AI QUANTUM LAB — HIV DRUG DISCOVERY PLATFORM',
        fontsize=16, fontweight='bold', ha='center', color='navy')
ax.text(10, 13.0, 'Quantum-Inspired Molecular Docking Pipeline for HIV Protease Inhibitor Research',
        fontsize=10, ha='center', style='italic', color='gray')

# ── QUANTUM COMPUTING CORE ───────────────────────────────────
qb = FancyBboxPatch((0.5, 9.5), 3.5, 2.5, boxstyle="round,pad=0.1",
                    facecolor='lightblue', edgecolor='navy', linewidth=2)
ax.add_patch(qb)
ax.text(2.25, 11.5, 'QUANTUM CORE',        fontsize=11, fontweight='bold', ha='center')
ax.text(2.25, 11.0, '3–10 Qubit Simulation', fontsize=9, ha='center')
ax.text(2.25, 10.6, 'Grover-Inspired Search', fontsize=9, ha='center')
ax.text(2.25, 10.2, 'Classical Hardware',    fontsize=9, ha='center', color='gray')

# ── AI AGENT ────────────────────────────────────────────────
ab = FancyBboxPatch((4.5, 9.5), 3.5, 2.5, boxstyle="round,pad=0.1",
                    facecolor='lightgreen', edgecolor='darkgreen', linewidth=2)
ax.add_patch(ab)
ax.text(6.25, 11.5, 'AI AGENT',              fontsize=11, fontweight='bold', ha='center')
ax.text(6.25, 11.0, 'Compound Design',       fontsize=9, ha='center')
ax.text(6.25, 10.6, 'Lipinski / QED Filter', fontsize=9, ha='center')
ax.text(6.25, 10.2, '100+ Compounds / Run',  fontsize=9, ha='center', color='green')

# ── DOCKING ENGINE ───────────────────────────────────────────
db = FancyBboxPatch((8.5, 9.5), 3.5, 2.5, boxstyle="round,pad=0.1",
                    facecolor='lightcoral', edgecolor='darkred', linewidth=2)
ax.add_patch(db)
ax.text(10.25, 11.5, 'DOCKING ENGINE',     fontsize=11, fontweight='bold', ha='center')
ax.text(10.25, 11.0, 'AutoDock Vina',      fontsize=9, ha='center')
ax.text(10.25, 10.6, 'CPU-Parallel',       fontsize=9, ha='center')
ax.text(10.25, 10.2, 'Meeko PDBQT Prep',  fontsize=9, ha='center', color='green')

# ── VALIDATION ───────────────────────────────────────────────
vb = FancyBboxPatch((12.5, 9.5), 3.5, 2.5, boxstyle="round,pad=0.1",
                    facecolor='lightyellow', edgecolor='goldenrod', linewidth=2)
ax.add_patch(vb)
ax.text(14.25, 11.5, 'VALIDATION',          fontsize=11, fontweight='bold', ha='center')
ax.text(14.25, 11.0, 'ChEMBL Similarity',   fontsize=9, ha='center')
ax.text(14.25, 10.6, 'PubChem Search',      fontsize=9, ha='center')
ax.text(14.25, 10.2, 'Drug-Likeness (QED)', fontsize=9, ha='center', color='green')

# ── OPTIMIZATION LOOP ────────────────────────────────────────
ob = FancyBboxPatch((16.5, 9.5), 3, 2.5, boxstyle="round,pad=0.1",
                    facecolor='lightgray', edgecolor='gray', linewidth=2)
ax.add_patch(ob)
ax.text(18, 11.5, 'OPTIMIZATION',        fontsize=11, fontweight='bold', ha='center')
ax.text(18, 11.0, 'Iterative Refinement', fontsize=9, ha='center')
ax.text(18, 10.6, 'SAR Analysis',         fontsize=9, ha='center')
ax.text(18, 10.2, '15 Generations',       fontsize=9, ha='center', color='green')

# ── ARROWS ───────────────────────────────────────────────────
for x1, x2 in [(4.0, 4.5), (8.0, 8.5), (12.0, 12.5), (16.0, 16.5)]:
    ax.annotate('', xy=(x2, 10.75), xytext=(x1, 10.75),
                arrowprops=dict(arrowstyle='->', color='navy', lw=2))
ax.annotate('', xy=(6.25, 9.5), xytext=(18, 9.5),
            arrowprops=dict(arrowstyle='->', color='green', lw=2,
                           connectionstyle="arc3,rad=-0.2"))
ax.text(11.25, 8.9, 'ITERATIVE OPTIMIZATION LOOP (15 Generations)', 
        fontsize=9, ha='center', color='green')

# ── PERFORMANCE METRICS ──────────────────────────────────────
mb = FancyBboxPatch((0.5, 3.0), 18.5, 2.5, boxstyle="round,pad=0.1",
                    facecolor='#F5F5F5', edgecolor='gray', linewidth=1)
ax.add_patch(mb)
ax.text(9.75, 5.2, 'PERFORMANCE METRICS (VERIFIED)', fontsize=10, fontweight='bold', ha='center')

metrics = [
    ('Compounds Screened', '130+',           'Across 15 generations'),
    ('Best Affinity',      '-7.333 kcal/mol', 'CURE_13G_001'),
    ('Improvement',        '-1.97 kcal/mol',  'From CURE_4G_003'),
    ('Gap to Darunavir',   '~2.87 kcal/mol',  'Vina benchmark -10.2'),
    ('Novel Scaffold',     'ChEMBL: 0 hits',   '85% similarity'),
    ('Generations Run',    '15',              '10 compounds/gen'),
]
x_pos = [1.5, 5.0, 8.5, 12.0, 15.5, 18.5]
for i, (label, value, desc) in enumerate(metrics):
    ax.text(x_pos[i], 4.6, label, fontsize=8, fontweight='bold', ha='center')
    ax.text(x_pos[i], 4.2, value, fontsize=9,  color='darkgreen', fontweight='bold', ha='center')
    ax.text(x_pos[i], 3.8, desc,  fontsize=7,  color='gray', ha='center')

# ── ACHIEVEMENTS ─────────────────────────────────────────────
ax.text(1, 2.4, 'KEY ACHIEVEMENTS', fontsize=10, fontweight='bold', color='navy')
achievements = [
    '✓ 130+ HIV Protease Inhibitor Candidates Generated',
    '✓ Quantum-Inspired Grover Search (simulated, 3–10 qubits)',
    '✓ Novel scaffold — zero ChEMBL matches at 85% similarity',
    '✓ Best compound: CURE_13G_001 at -7.333 kcal/mol',
    '✓ Meeko pipeline — clean, reproducible PDBQT preparation',
    '✓ Fully automated SMILES → Docking → Analysis pipeline',
]
for i, a in enumerate(achievements):
    ax.text(1, 2.0 - i * 0.27, a, fontsize=8, color='darkgreen')

# ── NEXT STEPS ───────────────────────────────────────────────
ax.text(12, 2.4, 'NEXT STEPS', fontsize=10, fontweight='bold', color='navy')
nexts = [
    'Reach -9.0 kcal/mol (Darunavir-level potency)',
    'In vitro IC50 testing of top 3 candidates',
    'Patent search & provisional filing',
    'Preprint submission to bioRxiv',
]
for i, n in enumerate(nexts):
    ax.text(12, 2.0 - i * 0.27, n, fontsize=8, color='darkorange')

plt.tight_layout()
plt.savefig('quantum_lab_workflow.png', dpi=200, bbox_inches='tight', facecolor='white')
plt.show()

print("=" * 70)
print("  SYSTEM DOCUMENTATION GENERATED")
print("=" * 70)
print("  Saved: quantum_lab_workflow.png")
print()
print("  KEY CORRECTIONS APPLIED:")
print("    - Best compound: CURE_13G_001 at -7.333 (updated from -7.29)")
print("    - Darunavir Vina ref: -10.2 kcal/mol (not -8.8)")
print("    - Gap to Darunavir: ~2.87 kcal/mol (not 1.51)")
print("    - Quantum: simulated Grover on CPU (not real quantum hardware)")
print("    - Docking: CPU-parallel (AutoDock Vina does not use GPU)")
print("=" * 70)