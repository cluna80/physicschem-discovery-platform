# monitor_job.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time
import sys

# Your job ID
JOB_ID = "d71pbapamkec73a09f80"

print("="*70)
print("🔍 QUANTUM JOB MONITOR")
print("="*70)

service = QiskitRuntimeService()

def check_job(job_id):
    job = service.job(job_id)
    status = job.status()
    
    print(f"\n📡 Job: {job_id}")
    print(f"📊 Status: {status}")
    
    # Try to get queue position
    try:
        position = job.queue_position()
        if position:
            print(f"⏳ Queue position: ~{position}")
    except:
        pass
    
    if status == 'QUEUED':
        print("\n⏳ Still queued...")
        return False
        
    elif status == 'RUNNING':
        print("\n🔄 Job is running on quantum hardware!")
        return False
        
    elif status == 'DONE':
        print("\n✅ JOB COMPLETED!")
        result = job.result()
        print(f"\n📈 RESULTS:")
        print(f"   Distribution: {result.quasi_dists}")
        
        # Parse Bell state results
        counts = result.quasi_dists[0]
        print("\n🔬 Measurement outcomes:")
        for state, prob in sorted(counts.items()):
            binary = format(state, '02b')
            bar = '█' * int(prob * 50)
            print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}")
        
        return True
        
    elif status == 'ERROR':
        print(f"\n❌ Job failed: {job.error_message()}")
        return True
    
    return False

# Monitor until done
print("\n⏳ Monitoring job (checking every 30 seconds)...")
print("   Press Ctrl+C to stop monitoring\n")

try:
    while True:
        done = check_job(JOB_ID)
        if done:
            break
        time.sleep(30)
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped. Check later with:")
    print(f"   python check_job.py")