# check_all_jobs.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time

print("="*70)
print("🔍 CHECKING QUANTUM JOBS")
print("="*70)

service = QiskitRuntimeService()

# Bell state job ID
BELL_JOB_ID = "d71pbapamkec73a09f80"

print("\n📡 BELL STATE JOB:")
print("-"*50)
bell_job = service.job(BELL_JOB_ID)
print(f"   Job ID: {BELL_JOB_ID}")
print(f"   Status: {bell_job.status()}")
print(f"   Circuit: Bell State (Entanglement)")
print(f"   Backend: ibm_fez (156 qubits)")

try:
    position = bell_job.queue_position()
    if position:
        print(f"   Queue position: ~{position}")
except:
    pass

if bell_job.status() == 'DONE':
    result = bell_job.result()
    print("\n✅ RESULTS:")
    counts = result.quasi_dists[0]
    print(f"   Measurement distribution: {counts}")
    
    print("\n🔬 Outcomes:")
    for state, prob in sorted(counts.items()):
        binary = format(state, '02b')
        bar = '█' * int(prob * 50)
        print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}")
    
    # Expected for Bell state: 50% |00⟩, 50% |11⟩
    if 0.4 <= counts.get(0, 0) <= 0.6 and 0.4 <= counts.get(3, 0) <= 0.6:
        print("\n✅ BELL STATE CONFIRMED! Entanglement detected!")
    else:
        print("\n⚠️  Results show noise effects (normal for real hardware)")

elif bell_job.status() == 'RUNNING':
    print("\n🔄 Job is running on quantum hardware...")
    
elif bell_job.status() == 'QUEUED':
    print("\n⏳ Still in queue...")
    
elif bell_job.status() == 'ERROR':
    print(f"\n❌ Error: {bell_job.error_message()}")

# Now check for Grover job if it exists
print("\n" + "="*70)
print("🔍 GROVER SEARCH JOB")
print("="*70)

try:
    with open("grover_job_id.txt", "r") as f:
        GROVER_JOB_ID = f.read().strip()
    
    grover_job = service.job(GROVER_JOB_ID)
    print(f"   Job ID: {GROVER_JOB_ID}")
    print(f"   Status: {grover_job.status()}")
    
    if grover_job.status() == 'DONE':
        result = grover_job.result()
        counts = result.quasi_dists[0]
        
        print("\n✅ GROVER RESULTS:")
        print(f"   Measurement distribution: {counts}")
        
        # Find target state |5⟩ (binary 101)
        target = 5
        target_prob = counts.get(target, 0)
        target_binary = format(target, '03b')
        
        print(f"\n🎯 Target state |{target_binary}⟩ probability: {target_prob*100:.1f}%")
        
        # Check if Grover worked
        if target_prob > 0.5:
            print("\n✅ SUCCESS! Grover found the target state!")
        else:
            print("\n⚠️  Grover didn't find the target (noise affects real hardware)")
        
        # Show all states
        print("\n📊 All measurement outcomes:")
        for state, prob in sorted(counts.items()):
            binary = format(state, '03b')
            bar = '█' * int(prob * 40)
            print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}")
            
except FileNotFoundError:
    print("   No Grover job submitted yet")
except Exception as e:
    print(f"   Error checking Grover job: {e}")

print("\n" + "="*70)