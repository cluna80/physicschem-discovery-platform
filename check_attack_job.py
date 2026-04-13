# check_attack_job.py
import sys
from qiskit_ibm_runtime import QiskitRuntimeService

if len(sys.argv) > 1:
    job_id = sys.argv[1]
else:
    try:
        with open("crypto_attack_job_id.txt", "r") as f:
            job_id = f.read().strip()
    except:
        job_id = input("Enter Job ID: ")

print("="*70)
print("🔍 CHECKING QUANTUM CRYPTO ATTACK JOB")
print("="*70)

service = QiskitRuntimeService()
job = service.job(job_id)

print(f"\n📡 Job ID: {job_id}")
print(f"📊 Status: {job.status()}")
print(f"⚛️ Backend: {job.backend().name}")

if job.status() == 'DONE':
    print("\n✅ JOB COMPLETED!")
    result = job.result()
    pub_result = result[0]
    counts = pub_result.data.c.get_counts()
    
    total = sum(counts.values())
    print("\n📊 RESULTS:")
    for key, count in sorted(counts.items()):
        prob = count / total * 100
        bar = '█' * int(prob / 2)
        print(f"   |{key}⟩: {prob:5.1f}% {bar}")
    
    target_prob = counts.get('101', 0) / total * 100
    print(f"\n🎯 Target |101⟩ probability: {target_prob:.1f}%")
    
elif job.status() == 'QUEUED':
    print("\n⏳ Job is queued. Check back later.")
    try:
        pos = job.queue_position()
        if pos:
            print(f"   Queue position: ~{pos}")
    except:
        pass
        
elif job.status() == 'RUNNING':
    print("\n🔄 Job is running on quantum hardware!")
    
elif job.status() == 'ERROR':
    print(f"\n❌ Error: {job.error_message()}")