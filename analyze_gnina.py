# -*- coding: utf-8 -*-
"""
Analyze Gnina CNN scoring results
CNN score (0-1) is a neural network prediction of binding probability
Higher CNN score = more likely to bind
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Gnina results from your run
results = {
    "CURE_17G_002": {
        "affinities": [-6.58, -6.14, -8.00, -7.21, -6.97, -5.83, -7.26, -6.69, -7.24],
        "cnn_scores": [0.5596, 0.5076, 0.4417, 0.4096, 0.3881, 0.3859, 0.3804, 0.3520, 0.3343]
    },
    "CURE_17G_003": {
        "affinities": [-6.65, -5.94, -5.57, -6.23, -5.57, -7.14, -5.46, -6.29, -6.87],
        "cnn_scores": [0.5668, 0.5313, 0.5229, 0.4943, 0.4776, 0.4534, 0.4515, 0.4471, 0.4432]
    },
    "CURE_17G_007": {
        "affinities": [-6.06, -5.54, -6.87, -6.56, -6.30, -8.01, -5.28, -5.24, -6.91],
        "cnn_scores": [0.5340, 0.4954, 0.4775, 0.4716, 0.4493, 0.4309, 0.4264, 0.4068, 0.4027]
    },
    "CURE_16G_007": {
        "affinities": [-7.13, -5.25, -4.27, -6.08, -5.62, -6.94, -5.39, -4.80, -6.77],
        "cnn_scores": [0.4795, 0.4771, 0.4749, 0.4743, 0.4683, 0.4653, 0.4649, 0.4639, 0.4602]
    },
    "CURE_13G_001": {
        "affinities": [-4.97, -4.85, -4.63, -4.56, -4.56, -4.54, -4.48, -4.48, -4.41],
        "cnn_scores": [0.6542, 0.6472, 0.6228, 0.6218, 0.6154, 0.6106, 0.6097, 0.6052, 0.6028]
    },
    "Q15_020": {
        "affinities": [-4.94, -4.91, -4.87, -4.71, -4.66, -4.60, -4.55, -4.53, -4.49],
        "cnn_scores": [0.4986, 0.4978, 0.4953, 0.4936, 0.4884, 0.4877, 0.4867, 0.4866, 0.4819]
    }
}

# Extract best pose for each compound
best_by_cnn = []
best_by_affinity = []

for compound, data in results.items():
    # Best by CNN score
    best_cnn_idx = np.argmax(data["cnn_scores"])
    best_by_cnn.append({
        "Compound": compound,
        "CNN Score": data["cnn_scores"][best_cnn_idx],
        "Vina Affinity": data["affinities"][best_cnn_idx],
        "Mode": best_cnn_idx + 1
    })
    
    # Best by Vina affinity (most negative = best binding)
    best_aff_idx = np.argmin(data["affinities"])
    best_by_affinity.append({
        "Compound": compound,
        "Vina Affinity": data["affinities"][best_aff_idx],
        "CNN Score": data["cnn_scores"][best_aff_idx],
        "Mode": best_aff_idx + 1
    })

# Create dataframes and sort
df_cnn = pd.DataFrame(best_by_cnn).sort_values("CNN Score", ascending=False)
df_aff = pd.DataFrame(best_by_affinity).sort_values("Vina Affinity", ascending=True)

print("=" * 80)
print("GNINA CNN SCORING ANALYSIS")
print("Higher CNN score = better predicted binding")
print("=" * 80)
print("\nRANKED BY CNN SCORE (Best to Worst):")
print("-" * 80)
print(f"{'Rank':<6} {'Compound':<15} {'CNN Score':<12} {'Vina Affinity':<15} {'Mode':<6}")
print("-" * 80)
for i, row in df_cnn.iterrows():
    print(f"{i+1:<6} {row['Compound']:<15} {row['CNN Score']:<12.4f} {row['Vina Affinity']:<15.2f} {row['Mode']:<6}")

print("\nRANKED BY VINA AFFINITY (Best to Worst):")
print("-" * 80)
print(f"{'Rank':<6} {'Compound':<15} {'Vina Affinity':<15} {'CNN Score':<12} {'Mode':<6}")
print("-" * 80)
for i, row in df_aff.iterrows():
    print(f"{i+1:<6} {row['Compound']:<15} {row['Vina Affinity']:<15.2f} {row['CNN Score']:<12.4f} {row['Mode']:<6}")

print("\n" + "=" * 80)
print("TOP PERFORMERS:")
print("=" * 80)
print(f"\nBest by CNN Score: {df_cnn.iloc[0]['Compound']}")
print(f"  CNN Score: {df_cnn.iloc[0]['CNN Score']:.4f}")
print(f"  Vina Affinity: {df_cnn.iloc[0]['Vina Affinity']:.2f} kcal/mol")

print(f"\nBest by Vina Affinity: {df_aff.iloc[0]['Compound']}")
print(f"  Vina Affinity: {df_aff.iloc[0]['Vina Affinity']:.2f} kcal/mol")
print(f"  CNN Score: {df_aff.iloc[0]['CNN Score']:.4f}")

# Create visualization
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Scatter plot: CNN Score vs Vina Affinity
compounds = list(results.keys())
cnn_scores = [df_cnn[df_cnn['Compound'] == c]['CNN Score'].values[0] for c in compounds]
vina_scores = [df_cnn[df_cnn['Compound'] == c]['Vina Affinity'].values[0] for c in compounds]

scatter = ax1.scatter(vina_scores, cnn_scores, s=100, c=range(len(compounds)), cmap='viridis')
for i, compound in enumerate(compounds):
    ax1.annotate(compound, (vina_scores[i], cnn_scores[i]), xytext=(5, 5), textcoords='offset points', fontsize=8)
ax1.set_xlabel('Vina Affinity (kcal/mol)', fontsize=10)
ax1.set_ylabel('CNN Score', fontsize=10)
ax1.set_title('CNN Score vs Vina Affinity\n(Best pose per compound)', fontsize=12)
ax1.grid(True, alpha=0.3)
ax1.axvline(x=-6, color='red', linestyle='--', alpha=0.5, label='Good binding threshold')
ax1.axhline(y=0.5, color='green', linestyle='--', alpha=0.5, label='High CNN score threshold')
ax1.legend()

# Bar plot: CNN Scores
colors = plt.cm.viridis(np.linspace(0, 1, len(compounds)))
ax2.bar(range(len(compounds)), cnn_scores, color=colors)
ax2.set_xticks(range(len(compounds)))
ax2.set_xticklabels(compounds, rotation=45, ha='right')
ax2.set_ylabel('CNN Score', fontsize=10)
ax2.set_title('CNN Scores by Compound', fontsize=12)
ax2.set_ylim([0, 1])
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('gnina_analysis.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved: gnina_analysis.png")

# Cross-validation: Combined scoring
print("\n" + "=" * 80)
print("CROSS-VALIDATION:")
print("=" * 80)

# Normalize scores for combined ranking
min_aff = df_aff['Vina Affinity'].min()
max_aff = df_aff['Vina Affinity'].max()
min_cnn = df_cnn['CNN Score'].min()
max_cnn = df_cnn['CNN Score'].max()

for compound in compounds:
    cnn_score = df_cnn[df_cnn['Compound'] == compound]['CNN Score'].values[0]
    vina_score = df_aff[df_aff['Compound'] == compound]['Vina Affinity'].values[0]
    
    # Normalize (CNN is already 0-1, Vina needs inversion since more negative is better)
    norm_vina = (vina_score - min_aff) / (max_aff - min_aff)
    # Invert so higher is better
    norm_vina = 1 - norm_vina
    norm_cnn = (cnn_score - min_cnn) / (max_cnn - min_cnn)
    
    combined = (norm_vina + norm_cnn) / 2
    
    print(f"{compound:<15} CNN: {cnn_score:.4f} | Vina: {vina_score:.2f} | Combined: {combined:.4f}")

best_combined = max([(compound, (df_cnn[df_cnn['Compound'] == compound]['CNN Score'].values[0] + 
                                 (1 - (df_aff[df_aff['Compound'] == compound]['Vina Affinity'].values[0] - min_aff) / (max_aff - min_aff))) / 2) 
                    for compound in compounds], key=lambda x: x[1])

print(f"\nBest Overall Candidate: {best_combined[0]}")
print(f"  Combined Score: {best_combined[1]:.4f}")

print("\n" + "=" * 80)
