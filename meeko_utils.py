# -*- coding: utf-8 -*-
"""
Meeko-based PDBQT generation - NO obabel, NO Mode 1 +10.000 issues!
"""

import os
from rdkit import Chem
from rdkit.Chem import AllChem
from meeko import MoleculePreparation, PDBQTWriterLegacy

def smiles_to_pdbqt_meeko(smiles, output_file, random_seed=42):
    """
    Convert SMILES to PDBQT using Meeko (proper format, no obabel issues)
    """
    try:
        # Create molecule from SMILES
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"  Error: Invalid SMILES: {smiles}")
            return False
        
        # Add hydrogens
        mol = Chem.AddHs(mol)
        
        # Generate 3D coordinates
        AllChem.EmbedMolecule(mol, randomSeed=random_seed)
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
        
        # Prepare with Meeko
        preparator = MoleculePreparation()
        setups = preparator.prepare(mol)
        
        if not setups:
            print(f"  Error: Meeko preparation failed for {smiles}")
            return False
        
        # Write PDBQT
        pdbqt_string, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        
        with open(output_file, 'w') as f:
            f.write(pdbqt_string)
        
        # Verify the file has content
        if os.path.getsize(output_file) > 100:
            return True
        else:
            print(f"  Warning: {output_file} is too small")
            return False
            
    except Exception as e:
        print(f"  Error in Meeko conversion: {e}")
        return False

# Test function
if __name__ == "__main__":
    # Test with CURE_7G_007
    test_smiles = "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1"
    test_file = "test_meeko.pdbqt"
    
    print("Testing Meeko PDBQT generation...")
    if smiles_to_pdbqt_meeko(test_smiles, test_file):
        print(f"✓ Successfully created {test_file}")
        
        # Check the file content
        with open(test_file, 'r') as f:
            lines = f.readlines()
            atoms = [l for l in lines if l.startswith("ATOM")]
            print(f"  Atoms: {len(atoms)}")
            print(f"  First atom: {atoms[0][:60]}...")
        
        # Clean up
        os.remove(test_file)
    else:
        print("✗ Failed to generate PDBQT")
