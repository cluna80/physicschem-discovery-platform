# -*- coding: utf-8 -*-
import subprocess
import os

def parse_vina_output(output_file):
    """Parse Vina output file for binding affinities"""
    if not os.path.exists(output_file):
        return None

    affinities = []
    try:
        with open(output_file, 'r') as f:
            content = f.read()

        in_table = False
        for line in content.split('\n'):
            if 'mode' in line and 'affinity' in line:
                in_table = True
                continue
            if in_table and line.strip():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0].isdigit():
                    affinities.append({
                        'mode': int(parts[0]),
                        'affinity': float(parts[1]),
                        'rmsd_lb': float(parts[2]) if len(parts) > 2 else 0,
                        'rmsd_ub': float(parts[3]) if len(parts) > 3 else 0
                    })
                elif len(parts) < 2:
                    break
    except:
        pass
    
    return affinities

print("="*70)
print("EGFR DOCKING RESULTS ANALYSIS")
print("="*70)

# Test system (working)
test_affinities = parse_vina_output("test_check.pdbqt")
if test_affinities:
    print(f"\n1. Test System (final_receptor + final_ligand):")
    print(f"   Best affinity: {test_affinities[0]['affinity']:.3f} kcal/mol")
    print(f"   Binding strength: Very weak (control experiment)")
else:
    print("\n1. Test system: No results")

# EGFR pocket with test ligand
egfr_test = parse_vina_output("egfr_dock_result.pdbqt")
if egfr_test:
    print(f"\n2. EGFR Pocket + Test Ligand:")
    print(f"   Best affinity: {egfr_test[0]['affinity']:.3f} kcal/mol")
    if egfr_test[0]['affinity'] < -7:
        strength = "Strong binding"
    elif egfr_test[0]['affinity'] < -5:
        strength = "Good binding"
    elif egfr_test[0]['affinity'] < -3:
        strength = "Moderate binding"
    else:
        strength = "Weak binding"
    print(f"   Binding strength: {strength}")
    print(f"\n   Top 5 binding modes:")
    for mode in egfr_test[:5]:
        print(f"     Mode {mode['mode']}: {mode['affinity']:.3f} kcal/mol (RMSD: {mode['rmsd_lb']:.2f} A)")
else:
    print("\n2. EGFR pocket + test ligand: No results yet")

# EGFR pocket with specific ligand (if it exists)
if os.path.exists("egfr_specific_result.pdbqt"):
    egfr_specific = parse_vina_output("egfr_specific_result.pdbqt")
    if egfr_specific:
        print(f"\n3. EGFR Pocket + Specific Ligand:")
        print(f"   Best affinity: {egfr_specific[0]['affinity']:.3f} kcal/mol")
    else:
        print("\n3. EGFR pocket + specific ligand: File exists but no results")

print("\n" + "="*70)
print("INTERPRETATION:")
print("="*70)

if egfr_test:
    affinity = egfr_test[0]['affinity']
    if affinity < -7:
        print("Excellent binding - strong drug candidate!")
    elif affinity < -5:
        print("Good binding - promising lead compound")
    elif affinity < -3:
        print("Moderate binding - needs optimization")
    else:
        print("Weak binding - not suitable for drug development")
    
    print(f"\nThe test ligand shows {abs(affinity):.2f} kcal/mol binding to EGFR")
    if test_affinities:
        print(f"This is {abs(affinity - test_affinities[0]['affinity']):.2f} kcal/mol stronger than the control")
        print(f"Improvement factor: {abs(affinity/test_affinities[0]['affinity']):.1f}x")
else:
    print("Run the docking first to get results")

print("\n" + "="*70)
