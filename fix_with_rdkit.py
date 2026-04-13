# -*- coding: utf-8 -*-
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
import os

def generate_3d_ligand(smiles_file, output_pdbqt):
    """Generate proper 3D coordinates using RDKit"""
    
    # Read SMILES
    with open(smiles_file, 'r') as f:
        smiles = f.readline().strip().split('\t')[0]
    
    print(f"  SMILES: {smiles[:60]}...")
    
    # Create molecule
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"  Invalid SMILES")
        return False
    
    # Add hydrogens
    mol = Chem.AddHs(mol)
    
    # Generate 3D coordinates
    try:
        # Use ETKDG method for better 3D generation
        AllChem.EmbedMolecule(mol, randomSeed=42, useRandomCoords=False)
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
        
        # Check if coordinates were generated
        conf = mol.GetConformer()
        positions = conf.GetPositions()
        
        # Verify coordinates are non-zero
        if all(abs(coord) < 0.1 for coord in positions[0]):
            # Try again with different parameters
            AllChem.EmbedMolecule(mol, randomSeed=42, useRandomCoords=True)
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)
            conf = mol.GetConformer()
            positions = conf.GetPositions()
        
        # Write to PDB file first
        temp_pdb = smiles_file.replace('.smi', '_3d.pdb')
        Chem.MolToPDBFile(mol, temp_pdb)
        
        # Convert to PDBQT using OpenBabel
        import subprocess
        result = subprocess.run(
            ["obabel", temp_pdb, "-O", output_pdbqt, "-xh"],
            capture_output=True
        )
        
        if result.returncode == 0:
            # Verify coordinates
            with open(output_pdbqt, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("ATOM"):
                        x = float(line[30:38].strip())
                        if abs(x) > 0.1:
                            print(f"  Success: Generated {len([l for l in lines if l.startswith('ATOM')])} atoms with 3D coordinates")
                            return True
                        break
            print(f"  Warning: Still zero coordinates")
            return False
        else:
            print(f"  Failed to convert to PDBQT")
            return False
            
    except Exception as e:
        print(f"  Error: {e}")
        return False

# Fix each compound
compounds = [
    ("gefitinib_like.smi", "gefitinib_like_3d.pdbqt"),
    ("erlotinib_like.smi", "erlotinib_like_3d.pdbqt"),
    ("inhibitor.smi", "inhibitor_3d.pdbqt")
]

print("="*70)
print("Generating 3D Ligands with RDKit")
print("="*70)

for smi, pdbqt in compounds:
    if os.path.exists(smi):
        print(f"\nProcessing {smi} -> {pdbqt}")
        generate_3d_ligand(smi, pdbqt)
    else:
        print(f"\n{smi} not found")

print("\n" + "="*70)
print("3D Ligands Created:")
for pdbqt in [c[1] for c in compounds]:
    if os.path.exists(pdbqt) and os.path.getsize(pdbqt) > 100:
        print(f"  {pdbqt} - OK")
    else:
        print(f"  {pdbqt} - MISSING")
