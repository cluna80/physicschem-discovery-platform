# first_quantum_job.py
from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler

print("="*60)
print("🚀 YOUR FIRST REAL QUANTUM CIRCUIT")
print("="*60)

# Connect
service = QiskitRuntimeService()

# Get available real quantum computers
backends = [b for b in service.backends() 
            if b.status().operational and 'simulator' not in b.name]

if backends:
    backend = backends[0]
    print(f"✅ Using REAL quantum hardware: {backend.name} ({backend.num_qubits} qubits)")
else:
    # Fallback to simulator
    backends = [b for b in service.backends() if b.status().operational]
    backend = backends[0]
    print(f"⚠️  No real hardware available, using simulator: {backend.name}")

# Create a Bell state circuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0,1], [0,1])

print(f"📊 Circuit depth: {qc.depth()}")
print("🚀 Submitting to quantum hardware...")

# Transpile for the backend
qc_transpiled = transpile(qc, backend)

# Run on REAL hardware
sampler = Sampler(backend)
job = sampler.run([qc_transpiled], shots=1024)

print(f"📡 Job ID: {job.job_id()}")
print("⏳ Waiting for results...")

# Wait for result
result = job.result()
print(f"\n✅ Results!")
print(f"📈 Measurement distribution: {result.quasi_dists[0]}")

# Interpret results
counts = result.quasi_dists[0]
print("\n🔬 Results interpretation:")
for state, prob in counts.items():
    if state == 0:
        print(f"   |00⟩: {prob*100:.1f}%")
    elif state == 1:
        print(f"   |01⟩: {prob*100:.1f}%")
    elif state == 2:
        print(f"   |10⟩: {prob*100:.1f}%")
    elif state == 3:
        print(f"   |11⟩: {prob*100:.1f}%")