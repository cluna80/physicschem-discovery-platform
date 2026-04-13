# monitor_grover_job.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time

# Load job ID
try:
    with open("grover_job_id.txt", "r") as f:
        JOB_ID = f.read().strip()
except:
    JOB_ID = input("Enter Job ID: ")

print("="*70)
print("🔍 MONITORING GROVER JOB")
print("="*70)

service = QiskitRuntimeService()

def check_grover_job(job_id):
    job = service.job(job_id)
    status = job.status()
    
    print(f"\n📡 Job ID: {job_id}")
    print(f"📊 Status: {status}")
    
    try:
        position = job.queue_position()
        if position:
            print(f"⏳ Queue position: ~{position}")
    except:
        pass
    
    if status == 'DONE':
        print("\n✅ JOB COMPLETED!")
        result = job.result()
        counts = result.quasi_dists[0]
        
        print(f"\n📈 RESULTS:")
        print("-"*50)
        
        # Find the most likely state
        best_state = max(counts, key=counts.get)
        best_prob = counts[best_state]
        best_binary = format(best_state, f'03b')
        
        print(f"\n🎯 Most measured state: |{best_binary}⟩")
        print(f"   Probability: {best_prob*100:.1f}%")
        
        print(f"\n📊 All measurement outcomes:")
        for state, prob in sorted(counts.items()):
            binary = format(state, f'03b')
            bar = '█' * int(prob * 40)
            print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}")
        
        # Check if we found the target
        target = 5
        target_prob = counts.get(target, 0)
        print(f"\n🎯 Target |{format(target, '03b')}⟩ probability: {target_prob*100:.1f}%")
        
        if target_prob > 0.5:
            print("\n✅ SUCCESS! Grover found the target!")
        else:
            print("\n⚠️  Algorithm needs more iterations or better transpilation")
            
        return True
    
    return False

print("\n⏳ Monitoring (checking every 30 seconds)...")
print("   Press Ctrl+C to stop\n")

try:
    while True:
        done = check_grover_job(JOB_ID)
        if done:
            break
        time.sleep(30)
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped")