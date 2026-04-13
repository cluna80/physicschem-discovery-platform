# test_connection.py
from qiskit_ibm_runtime import QiskitRuntimeService

print("="*60)
print("🔌 CONNECTING TO IBM QUANTUM")
print("="*60)

# This will now work with your saved account
service = QiskitRuntimeService()

print("✅ Connected!")

# List available quantum computers
print("\n🚀 Available Quantum Computers:")
print("-"*50)

for backend in service.backends():
    status = backend.status()
    if status.operational:
        print(f"✅ {backend.name}: {backend.num_qubits} qubits")
        print(f"   - Jobs in queue: {status.pending_jobs}")
        print(f"   - Status: {status.status_msg}")
    else:
        print(f"❌ {backend.name}: {backend.num_qubits} qubits (offline)")

# Get best available
operational = [b for b in service.backends() if b.status().operational]
if operational:
    best = operational[0]
    print(f"\n🎯 Best available: {best.name} ({best.num_qubits} qubits)")