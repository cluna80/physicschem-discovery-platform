# test_known_inhibitor.py
import subprocess
from rdkit import Chem
from rdkit.Chem import AllChem
import os

def test_docking_with_known_drug():
    """Test if docking works with erlotinib"""
    
    # Erlotinib SMILES (known EGFR inhibitor)
    erlotinib_smiles = "COc1ccc2c(c1)c(Nc1nccn3ccccc13)ncn2"
    
    print("Testing docking with erlotinib...")
    
    # Generate 3D structure
    mol = Chem.MolFromSmiles(erlotinib_smiles)
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    AllChem.MMFFOptimizeMolecule(mol)
    
    # Save as PDB
    Chem.MolToPDBFile(mol, "erlotinib_test.pdb")
    
    # Convert to PDBQT with obabel
    cmd_obabel = ["obabel", "erlotinib_test.pdb", "-O", "erlotinib_test.pdbqt", 
                  "--partialcharge", "gasteiger"]
    subprocess.run(cmd_obabel, capture_output=True)
    
    # Check if your receptor exists
    receptor = "egfr_receptor.pdbqt"
    if not os.path.exists(receptor):
        print(f"ERROR: {receptor} not found!")
        return
    
    # Dock with vina
    cmd_vina = [
        "vina",
        "--receptor", receptor,
        "--ligand", "erlotinib_test.pdbqt",
        "--center_x", "22.0",
        "--center_y", "2.5",
        "--center_z", "48.5",
        "--size_x", "20.0",
        "--size_y", "20.0",
        "--size_z", "20.0",
        "--exhaustiveness", "16",
        "--num_modes", "5",
        "--out", "erlotinib_docked.pdbqt"
    ]
    
    result = subprocess.run(cmd_vina, capture_output=True, text=True)
    
    # Parse affinity
    print("\nVina output:")
    for line in result.stdout.split('\n'):
        if line.strip() and line[0].isdigit():
            parts = line.split()
            if len(parts) >= 2:
                print(f"Mode {parts[0]}: {parts[1]} kcal/mol")
    
    # Check if we got reasonable affinity
    lines = result.stdout.split('\n')
    for line in lines:
        if "Affinity" in line and "kcal/mol" in line and not "Writing" in line:
            print(f"\n{line.strip()}")

if __name__ == "__main__":
    test_docking_with_known_drug()