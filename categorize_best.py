# -*- coding: utf-8 -*-
"""
Categorize and rank all best compounds from the optimization campaign
Creates a leaderboard of top HIV drug candidates
"""

import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# ============================================================
# COLLECT ALL YOUR BEST RESULTS
# ============================================================

# Results from your optimization campaign (update with actual values)
BEST_COMPOUNDS = [
    # Generation 4-6: Early optimization
    {"name": "CURE_4G_003", "affinity": -5.365, "generation": 4, 
     "features": "Trifluorophenyl + amide + hydroxyethylamine", "class": "Early Lead"},
    {"name": "CURE_5G_002", "affinity": -6.122, "generation": 5, 
     "features": "Naphthalene + THF", "class": "Optimized Lead"},
    {"name": "CURE_6G_002", "affinity": -6.772, "generation": 6, 
     "features": "Naphthalene + THF (optimized)", "class": "Strong Lead"},
    
    # Generation 7-8: P2 optimization
    {"name": "CURE_7G_007", "affinity": -5.183, "generation": 7, 
     "features": "Naphthalene + THP ring", "class": "THP Test"},
    {"name": "CURE_8G_001", "affinity": -5.335, "generation": 8, 
     "features": "Hydroxynaphthalene + THP", "class": "Hydroxy Test"},
    
    # Generation 9-10: bis-THF breakthrough
    {"name": "CURE_9G_008", "affinity": -6.207, "generation": 9, 
     "features": "Chiral THF", "class": "Stereochemistry"},
    {"name": "CURE_10G_007", "affinity": -6.861, "generation": 10, 
     "features": "Naphthalene + bis-THF", "class": "Bis-THF Breakthrough"},
    
    # Generation 11-12: P1 optimization
    {"name": "CURE_11G_007", "affinity": -7.265, "generation": 11, 
     "features": "meta-Fluorobenzyl P1 + bis-THF", "class": "P1 Optimized"},
    {"name": "CURE_12G_001", "affinity": -7.290, "generation": 12, 
     "features": "Chiral OH + meta-F + bis-THF", "class": "Top Candidate"},
    
    # Generation 13: P2' exploration
    {"name": "CURE_13G_002", "affinity": -7.034, "generation": 13, 
     "features": "Isoquinoline + R-OH + meta-F + bis-THF", "class": "Heteroaromatic"},
    
    # Final designs
    {"name": "CURE_FINAL", "affinity": None, "generation": 15, 
     "features": "P2' sulfonamide + N-methyl + meta-F + bis-THF", 
     "class": "Ultimate Design", "pending": True},
]

# Add ChEMBL benchmarks for comparison
CHEMBL_BENCHMARKS = [
    {"name": "Darunavir", "affinity": -8.8, "source": "ChEMBL", "ic50": 0.4},
    {"name": "Saquinavir", "affinity": -8.5, "source": "ChEMBL", "ic50": 0.6},
    {"name": "Ritonavir", "affinity": -8.2, "source": "ChEMBL", "ic50": 1.0},
]

print("="*80)
print("CURE OPTIMIZATION CAMPAIGN - LEADERBOARD")
print("="*80)

# Create DataFrame
df = pd.DataFrame([c for c in BEST_COMPOUNDS if c.get('affinity') is not None])
df_bench = pd.DataFrame(CHEMBL_BENCHMARKS)

# Sort by affinity
df = df.sort_values('affinity', ascending=False)
df_bench = df_bench.sort_values('affinity', ascending=False)

print("\nTOP 10 CANDIDATES (Best to Worst):")
print("-"*90)
print(f"{'Rank':<5} {'Compound':<15} {'Affinity':<12} {'Generation':<10} {'Features':<45}")
print("-"*90)

for i, row in df.head(10).iterrows():
    print(f"{i+1:<5} {row['name']:<15} {row['affinity']:<12.3f} {row['generation']:<10} {row['features'][:43]:<45}")

print("\n" + "="*80)
print("COMPARISON WITH FDA-APPROVED HIV DRUGS (ChEMBL)")
print("="*80)
print(f"{'Drug':<15} {'Affinity (kcal/mol)':<20} {'IC50 (nM)':<12} {'Status'}")
print("-"*60)
for _, row in df_bench.iterrows():
    print(f"{row['name']:<15} {row['affinity']:<20.1f} {row['ic50']:<12.1f} Approved")

