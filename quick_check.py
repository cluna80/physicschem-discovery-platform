# quick_check.py
from qiskit_ibm_runtime import QiskitRuntimeService

print("="*60)
print("🔍 QUICK JOB STATUS CHECK")
print("="*60)

service = QiskitRuntimeService()

# Your job IDs
bell_job = service.job("d71pbapamkec73a09f80")
grover_job = service.job("d71pesmqdfbc73d18qi0")

print(f"\n📡 Bell State Job: {bell_job.status()}")
print(f"🔍 Grover Job: {grover_job.status()}")

# Check queue positions
try:
    bell_pos = bell_job.queue_position()
    grover_pos = grover_job.queue_position()
    if bell_pos:
        print(f"\n⏳ Bell State queue position: ~{bell_pos}")
    if grover_pos:
        print(f"⏳ Grover queue position: ~{grover_pos}")
except:
    pass

# Check ibm_marrakesh (shorter queue!)
print("\n" + "="*60)
print("🚀 FASTER OPTION: ibm_marrakesh")
print("="*60)

marrakesh = service.backend("ibm_marrakesh")
print(f"✅ ibm_marrakesh: {marrakesh.num_qubits} qubits")
print(f"   Jobs in queue: {marrakesh.status().pending_jobs}")
print(f"   Status: {marrakesh.status().status_msg}")

if marrakesh.status().pending_jobs < 100:
    print("\n💡 This backend has a MUCH shorter queue!")
    print("   Consider submitting to ibm_marrakesh instead")