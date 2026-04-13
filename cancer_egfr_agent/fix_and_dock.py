# fix_and_dock.py
import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import rdMolDescriptors

def prepare_and_dock(smiles, name="test"):
    """Properly prepare ligand and dock"""
    
    print(f"\n{'='*60}")
    print(f"Processing: {smiles[:80]}")
    print(f"{'='*60}")
    
    # Step 1: Create molecule
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        print("✗ Invalid SMILES")
        return None
    
    # Step 2: Sanitize and fix
    try:
        Chem.SanitizeMol(mol)
        print("✓ Molecule sanitized")
    except Exception as e:
        print(f"⚠ Sanitization issue: {e}")
        # Try to fix
        try:
            mol = Chem.MolFromSmiles(smiles, sanitize=False)
            Chem.SanitizeMol(mol, Chem.SANITIZE_ALL)
            print("✓ Fixed after sanitization")
        except:
            print("✗ Cannot fix molecule")
            return None
    
    # Step 3: Add hydrogens and generate 3D
    mol = Chem.AddHs(mol)
    print(f"✓ Added hydrogens, total atoms: {mol.GetNumAtoms()}")
    
    # Step 4: Generate 3D conformation
    try:
        # Try ETKDGv3 first
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        print("✓ 3D structure generated (ETKDGv3)")
    except:
        try:
            # Fallback to original ETKDG
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            print("✓ 3D structure generated (ETKDG)")
        except:
            print("✗ Failed to generate 3D structure")
            return None
    
    # Step 5: Optimize geometry
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=1000)
        print("✓ Geometry optimized")
    except:
        try:
            # Try UFF as fallback
            AllChem.UFFOptimizeMolecule(mol, maxIters=1000)
            print("✓ Geometry optimized (UFF)")
        except:
            print("⚠ Geometry optimization failed, using raw embedding")
    
    # Step 6: Save as PDB
    pdb_file = f"{name}.pdb"
    Chem.MolToPDBFile(mol, pdb_file)
    print(f"✓ Saved to {pdb_file}")
    
    # Step 7: Convert to PDBQT with obabel (cleaner than meeko)
    pdbqt_file = f"{name}.pdbqt"
    cmd_obabel = [
        "obabel", pdb_file, "-O", pdbqt_file,
        "-h",  # Add hydrogens
        "--partialcharge", "gasteiger"
    ]
    
    result = subprocess.run(cmd_obabel, capture_output=True, text=True)
    if os.path.exists(pdbqt_file):
        # Check if file has content
        with open(pdbqt_file, 'r') as f:
            content = f.read()
            if len(content) > 100:
                print(f"✓ Converted to PDBQT ({len(content)} bytes)")
            else:
                print(f"⚠ PDBQT file too small: {len(content)} bytes")
                return None
    else:
        print(f"✗ Failed to create PDBQT")
        print(f"   Error: {result.stderr}")
        return None
    
    # Step 8: Check if receptor exists
    receptor = "egfr_4hjo.pdbqt"
    if not os.path.exists(receptor):
        print(f"✗ Receptor not found: {receptor}")
        print("  Run preparation commands first:")
        print("  grep '^ATOM' 4HJO.pdb | grep ' A ' > 4HJO_chainA.pdb")
        print("  grep -v 'HOH' 4HJO_chainA.pdb > 4HJO_protein.pdb")
        print("  obabel 4HJO_protein.pdb -O egfr_4hjo.pdbqt -xr")
        return None
    
    # Step 9: Run docking
    out_file = f"{name}_docked.pdbqt"
    cmd_vina = [
        "vina",
        "--receptor", receptor,
        "--ligand", pdbqt_file,
        "--center_x", "22.0",
        "--center_y", "0.5",
        "--center_z", "48.0",
        "--size_x", "24.0",
        "--size_y", "24.0",
        "--size_z", "24.0",
        "--exhaustiveness", "32",
        "--num_modes", "5",
        "--out", out_file
    ]
    
    print("\nRunning Vina docking...")
    result = subprocess.run(cmd_vina, capture_output=True, text=True)
    
    # Print Vina output
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)
    
    # Parse results
    if os.path.exists(out_file):
        with open(out_file, 'r') as f:
            content = f.read()
            
        # Find the affinity table
        in_table = False
        affinities = []
        for line in content.split('\n'):
            if "mode |   affinity" in line:
                in_table = True
                continue
            if in_table and line.strip() and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        mode = int(parts[0])
                        affinity = float(parts[1])
                        affinities.append(affinity)
                        print(f"Mode {mode}: {affinity:.2f} kcal/mol")
                    except:
                        pass
        
        if affinities:
            best = min(affinities)
            print(f"\n✓ BEST AFFINITY: {best:.2f} kcal/mol")
            return best
        else:
            print("\n✗ No binding poses found")
            return None
    else:
        print(f"\n✗ Docking failed, output file not created")
        return None

# Test with your best candidate
smiles = "C#Cc1c(OCCO)c(-c2cc(C=CC(=O)NCC)c3ncncc3c2)c(C)c2nccnc12"
print("DOCKING DE NOVO EGFR CANDIDATE")
print("="*60)
result = prepare_and_dock(smiles, "gen27_candidate")

if result:
    print(f"\n{'='*60}")
    print(f"SUCCESS! Binding affinity: {result:.2f} kcal/mol")
    print(f"{'='*60}")
    
    if result < -7.0:
        print("✓ Excellent binding - drug candidate quality")
    elif result < -5.0:
        print("⚠ Moderate binding - needs optimization")
    else:
        print("✗ Weak binding - check docking setup")
else:
    print("\nFailed to dock. Check errors above.")