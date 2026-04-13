# -*- coding: utf-8 -*-
import subprocess
import os

class VinaDocker:
    def __init__(self, vina_path="./bin/vina.exe"):
        self.vina_path = os.path.abspath(vina_path)
        if not os.path.exists(self.vina_path):
            raise FileNotFoundError(f"Vina not found at {self.vina_path}")

    def dock(self, receptor, ligand, center, size,
             num_modes=9, exhaustiveness=8, energy_range=3, cpu=1):
        """Run molecular docking"""
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
            "--exhaustiveness", str(exhaustiveness),
            "--energy_range", str(energy_range),
            "--cpu", str(cpu)
        ]
        
        print("Running docking...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
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
                elif len(parts) < 2:
                    break
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'affinities': affinities
        }

def main():
    docker = VinaDocker()
    
    print("="*60)
    print("AutoDock Vina - Molecular Docking")
    print("="*60)
    
    result = docker.dock(
        receptor="final_receptor.pdbqt",
        ligand="final_ligand.pdbqt",
        center=(15.0, 53.0, 17.0),
        size=(20.0, 20.0, 20.0),
        exhaustiveness=16
    )
    
    if result['success'] and result['affinities']:
        print("\n" + "="*60)
        print("Docking Results")
        print("="*60)
        print(f"{'Mode':<6} {'Affinity (kcal/mol)':<20} {'RMSD l.b.':<12} {'RMSD u.b.':<12}")
        print("-"*60)
        
        for aff in result['affinities']:
            print(f"{aff['mode']:<6} {aff['affinity']:<20.2f} {aff['rmsd_lb']:<12.2f} {aff['rmsd_ub']:<12.2f}")
        
        best = result['affinities'][0]
        print(f"\nBest binding affinity: {best['affinity']:.2f} kcal/mol")
        
        if best['affinity'] < -7:
            print("Interpretation: Strong binding")
        elif best['affinity'] < -5:
            print("Interpretation: Moderate binding")
        elif best['affinity'] < -3:
            print("Interpretation: Weak binding")
        else:
            print("Interpretation: Very weak binding")
        
        print("\nResults saved to: docking_result.pdbqt")
    else:
        print("Docking failed")
        if result['stderr']:
            print("Error:", result['stderr'])

if __name__ == "__main__":
    main()
