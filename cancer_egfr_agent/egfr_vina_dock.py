#!/usr/bin/env python3
"""
egfr_vina_dock.py
AutoDock Vina docking pipeline for EGFR de novo candidates.

Reads egfr_fragment_based_fixed/results.json  →  prepares each ligand  →
docks against EGFR (4HJO / 1IEP)  →  writes ranked_docking_results.json

Prerequisites:
  pip install rdkit meeko vina --break-system-packages
  - AutoDock Vina binary in PATH  (or set VINA_BIN below)
  - EGFR receptor PDBQT in this directory (see RECEPTOR_PDBQT below)
"""

import json, os, shutil, subprocess, tempfile
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# ===========================================
# CONFIG  — edit these for your setup
# ===========================================

RESULTS_JSON   = Path("egfr_fragment_based_fixed/results.json")
OUTPUT_DIR     = Path("vina_docking_results")
RECEPTOR_PDBQT = Path("egfr_receptor.pdbqt")  # prepared receptor — see NOTE below

# EGFR active site box — centred on Erlotinib binding pocket in 4HJO
# Units: Angstroms. Adjust if using a different crystal structure.
BOX_CENTER = (24.77, 9.19, 0.0)    # x, y, z
BOX_SIZE   = (20.0, 20.0, 20.0)   # size_x, size_y, size_z

VINA_BIN       = "vina"           # set full path if not on PATH e.g. "/usr/local/bin/vina"
VINA_EXHAUSTIVENESS = 16          # 8=fast, 16=balanced, 32=thorough
VINA_NUM_MODES  = 5               # top N poses to keep
TOP_N_CANDIDATES = 20             # how many from results.json to dock
USE_MEEKO       = True            # True = meeko (recommended), False = obabel fallback

OUTPUT_DIR.mkdir(exist_ok=True)

# ===========================================
# NOTE: Receptor preparation
# ===========================================
# If you don't have egfr_receptor.pdbqt yet:
#
#   1. Download 4HJO.pdb from https://www.rcsb.org/structure/4HJO
#   2. Remove HETATM / ligand lines, keep ATOM only, save as egfr_clean.pdb
#   3. Use MGLTools or obabel:
#        obabel egfr_clean.pdb -O egfr_receptor.pdbqt -xr --partialcharge gasteiger
#   4. Alternatively use the protein prep wizard in any docking suite.
#
# The box coords above target the erlotinib binding pocket in 4HJO.
# For 1IEP use: center (25.0, 10.5, 15.5), size (20, 20, 20)
# ===========================================


