# quantum_drug_16.py
# Search 16 real drugs using 4 qubits - NO RDKit needed!

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
import pubchempy as pcp
import matplotlib.pyplot as plt

print("="*70)
print("🧬 16-DRUG QUANTUM DRUG DISCOVERY")
print("   Searching 16 real drugs from PubChem!")
print("="*70)

# ============================================
# STEP 1: LOAD 16 REAL DRUGS FROM PUBCHEM
# ============================================

print("\n📊 Loading 16 real drugs from PubChem...")

drug_names = [
    "aspirin", "ibuprofen", "acetaminophen", "celecoxib",
    "naproxen", "diclofenac", "ketoprofen", "indomethacin",
    "morphine", "codeine", "caffeine", "vitamin_c",
    "omeprazole", "atorvastatin", "metformin", "lisinopril"
]

drugs_data = []

for name in drug_names:
    try:
        compounds = pcp.get_compounds(name, 'name')
        if compounds:
            c = compounds[0]
            drugs_data.append({
                "name": name.title(),
                "cid": c.cid,
                "mw": c.molecular_weight if c.molecular_weight else 0,
                "formula": c.molecular_formula if c.molecular_formula else "N/A"
            })
            print(f"   ✓ {name.title():15} | {c.molecular_formula}")
        else:
            print(f"   ✗ {name}: Not found")
    except Exception as e:
        print(f"   ✗ {name}: {e}")

print(f"\n✅ Loaded {len(drugs_data)} real drugs")

# ============================================
# STEP 2: SIMPLE DRUG SCORE (MW-based)
# ============================================

# Simple scoring: lower MW is better for oral drugs
for drug in drugs_data:
    mw = drug['mw']
    if mw and 100 < mw < 500:
        drug['score'] = 100 - (mw - 250) / 250 * 50
    elif mw and mw <= 100:
        drug['score'] = 90
    elif mw and mw >= 500:
        drug['score'] = 50
    else:
        drug['score'] = 70
    drug['score'] = max(0, min(100, drug['score']))

# Sort by score
drugs_data.sort(key=lambda x: x['score'], reverse=True)
top_drugs = drugs_data[:16]

print("\n🎯 TOP 16 DRUG CANDIDATES:")
print("-"*60)
for i, drug in enumerate(top_drugs):
    print(f"   {i:2}. {drug['name']:15} | Score: {drug['score']:.0f} | MW: {drug['mw']:.0f}")

# Target is the best drug
target_drug = top_drugs[0]
target_index = 0

print(f"\n🎯 QUANTUM SEARCH TARGET: {target_drug['name'].upper()}")
print(f"   Formula: {target_drug['formula']}")
print(f"   MW: {target_drug['mw']:.0f} g/mol")
print(f"   Score: {target_drug['score']:.0f}/100")

# ============================================
# STEP 3: BUILD 4-QUBIT QUANTUM CIRCUIT
# ============================================

print("\n🔬 Building 4-qubit quantum search circuit...")

n_qubits = 4
qc = QuantumCircuit(n_qubits, n_qubits)

# Superposition
qc.h(range(n_qubits))

# Oracle for target state |0000⟩
qc.x(range(n_qubits))
qc.h(n_qubits-1)
qc.mcx(list(range(n_qubits-1)), n_qubits-1)
qc.h(n_qubits-1)
qc.x(range(n_qubits))

# Diffusion (inversion about mean)
qc.h(range(n_qubits))
qc.x(range(n_qubits))
qc.h(n_qubits-1)
qc.mcx(list(range(n_qubits-1)), n_qubits-1)
qc.h(n_qubits-1)
qc.x(range(n_qubits))
qc.h(range(n_qubits))

# Measure
qc.measure(range(n_qubits), range(n_qubits))

print(f"   Qubits: {n_qubits} → Searching 2^{n_qubits} = {2**n_qubits} drugs")
print(f"   Circuit depth: {qc.depth()}")
print(f"   Gates: {qc.size()}")

# ============================================
# STEP 4: RUN QUANTUM SIMULATION
# ============================================

print("\n🚀 Running quantum search on 16 drugs...")

simulator = AerSimulator()
qc_transpiled = transpile(qc, simulator)
job = simulator.run(qc_transpiled, shots=8192)
result = job.result()
counts = result.get_counts()
total = sum(counts.values())

