# optimize_docking.py
import subprocess
import os
import json
from rdkit import Chem
from rdkit.Chem import AllChem

def dock_with_multiple_centers(smiles, name="candidate"):
    """Try multiple box centers to find the best binding pose"""
    
    print(f"\n{'='*70}")
    print(f"Optimizing docking for: {smiles[:80]}")
    print(f"{'='*70}")
    
    # Prepare ligand once
    mol = Chem.MolFromSmiles(smiles)
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    AllChem.MMFFOptimizeMolecule(mol)
    Chem.MolToPDBFile(mol, f"{name}.pdb")
    
    # Convert to PDBQT
    os.system(f"obabel {name}.pdb -O {name}.pdbqt -h --partialcharge gasteiger")
    
    # Test different box centers based on EGFR binding pocket
    box_configs = [
        # 4HJO (osimertinib-bound)
        {"name": "4HJO_center", "center": (22.0, 0.5, 48.0), "size": (24, 24, 24)},
        # Slightly shifted for your molecule
        {"name": "shifted_X", "center": (21.0, 0.5, 48.0), "size": (24, 24, 24)},
        {"name": "shifted_Y", "center": (22.0, 1.5, 48.0), "size": (24, 24, 24)},
        {"name": "shifted_Z", "center": (22.0, 0.5, 47.0), "size": (24, 24, 24)},
        # Larger box for flexibility
        {"name": "large_box", "center": (22.0, 0.5, 48.0), "size": (28, 28, 28)},
        # 1M17 coordinates (erlotinib-bound)
        {"name": "1M17_style", "center": (22.0, 0.25, 52.79), "size": (20, 20, 20)},
    ]
    
    results = []
    
    for config in box_configs:
        print(f"\nTesting: {config['name']}")
        print(f"  Center: {config['center']}")
        print(f"  Size: {config['size']}")
        
        out_file = f"{name}_{config['name']}.pdbqt"
        
        cmd_vina = [
            "vina",
            "--receptor", "egfr_4hjo.pdbqt",
            "--ligand", f"{name}.pdbqt",
            "--center_x", str(config['center'][0]),
            "--center_y", str(config['center'][1]),
            "--center_z", str(config['center'][2]),
            "--size_x", str(config['size'][0]),
            "--size_y", str(config['size'][1]),
            "--size_z", str(config['size'][2]),
            "--exhaustiveness", "32",
            "--num_modes", "5",
            "--out", out_file
        ]
        
        result = subprocess.run(cmd_vina, capture_output=True, text=True)
        
        # Parse best affinity
        best_affinity = None
        for line in result.stdout.split('\n'):
            if line.strip() and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        affinity = float(parts[1])
                        if best_affinity is None or affinity < best_affinity:
                            best_affinity = affinity
                    except:
                        pass
        
        if best_affinity:
            print(f"  ✓ Best affinity: {best_affinity:.2f} kcal/mol")
            results.append({
                'config': config['name'],
                'center': config['center'],
                'size': config['size'],
                'affinity': best_affinity
            })
        else:
            print(f"  ✗ No poses found")
    
    # Sort by best affinity
    results.sort(key=lambda x: x['affinity'])
    
    print(f"\n{'='*70}")
    print("BEST RESULTS")
    print(f"{'='*70}")
    for i, res in enumerate(results[:3], 1):
        print(f"{i}. {res['config']}: {res['affinity']:.2f} kcal/mol")
        print(f"   Center: {res['center']}")
    
    if results and results[0]['affinity'] < -5.0:
        print(f"\n✓ Good binding! Best affinity: {results[0]['affinity']:.2f} kcal/mol")
    elif results:
        print(f"\n⚠ Moderate binding: {results[0]['affinity']:.2f} kcal/mol")
        print("  Try increasing exhaustiveness or using a different receptor")
    
    return results

# Test with your best candidate
best_candidate = "C#Cc1c(OCCO)c(-c2cc(C=CC(=O)NCC)c3ncncc3c2)c(C)c2nccnc12"
results = dock_with_multiple_centers(best_candidate, "gen27")

# Also test with generation 38 (had better fitness)
gen38_candidate = "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCC)c4ncncc4c3)c(C)c2n1"
results2 = dock_with_multiple_centers(gen38_candidate, "gen38")

# Save all results
all_results = {
    'gen27': results,
    'gen38': results2
}

with open('optimized_docking_results.json', 'w') as f:
    json.dump(all_results, f, indent=2)

print(f"\nResults saved to optimized_docking_results.json")