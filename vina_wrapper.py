# -*- coding: utf-8 -*-
import subprocess
import os
import sys

class VinaDocker:
    def __init__(self, vina_path="./bin/vina.exe"):
        # Get absolute path relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.vina_path = os.path.join(script_dir, vina_path)
        
        # Verify vina exists
        if not os.path.exists(self.vina_path):
            raise FileNotFoundError(f"Vina not found at {self.vina_path}")
    
    def dock(self, receptor, ligand, center, size, output="out.pdbqt", 
             num_modes=9, exhaustiveness=8, energy_range=3, cpu=1):
        """
        Run molecular docking with AutoDock Vina
        
        Parameters:
        - receptor: path to receptor.pdbqt file
        - ligand: path to ligand.pdbqt file  
        - center: tuple (x, y, z) for search space center
        - size: tuple (x, y, z) for search space dimensions
        - output: output filename for docking results
        - num_modes: number of binding modes to generate (default: 9)
        - exhaustiveness: exhaustiveness of search (default: 8)
        - energy_range: max energy difference between best and worst modes (default: 3)
        - cpu: number of CPUs to use (default: 1)
        """
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
            "--out", output,
            "--num_modes", str(num_modes),
            "--exhaustiveness", str(exhaustiveness),
            "--energy_range", str(energy_range),
            "--cpu", str(cpu)
        ]
        
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return None
        
        # Parse binding affinities
        affinities = []
        modes = []
        current_mode = {}
        
        for line in result.stdout.split('\n'):
            if "Affinity" in line and "kcal/mol" in line:
                affinities.append(line.strip())
            if "mode" in line and "affinity" in line:
                modes.append(line.strip())
        
        return {
            'output': result.stdout,
            'affinities': affinities,
            'modes': modes,
            'return_code': result.returncode
        }
    
    def test_vina(self):
        """Test if vina is working"""
        try:
            result = subprocess.run([self.vina_path, "--help"], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"Error testing vina: {e}")
            return False

if __name__ == "__main__":
    docker = VinaDocker()
    if docker.test_vina():
        print("✅ Vina is working!")
        print(f"   Vina path: {docker.vina_path}")
    else:
        print("❌ Vina test failed")
