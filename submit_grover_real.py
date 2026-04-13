# submit_grover_real.py
from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np

print("="*70)
print("🔍 SUBMITTING GROVER'S ALGORITHM TO REAL 156-QUBIT HARDWARE")
print("="*70)

# Connect
service = QiskitRuntimeService()
backend = service.backend("ibm_fez")
print(f"✅ Connected to {backend.name} ({backend.num_qubits} qubits)")

# Grover parameters
n_qubits = 3
target = 5
target_bin = format(target, f'0{n_qubits}b')
optimal_iters = int(np.pi/4 * np.sqrt(2**n_qubits))

print(f"\n🎯 Grover Search:")
print(f"   Search space: {2**n_qubits} items")
print(f"   Target: |{target}⟩ (binary: {target_bin})")
print(f"   Optimal iterations: {optimal_iters}")

# Build Grover circuit
qc = QuantumCircuit(n_qubits, n_qubits)

# Superposition
qc.h(range(n_qubits))

# Oracle for |101⟩ (target 5)
# Mark state where q0=1, q1=0, q2=1
qc.cz(0, 2)  # Phase flip when both q0 and q2 are 1

# Diffusion (inversion about mean)
qc.h(range(n_qubits))
qc.x(range(n_qubits))
qc.h(2)
qc.ccx(0, 1, 2)
qc.h(2)
qc.x(range(n_qubits))
qc.h(range(n_qubits))

# Measure
qc.measure(range(n_qubits), range(n_qubits))

print(f"\n📊 Circuit:")
print(f"   Depth: {qc.depth()}")
print(f"   Width: {qc.width()}")
print(f"   Gates: {qc.count_ops()}")

# Transpile for hardware
print(f"\n🔄 Transpiling for {backend.name}...")
pm = generate_preset_pass_manager(backend=backend, optimization_level=2)
qc_transpiled = pm.run(qc)

print(f"\n📊 Transpiled Circuit:")
print(f"   Depth: {qc_transpiled.depth()}")
print(f"   Width: {qc_transpiled.width()}")
print(f"   Gates: {qc_transpiled.count_ops()}")

# Submit job
print(f"\n🚀 Submitting to quantum hardware...")
sampler = Sampler(backend)
job = sampler.run([qc_transpiled], shots=4096)

print(f"\n📡 JOB SUBMITTED!")
print(f"   Job ID: {job.job_id()}")
print(f"   Status: {job.status()}")

# Save job ID
with open("grover_job_id.txt", "w") as f:
    f.write(job.job_id())

print(f"\n💾 Job ID saved to grover_job_id.txt")

# Try to get queue position
try:
    position = job.queue_position()
    if position:
        print(f"⏳ Queue position: ~{position}")
except:
    pass

print(f"\n🔍 Monitor with:")
print(f"   python check_all_jobs.py")