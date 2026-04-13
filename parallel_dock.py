# -*- coding: utf-8 -*-
"""
High-Performance Parallel Docking for HIV Drug Discovery
Uses all available CPU cores for maximum speed
"""

import subprocess
import os
import multiprocessing as mp
import json
from datetime import datetime
import time

class ParallelDocker:
    """High-performance parallel docking using multiple CPU cores"""
    
    def __init__(self, n_cores=None):
        if n_cores is None:
            n_cores = mp.cpu_count()
        self.n_cores = n_cores
        print(f"Initializing Parallel Docker with {n_cores} CPU cores")
        
    def dock_single(self, args):
        """Dock a single ligand (runs in parallel)"""
        ligand_file, receptor_file, binding_site, output_dir, exhaustiveness = args
        
        try:
            # Use 2 threads per ligand (balance between cores)
            cpu_threads = max(1, self.n_cores // 4)
            
            cmd = [
                "./bin/vina.exe",
                "--receptor", receptor_file,
                "--ligand", ligand_file,
                "--center_x", str(binding_site[0]),
                "--center_y", str(binding_site[1]),
                "--center_z", str(binding_site[2]),
                "--size_x", "25",
                "--size_y", "25",
                "--size_z", "25",
                "--out", os.path.join(output_dir, f"result_{os.path.basename(ligand_file)}"),
                "--num_modes", "1",
                "--exhaustiveness", str(exhaustiveness),
                "--cpu", str(cpu_threads)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            
            # Parse affinity
            for line in result.stdout.split('\n'):
                if line.strip() and line.strip()[0].isdigit():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            affinity = float(parts[1])
                            if affinity < 5:  # Valid binding
                                return {
                                    'ligand': ligand_file,
                                    'affinity': affinity,
                                    'success': True
                                }
                        except:
                            continue
            
            return {'ligand': ligand_file, 'affinity': None, 'success': False}
            
        except Exception as e:
            print(f"Error with {ligand_file}: {e}")
            return {'ligand': ligand_file, 'affinity': None, 'success': False}
    
    def batch_dock(self, ligands, receptor, binding_site, exhaustiveness=12, chunk_size=None):
        """Dock multiple ligands in parallel"""
        
        print("="*80)
        print("PARALLEL DOCKING BATCH")
        print("="*80)
        print(f"CPU Cores: {self.n_cores}")
        print(f"Ligands: {len(ligands)}")
        print(f"Exhaustiveness: {exhaustiveness}")
        print(f"Start: {datetime.now().strftime('%H:%M:%S')}")
        print("-"*80)
        
        # Create output directory
        output_dir = "parallel_results"
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare arguments
        args_list = [(ligand, receptor, binding_site, output_dir, exhaustiveness) 
                     for ligand in ligands]
        
        # Determine chunk size for progress reporting
        if chunk_size is None:
            chunk_size = max(1, len(ligands) // 20)
        
        # Run parallel docking
        results = []
        with mp.Pool(processes=self.n_cores) as pool:
            for i, result in enumerate(pool.imap_unordered(self.dock_single, args_list, chunksize=chunk_size)):
                if result['success']:
                    results.append(result)
                
                if (i + 1) % max(1, len(ligands) // 10) == 0:
                    print(f"  Progress: {i+1}/{len(ligands)} ligands processed")
        
        results.sort(key=lambda x: x['affinity'])
        
        print(f"\nEnd: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Successful: {len(results)}/{len(ligands)} ligands")
        
        return results
    
    def dock_priority(self, ligand, receptor, binding_site, exhaustiveness=16):
        """Dock a single ligand with maximum priority"""
        
        cmd = [
            "./bin/vina.exe",
            "--receptor", receptor,
            "--ligand", ligand,
            "--center_x", str(binding_site[0]),
            "--center_y", str(binding_site[1]),
            "--center_z", str(binding_site[2]),
            "--size_x", "25",
            "--size_y", "25",
            "--size_z", "25",
            "--out", "priority_result.pdbqt",
            "--num_modes", "9",
            "--exhaustiveness", str(exhaustiveness),
            "--cpu", str(self.n_cores)
        ]
        
        print(f"\nDocking with MAXIMUM priority...")
        print(f"   Using all {self.n_cores} CPU cores")
        print(f"   Ligand: {ligand}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        affinities = []
        for line in result.stdout.split('\n'):
            if line.strip() and line.strip()[0].isdigit():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        affinities.append(float(parts[1]))
                    except:
                        continue
        
        return affinities

# ================== MAIN ==================
print("="*80)
print("HIGH-PERFORMANCE HIV DRUG DISCOVERY")
print("="*80)

docker = ParallelDocker()

with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print(f"\nBinding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")

# Find ligands
ligands = []
for f in os.listdir("."):
    if f.endswith(".pdbqt") and "result" not in f and "temp" not in f:
        if "CURE" in f or "ligand_" in f:
            ligands.append(f)

if os.path.exists("hiv_ligands") and not ligands:
    ligands = [os.path.join("hiv_ligands", f) for f in os.listdir("hiv_ligands") if f.endswith(".pdbqt")]

print(f"\nFound {len(ligands)} ligands")

# Dock best candidate
print("\n" + "="*80)
print("MAXIMUM PRIORITY DOCKING")
print("="*80)

best_candidate = None
for f in ligands:
    if "CURE_076" in f or "CURE_070" in f:
        best_candidate = f
        break

if best_candidate:
    print(f"\nDocking best candidate: {best_candidate}")
    affinities = docker.dock_priority(best_candidate, "hiv_protease.pdbqt", binding_site)
    
    if affinities:
        valid = [a for a in affinities if a < 5]
        best = min(valid) if valid else affinities[0]
        print(f"\nRESULTS:")
        print(f"  Best affinity: {best:.3f} kcal/mol")
        print(f"  All modes: {affinities[:5]}")
        
        with open("best_candidate_affinities.txt", "w") as f:
            for aff in affinities:
                f.write(f"{aff}\n")
    else:
        print("No valid affinities found")

# Batch dock test set
print("\n" + "="*80)
print("BATCH DOCKING (Test Set)")
print("="*80)

test_ligands = ligands[:min(20, len(ligands))]
print(f"\nDocking {len(test_ligands)} test ligands...")

results = docker.batch_dock(test_ligands, "hiv_protease.pdbqt", binding_site, exhaustiveness=12)

if results:
    print("\n" + "="*80)
    print("TOP 10 BINDERS (Batch Results)")
    print("="*80)
    print(f"{'Rank':<6} {'Ligand':<45} {'Affinity':<12}")
    print("-"*70)
    for i, r in enumerate(results[:10], 1):
        ligand_name = os.path.basename(r['ligand'])
        print(f"{i:<6} {ligand_name:<45} {r['affinity']:<12.3f}")
    
    with open("parallel_batch_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: parallel_batch_results.json")

print("\n" + "="*80)
print("DOCKING COMPLETE!")
print("="*80)
