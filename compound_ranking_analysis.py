#!/usr/bin/env python3
"""
Comprehensive Compound Ranking Analysis
Combines Gnina docking results with MD simulation insights
Identifies the strongest candidate for experimental validation
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import os

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.size'] = 11

print("="*70)
print("COMPREHENSIVE COMPOUND RANKING ANALYSIS")
print("="*70)

# ============================================================================
# 1. Load Gnina Docking Results
# ============================================================================
gnina_data = {
    'Compound': ['CURE_13G_001', 'CURE_17G_003', 'CURE_17G_002', 
                 'CURE_17G_007', 'Q15_020', 'CURE_16G_007'],
    'CNN_Score': [0.6542, 0.5668, 0.5596, 0.5340, 0.4986, 0.4795],
    'Vina_Affinity': [-4.97, -6.65, -6.58, -6.06, -4.94, -7.13],
    'Mode': [1, 1, 1, 1, 1, 1]  # Best pose from Gnina
}

df = pd.DataFrame(gnina_data)

print("\ní³Š GNINA DOCKING RESULTS:")
print(df.to_string(index=False))

# ============================================================================
# 2. Normalize and Score Each Compound
# ============================================================================
# Normalize CNN Score (0-1 scale, higher is better)
df['CNN_Norm'] = (df['CNN_Score'] - df['CNN_Score'].min()) / (df['CNN_Score'].max() - df['CNN_Score'].min())

# Normalize Vina Affinity (0-1 scale, more negative is better - invert so higher is better)
df['Vina_Norm'] = (df['Vina_Affinity'].max() - df['Vina_Affinity']) / (df['Vina_Affinity'].max() - df['Vina_Affinity'].min())

# Calculate combined score (50% CNN, 50% Vina)
df['Combined_Score'] = (df['CNN_Norm'] + df['Vina_Norm']) / 2

# Add ranking
df['Rank'] = df['Combined_Score'].rank(ascending=False).astype(int)

# Sort by combined score
df_sorted = df.sort_values('Combined_Score', ascending=False).reset_index(drop=True)

print("\ní¾¯ RANKING BY COMBINED SCORE (CNN + Vina):")
print("="*70)
print(df_sorted[['Rank', 'Compound', 'CNN_Score', 'Vina_Affinity', 'CNN_Norm', 'Vina_Norm', 'Combined_Score']].to_string(index=False))
print("="*70)

# ============================================================================
# 3. MD Simulation Insights
# ============================================================================
print("\ní´¬ MD SIMULATION INSIGHTS:")
print("-"*50)
print("The 1 ns MD simulation validated the target protein stability:")
print("  â€¢ RMSD: 0.136 Â± 0.021 nm (EXCELLENT - protein is stable)")
print("  â€¢ Temperature: 300.1 Â± 0.5 K (perfect)")
print("  â€¢ Pressure: 1.3 Â± 0.5 bar (equilibrated)")
print("  â€¢ Flap region (residues 43-58) is flexible and accessible")
print("\nThis confirms the protein is ready for reliable docking predictions.")

# ============================================================================
# 4. Compound Profile Summary
# ============================================================================
print("\ní³‹ COMPOUND PROFILES:")
print("="*70)

top_compounds = df_sorted.head(3)

for idx, row in top_compounds.iterrows():
    print(f"\ní¿† #{row['Rank']}: {row['Compound']}")
    print(f"   â”œâ”€ CNN Score: {row['CNN_Score']:.4f} ({row['CNN_Norm']*100:.1f}% normalized)")
    print(f"   â”œâ”€ Vina Affinity: {row['Vina_Affinity']:.2f} kcal/mol ({row['Vina_Norm']*100:.1f}% normalized)")
    print(f"   â””â”€ Combined Score: {row['Combined_Score']:.4f}")

# ============================================================================
# 5. Recommendation
# ============================================================================
print("\n" + "="*70)
print("í¿† RECOMMENDATION: STRONGEST COMPOUND")
print("="*70)

best = df_sorted.iloc[0]
second = df_sorted.iloc[1]
third = df_sorted.iloc[2]

print(f"\nâœ… PRIMARY CANDIDATE: {best['Compound']}")
print(f"   â€¢ Highest combined score: {best['Combined_Score']:.4f}")
print(f"   â€¢ CNN Score: {best['CNN_Score']:.4f} (excellent binding probability)")
print(f"   â€¢ Vina Affinity: {best['Vina_Affinity']:.2f} kcal/mol (strong binding)")
print(f"\n   Why this compound?")
print(f"   â€¢ Balances both binding probability and affinity")
print(f"   â€¢ Shows robust performance across both metrics")
print(f"   â€¢ Ideal lead for experimental validation")

print(f"\ní³Œ SECONDARY CANDIDATE: {second['Compound']}")
print(f"   â€¢ Combined score: {second['Combined_Score']:.4f}")
print(f"   â€¢ Strong Vina affinity: {second['Vina_Affinity']:.2f} kcal/mol")

print(f"\ní³Œ TERTIARY CANDIDATE: {third['Compound']}")
print(f"   â€¢ Combined score: {third['Combined_Score']:.4f}")
print(f"   â€¢ High CNN confidence: {third['CNN_Score']:.4f}")

# ============================================================================
# 6. Create Visualization
# ============================================================================
print("\ní³Š GENERATING VISUALIZATIONS...")

fig, axes = plt.subplots(2, 2, figsize=(14, 12))
fig.suptitle('Compound Ranking Analysis - HIV Protease Inhibitors', fontsize=16, fontweight='bold')

# 1. Bar chart - CNN Scores
ax1 = axes[0,0]
bars1 = ax1.bar(df_sorted['Compound'], df_sorted['CNN_Score'], color='steelblue', alpha=0.8)
ax1.set_ylabel('CNN Score (Binding Probability)', fontsize=12)
ax1.set_title('CNN Score Ranking', fontsize=12, fontweight='bold')
ax1.tick_params(axis='x', rotation=45)
ax1.axhline(y=0.5, color='red', linestyle='--', label='High Confidence (0.5)')
ax1.legend()
for bar, val in zip(bars1, df_sorted['CNN_Score']):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{val:.3f}', ha='center', va='bottom', fontsize=9)

# 2. Bar chart - Vina Affinity
ax2 = axes[0,1]
colors = ['coral' if x < -6 else 'lightcoral' for x in df_sorted['Vina_Affinity']]
bars2 = ax2.bar(df_sorted['Compound'], df_sorted['Vina_Affinity'], color=colors, alpha=0.8)
ax2.set_ylabel('Vina Affinity (kcal/mol)', fontsize=12)
ax2.set_title('Vina Affinity Ranking', fontsize=12, fontweight='bold')
ax2.tick_params(axis='x', rotation=45)
ax2.axhline(y=-6, color='green', linestyle='--', label='Strong Binding (< -6)')
ax2.legend()
for bar, val in zip(bars2, df_sorted['Vina_Affinity']):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
             f'{val:.2f}', ha='center', va='bottom', fontsize=9)

# 3. Combined Score
ax3 = axes[1,0]
bars3 = ax3.bar(df_sorted['Compound'], df_sorted['Combined_Score'], 
                color='darkgreen', alpha=0.8)
ax3.set_ylabel('Combined Score', fontsize=12)
ax3.set_title('Combined Ranking Score (CNN + Vina)', fontsize=12, fontweight='bold')
ax3.tick_params(axis='x', rotation=45)
for bar, val in zip(bars3, df_sorted['Combined_Score']):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{val:.3f}', ha='center', va='bottom', fontsize=9)

# 4. Normalized Comparison
ax4 = axes[1,1]
x = np.arange(len(df_sorted))
width = 0.35
ax4.bar(x - width/2, df_sorted['CNN_Norm'], width, label='CNN Score', color='steelblue', alpha=0.8)
ax4.bar(x + width/2, df_sorted['Vina_Norm'], width, label='Vina Affinity', color='coral', alpha=0.8)
ax4.set_xticks(x)
ax4.set_xticklabels(df_sorted['Compound'], rotation=45, ha='right')
ax4.set_ylabel('Normalized Score (0-1)', fontsize=12)
ax4.set_title('Normalized Comparison', fontsize=12, fontweight='bold')
ax4.legend()
ax4.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('compound_ranking_analysis.png', dpi=300, bbox_inches='tight')
plt.close()
print("   âœ“ Saved: compound_ranking_analysis.png")

# Create a summary table
print("\ní³Š GENERATING SUMMARY TABLE...")

summary = df_sorted[['Rank', 'Compound', 'CNN_Score', 'Vina_Affinity', 'Combined_Score']].copy()
summary['CNN_Norm'] = df_sorted['CNN_Norm'].map(lambda x: f"{x:.3f}")
summary['Vina_Norm'] = df_sorted['Vina_Norm'].map(lambda x: f"{x:.3f}")
summary['Combined_Score'] = summary['Combined_Score'].map(lambda x: f"{x:.4f}")

print("\n" + "="*70)
print("FINAL RANKING TABLE")
print("="*70)
print(summary.to_string(index=False))

# ============================================================================
# 7. Export Results
# ============================================================================
print("\ní²¾ EXPORTING RESULTS...")

# Save to CSV
df_sorted.to_csv('compound_ranking.csv', index=False)
print("   âœ“ Saved: compound_ranking.csv")

# Create a text report
with open('compound_ranking_report.txt', 'w') as f:
    f.write("="*70 + "\n")
    f.write("COMPREHENSIVE COMPOUND RANKING REPORT\n")
    f.write("HIV Protease Inhibitor Candidates\n")
    f.write("="*70 + "\n\n")
    
    f.write("GNINA DOCKING RESULTS:\n")
    f.write("-"*50 + "\n")
    for idx, row in df_sorted.iterrows():
        f.write(f"{row['Rank']}. {row['Compound']}: CNN={row['CNN_Score']:.4f}, Vina={row['Vina_Affinity']:.2f} kcal/mol\n")
    
    f.write("\nMD SIMULATION VALIDATION:\n")
    f.write("-"*50 + "\n")
    f.write("âœ“ Protein RMSD: 0.136 Â± 0.021 nm (excellent stability)\n")
    f.write("âœ“ Temperature: 300.1 Â± 0.5 K\n")
    f.write("âœ“ Pressure: 1.3 Â± 0.5 bar\n")
    f.write("âœ“ System well-equilibrated for docking\n\n")
    
    f.write("RECOMMENDATION:\n")
    f.write("-"*50 + "\n")
    f.write(f"PRIMARY CANDIDATE: {best['Compound']}\n")
    f.write(f"  - Combined Score: {best['Combined_Score']:.4f}\n")
    f.write(f"  - CNN: {best['CNN_Score']:.4f} | Vina: {best['Vina_Affinity']:.2f} kcal/mol\n\n")
    f.write(f"SECONDARY CANDIDATE: {second['Compound']}\n")
    f.write(f"  - Combined Score: {second['Combined_Score']:.4f}\n")
    f.write(f"  - CNN: {second['CNN_Score']:.4f} | Vina: {second['Vina_Affinity']:.2f} kcal/mol\n\n")
    f.write(f"TERTIARY CANDIDATE: {third['Compound']}\n")
    f.write(f"  - Combined Score: {third['Combined_Score']:.4f}\n")
    f.write(f"  - CNN: {third['CNN_Score']:.4f} | Vina: {third['Vina_Affinity']:.2f} kcal/mol\n")
    
    f.write("\n" + "="*70 + "\n")
    f.write("Generated: March 27, 2026\n")
    f.write("="*70 + "\n")

print("   âœ“ Saved: compound_ranking_report.txt")

print("\n" + "="*70)
print("âœ… ANALYSIS COMPLETE!")
print("="*70)
print(f"\ní¿† STRONGEST COMPOUND: {best['Compound']}")
print(f"   Combined Score: {best['Combined_Score']:.4f}")
print(f"   CNN: {best['CNN_Score']:.4f} | Vina: {best['Vina_Affinity']:.2f} kcal/mol")
print("\nFiles created:")
print("  í³Š compound_ranking_analysis.png - Visualization")
print("  í³„ compound_ranking.csv - Data table")
print("  í³ compound_ranking_report.txt - Full report")
print("\n" + "="*70)

