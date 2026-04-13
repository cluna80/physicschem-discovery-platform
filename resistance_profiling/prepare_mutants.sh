#!/bin/bash
echo "========================================="
echo "Preparing Mutant HIV Protease Structures"
echo "========================================="

# This script shows how to prepare mutant structures
# Actual execution requires PDB files for each mutant

echo """
To prepare mutant structures:

1. Download PDB files:
   - WT: https://files.rcsb.org/download/1HHP.pdb
   - D30N: Search for HIV protease D30N mutation
   - V82A: HIV protease V82A mutant
   etc.

2. For each mutant, convert to PDBQT:
   prepare_receptor4.py -r mutant.pdb -o mutant.pdbqt

3. For manual mutagenesis (if structure not available):
   - Use PyMOL to mutate residues
   - Minimize the structure
   - Convert to PDBQT

Example for V82A mutation:
   pymol -c -d "load 1HHP.pdb; alter resi 82 and name V, resn ALA; save mutant_V82A.pdb"
   prepare_receptor4.py -r mutant_V82A.pdb -o mutant_V82A.pdbqt
"""

echo ""
echo "Quick test with available structure..."
if [ -f "docking_out/prot_WT.pdbqt" ]; then
    echo "Testing CURE_17G_002 against WT..."
    ../gnina_cu11 --no_gpu \
        -r docking_out/prot_WT.pdbqt \
        -l ligand_cleaned.pdbqt \
        --autobox_ligand ligand_cleaned.pdbqt \
        --autobox_add 8 \
        --num_modes 3 \
        --exhaustiveness 8 \
        --cnn_scoring rescore \
        -o WT_out.pdbqt 2>&1 | grep -E "Affinity|CNN"
fi

