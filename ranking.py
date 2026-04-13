import matplotlib.pyplot as plt
import numpy as np

print("="*70)
print("CURE COMPOUNDS RANKING - HIV PROTEASE INHIBITORS")
print("="*70)

# Data from gnina_results.csv
compounds = ['CURE_17G_002', 'CURE_17G_003', 'CURE_17G_007', 'CURE_16G_007', 'Q15_020', 'CURE_13G_001']
vina = [-7.753, -7.549, -7.522, -7.487, -7.398, -7.333]
cnn = [0.4417, 0.4534, 0.4309, 0.4795, 0.4986, 0.6542]

print("\nRANKING BY VINA AFFINITY (Strongest to Weakest):")
print("-" * 55)
print(f"{'Rank':<4} {'Compound':<15} {'Vina (kcal/mol)':<15} {'CNN Score':<12}")
print("-" * 55)
for i in range(len(compounds)):
    print(f"{i+1:<4} {compounds[i]:<15} {vina[i]:<15.3f} {cnn[i]:<12.4f}")

# Find strongest
strongest_idx = np.argmin(vina)
highest_cnn_idx = np.argmax(cnn)

print("\n" + "="*70)
print("SUMMARY:")
print("="*70)
print(f"\nSTRONGEST BINDER: {compounds[strongest_idx]}")
print(f"   Vina Affinity: {vina[strongest_idx]:.3f} kcal/mol")
print(f"   CNN Score: {cnn[strongest_idx]:.4f}")

print(f"\nHIGHEST CONFIDENCE: {compounds[highest_cnn_idx]}")
print(f"   CNN Score: {cnn[highest_cnn_idx]:.4f}")
print(f"   Vina Affinity: {vina[highest_cnn_idx]:.3f} kcal/mol")

# Normalize and get combined score
min_v = min(vina)
max_v = max(vina)
min_c = min(cnn)
max_c = max(cnn)

combined = []
for i in range(len(compounds)):
    v_norm = (max_v - vina[i]) / (max_v - min_v)
    c_norm = (cnn[i] - min_c) / (max_c - min_c)
    combined.append((v_norm + c_norm) / 2)

# Sort by combined
combined_pairs = list(zip(compounds, vina, cnn, combined))
combined_pairs.sort(key=lambda x: x[3], reverse=True)

print("\n" + "="*70)
print("RANKING BY COMBINED SCORE (Vina + CNN):")
print("="*70)
print(f"{'Rank':<4} {'Compound':<15} {'Vina':<10} {'CNN':<10} {'Combined':<10}")
print("-" * 55)
for i, (comp, v, c, comb) in enumerate(combined_pairs, 1):
    print(f"{i:<4} {comp:<15} {v:<10.3f} {c:<10.4f} {comb:<10.4f}")

best_combined = combined_pairs[0]
print(f"\nBEST BALANCED CANDIDATE: {best_combined[0]}")
print(f"   Combined Score: {best_combined[3]:.4f}")
print(f"   Vina: {best_combined[1]:.3f} kcal/mol | CNN: {best_combined[2]:.4f}")

# Create plot
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Vina affinity plot
ax1 = axes[0]
colors = ['darkred' if x < -7.5 else 'coral' for x in vina]
bars = ax1.bar(compounds, vina, color=colors)
ax1.set_ylabel('Vina Affinity (kcal/mol)')
ax1.set_title('Vina Affinity Ranking')
ax1.tick_params(axis='x', rotation=45)
ax1.axhline(y=-7.5, color='green', linestyle='--', label='-7.5 threshold')
ax1.legend()
for bar, val in zip(bars, vina):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{val:.3f}', ha='center', va='bottom', fontsize=9)

# Combined score plot
ax2 = axes[1]
comp_sorted = [x[0] for x in combined_pairs]
comb_sorted = [x[3] for x in combined_pairs]
bars2 = ax2.bar(comp_sorted, comb_sorted, color='darkgreen')
ax2.set_ylabel('Combined Score')
ax2.set_title('Combined Ranking (Vina + CNN)')
ax2.tick_params(axis='x', rotation=45)
for bar, val in zip(bars2, comb_sorted):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
             f'{val:.3f}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig('cure_ranking.png', dpi=300, bbox_inches='tight')
plt.close()
print("\n✅ Plot saved: cure_ranking.png")

# Save report
with open('cure_ranking.txt', 'w') as f:
    f.write("="*70 + "\n")
    f.write("CURE COMPOUNDS RANKING - HIV PROTEASE INHIBITORS\n")
    f.write("="*70 + "\n\n")
    f.write("RANKING BY VINA AFFINITY:\n")
    f.write("-"*50 + "\n")
    for i in range(len(compounds)):
        f.write(f"{i+1}. {compounds[i]}: {vina[i]:.3f} kcal/mol (CNN: {cnn[i]:.4f})\n")
    f.write("\nRANKING BY COMBINED SCORE:\n")
    f.write("-"*50 + "\n")
    for i, (comp, v, c, comb) in enumerate(combined_pairs, 1):
        f.write(f"{i}. {comp}: Combined={comb:.4f} (Vina={v:.3f}, CNN={c:.4f})\n")
    f.write("\n" + "="*70 + "\n")
    f.write("RECOMMENDATION:\n")
    f.write("="*70 + "\n")
    f.write(f"STRONGEST BINDER: {compounds[strongest_idx]} ({vina[strongest_idx]:.3f} kcal/mol)\n")
    f.write(f"BEST BALANCED: {best_combined[0]} (Combined={best_combined[3]:.4f})\n")
    f.write(f"HIGHEST CONFIDENCE: {compounds[highest_cnn_idx]} (CNN={cnn[highest_cnn_idx]:.4f})\n")

print("✅ Report saved: cure_ranking.txt")

