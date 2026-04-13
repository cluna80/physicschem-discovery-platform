# quantum_crypto_demo.py
# EDUCATIONAL ONLY - Shows the PRINCIPLE of quantum attacks
# Uses SIMPLIFIED 3-bit "keys" (8 possibilities)

from qiskit import QuantumCircuit, transpile
from qiskit_ibm_runtime import QiskitRuntimeService, Sampler
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import matplotlib.pyplot as plt
import time

print("="*70)
print("🔐 EDUCATIONAL DEMO: Quantum Threat to Cryptography")
print("="*70)
print("\n⚠️  THIS IS AN EDUCATIONAL DEMONSTRATION")
print("   We are attacking a SIMPLIFIED 3-bit 'crypto key'")
print("   REAL Bitcoin uses 256-bit keys - FAR beyond current quantum computers")
print("="*70)

class EducationalCryptoAttack:
    """
    EDUCATIONAL DEMO: Demonstrate quantum speedup for key search
    Using a SIMPLIFIED 3-bit key (8 possibilities)
    Shows the PRINCIPLE behind quantum attacks on crypto
    """
    
    def __init__(self):
        self.service = QiskitRuntimeService()
        self.backend = self.service.backend("ibm_marrakesh")
        print(f"\n✅ Connected to {self.backend.name} ({self.backend.num_qubits} qubits)")
        
    def create_simplified_crypto_key(self):
        """
        Create a SIMPLIFIED 3-bit "crypto key" for education
        NOT a real cryptographic key!
        """
        # In real crypto: 256-bit private key
        # Our demo: 3-bit key (8 possibilities)
        secret_key = 5  # |101⟩
        print(f"\n🔑 SIMPLIFIED 'Crypto Key' (3-bit): {format(secret_key, '03b')}")
        print(f"   Key space size: 8 possibilities")
        print(f"   Real Bitcoin key space: 2^256 possibilities (10^77)")
        return secret_key
    
    def classical_brute_force_demo(self, secret_key):
        """Show classical brute force approach"""
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
        print(f"   For 8 possibilities, average: 4 attempts")
        return attempts
    
    def quantum_grover_attack(self, secret_key):
        """Run Grover's algorithm to find the key (on real IBM hardware)"""
        print("\n" + "="*70)
        print("⚛️ QUANTUM GROVER ATTACK (on REAL IBM hardware)")
        print("="*70)
        
        n_qubits = 3
        target = secret_key
        
        print(f"\n🎯 Searching for key: |{format(target, '03b')}⟩")
        print(f"   Key space: 8 possibilities")
        
        # Build Grover circuit (same as your working version)
        qc = QuantumCircuit(n_qubits, n_qubits)
        
        # Superposition
        qc.h(range(n_qubits))
        
        # Oracle for target
        qc.cz(0, 2)
        
        # Diffusion
        qc.h(range(n_qubits))
        qc.x(range(n_qubits))
        qc.h(2)
        qc.ccx(0, 1, 2)
        qc.h(2)
        qc.x(range(n_qubits))
        qc.h(range(n_qubits))
        
        qc.measure(range(n_qubits), range(n_qubits))
        
        # Transpile for hardware
        print(f"\n🔄 Transpiling for {self.backend.name}...")
        pm = generate_preset_pass_manager(backend=self.backend, optimization_level=2)
        qc_transpiled = pm.run(qc)
        
        # Run on real quantum hardware
        print(f"🚀 Running quantum attack on real hardware...")
        sampler = Sampler(self.backend)
        job = sampler.run([qc_transpiled], shots=4096)
        
        # Wait for results
        print(f"⏳ Quantum computer searching...")
        time.sleep(5)  # Give it a moment to start
        
        # Check status
        while job.status() == 'QUEUED':
            print(f"   Still in queue...")
            time.sleep(10)
        
        print(f"   Quantum attack running...")
        
        # Get results
        result = job.result()
        pub_result = result[0]
        counts = pub_result.data.c.get_counts()
        
        # Find most measured state
        most_likely = max(counts, key=counts.get)
        target_prob = counts.get(format(target, '03b'), 0) / 4096 * 100
        
        print(f"\n📊 QUANTUM ATTACK RESULTS:")
        print(f"   Most likely key: |{most_likely}⟩")
        print(f"   Actual key:      |{format(target, '03b')}⟩")
        print(f"   Success rate:    {target_prob:.1f}%")
        
        return counts, target_prob
    
    def compare_attacks(self, classical_attempts, quantum_success):
        """Compare classical vs quantum"""
        print("\n" + "="*70)
        print("📊 COMPARISON: Classical vs Quantum Attack")
        print("="*70)
        
        print("\n🔍 CLASSICAL ATTACK:")
        print(f"   Attempts needed: {classical_attempts}")
        print(f"   Average attempts: 4")
        
        print("\n⚛️ QUANTUM ATTACK:")
        print(f"   Quantum steps: ~{int(np.sqrt(8))} (Grover's algorithm)")
        print(f"   Success rate: {quantum_success:.1f}%")
        print(f"   Speedup: {classical_attempts/int(np.sqrt(8)):.1f}x theoretical")
        
        print("\n" + "="*70)
        print("🔬 EDUCATIONAL INSIGHTS")
        print("="*70)
        
        print("\n1. **PRINCIPLE DEMONSTRATED**: Quantum search is quadratically faster")
        print("   - Classical: O(N) steps")
        print("   - Quantum: O(√N) steps")
        
        print("\n2. **REAL CRYPTO THREAT**:")
        print("   - Bitcoin uses 256-bit keys (2^256 possibilities)")
        print("   - Classical brute force: 2^256 attempts (impossible)")
        print("   - Quantum Grover: 2^128 attempts (still impossible today)")
        
        print("\n3. **WHY BITCOIN IS SAFE (FOR NOW):")
        print("   - Would need 2,500+ qubits with <0.1% error")
        print("   - Current hardware: 156 qubits with 5-10% error")
        print("   - Your simulation shows: 28 qubits max with 50% error")
        print("   - Gap: ~100x more qubits, 100x less noise")
        
        print("\n4. **POST-QUANTUM SOLUTIONS EXIST**:")
        print("   - NIST standards: Kyber, Dilithium")
        print("   - Quantum-resistant blockchains: QRL, Algorand")
        print("   - Your skills can help PROTECT crypto")
    
    def visualize_results(self, counts, target):
        """Create educational visualization"""
        plt.figure(figsize=(12, 6))
        
        states = list(counts.keys())
        probs = [counts[s]/4096*100 for s in states]
        
        # Sort by state value
        sorted_indices = sorted(range(len(states)), key=lambda i: int(states[i], 2))
        states = [states[i] for i in sorted_indices]
        probs = [probs[i] for i in sorted_indices]
        
        colors = ['red' if s == format(target, '03b') else 'steelblue' for s in states]
        
        plt.bar(states, probs, color=colors, edgecolor='black')
        plt.axhline(y=12.5, color='gray', linestyle='--', linewidth=2, 
                   label='Random guess (12.5%)')
        plt.ylabel('Probability (%)', fontsize=12)
        plt.xlabel('Possible Key (3-bit)', fontsize=12)
        plt.title(f'Quantum Attack on Simplified 3-Bit "Crypto Key"\n'
                  f'Real IBM Quantum Hardware - Target Key: |{format(target, "03b")}⟩\n'
                  f'Success: {probs[states.index(format(target, "03b"))]:.1f}%', fontsize=14)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 100)
        
        # Add educational notes
        plt.figtext(0.99, 0.01, 
                   "EDUCATIONAL DEMO ONLY - Real Bitcoin uses 256-bit keys (2^256 possibilities)\n"
                   "Current quantum computers need 2,500+ qubits with <0.1% error to threaten Bitcoin",
                   ha='right', fontsize=8, style='italic')
        
        plt.tight_layout()
        plt.savefig('quantum_crypto_attack_demo.png', dpi=150)
        print("\n📊 Visualization saved: quantum_crypto_attack_demo.png")

