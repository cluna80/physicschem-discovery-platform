# -*- coding: utf-8 -*-
import subprocess
import os
import json
import time

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
        
        # Parse affinity from output
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
    except Exception as e:
        return None

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*70)
print("HIV SCREENING - 100 COMPOUNDS")
print("="*70)
print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")
print("-"*70)

# Get all ligands
ligand_files = sorted([f for f in os.listdir("hiv_ligands") if f.endswith('.pdbqt')])
print(f"Found {len(ligand_files)} ligands to screen\n")

results = []
results_file = "hiv_screening_100.json"

# Check for existing results
if os.path.exists(results_file):
    with open(results_file, 'r') as f:
        results = json.load(f)
    print(f"Resuming from previous: {len(results)} compounds done\n")
    start_idx = len(results)
else:
    start_idx = 0

# Screen compounds
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
    
    # Save after each compound
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    if (i + 1) % 10 == 0:
        print(f"  -> Progress saved: {len(results)}/100\n")

print("\n" + "="*70)
print("SCREENING COMPLETE!")
print(f"Successfully docked: {len(results)}/{len(ligand_files)}")
print("="*70)

if results:
    results.sort(key=lambda x: x['affinity'])
    print("\nTOP 10 HITS:")
    print("-"*50)
    for i, r in enumerate(results[:10], 1):
        print(f"{i:2d}. {r['affinity']:6.2f} kcal/mol  {r['ligand']}")
    
    # Statistics
    affinities = [r['affinity'] for r in results]
    print(f"\nBest: {min(affinities):.2f} kcal/mol")
    print(f"Average: {sum(affinities)/len(affinities):.2f} kcal/mol")
    
    strong = sum(1 for a in affinities if a < -7)
    print(f"Strong binders (< -7): {strong}")
    
    # Save top 20
    with open("hiv_top_hits.txt", "w") as f:
        f.write("Ligand\tAffinity\n")
        for r in results[:20]:
            f.write(f"{r['ligand']}\t{r['affinity']:.2f}\n")
    
    print("\nResults saved to: hiv_screening_100.json")
    print("Top hits saved to: hiv_top_hits.txt")
