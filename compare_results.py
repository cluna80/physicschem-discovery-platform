# -*- coding: utf-8 -*-
import subprocess

def get_best_affinity(output_file):
    """Extract best affinity from Vina output"""
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        for line in content.split('\n'):
            if 'mode' in line and 'affinity' in line:
                continue
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                return float(parts[1])
    except:
        pass
    return None

print("="*70)
print("DOCKING RESULTS COMPARISON")
print("="*70)

# Test system (working)
test_aff = get_best_affinity("test_check.pdbqt")
print(f"\nTest system (final_receptor + final_ligand):")
print(f"  Best affinity: {test_aff:.2f} kcal/mol")

# EGFR pocket with test ligand
egfr_test_aff = get_best_affinity("egfr_dock_result.pdbqt")
if egfr_test_aff:
    print(f"\nEGFR pocket + test ligand:")
    print(f"  Best affinity: {egfr_test_aff:.2f} kcal/mol")
else:
    print(f"\nEGFR pocket + test ligand: No results yet")

# EGFR pocket with specific ligand
egfr_specific_aff = get_best_affinity("egfr_specific_result.pdbqt")
if egfr_specific_aff:
    print(f"\nEGFR pocket + specific ligand:")
    print(f"  Best affinity: {egfr_specific_aff:.2f} kcal/mol")
else:
    print(f"\nEGFR pocket + specific ligand: No results yet")

print("\n" + "="*70)
print("Note: More negative affinity = stronger binding")
print("="*70)
