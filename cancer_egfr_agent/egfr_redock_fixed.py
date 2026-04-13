#!/usr/bin/env python3
"""
egfr_redock_fixed.py  v3
MODE flag controls what gets docked:
  "results"  → top N from results.json  (original behaviour)
  "variants" → warhead-extended variants of best candidate
  "custom"   → whatever is in CUSTOM_CANDIDATES list
"""

import json, subprocess
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# ===========================================
# CONFIG
# ===========================================

MODE           = "variants"   # "results" | "variants" | "custom"

PDB_FILE       = Path("4ZAU.pdb")
RESULTS_JSON   = Path("egfr_fragment_based_fixed/results.json")
OUTPUT_DIR     = Path("vina_docking_v4")
EXHAUSTIVENESS = 24
NUM_MODES      = 9
BOX_SIZE       = (22.0, 22.0, 22.0)
TOP_N          = 20           # only used in "results" mode

# Confirmed from PyMOL click inspection
CYS_RESI = 797   # CYS751 SG — covalent warhead target
MET_RESI = 742   # MET742 N  — hinge H-bond

OUTPUT_DIR.mkdir(exist_ok=True)

# ===========================================
# WARHEAD VARIANTS
# Best candidate (rank 1, -10.54 kcal/mol):
#   C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCC)c4ncncc4c3)c(C)c2n1
# Issue: CYS751 SG = 6.2-6.4 Å across all linker lengths — orientation problem.
# Next: flip attachment point + piperazine+acrylamide combo
# ===========================================

WARHEAD_VARIANTS = [
    {
        "name":   "original",
        "note":   "best from evolution — CYS751 6.35 Å (baseline)",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCC)c4ncncc4c3)c(C)c2n1",
        "generation": "38", "fitness": 184.0, "mw": 477.0, "logp": 3.00,
    },
    {
        "name":   "linker+1",
        "note":   "+1 CH2 in amine linker — target CYS751 < 5 Å",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCCC)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 491.0, "logp": 3.05,
    },
    {
        "name":   "linker+2",
        "note":   "+2 CH2 — maximum reach toward CYS751",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCCCC)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 505.0, "logp": 3.10,
    },
    {
        "name":   "E_acrylamide",
        "note":   "trans acrylamide — locks Michael acceptor geometry",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(/C=C/C(=O)NCC)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 477.0, "logp": 3.00,
    },
    {
        "name":   "piperazine",
        "note":   "piperazine linker — -11.45 kcal/mol lead, non-covalent",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)N4CCNCC4)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 517.0, "logp": 2.85,
    },
    {
        "name":   "dimethyl_linker",
        "note":   "N,N-dimethyl + longer chain — osimertinib-like solubilizer",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)NCCN(C)C)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 504.0, "logp": 3.20,
    },
    {
        "name":   "warhead_flipped",
        "note":   "acrylamide on N-side of phthalazine — different vector toward CYS751",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(NCC(=O)C=C)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 477.0, "logp": 3.00,
    },
    {
        "name":   "piperazine_acrylamide",
        "note":   "piperazine + acrylamide N-cap — best of both worlds",
        "smiles": "C#Cc1cnc2c(C#C)c(OCCN)c(-c3cc(C=CC(=O)N4CCN(C=O)CC4)c4ncncc4c3)c(C)c2n1",
        "generation": "variant", "fitness": 0.0, "mw": 571.0, "logp": 2.90,
    },
]

# ===========================================
# CUSTOM CANDIDATES
# ===========================================

CUSTOM_CANDIDATES = [
    # {"name": "my_compound", "smiles": "...", "generation": "manual", "fitness": 0, "mw": 0, "logp": 0},
]

# ===========================================
# BOX CENTER
# ===========================================

def get_box_center_from_pdb(pdb_path: Path):
    SKIP = {"HOH","WAT","EDO","GOL","SO4","PO4","CL","NA","MG",
            "ZN","CA","FE","MN","CO","NI","CU","K","BR","I",
            "DMS","ACT","ACY","MPD","PEG","BME","DTT","TRS"}
    coords, ligand_name = [], None
    with open(pdb_path) as f:
        for line in f:
            if not line.startswith("HETATM"):
                continue
            resname = line[17:20].strip()
            if resname in SKIP:
                continue
            try:
                coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
                ligand_name = ligand_name or resname
            except ValueError:
                continue
    if not coords:
        return None, None
    n = len(coords)
    return (round(sum(c[0] for c in coords)/n, 2),
            round(sum(c[1] for c in coords)/n, 2),
            round(sum(c[2] for c in coords)/n, 2)), ligand_name

# ===========================================
# PDBQT PREP
# ===========================================

