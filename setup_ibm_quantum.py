# setup_ibm_quantum.py
from qiskit_ibm_runtime import QiskitRuntimeService

print("="*70)
print("🔧 IBM QUANTUM SETUP WIZARD")
print("="*70)

# Try to connect first
try:
    service = QiskitRuntimeService()
    print("✅ Account already configured!")
    
    # Show available backends
    print("\n📡 Available quantum computers:")
    backends = service.backends()
    for backend in backends[:10]:
        if backend.status().operational:
            print(f"   ✅ {backend.name}: {backend.num_qubits} qubits")
    
    print(f"\n🎯 Total available: {len([b for b in backends if b.status().operational])} quantum computers")
    
except Exception as e:
    print("⚠️  No account found. Let's set it up.")
    print("\n1. Go to: https://quantum-computing.ibm.com/account")
    print("2. Find 'API Tokens' section")
    print("3. Click 'Generate new token'")
    print("4. Copy the token (starts with 'q-')")
    print("\n" + "="*70)
    
    # Get token from user
    token = input("Paste your API token here: ").strip()
    
    if token.startswith('q-'):
        # Save the token with correct channel name
        QiskitRuntimeService.save_account(
            channel="ibm_quantum_platform",  # <-- CORRECT CHANNEL
            token=token,
            set_as_default=True,
            overwrite=True
        )
        print("\n✅ Token saved successfully!")
        
        # Test connection
        service = QiskitRuntimeService()
        print("\n📡 Available quantum computers:")
        for backend in service.backends()[:10]:
            if backend.status().operational:
                print(f"   ✅ {backend.name}: {backend.num_qubits} qubits")
        
        print(f"\n🎯 Total available: {len([b for b in service.backends() if b.status().operational])} quantum computers")
    else:
        print("\n❌ Invalid token format. Token should start with 'q-'")

print("\n" + "="*70)
print("🚀 Setup complete!")