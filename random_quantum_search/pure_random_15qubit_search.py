#!/usr/bin/env python3
"""
PURE RANDOM 15-QUBIT QUANTUM SEARCH
No fragment library — exploring completely random chemical space
Testing if quantum can discover novel scaffolds without prior knowledge
"""

import numpy as np
import random
import json
import time
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors

print("="*80)
print("🎲 PURE RANDOM 15-QUBIT QUANTUM SEARCH")
print("Testing: Can quantum discover novel scaffolds without prior knowledge?")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ============================================================================
# COMPLETELY RANDOM CHEMICAL BUILDING BLOCKS
# No bias from previous discoveries — pure random chemical space
# ============================================================================

# Random atoms (the most basic building blocks)
random_atoms = [
    {"name": "Carbon", "smiles": "C"},
    {"name": "Nitrogen", "smiles": "N"},
    {"name": "Oxygen", "smiles": "O"},
    {"name": "Sulfur", "smiles": "S"},
    {"name": "Fluorine", "smiles": "F"},
    {"name": "Chlorine", "smiles": "Cl"},
    {"name": "Bromine", "smiles": "Br"},
]

# Random ring systems (completely arbitrary)
random_rings = [
    {"name": "Cyclopropane", "smiles": "C1CC1"},
    {"name": "Cyclobutane", "smiles": "C1CCC1"},
    {"name": "Cyclopentane", "smiles": "C1CCCC1"},
    {"name": "Cyclohexane", "smiles": "C1CCCCC1"},
    {"name": "Benzene", "smiles": "c1ccccc1"},
    {"name": "Pyridine", "smiles": "c1ccncc1"},
    {"name": "Pyrimidine", "smiles": "c1cncnc1"},
    {"name": "Furan", "smiles": "c1ccoc1"},
    {"name": "Thiophene", "smiles": "c1ccsc1"},
    {"name": "Pyrrole", "smiles": "c1cc[nH]c1"},
]

# Random linkers (completely arbitrary connections)
random_linkers = [
    {"name": "Single bond", "smiles": "-"},
    {"name": "Double bond", "smiles": "="},
    {"name": "Amide", "smiles": "C(=O)N"},
    {"name": "Ester", "smiles": "C(=O)O"},
    {"name": "Ether", "smiles": "O"},
    {"name": "Sulfide", "smiles": "S"},
    {"name": "Sulfonamide", "smiles": "S(=O)(=O)N"},
    {"name": "Urea", "smiles": "NC(=O)N"},
]

# Random functional groups (completely arbitrary)
random_groups = [
    {"name": "Methyl", "smiles": "C"},
    {"name": "Ethyl", "smiles": "CC"},
    {"name": "Hydroxy", "smiles": "O"},
    {"name": "Amino", "smiles": "N"},
    {"name": "Carboxyl", "smiles": "C(=O)O"},
    {"name": "Aldehyde", "smiles": "C=O"},
    {"name": "Ketone", "smiles": "C(=O)C"},
    {"name": "Nitro", "smiles": "N(=O)=O"},
    {"name": "Cyano", "smiles": "C#N"},
    {"name": "Trifluoromethyl", "smiles": "C(F)(F)F"},
]

# ============================================================================
# Quantum Search Setup
# ============================================================================