def fix_pdbqt_atom_types(pdbqt_path: Path):
    AD = {'C': 'C.3', 'N': 'N.3', 'O': 'O.3', 'S': 'S.3', 'P': 'P.3'}
    lines = pdbqt_path.read_text().splitlines()
    fixed = []
    for line in lines:
        if line.startswith(('ATOM', 'HETATM')):
            parts = line.split()
            if parts and parts[-1] in AD:
                last = parts[-1]
                line = line.rstrip()[:line.rstrip().rfind(last)] + AD[last]
        fixed.append(line)
    pdbqt_path.write_text('\n'.join(fixed) + '\n')


def mol_to_pdbqt(mol, out_path: Path) -> bool:
    # meeko v0.5
    try:
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        setups = MoleculePreparation().prepare(mol)
        pdbqt_str, ok, err = PDBQTWriterLegacy.write_string(setups[0])
        if ok:
            out_path.write_text(pdbqt_str)
            return True
    except Exception:
        pass
    # meeko legacy
    try:
        import warnings
        from meeko import MoleculePreparation
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prep = MoleculePreparation()
            prep.prepare(mol)
            out_path.write_text(prep.write_pdbqt_string())
        return True
    except Exception:
        pass
    # obabel fallback
    try:
        sdf = out_path.with_suffix('.sdf')
        Chem.SDWriter(str(sdf)).write(mol)
        subprocess.run(["obabel", str(sdf), "-O", str(out_path),
                        "--partialcharge", "gasteiger", "-h"],
                       capture_output=True, text=True, timeout=30)
        sdf.unlink(missing_ok=True)
        if out_path.exists():
            fix_pdbqt_atom_types(out_path)
            return True
    except Exception as e:
        print(f"    [obabel] {e}")
    return False


def smiles_to_3d(smiles: str):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    mol = Chem.AddHs(mol)
    for method in [AllChem.ETKDGv3(), AllChem.ETKDG()]:
        if AllChem.EmbedMolecule(mol, method) == 0:
            AllChem.MMFFOptimizeMolecule(mol, maxIters=2000)
            return mol
    return None

# ===========================================
# VINA
# ===========================================

