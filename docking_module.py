# -*- coding: utf-8 -*-
"""
AutoDock Vina Python Module
Reusable docking functions for your AI quantum lab
"""

import subprocess
import os

class VinaDocker:
    """AutoDock Vina wrapper class"""
    
    def __init__(self, vina_path="./bin/vina.exe"):
        self.vina_path = os.path.abspath(vina_path)
        if not os.path.exists(self.vina_path):
            raise FileNotFoundError(f"Vina not found at {self.vina_path}")
    
    def dock(self, receptor, ligand, center, size, exhaustiveness=16, num_modes=9):
        """Run docking and return parsed results"""
        
        if isinstance(size, (int, float)):
            size = (size, size, size)
        
        cmd = [
            self.vina_path,
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
        
        # Parse results
        affinities = []
        reading_data = False
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if '-----+------------+----------+----------' in line:
                reading_data = True
                continue
            if reading_data and line:
                parts = line.split()
                if len(parts) >= 3 and parts[0].isdigit():
                    try:
                        affinities.append({
                            'mode': int(parts[0]),
                            'affinity': float(parts[1]),
                            'rmsd_lb': float(parts[2]),
                            'rmsd_ub': float(parts[3]) if len(parts) > 3 else 0
                        })
                    except ValueError:
                        continue
                elif len(parts) < 2:
                    reading_data = False
        
        return affinities
    
    def get_best_affinity(self, receptor, ligand, center, size, exhaustiveness=16):
        """Quickly get just the best binding affinity"""
        affinities = self.dock(receptor, ligand, center, size, exhaustiveness, num_modes=1)
        return affinities[0]['affinity'] if affinities else None

# Test the module
if __name__ == "__main__":
    docker = VinaDocker()
    
    print("Testing VinaDocker module...")
    affinities = docker.dock(
        receptor="final_receptor.pdbqt",
        ligand="final_ligand.pdbqt",
        center=(15.0, 53.0, 17.0),
        size=20,
        exhaustiveness=16
    )
    
    print(f"\nFound {len(affinities)} binding modes")
    for a in affinities[:5]:
        print(f"  Mode {a['mode']}: {a['affinity']:.3f} kcal/mol")
    
    best = docker.get_best_affinity(
        receptor="final_receptor.pdbqt",
        ligand="final_ligand.pdbqt",
        center=(15.0, 53.0, 17.0),
        size=20
    )
    print(f"\nBest affinity: {best:.3f} kcal/mol")
