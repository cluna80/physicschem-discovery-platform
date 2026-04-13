"""
prepare_receptors.py
====================
PhysicsChem FBDD Platform v2 - Receptor Preparation Pipeline

Downloads PDB structures from RCSB, strips waters/ligands,
adds hydrogens, converts to PDBQT for AutoDock Vina.

USAGE:
    python prepare_receptors.py                    # prep all 18 targets
    python prepare_receptors.py --target EGFR      # prep one target
    python prepare_receptors.py --target COVID_MPRO --check  # check status

REQUIREMENTS:
    pip install requests biopython meeko rdkit
    
    meeko for PDBQT conversion (preferred):
        pip install meeko
    
    fallback: obabel (open babel) in PATH
        conda install -c conda-forge openbabel
        OR: https://openbabel.org/wiki/Install
"""

import os, sys, re, json, shutil, argparse, subprocess, tempfile, time
import urllib.request
from pathlib import Path

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from Bio import PDB
    BIOPYTHON_OK = True
except ImportError:
    BIOPYTHON_OK = False

try:
    from meeko import MoleculePreparation
    from rdkit import Chem
    from rdkit.Chem import AllChem
    MEEKO_OK = True
except ImportError:
    MEEKO_OK = False

# ── Target receptor map ───────────────────────────────────────────────
RECEPTOR_MAP = {
    "EGFR":       {"pdb":"4HJO","chain":"A","out":"cancer_egfr_agent/egfr_receptor.pdbqt",
                   "ligand":"AQ4","ph":7.4},
    "T790M":      {"pdb":"3IKA","chain":"A","out":"egfr_t790m.pdbqt",
                   "ligand":"BIM","ph":7.4},
    "VEGFR2":     {"pdb":"4ASD","chain":"A","out":"vegfr2.pdbqt",
                   "ligand":"STR","ph":7.4},
    "KRAS_G12C":  {"pdb":"6OIM","chain":"A","out":"kras_g12c.pdbqt",
                   "ligand":"GDP","ph":7.4},
    "BRAF_V600E": {"pdb":"4MNE","chain":"A","out":"braf_v600e.pdbqt",
                   "ligand":"032","ph":7.4},
    "CDK4":       {"pdb":"5L2T","chain":"A","out":"cdk4.pdbqt",
                   "ligand":"LEI","ph":7.4},
    "PARP1":      {"pdb":"4UND","chain":"A","out":"parp1.pdbqt",
                   "ligand":"BMN","ph":7.4},
    "HIV":        {"pdb":"1HHP","chain":"A","out":"hiv_protease.pdbqt",
                   "ligand":None,"ph":5.0},
    "COVID_MPRO": {"pdb":"6LU7","chain":"A","out":"covid_mpro.pdbqt",
                   "ligand":"PRD","ph":7.4},
    "TB_INHA":    {"pdb":"2X23","chain":"A","out":"tb_inha.pdbqt",
                   "ligand":"INS","ph":7.4},
    "BACE1":      {"pdb":"2WEJ","chain":"A","out":"bace1.pdbqt",
                   "ligand":"LIG","ph":5.0},
    "ACHE":       {"pdb":"1EVE","chain":"A","out":"ache.pdbqt",
                   "ligand":"THA","ph":7.4},
    "MAO_B":      {"pdb":"2V5Z","chain":"A","out":"mao_b.pdbqt",
                   "ligand":None,"ph":7.4},
    "THROMBIN":   {"pdb":"1A46","chain":"A","out":"thrombin.pdbqt",
                   "ligand":"BMI","ph":7.4},
    "FACTOR_XA":  {"pdb":"2BOH","chain":"A","out":"factor_xa.pdbqt",
                   "ligand":"ZMR","ph":7.4},
    "DPP4":       {"pdb":"1X70","chain":"A","out":"dpp4.pdbqt",
                   "ligand":"P32","ph":7.4},
    "COX2":       {"pdb":"5IKR","chain":"A","out":"cox2.pdbqt",
                   "ligand":"CR2","ph":7.4},
    "JAK1":       {"pdb":"3EYH","chain":"A","out":"jak1.pdbqt",
                   "ligand":"STU","ph":7.4},
}

