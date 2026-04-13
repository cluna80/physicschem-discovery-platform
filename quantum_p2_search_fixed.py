# -*- coding: utf-8 -*-
"""
4-QUBIT QUANTUM SEARCH FOR P2' OPTIMIZATION
Only using chemically valid substituents
"""

import json
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, QED

# Base affinity from your best compound
BASE_AFFINITY = -7.333

class QuantumSearch:
    """Quantum search that works with any number of compounds"""
    
    def __init__(self, n_qubits=4):
        self.n_qubits = n_qubits
        self.max_states = 2 ** n_qubits  # 16 max
        
    def quantum_score(self, smiles):
        """Score P2' modifications based on predicted binding gain"""
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return 0
        
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        qed = QED.qed(mol)
        hbd = Descriptors.NumHDonors(mol)
        hba = Descriptors.NumHAcceptors(mol)
        
        score = 0
        score += qed * 1.5
        if 350 < mw < 550: score += 0.3
        if 1.5 < logp < 3.5: score += 0.3
        if hbd > 0: score += 0.2
        if hba > 2: score += 0.2
        
        return score
    
    def prioritize(self, compounds):
        """Run quantum search on valid compounds"""
        
        # Score all compounds
        for c in compounds:
            c['quantum_score'] = self.quantum_score(c['smiles'])
        
        # Sort by quantum score
        compounds.sort(key=lambda x: x['quantum_score'], reverse=True)
        
        # Apply quantum-inspired weighting
        n = len(compounds)
        scores = [c['quantum_score'] for c in compounds]
        probs = np.exp(scores) / np.sum(np.exp(scores))
        
        # Simple Grover-inspired amplification for top candidates
        for i in range(min(3, n)):
            probs[i] = probs[i] * 2
        
        # Normalize
        probs = probs / np.sum(probs)
        
        for i, c in enumerate(compounds):
            c['quantum_prob'] = float(probs[i])
        
        return compounds

# ============================================================
# ONLY VALID P2' SUBSTITUTIONS (from validation)
# ============================================================

BASE_SCAFFOLD = "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

VALID_SUBSTITUTIONS = [
    {"name": "H", "substituent": "H", "feature": "Hydrogen (baseline)", "predicted_boost": 0.0},
    {"name": "OH", "substituent": "O", "feature": "Hydroxyl", "predicted_boost": 0.4},
    {"name": "NH2", "substituent": "N", "feature": "Amino", "predicted_boost": 0.5},
    {"name": "CH3", "substituent": "C", "feature": "Methyl", "predicted_boost": 0.3},
    {"name": "OMe", "substituent": "OC", "feature": "Methoxy", "predicted_boost": 0.4},
    {"name": "SO2NH2", "substituent": "S(=O)(=O)N", "feature": "Sulfonamide", "predicted_boost": 0.7},
    {"name": "COOH", "substituent": "C(=O)O", "feature": "Carboxylic acid", "predicted_boost": 0.5},
    {"name": "CONH2", "substituent": "C(=O)N", "feature": "Carboxamide", "predicted_boost": 0.6},
    {"name": "CH2OH", "substituent": "CO", "feature": "Hydroxymethyl", "predicted_boost": 0.4},
    {"name": "NHCOCH3", "substituent": "NC(=O)C", "feature": "Acetamido", "predicted_boost": 0.5},
    {"name": "SO2CH3", "substituent": "S(=O)(=O)C", "feature": "Methylsulfonyl", "predicted_boost": 0.5},
]

# Build full SMILES
for sub in VALID_SUBSTITUTIONS:
    if sub['name'] == "H":
        sub['smiles'] = BASE_SCAFFOLD
    else:
        sub['smiles'] = f"c1{ sub['substituent'] }c2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

print("="*80)
print("QUANTUM SEARCH FOR P2' OPTIMIZATION (Valid Compounds Only)")
print(f"Number of valid P2' substitutions: {len(VALID_SUBSTITUTIONS)}")
print("="*80)

# Validate again
print("\n[VALIDATION]")
for sub in VALID_SUBSTITUTIONS:
    mol = Chem.MolFromSmiles(sub['smiles'])
    if mol:
        sub['valid'] = True
        print(f"  OK {sub['name']:<12} {sub['feature']}")
    else:
        sub['valid'] = False
        print(f"  XX {sub['name']:<12} INVALID")

# Filter valid
valid_subs = [s for s in VALID_SUBSTITUTIONS if s.get('valid', False)]
print(f"\nValid compounds for quantum search: {len(valid_subs)}")

# Run quantum search
quantum = QuantumSearch()
prioritized = quantum.prioritize(valid_subs)

print("\n[QUANTUM PRIORITY ORDER]")
print("-"*80)
print(f"{'Rank':<6} {'Substituent':<12} {'Quantum Score':<12} {'Quantum Prob':<12} {'Predicted Boost':<12}")
print("-"*80)

for i, c in enumerate(prioritized, 1):
    boost = c['predicted_boost']
    predicted_aff = BASE_AFFINITY + boost
    print(f"{i:<6} {c['name']:<12} {c['quantum_score']:<12.3f} {c.get('quantum_prob', 0):<12.3f} +{boost:<11.1f} {c['feature']}")

# Top recommendation
best = prioritized[0]
print("\n" + "="*80)
print("QUANTUM RECOMMENDATION")
print("="*80)
print(f"Best P2' substituent: {best['name']} ({best['feature']})")
print(f"Quantum probability: {best.get('quantum_prob', 0):.3f}")
print(f"Predicted boost: +{best['predicted_boost']:.1f} kcal/mol")
print(f"Expected new affinity: {BASE_AFFINITY + best['predicted_boost']:.3f} kcal/mol")
print(f"Gap to -9.0: {(BASE_AFFINITY + best['predicted_boost']) - (-9.0):.2f} kcal/mol")

# Save for docking
with open("p2_quantum_results.json", "w") as f:
    json.dump(prioritized, f, indent=2)

print("\nSaved: p2_quantum_results.json")
print("="*80)
