import os
import subprocess
from vina_wrapper import VinaDocker

class DockingWorkflow:
    def __init__(self):
        self.vina = VinaDocker()
        print(f"Vina path: {self.vina.vina_path}")
    
    def pdb_to_pdbqt(self, pdb_file, pdbqt_file, is_receptor=False):
        """Convert PDB to PDBQT using OpenBabel"""
        cmd = ["obabel", pdb_file, "-O", pdbqt_file]
        if is_receptor:
            cmd.append("-xr")  # AutoDock4 atom types
            cmd.append("-p")   # Keep hydrogens
        else:
            cmd.append("-xh")  # Add hydrogens for ligands
            
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"‚úÖ Converted {pdb_file} -> {pdbqt_file}")
            return True
        else:
            print(f"‚ùå Conversion failed: {result.stderr}")
            return False
    
    def run_docking_demo(self):
        """Run a demonstration of docking"""
        print("\nÌ¥¨ Docking Workflow Demo")
        print("=" * 50)
        
        # Check if Vina is working
        if not self.vina.test_vina():
            print("‚ùå Vina not available")
            return
        
        print("‚úÖ Vina is ready")
        print("\nTo perform actual docking, you need:")
        print("1. A receptor PDB file (protein)")
        print("2. A ligand PDB file (small molecule)")
        print("3. Convert both to PDBQT format")
        print("4. Define the docking box center and size")
        print("5. Run docking")
        
        print("\nExample command for docking:")
        print("""
        vina.dock(
            receptor="receptor.pdbqt",
            ligand="ligand.pdbqt", 
            center=(15.0, 20.0, 10.0),
            size=(20.0, 20.0, 20.0),
            output="result.pdbqt"
        )
        """)

def download_sample_files():
    """Download sample protein and ligand for testing"""
    print("Ì≥• Downloading sample files...")
    
    # Download a small protein (HIV protease - 1HVR)
    subprocess.run([
        "wget", "-O", "sample_receptor.pdb", 
        "https://files.rcsb.org/download/1HVR.pdb"
    ], capture_output=True)
    
    # Create a simple test ligand
    with open("sample_ligand.sdf", "w") as f:
        f.write("""
sample_ligand
  ZINC00000001 3D
 12 12  0  0  0  0  0  0  0  0999 V2000
   -2.2430    1.0960   -0.0460 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.0210    1.5900   -0.4030 C   0  0  0  0  0  0  0  0  0  0  0  0
   -1.7420   -0.1150    0.3100 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.1130    0.8650   -0.4620 C   0  0  0  0  0  0  0  0  0  0  0  0
   -0.5530   -0.2790    0.2760 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.3750    1.2320   -0.8940 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.4370    0.4050   -0.9850 C   0  0  0  0  0  0  0  0  0  0  0  0
    2.3450   -0.9280   -0.6510 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.1550   -1.3310   -0.1940 C   0  0  0  0  0  0  0  0  0  0  0  0
    0.0930   -0.4870   -0.1030 C   0  0  0  0  0  0  0  0  0  0  0  0
    3.7080    0.8650   -1.4730 C   0  0  0  0  0  0  0  0  0  0  0  0
    1.0730   -2.7050    0.1710 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0
  1  3  1  0
  2  4  1  0
  3  5  1  0
  4  5  1  0
  4  6  1  0
  5 10  1  0
  6  7  1  0
  7  8  2  0
  7 11  1  0
  8  9  1  0
  9 10  2  0
  9 12  1  0
M  END
$$$$
""")
    print("‚úÖ Sample files created")
    print("   - sample_receptor.pdb")
    print("   - sample_ligand.sdf")

if __name__ == "__main__":
    workflow = DockingWorkflow()
    workflow.run_docking_demo()
    
    # Ask user if they want to download sample files
    response = input("\nÌ≥• Download sample files for testing? (y/n): ")
    if response.lower() == 'y':
        download_sample_files()
        print("\nÌ∫Ä Next steps:")
        print("1. Convert files to PDBQT: obabel sample_receptor.pdb -O receptor.pdbqt -xr -p")
        print("2. Convert ligand: obabel sample_ligand.sdf -O ligand.pdbqt -xh")
        print("3. Edit your wrapper to use these files")
