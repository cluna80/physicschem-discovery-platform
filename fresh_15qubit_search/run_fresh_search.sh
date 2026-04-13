#!/bin/bash
echo "========================================="
echo "íº€ PURE 15-QUBIT QUANTUM SEARCH â€” Fresh Run"
echo "========================================="

# Step 1: Quantum search
echo ""
echo "í´¬ Step 1: Running 15-qubit quantum search..."
python3 quantum_15qubit_pure_search.py

# Step 2: Dock candidates
echo ""
echo "í´¬ Step 2: Docking quantum candidates with Gnina..."
python3 dock_quantum_candidates.py

echo ""
echo "========================================="
echo "âœ… FRESH SEARCH COMPLETE!"
echo "========================================="
echo ""
echo "í³Š Results:"
echo "   - quantum_candidates.json (quantum search results)"
echo "   - docking_results.json (Gnina validation)"
echo "   - candidate_smiles.txt (SMILES for synthesis)"
echo ""
echo "í¿† Best candidate identified and ready for MD simulation!"
echo "========================================="
