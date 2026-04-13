#!/usr/bin/env python3
"""
Generate all publication-quality plots for HIV Protease MD Simulation Report
"""

import numpy as np
import matplotlib.pyplot as plt
import os
from matplotlib.patches import Rectangle

# Set publication-quality style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['font.size'] = 12
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']

print("="*60)
print("Generating Publication-Quality Figures")
print("="*60)

# 1. RMSD Plot
if os.path.exists('rmsd.xvg'):
    data = np.loadtxt('rmsd.xvg', comments=['@', '#'])
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(data[:,0], data[:,1], 'b-', linewidth=2, label='RMSD')
    ax.set_xlabel('Time (ns)', fontsize=12)
    ax.set_ylabel('RMSD (nm)', fontsize=12)
    ax.set_title('HIV Protease Stability During 1 ns MD Simulation', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=np.mean(data[:,1]), color='r', linestyle='--', 
               label=f'Mean RMSD: {np.mean(data[:,1]):.3f} nm')
    ax.legend()
    ax.set_xlim(0, 1)
    plt.tight_layout()
    plt.savefig('documentation/figures/Figure1_RMSD.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figure 1: RMSD plot generated")

# 2. RMSF Plot with Flap Region Highlight
if os.path.exists('rmsf.xvg'):
    data = np.loadtxt('rmsf.xvg', comments=['@', '#'])
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(data[:,0], data[:,1], 'r-', linewidth=2)
    ax.fill_between(data[:,0], 0, data[:,1], alpha=0.3, color='red')
    ax.set_xlabel('Residue Number', fontsize=12)
    ax.set_ylabel('RMSF (nm)', fontsize=12)
    ax.set_title('Residue Flexibility in HIV Protease', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    # Highlight flap region
    ax.axvspan(43, 58, alpha=0.3, color='orange', label='Flap Region (43-58)')
    ax.legend()
    plt.tight_layout()
    plt.savefig('documentation/figures/Figure2_RMSF.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figure 2: RMSF plot generated")

# 3. Radius of Gyration
if os.path.exists('gyrate.xvg'):
    data = np.loadtxt('gyrate.xvg', comments=['@', '#'])
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(data[:,0], data[:,1], 'g-', linewidth=2)
    ax.set_xlabel('Time (ns)', fontsize=12)
    ax.set_ylabel('Radius of Gyration (nm)', fontsize=12)
    ax.set_title('Protein Compactness During Simulation', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=np.mean(data[:,1]), color='orange', linestyle='--',
               label=f'Mean Rg: {np.mean(data[:,1]):.3f} nm')
    ax.legend()
    plt.tight_layout()
    plt.savefig('documentation/figures/Figure3_Gyration.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Figure 3: Radius of Gyration plot generated")

# 4. Combined Analysis Figure
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('HIV Protease MD Simulation Analysis (1 ns)', fontsize=16, fontweight='bold')

# RMSD
if os.path.exists('rmsd.xvg'):
    data = np.loadtxt('rmsd.xvg', comments=['@', '#'])
    axes[0,0].plot(data[:,0], data[:,1], 'b-', linewidth=2)
    axes[0,0].set_xlabel('Time (ns)')
    axes[0,0].set_ylabel('RMSD (nm)')
    axes[0,0].set_title('Protein Stability')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].axhline(y=np.mean(data[:,1]), color='r', linestyle='--')

# RMSF
if os.path.exists('rmsf.xvg'):
    data = np.loadtxt('rmsf.xvg', comments=['@', '#'])
    axes[0,1].plot(data[:,0], data[:,1], 'r-', linewidth=2)
    axes[0,1].fill_between(data[:,0], 0, data[:,1], alpha=0.3, color='red')
    axes[0,1].set_xlabel('Residue Number')
    axes[0,1].set_ylabel('RMSF (nm)')
    axes[0,1].set_title('Residue Flexibility')
    axes[0,1].grid(True, alpha=0.3)
    axes[0,1].axvspan(43, 58, alpha=0.3, color='orange')

# Rg
if os.path.exists('gyrate.xvg'):
    data = np.loadtxt('gyrate.xvg', comments=['@', '#'])
    axes[1,0].plot(data[:,0], data[:,1], 'g-', linewidth=2)
    axes[1,0].set_xlabel('Time (ns)')
    axes[1,0].set_ylabel('Rg (nm)')
    axes[1,0].set_title('Protein Compactness')
    axes[1,0].grid(True, alpha=0.3)

# Temperature stability from log
axes[1,1].text(0.1, 0.5, 'Temperature: 300 ± 3 K\nPressure: 1.3 ± 0.5 bar\nEnergy Drift: 1.67e-05 kJ/mol/ps/atom\n\nSimulation Time: 1 ns\nSteps: 500,000\nAtoms: 31,522\n\nStability: EXCELLENT\nRMSD < 0.15 nm', 
               transform=axes[1,1].transAxes, fontsize=10, verticalalignment='center')
axes[1,1].set_title('Simulation Statistics')
axes[1,1].axis('off')

plt.tight_layout()
plt.savefig('documentation/figures/Figure_Summary.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Figure Summary: Combined analysis plot generated")

# 5. Gnina Results Bar Chart
gnina_data = {
    'Compound': ['CURE_13G_001', 'CURE_17G_003', 'CURE_17G_002', 'CURE_17G_007', 'Q15_020', 'CURE_16G_007'],
    'CNN_Score': [0.6542, 0.5668, 0.5596, 0.5340, 0.4986, 0.4795],
    'Vina_Affinity': [-4.97, -6.65, -6.58, -6.06, -4.94, -7.13]
}

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle('Gnina Docking Results for CURE Compounds', fontsize=14, fontweight='bold')

# CNN Scores
bars1 = axes[0].bar(gnina_data['Compound'], gnina_data['CNN_Score'], color='steelblue')
axes[0].set_ylabel('CNN Score (Binding Probability)')
axes[0].set_title('CNN Score Ranking')
axes[0].tick_params(axis='x', rotation=45)
axes[0].axhline(y=0.5, color='r', linestyle='--', label='High Confidence Threshold')
axes[0].legend()
for bar, score in zip(bars1, gnina_data['CNN_Score']):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'{score:.3f}', ha='center', va='bottom', fontsize=9)

# Vina Affinity
bars2 = axes[1].bar(gnina_data['Compound'], gnina_data['Vina_Affinity'], color='coral')
axes[1].set_ylabel('Vina Affinity (kcal/mol)')
axes[1].set_title('Vina Affinity Ranking')
axes[1].tick_params(axis='x', rotation=45)
axes[1].axhline(y=-7.0, color='g', linestyle='--', label='Strong Binding Threshold')
axes[1].legend()
for bar, aff in zip(bars2, gnina_data['Vina_Affinity']):
    axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{aff:.2f}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig('documentation/figures/Figure_Gnina_Results.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ Figure 4: Gnina docking results generated")

print("\n✅ All figures saved to documentation/figures/")