def smiles_to_3d_mol(smiles: str):
    """Generate a 3D conformer from SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if result != 0:
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
    if result != 0:
        return None
    AllChem.MMFFOptimizeMolecule(mol, maxIters=1000)
    return mol


def mol_to_pdbqt_meeko(mol, out_path: Path) -> bool:
    """Convert RDKit mol to PDBQT using meeko."""
    try:
        from meeko import MoleculePreparation
        preparator = MoleculePreparation()
        preparator.prepare(mol)
        pdbqt_string = preparator.write_pdbqt_string()
        out_path.write_text(pdbqt_string)
        return True
    except Exception as e:
        print(f"    [meeko] {e}")
        return False


def mol_to_pdbqt_obabel(mol, out_path: Path) -> bool:
    """Convert RDKit mol to PDBQT via obabel (fallback)."""
    try:
        sdf_path = out_path.with_suffix('.sdf')
        writer = Chem.SDWriter(str(sdf_path))
        writer.write(mol)
        writer.close()
        result = subprocess.run(
            ["obabel", str(sdf_path), "-O", str(out_path), "--partialcharge", "gasteiger"],
            capture_output=True, text=True, timeout=30
        )
        sdf_path.unlink(missing_ok=True)
        return out_path.exists()
    except Exception as e:
        print(f"    [obabel] {e}")
        return False


def prepare_ligand(smiles: str, out_path: Path) -> bool:
    """Full ligand prep: SMILES → 3D → PDBQT."""
    mol = smiles_to_3d_mol(smiles)
    if not mol:
        return False
    if USE_MEEKO:
        if mol_to_pdbqt_meeko(mol, out_path):
            return True
        print("    meeko failed, trying obabel...")
    return mol_to_pdbqt_obabel(mol, out_path)


def run_vina(ligand_pdbqt: Path, output_pdbqt: Path) -> dict:
    """
    Run AutoDock Vina and parse the best binding affinity.
    Returns dict with 'affinity' (kcal/mol) and 'poses' list.
    """
    cx, cy, cz = BOX_CENTER
    sx, sy, sz = BOX_SIZE

    cmd = [
        VINA_BIN,
        "--receptor",    str(RECEPTOR_PDBQT),
        "--ligand",      str(ligand_pdbqt),
        "--out",         str(output_pdbqt),
        "--center_x",   str(cx),
        "--center_y",   str(cy),
        "--center_z",   str(cz),
        "--size_x",     str(sx),
        "--size_y",     str(sy),
        "--size_z",     str(sz),
        "--exhaustiveness", str(VINA_EXHAUSTIVENESS),
        "--num_modes",   str(VINA_NUM_MODES),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stdout = result.stdout + result.stderr

        # Parse affinity table from Vina output
        poses = []
        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 4 and parts[0].isdigit():
                try:
                    mode     = int(parts[0])
                    affinity = float(parts[1])
                    rmsd_lb  = float(parts[2])
                    rmsd_ub  = float(parts[3])
                    poses.append({
                        "mode": mode,
                        "affinity_kcal_mol": affinity,
                        "rmsd_lb": rmsd_lb,
                        "rmsd_ub": rmsd_ub
                    })
                except ValueError:
                    continue

        if poses:
            return {
                "success": True,
                "best_affinity": poses[0]["affinity_kcal_mol"],
                "poses": poses,
                "vina_log": stdout
            }
        else:
            return {"success": False, "error": "No poses parsed", "vina_log": stdout}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Vina timeout (>300s)"}
    except FileNotFoundError:
        return {"success": False, "error": f"Vina binary not found: '{VINA_BIN}'. Set VINA_BIN in config."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def calculate_properties(smiles: str) -> dict:
    """Quick property recalc for the final report."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return {}
    return {
        "mw":          round(Descriptors.MolWt(mol), 1),
        "logp":        round(Descriptors.MolLogP(mol), 2),
        "hbd":         Chem.rdMolDescriptors.CalcNumHBD(mol),
        "hba":         Chem.rdMolDescriptors.CalcNumHBA(mol),
        "rot_bonds":   Descriptors.NumRotatableBonds(mol),
        "rings":       Chem.rdMolDescriptors.CalcNumRings(mol),
        "tpsa":        round(Chem.rdMolDescriptors.CalcTPSA(mol), 1),
        "qed":         round(Chem.QED.qed(mol), 3) if hasattr(Chem, 'QED') else None,
    }


