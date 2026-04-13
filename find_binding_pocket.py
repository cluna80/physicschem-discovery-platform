# -*- coding: utf-8 -*-
import subprocess

def analyze_egfr():
    """Analyze EGFR structure to find binding pocket"""
    
    # Check if the protein has ligands bound
    print("Analyzing EGFR structure (1M17)...")
    print("="*60)
    
    # Look for ligand entries in the PDB file
    print("\nLooking for bound ligands in the structure:")
    result = subprocess.run(["grep", "^HETATM", "egfr.pdb"], capture_output=True, text=True)
    
    hetatoms = result.stdout.strip().split('\n')
    ligands = set()
    for line in hetatoms[:20]:  # Show first few
        if len(line) > 50:
            print(f"  {line[:50]}...")
    
    # Check if there's a known inhibitor
    print("\nSearching for known EGFR inhibitors...")
    result = subprocess.run(["grep", "-i", "quinazoline", "egfr.pdb"], capture_output=True, text=True)
    if result.stdout:
        print("Found quinazoline-like compound in structure")
        print(result.stdout[:500])
    
    # Find coordinates for pocket - look at key residues
    key_residues = ["MET793", "LYS745", "GLU762", "ASP855"]  # Common EGFR binding residues
    print("\nChecking key residues in binding pocket:")
    for res in key_residues:
        result = subprocess.run(["grep", res, "egfr.pdb"], capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines[:3]:
                if "ATOM" in line:
                    # Extract coordinates (columns 30-54 typically)
                    x = line[30:38].strip()
                    y = line[38:46].strip()
                    z = line[46:54].strip()
                    print(f"  {res}: x={x}, y={y}, z={z}")
    
    print("\n" + "="*60)
    print("Recommended binding site:")
    print("  Center: (40.0, 40.0, 40.0) - adjust based on above")
    print("  Size: 25.0 (should cover ATP pocket)")

if __name__ == "__main__":
    analyze_egfr()
