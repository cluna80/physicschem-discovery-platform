# -*- coding: utf-8 -*-
from docking_agent import DockingAgent

# CORRECT binding pocket from crystal structure
binding_site = {
    'center': (22.0, 0.3, 52.8),
    'size': 21
}

print("="*70)
print("EGFR Docking - Final Test")
print("="*70)
print(f"Binding pocket: center={binding_site['center']}, size={binding_site['size']}")
print()

# Initialize agent
agent = DockingAgent()

# Test with our manually created ligand
print("Docking simple_test.pdbqt (benzene ring at binding site)...")
result = agent.evaluate_compound(
    ligand_file="simple_test.pdbqt",
    receptor_file="egfr.pdbqt",
    binding_site=binding_site,
    exhaustiveness=16,
    num_modes=9
)

if result['success']:
    print(f"\n{'='*70}")
    print("SUCCESS!")
    print(f"{'='*70}")
    print(f"Best binding affinity: {result['best_affinity']:.2f} kcal/mol")
    print(f"Binding strength: {result['binding_strength']}")
    
    print(f"\nAll binding modes:")
    for mode in result['all_modes'][:5]:
        print(f"  Mode {mode['mode']}: {mode['affinity']:.2f} kcal/mol")
    
    # Interpretation
    print(f"\n{'='*70}")
    if result['best_affinity'] < -7:
        print("Interpretation: STRONG binding - good drug candidate!")
    elif result['best_affinity'] < -5:
        print("Interpretation: Moderate binding - needs optimization")
    elif result['best_affinity'] < -3:
        print("Interpretation: Weak binding")
    else:
        print("Interpretation: Very weak binding")
    print(f"{'='*70}")
else:
    print(f"\nDocking failed: {result.get('error', 'Unknown error')}")

print("\nResults saved to: docking_result.pdbqt")
