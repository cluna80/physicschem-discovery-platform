#!/usr/bin/env python3
"""
Test script for MutantFBDDAgent
Verifies ML-based affinity prediction pipeline
"""

import os
import sys

# Set environment variables for testing
os.environ["MUTANT_FBDD_ENABLED"] = "1"
os.environ["OLLAMA_MODEL"] = "llama3.2"  # or whatever model you have

print("="*72)
print("  🧬 MUTANT FBDD AGENT TEST")
print("="*72)
print()
print("Testing ML-based drug discovery pipeline...")
print()
print("Prerequisites:")
print("  1. Ollama installed and running (ollama serve)")
print("  2. Model pulled (e.g., ollama pull llama3.2)")
print("  3. MUTANT_FBDD_ENABLED=1 environment variable set")
print()
print("="*72)
print()

# Import after setting env vars
from autonomous_drug_agentV2 import MutantFBDDAgent, AgentLogger

# Create logger
logger = AgentLogger("test_mutant_fbdd.log")

# Create agent
agent = MutantFBDDAgent("EGFR", logger)

if not agent.enabled:
    print("❌ MutantFBDDAgent not enabled!")
    print("   Check:")
    print("   - MUTANT_FBDD_ENABLED=1 is set")
    print("   - requests library is installed")
    sys.exit(1)

print("✅ MutantFBDDAgent initialized")
print(f"   Model: {agent.model}")
print(f"   Target: {agent.target_key}")
print()

# Test single prediction
print("Testing single affinity prediction...")
test_smiles = "c1ccncc1"  # pyridine
predicted_affinity = agent.predict_affinity(test_smiles)
print(f"   SMILES: {test_smiles}")
print(f"   Predicted affinity: {predicted_affinity:.2f} kcal/mol")
print()

# Run full pipeline
print("Running full Mutant FBDD pipeline...")
print("(This will predict affinities for 50 fragments)")
print()

results = agent.run()

print()
print("="*72)
print("  ✅ TEST COMPLETE")
print("="*72)
print()
print(f"Generated {len(results)} predictions")
print(f"Results saved to: agent_results_MUTANT_FBDD_EGFR_*.csv")
print(f"Log saved to: test_mutant_fbdd.log")
print()
print("Top 5 predictions:")
for i, c in enumerate(results[:5], 1):
    print(f"  {i}. {c['id']:<20} {c['dock_affinity']:>7.2f} kcal/mol")
print()

# Made with Bob
