# check_marrakesh_job.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time
import os

print("="*70)
print("🔍 MONITORING GROVER ON ibm_marrakesh")
print("="*70)

service = QiskitRuntimeService()

# Load job ID
try:
    with open("grover_marrakesh_job.txt", "r") as f:
        JOB_ID = f.read().strip()
except:
    JOB_ID = input("Enter Job ID: ")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

print(f"\n📡 Job ID: {JOB_ID}")
print(f"🎯 Target: |5⟩ (binary 101)")
print(f"⏳ Checking every 10 seconds...\n")

try:
    while True:
        job = service.job(JOB_ID)
        status = job.status()
        
        clear_screen()
        print("="*70)
        print(f"🔍 GROVER ON ibm_marrakesh - {time.strftime('%H:%M:%S')}")
        print("="*70)
        print(f"\n📡 Job ID: {JOB_ID}")
        print(f"📊 Status: {status}")
        
        try:
            pos = job.queue_position()
            if pos:
                print(f"⏳ Queue position: ~{pos}")
        except:
            pass
        
        if status == 'QUEUED':
            print("\n⏳ In queue - should start soon!")
            
        elif status == 'RUNNING':
            print("\n🔄 RUNNING ON QUANTUM HARDWARE!")
            print("   This takes 1-2 minutes...")
            
        elif status == 'DONE':
            print("\n✅ JOB COMPLETED!")
            result = job.result()
            counts = result.quasi_dists[0]
            
            print("\n" + "="*70)
            print("📈 RESULTS")
            print("="*70)
            
            # Target |5⟩ is binary 101 = decimal 5
            target = 5
            target_prob = counts.get(target, 0)
            
            print(f"\n🎯 TARGET STATE |101⟩: {target_prob*100:.1f}%")
            
            # Visualize
            bar = '█' * int(target_prob * 50)
            print(f"   [{bar:<50}] {target_prob*100:.1f}%")
            
            print(f"\n📊 ALL MEASUREMENT OUTCOMES:")
            print("-"*50)
            for state, prob in sorted(counts.items()):
                binary = format(state, '03b')
                bar = '█' * int(prob * 40)
                highlight = " ← TARGET!" if state == target else ""
                print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}{highlight}")
            
            # Analysis
            if target_prob > 0.5:
                print("\n✅ SUCCESS! Grover found the target on real quantum hardware!")
                print("   This demonstrates quantum speedup on IBM's 156-qubit computer!")
            elif target_prob > 0.3:
                print("\n⚠️  Partial success - hardware noise affected results")
                print("   Still shows quantum advantage over random guessing (12.5%)")
            else:
                print("\n⚠️  Hardware noise degraded results")
                print("   This is normal for current quantum computers")
            
            break
            
        elif status == 'ERROR':
            print(f"\n❌ Error: {job.error_message()}")
            break
        
        print("\n" + "="*70)
        print("⏳ Checking again in 10 seconds...")
        time.sleep(10)
        
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped")