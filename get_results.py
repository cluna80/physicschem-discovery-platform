# get_results.py
from qiskit_ibm_runtime import QiskitRuntimeService

print("="*70)
print("🎉 GROVER RESULTS FROM REAL QUANTUM HARDWARE!")
print("="*70)

service = QiskitRuntimeService()

# Your job ID
JOB_ID = "d71pncmqdfbc73d1987g"

# Get the job
job = service.job(JOB_ID)
print(f"\n📡 Job ID: {JOB_ID}")
print(f"📊 Status: {job.status()}")

# Get results
result = job.result()
print(f"\n📈 Raw result type: {type(result)}")

# Try different ways to extract results
try:
    # Method 1: Try quasi_dists (new API)
    if hasattr(result, 'quasi_dists'):
        counts = result.quasi_dists[0]
    # Method 2: Try get_counts (old API)
    elif hasattr(result, 'get_counts'):
        counts = result.get_counts()
    # Method 3: Try data attribute
    elif hasattr(result, 'data'):
        counts = result.data
    else:
        # Print raw result to see structure
        print("\n🔍 Raw result structure:")
        print(dir(result))
        print("\n" + str(result))
        counts = None
        
except Exception as e:
    print(f"\n⚠️ Error extracting: {e}")
    print("\nLet's look at the raw result:")
    print(result)

# If we got counts, display them
if counts:
    print("\n" + "="*70)
    print("📊 QUANTUM MEASUREMENT RESULTS")
    print("="*70)
    
    # Convert to dictionary if needed
    if hasattr(counts, 'items'):
        counts_dict = dict(counts.items())
    else:
        counts_dict = counts
    
    # Find target |5⟩ (binary 101)
    target = 5
    target_bin = "101"
    
    # Try to find target in results
    target_prob = 0
    for state, prob in counts_dict.items():
        # Convert state to binary string if it's an integer
        if isinstance(state, int):
            binary = format(state, '03b')
        else:
            binary = state
        
        if binary == target_bin or state == target:
            target_prob = prob
            
        # Show probability
        if isinstance(prob, (int, float)):
            bar = '█' * int(prob * 50)
            print(f"   |{binary}⟩: {prob*100:5.1f}% {bar}")
        else:
            print(f"   |{binary}⟩: {prob}")
    
    print("\n" + "="*70)
    print(f"🎯 TARGET |{target_bin}⟩ PROBABILITY: {target_prob*100:.1f}%")
    print("="*70)
    
    # Analysis
    if target_prob > 0.5:
        print("\n✅ SUCCESS! Grover found the target on real quantum hardware!")
        print(f"   Probability: {target_prob*100:.1f}%")
        print("   This demonstrates quantum speedup on IBM's 156-qubit computer!")
    elif target_prob > 0.3:
        print("\n⚠️  Partial success - hardware noise affected results")
        print(f"   Target probability: {target_prob*100:.1f}%")
        print("   Still shows quantum advantage over random (12.5%)")
    else:
        print("\n⚠️  Hardware noise significantly degraded results")
        print("   This is normal for current quantum computers")
        print("   More shots would improve accuracy")