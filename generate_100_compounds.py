# -*- coding: utf-8 -*-
"""
Generate 100 diverse drug-like compounds for HIV screening
"""

from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski
import random

# Simple, diverse scaffolds that are known to be drug-like
simple_scaffolds = [
    "c1ccccc1",  # benzene
    "c1ccccc1C(=O)N",  # benzamide
    "c1ccccc1S(=O)(=O)N",  # benzenesulfonamide
    "c1ncccc1",  # pyridine
    "c1ccncc1",  # pyrazine
    "C1CCCCC1",  # cyclohexane
    "C1CCNCC1",  # piperidine
    "C1COCCN1",  # piperazine
]

# Functional groups to add
functional_groups = [
    "C",  # methyl
    "CC",  # ethyl
    "OC",  # methoxy
    "F",  # fluorine
    "Cl",  # chlorine
    "C(=O)N",  # amide
    "C(=O)O",  # ester
    "C(=O)C",  # ketone
    "C(N)C",  # amine
    "C(O)C",  # alcohol
]

def generate_compound():
    """Generate a single drug-like compound"""
    
    # Start with a random scaffold
    scaffold = random.choice(simple_scaffolds)
    mol = Chem.MolFromSmiles(scaffold)
    
    if not mol:
        return None
    
    # Add 1-3 functional groups
    n_groups = random.randint(1, 3)
    current_smiles = scaffold
    
    for _ in range(n_groups):
        group = random.choice(functional_groups)
        # Simple concatenation (works for basic groups)
        new_smiles = current_smiles + group
        try:
            mol = Chem.MolFromSmiles(new_smiles)
            if mol:
                current_smiles = new_smiles
        except:
            continue
    
    # Check drug-likeness
    try:
        mol = Chem.MolFromSmiles(current_smiles)
        if mol:
            mw = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd = Lipinski.NumHDonors(mol)
            hba = Lipinski.NumHAcceptors(mol)
            
            # Lipinski's Rule of 5
            if (mw < 500 and logp < 5 and hbd <= 5 and hba <= 10):
                return current_smiles
    except:
        pass
    
    return None

print("="*60)
print("Generating 100 HIV-targeted compounds")
print("="*60)

compounds = []
used_smiles = set()

for i in range(200):  # Generate extra to ensure 100 unique
    if len(compounds) >= 100:
        break
    
    smiles = generate_compound()
    if smiles and smiles not in used_smiles:
        used_smiles.add(smiles)
        compounds.append(smiles)
        
    if (i + 1) % 50 == 0:
        print(f"  Generated {len(compounds)} unique compounds...")

print(f"\nSuccessfully generated {len(compounds)} compounds")

# Save to file
with open("hiv_library_100.smi", "w") as f:
    for i, smiles in enumerate(compounds):
        f.write(f"{smiles}\tHIV_compound_{i+1:03d}\n")

print(f"\nSaved to: hiv_library_100.smi")
print("\nFirst 10 compounds:")
for i, smiles in enumerate(compounds[:10]):
    print(f"  {i+1:2d}. {smiles}")
