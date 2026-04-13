#!/usr/bin/env python3
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle

print("Creating comparison figure...")

fig, axes = plt.subplots(1, 2, figsize=(16, 8))
fig.suptitle('CURE_17G_002 vs opt5_v2_7: 30% Improvement in Binding Affinity', 
             fontsize=16, fontweight='bold')

# Left: Original
ax1 = axes[0]
ax1.set_xlim(0, 10)
ax1.set_ylim(0, 10)
ax1.axis('off')
ax1.add_patch(Rectangle((0.5, 0.5), 9, 9, fill=False, edgecolor='black', linewidth=2))
ax1.text(5, 9, 'CURE_17G_002', ha='center', fontsize=14, fontweight='bold', color='darkorange')
ax1.text(5, 8.2, 'Original Lead Compound', ha='center', fontsize=11, style='italic')
ax1.text(5, 5, '3,5-diF\nbis-THF\nS-OH', ha='center', va='center', fontsize=12, family='monospace')
ax1.add_patch(Rectangle((2, 1), 6, 1.5, facecolor='darkorange', alpha=0.3, edgecolor='darkorange'))
ax1.text(5, 1.75, 'Binding Affinity:', ha='center', fontsize=10, fontweight='bold')
ax1.text(5, 1.25, '-7.753 kcal/mol', ha='center', fontsize=16, fontweight='bold', color='darkorange')

# Right: Optimized
ax2 = axes[1]
ax2.set_xlim(0, 10)
ax2.set_ylim(0, 10)
ax2.axis('off')
ax2.add_patch(Rectangle((0.5, 0.5), 9, 9, fill=False, edgecolor='green', linewidth=3))
ax2.text(5, 9, 'opt5_v2_7', ha='center', fontsize=14, fontweight='bold', color='green')
ax2.text(5, 8.2, 'Optimized Compound (v2)', ha='center', fontsize=11, style='italic')
ax2.text(5, 5, '3,5-diF + 4-CF3\nCH3 + F on isoquinoline\nReverse amide + Spiro-THF', 
         ha='center', va='center', fontsize=10, family='monospace')
ax2.add_patch(Rectangle((2, 1), 6, 1.5, facecolor='green', alpha=0.3, edgecolor='green'))
ax2.text(5, 1.75, 'Binding Affinity:', ha='center', fontsize=10, fontweight='bold')
ax2.text(5, 1.25, '-10.103 kcal/mol', ha='center', fontsize=16, fontweight='bold', color='green')

plt.tight_layout()
plt.savefig('original_vs_optimized_comparison.png', dpi=300, bbox_inches='tight')
plt.close()
print("✅ Created: original_vs_optimized_comparison.png")

# Bar chart
fig2, ax = plt.subplots(figsize=(10, 6))
compounds = ['CURE_17G_002', 'opt5_v2_7']
affinities = [-7.753, -10.103]
colors = ['#FF9800', '#4CAF50']
bars = ax.bar(compounds, [-a for a in affinities], color=colors)
ax.set_ylabel('|Affinity| (kcal/mol)')
ax.set_title('Optimization Result: 30% Improvement', fontsize=14, fontweight='bold')
for bar, val in zip(bars, affinities):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
            f'{val:.3f}', ha='center', va='bottom', fontsize=12, fontweight='bold')
plt.tight_layout()
plt.savefig('optimization_result.png', dpi=150, bbox_inches='tight')
plt.close()
print("✅ Created: optimization_result.png")

print("\n🏆 opt5_v2_7: -10.103 kcal/mol (30% improvement!)")