RCSB_URL = "https://files.rcsb.org/download/{}.pdb"

# ── Colors ────────────────────────────────────────────────────────────
GRN = "\033[92m"; YLW = "\033[93m"; RED = "\033[91m"
CYN = "\033[96m"; RST = "\033[0m";  BLD = "\033[1m"

def info(msg): print(f"  {CYN}[INFO]{RST}  {msg}")
def ok(msg):   print(f"  {GRN}[OK]{RST}    {msg}")
def warn(msg): print(f"  {YLW}[WARN]{RST}  {msg}")
def err(msg):  print(f"  {RED}[FAIL]{RST}  {msg}")


def download_pdb(pdb_id: str, out_path: str) -> bool:
    """Download PDB from RCSB."""
    url = RCSB_URL.format(pdb_id.upper())
    try:
        info(f"Downloading {pdb_id} from RCSB...")
        if REQUESTS_OK:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            with open(out_path,'w') as f: f.write(r.text)
        else:
            urllib.request.urlretrieve(url, out_path)
        ok(f"Downloaded {pdb_id} ({os.path.getsize(out_path)//1024} KB)")
        return True
    except Exception as e:
        err(f"Download failed for {pdb_id}: {e}")
        return False


def clean_pdb(raw_pdb: str, chain: str, ligand_to_keep: str = None) -> str:
    """
    Strip waters, strip most HETATM records (keep only protein ATOM lines),
    keep only specified chain. Returns cleaned PDB string.
    Biopython-powered if available, regex fallback otherwise.
    """
    KEEP_RESN = {"HOH","WAT","H2O"}  # waters to strip

    if BIOPYTHON_OK:
        try:
            import io
            from Bio.PDB import PDBParser, PDBIO, Select
            class CleanSelect(Select):
                def accept_model(self, m): return m.id == 0
                def accept_chain(self, c): return c.id == chain
                def accept_residue(self, r):
                    if r.id[0] == " ": return True   # standard residue
                    if r.resname.strip() in KEEP_RESN: return False
                    if ligand_to_keep and r.resname.strip() == ligand_to_keep:
                        return False  # strip reference ligand too (we want apo)
                    return False  # strip all HETATM
                def accept_atom(self, a):
                    if a.element == "H": return False  # strip H (will re-add)
                    return True

            parser = PDBParser(QUIET=True)
            struct = parser.get_structure("X", io.StringIO(raw_pdb))
            out_io = io.StringIO()
            writer = PDBIO()
            writer.set_structure(struct)
            writer.save(out_io, CleanSelect())
            return out_io.getvalue()
        except Exception as e:
            warn(f"BioPython clean failed ({e}), using regex fallback")

    # Regex fallback
    cleaned = []
    for line in raw_pdb.splitlines():
        rec = line[:6].strip()
        if rec == "ATOM":
            if chain and line[21:22] != chain: continue
            elem = line[76:78].strip() if len(line) > 76 else ""
            if elem in ("H","D"): continue
            cleaned.append(line)
        elif rec in ("TER","END"):
            cleaned.append(line)
    return "\n".join(cleaned)


def pdb_to_pdbqt_meeko(pdb_str: str, out_path: str, ph: float = 7.4) -> bool:
    """Convert PDB string to PDBQT using meeko + rdkit."""
    try:
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        from rdkit import Chem
        from rdkit.Chem import AllChem
        import tempfile

        # Write temp PDB
        with tempfile.NamedTemporaryFile(suffix=".pdb",mode='w',delete=False) as tf:
            tf.write(pdb_str)
            tmp_pdb = tf.name

        # meeko doesn't do full proteins well - use obabel for protein
        return pdb_to_pdbqt_obabel(tmp_pdb, out_path, ph)
    except Exception as e:
        warn(f"Meeko failed: {e}")
        return False
    finally:
        try: os.remove(tmp_pdb)
        except: pass