def main():
    print("=" * 70)
    print("EGFR VINA DOCKING PIPELINE")
    print("=" * 70)

    # Safety check
    if not RECEPTOR_PDBQT.exists():
        print(f"\n[ERROR] Receptor file not found: {RECEPTOR_PDBQT}")
        print("  See NOTE in the script header for preparation instructions.")
        print("  Quick option: obabel 4HJO.pdb -O egfr_receptor.pdbqt -xr --partialcharge gasteiger")
        return

    # Load candidates
    with open(RESULTS_JSON) as f:
        candidates = json.load(f)

    print(f"\nLoaded {len(candidates)} candidates from {RESULTS_JSON}")
    candidates = candidates[:TOP_N_CANDIDATES]
    print(f"Docking top {len(candidates)} candidates against {RECEPTOR_PDBQT}")
    print(f"Box center: {BOX_CENTER}  size: {BOX_SIZE}")
    print(f"Exhaustiveness: {VINA_EXHAUSTIVENESS}  Poses: {VINA_NUM_MODES}\n")

    docking_results = []

    for i, cand in enumerate(candidates):
        smiles = cand['smiles']
        rank   = i + 1
        gen    = cand.get('generation', '?')
        fit    = cand.get('fitness', 0)
        print(f"[{rank:02d}/{len(candidates)}] Gen={gen}  EvolFit={fit:.1f}")
        print(f"       SMILES: {smiles[:72]}")

        lig_path = OUTPUT_DIR / f"ligand_{rank:02d}.pdbqt"
        out_path = OUTPUT_DIR / f"docked_{rank:02d}.pdbqt"

        # Prepare ligand
        prep_ok = prepare_ligand(smiles, lig_path)
        if not prep_ok:
            print(f"       [SKIP] Ligand preparation failed\n")
            docking_results.append({
                "rank": rank,
                "smiles": smiles,
                "generation": gen,
                "evol_fitness": fit,
                "docking": {"success": False, "error": "Ligand prep failed"},
                "properties": calculate_properties(smiles)
            })
            continue

        # Dock
        dock_result = run_vina(lig_path, out_path)

        if dock_result["success"]:
            aff = dock_result["best_affinity"]
            print(f"       Best affinity: {aff:.3f} kcal/mol  ({len(dock_result['poses'])} poses)")
        else:
            print(f"       [FAIL] {dock_result.get('error', 'unknown')}")

        props = calculate_properties(smiles)
        docking_results.append({
            "rank": rank,
            "smiles": smiles,
            "generation": gen,
            "evol_fitness": fit,
            "docking": dock_result,
            "properties": props
        })
        print()

    # Sort by best affinity (more negative = better)
    successful = [r for r in docking_results if r['docking'].get('success')]
    failed     = [r for r in docking_results if not r['docking'].get('success')]
    successful.sort(key=lambda x: x['docking']['best_affinity'])

    ranked = successful + failed

    # Save
    output_json = OUTPUT_DIR / "ranked_docking_results.json"
    with open(output_json, 'w') as f:
        json.dump(ranked, f, indent=2)

    # Print final report
    print("=" * 70)
    print("DOCKING COMPLETE — Ranked by Binding Affinity")
    print("=" * 70)
    print(f"\n{'Dock Rank':<10} {'Evol Rank':<11} {'Affinity':>10} {'MW':>6} {'LogP':>6} "
          f"{'TPSA':>6} {'QED':>5}  SMILES")
    print("-" * 90)

    for dr, res in enumerate(successful[:15], 1):
        d   = res['docking']
        p   = res['properties']
        aff = d.get('best_affinity', 999)
        qed = p.get('qed')
        qed_str = f"{qed:.3f}" if qed else "  n/a"
        print(f"{dr:<10} {res['rank']:<11} {aff:>10.3f} {p.get('mw',0):>6.0f} "
              f"{p.get('logp',0):>6.2f} {p.get('tpsa',0):>6.1f} {qed_str:>5}  "
              f"{res['smiles'][:40]}")

    if failed:
        print(f"\n{len(failed)} candidates failed (ligand prep or Vina error) — see {output_json}")

    print(f"\nFull results saved to: {output_json}")
    print(f"Docked poses saved to: {OUTPUT_DIR}/docked_*.pdbqt")

    # Quick analysis
    if successful:
        best = successful[0]
        print(f"\nBest candidate: Evol rank {best['rank']}  Gen {best['generation']}")
        print(f"  Affinity : {best['docking']['best_affinity']:.3f} kcal/mol")
        print(f"  SMILES   : {best['smiles']}")
        p = best['properties']
        print(f"  MW={p.get('mw')}  LogP={p.get('logp')}  TPSA={p.get('tpsa')}  "
              f"HBD={p.get('hbd')}  HBA={p.get('hba')}  QED={p.get('qed')}")
        print(f"\n  Reference: Osimertinib docks at ~-9.5 to -11.0 kcal/mol on 4HJO")
        print(f"             Erlotinib docks at   ~-8.5 to -10.0 kcal/mol on 4HJO")


if __name__ == "__main__":
    main()