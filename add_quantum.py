# -*- coding: utf-8 -*-
"""
Add quantum chemistry calculations to your ligands
"""
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

def calculate_properties(smiles):
    """Calculate quantum-like properties using RDKit"""
    mol = Chem.MolFromSmiles(smiles)
    if mol:
        # Calculate molecular properties
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        h_bond_donors = Descriptors.NumHDonors(mol)
        h_bond_acceptors = Descriptors.NumHAcceptors(mol)
        
        # Generate 3D conformation
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
        
        print(f"Properties: MW={mw:.1f}, LogP={logp:.2f}, H-donors={h_bond_donors}, H-acceptors={h_bond_acceptors}")
        return mol
    return None

# Example with your ligands
smiles_list = [
    "COC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC(=C(C=C3)Cl)Cl)OCCOC",  # gefitinib-like
    "COCCOC1=CC2=NC=NC(=C2C=C1OCCOC)NC3=CC=CC=C3",  # erlotinib-like
]

for smiles in smiles_list:
    print(f"\nAnalyzing: {smiles[:50]}...")
    calculate_properties(smiles)
