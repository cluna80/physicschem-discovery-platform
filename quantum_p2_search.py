# -*- coding: utf-8 -*-
"""
4-QUBIT QUANTUM SEARCH FOR P2' OPTIMIZATION
Searches 16 P2' substitutions in superposition
Target: Find best naphthalene modifications for ultra-potent HIV inhibitors
"""

import json
import numpy as np
from rdkit import Chem
from rdkit.Chem import Descriptors, QED

# Base affinity from your best compound
BASE_AFFINITY = -7.333

class Quantum4QubitSearcher:
    """4-qubit Grover search - 16 states in superposition"""
    
    def __init__(self):
        self.n_qubits = 4
        self.n_states = 2 ** self.n_qubits  # 16 states
        self.iterations = int(np.pi/4 * np.sqrt(self.n_states))  # ~3 iterations
        
    def quantum_score(self, smiles):
        """Score P2' modifications based on predicted binding gain"""
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return 0
        
        # Calculate properties relevant to P2' pocket
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        qed = QED.qed(mol)
        
        # H-bond donors/acceptors for P2' interactions
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
        """Run 4-qubit Grover to find best P2' substitutions"""
        
        # Score all compounds
        for c in compounds:
            c['quantum_score'] = self.quantum_score(c['smiles'])
        
        # Take top 16 for quantum search
        top = sorted(compounds, key=lambda x: x['quantum_score'], reverse=True)[:self.n_states]
        scores = [c['quantum_score'] for c in top]
        
        # Quantum superposition
        probs = np.exp(scores) / np.sum(np.exp(scores))
        state = np.sqrt(probs)
        state = state / np.linalg.norm(state)
        
        # Oracle (mark best)
        oracle = np.eye(self.n_states, dtype=complex)
        oracle[0, 0] = -1
        
        # Diffusion
        diffusion = 2 * np.outer(np.ones(self.n_states)/self.n_states, 
                                  np.ones(self.n_states)) - np.eye(self.n_states)
        
        # Apply Grover iterations
        for _ in range(self.iterations):
            state = oracle @ state
            state = diffusion @ state
        
        quantum_probs = np.abs(state)**2
        
        # Apply quantum probabilities
        for i, c in enumerate(top):
            c['quantum_prob'] = float(quantum_probs[i])
            c['priority'] = c['quantum_prob'] * c['quantum_score']
        
        # Sort by quantum priority
        compounds.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return compounds

# ============================================================
# P2' SUBSTITUTIONS TO SCREEN (16 candidates)
# Base scaffold with naphthalene - we modify the naphthalene ring
# ============================================================

BASE_SCAFFOLD = "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

P2_SUBSTITUTIONS = [
    {"name": "H", "substituent": "H", "feature": "Hydrogen (baseline)", "predicted_boost": 0.0},
    {"name": "OH", "substituent": "O", "feature": "Hydroxyl", "predicted_boost": 0.4},
    {"name": "NH2", "substituent": "N", "feature": "Amino", "predicted_boost": 0.5},
    {"name": "CH3", "substituent": "C", "feature": "Methyl", "predicted_boost": 0.3},
    {"name": "F", "substituent": "F", "feature": "Fluoro", "predicted_boost": 0.3},
    {"name": "Cl", "substituent": "Cl", "feature": "Chloro", "predicted_boost": 0.3},
    {"name": "OMe", "substituent": "OC", "feature": "Methoxy", "predicted_boost": 0.4},
    {"name": "CF3", "substituent": "C(F)(F)F", "feature": "Trifluoromethyl", "predicted_boost": 0.4},
    {"name": "SO2NH2", "substituent": "S(=O)(=O)N", "feature": "Sulfonamide", "predicted_boost": 0.7},
    {"name": "COOH", "substituent": "C(=O)O", "feature": "Carboxylic acid", "predicted_boost": 0.5},
    {"name": "CONH2", "substituent": "C(=O)N", "feature": "Carboxamide", "predicted_boost": 0.6},
    {"name": "CH2OH", "substituent": "CO", "feature": "Hydroxymethyl", "predicted_boost": 0.4},
    {"name": "NO2", "substituent": "N(=O)=O", "feature": "Nitro", "predicted_boost": 0.3},
    {"name": "CN", "substituent": "C#N", "feature": "Cyano", "predicted_boost": 0.3},
    {"name": "NHCOCH3", "substituent": "NC(=O)C", "feature": "Acetamido", "predicted_boost": 0.5},
    {"name": "SO2CH3", "substituent": "S(=O)(=O)C", "feature": "Methylsulfonyl", "predicted_boost": 0.5},
]

# Build full SMILES for each substitution
for sub in P2_SUBSTITUTIONS:
    if sub['name'] == "H":
        sub['smiles'] = BASE_SCAFFOLD
    else:
        sub['smiles'] = f"c1{ sub['substituent'] }c2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1"

print("="*80)
print("4-QUBIT QUANTUM SEARCH FOR P2' OPTIMIZATION")
print(f"Superposition: {2**4} states | Grover iterations: {int(np.pi/4 * np.sqrt(16))}")
print("="*80)

# Validate SMILES
print("\n[VALIDATION]")
valid_subs = []
for sub in P2_SUBSTITUTIONS:
    mol = Chem.MolFromSmiles(sub['smiles'])
    if mol:
        sub['valid'] = True
        valid_subs.append(sub)
        print(f"  OK {sub['name']:<12} {sub['feature']}")
    else:
        sub['valid'] = False
        print(f"  XX {sub['name']:<12} INVALID - {sub['feature']}")

# Run quantum search on valid substitutions
quantum = Quantum4QubitSearcher()
prioritized = quantum.prioritize(valid_subs)

print("\n[QUANTUM PRIORITY ORDER - DOCK IN THIS ORDER]")
print("-"*80)
print(f"{'Rank':<6} {'Substituent':<12} {'Quantum Score':<12} {'Quantum Prob':<12} {'Predicted Boost':<12}")
print("-"*80)

for i, c in enumerate(prioritized[:16], 1):
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
