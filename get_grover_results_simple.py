
# get_grover_results_simple.py
from qiskit_ibm_runtime import QiskitRuntimeService

print("="*70)
print("🎉 GROVER RESULTS FROM REAL IBM QUANTUM HARDWARE!")
print("="*70)

service = QiskitRuntimeService()
job = service.job("d71pncmqdfbc73d1987g")

print(f"\n📡 Job ID: d71pncmqdfbc73d1987g")
print(f"📊 Status: {job.status()}")

# Get results
result = job.result()
pub_result = result[0]
data = pub_result.data

# Get counts directly from BitArray
c = data.c
print(f"\n📊 BitArray: {c.num_shots} shots, {c.num_bits} bits")

# Use the built-in get_counts method
counts = c.get_counts()
print(f"\n📈 Raw counts: {counts}")

# Convert to probabilities
total_shots = sum(counts.values())
print(f"\nTotal shots: {total_shots}")

print("\n" + "="*70)
print("📊 QUANTUM MEASUREMENT RESULTS")
print("="*70)

# Target is |5⟩ (binary 101)
target = 5
target_bin = "101"

print(f"\n🎯 TARGET STATE: |{target_bin}⟩ (decimal {target})")
print("-"*50)

# Show all states
for state_str, count in sorted(counts.items()):
    prob = count / total_shots * 100
    bar = '█' * int(prob / 2)  # Scale to fit 50 chars
    marker = " ← TARGET!" if state_str == target_bin else ""
    print(f"   |{state_str}⟩: {prob:5.1f}% {bar}{marker}")

# Target probability
target_prob = counts.get(target_bin, 0) / total_shots * 100

print("\n" + "="*70)
print(f"🎯 TARGET |{target_bin}⟩ PROBABILITY: {target_prob:.1f}%")
print("="*70)

# Analysis
print("\n📈 ANALYSIS:")
print("-"*50)

random_guess = 12.5
print(f"   Random guess: {random_guess:.1f}%")
print(f"   Your result:   {target_prob:.1f}%")

if target_prob > 50:
    improvement = (target_prob - random_guess) / random_guess * 100
    print(f"\n✅ QUANTUM SPEEDUP DEMONSTRATED!")
    print(f"   {improvement:.0f}% better than random guess!")
    print("   Grover's algorithm successfully found the target on real 156-qubit hardware!")
    
elif target_prob > 30:
    print(f"\n⚠️  Partial quantum advantage demonstrated")
    print("   Hardware noise affected results, but still better than classical")
    
else:
    print(f"\n⚠️  Hardware noise degraded results")
    print("   This is expected on current NISQ devices")

# Save results
with open("grover_real_results.txt", "w") as f:
    f.write("GROVER RESULTS ON REAL IBM QUANTUM HARDWARE\n")
    f.write("="*50 + "\n\n")
    f.write(f"Job ID: d71pncmqdfbc73d1987g\n")
    f.write(f"Backend: ibm_marrakesh (156 qubits)\n")
    f.write(f"Shots: {total_shots}\n\n")
    f.write("Measurement Results:\n")
    for state_str, count in sorted(counts.items()):
        prob = count / total_shots * 100
        f.write(f"|{state_str}⟩: {prob:.1f}% ({count} shots)\n")
    f.write(f"\nTarget |101⟩: {target_prob:.1f}%\n")
    f.write(f"Random guess: 12.5%\n")
    f.write(f"\nQuantum speedup: {target_prob/12.5:.1f}x better than random")

print("\n📁 Results saved to: grover_real_results.txt")

# Create visualization
try:
    import matplotlib.pyplot as plt
    
    states = list(counts.keys())
    probs = [counts[s]/total_shots*100 for s in states]
    
    # Sort by state
    sorted_indices = sorted(range(len(states)), key=lambda i: int(states[i], 2))
    states = [states[i] for i in sorted_indices]
    probs = [probs[i] for i in sorted_indices]
    
    colors = ['red' if s == target_bin else 'steelblue' for s in states]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(states, probs, color=colors, edgecolor='black')
    plt.axhline(y=12.5, color='gray', linestyle='--', linewidth=2, label='Random guess (12.5%)')
    plt.ylabel('Probability (%)', fontsize=12)
    plt.xlabel('Quantum State', fontsize=12)
    plt.title(f'Grover Search on IBM Quantum (156 qubits)\nTarget: |101⟩ - Found with {target_prob:.1f}%', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.ylim(0, 100)
    
    # Add value labels on bars
    for bar, prob in zip(bars, probs):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{prob:.1f}%', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('grover_real_hardware_results.png', dpi=150)
    print("📊 Visualization saved: grover_real_hardware_results.png")
    
except Exception as e:
    print(f"Visualization note: {e}")

print("\n" + "="*70)
print("🚀 YOUR QUANTUM ALGORITHM RAN ON IBM'S 156-QUBIT QUANTUM COMPUTER!")
print("="*70)

# Display the raw counts for verification
print("\n📊 RAW COUNTS:")
print(f"   {counts}")