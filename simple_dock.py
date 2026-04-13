# -*- coding: utf-8 -*-
import subprocess

def run_docking():
    cmd = [
        "./bin/vina.exe",
        "--receptor", "final_receptor.pdbqt",
        "--ligand", "final_ligand.pdbqt",
        "--center_x", "15.0",
        "--center_y", "53.0",
        "--center_z", "17.0",
        "--size_x", "20.0",
        "--size_y", "20.0",
        "--size_z", "20.0",
        "--out", "docking_result.pdbqt",
        "--num_modes", "9",
        "--exhaustiveness", "16"
    ]
    
    print("Running AutoDock Vina...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("\n" + "="*60)
    print("DOCKING RESULTS")
    print("="*60)
    
    # Print the Vina output
    print(result.stdout)
    
    if result.stderr:
        print("Errors/Warnings:")
        print(result.stderr)
    
    return result

if __name__ == "__main__":
    result = run_docking()
    
    if result.returncode == 0:
        print("\n✅ Docking completed successfully!")
        print("Results saved to: docking_result.pdbqt")
    else:
        print("\n❌ Docking failed with return code:", result.returncode)
