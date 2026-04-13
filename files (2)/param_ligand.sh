#!/bin/bash
# ============================================================
# Ligand Parameterization for GROMACS
# Uses ACPYPE (wrapper around AmberTools antechamber)
# Install: pip install acpype
# ============================================================
set -e

# ── Install ACPYPE if needed ──────────────────────────────────
# pip install acpype
# OR: conda install -c conda-forge acpype

LIGAND_CHARGE=0   # Set net formal charge of your ligand
ATOM_TYPE="gaff2" # gaff or gaff2

echo "========================================"
echo " Ligand Parameterization via ACPYPE"
echo "========================================"

for ligand_pdb in CURE_*_pose*.pdb; do
    [ -f "$ligand_pdb" ] || continue
    base="${ligand_pdb%.pdb}"
    echo ""
    echo "── Processing: $base ──"

    mkdir -p "ligand_params/${base}"
    cp "$ligand_pdb" "ligand_params/${base}/"
    cd "ligand_params/${base}"

    # ── Run ACPYPE ────────────────────────────────────────────
    # This generates GROMACS-ready .itp and .gro files
    acpype \
        -i "${base}.pdb" \
        -c bcc \
        -n ${LIGAND_CHARGE} \
        -a ${ATOM_TYPE} \
        -o gmx

    # ACPYPE creates a directory: ${base}.acpype/
    # Key files inside:
    #   ${base}_GMX.itp   — ligand force field parameters
    #   ${base}_GMX.gro   — ligand coordinates
    #   posre_${base}.itp — position restraints

    echo "  Output in: ligand_params/${base}/${base}.acpype/"
    ls "${base}.acpype/" 2>/dev/null || echo "  (acpype dir not found — check for errors above)"

    cd ../..
done

echo ""
echo "========================================"
echo " Next steps: merge ligand into system"
echo "========================================"
echo ""
echo "1. Combine protein + ligand GROs:"
echo "   cat protein.gro ligand.gro > complex.gro"
echo "   (fix atom count on line 2 manually)"
echo ""
echo "2. Edit topol.top — add BEFORE [ system ]:"
echo '   #include "ligand_params/LIG.acpype/LIG_GMX.itp"'
echo ""
echo "3. Add ligand to [ molecules ] at bottom of topol.top:"
echo "   LIG    1"
echo ""
echo "4. Then continue with box → solvate → ions → EM..."