def run_vina(ligand_pdbqt: Path, out_pdbqt: Path, center: tuple, size: tuple) -> dict:
    cx, cy, cz = center
    sx, sy, sz = size
    cmd = ["vina",
           "--receptor",       "egfr_4zau_receptor.pdbqt",
           "--ligand",         str(ligand_pdbqt),
           "--out",            str(out_pdbqt),
           "--center_x",       str(cx), "--center_y", str(cy), "--center_z", str(cz),
           "--size_x",         str(sx), "--size_y",   str(sy), "--size_z",   str(sz),
           "--exhaustiveness", str(EXHAUSTIVENESS),
           "--num_modes",      str(NUM_MODES)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
        output = r.stdout + r.stderr
        poses = []
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) == 4 and parts[0].isdigit():
                try:
                    poses.append({"mode": int(parts[0]), "affinity": float(parts[1]),
                                  "rmsd_lb": float(parts[2]), "rmsd_ub": float(parts[3])})
                except ValueError:
                    continue
        if poses:
            return {"success": True, "best": poses[0]["affinity"], "poses": poses}
        return {"success": False, "error": "No poses", "log": output[-400:]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===========================================
# CYS DISTANCE — auto-measured from PDBQT
# ===========================================

def measure_cys_distance(docked_pdbqt: Path) -> float | None:
    try:
        cys_coords = []
        with open("egfr_4zau_receptor.pdbqt") as f:
            for line in f:
                if line.startswith("ATOM") and f" {CYS_RESI} " in line and "SG" in line:
                    cys_coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        if not cys_coords:
            return None
        lig_coords = []
        in_model1 = False
        with open(docked_pdbqt) as f:
            for line in f:
                if "MODEL 1" in line:
                    in_model1 = True
                elif "ENDMDL" in line and in_model1:
                    break
                elif in_model1 and line.startswith(("ATOM", "HETATM")):
                    elem = line[77:79].strip()
                    if elem not in ("H", "HD"):
                        lig_coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        if not lig_coords:
            return None
        return round(min(
            ((lx-cx)**2 + (ly-cy)**2 + (lz-cz)**2)**0.5
            for (lx, ly, lz) in lig_coords
            for (cx, cy, cz) in cys_coords
        ), 2)
    except Exception:
        return None

# ===========================================
# MAIN
# ===========================================

def main():
    print("=" * 70)
    print(f"EGFR REDOCK v3 — Mode: {MODE.upper()}")
    print("=" * 70)

    center, ligand_name = get_box_center_from_pdb(PDB_FILE)
    if center:
        print(f"\n✓ Ligand '{ligand_name}' centroid: {center}")
    else:
        center = (24.77, 9.19, 0.0)
        print(f"\n[WARN] Using fallback center: {center}")
    print(f"  Box size: {BOX_SIZE}")

    if not Path("egfr_4zau_receptor.pdbqt").exists():
        print("\n[ERROR] egfr_4zau_receptor.pdbqt not found")
        return

    if MODE == "results":
        with open(RESULTS_JSON) as f:
            raw = json.load(f)[:TOP_N]
        candidates = [{"name": f"cand_{i+1}", **c} for i, c in enumerate(raw)]
    elif MODE == "variants":
        candidates = WARHEAD_VARIANTS
    elif MODE == "custom":
        candidates = CUSTOM_CANDIDATES
    else:
        print(f"[ERROR] Unknown MODE: {MODE}")
        return

    print(f"\nDocking {len(candidates)} candidates  "
          f"(exhaustiveness={EXHAUSTIVENESS}, modes={NUM_MODES})\n")

    results = []
    for i, cand in enumerate(candidates):
        name   = cand.get("name", f"cand_{i+1}")
        smiles = cand["smiles"]
        note   = cand.get("note", "")
        print(f"[{i+1:02d}/{len(candidates)}] {name}")
        if note:
            print(f"  Note: {note}")
        print(f"  SMILES: {smiles[:72]}")

        lig_path = OUTPUT_DIR / f"lig_{i+1:02d}_{name}.pdbqt"
        out_path = OUTPUT_DIR / f"docked_{i+1:02d}_{name}.pdbqt"

        mol = smiles_to_3d(smiles)
        if not mol:
            print("  [SKIP] 3D generation failed\n")
            results.append({**cand, "docking": {"success": False, "error": "3D gen failed"}})
            continue
        if not mol_to_pdbqt(mol, lig_path):
            print("  [SKIP] PDBQT conversion failed\n")
            results.append({**cand, "docking": {"success": False, "error": "PDBQT failed"}})
            continue

        dock = run_vina(lig_path, out_path, center, BOX_SIZE)

        cys_dist = None
        if dock["success"] and out_path.exists():
            cys_dist = measure_cys_distance(out_path)
            dock["cys751_sg_dist"] = cys_dist

        if dock["success"]:
            aff   = dock["best"]
            stars = "★★★" if aff < -9.0 else "★★" if aff < -8.0 else "★" if aff < -7.0 else ""
            cov   = (" ← COVALENT GEOMETRY OK" if cys_dist and cys_dist < 4.5 else
                     " ← borderline"            if cys_dist and cys_dist < 5.5 else
                     " ← warhead too far"        if cys_dist else "")
            print(f"  Affinity : {aff:.3f} kcal/mol  {stars}")
            if cys_dist:
                print(f"  CYS751 SG: {cys_dist:.2f} Å{cov}")
            print()
        else:
            print(f"  [FAIL] {dock.get('error')}\n")

        results.append({**cand, "docking": dock})

    success = sorted([r for r in results if r["docking"].get("success")],
                     key=lambda x: x["docking"]["best"])

    print("\n" + "=" * 70)
    print("FINAL RANKING")
    print("=" * 70)
    print(f"\n{'#':<4} {'Name':<22} {'Affinity':>10} {'CYS751 SG':>10}  {'Stars':<5}  Note")
    print("-" * 85)
    for dr, r in enumerate(success, 1):
        d     = r["docking"]
        aff   = d["best"]
        dist  = d.get("cys751_sg_dist")
        ds    = f"{dist:.2f} Å" if dist else "  n/a"
        stars = "★★★" if aff < -9.0 else "★★" if aff < -8.0 else "★" if aff < -7.0 else ""
        cov   = "✓ covalent" if dist and dist < 4.5 else ("~ border" if dist and dist < 5.5 else "")
        print(f"{dr:<4} {r.get('name','?'):<22} {aff:>10.3f} {ds:>10}  {stars:<5}  {cov}")

    print(f"\nRef: Osimertinib ~-9.5 to -11.0 | Erlotinib ~-8.5 to -10.0 kcal/mol")
    print(f"Covalent geometry: CYS751 SG < 4.5 Å = viable Michael acceptor")
    print(f"\nBox: center={center}  size={BOX_SIZE}")

    out_json = OUTPUT_DIR / "ranked_docking_v3.json"
    with open(out_json, "w") as f:
        json.dump({"mode": MODE, "box_center": center,
                   "box_size": BOX_SIZE, "results": success}, f, indent=2)
    print(f"\nSaved : {out_json}")
    print(f"Poses : {OUTPUT_DIR}/docked_*.pdbqt")


if __name__ == "__main__":
    main()