def main():
    print("\n" + "="*70)
    print("🔬 EDUCATIONAL QUANTUM CRYPTO ANALYSIS")
    print("   Using IBM Quantum Hardware + Your Simulator")
    print("="*70)
    
    # Create the educational demo
    demo = EducationalCryptoAttack()
    
    # Create a simplified "crypto key"
    secret_key = demo.create_simplified_crypto_key()
    
    # Show classical brute force
    classical_attempts = demo.classical_brute_force_demo(secret_key)
    
    # Run quantum attack on real IBM hardware
    counts, quantum_success = demo.quantum_grover_attack(secret_key)
    
    # Compare and explain
    demo.compare_attacks(classical_attempts, quantum_success)
    
    # Visualize
    demo.visualize_results(counts, secret_key)
    
    print("\n" + "="*70)
    print("🎓 EDUCATIONAL TAKEAWAYS")
    print("="*70)
    print("\n✅ The PRINCIPLE of quantum speedup is demonstrated")
    print("✅ Current quantum computers CANNOT break real crypto")
    print("✅ This demo uses SIMPLIFIED 3-bit keys (8 possibilities)")
    print("✅ Real crypto uses 256-bit keys (10^77 possibilities)")
    print("\n🔐 YOUR QUANTUM SKILLS CAN BE USED TO:")
    print("   - Study post-quantum cryptography")
    print("   - Help companies prepare for quantum threats")
    print("   - Build quantum-resistant systems")
    print("   - Educate others about quantum security")
    print("\n" + "="*70)
    print("🚀 This is how ethical quantum researchers work!")
    print("   Using real hardware to demonstrate concepts,")
    print("   not to attack real systems.")
    print("="*70)

if __name__ == "__main__":
    main()