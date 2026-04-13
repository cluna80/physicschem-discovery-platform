import json
from pathlib import Path
import sys

def analyze_docking_results():
    """Parse and analyze nextgen docking results"""
    
    results_file = Path('nextgen_docking/nextgen_results.json')
    if not results_file.exists():
        print("❌ Results not found. Run dock_nextgen.py first.")
        print(f"   Expected: {results_file.absolute()}")
        return
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    print("=" * 80)
    print("🏆 NEXT-GEN DOCKING ANALYSIS")
    print("=" * 80)
    
    # Filter valid results
    valid = []
    for name, data in results.items():
        if data.get('affinity') is not None:
            valid.append((name, data))
    
    if not valid:
        print("❌ No valid docking results found.")
        return
    
    valid.sort(key=lambda x: x[1]['affinity'])
    
    print("\n📊 COMPLETE RANKINGS:")
    print("-" * 70)
    print(f"{'Candidate':<12} {'Affinity':<10} {'CNN':<8} {'MW':<6} {'Status':<10}")
    print("-" * 70)
    
    for name, data in valid:
        aff = data['affinity']
        cnn = max(data.get('cnn_scores', [0])) if data.get('cnn_scores') else 0
        mw = data['mw']
        
        if aff <= -10.0:
            status = "🔥 EXCELLENT"
        elif aff <= -9.0:
            status = "✅ GOOD"
        elif aff <= -8.0:
            status = "⚠️ MODERATE"
        else:
            status = "❌ WEAK"
        
        print(f"{name:<12} {aff:>6.2f}       {cnn:>6.3f}  {mw:>4}    {status}")
    
    # Find best candidates
    print("\n" + "=" * 80)
    print("📈 PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    # Baseline comparison
    baseline = results.get('HYB-001', {}).get('affinity', None)
    best_name, best_data = valid[0]
    best_aff = best_data['affinity']
    
    if baseline:
        improvement = best_aff - baseline
        print(f"\n🎯 BASELINE COMPARISON:")
        print(f"   HYB-001 (original): {baseline:.2f} kcal/mol")
        print(f"   Best Next-Gen ({best_name}): {best_aff:.2f} kcal/mol")
        print(f"   Improvement: {improvement:.2f} kcal/mol")
        
        if improvement <= -1.5:
            print("   🎉 SIGNIFICANT! Clinical candidate territory!")
        elif improvement <= -1.0:
            print("   ✅ Good improvement, worth pursuing")
        else:
            print("   ⚠️ Marginal improvement, need optimization")
    
    # Group by scaffold type
    print(f"\n🔬 SCAFFOLD TYPE ANALYSIS:")
    print("-" * 60)
    
    spiro = []
    bis_thf = []
    simple = []
    
    for name, data in valid:
        if 'spiro' in name.lower() or name in ['NG-007', 'NG-009']:
            spiro.append(data['affinity'])
        elif 'NG-006' in name or 'NG-008' in name:
            bis_thf.append(data['affinity'])
        else:
            simple.append(data['affinity'])
    
    if spiro:
        avg_spiro = sum(spiro) / len(spiro)
        print(f"   Spiro-THF group ({len(spiro)} candidates): {avg_spiro:.2f} kcal/mol avg")
        print(f"      Best: {min(spiro):.2f}")
    
    if bis_thf:
        avg_bis = sum(bis_thf) / len(bis_thf)
        print(f"   Bis-THF group ({len(bis_thf)} candidates): {avg_bis:.2f} kcal/mol avg")
        print(f"      Best: {min(bis_thf):.2f}")
    
    if simple:
        avg_simple = sum(simple) / len(simple)
        print(f"   Simple benzyl ({len(simple)} candidates): {avg_simple:.2f} kcal/mol avg")
        print(f"      Best: {min(simple):.2f}")
    
    # Ligand efficiency analysis
    print(f"\n⚡ LIGAND EFFICIENCY (Affinity per heavy atom):")
    print("-" * 60)
    
    try:
        from rdkit import Chem
        for name, data in valid[:5]:
            smiles = data['smiles']
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                heavy_atoms = mol.GetNumHeavyAtoms()
                le = data['affinity'] / heavy_atoms
                print(f"   {name}: LE = {le:.3f} ({data['affinity']:.2f} / {heavy_atoms} atoms)")
    except:
        print("   RDKit not available for heavy atom calculation")
    
    # Recommendation
    print(f"\n" + "=" * 80)
    print(f"💡 FINAL RECOMMENDATION")
    print("=" * 80)
    
    if best_aff <= -10.0:
        print(f"\n🏆 {best_name} achieved CLINICAL CANDIDATE binding ({best_aff:.2f} kcal/mol)!")
        print(f"\n   → Proceed to synthesis planning")
        print(f"   → File provisional patent within 6 months")
        print(f"   → Order building blocks immediately")
        print(f"   → Prioritize: {best_name}")
        
        if len(valid) > 1:
            second_name, second_data = valid[1]
            print(f"\n   Backup candidate: {second_name} ({second_data['affinity']:.2f} kcal/mol)")
            
    elif best_aff <= -9.0:
        print(f"\n✅ {best_name} is strong ({best_aff:.2f} kcal/mol), needs slight optimization")
        print(f"\n   → Try fluorination pattern optimization")
        print(f"   → Consider MW reduction while preserving P2 group")
        print(f"   → Test combination with spiro-THF from NG-007")
    else:
        print(f"\n⚠️ Results below target ({best_aff:.2f} kcal/mol), need scaffold redesign")
        print(f"\n   → Re-evaluate P2 group attachment point")
        print(f"   → Consider alternative hydrophobic cores")
    
    # Save analysis
    output = {
        'baseline': baseline,
        'best_candidate': best_name,
        'best_affinity': best_aff,
        'improvement': improvement if baseline else None,
        'top_5': [(n, d['affinity']) for n, d in valid[:5]],
        'scaffold_performance': {
            'spiro_thf_avg': avg_spiro if spiro else None,
            'bis_thf_avg': avg_bis if bis_thf else None,
            'simple_avg': avg_simple if simple else None
        }
    }
    
    with open('nextgen_docking/analysis.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n📁 Detailed analysis saved: nextgen_docking/analysis.json")
    print("\n" + "=" * 80)

if __name__ == "__main__":
    analyze_docking_results()
