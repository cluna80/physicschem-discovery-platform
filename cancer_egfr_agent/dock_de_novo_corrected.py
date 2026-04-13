# dock_de_novo_corrected.py
import json
import subprocess
import tempfile
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem
import os

# Use your existing receptor (it's correct!)
RECEPTOR = "egfr_4hjo.pdbqt"  # or egfr_1m17.pdbqt if you prefer

# Correct box center for the binding pocket in 4HJO
# Based on the coordinates of MET A 742 (actual MET793) and CYS A 751 (actual CYS797)
BOX_CENTER = (22.0, 0.5, 48.0)  # Centered on the ATP binding pocket
BOX_SIZE = (24.0, 24.0, 24.0)   # Large enough to cover the pocket

# Load your de novo results
with open("egfr_de_novo_results/de_novo_results.json") as f:
    candidates = json.load(f)

# Sort by fitness and take top 10
candidates.sort(key=lambda x: x['fitness'], reverse=True)
top_candidates = candidates[:10]

print("="*70)
print("DOCKING DE NOVO EGFR CANDIDATES (CORRECTED)")
print("="*70)
print(f"Receptor: {RECEPTOR}")
print(f"Box center: {BOX_CENTER}")
print(f"Box size: {BOX_SIZE}")
print(f"Docking {len(top_candidates)} candidates\n")

results = []

for i, cand in enumerate(top_candidates, 1):
    smiles = cand['smiles']
    gen = cand['generation']
    fitness = cand['fitness']
    
    print(f"[{i}/10] Gen={gen} Fitness={fitness:.1f}")
    print(f"  SMILES: {smiles[:80]}")
    
    try:
        # Generate 3D structure
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"  ✗ Invalid SMILES")
            continue
        
        # Sanitize
        try:
            Chem.SanitizeMol(mol)
        except:
            # Try to fix
            Chem.Kekulize(mol)
            Chem.SanitizeMol(mol)
        
        # Add hydrogens
        mol = Chem.AddHs(mol)
        
        # Generate 3D conformation
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol, maxIters=1000)
        
        # Save to temporary files
        with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False) as pdb_file:
            pdb_path = pdb_file.name
            Chem.MolToPDBFile(mol, pdb_path)
        
        pdbqt_path = pdb_path.replace('.pdb', '.pdbqt')
        out_path = f"docked_gen{gen}_rank{i}.pdbqt"
        
        # Convert to PDBQT with obabel
        cmd_obabel = [
            "obabel", pdb_path, "-O", pdbqt_path,
            "--partialcharge", "gasteiger", "-h"
        ]
        subprocess.run(cmd_obabel, capture_output=True, text=True)
        
        # Check if PDBQT was created
        if not os.path.exists(pdbqt_path):
            print(f"  ✗ Failed to create PDBQT")
            continue
        
        # Dock with vina
        cmd_vina = [
            "vina",
            "--receptor", RECEPTOR,
            "--ligand", pdbqt_path,
            "--center_x", str(BOX_CENTER[0]),
            "--center_y", str(BOX_CENTER[1]),
            "--center_z", str(BOX_CENTER[2]),
            "--size_x", str(BOX_SIZE[0]),
            "--size_y", str(BOX_SIZE[1]),
            "--size_z", str(BOX_SIZE[2]),
            "--exhaustiveness", "32",  # High for accurate results
            "--num_modes", "10",
            "--out", out_path
        ]
        
        result = subprocess.run(cmd_vina, capture_output=True, text=True, timeout=300)
        
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
                'rank': i,
                'generation': gen,
                'fitness': fitness,
                'smiles': smiles,
                'affinity': best_affinity,
                'output_file': out_path
            })
        else:
            print(f"  ✗ No poses found")
            
        # Cleanup
        os.unlink(pdb_path)
        if os.path.exists(pdbqt_path):
            os.unlink(pdbqt_path)
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
    
    print()

# Sort results by affinity (most negative = best)
results.sort(key=lambda x: x['affinity'])

print("="*70)
print("DOCKING RESULTS (Sorted by Affinity)")
print("="*70)
print(f"{'Rank':<5} {'Gen':<6} {'Affinity':<12} {'Fitness':<10} SMILES")
print("-"*70)

for i, res in enumerate(results[:10], 1):
    print(f"{i:<5} {res['generation']:<6} {res['affinity']:<12.2f} {res['fitness']:<10.1f} {res['smiles'][:50]}...")

# Save results
with open("docking_results_de_novo.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✓ Full results saved to docking_results_de_novo.json")
print(f"\nBest candidate: Gen={results[0]['generation']} Affinity={results[0]['affinity']:.2f} kcal/mol")
print(f"  SMILES: {results[0]['smiles']}")