# -*- coding: utf-8 -*-
import subprocess
import os
from rdkit import Chem
from rdkit.Chem import AllChem
import multiprocessing as mp

def smiles_to_pdbqt(smiles, output_file):
    """Convert SMILES to 3D PDBQT"""
    try:
        # Generate 3D structure
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            
            # Save as PDB
            pdb_file = output_file.replace('.pdbqt', '.pdb')
            Chem.MolToPDBFile(mol, pdb_file)
            
            # Convert to PDBQT
            result = subprocess.run(
                ["obabel", pdb_file, "-O", output_file, "-xh"],
                capture_output=True
            )
            
            # Clean up
            if os.path.exists(pdb_file):
                os.remove(pdb_file)
            
            return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}")
    return False

def convert_batch(batch_data):
    """Convert a batch of compounds"""
    smiles_list, start_idx, output_dir = batch_data
    results = []
    
    for i, smiles in enumerate(smiles_list):
        idx = start_idx + i
        output_file = f"{output_dir}/hiv_ligand_{idx:03d}.pdbqt"
        
        if smiles_to_pdbqt(smiles, output_file):
            results.append((idx, True))
        else:
            results.append((idx, False))
        
        if (i + 1) % 20 == 0:
            print(f"  Converted {start_idx + i + 1} compounds...")
    
    return results

# Read SMILES
smiles_list = []
with open("hiv_library_100.smi", 'r') as f:
    for line in f:
        smiles = line.strip().split('\t')[0]
        smiles_list.append(smiles)

print("="*60)
print(f"Converting {len(smiles_list)} compounds to 3D PDBQT...")
print("="*60)

# Create output directory
os.makedirs("hiv_ligands", exist_ok=True)

# Process in batches
batch_size = 25
batches = []
for i in range(0, len(smiles_list), batch_size):
    batch = (smiles_list[i:i+batch_size], i, "hiv_ligands")
    batches.append(batch)

# Process sequentially (more reliable than parallel for this size)
successful = 0
for batch in batches:
    results = convert_batch(batch)
    successful += sum(1 for r in results if r[1])

print(f"\n‚úÖ Conversion complete: {successful}/{len(smiles_list)} successful")
print(f"Ì≥Å Ligands saved to: hiv_ligands/")
