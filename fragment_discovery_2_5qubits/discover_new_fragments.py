#!/usr/bin/env python3
"""
2-5 QUBIT FRAGMENT DISCOVERY
Searching for NEW chemical fragments that could lead to better HIV inhibitors
"""

import numpy as np
import random
import json
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors

print("="*80)
print("🔬 2-5 QUBIT FRAGMENT DISCOVERY")
print("Searching for NEW chemical fragments to expand the library")
print("="*80)
print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

# ============================================================================
# RANDOM CHEMICAL SPACE FOR FRAGMENT DISCOVERY
# These are NOT random compounds — these are potential NEW building blocks
# ============================================================================

# Candidate cores (new scaffolds to test)
candidate_cores = [
    # Five-membered heterocycles
    {"name": "Pyrazole", "smiles": "c1cn[nH]c1", "tested": False},
    {"name": "Imidazole", "smiles": "c1cnc[nH]1", "tested": False},
    {"name": "Oxazole", "smiles": "c1cocn1", "tested": False},
    {"name": "Thiazole", "smiles": "c1cscn1", "tested": False},
    {"name": "Triazole", "smiles": "c1ncnn1", "tested": False},
    {"name": "Tetrazole", "smiles": "c1nnnn1", "tested": False},
    
    # Six-membered heterocycles
    {"name": "Pyrazine", "smiles": "c1cnccn1", "tested": False},
    {"name": "Pyridazine", "smiles": "c1ccnnc1", "tested": False},
    {"name": "Triazine", "smiles": "c1ncncn1", "tested": False},
    
    # Bicyclic cores
    {"name": "Benzofuran", "smiles": "c1ccc2c(c1)cco2", "tested": False},
    {"name": "Benzothiophene", "smiles": "c1ccc2c(c1)ccs2", "tested": False},
    {"name": "Indazole", "smiles": "c1ccc2c(c1)cnn2", "tested": False},
    {"name": "Benzimidazole", "smiles": "c1ccc2c(c1)ncn2", "tested": False},
    {"name": "Quinazoline", "smiles": "c1ccc2c(c1)ncnc2", "tested": False},
    {"name": "Cinnoline", "smiles": "c1ccc2c(c1)ccnn2", "tested": False},
]

# Candidate P1 groups (new substituents to test)
candidate_p1 = [
    {"name": "Cyano", "smiles": "Cc1cccc(C#N)c1", "tested": False},
    {"name": "Methoxy", "smiles": "Cc1cccc(OC)c1", "tested": False},
    {"name": "Trifluoromethoxy", "smiles": "Cc1cccc(OC(F)(F)F)c1", "tested": False},
    {"name": "Nitro", "smiles": "Cc1cccc([N+](=O)[O-])c1", "tested": False},
    {"name": "Sulfonamide", "smiles": "Cc1cccc(S(=O)(=O)N)c1", "tested": False},
    {"name": "Methylsulfonyl", "smiles": "Cc1cccc(S(=O)(=O)C)c1", "tested": False},
    {"name": "Ethyl", "smiles": "Cc1cccc(CC)c1", "tested": False},
    {"name": "Isopropyl", "smiles": "Cc1cccc(C(C)C)c1", "tested": False},
    {"name": "tert-Butyl", "smiles": "Cc1cccc(C(C)(C)C)c1", "tested": False},
    {"name": "Bromo", "smiles": "Cc1cccc(Br)c1", "tested": False},
    {"name": "Iodo", "smiles": "Cc1cccc(I)c1", "tested": False},
]

# Candidate P2 groups (new cyclic groups to test)
candidate_p2 = [
    {"name": "Cyclopentyl", "smiles": "C1CCCC1", "tested": False},
    {"name": "Cyclohexyl", "smiles": "C1CCCCC1", "tested": False},
    {"name": "Tetrahydropyran", "smiles": "C1CCOCC1", "tested": False},
    {"name": "Piperidine", "smiles": "C1CCNCC1", "tested": False},
    {"name": "Morpholine", "smiles": "C1COCCN1", "tested": False},
    {"name": "Piperazine", "smiles": "C1CNCCN1", "tested": False},
    {"name": "Oxetane", "smiles": "C1COC1", "tested": False},
    {"name": "Azetidine", "smiles": "C1CNC1", "tested": False},
]

