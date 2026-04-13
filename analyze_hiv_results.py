# -*- coding: utf-8 -*-
import json
import os

# Load results
if os.path.exists("hiv_screening_100.json"):
    with open("hiv_screening_100.json", 'r') as f:
        results = json.load(f)
else:
    print("No results found. Screening may still be running.")
    exit()

print("="*70)
print("HIV-1 PROTEASE SCREENING RESULTS")
print("="*70)

if not results:
    print("No successful docking results")
    exit()

# Sort by affinity
results.sort(key=lambda x: x['affinity'])

print(f"\nTotal compounds screened: {len(results)}")
print(f"Compounds with valid binding: {len(results)}")

print("\nTOP 10 BEST BINDERS:")
print("-"*60)
print(f"{'Rank':<6} {'Affinity (kcal/mol)':<20} {'Ligand'}")
print("-"*60)

for i, r in enumerate(results[:10], 1):
    print(f"{i:<6} {r['affinity']:<20.2f} {r['ligand']}")

# Statistics
affinities = [r['affinity'] for r in results]
best = min(affinities)
worst = max(affinities)
avg = sum(affinities) / len(affinities)

print("\nSTATISTICS:")
print("-"*60)
print(f"Best binding affinity: {best:.2f} kcal/mol")
print(f"Worst binding affinity: {worst:.2f} kcal/mol")
print(f"Average affinity: {avg:.2f} kcal/mol")

# Classification
strong = [r for r in results if r['affinity'] < -7]
moderate = [r for r in results if -7 <= r['affinity'] < -5]
weak = [r for r in results if -5 <= r['affinity'] < -3]
very_weak = [r for r in results if r['affinity'] >= -3]

print("\nBINDING STRENGTH DISTRIBUTION:")
print("-"*60)
print(f"Strong binders (< -7 kcal/mol): {len(strong)} compounds")
print(f"Moderate binders (-7 to -5): {len(moderate)} compounds")
print(f"Weak binders (-5 to -3): {len(weak)} compounds")
print(f"Very weak binders (> -3): {len(very_weak)} compounds")

# Best candidate analysis
if strong:
    best_candidate = strong[0]
    print("\nBEST CANDIDATE FOR HIV/AIDS:")
    print("-"*60)
    print(f"Ligand: {best_candidate['ligand']}")
    print(f"Binding affinity: {best_candidate['affinity']:.2f} kcal/mol")
    
    if best_candidate['affinity'] < -9:
        print("Classification: EXCELLENT - High affinity drug candidate")
        print("Recommendation: Proceed to in vitro testing")
    elif best_candidate['affinity'] < -7:
        print("Classification: STRONG - Promising lead compound")
        print("Recommendation: Optimize through medicinal chemistry")
    else:
        print("Classification: MODERATE - Needs optimization")
        print("Recommendation: Design analogs for improved binding")
else:
    print("\nNo strong binders found.")
    if moderate:
        print(f"Found {len(moderate)} moderate binders that could be optimized")
    else:
        print("Consider generating more diverse compounds or using known HIV scaffolds")

# Save top hits
with open("hiv_top_hits.txt", "w") as f:
    f.write("Ligand\tAffinity\n")
    for r in results[:20]:
        f.write(f"{r['ligand']}\t{r['affinity']:.2f}\n")

print("\nTop 20 hits saved to: hiv_top_hits.txt")
print("Full results saved to: hiv_screening_100.json")
print("="*70)

# Check if any compounds show promise
if best < -5:
    print("\nSUCCESS! Found promising HIV drug candidates!")
    print(f"Best compound binds with {best:.2f} kcal/mol")
    print("Consider further optimization and testing")
else:
    print("\nNo strong binders found. Consider:")
    print("1. Generating more diverse compounds")
    print("2. Using known HIV drug scaffolds")
    print("3. Increasing exhaustiveness in docking")
