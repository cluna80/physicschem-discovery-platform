# -*- coding: utf-8 -*-
import subprocess
import os
import json
import re

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
        
        # Look for the affinity value in the output
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            # Look for the line with mode and affinity table
            if 'mode' in line.lower() and 'affinity' in line.lower():
                # Next line after the separator should have the data
                for j in range(i+1, min(i+10, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not next_line.startswith('----'):
                        parts = next_line.split()
                        if len(parts) >= 2 and parts[0].isdigit():
                            try:
                                affinity = float(parts[1])
                                return affinity
                            except:
                                continue
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*70)
print("HIV SCREENING - CORRECT BINDING SITE")
print("="*70)
print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")
print("-"*70)

# Get ligands
ligand_files = sorted([f for f in os.listdir("hiv_ligands") if f.endswith('.pdbqt')])
print(f"Found {len(ligand_files)} ligands\n")

results = []
results_file = "hiv_screening_fixed.json"

# Resume if exists
if os.path.exists(results_file):
    with open(results_file, 'r') as f:
        results = json.load(f)
    print(f"Resuming: {len(results)} compounds done\n")
    start_idx = len(results)
else:
    start_idx = 0

# Test first ligand to verify parsing
if start_idx == 0:
    print("Testing parsing with ligand_001...")
    test_ligand = "hiv_ligands/ligand_001.pdbqt"
    test_aff = dock_ligand(test_ligand, binding_site)
    print(f"Test affinity: {test_aff} kcal/mol\n")

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
    
    # Save after each compound
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    if (i + 1) % 10 == 0:
        print(f"  Progress: {len(results)}/100\n")

print("\n" + "="*70)
print("SCREENING COMPLETE!")
print(f"Success: {len(results)}/{len(ligand_files)}")
print("="*70)

if results:
    results.sort(key=lambda x: x['affinity'])
    
    print("\nTOP 10 HITS:")
    print("-"*60)
    for i, r in enumerate(results[:10], 1):
        print(f"{i:2d}. {r['affinity']:6.2f} kcal/mol  {r['ligand']}")
    
    # Statistics
    affinities = [r['affinity'] for r in results]
    best = min(affinities)
    worst = max(affinities)
    avg = sum(affinities) / len(affinities)
    
    print("\nSTATISTICS:")
    print(f"Best: {best:.2f} kcal/mol")
    print(f"Worst: {worst:.2f} kcal/mol")
    print(f"Average: {avg:.2f} kcal/mol")
    
    # Classification
    strong = sum(1 for a in affinities if a < -7)
    moderate = sum(1 for a in affinities if -7 <= a < -5)
    weak = sum(1 for a in affinities if -5 <= a < -3)
    
    print(f"\nStrong binders (< -7): {strong}")
    print(f"Moderate binders (-7 to -5): {moderate}")
    print(f"Weak binders (-5 to -3): {weak}")
    
    # Save top hits
    with open("hiv_top_hits_fixed.txt", "w") as f:
        for r in results[:20]:
            f.write(f"{r['ligand']}\t{r['affinity']:.2f}\n")
    
    print(f"\nResults saved to: {results_file}")
    
    if best < -7:
        print(f"\nSUCCESS! Best candidate: {results[0]['ligand']} with {best:.2f} kcal/mol")
    elif best < -5:
        print(f"\nGood candidate: {results[0]['ligand']} with {best:.2f} kcal/mol")
    else:
        print(f"\nBest so far: {best:.2f} kcal/mol - need stronger binders")
