# watch_jobs.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time
import os

print("="*70)
print("🔭 QUANTUM JOB OBSERVATORY")
print("="*70)
print("Watching your jobs on ibm_fez (156 qubits)")
print("Press Ctrl+C to stop\n")

service = QiskitRuntimeService()

BELL_JOB = "d71pbapamkec73a09f80"
GROVER_JOB = "d71pesmqdfbc73d18qi0"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_queue_position(job):
    try:
        pos = job.queue_position()
        return f"~{pos}" if pos else "Unknown"
    except:
        return "Calculating..."

try:
    while True:
        clear_screen()
        print("="*70)
        print(f"🔭 QUANTUM JOB OBSERVATORY - {time.strftime('%H:%M:%S')}")
        print("="*70)
        
        # Bell State Job
        bell = service.job(BELL_JOB)
        bell_status = bell.status()
        bell_pos = get_queue_position(bell)
        
        print(f"\n📡 BELL STATE JOB (Entanglement)")
        print("-"*50)
        print(f"   ID: {BELL_JOB}")
        print(f"   Status: {bell_status}")
        if bell_status == 'QUEUED':
            print(f"   Queue: {bell_pos}")
        elif bell_status == 'RUNNING':
            print("   🔄 Running on quantum hardware!")
        elif bell_status == 'DONE':
            print("   ✅ COMPLETED!")
        
        # Grover Job
        grover = service.job(GROVER_JOB)
        grover_status = grover.status()
        grover_pos = get_queue_position(grover)
        
        print(f"\n🔍 GROVER SEARCH JOB (Target |5⟩)")
        print("-"*50)
        print(f"   ID: {GROVER_JOB}")
        print(f"   Status: {grover_status}")
        if grover_status == 'QUEUED':
            print(f"   Queue: {grover_pos}")
        elif grover_status == 'RUNNING':
            print("   🔄 Running on quantum hardware!")
        elif grover_status == 'DONE':
            print("   ✅ COMPLETED!")
        
        # Show queue info for ibm_fez
        backend = service.backend("ibm_fez")
        print(f"\n💻 IBM_FEZ STATUS")
        print("-"*50)
        print(f"   Status: {backend.status().status_msg}")
        print(f"   Pending jobs: {backend.status().pending_jobs}")
        
        print("\n" + "="*70)
        print("⏳ Checking again in 30 seconds...")
        time.sleep(30)
        
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped!")
    print("\nCheck results manually with:")
    print(f"   python check_all_jobs.py")