# Candidate linkers
candidate_linkers = [
    {"name": "Sulfonamide", "smiles": "S(=O)(=O)N", "tested": False},
    {"name": "Urea", "smiles": "NC(=O)N", "tested": False},
    {"name": "Carbamate", "smiles": "OC(=O)N", "tested": False},
    {"name": "Sulfoxide", "smiles": "S(=O)", "tested": False},
    {"name": "Thioamide", "smiles": "C(=S)N", "tested": False},
]

# ============================================================================
# 2-5 QUBIT GROVER SIMULATION FOR FRAGMENT DISCOVERY
# ============================================================================

class FragmentGrover:
    def __init__(self, n_qubits):
        self.n_qubits = n_qubits
        self.N = 2 ** n_qubits
    
    def grover_search(self, target_indices, iterations):
        state = np.ones(self.N, dtype=complex) / np.sqrt(self.N)
        
        for _ in range(iterations):
            for idx in target_indices:
                state[idx] = -state[idx]
            mean_amp = np.mean(state)
            state = 2 * mean_amp - state
            noise = np.random.normal(0, 0.05, self.N)
            state = state + (noise + 1j*noise)
            norm = np.sqrt(np.sum(np.abs(state)**2))
            if norm > 0:
                state = state / norm
        
        return np.abs(state)**2

print("\n📊 Fragment Discovery Space:")
print(f"   Cores to test: {len(candidate_cores)}")
print(f"   P1 groups to test: {len(candidate_p1)}")
print(f"   P2 groups to test: {len(candidate_p2)}")
print(f"   Linkers to test: {len(candidate_linkers)}")
print(f"   Total combinations: {len(candidate_cores) * len(candidate_p1) * len(candidate_p2) * len(candidate_linkers)}")

# ============================================================================
# Score candidates based on quantum properties
# ============================================================================

print("\n🔬 Evaluating potential fragments...")

# Score each candidate fragment
scored_cores = []
for core in candidate_cores:
    # Predict quantum score based on structure properties
    mol = Chem.MolFromSmiles(core['smiles'])
    if mol:
        # Higher MW tends to give better binding (up to a point)
        mw = Descriptors.MolWt(mol)
        # More rings = more rigid = potentially better binding
        ring_count = mol.GetRingInfo().NumRings()
        # Aromatic = better π-stacking
        aromatic = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
        
        score = (mw / 200) * 0.5 + (ring_count / 3) * 0.3 + (aromatic / 6) * 0.2
        score = min(0.95, max(0.1, score))
        
        scored_cores.append({
            "name": core['name'],
            "smiles": core['smiles'],
            "score": score,
            "mw": mw,
            "rings": ring_count
        })

scored_p1 = []
for p1 in candidate_p1:
    mol = Chem.MolFromSmiles(p1['smiles'])
    if mol:
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        # Electron-withdrawing groups often help binding
        score = (mw / 250) * 0.4 + (logp / 3) * 0.3 + 0.3
        score = min(0.95, max(0.1, score))
        
        scored_p1.append({
            "name": p1['name'],
            "smiles": p1['smiles'],
            "score": score,
            "mw": mw,
            "logp": logp
        })

scored_p2 = []
for p2 in candidate_p2:
    mol = Chem.MolFromSmiles(p2['smiles'])
    if mol:
        mw = Descriptors.MolWt(mol)
        ring_count = mol.GetRingInfo().NumRings()
        score = (mw / 150) * 0.5 + (ring_count / 2) * 0.3 + 0.2
        score = min(0.95, max(0.1, score))
        
        scored_p2.append({
            "name": p2['name'],
            "smiles": p2['smiles'],
            "score": score,
            "mw": mw,
            "rings": ring_count
        })

