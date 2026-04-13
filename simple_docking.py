# -*- coding: utf-8 -*-
import subprocess
import os
from vina_wrapper import VinaDocker

def prepare_files():
    """Prepare receptor and ligand files for docking"""
    
    # Check if files already exist
    if not os.path.exists("receptor.pdbqt") or not os.path.exists("ligand.pdbqt"):
        print("Preparing docking files...")
        
        # Download a small protein (trypsin inhibitor)
        print("Downloading receptor...")
        subprocess.run([
            "curl", "-s", "-o", "1t7r.pdb",
            "https://files.rcsb.org/download/1T7R.pdb"
        ], capture_output=True)
        
        # Convert receptor to PDBQT
        print("Converting receptor to PDBQT...")
        subprocess.run([
            "obabel", "1t7r.pdb", "-O", "receptor.pdbqt",
            "-xr", "-p"
        ], capture_output=True)
        
        # Create a simple ligand (benzene-like molecule)
        print("Creating ligand...")
        with open("ligand.pdb", "w") as f:
            f.write("""HETATM    1  C   LIG     1       0.000   0.000   0.000  1.00  0.00           C
HETATM    2  C   LIG     1       1.000   0.000   0.000  1.00  0.00           C
HETATM    3  C   LIG     1       1.500   0.866   0.000  1.00  0.00           C
HETATM    4  C   LIG     1       1.000   1.732   0.000  1.00  0.00           C
HETATM    5  C   LIG     1       0.000   1.732   0.000  1.00  0.00           C
HETATM    6  C   LIG     1      -0.500   0.866   0.000  1.00  0.00           C
HETATM    7  H   LIG     1      -0.500  -0.500   0.000  1.00  0.00           H
HETATM    8  H   LIG     1       1.500  -0.500   0.000  1.00  0.00           H
HETATM    9  H   LIG     1       2.500   0.866   0.000  1.00  0.00           H
HETATM   10  H   LIG     1       1.500   2.232   0.000  1.00  0.00           H
HETATM   11  H   LIG     1      -0.500   2.232   0.000  1.00  0.00           H
HETATM   12  H   LIG     1      -1.500   0.866   0.000  1.00  0.00           H
END""")
        
        # Convert ligand to PDBQT
        print("Converting ligand to PDBQT...")
        subprocess.run([
            "obabel", "ligand.pdb", "-O", "ligand.pdbqt", "-xh"
        ], capture_output=True)
        
        print("Files prepared successfully!")
    else:
        print("Files already exist, using existing files.")

def main():
    print("=" * 60)
    print("AutoDock Vina Docking Example")
    print("=" * 60)
    
    # Prepare files
    prepare_files()
    
    # Initialize Vina
    vina = VinaDocker()
    
    # Check if Vina works
    if not vina.test_vina():
        print("Vina not working!")
        return
    
    # Define docking box
    # Center of the binding pocket (estimated)
    center = (15.0, 10.0, 5.0)
    size = (20.0, 20.0, 20.0)
    
    print(f"\nDocking parameters:")
    print(f"  Search box center: {center}")
    print(f"  Search box size: {size}")
    print(f"  Output file: docking_result.pdbqt")
    
    # Run docking
    print("\nRunning docking (this may take 30-60 seconds)...")
    result = vina.dock(
        receptor="receptor.pdbqt",
        ligand="ligand.pdbqt",
        center=center,
        size=size,
        output="docking_result.pdbqt",
        num_modes=5,
        exhaustiveness=8
    )
    
    # Display results
    if result and result['return_code'] == 0:
        print("\n" + "=" * 60)
        print("DOCKING RESULTS")
        print("=" * 60)
        
        if result['affinities']:
            print("\nBinding affinities (kcal/mol):")
            for i, aff in enumerate(result['affinities'][:5], 1):
                print(f"  Mode {i}: {aff}")
        
        print(f"\nDetailed results saved to: docking_result.pdbqt")
        
        # Show summary
        print("\nSummary of top binding mode:")
        for line in result['output'].split('\n')[:15]:
            if any(key in line.lower() for key in ['mode', 'affinity', 'rmsd', 'binding']):
                print(f"  {line}")
    
    else:
        print("\nDocking failed!")
        if result:
            print("Error output:", result['output'])
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