print("\n" + "="*80)
print("PROGRESS SUMMARY")
print("="*80)

# Calculate improvements
first = df.iloc[-1]['affinity'] if len(df) > 0 else -5.365
best = df.iloc[0]['affinity'] if len(df) > 0 else -7.290
improvement = best - first

print(f"Starting point (CURE_4G_003): {first:.3f} kcal/mol")
print(f"Current best (CURE_12G_001): {best:.3f} kcal/mol")
print(f"Total improvement: {improvement:+.2f} kcal/mol")
print(f"Gap to Darunavir: {best - (-8.8):.2f} kcal/mol")

# Classify candidates
strong = df[df['affinity'] < -7]
moderate = df[(df['affinity'] >= -7) & (df['affinity'] < -6)]
weak = df[df['affinity'] >= -6]

print(f"\nCLASSIFICATION:")
print(f"  Strong binders (< -7): {len(strong)} compounds")
print(f"  Moderate binders (-7 to -6): {len(moderate)} compounds")
print(f"  Weak binders (> -6): {len(weak)} compounds")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)

# Get top 3 candidates
top3 = df.head(3)
print("\nTop 3 Candidates for Further Development:")
for i, row in top3.iterrows():
    print(f"\n{i+1}. {row['name']} ({row['affinity']:.3f} kcal/mol)")
    print(f"   Features: {row['features']}")
    print(f"   Generation: {row['generation']}")
    
    if row['affinity'] < -8:
        print("   → DRUG CANDIDATE! Proceed to in vitro testing")
    elif row['affinity'] < -7.5:
        print("   → Excellent! Synthesize and test")
    elif row['affinity'] < -7:
        print("   → Strong lead - optimize further")
    else:
        print("   → Needs optimization")

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Optimization progress
ax1 = axes[0, 0]
generations = df.sort_values('generation')['generation'].values
affinities = df.sort_values('generation')['affinity'].values
ax1.plot(generations, affinities, 'o-', linewidth=2, markersize=8, color='blue')
ax1.axhline(y=-8.8, color='red', linestyle='--', linewidth=2, label='Darunavir')
ax1.set_xlabel('Generation')
ax1.set_ylabel('Binding Affinity (kcal/mol)')
ax1.set_title('Optimization Progress')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 2. Affinity distribution
ax2 = axes[0, 1]
ax2.hist(affinities, bins=10, edgecolor='black', alpha=0.7, color='green')
ax2.axvline(x=-8.8, color='red', linestyle='--', linewidth=2, label='Darunavir')
ax2.set_xlabel('Binding Affinity (kcal/mol)')
ax2.set_ylabel('Number of Compounds')
ax2.set_title('Affinity Distribution')
ax2.legend()

# 3. Top 10 bar chart
ax3 = axes[1, 0]
top10 = df.head(10)
colors = ['red' if i < 3 else 'blue' for i in range(len(top10))]
bars = ax3.barh(range(len(top10)), top10['affinity'].values, color=colors)
ax3.set_yticks(range(len(top10)))
ax3.set_yticklabels(top10['name'].values)
ax3.set_xlabel('Binding Affinity (kcal/mol)')
ax3.set_title('Top 10 Candidates')
ax3.axvline(x=-8.8, color='red', linestyle='--', linewidth=2, label='Darunavir')
ax3.legend()

# 4. Generation comparison
ax4 = axes[1, 1]
gen_avg = df.groupby('generation')['affinity'].mean()
ax4.bar(gen_avg.index, gen_avg.values, color='purple', alpha=0.7)
ax4.axhline(y=-8.8, color='red', linestyle='--', linewidth=2, label='Darunavir')
ax4.set_xlabel('Generation')
ax4.set_ylabel('Average Affinity (kcal/mol)')
ax4.set_title('Average Affinity by Generation')
ax4.legend()

plt.tight_layout()
plt.savefig('cure_leaderboard.png', dpi=150, bbox_inches='tight')
plt.show()

print("\nPlot saved: cure_leaderboard.png")
print("="*80)

# Save top candidates
with open("cure_top_candidates.json", "w") as f:
    json.dump(df.head(10).to_dict('records'), f, indent=2)

print("\nSaved: cure_top_candidates.json")
print("="*80)
