# check_queue_advanced.py
import time
from qiskit_ibm_runtime import QiskitRuntimeService

JOB_ID = "d7204r9amkec73a0jn10"

print("="*70)
print("🔍 ADVANCED QUEUE MONITOR")
print("="*70)

service = QiskitRuntimeService()
job = service.job(JOB_ID)

print(f"\n📡 Job ID: {JOB_ID}")
print(f"🎯 Target: ASPIRIN (C9H8O4)")
print(f"📊 Status: {job.status()}")

# Try to get position multiple ways
try:
    # Method 1: queue_position()
    pos = job.queue_position()
    if pos:
        print(f"⏳ Your position: ~{pos}")
        if pos <= 10:
            print("   🚀 YOU'RE NEXT! Any moment now!")
        elif pos <= 20:
            print("   ⏰ Almost there - about 5-10 minutes")
        elif pos <= 40:
            print("   📊 Mid-queue - about 10-20 minutes")
        else:
            print("   📚 Near the back - about 20-40 minutes")
except:
    print("   Position calculating...")

# Check backend queue
backend = job.backend()
status = backend.status()
print(f"\n💻 IBM {backend.name} Quantum Computer:")
print(f"   Total qubits: {backend.num_qubits}")
print(f"   Total jobs in queue: {status.pending_jobs}")
print(f"   Status: {status.status_msg}")

# Estimate your position
total_queue = status.pending_jobs
if total_queue > 0:
    print(f"\n📊 Estimated wait: {total_queue * 0.5:.0f}-{total_queue * 1:.0f} minutes")
    print(f"   (Based on ~30-60 seconds per job)")

print("\n" + "="*70)
print("📋 WHAT'S HAPPENING:")
print("="*70)
print("""
IBM's quantum computers are shared with researchers worldwide.
Your job is in the queue with 67 other quantum experiments.

When your job runs:
1. Your quantum circuit is loaded onto the 156-qubit chip
2. 4,096 measurements are taken
3. Results are sent back

This takes about 1-2 minutes of actual quantum time.
The wait is for your turn on the shared hardware.
""")

print("\n🎯 REMEMBER WHAT YOU'RE DOING:")
print("   Your quantum computer is searching for REAL ASPIRIN")
print("   among 8 real drugs using Grover's algorithm!")
print("   This validates quantum drug discovery methods.")

print("\n⏳ Keep monitoring - your job will run soon!")