# -*- coding: utf-8 -*-
import subprocess
import os
import json
from datetime import datetime

def dock_ligand(ligand_file, binding_site):
    try:
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
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        for line in result.stdout.split('\n'):
            if line.strip() and line.strip()[0].isdigit():
                parts = line.strip().split()
                if len(parts) >= 2:
                    return float(parts[1])
        return None
    except:
        return None

with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*70)
print("SCREENING 100 COMPOUNDS AGAINST HIV-1 PROTEASE")
print("="*70)
print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")
print(f"Start: {datetime.now().strftime('%H:%M:%S')}")
print("-"*70)

ligand_files = sorted([f for f in os.listdir("hiv_ligands") if f.endswith('.pdbqt')])
print(f"Found {len(ligand_files)} ligands\n")

results = []
for i, ligand in enumerate(ligand_files, 1):
    ligand_path = os.path.join("hiv_ligands", ligand)
    affinity = dock_ligand(ligand_path, binding_site)
    
    if affinity:
        results.append({'ligand': ligand, 'affinity': affinity})
        print(f"{i:3d}. {ligand:<25} {affinity:>6.2f} kcal/mol")
    else:
        print(f"{i:3d}. {ligand:<25} FAILED")
    
    if i % 20 == 0:
        print(f"\nProgress: {i}/{len(ligand_files)}\n")

with open("hiv_screening_100.json", 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "="*70)
print("SCREENING COMPLETE")
print(f"End: {datetime.now().strftime('%H:%M:%S')}")
print("="*70)

if results:
    results.sort(key=lambda x: x['affinity'])
    
    print("\nTOP 10 HITS:")
    print("-"*50)
    for i, r in enumerate(results[:10], 1):
        print(f"{i:2d}. {r['affinity']:6.2f} kcal/mol  {r['ligand']}")
    
    affinities = [r['affinity'] for r in results]
    print(f"\nStatistics:")
    print(f"  Best: {min(affinities):.2f} kcal/mol")
    print(f"  Average: {sum(affinities)/len(affinities):.2f} kcal/mol")
    
    strong = sum(1 for a in affinities if a < -7)
    print(f"  Strong binders (< -7): {strong}")
    
    print(f"\nResults saved to: hiv_screening_100.json")
else:
    print("\nNo successful docking results")
