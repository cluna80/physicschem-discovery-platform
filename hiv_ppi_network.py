#!/usr/bin/env python3
"""
HIV Protein-Protein Interaction Network Agent
Screens compounds against multiple HIV targets simultaneously
based on patient CD4/viral load to build a pan-HIV activity profile.
"""
import os
import sys
import csv
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# ── HIV PPI Network Definition ─────────────────────────────────────
# Each node = a protein target in the HIV replication cycle
# Edges = functional dependencies (if you hit node A, node B is affected)

HIV_PPI_NETWORK = {
    "HIV_RT": {
        "name":       "HIV-1 Reverse Transcriptase",
        "receptor":   "hiv_rt_target.pdbqt",
        "pdb":        "1RTD",
        "center":     (-8.0, 22.0, 18.0),
        "size":       (25, 25, 25),
        "ref_drug":   "Efavirenz",
        "ref_affinity": -10.0,
        "mechanism":  "NNRTI binding pocket — blocks DNA synthesis",
        "active_above_cd4": 0,     # always active
        "ppi_partners": ["PCNA", "RNaseH"],
        "fragment_bias": "aniline",
    },
    "HIV_INTEGRASE": {
        "name":       "HIV-1 Integrase (LEDGF interface)",
        "receptor":   "hiv_integrase.pdbqt",
        "pdb":        "3L2T",
        "center":     (-38.5, 30.5, -20.8),
        "size":       (25, 25, 25),
        "ref_drug":   "Dolutegravir",
        "ref_affinity": -9.43,
        "mechanism":  "INSTI — blocks strand transfer into host chromosome",
        "active_above_cd4": 0,
        "ppi_partners": ["LEDGF/p75", "TNPO3"],
        "fragment_bias": "naphthalene",
    },
    "HIV_PROTEASE": {
        "name":       "HIV-1 Protease",
        "receptor":   "hiv_protease.pdbqt",
        "pdb":        "1HHP",
        "center":     (-11.4, 19.8, 28.0),
        "size":       (20, 20, 20),
        "ref_drug":   "Darunavir",
        "ref_affinity": -12.0,
        "mechanism":  "PI — blocks viral polyprotein maturation",
        "active_above_cd4": 0,
        "ppi_partners": ["Gag", "GagPol"],
        "fragment_bias": "quinoline",
    },
}

# Resistance mutations — screen when CD4 < 350 (advanced HIV)
RESISTANCE_VARIANTS = {
    "HIV_PROT_D30N": {
        "name": "HIV-1 Protease D30N (PI resistance)",
        "receptor": "resistance_profiling/docking_results/protein_D30N.pdbqt",
        "center": (-11.4, 19.8, 28.0), "size": (20, 20, 20),
        "mutation": "D30N", "resistance_to": "Nelfinavir",
    },
    "HIV_PROT_V82A": {
        "name": "HIV-1 Protease V82A (PI resistance)",
        "receptor": "resistance_profiling/docking_results/protein_V82A.pdbqt",
        "center": (-11.4, 19.8, 28.0), "size": (20, 20, 20),
        "mutation": "V82A", "resistance_to": "Ritonavir/Indinavir",
    },
    "HIV_PROT_I50V": {
        "name": "HIV-1 Protease I50V (PI resistance)",
        "receptor": "resistance_profiling/docking_results/protein_I50V.pdbqt",
        "center": (-11.4, 19.8, 28.0), "size": (20, 20, 20),
        "mutation": "I50V", "resistance_to": "Amprenavir/Darunavir",
    },
    "HIV_PROT_L90M": {
        "name": "HIV-1 Protease L90M (PI resistance)",
        "receptor": "resistance_profiling/docking_results/protein_L90M.pdbqt",
        "center": (-11.4, 19.8, 28.0), "size": (20, 20, 20),
        "mutation": "L90M", "resistance_to": "Saquinavir",
    },
}

