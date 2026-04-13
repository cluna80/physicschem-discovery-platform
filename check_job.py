# check_job.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time

# Your job ID from above
JOB_ID = "d71pbapamkec73a09f80"

print("="*60)
print("🔍 CHECKING QUANTUM JOB STATUS")
print("="*60)

service = QiskitRuntimeService()

# Get job
job = service.job(JOB_ID)

print(f"\n📡 Job ID: {job.job_id()}")
print(f"📊 Status: {job.status()}")

# Get queue position
try:
    position = job.queue_position()
    if position:
        print(f"⏳ Queue position: {position}")
except:
    pass

# If completed, get results
if job.status() == 'DONE':
    result = job.result()
    print(f"\n✅ RESULTS!")
    print(f"📈 Distribution: {result.quasi_dists}")
    
    # Parse results
    counts = result.quasi_dists[0]
    print("\n🔬 Measurement outcomes:")
    for state, prob in counts.items():
        binary = format(state, '02b')
        print(f"   |{binary}⟩: {prob*100:.1f}%")
        
elif job.status() == 'RUNNING':
    print("\n⏳ Job is still running...")
    print("   Check back in a few minutes")
    
elif job.status() == 'QUEUED':
    print("\n⏳ Job is queued...")
    print("   There are jobs ahead of you")
    
elif job.status() == 'ERROR':
    print("\n❌ Job failed")
    print(f"   Error: {job.error_message()}")