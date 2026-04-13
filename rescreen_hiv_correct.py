# -*- coding: utf-8 -*-
import subprocess
import os
import json
from datetime import datetime

def dock_ligand(ligand_file, binding_site):
    cmd = [
        "./bin/vina.exe",
        "--receptor", "hiv_protease.pdbqt",
        "--ligand", ligand_file,
        "--center_x", str(binding_site[0]),
        "--center_y", str(binding_site[1]),
        "--center_z", str(binding_site[2]),
        "--size_x", "20",
        "--size_y", "20",
        "--size_z", "20",
        "--out", "temp_out.pdbqt",
        "--num_modes", "1",
        "--exhaustiveness", "12"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except:
                        continue
        return None
    except:
        return None

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*70)
print("HIV SCREENING - CORRECT BINDING SITE")
print("="*70)
print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")
print(f"Start: {datetime.now().strftime('%H:%M:%S')}")
print("-"*70)

# Get ligands
ligand_files = sorted([f for f in os.listdir("hiv_ligands") if f.endswith('.pdbqt')])
print(f"Found {len(ligand_files)} ligands\n")

results = []
results_file = "hiv_screening_correct.json"

# Resume if exists
if os.path.exists(results_file):
    with open(results_file, 'r') as f:
        results = json.load(f)
    print(f"Resuming: {len(results)} compounds done\n")
    start_idx = len(results)
else:
    start_idx = 0

# Screen
for i in range(start_idx, len(ligand_files)):
    ligand = ligand_files[i]
    ligand_path = os.path.join("hiv_ligands", ligand)
    
    print(f"{i+1:3d}. {ligand:<25} ", end="", flush=True)
    
    affinity = dock_ligand(ligand_path, binding_site)
    
    if affinity is not None:
        results.append({'ligand': ligand, 'affinity': affinity})
        print(f"{affinity:>6.2f} kcal/mol")
    else:
        print("FAILED")
    
    # Save progress
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    if (i + 1) % 10 == 0:
        print(f"  Progress: {len(results)}/100\n")

print("\n" + "="*70)
print("SCREENING COMPLETE!")
print(f"End: {datetime.now().strftime('%H:%M:%S')}")
print(f"Success: {len(results)}/{len(ligand_files)}")
print("="*70)

if results:
    results.sort(key=lambda x: x['affinity'])
    
    print("\nTOP 10 HITS:")
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
    print(f"Best affinity: {best:.2f} kcal/mol")
    print(f"Worst affinity: {worst:.2f} kcal/mol")
    print(f"Average affinity: {avg:.2f} kcal/mol")
    
    # Classification
    strong = [r for r in results if r['affinity'] < -7]
    moderate = [r for r in results if -7 <= r['affinity'] < -5]
    weak = [r for r in results if -5 <= r['affinity'] < -3]
    
    print("\nBINDING STRENGTH:")
    print("-"*60)
    print(f"Strong binders (< -7): {len(strong)}")
    print(f"Moderate binders (-7 to -5): {len(moderate)}")
    print(f"Weak binders (-5 to -3): {len(weak)}")
    
    # Save top hits
    with open("hiv_top_hits_correct.txt", "w") as f:
        f.write("Ligand\tAffinity\n")
        for r in results[:20]:
            f.write(f"{r['ligand']}\t{r['affinity']:.2f}\n")
    
    print("\nResults saved to: hiv_screening_correct.json")
    print("Top hits saved to: hiv_top_hits_correct.txt")
    
    if best < -7:
        print("\nSUCCESS! Found strong HIV drug candidates!")
        print(f"Best compound: {results[0]['ligand']} with {best:.2f} kcal/mol")
    elif best < -5:
        print("\nGood! Found moderate HIV drug candidates to optimize")
        print(f"Best compound: {results[0]['ligand']} with {best:.2f} kcal/mol")
    else:
        print("\nOnly weak binders found. Consider generating more diverse compounds")