def get_active_ppi_nodes(cd4: float, viral_load: float) -> dict:
    """
    Determine which HIV PPI nodes are active based on patient lab data.
    Returns subset of HIV_PPI_NETWORK to screen.
    """
    nodes = {}
    
    # Always screen RT and Integrase
    nodes["HIV_RT"] = HIV_PPI_NETWORK["HIV_RT"]
    nodes["HIV_INTEGRASE"] = HIV_PPI_NETWORK["HIV_INTEGRASE"]
    
    # Add Protease for moderate-advanced HIV
    if cd4 < 500:
        nodes["HIV_PROTEASE"] = HIV_PPI_NETWORK["HIV_PROTEASE"]
    
    # Add resistance variants for advanced HIV
    resistance_nodes = {}
    if cd4 < 350:
        resistance_nodes["HIV_PROT_D30N"] = RESISTANCE_VARIANTS["HIV_PROT_D30N"]
        resistance_nodes["HIV_PROT_V82A"] = RESISTANCE_VARIANTS["HIV_PROT_V82A"]
    if cd4 < 200:
        resistance_nodes["HIV_PROT_I50V"] = RESISTANCE_VARIANTS["HIV_PROT_I50V"]
        resistance_nodes["HIV_PROT_L90M"] = RESISTANCE_VARIANTS["HIV_PROT_L90M"]
    
    return nodes, resistance_nodes

VINA_EXE = "./bin/vina.exe"

def smiles_to_pdbqt(smiles: str, path: str) -> bool:
    """Convert SMILES to PDBQT using RDKit + Meeko."""
    try:
        import warnings
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from meeko import MoleculePreparation
        from meeko import PDBQTWriterLegacy
        mol = Chem.MolFromSmiles(smiles)
        if mol is None: return False
        mol = Chem.AddHs(mol)
        p = AllChem.ETKDGv3(); p.randomSeed = 42
        if AllChem.EmbedMolecule(mol, p) == -1:
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        AllChem.MMFFOptimizeMolecule(mol)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prep = MoleculePreparation()
            setups = prep.prepare(mol)
        if not setups: return False
        pdbqt, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        with open(path, 'w') as f: f.write(pdbqt)
        return True
    except Exception:
        return False

