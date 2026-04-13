# -*- coding: utf-8 -*-
from docking_agent import DockingAgent

binding_site = {
    'center': (22.0, 0.3, 52.8),
    'size': 21
}

print("="*70)
print("EGFR Docking with Erlotinib-derived Ligand")
print("="*70)
print(f"Binding pocket: center={binding_site['center']}, size={binding_site['size']}")
print()

agent = DockingAgent()

# Test with the ligand extracted from the crystal structure
print("Docking egfr_ligand.pdbqt (based on bound erlotinib)...")
result = agent.evaluate_compound(
    ligand_file="egfr_ligand.pdbqt",
    receptor_file="egfr.pdbqt",
    binding_site=binding_site,
    exhaustiveness=16,
    num_modes=9
)

if result['success']:
    print(f"\n{'='*70}")
    print("SUCCESSFUL DOCKING!")
    print(f"{'='*70}")
    print(f"Best binding affinity: {result['best_affinity']:.2f} kcal/mol")
    print(f"Binding strength: {result['binding_strength']}")
    
    print(f"\nTop 5 binding modes:")
    for mode in result['all_modes'][:5]:
        print(f"  Mode {mode['mode']}: {mode['affinity']:.2f} kcal/mol")
    
    # Classification
    if result['best_affinity'] < -9:
        print("\n*** Excellent! This is a very strong binder ***")
    elif result['best_affinity'] < -7:
        print("\n*** Good binding affinity - promising drug candidate ***")
    elif result['best_affinity'] < -5:
        print("\n*** Moderate binding - needs optimization ***")
    else:
        print("\n*** Weak binding - not suitable for drug development ***")
else:
    print(f"\nDocking failed: {result.get('error', 'Unknown error')}")

print("\n" + "="*70)
