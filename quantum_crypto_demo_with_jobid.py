# quantum_crypto_demo_with_jobid.py
# EDUCATIONAL ONLY - Shows principle of quantum attacks

from qiskit import QuantumCircuit
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import time
import matplotlib.pyplot as plt

print("="*70)
print("🔐 EDUCATIONAL DEMO: Quantum Threat to Cryptography")
print("="*70)
print("\n⚠️  THIS IS AN EDUCATIONAL DEMONSTRATION")
print("   We are attacking a SIMPLIFIED 3-bit 'crypto key'")
print("   REAL Bitcoin uses 256-bit keys - FAR beyond current quantum computers")
print("="*70)

class EducationalCryptoAttack:
    def __init__(self):
        self.service = QiskitRuntimeService()
        self.backend = self.service.backend("ibm_marrakesh")
        print(f"\n✅ Connected to {self.backend.name} ({self.backend.num_qubits} qubits)")
        
    def create_simplified_crypto_key(self):
        secret_key = 5
        print(f"\n🔑 SIMPLIFIED 'Crypto Key' (3-bit): {format(secret_key, '03b')}")
        print(f"   Key space size: 8 possibilities")
        print(f"   Real Bitcoin key space: 2^256 possibilities (10^77)")
        return secret_key
    
    def classical_brute_force_demo(self, secret_key):
        print("\n" + "="*70)
        print("💻 CLASSICAL BRUTE FORCE")
        print("="*70)
        
        attempts = 0
        for guess in range(8):
            attempts += 1
            print(f"   Attempt {attempts}: Trying |{format(guess, '03b')}⟩")
            if guess == secret_key:
                print(f"   ✅ FOUND! Key is |{format(secret_key, '03b')}⟩")
                break
        
        print(f"\n📊 Classical attacks needed: {attempts} attempts")
        return attempts
    
    def quantum_grover_attack(self, secret_key):
        print("\n" + "="*70)
        print("⚛️ QUANTUM GROVER ATTACK (on REAL IBM hardware)")
        print("="*70)
        
        n_qubits = 3
        target = secret_key
        
        print(f"\n🎯 Searching for key: |{format(target, '03b')}⟩")
        
        # Build Grover circuit
        qc = QuantumCircuit(n_qubits, n_qubits)
        qc.h(range(n_qubits))
        qc.cz(0, 2)  # Oracle for |101⟩
        qc.h(range(n_qubits))
        qc.x(range(n_qubits))
        qc.h(2)
        qc.ccx(0, 1, 2)
        qc.h(2)
        qc.x(range(n_qubits))
        qc.h(range(n_qubits))
        qc.measure(range(n_qubits), range(n_qubits))
        
        # Transpile
        pm = generate_preset_pass_manager(backend=self.backend, optimization_level=2)
        qc_transpiled = pm.run(qc)
        
        # Submit job
        sampler = Sampler(self.backend)
        job = sampler.run([qc_transpiled], shots=4096)
        
        # Capture and display job ID
        job_id = job.job_id()
        print(f"\n📡 JOB ID: {job_id}")
        print(f"   Track at: https://quantum-computing.ibm.com/jobs/{job_id}")
        print(f"\n⏳ Quantum attack in queue...")
        print("   Use this command to check status:")
        print(f"   python check_job.py {job_id}")
        
        # Save job ID for later
        with open("crypto_attack_job_id.txt", "w") as f:
            f.write(job_id)
        print(f"\n💾 Job ID saved to crypto_attack_job_id.txt")
        
        return job_id, qc_transpiled
    
    def get_results(self, job_id):
        """Retrieve results once job is done"""
        job = self.service.job(job_id)
        
        print(f"\n📡 Checking job {job_id}")
        print(f"   Status: {job.status()}")
        
        if job.status() == 'DONE':
            result = job.result()
            pub_result = result[0]
            counts = pub_result.data.c.get_counts()
            return counts
        else:
            return None
    
    def analyze_results(self, counts, secret_key):
        total = sum(counts.values())
        target = format(secret_key, '03b')
        target_prob = counts.get(target, 0) / total * 100
        
        print("\n" + "="*70)
        print("📊 QUANTUM ATTACK RESULTS")
        print("="*70)
        
        print(f"\n🎯 Target key: |{target}⟩")
        print(f"📈 Quantum found: |{max(counts, key=counts.get)}⟩")
        print(f"✅ Success rate: {target_prob:.1f}%")
        
        print("\n📊 ALL KEYS:")
        for key, count in sorted(counts.items()):
            prob = count / total * 100
            bar = '█' * int(prob / 2)
            marker = " ← CORRECT!" if key == target else ""
            print(f"   |{key}⟩: {prob:5.1f}% {bar}{marker}")
        
        return target_prob

def main():
    demo = EducationalCryptoAttack()
    
    # Step 1: Create simplified key
    secret_key = demo.create_simplified_crypto_key()
    
    # Step 2: Classical brute force
    classical_attempts = demo.classical_brute_force_demo(secret_key)
    
    # Step 3: Submit quantum attack
    job_id, circuit = demo.quantum_grover_attack(secret_key)
    
    print("\n" + "="*70)
    print("📋 NEXT STEPS")
    print("="*70)
    print(f"\n1. Track your job: python check_job.py {job_id}")
    print(f"2. Or visit: https://quantum-computing.ibm.com/jobs/{job_id}")
    print("\n3. Once complete, run:")
    print(f"   python get_attack_results.py {job_id}")
    
    print("\n" + "="*70)
    print("🎓 EDUCATIONAL CONTEXT")
    print("="*70)
    print("\n🔬 This demo shows:")
    print("   ✓ Quantum computers can find patterns faster")
    print("   ✓ Same principle threatens real crypto")
    print("   ✓ Current hardware is too small (need 2,500+ qubits)")
    print("   ✓ Real Bitcoin keys are 10^77 times larger")
    print("\n✅ Bitcoin is SAFE today, but we must prepare for quantum future")

if __name__ == "__main__":
    main()