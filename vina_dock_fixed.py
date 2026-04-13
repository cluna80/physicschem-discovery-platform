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
    - list of dictionaries with mode, affinity, rmsd_lb, rmsd_ub
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
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse binding affinities
    affinities = []
    reading_data = False
    
    for line in result.stdout.split('\n'):
        line = line.strip()
        
        # Start reading when we see the separator line after the header
        if '-----+------------+----------+----------' in line:
            reading_data = True
            continue
        
        # Parse data lines
        if reading_data and line:
            parts = line.split()
            # Look for lines that start with a number (mode)
            if len(parts) >= 3 and parts[0].isdigit():
                try:
                    mode = int(parts[0])
                    affinity = float(parts[1])
                    rmsd_lb = float(parts[2])
                    rmsd_ub = float(parts[3]) if len(parts) > 3 else 0
                    
                    affinities.append({
                        'mode': mode,
                        'affinity': affinity,
                        'rmsd_lb': rmsd_lb,
                        'rmsd_ub': rmsd_ub
                    })
                except (ValueError, IndexError):
                    continue
    
    return affinities, result.stdout

if __name__ == "__main__":
    print("="*50)
    print("Vina Docking Results")
    print("="*50)
    
    # Run docking
    affinities, output = dock(
        receptor="final_receptor.pdbqt",
        ligand="final_ligand.pdbqt",
        center=(15.0, 53.0, 17.0),
        size=20
    )
    
    print("\nBinding Affinities:")
    print("-"*40)
    
    if affinities:
        for a in affinities:
            print(f"Mode {a['mode']}: {a['affinity']:.3f} kcal/mol  (RMSD: {a['rmsd_lb']:.2f}/{a['rmsd_ub']:.2f})")
        
        print("\n" + "-"*40)
        print(f"Best binding affinity: {affinities[0]['affinity']:.3f} kcal/mol")
        
        # Interpretation
        if affinities[0]['affinity'] < -7:
            print("Interpretation: Strong binding")
        elif affinities[0]['affinity'] < -5:
            print("Interpretation: Moderate binding")
        elif affinities[0]['affinity'] < -3:
            print("Interpretation: Weak binding")
        else:
            print("Interpretation: Very weak binding")
    else:
        print("No binding affinities found!")
        print("\nFirst few lines of output:")
        for line in output.split('\n')[:20]:
            print(line)
