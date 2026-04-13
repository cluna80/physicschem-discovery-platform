# real_docking.py
# Real AutoDock Vina binding prediction
# Drop-in replacement for the fake QSAR predict_binding() function
#
# Requirements:
#   - vina in PATH (run setup_receptors.py first)
#   - pip install meeko  (for ligand preparation)
#   - receptors/ folder prepared by setup_receptors.py

import os
import subprocess
import tempfile
import random
import hashlib
import json

RECEPTOR_DIR = "receptors"
DOCKING_CACHE_FILE = "docking_cache.json"

# Load cache to avoid re-docking identical molecules
_docking_cache = {}
if os.path.exists(DOCKING_CACHE_FILE):
    try:
        with open(DOCKING_CACHE_FILE) as f:
            _docking_cache = json.load(f)
        print(f"✅ Docking cache loaded ({len(_docking_cache)} entries)")
    except Exception:
        _docking_cache = {}

def save_cache():
    with open(DOCKING_CACHE_FILE, 'w') as f:
        json.dump(_docking_cache, f)

# Receptor config: PDB ID → (center_x, center_y, center_z, size)
RECEPTOR_CONFIGS = {
    "HIV Protease":       ("1HVR", (-1.3,  2.0,  -0.5), (22, 22, 22)),
    "EGFR (Cancer)":      ("1M17", ( 3.0, -1.5,   7.0), (25, 25, 25)),
    "BRAF (Melanoma)":    ("5J18", (-3.0, 10.5,  -5.0), (22, 22, 22)),
    "JAK (Arthritis)":    ("4E4L", ( 0.5, -2.0,   4.5), (22, 22, 22)),
    "COX-2 (Inflammation)":("5IKR",(21.0, -5.0,  14.0), (20, 20, 20)),
    "HMG-CoA (Cholesterol)":("1HWK",(18.0,40.0,  15.0), (22, 22, 22)),
    "ACE (Blood Pressure)": ("1O86",(36.5,33.0,  31.0), (22, 22, 22)),
}

# QSAR fallback coefficients (used when Vina docking fails)
QSAR_FALLBACK = {
    "HIV Protease":       -9.50,
    "BRAF (Melanoma)":    -9.40,
    "EGFR (Cancer)":      -9.20,
    "JAK (Arthritis)":    -9.30,
    "ACE (Blood Pressure)":-8.50,
    "COX-2 (Inflammation)":-8.96,
    "HMG-CoA (Cholesterol)":-9.00,
}


def smiles_to_pdbqt(smiles, out_path):
    """
    Convert SMILES to docking-ready PDBQT.
    Tries meeko first (better), falls back to obabel.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        import meeko

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return False
        mol = Chem.AddHs(mol)
        result = AllChem.EmbedMolecule(mol, randomSeed=42,
                                        params=AllChem.ETKDGv3())
        if result != 0:
            AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol, maxIters=200)

        preparator = meeko.MoleculePreparation()
        preparator.prepare(mol)
        pdbqt_string = meeko.PDBQTWriterLegacy.write_string(preparator.setup)
        with open(out_path, 'w') as f:
            f.write(pdbqt_string[0] if isinstance(pdbqt_string, tuple) else pdbqt_string)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 50

    except Exception as e_meeko:
        # Fallback: obabel
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
            import tempfile

            mol = Chem.MolFromSmiles(smiles)
            if not mol:
                return False
            mol = Chem.AddHs(mol)
            AllChem.EmbedMolecule(mol, randomSeed=42)
            AllChem.MMFFOptimizeMolecule(mol)

            with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False, mode='w') as f:
                from rdkit.Chem import rdmolfiles
                f.write(rdmolfiles.MolToPDBBlock(mol))
                tmp_pdb = f.name

            subprocess.run(
                ["obabel", tmp_pdb, "-O", out_path, "-xh"],
                capture_output=True, timeout=30
            )
            os.unlink(tmp_pdb)
            return os.path.exists(out_path) and os.path.getsize(out_path) > 50

        except Exception as e_obabel:
            return False


def run_vina(receptor_pdbqt, ligand_pdbqt, center, size,
             exhaustiveness=8, num_modes=3):
    """
    Run AutoDock Vina and return the best binding affinity (kcal/mol).
    Returns None if docking fails.
    """
    cx, cy, cz = center
    sx, sy, sz = size

    out_pdbqt = ligand_pdbqt.replace('.pdbqt', '_out.pdbqt')

    cmd = [
        "vina",
        "--receptor", receptor_pdbqt,
        "--ligand",   ligand_pdbqt,
        "--center_x", str(cx),
        "--center_y", str(cy),
        "--center_z", str(cz),
        "--size_x",   str(sx),
        "--size_y",   str(sy),
        "--size_z",   str(sz),
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes", str(num_modes),
        "--out",      out_pdbqt,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr

        # Parse binding affinity from Vina output
        best_affinity = None
        for line in output.split('\n'):
            line = line.strip()
            # Vina output format: "   1         -8.5      0.000      0.000"
            if line and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        affinity = float(parts[1])
                        if affinity < 0:  # binding affinities are negative
                            best_affinity = affinity
                            break
                    except ValueError:
                        continue

        # Also try parsing from output file
        if best_affinity is None and os.path.exists(out_pdbqt):
            with open(out_pdbqt) as f:
                for line in f:
                    if 'VINA RESULT' in line or 'RESULT' in line:
                        parts = line.split()
                        for part in parts:
                            try:
                                val = float(part)
                                if val < -1:
                                    best_affinity = val
                                    break
                            except ValueError:
                                continue

        # Clean up output file
        if os.path.exists(out_pdbqt):
            os.unlink(out_pdbqt)

        return best_affinity

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def qsar_fallback(smiles, target_name):
    """Fast QSAR estimate when real docking unavailable."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, AllChem, DataStructs

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return QSAR_FALLBACK.get(target_name, -8.0)

        base = QSAR_FALLBACK.get(target_name, -8.5)
        mw   = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd  = Descriptors.NumHDonors(mol)
        hba  = Descriptors.NumHAcceptors(mol)

        adj = 0.0
        adj -= 0.004 * abs(mw - 350)
        adj -= 0.25  * abs(logp - 2.5)
        adj -= 0.08  * hbd
        adj -= 0.04  * hba
        adj += random.uniform(-0.4, 0.4)

        return round(max(-12.0, min(-5.0, base + adj)), 2)
    except Exception:
        return QSAR_FALLBACK.get(target_name, -8.0)


