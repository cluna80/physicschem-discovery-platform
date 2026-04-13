# -*- coding: utf-8 -*-
import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem

def smiles_to_pdbqt(smiles, output_file):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            
            pdb_file = output_file.replace('.pdbqt', '.pdb')
            Chem.MolToPDBFile(mol, pdb_file)
            
            result = subprocess.run(
                ["obabel", pdb_file, "-O", output_file, "-xh"],
                capture_output=True
            )
            
            if os.path.exists(pdb_file):
                os.remove(pdb_file)
            
            return result.returncode == 0
    except:
        pass
    return False

print("="*60)
print("Converting compounds to PDBQT")
print("="*60)

smiles_list = []
with open("hiv_library_100.smi", 'r') as f:
    for line in f:
        if line.strip():
            smiles = line.strip().split('\t')[0]
            smiles_list.append(smiles)

print(f"Found {len(smiles_list)} compounds to convert")

os.makedirs("hiv_ligands", exist_ok=True)

successful = 0
for i, smiles in enumerate(smiles_list, 1):
    output_file = f"hiv_ligands/ligand_{i:03d}.pdbqt"
    
    if smiles_to_pdbqt(smiles, output_file):
        successful += 1
        print(f"{i:3d}. OK - {output_file}")
    else:
        print(f"{i:3d}. FAIL - {output_file}")
    
    if i % 20 == 0:
        print(f"  Progress: {i}/{len(smiles_list)}")

print(f"\nDone: {successful}/{len(smiles_list)} successful")
