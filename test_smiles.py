# -*- coding: utf-8 -*-
from rdkit import Chem
from rdkit.Chem import AllChem

smiles = "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1"
print(f"Testing SMILES: {smiles}")

mol = Chem.MolFromSmiles(smiles)
if mol:
    print("✓ SMILES is valid")
    mol = Chem.AddHs(mol)
    print(f"  Atoms: {mol.GetNumAtoms()}")
    print(f"  Bonds: {mol.GetNumBonds()}")
    
    # Try to generate 3D
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    print("✓ 3D structure generated")
    
    # Check coordinates
    conf = mol.GetConformer()
    first_atom = conf.GetAtomPosition(0)
    print(f"  First atom coordinates: ({first_atom.x:.2f}, {first_atom.y:.2f}, {first_atom.z:.2f})")
else:
    print("✗ Invalid SMILES")