def dock_molecule(smiles, target_name, fast=False):
    """
    Dock a molecule against a target.
    Returns (affinity_kcal_mol, method_used).

    fast=True: skip real docking, use QSAR (for bulk screening)
    fast=False: attempt real Vina docking with QSAR fallback
    """
    # Cache key = hash of SMILES + target
    cache_key = hashlib.md5(f"{smiles}::{target_name}".encode()).hexdigest()
    if cache_key in _docking_cache:
        entry = _docking_cache[cache_key]
        return entry['affinity'], entry['method'] + '_cached'

    if fast:
        aff = qsar_fallback(smiles, target_name)
        return aff, 'qsar'

    # Check receptor availability
    if target_name not in RECEPTOR_CONFIGS:
        aff = qsar_fallback(smiles, target_name)
        return aff, 'qsar'

    pdb_id, center, size = RECEPTOR_CONFIGS[target_name]
    receptor_pdbqt = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdbqt")

    if not os.path.exists(receptor_pdbqt):
        aff = qsar_fallback(smiles, target_name)
        return aff, 'qsar_no_receptor'

    # Prepare ligand
    with tempfile.NamedTemporaryFile(suffix='.pdbqt', delete=False,
                                      prefix='qdl_lig_') as f:
        lig_path = f.name

    try:
        ok = smiles_to_pdbqt(smiles, lig_path)
        if not ok:
            aff = qsar_fallback(smiles, target_name)
            return aff, 'qsar_prep_failed'

        # Run Vina
        affinity = run_vina(receptor_pdbqt, lig_path, center, size,
                            exhaustiveness=8 if not fast else 4)

        if affinity is not None and -20 < affinity < 0:
            method = 'vina_real'
            aff = round(affinity, 2)
        else:
            aff = qsar_fallback(smiles, target_name)
            method = 'qsar_vina_failed'

    except Exception as e:
        aff = qsar_fallback(smiles, target_name)
        method = 'qsar_exception'
    finally:
        if os.path.exists(lig_path):
            try:
                os.unlink(lig_path)
            except Exception:
                pass

    # Cache result
    _docking_cache[cache_key] = {'affinity': aff, 'method': method}
    if len(_docking_cache) % 10 == 0:
        save_cache()

    return aff, method


def dock_all_targets(smiles, fast=False):
    """
    Dock against all 7 targets and return binding profile.
    Uses parallel-friendly sequential calls with caching.
    """
    results = {}
    methods = {}
    for target_name in RECEPTOR_CONFIGS:
        aff, method = dock_molecule(smiles, target_name, fast=fast)
        results[target_name] = aff
        methods[target_name] = method

    real_count = sum(1 for m in methods.values() if 'vina_real' in m)
    if real_count > 0:
        print(f"   ⚡ Real Vina docking: {real_count}/7 targets, "
              f"best={min(results.values()):.2f} kcal/mol")

    return results, methods


def get_docking_status():
    """Return which targets have real receptors ready."""
    status = {}
    for target_name, (pdb_id, _, _) in RECEPTOR_CONFIGS.items():
        pdbqt = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdbqt")
        status[target_name] = {
            'ready': os.path.exists(pdbqt),
            'pdb_id': pdb_id,
            'pdbqt_path': pdbqt
        }
    return status


if __name__ == "__main__":
    print("\nDocking status:")
    for target, info in get_docking_status().items():
        icon = "✅" if info['ready'] else "❌"
        print(f"  {icon} {target} ({info['pdb_id']})")

    print("\nTest docking aspirin vs HIV Protease...")
    aff, method = dock_molecule("CC(=O)Oc1ccccc1C(=O)O", "HIV Protease")
    print(f"  Affinity: {aff} kcal/mol (method: {method})")
