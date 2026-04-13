# -*- coding: utf-8 -*-
from docking_agent import DockingAgent

# Binding site from crystal structure
binding_site = {
    'center': (22.0, 0.3, 52.8),
    'size': 21
}

print("="*70)
print("EGFR Docking with Clean Ligand")
print("="*70)
print(f"Binding pocket: center={binding_site['center']}, size={binding_site['size']}")
print()

# Initialize agent
agent = DockingAgent()

# Dock the clean ligand
print("Docking clean_ligand.pdbqt...")
result = agent.evaluate_compound(
    ligand_file="clean_ligand.pdbqt",
    receptor_file="egfr.pdbqt",
    binding_site=binding_site,
    exhaustiveness=16,
    num_modes=9
)

if result['success']:
    print(f"\n{'='*70}")
    print("DOCKING SUCCESSFUL!")
    print(f"{'='*70}")
    print(f"\nBest binding affinity: {result['best_affinity']:.2f} kcal/mol")
    print(f"Binding strength: {result['binding_strength']}")
    
    print(f"\nTop 5 binding modes:")
    for mode in result['all_modes'][:5]:
        print(f"  Mode {mode['mode']}: {mode['affinity']:.2f} kcal/mol (RMSD: {mode['rmsd_lb']:.2f} A)")
    
    print(f"\n{'='*70}")
    if result['best_affinity'] < -7:
        print("*** STRONG BINDING - Promising drug candidate ***")
    elif result['best_affinity'] < -5:
        print("*** MODERATE BINDING - Good starting point for optimization ***")
    elif result['best_affinity'] < -3:
        print("*** WEAK BINDING - Needs structural optimization ***")
    else:
        print("*** VERY WEAK BINDING - Likely non-binder ***")
    print(f"{'='*70}")
    
    print(f"\nResults saved to: docking_result.pdbqt")
else:
    print(f"\nDocking failed: {result.get('error', 'Unknown error')}")

print("\n" + "="*70)
