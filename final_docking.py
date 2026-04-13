# -*- coding: utf-8 -*-
import subprocess
import os

def download_example_files():
    """Download working example files from Vina repository"""
    print("Downloading example files...")
    
    files = {
        "receptor.pdbqt": "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/develop/example/receptor.pdbqt",
        "ligand.pdbqt": "https://raw.githubusercontent.com/ccsb-scripps/AutoDock-Vina/develop/example/ligand.pdbqt"
    }
    
    for filename, url in files.items():
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            print(f"  Downloading {filename}...")
            subprocess.run(["curl", "-s", "-L", "-o", filename, url])
        else:
            print(f"  {filename} already exists")
    
    # Verify files
    for filename in files.keys():
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            result = subprocess.run(f"grep -c '^ATOM' {filename}", shell=True, capture_output=True, text=True)
            atoms = int(result.stdout.strip() or 0)
            print(f"  {filename}: {atoms} atoms")
        else:
            print(f"  ERROR: {filename} is empty or missing")

def run_docking():
    """Run Vina docking with example files"""
    print("\n" + "="*60)
    print("Running AutoDock Vina Docking")
    print("="*60)
    
    # Parameters for the example system
    center = (15.0, 53.0, 17.0)
    size = (20.0, 20.0, 20.0)
    
    cmd = [
        "./bin/vina.exe",
        "--receptor", "receptor.pdbqt",
        "--ligand", "ligand.pdbqt",
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size[0]),
        "--size_y", str(size[1]),
        "--size_z", str(size[2]),
        "--out", "docking_result.pdbqt",
        "--num_modes", "9",
        "--exhaustiveness", "16"
    ]
    
    print(f"\nDocking parameters:")
    print(f"  Center: {center}")
    print(f"  Box size: {size}")
    print(f"  Exhaustiveness: 16")
    print(f"\nRunning docking (this may take 1-2 minutes)...\n")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print Vina output
    print(result.stdout)
    
    if result.stderr:
        print("Errors/Warnings:", result.stderr)
    
    # Parse results
    print("\n" + "="*60)
    print("BINDING AFFINITIES")
    print("="*60)
    
    in_table = False
    affinities = []
    
    for line in result.stdout.split('\n'):
        if 'mode' in line and 'affinity' in line:
            in_table = True
            print(f"\n{line}")
            print("-"*50)
            continue
        
        if in_table and line.strip():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].isdigit():
                mode = int(parts[0])
                affinity = float(parts[1])
                rmsd_lb = float(parts[2])
                rmsd_ub = float(parts[3]) if len(parts) > 3 else 0
                affinities.append((mode, affinity, rmsd_lb, rmsd_ub))
                
                print(f"{mode:>4}     {affinity:>10.2f} kcal/mol     {rmsd_lb:>8.2f}     {rmsd_ub:>8.2f}")
    
    # Summary
    if affinities:
        print("\n" + "="*60)
        print("DOCKING SUMMARY")
        print("="*60)
        
        best_mode, best_aff, best_rmsd_lb, best_rmsd_ub = affinities[0]
        print(f"\nBest binding mode: Mode {best_mode}")
        print(f"Binding affinity: {best_aff:.2f} kcal/mol")
        print(f"RMSD from best mode: {best_rmsd_lb:.2f} A (lower bound), {best_rmsd_ub:.2f} A (upper bound)")
        
        # Interpretation
        if best_aff < -9:
            strength = "Very strong binding (high affinity)"
        elif best_aff < -7:
            strength = "Strong binding"
        elif best_aff < -5:
            strength = "Moderate binding"
        elif best_aff < -3:
            strength = "Weak binding"
        else:
            strength = "Very weak binding"
        
        print(f"\nInterpretation: {strength}")
        
        # Check if there are multiple good modes
        if len(affinities) > 1:
            gap = affinities[0][1] - affinities[1][1]
            if gap > 2:
                print(f"Energy gap to next mode: {gap:.2f} kcal/mol -> Clear single binding mode")
            else:
                print(f"Energy gap to next mode: {gap:.2f} kcal/mol -> Multiple possible binding modes")
    else:
        print("\nNo binding affinities found. Check if docking completed successfully.")
    
    print(f"\nDetailed results saved to: docking_result.pdbqt")
    print("="*60)

if __name__ == "__main__":
    download_example_files()
    run_docking()
