#!/bin/bash
echo "========================================="
echo "Complete MD Analysis for HIV Protease"
echo "========================================="

# 1. Calculate RMSD (protein stability over time)
echo "1. Calculating RMSD..."
echo "4 4" | gmx rms -s md.tpr -f md.xtc -o rmsd.xvg -tu ns

# 2. Calculate RMSF (per-residue fluctuations)
echo "2. Calculating RMSF..."
echo "4" | gmx rmsf -s md.tpr -f md.xtc -o rmsf.xvg -res

# 3. Calculate Radius of Gyration (compactness)
echo "3. Calculating Radius of Gyration..."
echo "4" | gmx gyrate -s md.tpr -f md.xtc -o gyrate.xvg

# 4. Calculate hydrogen bonds (protein stability)
echo "4. Calculating hydrogen bonds..."
echo "4 4" | gmx hbond -s md.tpr -f md.xtc -num hbonds.xvg

# 5. Extract final structure for docking
echo "5. Extracting final structure..."
echo "0" | gmx trjconv -s md.tpr -f md.xtc -o final_structure.pdb -dump 1000

# 6. Extract average structure
echo "6. Extracting average structure..."
echo "0" | gmx trjconv -s md.tpr -f md.xtc -o average_structure.pdb -avg

echo ""
echo "✅ Analysis complete!"
echo "Generated files:"
ls -lh rmsd.xvg rmsf.xvg gyrate.xvg hbonds.xvg final_structure.pdb average_structure.pdb
