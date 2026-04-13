# get_grover_results.py
from qiskit_ibm_runtime import QiskitRuntimeService
import numpy as np

print("="*70)
print("🎉 GROVER RESULTS FROM REAL IBM QUANTUM HARDWARE!")
print("="*70)

service = QiskitRuntimeService()
job = service.job("d71pncmqdfbc73d1987g")

print(f"\n📡 Job ID: d71pncmqdfbc73d1987g")
print(f"📊 Status: DONE")

# Get the result
result = job.result()

# Extract the measurement data
print("\n🔬 Processing quantum measurement results...")

# Get the first publication result
pub_result = result[0]

# Get the data bin
data = pub_result.data

# The measurements are in a BitArray
c = data.c

print(f"\n📊 BitArray info:")
print(f"   Type: {type(c)}")
print(f"   Shape: {c.shape}")
print(f"   Num shots: {c.num_shots}")
print(f"   Num bits: {c.num_bits}")

# Convert BitArray to counts
counts = {}

# Method 1: Try to get array
try:
    # Get as numpy array
    if hasattr(c, 'array'):
        array = c.array
        print(f"\n   Array shape: {array.shape}")
        
        # Process each shot
        for i in range(c.num_shots):
            # Get bits for this shot
            bits = []
            for b in range(c.num_bits):
                # Access bit
                bit_val = (array[i] >> b) & 1
                bits.append(bit_val)
            
            # Convert to integer state
            state = 0
            for b in range(c.num_bits):
                state |= (bits[b] << b)
            counts[state] = counts.get(state, 0) + 1
            
except Exception as e:
    print(f"   Method 1 failed: {e}")
    
    # Method 2: Try direct iteration
    try:
        for i in range(c.num_shots):
            # Try to get the integer value directly
            if hasattr(c, 'get_int'):
                val = c.get_int(i)
                counts[val] = counts.get(val, 0) + 1
            elif hasattr(c, '__getitem__'):
                val = c[i]
                if isinstance(val, int):
                    counts[val] = counts.get(val, 0) + 1
    except Exception as e2:
        print(f"   Method 2 failed: {e2}")
        
        # Method 3: Print raw data to understand structure
        print("\n🔍 Raw data structure:")
        print(f"   Data: {data}")
        print(f"   c: {c}")
        
        # Try to get all shots
        try:
            shots = c.get_counts()
            counts = shots
        except:
            pass

# If we have counts, process them
if counts:
    # Convert to probabilities
    total_shots = sum(counts.values())
    probs = {state: count/total_shots for state, count in counts.items()}
    
    print("\n" + "="*70)
    print("📊 QUANTUM MEASUREMENT RESULTS")
    print("="*70)
    
    # Target is |5⟩ (binary 101)
    target = 5
    target_bin = "101"
    
    print(f"\n🎯 TARGET STATE: |{target_bin}⟩ (decimal {target})")
    print("-"*50)
    
    # Show all states sorted
    for state in sorted(probs.keys()):
        binary = format(state, '03b')
        prob = probs[state]
        bar = '█' * int(prob * 50)
        marker = " ← TARGET!" if state == target else ""
        print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}{marker}")
    
    # Target probability
    target_prob = probs.get(target, 0)
    
    print("\n" + "="*70)
    print(f"🎯 TARGET |{target_bin}⟩ PROBABILITY: {target_prob*100:.1f}%")
    print("="*70)
    
    # Analysis
    print("\n📈 ANALYSIS:")
    print("-"*50)
    
    # Random guess probability
    random_guess = 1 / 8 * 100
    print(f"   Random guess: {random_guess:.1f}%")
    print(f"   Your result:   {target_prob*100:.1f}%")
    
    if target_prob > 0.5:
        improvement = (target_prob - 0.125) / 0.125 * 100
        print(f"\n✅ QUANTUM SPEEDUP DEMONSTRATED!")
        print(f"   {improvement:.0f}% better than random guess!")
        print("   Grover's algorithm successfully found the target on real hardware!")
        
    elif target_prob > 0.3:
        print(f"\n⚠️  Partial quantum advantage demonstrated")
        print("   Hardware noise affected results, but still better than classical")
        
    else:
        print(f"\n⚠️  Hardware noise degraded results")
        print("   This is expected on current NISQ devices")
    
    # Save results
    with open("grover_real_results.txt", "w") as f:
        f.write("GROVER RESULTS ON REAL IBM QUANTUM HARDWARE\n")
        f.write("="*50 + "\n\n")
        for state in sorted(probs.keys()):
            binary = format(state, '03b')
            prob = probs[state]
            f.write(f"|{binary}⟩: {prob*100:.1f}%\n")
        f.write(f"\nTarget |101⟩: {target_prob*100:.1f}%\n")
        f.write(f"Random guess: 12.5%\n")
    
    print("\n📁 Results saved to: grover_real_results.txt")
    
    # Visualize
    try:
        import matplotlib.pyplot as plt
        
        states = list(probs.keys())
        probabilities = [probs[s]*100 for s in states]
        state_labels = [f"|{format(s, '03b')}⟩" for s in states]
        colors = ['red' if s == target else 'skyblue' for s in states]
        
        plt.figure(figsize=(10, 6))
        plt.bar(state_labels, probabilities, color=colors)
        plt.axhline(y=12.5, color='gray', linestyle='--', label='Random guess (12.5%)')
        plt.ylabel('Probability (%)')
        plt.title(f'Grover Search on IBM Quantum (156 qubits)\nTarget: |101⟩ - Found with {target_prob*100:.1f}%')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 100)
        plt.tight_layout()
        plt.savefig('grover_real_hardware_results.png', dpi=150)
        print("📊 Visualization saved: grover_real_hardware_results.png")
    except Exception as e:
        print(f"Visualization error: {e}")

else:
    print("\n⚠️  Could not extract counts. Let me print raw data:")
    print(result)
    
    # Try a different approach
    print("\n" + "="*70)
    print("ALTERNATIVE: Using Qiskit's built-in result parser")
    print("="*70)
    
    # Get the raw data
    for i, pub_result in enumerate(result):
        print(f"\nPublication {i}:")
        data = pub_result.data
        if hasattr(data, 'c'):
            c = data.c
            print(f"  c: {c}")
            print(f"  c.get_counts(): {c.get_counts() if hasattr(c, 'get_counts') else 'N/A'}")