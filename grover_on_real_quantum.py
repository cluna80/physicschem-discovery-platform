# grover_on_real_quantum.py
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import time

print("="*70)
print("🔍 GROVER'S ALGORITHM ON REAL 156-QUBIT QUANTUM COMPUTER")
print("="*70)

# Connect to IBM Quantum
service = QiskitRuntimeService()

# Get the 156-qubit quantum computer
backend = service.backend("ibm_fez")
print(f"\n✅ Connected to {backend.name}")
print(f"   Qubits: {backend.num_qubits}")
print(f"   Status: {backend.status().status_msg}")
print(f"   Jobs in queue: {backend.status().pending_jobs}")

# Grover's algorithm parameters
n_qubits = 3  # Search 8 items
target = 5    # Looking for |5⟩ (binary 101)

print(f"\n🎯 Grover Search Parameters:")
print(f"   Search space: {2**n_qubits} items")
print(f"   Target state: |{target}⟩ (binary: {format(target, f'0{n_qubits}b')})")
print(f"   Optimal iterations: {int(np.pi/4 * np.sqrt(2**n_qubits))}")

# Build Grover circuit
qc = QuantumCircuit(n_qubits, n_qubits)

# Step 1: Superposition
qc.h(range(n_qubits))

# Step 2: Oracle for target state
# Mark |101⟩ (qubit 0=1, qubit1=0, qubit2=1)
qc.cz(0, 2)  # Phase flip when both q0 and q2 are 1

# Step 3: Diffusion operator
qc.h(range(n_qubits))
qc.x(range(n_qubits))
qc.h(2)
qc.ccx(0, 1, 2)
qc.h(2)
qc.x(range(n_qubits))
qc.h(range(n_qubits))

# Step 4: Measure
qc.measure(range(n_qubits), range(n_qubits))

print(f"\n📊 Circuit Statistics:")
print(f"   Original depth: {qc.depth()}")
print(f"   Original width: {qc.width()}")

# Transpile for hardware
print(f"\n🔄 Transpiling for {backend.name}...")
pm = generate_preset_pass_manager(backend=backend, optimization_level=2)
qc_transpiled = pm.run(qc)

print(f"\n📊 Transpiled Statistics:")
print(f"   Depth: {qc_transpiled.depth()}")
print(f"   Width: {qc_transpiled.width()}")
print(f"   Gate count: {qc_transpiled.count_ops()}")

# Submit to real quantum hardware
print(f"\n🚀 Submitting to quantum hardware...")
sampler = Sampler(backend)
job = sampler.run([qc_transpiled], shots=4096)

print(f"\n📡 JOB SUBMITTED!")
print(f"   Job ID: {job.job_id()}")
print(f"   Status: {job.status()}")

# Save job ID for later
with open("grover_job_id.txt", "w") as f:
    f.write(job.job_id())

print(f"\n💾 Job ID saved to grover_job_id.txt")
print(f"\n🔍 Monitor with:")
print(f"   python monitor_grover_job.py")

# Try to get queue position
try:
    position = job.queue_position()
    if position:
        print(f"⏳ Queue position: ~{position}")
except:
    pass