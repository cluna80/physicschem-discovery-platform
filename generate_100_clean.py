# -*- coding: utf-8 -*-
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski
import random

# Simple scaffolds
simple_scaffolds = [
    "c1ccccc1",
    "c1ccccc1C(=O)N",
    "c1ccccc1S(=O)(=O)N",
    "c1ncccc1",
    "c1ccncc1",
    "C1CCCCC1",
    "C1CCNCC1",
    "C1COCCN1",
]

# Functional groups
functional_groups = [
    "C",
    "CC",
    "OC",
    "F",
    "Cl",
    "C(=O)N",
    "C(=O)O",
    "C(=O)C",
]

def generate_compound():
    scaffold = random.choice(simple_scaffolds)
    current_smiles = scaffold
    
    n_groups = random.randint(1, 2)
    for _ in range(n_groups):
        group = random.choice(functional_groups)
        new_smiles = current_smiles + group
        try:
            mol = Chem.MolFromSmiles(new_smiles)
            if mol:
                current_smiles = new_smiles
        except:
            continue
    
    try:
        mol = Chem.MolFromSmiles(current_smiles)
        if mol:
            mw = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd = Lipinski.NumHDonors(mol)
            hba = Lipinski.NumHAcceptors(mol)
            
            if mw < 500 and logp < 5 and hbd <= 5 and hba <= 10:
                return current_smiles
    except:
        pass
    
    return None

print("="*60)
print("Generating 100 HIV-targeted compounds")
print("="*60)

compounds = []
used_smiles = set()

for i in range(200):
    if len(compounds) >= 100:
        break
    
    smiles = generate_compound()
    if smiles and smiles not in used_smiles:
        used_smiles.add(smiles)
        compounds.append(smiles)
    
    if (i + 1) % 50 == 0:
        print(f"Generated {len(compounds)} unique compounds...")

print(f"\nSuccessfully generated {len(compounds)} compounds")

with open("hiv_library_100.smi", "w") as f:
    for i, smiles in enumerate(compounds):
        f.write(f"{smiles}\tHIV_compound_{i+1:03d}\n")

print(f"\nSaved to: hiv_library_100.smi")
print("\nFirst 10 compounds:")
for i, smiles in enumerate(compounds[:10]):
    print(f"  {i+1:2d}. {smiles}")
