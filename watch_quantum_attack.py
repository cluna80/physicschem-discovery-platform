# watch_quantum_attack.py
import time
import os
from qiskit_ibm_runtime import QiskitRuntimeService

# Your job ID
JOB_ID = "d71v764scmvs73ab898g"

print("="*70)
print("🔭 WATCHING QUANTUM CRYPTO ATTACK")
print("="*70)
print(f"\n📡 Job ID: {JOB_ID}")
print("⏳ Checking every 30 seconds...")
print("   Press Ctrl+C to stop monitoring\n")

service = QiskitRuntimeService()

try:
    while True:
        # Clear screen for fresh view
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("="*70)
        print(f"🔭 QUANTUM CRYPTO ATTACK MONITOR - {time.strftime('%H:%M:%S')}")
        print("="*70)
        
        job = service.job(JOB_ID)
        status = job.status()
        
        print(f"\n📡 Job ID: {JOB_ID}")
        print(f"📊 Status: {status}")
        print(f"⚛️ Backend: {job.backend().name}")
        
        try:
            pos = job.queue_position()
            if pos:
                print(f"⏳ Queue position: ~{pos}")
        except:
            pass
        
        if status == 'QUEUED':
            print("\n⏳ In queue - your attack is waiting...")
            print("   IBM's quantum computers are shared globally")
            print("   Expect 5-30 minute wait time")
            
        elif status == 'RUNNING':
            print("\n🔄 RUNNING ON QUANTUM HARDWARE!")
            print("   Your attack is executing on real qubits")
            print("   Results coming in 1-2 minutes...")
            
        elif status == 'DONE':
            print("\n✅ ATTACK COMPLETED!")
            print("   Getting results...")
            
            # Get results
            result = job.result()
            pub_result = result[0]
            counts = pub_result.data.c.get_counts()
            total = sum(counts.values())
            
            print("\n" + "="*70)
            print("📊 ATTACK RESULTS")
            print("="*70)
            
            target_prob = counts.get('101', 0) / total * 100
            
            print("\n🎯 Target key |101⟩:")
            print(f"   Found with {target_prob:.1f}% probability")
            
            print("\n📈 All keys:")
            for key in sorted(counts.keys()):
                prob = counts[key] / total * 100
                bar = '█' * int(prob / 2)
                marker = " ← CORRECT!" if key == "101" else ""
                print(f"   |{key}⟩: {prob:5.1f}% {bar}{marker}")
            
            print("\n" + "="*70)
            print("🔬 EDUCATIONAL INTERPRETATION")
            print("="*70)
            
            if target_prob > 30:
                print("\n✅ QUANTUM SPEEDUP DEMONSTRATED!")
                print(f"   {target_prob:.1f}% > random guess (12.5%)")
                print("   Same principle threatens real crypto keys")
            else:
                print("\n⚠️  Hardware noise affected results")
                print("   This is expected on current NISQ devices")
            
            print("\n🔐 REAL CRYPTO CONTEXT:")
            print("   • Bitcoin uses 256-bit keys (10^77 possibilities)")
            print("   • Need 2,500+ perfect qubits to break Bitcoin")
            print("   • Current hardware: 156 qubits with noise")
            print("   • Bitcoin is SAFE today")
            
            print("\n🎓 YOUR SKILLS:")
            print("   ✓ Ran quantum algorithm on real hardware")
            print("   ✓ Demonstrated crypto threat principle")
            print("   ✓ Can help prepare for quantum future")
            
            # Save results
            with open("crypto_attack_results.txt", "w") as f:
                f.write(f"QUANTUM CRYPTO ATTACK RESULTS\n")
                f.write(f"Job ID: {JOB_ID}\n")
                f.write(f"Backend: ibm_marrakesh\n\n")
                for key in sorted(counts.keys()):
                    prob = counts[key] / total * 100
                    f.write(f"|{key}⟩: {prob:.1f}%\n")
                f.write(f"\nTarget |101⟩: {target_prob:.1f}%\n")
            
            print("\n📁 Results saved to: crypto_attack_results.txt")
            
            break
            
        elif status == 'ERROR':
            print(f"\n❌ Error: {job.error_message()}")
            break
        
        print("\n" + "="*70)
        print("⏳ Checking again in 30 seconds...")
        time.sleep(30)
        
except KeyboardInterrupt:
    print("\n\n👋 Monitoring stopped. Check later with:")
    print(f"   python check_attack_job.py {JOB_ID}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")