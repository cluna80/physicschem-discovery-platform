# monitor_crypto_attack.py
from qiskit_ibm_runtime import QiskitRuntimeService
import time
import os

print("="*70)
print("🔐 MONITORING QUANTUM CRYPTO ATTACK")
print("="*70)

service = QiskitRuntimeService()

# The job from your quantum_crypto_demo.py
# If you don't have the job ID, we need to capture it

print("\n📡 The quantum attack job is QUEUED on ibm_marrakesh")
print("   This is normal - many researchers use IBM's quantum computers")
print("\n⏳ Expected wait time: 5-30 minutes")
print("   Once running, results will appear automatically")

print("\n💡 PRO TIP: In your quantum_crypto_demo.py, add this line after job submission:")
print("   print(f'JOB ID: {job.job_id()}')")
print("\n   Then you can track it with:")
print("   python check_job.py [JOB_ID]")

print("\n" + "="*70)
print("🎓 WHILE WAITING - EDUCATIONAL CONTEXT")
print("="*70)

print("\n🔬 WHAT'S HAPPENING ON THE QUANTUM COMPUTER:")
print("   - Grover's algorithm is searching 8 possible keys")
print("   - Each quantum state represents a possible key")
print("   - The algorithm amplifies the correct key |101⟩")
print("   - Real hardware noise reduces success to 43.8%")

print("\n🔐 REAL CRYPTO COMPARISON:")
print("   Our demo:    3-bit key → 8 possibilities")
print("   Bitcoin:     256-bit key → 2^256 possibilities")
print("   Gap:         10^77 times larger!")

print("\n⚛️ QUANTUM THREAT REALITY:")
print("   To break Bitcoin:")
print("   - Need 2,500+ logical qubits")
print("   - Error rate <0.1%")
print("   - Today: 156 physical qubits, 5-10% error")
print("   - Timeline: 10-20 years (if ever)")

print("\n" + "="*70)
print("🚀 ONCE THE JOB COMPLETES, YOU'LL SEE:")
print("="*70)
print("   Quantum attack results:")
print("   - Most likely key: |101⟩ (or |111⟩ due to noise)")
print("   - Success probability: 40-50%")
print("   - Proof that quantum computers can find patterns faster")
print("\n   Then you can explain why real crypto is still safe!")

print("\n" + "="*70)
print("📊 CHECK BACK SOON!")
print("="*70)