def dock_smiles_to_target(smiles: str, compound_id: str, target_key: str,
                           target_info: dict, exhaustiveness: int = 8) -> float | None:
    """Dock SMILES against target using ./bin/vina.exe"""
    receptor = target_info["receptor"]
    if not Path(receptor).exists():
        return None
    if not Path(VINA_EXE).exists():
        return None

    import re as _re
    with tempfile.NamedTemporaryFile(suffix=".pdbqt", delete=False, mode='w') as f:
        lig_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".pdbqt", delete=False, mode='w') as f:
        out_path = f.name

    try:
        if not smiles_to_pdbqt(smiles, lig_path):
            return None
        cx, cy, cz = target_info["center"]
        sx, sy, sz = target_info["size"]
        cmd = [
            VINA_EXE,
            "--receptor",       receptor,
            "--ligand",         lig_path,
            "--out",            out_path,
            "--center_x",       str(cx),
            "--center_y",       str(cy),
            "--center_z",       str(cz),
            "--size_x",         str(sx),
            "--size_y",         str(sy),
            "--size_z",         str(sz),
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes",      "3",
            "--energy_range",   "4",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = r.stdout + r.stderr
        for line in output.splitlines():
            m = _re.match(r'\s+(\d+)\s+(-?\d+\.\d+)', line)
            if m:
                return float(m.group(2))
        return None
    except Exception:
        return None
    finally:
        for p in [lig_path, out_path]:
            try: os.unlink(p)
            except: pass

def run_ppi_screen(compounds: list, cd4: float, viral_load: float,
                   exhaustiveness: int = 8) -> list:
    """
    Screen a list of compounds against the active HIV PPI network.
    Returns compounds annotated with multi-target binding profiles.
    """
    active_nodes, resistance_nodes = get_active_ppi_nodes(cd4, viral_load)
    all_nodes = {**active_nodes, **resistance_nodes}
    
    print(f"\n[PPI Network] Patient CD4={cd4:.0f}, Viral Load={viral_load:.0f}")
    print(f"[PPI Network] Active targets: {list(active_nodes.keys())}")
    if resistance_nodes:
        print(f"[PPI Network] Resistance variants: {list(resistance_nodes.keys())}")
    
    results = []
    for c in compounds[:10]:  # Screen top 10 candidates
        smiles = c.get("smiles", "")
        cid = c.get("id", "UNK")
        if not smiles:
            continue
        
        profile = {"id": cid, "smiles": smiles, "original_affinity": c.get("dock_affinity")}
        target_affinities = {}
        pan_score = 0
        n_targets = 0
        
        for tkey, tinfo in all_nodes.items():
            if not Path(tinfo["receptor"]).exists():
                continue
            aff = dock_smiles_to_target(smiles, cid, tkey, tinfo, exhaustiveness)
            if aff is not None:
                target_affinities[tkey] = aff
                ref = tinfo.get("ref_affinity", -8.0)
                # Normalize: 1.0 = matches reference, >1.0 = better
                pan_score += min(aff / ref, 1.0) if ref != 0 else 0
                n_targets += 1
        
        profile["target_affinities"] = target_affinities
        profile["pan_hiv_score"] = pan_score / n_targets if n_targets > 0 else 0
        profile["n_targets_hit"] = sum(1 for a in target_affinities.values() 
                                        if a < -6.0)
        
        # Resistance profile: does it still bind mutant protease?
        profile["resistance_coverage"] = {}
        for rkey, rinfo in resistance_nodes.items():
            if rkey in target_affinities:
                wt_aff = target_affinities.get("HIV_PROTEASE", -8.0)
                mut_aff = target_affinities[rkey]
                # If affinity loss <1 kcal/mol vs WT, covers this mutation
                profile["resistance_coverage"][rinfo["mutation"]] = (
                    "COVERED" if (mut_aff - wt_aff) < 1.0 else "RESISTANT"
                )
        
        results.append(profile)
        
        print(f"[PPI] {cid}: " + " | ".join(
            f"{k}={v:.2f}" for k, v in target_affinities.items()
        ))
        print(f"      Pan-HIV score={profile['pan_hiv_score']:.3f} | "
              f"Targets hit={profile['n_targets_hit']}")
    
    # Sort by pan-HIV score (higher = better multi-target coverage)
    results.sort(key=lambda x: x["pan_hiv_score"], reverse=True)
    return results

def save_ppi_results(results: list, run_id: str):
    """Save PPI network results to JSON and CSV."""
    json_path = f"ppi_results_{run_id}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    csv_path = f"ppi_results_{run_id}.csv"
    if results:
        fields = ["id", "smiles", "original_affinity", "pan_hiv_score", "n_targets_hit",
                  "HIV_RT", "HIV_INTEGRASE", "HIV_PROTEASE"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in results:
                row = {**r}
                for tkey, aff in r.get("target_affinities", {}).items():
                    row[tkey] = aff
                w.writerow(row)
    
    print(f"[PPI] Results saved: {json_path}, {csv_path}")
    return json_path, csv_path

if __name__ == "__main__":
    # Standalone test
    cd4 = float(os.environ.get("PATIENT_CD4", "320"))
    vl  = float(os.environ.get("PATIENT_VIRAL_LOAD", "158489"))
    
    # Load latest HIV integrase results
    import glob
    csvs = sorted(glob.glob("agent_results_HIV_INTEGRASE_*.csv"), 
                  key=os.path.getmtime)
    if not csvs:
        print("No HIV integrase results found")
        sys.exit(1)
    
    compounds = []
    with open(csvs[-1], encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("dock_affinity"):
                compounds.append({
                    "id": row["id"],
                    "smiles": row["smiles"],
                    "dock_affinity": float(row["dock_affinity"]),
                })
    
    compounds.sort(key=lambda x: x["dock_affinity"])
    print(f"[PPI] Loaded {len(compounds)} compounds from {csvs[-1]}")
    
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = run_ppi_screen(compounds, cd4, vl, exhaustiveness=4)
    save_ppi_results(results, run_id)
    
    if results:
        best = results[0]
        print(f"\n[PPI] Best pan-HIV candidate: {best['id']}")
        print(f"  Pan-HIV score: {best['pan_hiv_score']:.3f}")
        print(f"  Targets hit:   {best['n_targets_hit']}")
        print(f"  Target profile: {best.get('target_affinities', {})}")