class PureRandomQuantumSearch:
    def __init__(self, n_qubits=15):
        self.n_qubits = n_qubits
        self.N = 2 ** n_qubits  # 32,768 states
        self.optimal_iters = int(np.pi / 4 * np.sqrt(self.N))
        print(f"\n📊 Random Search Space: {self.N:,} states")
        print(f"   Grover iterations: {self.optimal_iters}")
    
    def encode_random_state(self, atom_idx, ring_idx, linker_idx, group_idx):
        """Encode completely random chemical combination into quantum state"""
        n_atoms = len(random_atoms)
        n_rings = len(random_rings)
        n_linkers = len(random_linkers)
        n_groups = len(random_groups)
        
        idx = atom_idx
        idx = idx * n_rings + ring_idx
        idx = idx * n_linkers + linker_idx
        idx = idx * n_groups + group_idx
        return idx
    
    def decode_random_state(self, idx):
        """Decode quantum state to random chemical structure"""
        n_atoms = len(random_atoms)
        n_rings = len(random_rings)
        n_linkers = len(random_linkers)
        n_groups = len(random_groups)
        
        group = idx % n_groups
        idx //= n_groups
        linker = idx % n_linkers
        idx //= n_linkers
        ring = idx % n_rings
        idx //= n_rings
        atom = idx % n_atoms
        
        # Build completely random SMILES
        # This has no relation to any known drug scaffold
        smiles = f"{random_rings[ring]['smiles']}{random_linkers[linker]['smiles']}{random_atoms[atom]['smiles']}{random_groups[group]['smiles']}"
        
        return {
            "atom": random_atoms[atom]['name'],
            "ring": random_rings[ring]['name'],
            "linker": random_linkers[linker]['name'],
            "group": random_groups[group]['name'],
            "smiles": smiles
        }
    
    def random_grover_search(self):
        """Pure random Grover search — no target bias"""
        # Choose random target states (no chemical bias)
        random_targets = random.sample(range(self.N), 100)
        
        # Initialize uniform superposition
        state = np.ones(self.N, dtype=complex) / np.sqrt(self.N)
        
        # Grover iterations
        for _ in range(self.optimal_iters):
            # Oracle: flip random targets
            for idx in random_targets:
                state[idx] = -state[idx]
            
            # Diffusion: inversion about mean
            mean_amp = np.mean(state)
            state = 2 * mean_amp - state
            
            # Add realistic noise (5%)
            noise = np.random.normal(0, 0.05, self.N)
            noise_complex = noise + 1j * noise
            state = state + noise_complex
            
            # Normalize
            norm = np.sqrt(np.sum(np.abs(state)**2))
            if norm > 0:
                state = state / norm
        
        return np.abs(state)**2

# ============================================================================
# Run Pure Random Quantum Search
# ============================================================================

print("\n🔬 Running pure random 15-qubit Grover search...")
print("   (No prior knowledge — exploring completely random chemical space)")

quantum = PureRandomQuantumSearch(n_qubits=15)
start_time = time.time()
probabilities = quantum.random_grover_search()
elapsed = time.time() - start_time

print(f"   Completed in {elapsed:.2f} seconds")

# Get top random states
top_indices = np.argsort(probabilities)[::-1][:50]
top_probs = probabilities[top_indices]

# Generate random candidates
random_candidates = []
for idx, prob in zip(top_indices, top_probs):
    if prob > 0.001:  # Keep states with >0.1% probability
        chem = quantum.decode_random_state(idx)
        random_candidates.append({
            "quantum_probability": float(prob),
            **chem
        })

print(f"\n🎲 Generated {len(random_candidates)} random quantum candidates")

# Save results
with open("random_quantum_candidates.json", "w") as f:
    json.dump(random_candidates, f, indent=2)

# Show top random candidates
print("\n" + "="*80)
print("TOP 20 RANDOM QUANTUM-DISCOVERED CANDIDATES")
print("(Completely random — no prior knowledge)")
print("="*80)
print(f"\n{'Rank':<4} {'Ring':<12} {'Linker':<12} {'Atom':<8} {'Group':<12} {'Prob':<8}")
print("-"*70)

for i, c in enumerate(random_candidates[:20]):
    print(f"{i+1:<4} {c['ring']:<12} {c['linker']:<12} {c['atom']:<8} {c['group']:<12} {c['quantum_probability']:<8.4f}")

print("\n" + "="*80)
print("🔬 NEXT STEP: Dock these random candidates with Gnina")
print("   python3 dock_random_candidates.py")
print("="*80)