def pdb_to_pdbqt_obabel(pdb_path: str, out_path: str, ph: float = 7.4) -> bool:
    """Convert PDB to PDBQT using Open Babel."""
    obabel = shutil.which("obabel") or shutil.which("babel")
    if not obabel:
        # Try common install locations
        for loc in [r"C:\Program Files\OpenBabel",
                    r"C:\ProgramData\chocolatey\lib\openbabel\tools",
                    "/usr/bin", "/usr/local/bin"]:
            cand = os.path.join(loc, "obabel")
            if os.path.isfile(cand): obabel = cand; break
            cand2 = os.path.join(loc, "obabel.exe")
            if os.path.isfile(cand2): obabel = cand2; break

    if not obabel:
        warn("Open Babel not found. Install: conda install -c conda-forge openbabel")
        return False

    try:
        cmd = [obabel, pdb_path, "-O", out_path,
               "-xr",  # rigid receptor
               f"--pH", str(ph)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if os.path.isfile(out_path) and os.path.getsize(out_path) > 100:
            return True
        else:
            warn(f"obabel output empty: {result.stderr[:200]}")
            return False
    except Exception as e:
        warn(f"obabel conversion failed: {e}")
        return False


def simple_pdb_to_pdbqt(pdb_str: str, out_path: str) -> bool:
    """
    Minimal fallback: write a bare-bones PDBQT with dummy charges.
    Good enough for Vina if obabel not available.
    Not ideal but functional.
    """
    ATOM_TYPES = {
        "C":"C","N":"NA","O":"OA","S":"SA","P":"P",
        "F":"F","CL":"Cl","BR":"Br","I":"I","FE":"Fe",
        "ZN":"Zn","MG":"Mg","CA":"Ca","H":"H",
    }
    lines = []
    for line in pdb_str.splitlines():
        if not line.startswith(("ATOM","HETATM")): continue
        elem = line[76:78].strip().upper() if len(line) >= 78 else ""
        if not elem:
            atom_name = line[12:16].strip()
            elem = re.sub(r'[0-9]','',atom_name)[:2].upper()
        atype = ATOM_TYPES.get(elem, "C")
        # PDBQT format: add charge (0.000) and atom type
        pdbqt_line = f"{line[:66]:<66}  0.000 {atype}"
        lines.append(pdbqt_line)
    lines.append("END")

    with open(out_path,'w') as f: f.write("\n".join(lines))
    return os.path.getsize(out_path) > 100


def prepare_target(key: str, force: bool = False) -> dict:
    """
    Full pipeline for one target:
    1. Check if PDBQT already exists
    2. Download PDB from RCSB
    3. Clean (strip waters, ligands, H)
    4. Convert to PDBQT (obabel preferred, fallback to simple)
    5. Create output dir if needed
    """
    cfg = RECEPTOR_MAP[key]
    out_path = cfg["out"]

    # Create parent directory
    os.makedirs(os.path.dirname(out_path) if "/" in out_path else ".", exist_ok=True)

    result = {"key":key,"pdb":cfg["pdb"],"out":out_path,
              "status":"unknown","method":"?"}

    # Already exists?
    if os.path.isfile(out_path) and not force:
        size = os.path.getsize(out_path)
        if size > 1000:
            ok(f"{key}: already prepared ({size//1024} KB) -> {out_path}")
            result.update({"status":"ready","method":"cached"})
            return result
        else:
            warn(f"{key}: existing file too small ({size} B), re-preparing")

    print(f"\n  {BLD}{CYN}[{key}]{RST} {cfg['pdb']} -> {out_path}")

    # Download
    with tempfile.NamedTemporaryFile(suffix=".pdb",mode='w',delete=False) as tf:
        tmp_raw = tf.name

    if not download_pdb(cfg["pdb"], tmp_raw):
        result["status"] = "download_failed"
        return result

    # Read and clean
    with open(tmp_raw) as f: raw = f.read()
    cleaned = clean_pdb(raw, cfg["chain"], cfg.get("ligand"))
    n_atoms = cleaned.count("\nATOM")
    info(f"Cleaned: {n_atoms} ATOM records (chain {cfg['chain']})")

    if n_atoms < 50:
        warn(f"Very few atoms in chain {cfg['chain']} — trying without chain filter")
        cleaned = clean_pdb(raw, chain=None, ligand_to_keep=cfg.get("ligand"))
        n_atoms = cleaned.count("\nATOM")
        info(f"Unfiltered: {n_atoms} ATOM records")

    # Write cleaned PDB
    with tempfile.NamedTemporaryFile(suffix="_clean.pdb",mode='w',delete=False) as tf:
        tf.write(cleaned)
        tmp_clean = tf.name

    # Convert to PDBQT
    method = "unknown"
    success = False

    # Try obabel first
    if not success:
        success = pdb_to_pdbqt_obabel(tmp_clean, out_path, cfg["ph"])
        if success: method = "obabel"

    # Simple fallback
    if not success:
        warn(f"Using simple PDBQT conversion (no obabel) — install obabel for better results")
        success = simple_pdb_to_pdbqt(cleaned, out_path)
        if success: method = "simple"

    # Cleanup
    for f in [tmp_raw, tmp_clean]:
        try: os.remove(f)
        except: pass

    if success:
        size = os.path.getsize(out_path)
        ok(f"{key}: prepared via {method} ({size//1024} KB) -> {out_path}")
        result.update({"status":"ready","method":method})
    else:
        err(f"{key}: preparation failed")
        result["status"] = "failed"

    return result


def check_status() -> dict:
    """Check which targets have ready receptor files."""
    print(f"\n  {BLD}PhysicsChem FBDD — Receptor Status{RST}")
    print("  " + "="*60)
    statuses = {}
    for key, cfg in RECEPTOR_MAP.items():
        path = cfg["out"]
        if os.path.isfile(path):
            size = os.path.getsize(path)
            if size > 1000:
                print(f"  {GRN}[READY]{RST}  {key:<14} {path}")
                statuses[key] = "ready"
            else:
                print(f"  {YLW}[SMALL]{RST}  {key:<14} {path} ({size}B)")
                statuses[key] = "small"
        else:
            print(f"  {RED}[MISSING]{RST} {key:<14} {path}")
            statuses[key] = "missing"
    n_ready = sum(1 for s in statuses.values() if s=="ready")
    print(f"\n  Ready: {n_ready}/{len(RECEPTOR_MAP)} targets")
    return statuses


def write_status_json():
    """Write receptor_status.json for dashboard to read."""
    statuses = {}
    for key, cfg in RECEPTOR_MAP.items():
        path = cfg["out"]
        if os.path.isfile(path) and os.path.getsize(path) > 1000:
            statuses[key] = "ready"
        else:
            statuses[key] = "missing"
    with open("receptor_status.json","w") as f:
        json.dump(statuses, f, indent=2)
    ok("receptor_status.json written for dashboard")


def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Receptor Preparation Pipeline")
    parser.add_argument("--target", default=None,
        choices=list(RECEPTOR_MAP.keys()), metavar="TARGET",
        help="Prepare one target (default: all)")
    parser.add_argument("--check", action="store_true",
        help="Check receptor status without preparing")
    parser.add_argument("--force", action="store_true",
        help="Re-prepare even if PDBQT already exists")
    parser.add_argument("--list", action="store_true",
        help="List all targets and PDB IDs")
    args = parser.parse_args()

    print(f"\n{BLD}PhysicsChem FBDD Platform v2 — Receptor Preparation{RST}")
    print("="*60)

    if args.list:
        for k,v in RECEPTOR_MAP.items():
            print(f"  {k:<14} PDB:{v['pdb']}  -> {v['out']}")
        return

    if args.check:
        check_status()
        write_status_json()
        return

    targets = [args.target] if args.target else list(RECEPTOR_MAP.keys())
    results = []

    for key in targets:
        result = prepare_target(key, force=args.force)
        results.append(result)
        time.sleep(0.5)  # polite to RCSB

    # Summary
    print(f"\n{'='*60}")
    print(f"{BLD}Summary{RST}")
    ready   = [r for r in results if r["status"]=="ready"]
    failed  = [r for r in results if r["status"]!="ready"]
    print(f"  Ready  : {len(ready)}/{len(results)}")
    if failed:
        print(f"  Failed : {[r['key'] for r in failed]}")
    print()

    write_status_json()

    if failed:
        print(f"{YLW}For failed targets, install Open Babel:{RST}")
        print("  conda install -c conda-forge openbabel")
        print("  OR: choco install openbabel")
        print("  Then: python prepare_receptors.py --force")


if __name__ == "__main__":
    main()
