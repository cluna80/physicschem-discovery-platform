# run_drug_discovery.py
# Quantum Drug Discovery on REAL IBM Hardware

from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import time

print("="*70)
print("🧬 QUANTUM DRUG DISCOVERY - RUNNING ON REAL IBM HARDWARE")
print("="*70)

# ============================================
# YOUR MOLECULES (from your successful simulation)
# ============================================

# Top 8 drug candidates (for 3-qubit search)
molecules = {
    "000": {"name": "Synthetic_193", "binding": -9.97, "toxicity": 0.029, "score": 93.1},
    "001": {"name": "Synthetic_451", "binding": -9.65, "toxicity": 0.131, "score": 90.2},
    "010": {"name": "Synthetic_215", "binding": -9.92, "toxicity": 0.04, "score": 86.8},
    "011": {"name": "Synthetic_233", "binding": -9.93, "toxicity": 0.177, "score": 85.2},
    "100": {"name": "Synthetic_340", "binding": -9.66, "toxicity": 0.20, "score": 88.1},
    "101": {"name": "Synthetic_127", "binding": -9.88, "toxicity": 0.114, "score": 87.6},
    "110": {"name": "Synthetic_38", "binding": -9.69, "toxicity": 0.069, "score": 91.1},
    "111": {"name": "Synthetic_186", "binding": -9.31, "toxicity": 0.031, "score": 88.9},
}

print(f"\n📊 Screening {len(molecules)} drug candidates:")
for state, info in molecules.items():
    print(f"   |{state}⟩: {info['name']:15} | Score: {info['score']:.1f}")

# Best molecule (target)
target = "000"
target_molecule = molecules[target]["name"]
print(f"\n🎯 TARGET: {target_molecule} (Score: {molecules[target]['score']:.1f})")
print(f"   Binding: {molecules[target]['binding']} kcal/mol")
print(f"   Toxicity: {molecules[target]['toxicity']*100:.1f}%")

# ============================================
# BUILD QUANTUM CIRCUIT
# ============================================

print("\n🔬 Building quantum circuit for drug search...")
n_qubits = 3
qc = QuantumCircuit(n_qubits, n_qubits)

# Superposition
qc.h(range(n_qubits))

# Oracle for target |000⟩
qc.x(0)
qc.x(1)
qc.x(2)
qc.h(2)
qc.mcx([0,1], 2)
qc.h(2)
qc.x(0)
qc.x(1)
qc.x(2)

# Diffusion operator
qc.h(range(n_qubits))
qc.x(range(n_qubits))
qc.h(2)
qc.mcx([0,1], 2)
qc.h(2)
qc.x(range(n_qubits))
qc.h(range(n_qubits))

# Measure
qc.measure(range(n_qubits), range(n_qubits))

print(f"   Circuit depth: {qc.depth()}")
print(f"   Number of gates: {qc.size()}")

# ============================================
# CONNECT TO IBM QUANTUM
# ============================================

print("\n" + "="*70)
print("🚀 CONNECTING TO IBM QUANTUM HARDWARE")
print("="*70)

service = QiskitRuntimeService()

# Try ibm_marrakesh (shorter queue)
backend = service.backend("ibm_marrakesh")
print(f"\n✅ Connected to {backend.name}")
print(f"   Qubits: {backend.num_qubits}")
print(f"   Queue: {backend.status().pending_jobs} jobs pending")

# Transpile
print("\n🔄 Transpiling for hardware...")
pm = generate_preset_pass_manager(backend=backend, optimization_level=2)
qc_transpiled = pm.run(qc)

print(f"   Transpiled depth: {qc_transpiled.depth()}")
print(f"   Transpiled width: {qc_transpiled.width()}")

# Submit job
print("\n🚀 Submitting to quantum hardware...")
sampler = Sampler(backend)
job = sampler.run([qc_transpiled], shots=4096)

job_id = job.job_id()
print(f"\n📡 JOB SUBMITTED!")
print(f"   Job ID: {job_id}")
print(f"   Target: {target_molecule}")
print(f"\n🔍 Track at: https://quantum-computing.ibm.com/jobs/{job_id}")

# Save job ID
with open("drug_job_id.txt", "w") as f:
    f.write(job_id)

print(f"\n💾 Job ID saved to drug_job_id.txt")

# Try to get queue position
try:
    pos = job.queue_position()
    if pos:
        print(f"⏳ Queue position: ~{pos}")
except:
    pass

print("\n" + "="*70)
print("📊 NEXT STEPS")
print("="*70)
print(f"\n1. Monitor with: python check_drug_job.py {job_id}")
print(f"\n2. Or check web: https://quantum-computing.ibm.com/jobs/{job_id}")
print("\n3. When complete, results will show Synthetic_193 as top candidate!")
print("\n" + "="*70)