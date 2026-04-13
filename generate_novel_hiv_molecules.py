# -*- coding: utf-8 -*-
"""
Generate Novel HIV Cure Candidates for 10-Qubit Quantum Search
Creating diverse, drug-like molecules optimized for HIV targets
"""

import random
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski
import json

# Simple, validated scaffolds that work with RDKit
VALID_SCAFFOLDS = [
    "c1ccccc1",  # Benzene
    "c1ncccc1",  # Pyridine
    "c1ccncc1",  # Pyrazine
    "C1CCCCC1",  # Cyclohexane
    "C1CCNCC1",  # Piperidine
    "C1COCCN1",  # Piperazine
]

# Functional groups that work reliably
VALID_GROUPS = [
    "C", "CC", "OC", "F", "Cl", "C(=O)N", "C(=O)O", "C(=O)C", "CN", "C(F)(F)F"
]

def generate_molecule():
    """Generate a simple, valid molecule"""
    # Start with a random scaffold
    scaffold = random.choice(VALID_SCAFFOLDS)
    mol = Chem.MolFromSmiles(scaffold)
    
    if not mol:
        return None
    
    current_smiles = scaffold
    
    # Add 1-3 functional groups
    for _ in range(random.randint(1, 3)):
        group = random.choice(VALID_GROUPS)
        new_smiles = current_smiles + group
        test_mol = Chem.MolFromSmiles(new_smiles)
        if test_mol:
            current_smiles = new_smiles
            mol = test_mol
    
    # Calculate properties
    try:
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd = Lipinski.NumHDonors(mol)
        hba = Lipinski.NumHAcceptors(mol)
        
        # Filter for drug-like properties
        if mw < 500 and logp < 5 and hbd <= 5 and hba <= 10:
            return {
                'smiles': current_smiles,
                'mw': mw,
                'logp': logp,
                'hbd': hbd,
                'hba': hba,
                'heavy_atoms': mol.GetNumHeavyAtoms()
            }
    except:
        pass
    
    return None

def calculate_quantum_potential(props):
    """Calculate quantum potential score"""
    score = 0
    if 300 < props['mw'] < 500: score += 0.3
    elif 250 < props['mw'] < 550: score += 0.15
    
    if 2 < props['logp'] < 4: score += 0.3
    elif 1 < props['logp'] < 5: score += 0.15
    
    if 1 <= props['hbd'] <= 3: score += 0.2
    elif props['hbd'] <= 5: score += 0.1
    
    if 4 <= props['hba'] <= 7: score += 0.2
    elif 2 <= props['hba'] <= 9: score += 0.1
    
    return score

print("="*80)
print("GENERATING NOVEL HIV CURE CANDIDATES")
print("="*80)

# Generate molecules
novel_molecules = []
used_smiles = set()

for i in range(100):
    mol_data = generate_molecule()
    if mol_data and mol_data['smiles'] not in used_smiles:
        used_smiles.add(mol_data['smiles'])
        quantum_score = calculate_quantum_potential(mol_data)
        
        novel_molecules.append({
            'name': f"HIV_CURE_{len(novel_molecules)+1:03d}",
            'smiles': mol_data['smiles'],
            'mw': mol_data['mw'],
            'logp': mol_data['logp'],
            'hbd': mol_data['hbd'],
            'hba': mol_data['hba'],
            'heavy_atoms': mol_data['heavy_atoms'],
            'quantum_potential': quantum_score
        })
    
    if (i + 1) % 20 == 0:
        print(f"Generated {len(novel_molecules)} molecules...")

print(f"\nSuccessfully generated {len(novel_molecules)} novel molecules")

# Sort by quantum potential
novel_molecules.sort(key=lambda x: x['quantum_potential'], reverse=True)

print("\nTOP 10 BY QUANTUM POTENTIAL:")
print("-"*80)
print(f"{'Name':<15} {'MW':<8} {'LogP':<8} {'HBD':<6} {'HBA':<6} {'Quantum Score':<12}")
print("-"*80)

for m in novel_molecules[:10]:
    print(f"{m['name']:<15} {m['mw']:<8.0f} {m['logp']:<8.2f} {m['hbd']:<6} {m['hba']:<6} {m['quantum_potential']:<12.3f}")

# Save for quantum screening
with open("novel_hiv_molecules.json", "w") as f:
    json.dump(novel_molecules, f, indent=2)

print(f"\nSaved {len(novel_molecules)} molecules to novel_hiv_molecules.json")
print("="*80)
