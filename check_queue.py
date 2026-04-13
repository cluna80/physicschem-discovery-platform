# check_queue.py
from qiskit_ibm_runtime import QiskitRuntimeService

JOB_ID = "d7204r9amkec73a0jn10"

service = QiskitRuntimeService()
job = service.job(JOB_ID)

print("="*60)
print("🔍 JOB QUEUE STATUS")
print("="*60)

print(f"\n📡 Job ID: {JOB_ID}")
print(f"📊 Status: {job.status()}")
print(f"🎯 Target: ASPIRIN")

try:
    pos = job.queue_position()
    if pos:
        print(f"⏳ Position in queue: ~{pos}")
        if pos < 10:
            print("   🚀 Almost there! Will run soon!")
        elif pos < 30:
            print("   ⏰ Mid-queue - about 10-20 minutes")
        else:
            print("   📚 Near the back - may take 20-40 minutes")
except:
    print("   Calculating position...")

# Get backend info
backend = job.backend()
status = backend.status()
print(f"\n💻 Backend: {backend.name}")
print(f"   Total qubits: {backend.num_qubits}")
print(f"   Queue length: {status.pending_jobs} jobs total")
print(f"   Status: {status.status_msg}")

print("\n" + "="*60)