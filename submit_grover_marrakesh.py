# submit_grover_marrakesh.py
from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np

print("="*70)
print("🚀 SUBMITTING GROVER TO ibm_marrakesh (FAST QUEUE!)")
print("="*70)

# Connect
service = QiskitRuntimeService()

# Use ibm_marrakesh - only 1 job ahead!
backend = service.backend("ibm_marrakesh")
print(f"\n✅ Connected to {backend.name}")
print(f"   Qubits: {backend.num_qubits}")
print(f"   Jobs in queue: {backend.status().pending_jobs} ⚡⚡⚡")
print(f"   Status: {backend.status().status_msg}")

# Grover parameters
n_qubits = 3
target = 5
target_bin = format(target, f'0{n_qubits}b')

print(f"\n🎯 Grover Search:")
print(f"   Search space: 8 items (|000⟩ to |111⟩)")
print(f"   Target state: |{target}⟩ (binary: {target_bin})")
print(f"   Optimal iterations: {int(np.pi/4 * np.sqrt(2**n_qubits))}")

# Build Grover circuit
qc = QuantumCircuit(n_qubits, n_qubits)

# Step 1: Superposition
qc.h(range(n_qubits))

# Step 2: Oracle for |101⟩ (target 5)
# This flips the phase of the target state
qc.cz(0, 2)  # Multi-controlled Z gate

# Step 3: Diffusion operator (inversion about mean)
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
print(f"   Depth: {qc.depth()}")
print(f"   Width: {qc.width()}")
print(f"   Gates: {dict(qc.count_ops())}")

# Transpile for ibm_marrakesh
print(f"\n🔄 Transpiling for {backend.name}...")
pm = generate_preset_pass_manager(backend=backend, optimization_level=2)
qc_transpiled = pm.run(qc)

print(f"\n📊 Transpiled Circuit:")
print(f"   Depth: {qc_transpiled.depth()}")
print(f"   Width: {qc_transpiled.width()}")
print(f"   Gates: {dict(qc_transpiled.count_ops())}")

# Submit to quantum hardware
print(f"\n🚀 Submitting to quantum hardware...")
sampler = Sampler(backend)
job = sampler.run([qc_transpiled], shots=4096)

print(f"\n✅ JOB SUBMITTED!")
print(f"   Job ID: {job.job_id()}")
print(f"   Backend: {backend.name}")
print(f"   Status: {job.status()}")

# Save job ID
with open("grover_marrakesh_job.txt", "w") as f:
    f.write(job.job_id())

print(f"\n💾 Job ID saved to grover_marrakesh_job.txt")

# Get queue position
try:
    pos = job.queue_position()
    if pos:
        print(f"⏳ Queue position: ~{pos} (should be VERY fast!)")
except:
    pass

print(f"\n🔍 Monitor with:")
print(f"   python check_marrakesh_job.py")