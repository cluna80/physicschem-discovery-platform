# -*- coding: utf-8 -*-
import re

def extract_vina_results(filename):
    """Extract binding affinities from Vina PDBQT output"""
    
    affinities = []
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('REMARK VINA RESULT:'):
                # Format: REMARK VINA RESULT:    -3.502      0.000      0.000
                parts = line.strip().split()
                if len(parts) >= 5:
                    affinity = float(parts[3])
                    rmsd_lb = float(parts[4])
                    rmsd_ub = float(parts[5]) if len(parts) > 5 else 0
                    
                    # Count models to get mode number
                    mode_num = len(affinities) + 1
                    affinities.append({
                        'mode': mode_num,
                        'affinity': affinity,
                        'rmsd_lb': rmsd_lb,
                        'rmsd_ub': rmsd_ub
                    })
    return affinities

print("="*70)
print("EGFR DOCKING RESULTS")
print("="*70)

# Extract results
affinities = extract_vina_results("egfr_dock_result.pdbqt")

if affinities:
    print(f"\n{'Mode':<6} {'Affinity (kcal/mol)':<20} {'RMSD l.b.':<12} {'RMSD u.b.':<12}")
    print("-"*60)
    
    for aff in affinities:
        print(f"{aff['mode']:<6} {aff['affinity']:<20.3f} {aff['rmsd_lb']:<12.2f} {aff['rmsd_ub']:<12.2f}")
    
    best = affinities[0]
    print(f"\n{'='*70}")
    print(f"BEST BINDING MODE: Mode {best['mode']}")
    print(f"Binding affinity: {best['affinity']:.3f} kcal/mol")
    print(f"{'='*70}")
    
    # Classification
    if best['affinity'] < -7:
        classification = "STRONG binding - promising drug candidate"
    elif best['affinity'] < -5:
        classification = "MODERATE binding - good starting point"
    elif best['affinity'] < -3:
        classification = "WEAK binding - needs optimization"
    else:
        classification = "VERY WEAK binding - not suitable"
    
    print(f"\nClassification: {classification}")
    
    # Compare with control
    if "test_check.pdbqt" in __import__("os").listdir("."):
        control_affinities = extract_vina_results("test_check.pdbqt")
        if control_affinities:
            control = control_affinities[0]['affinity']
            print(f"\nComparison with control system:")
            print(f"  Control affinity: {control:.3f} kcal/mol")
            print(f"  EGFR affinity: {best['affinity']:.3f} kcal/mol")
            print(f"  Difference: {abs(best['affinity'] - control):.3f} kcal/mol")
            print(f"  Factor: {abs(best['affinity']/control):.1f}x stronger binding to EGFR")
    
    print("\n" + "="*70)
    print("All 9 binding modes saved in: egfr_dock_result.pdbqt")
    print("="*70)
else:
    print("No results found in the file")

