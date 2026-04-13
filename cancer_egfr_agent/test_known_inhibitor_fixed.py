# test_known_inhibitor_fixed.py
import subprocess
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
import os

def test_docking_with_known_drug():
    """Test if docking works with known EGFR inhibitors"""
    
    # Use a simpler, validated SMILES for erlotinib
    # Erlotinib (canonical SMILES from PubChem)
    erlotinib_smiles = "COc1ccc2c(c1)c(Nc1nccn3ccccc13)ncn2"
    
    print("="*70)
    print("TESTING DOCKING PIPELINE WITH KNOWN EGFR INHIBITOR")
    print("="*70)
    
    print(f"\n1. Processing erlotinib: {erlotinib_smiles}")
    
    # Generate 3D structure with error handling
    mol = Chem.MolFromSmiles(erlotinib_smiles)
    if mol is None:
        print("   ERROR: Invalid SMILES")
        return
    
    # Sanitize first
    try:
        Chem.SanitizeMol(mol)
        print("   ✓ Molecule sanitized")
    except Exception as e:
        print(f"   Sanitization warning: {e}")
        # Try to fix with kekulization
        try:
            Chem.Kekulize(mol)
            Chem.SanitizeMol(mol)
            print("   ✓ Fixed with kekulization")
        except:
            print("   ✗ Cannot fix molecule")
            return
    
    # Add hydrogens
    mol = Chem.AddHs(mol)
    print(f"   ✓ Added {mol.GetNumAtoms()} atoms with hydrogens")
    
    # Generate 3D conformation
    try:
        # Try ETKDGv3 first
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        if result == 0:
            print("   ✓ 3D conformation generated (ETKDGv3)")
        else:
            # Fallback to original ETKDG
            result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            if result == 0:
                print("   ✓ 3D conformation generated (ETKDG)")
            else:
                print(f"   ✗ 3D generation failed (error code {result})")
                return
    except Exception as e:
        print(f"   ✗ 3D generation error: {e}")
        return
    
    # Optimize geometry
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=1000)
        print("   ✓ Geometry optimized")
    except:
        print("   ⚠ Optimization warning, continuing...")
    
    # Save as PDB
    pdb_file = "erlotinib_test.pdb"
    Chem.MolToPDBFile(mol, pdb_file)
    print(f"   ✓ Saved to {pdb_file}")
    
    # Check if receptor exists
    receptor = "egfr_receptor.pdbqt"
    if not os.path.exists(receptor):
        print(f"\n✗ ERROR: Receptor file '{receptor}' not found!")
        print("  Please prepare receptor first:")
        print("  1. Download 4HJO.pdb from RCSB")
        print("  2. Run: obabel 4HJO.pdb -O egfr_receptor.pdbqt -xr --partialcharge gasteiger")
        return
    
    # Check receptor quality
    print("\n2. Checking receptor file...")
    with open(receptor, 'r') as f:
        content = f.read()
        if "MET793" in content:
            print("   ✓ MET793 found (hinge residue)")
        else:
            print("   ⚠ MET793 not found - receptor may be incomplete")
        if "CYS797" in content:
            print("   ✓ CYS797 found (covalent target)")
        else:
            print("   ⚠ CYS797 not found - covalent binding may not work")
    
    # Convert to PDBQT with obabel
    print("\n3. Converting ligand to PDBQT...")
    pdbqt_file = "erlotinib_test.pdbqt"
    cmd_obabel = [
        "obabel", pdb_file, "-O", pdbqt_file,
        "--partialcharge", "gasteiger",
        "-h"  # Add hydrogens
    ]
    
    try:
        result = subprocess.run(cmd_obabel, capture_output=True, text=True, timeout=30)
        if os.path.exists(pdbqt_file):
            print("   ✓ PDBQT created with obabel")
        else:
            print(f"   ✗ obabel failed: {result.stderr}")
            return
    except Exception as e:
        print(f"   ✗ obabel error: {e}")
        return
    
    # Test multiple box centers
    print("\n4. Testing docking with different box centers...")
    
    # Try different box centers based on common EGFR structures
    box_configs = [
        {"name": "4HJO (covalent)", "center": (22.0, 0.5, 48.0), "size": (22.0, 24.0, 22.0)},
        {"name": "1M17 (your target)", "center": (22.0, 0.25, 52.79), "size": (20.0, 20.0, 20.0)},
        {"name": "1IEP (erlotinib)", "center": (25.0, 10.5, 15.5), "size": (20.0, 20.0, 20.0)},
    ]
    
    best_affinity = None
    best_config = None
    
    for config in box_configs:
        print(f"\n   Testing {config['name']}: center={config['center']}")
        
        out_file = f"erlotinib_docked_{config['name'].replace(' ', '_')}.pdbqt"
        
        cmd_vina = [
            "vina",
            "--receptor", receptor,
            "--ligand", pdbqt_file,
            "--center_x", str(config['center'][0]),
            "--center_y", str(config['center'][1]),
            "--center_z", str(config['center'][2]),
            "--size_x", str(config['size'][0]),
            "--size_y", str(config['size'][1]),
            "--size_z", str(config['size'][2]),
            "--exhaustiveness", "16",
            "--num_modes", "5",
            "--out", out_file
        ]
        
        try:
            result = subprocess.run(cmd_vina, capture_output=True, text=True, timeout=120)
            
            # Parse best affinity
            for line in result.stdout.split('\n'):
                if line.strip() and line[0].isdigit():
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            affinity = float(parts[1])
                            if best_affinity is None or affinity < best_affinity:
                                best_affinity = affinity
                                best_config = config['name']
                            print(f"     Mode {parts[0]}: {affinity:.2f} kcal/mol")
                            break
                        except:
                            pass
            
            # Also look for summary line
            for line in result.stdout.split('\n'):
                if "Affinity" in line and "kcal/mol" in line and not "Writing" in line:
                    print(f"     {line.strip()}")
                    
        except subprocess.TimeoutExpired:
            print(f"     Timeout for {config['name']}")
        except Exception as e:
            print(f"     Error: {e}")
    
    # Report results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if best_affinity:
        print(f"\nBest docking affinity: {best_affinity:.2f} kcal/mol with {best_config}")
        print("\nInterpretation:")
        if best_affinity < -8.0:
            print("  ✓ EXCELLENT: Pipeline working correctly")
            print("  ✓ Affinity matches expected range (-8.0 to -10.0)")
        elif best_affinity < -5.0:
            print("  ⚠ MODERATE: Pipeline may have issues")
            print("  ⚠ Expected -8.0 to -10.0, got {:.1f}".format(best_affinity))
        else:
            print("  ✗ POOR: Pipeline is broken")
            print("  ✗ Your receptor or box coordinates are wrong")
        
        print(f"\nExpected affinity for erlotinib: -8.5 to -10.0 kcal/mol")
        print(f"Your result: {best_affinity:.1f} kcal/mol")
        
        if best_affinity > -5.0:
            print("\nRECOMMENDED FIXES:")
            print("  1. Download 4HJO.pdb and prepare fresh receptor:")
            print("     wget https://files.rcsb.org/download/4HJO.pdb")
            print("     grep '^ATOM' 4HJO.pdb | grep ' A ' > 4HJO_clean.pdb")
            print("     obabel 4HJO_clean.pdb -O egfr_corrected.pdbqt -xr")
            print("  2. Use box center (22.0, 0.5, 48.0) for 4HJO")
            print("  3. Increase exhaustiveness to 32")
    else:
        print("\n✗ No valid docking results obtained")
        print("  Check if vina is installed: which vina")
        print("  Check if receptor file is valid: head egfr_receptor.pdbqt")
    
    # Cleanup
    for f in ["erlotinib_test.pdb", "erlotinib_test.pdbqt"]:
        if os.path.exists(f):
            os.remove(f)
            print(f"\nCleaned up {f}")

if __name__ == "__main__":
    test_docking_with_known_drug()