# -*- coding: utf-8 -*-
from docking_agent import DockingAgent

# Initialize your AI agent
agent = DockingAgent()

# EGFR binding site coordinates (from literature)
# The ATP-binding pocket center for 1M17 is approximately:
binding_site = {
    'center': (40.0, 30.0, 35.0),
    'size': 25  # Large enough to cover the binding pocket
}

print("="*60)
print("EGFR Docking with AI Agent")
print("="*60)

# Dock your test ligand
result = agent.evaluate_compound(
    ligand_file="final_ligand.pdbqt",
    receptor_file="egfr.pdbqt",
    binding_site=binding_site,
    exhaustiveness=16
)

if result['success']:
    print(f"\nResults for test ligand:")
    print(f"  Best affinity: {result['best_affinity']:.2f} kcal/mol")
    print(f"  Binding strength: {result['binding_strength']}")
    
    # Show all binding modes
    print(f"\nAll binding modes (affinity in kcal/mol):")
    for mode in result['all_modes'][:5]:
        print(f"  Mode {mode['mode']}: {mode['affinity']:.2f}")
else:
    print("Docking failed")

print("\n" + "="*60)