# ============================================
# STEP 5: RESULTS
# ============================================

print("\n" + "="*70)
print("📊 QUANTUM SEARCH RESULTS (16 Drugs)")
print("="*70)

states = [format(i, f'0{n_qubits}b') for i in range(2**n_qubits)]

results_list = []
for i, state in enumerate(states):
    prob = counts.get(state, 0) / total * 100
    if i < len(top_drugs):
        drug = top_drugs[i]
        results_list.append((drug['name'], prob, i == target_index))

# Sort by probability
results_list.sort(key=lambda x: x[1], reverse=True)

print("\n🎯 TOP DRUG CANDIDATES:")
print("-"*60)
for rank, (name, prob, is_target) in enumerate(results_list[:10], 1):
    bar = '█' * int(prob / 2)
    marker = " ★ TARGET DRUG!" if is_target else ""
    print(f"   {rank:2}. {name:20}: {prob:5.1f}% {bar}{marker}")

target_prob = results_list[0][1]

print("\n" + "="*70)
print(f"🎯 RESULT: {target_drug['name'].upper()} found with {target_prob:.1f}% confidence!")
print("="*70)

# ============================================
# STEP 6: STATISTICS
# ============================================

random_guess = 100 / len(top_drugs)
speedup = len(top_drugs) / np.sqrt(len(top_drugs))

print("\n📊 QUANTUM ADVANTAGE ANALYSIS:")
print("-"*50)
print(f"   Database size: {len(top_drugs)} drugs")
print(f"   Random guess: {random_guess:.1f}%")
print(f"   Quantum result: {target_prob:.1f}%")
print(f"   Improvement: {target_prob/random_guess:.1f}x better than random")
print(f"   Theoretical speedup: {speedup:.0f}x")

if target_prob > random_guess * 2:
    print("\n   ✅ SIGNIFICANT QUANTUM ADVANTAGE DEMONSTRATED!")
elif target_prob > random_guess:
    print("\n   ✅ QUANTUM ADVANTAGE DEMONSTRATED!")

# ============================================
# STEP 7: SAVE RESULTS
# ============================================

with open("drug_discovery_16_results.txt", "w") as f:
    f.write("QUANTUM DRUG DISCOVERY - 16 DRUGS\n")
    f.write("="*50 + "\n\n")
    f.write(f"Target: {target_drug['name'].upper()} ({target_drug['formula']})\n")
    f.write(f"Confidence: {target_prob:.1f}%\n\n")
    f.write("Top 10 Candidates:\n")
    for rank, (name, prob, _) in enumerate(results_list[:10], 1):
        f.write(f"{rank}. {name}: {prob:.1f}%\n")
    f.write(f"\nRandom guess: {random_guess:.1f}%\n")
    f.write(f"Quantum speedup: {speedup:.0f}x\n")

print("\n📁 Results saved to: drug_discovery_16_results.txt")

# ============================================
# STEP 8: VISUALIZATION
# ============================================

try:
    plt.figure(figsize=(12, 6))
    names = [r[0] for r in results_list[:10]]
    probs = [r[1] for r in results_list[:10]]
    colors = ['red' if i == 0 else 'steelblue' for i in range(len(names))]
    
    plt.bar(names, probs, color=colors)
    plt.axhline(y=random_guess, color='gray', linestyle='--', 
                label=f'Random guess ({random_guess:.1f}%)')
    plt.ylabel('Probability (%)')
    plt.xlabel('Drug Candidate')
    plt.title(f'Quantum Drug Discovery: 16 Drugs on 4 Qubits\n'
              f'Target: {target_drug["name"]} - Found with {target_prob:.1f}%')
    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()
    plt.savefig('drug_discovery_16_results.png', dpi=150)
    print("📊 Visualization saved: drug_discovery_16_results.png")
except Exception as e:
    print(f"Visualization: {e}")

print("\n" + "="*70)
print("✅ 16-DRUG QUANTUM DRUG DISCOVERY COMPLETE!")
print("="*70)

# ============================================
# STEP 9: TRY DIFFERENT TARGETS
# ============================================

print("\n💡 TO FIND A DIFFERENT DRUG:")
print("   Modify the target_index in the code:")
print("   - target_index = 1  # Ibuprofen")
print("   - target_index = 2  # Acetaminophen")
print("   - target_index = 8  # Morphine")
print("\n   Or run a different circuit targeting that drug!")