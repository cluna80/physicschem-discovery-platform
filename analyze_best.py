# -*- coding: utf-8 -*-
import subprocess
import os

def analyze_compound(ligand_file, affinity):
    """Analyze the best compound"""
    print("="*70)
    print(f"ANALYZING BEST COMPOUND: {ligand_file}")
    print("="*70)
    print(f"Binding affinity: {affinity:.2f} kcal/mol")
    
    # Classification
    if affinity < -9:
        print("Classification: EXCELLENT - High affinity drug candidate")
    elif affinity < -7:
        print("Classification: STRONG - Promising lead compound")
    elif affinity < -5:
        print("Classification: MODERATE - Needs optimization")
    else:
        print("Classification: WEAK - Not suitable")
    
    # Check molecular properties
    print("\n" + "-"*70)
    print("MOLECULAR PROPERTIES:")
    print("-"*70)
    
    # Extract SMILES from original file
    if os.path.exists("inhibitor.smi"):
        with open("inhibitor.smi", 'r') as f:
            smiles = f.readline().strip()
            print(f"SMILES: {smiles}")
    
    # Count atoms in ligand
    if os.path.exists(ligand_file):
        with open(ligand_file, 'r') as f:
            atoms = sum(1 for line in f if line.startswith("ATOM"))
            print(f"Number of atoms: {atoms}")
    
    print("\n" + "-"*70)
    print("RECOMMENDATIONS:")
    print("-"*70)
    print("1. Proceed to in vitro testing")
    print("2. Synthesize analogs to optimize ADMET properties")
    print("3. Use as a template for structure-activity relationship (SAR) studies")
    print("4. Consider co-crystallization to validate binding mode")
    
    print("\n" + "="*70)

# Analyze the best compound
analyze_compound("inhibitor_3d.pdbqt", -8.10)

# Compare all compounds
print("\n\n" + "="*70)
print("COMPOUND COMPARISON")
print("="*70)
print("The best compound (inhibitor_3d.pdbqt) shows:")
print(f"  - {abs(-8.10 - (-7.64)):.2f} kcal/mol better than gefitinib-like")
print(f"  - {abs(-8.10 - (-6.95)):.2f} kcal/mol better than erlotinib-like")
print(f"  - {abs(-8.10 - (-3.49)):.2f} kcal/mol better than test ligand")
print(f"  - {abs(-8.10 / -3.49):.1f}x stronger than test ligand")
