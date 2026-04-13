# -*- coding: utf-8 -*-
import subprocess

def dock(receptor, ligand, center, size, exhaustiveness=16, num_modes=9):
    """
    Dock a ligand into a receptor using AutoDock Vina
    
    Parameters:
    - receptor: path to receptor PDBQT file
    - ligand: path to ligand PDBQT file
    - center: tuple (x, y, z) for grid center
    - size: tuple (x, y, z) or int for grid size
    - exhaustiveness: int (higher = more thorough, default 16)
    - num_modes: int (number of binding modes, default 9)
    
    Returns:
    - list of (mode, affinity, rmsd_lb, rmsd_ub) for each mode
    """
    if isinstance(size, (int, float)):
        size = (size, size, size)
    
    cmd = [
        "./bin/vina.exe",
        "--receptor", receptor,
        "--ligand", ligand,
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size[0]),
        "--size_y", str(size[1]),
        "--size_z", str(size[2]),
        "--out", "docking_result.pdbqt",
        "--num_modes", str(num_modes),
        "--exhaustiveness", str(exhaustiveness)
    ]
    
    print("Running Vina docking...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print the full output for debugging
    print(result.stdout)
    
    # Parse binding affinities
    affinities = []
    in_table = False
    
    for line in result.stdout.split('\n'):
        if 'mode' in line and 'affinity' in line:
            in_table = True
            continue
        if in_table and line.strip():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].isdigit():
                affinities.append({
                    'mode': int(parts[0]),
                    'affinity': float(parts[1]),
                    'rmsd_lb': float(parts[2]),
                    'rmsd_ub': float(parts[3]) if len(parts) > 3 else 0
                })
                print(f"Parsed: Mode {parts[0]} = {parts[1]} kcal/mol")
            elif len(parts) < 2:
                break
    
    return affinities, result.stdout

if __name__ == "__main__":
    print("="*50)
    print("Testing Vina Docking")
    print("="*50)
    
    # Check if files exist
    import os
    for f in ["final_receptor.pdbqt", "final_ligand.pdbqt"]:
        if os.path.exists(f):
            print(f"✓ {f} exists")
        else:
            print(f"✗ {f} NOT found")
    
    print("\n" + "="*50)
    
    # Run docking
    affinities, output = dock(
        receptor="final_receptor.pdbqt",
        ligand="final_ligand.pdbqt",
        center=(15.0, 53.0, 17.0),
        size=20
    )
    
    print("\n" + "="*50)
    print("Docking Results Summary:")
    print("="*50)
    
    if affinities:
        for a in affinities:
            print(f"  Mode {a['mode']}: {a['affinity']:.3f} kcal/mol (RMSD: {a['rmsd_lb']:.2f}/{a['rmsd_ub']:.2f})")
        
        print(f"\nBest binding affinity: {affinities[0]['affinity']:.3f} kcal/mol")
    else:
        print("No binding affinities were parsed. Check the output above.")