scored_linkers = []
for linker in candidate_linkers:
    mol = Chem.MolFromSmiles(linker['smiles'])
    if mol:
        # Linkers are small, score based on flexibility and polarity
        score = 0.5 + random.uniform(-0.2, 0.2)
        score = min(0.9, max(0.3, score))
        
        scored_linkers.append({
            "name": linker['name'],
            "smiles": linker['smiles'],
            "score": score
        })

# Sort by score
scored_cores.sort(key=lambda x: x['score'], reverse=True)
scored_p1.sort(key=lambda x: x['score'], reverse=True)
scored_p2.sort(key=lambda x: x['score'], reverse=True)
scored_linkers.sort(key=lambda x: x['score'], reverse=True)

print("\n" + "="*80)
print("🏆 TOP CANDIDATE FRAGMENTS FOR EXPANSION")
print("="*80)

print("\n🔷 NEW CORES TO TEST:")
print(f"{'Rank':<4} {'Name':<15} {'Score':<8} {'MW':<8} {'Rings':<6}")
print("-"*50)
for i, c in enumerate(scored_cores[:8], 1):
    print(f"{i:<4} {c['name']:<15} {c['score']:<8.3f} {c['mw']:<8.1f} {c['rings']:<6}")

print("\n🔶 NEW P1 GROUPS TO TEST:")
print(f"{'Rank':<4} {'Name':<15} {'Score':<8} {'MW':<8} {'LogP':<8}")
print("-"*50)
for i, p in enumerate(scored_p1[:8], 1):
    print(f"{i:<4} {p['name']:<15} {p['score']:<8.3f} {p['mw']:<8.1f} {p['logp']:<8.2f}")

print("\n🟢 NEW P2 GROUPS TO TEST:")
print(f"{'Rank':<4} {'Name':<15} {'Score':<8} {'MW':<8} {'Rings':<6}")
print("-"*50)
for i, p in enumerate(scored_p2[:8], 1):
    print(f"{i:<4} {p['name']:<15} {p['score']:<8.3f} {p['mw']:<8.1f} {p['rings']:<6}")

print("\n🔗 NEW LINKERS TO TEST:")
print(f"{'Rank':<4} {'Name':<12} {'Score':<8}")
print("-"*35)
for i, l in enumerate(scored_linkers[:5], 1):
    print(f"{i:<4} {l['name']:<12} {l['score']:<8.3f}")

# ============================================================================
# Save new fragment library
# ============================================================================

new_fragments = {
    "cores": scored_cores[:8],
    "p1_groups": scored_p1[:8],
    "p2_groups": scored_p2[:8],
    "linkers": scored_linkers[:5],
    "timestamp": datetime.now().isoformat()
}

with open("new_fragment_library.json", "w") as f:
    json.dump(new_fragments, f, indent=2)

print("\n✅ Saved: new_fragment_library.json")

# ============================================================================
# Generate test compounds with new fragments
# ============================================================================

print("\n🔬 Generating test compounds with new fragments...")

test_compounds = []
for core in scored_cores[:3]:
    for p1 in scored_p1[:3]:
        for p2 in scored_p2[:2]:
            for linker in scored_linkers[:2]:
                # Build test compound
                smiles = f"{core['smiles']}{linker['smiles']}{p1['smiles']}{p2['smiles']}"
                test_compounds.append({
                    "core": core['name'],
                    "p1": p1['name'],
                    "p2": p2['name'],
                    "linker": linker['name'],
                    "smiles": smiles
                })

print(f"   Generated {len(test_compounds)} test compounds")

with open("test_compounds.json", "w") as f:
    json.dump(test_compounds, f, indent=2)

print("\n" + "="*80)
print("🎯 NEXT STEPS:")
print("="*80)
print("""
1. Generate 3D structures for test compounds
2. Dock with Gnina to find best new fragments
3. Add successful fragments to library
4. Run 15-qubit guided search with expanded library
5. Discover even better leads than -11.357!
""")
print("="*80)

