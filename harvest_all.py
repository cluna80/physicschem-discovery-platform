"""
harvest_all.py
==============
PhysicsChem Platform — Universal Campaign Harvester

Scans your entire project folder for ALL previous discovery results
across every format:
  - agent_results_*.csv          (autonomous agent runs)
  - gnina_results*.csv/json      (Gnina GPU docking)
  - cure_*.json / hiv_*.json     (CURE series campaigns)
  - quantum_*.json               (quantum search results)
  - *_results.json               (any results JSON)
  - whitepaper SMILES            (manually entered leads)

Deduplicates by SMILES, enriches with RDKit properties,
and loads everything into fragment_library.db.

USAGE:
    python harvest_all.py                    # harvest everything
    python harvest_all.py --dry-run          # preview without writing
    python harvest_all.py --folder .         # specify folder
    python harvest_all.py --show-formats     # show what formats found
"""

import os, sys, json, csv, re, sqlite3, hashlib, argparse
import warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings('ignore')

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False

# ── Colors ────────────────────────────────────────────────────────────
GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {color}{msg}{RST}")

def ok(msg):  log(f"  ✓  {msg}", GRN)
def warn(msg): log(f"  !  {msg}", YLW)

# ── Disease area mapping ──────────────────────────────────────────────
DISEASE_MAP = {
    "EGFR": ("Oncology", "Non-Small Cell Lung Cancer"),
    "T790M": ("Oncology", "NSCLC (T790M resistant)"),
    "HIV": ("Infectious Disease", "HIV/AIDS"),
    "HIV_INTEGRASE": ("Infectious Disease", "HIV/AIDS"),
    "HIV_INT": ("Infectious Disease", "HIV/AIDS"),
    "COVID_MPRO": ("Infectious Disease", "COVID-19"),
    "COVID": ("Infectious Disease", "COVID-19"),
    "BACE1": ("Neurological", "Alzheimer's Disease"),
    "THROMBIN": ("Cardiovascular", "Thrombosis"),
    "VEGFR2": ("Oncology", "Angiogenesis"),
    "KRAS_G12C": ("Oncology", "KRAS-driven cancers"),
    "BRAF_V600E": ("Oncology", "Melanoma"),
    "CDK4": ("Oncology", "Cell cycle"),
    "PARP1": ("Oncology", "DNA damage response"),
    "ACHE": ("Neurological", "Alzheimer's Disease"),
    "MAO_B": ("Neurological", "Parkinson's Disease"),
    "FACTOR_XA": ("Cardiovascular", "Thrombosis"),
    "DPP4": ("Metabolic", "Type 2 Diabetes"),
    "COX2": ("Inflammation", "Inflammation/Pain"),
    "JAK1": ("Inflammation", "Autoimmune"),
    "TB_INHA": ("Infectious Disease", "Tuberculosis"),
    "HER2": ("Oncology", "Breast/Gastric Cancer"),
    "BCR_ABL": ("Oncology", "CML Leukemia"),
}

def infer_target_from_filename(filename: str) -> str:
    """Infer target from filename."""
    fn = filename.upper()
    for key in DISEASE_MAP:
        if key in fn:
            return key
    if "CURE" in fn or "HIV" in fn:
        return "HIV"
    if "EGFR" in fn or "ERLOTINIB" in fn or "GEFITINIB" in fn:
        return "EGFR"
    if "COVID" in fn or "MPRO" in fn or "NIRMATRELVIR" in fn:
        return "COVID_MPRO"
    if "GNINA" in fn:
        return "HIV"  # most gnina runs were HIV
    if "QUANTUM" in fn and "HIV" in fn:
        return "HIV"
    return "UNKNOWN"

def calc_props(smiles: str) -> dict:
    """Calculate molecular properties."""
    props = {"mw": None, "logp": None, "hbd": None, "hba": None,
             "tpsa": None, "rotbonds": None, "rings": None, "inchi_key": None}
    if not RDKIT_OK or not smiles:
        return props
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return props
        props.update({
            "mw":       round(Descriptors.MolWt(mol), 2),
            "logp":     round(Descriptors.MolLogP(mol), 2),
            "hbd":      rdMolDescriptors.CalcNumHBD(mol),
            "hba":      rdMolDescriptors.CalcNumHBA(mol),
            "tpsa":     round(Descriptors.TPSA(mol), 1),
            "rotbonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
            "rings":    rdMolDescriptors.CalcNumRings(mol),
        })
        try:
            from rdkit.Chem.inchi import MolToInchiKey
            props["inchi_key"] = MolToInchiKey(mol)
        except Exception:
            pass
    except Exception:
        pass
    return props

def validate_smiles(smiles: str) -> bool:
    """Check if SMILES is valid."""
    if not RDKIT_OK or not smiles:
        return bool(smiles and len(smiles) > 3)
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol is not None
    except Exception:
        return False

def make_compound_id(smiles: str, prefix: str = "HARVEST") -> str:
    h = hashlib.md5(smiles.encode()).hexdigest()[:8].upper()
    return f"{prefix}_{h}"

# ══════════════════════════════════════════════════════════════════════
# PARSERS — one per file format
# ══════════════════════════════════════════════════════════════════════

def parse_agent_results_csv(path: str) -> list:
    """Parse standard agent_results_*.csv files."""
    results = []
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as f:
            for row in csv.DictReader(f):
                smiles = row.get('smiles', row.get('SMILES', ''))
                if not smiles or not validate_smiles(smiles):
                    continue
                aff = float(row.get('dock_affinity', row.get('affinity', 0)) or 0)
                if aff >= -4.0:
                    continue
                results.append({
                    'smiles':       smiles,
                    'id':           row.get('id', make_compound_id(smiles)),
                    'dock_affinity': aff,
                    'ligand_eff':   float(row.get('LE', row.get('ligand_eff', 0)) or 0),
                    'confidence':   int(float(row.get('confidence', 0) or 0)),
                    'hERG':         float(row.get('hERG', 0) or 0),
                    'DILI':         float(row.get('DILI', 0) or 0),
                    'AMES':         float(row.get('AMES', 0) or 0),
                    'source':       'agent_csv',
                })
    except Exception as e:
        warn(f"CSV parse error {path}: {e}")
    return results

def parse_gnina_results(path: str) -> list:
    """Parse gnina_results*.csv or gnina_results*.json"""
    results = []
    try:
        if path.endswith('.json'):
            with open(path, encoding='utf-8', errors='replace') as f:
                data = json.load(f)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('results', data.get('compounds',
                         data.get('candidates', list(data.values()))))
                if isinstance(items, dict):
                    items = list(items.values())
            else:
                return []
            for item in items:
                if not isinstance(item, dict):
                    continue
                smiles = item.get('smiles', item.get('SMILES', ''))
                if not smiles or not validate_smiles(smiles):
                    continue
                aff = float(item.get('affinity', item.get('vina_affinity',
                      item.get('score', item.get('dock_affinity', 0)))) or 0)
                cnn = float(item.get('cnn_affinity', item.get('CNN_affinity',
                      item.get('cnn_score', 0))) or 0)
                if aff >= -4.0:
                    continue
                results.append({
                    'smiles':       smiles,
                    'id':           item.get('id', item.get('name',
                                    item.get('compound_id',
                                    make_compound_id(smiles, 'GNINA')))),
                    'dock_affinity': aff,
                    'ligand_eff':   0.0,
                    'confidence':   min(int(abs(aff) * 8), 90),
                    'hERG':         0.0,
                    'DILI':         0.0,
                    'AMES':         0.0,
                    'notes':        f"CNN_affinity={cnn:.3f}" if cnn else "",
                    'source':       'gnina',
                })
        else:  # CSV
            with open(path, encoding='utf-8-sig', errors='replace') as f:
                for row in csv.DictReader(f):
                    smiles = row.get('smiles', row.get('SMILES', ''))
                    if not smiles or not validate_smiles(smiles):
                        continue
                    aff = float(row.get('affinity', row.get('vina_affinity',
                          row.get('score', 0))) or 0)
                    if aff >= -4.0:
                        continue
                    results.append({
                        'smiles':       smiles,
                        'id':           row.get('name', row.get('id',
                                        make_compound_id(smiles, 'GNINA'))),
                        'dock_affinity': aff,
                        'ligand_eff':   0.0,
                        'confidence':   min(int(abs(aff) * 8), 90),
                        'hERG':         0.0,
                        'DILI':         0.0,
                        'AMES':         0.0,
                        'source':       'gnina_csv',
                    })
    except Exception as e:
        warn(f"Gnina parse error {path}: {e}")
    return results

def parse_json_results(path: str) -> list:
    """Generic JSON results parser — handles many formats."""
    results = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            data = json.load(f)

        # Flatten to list of dicts
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ['results', 'compounds', 'candidates', 'hits',
                        'discoveries', 'leads', 'molecules']:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            if not items:
                # Try treating values as compounds
                for v in data.values():
                    if isinstance(v, dict) and ('smiles' in v or 'SMILES' in v):
                        items.append(v)
                    elif isinstance(v, list):
                        for vi in v:
                            if isinstance(vi, dict):
                                items.append(vi)

        for item in items:
            if not isinstance(item, dict):
                continue
            smiles = (item.get('smiles') or item.get('SMILES') or
                      item.get('smile') or '')
            if not smiles or not validate_smiles(smiles):
                continue
            aff = float(item.get('affinity', item.get('dock_affinity',
                  item.get('vina_affinity', item.get('score',
                  item.get('docking_score', 0))))) or 0)
            if aff == 0:
                # Try finding any negative float
                for k, v in item.items():
                    if isinstance(v, (int, float)) and -15 < v < -3:
                        aff = float(v)
                        break
            if aff >= -4.0:
                continue

            cid = (item.get('id') or item.get('compound_id') or
                   item.get('name') or item.get('ID') or
                   make_compound_id(smiles, 'JSON'))

            results.append({
                'smiles':       smiles,
                'id':           str(cid),
                'dock_affinity': aff,
                'ligand_eff':   float(item.get('LE', item.get('ligand_efficiency', 0)) or 0),
                'confidence':   int(float(item.get('confidence', item.get('conf', 0)) or 0)),
                'hERG':         float(item.get('hERG', item.get('herg', 0)) or 0),
                'DILI':         float(item.get('DILI', item.get('dili', 0)) or 0),
                'AMES':         float(item.get('AMES', item.get('ames', 0)) or 0),
                'sigma_label':  str(item.get('sigma', item.get('sigma_label', ''))),
                'source':       'json',
            })
    except Exception as e:
        pass  # Many JSONs will fail, that's OK
    return results

def parse_whitepaper_smiles() -> list:
    """
    Parse the known lead compounds from previous campaigns
    that are documented in whitepapers/reports.
    """
    KNOWN_LEADS = [
        # HIV Integrase leads (from HIV whitepaper)
        {"id":"naph_metaCF3","target":"HIV_INTEGRASE",
         "smiles":"O=C(NCC(O)CNC(=O)C1COC2OCCC12)c1cccc2ccccc12",
         "dock_affinity":-10.65,"notes":"Gnina CNN=7.226, Best Vina HIV Integrase naph+bisTHF"},
        {"id":"isoq_35diF","target":"HIV_INTEGRASE",
         "smiles":"O=C(NCC(O)Cc1cc(F)cc(F)c1)c1cccc2cccnc12",
         "dock_affinity":-9.82,"notes":"Gnina CNN=7.561, Best CNN HIV Integrase isoq+35diF"},
        {"id":"HYB-005","target":"HIV_INTEGRASE",
         "smiles":"Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1",
         "dock_affinity":-8.43,"notes":"Gnina CNN=7.637, Best overall CNN, diketo warhead"},
        {"id":"naph_metaF","target":"HIV_INTEGRASE",
         "smiles":"O=C(NCC(O)Cc1cccc(F)c1)c1cccc2ccccc12",
         "dock_affinity":-10.35,"notes":"Gnina CNN=7.093, naph+metaF"},
        {"id":"HIV-022","target":"HIV_INTEGRASE",
         "smiles":"Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1",
         "dock_affinity":-7.28,"notes":"De novo evolutionary agent, Lipinski 4/4"},
        {"id":"HIV-020","target":"HIV_INTEGRASE",
         "smiles":"Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1",
         "dock_affinity":-8.25,"notes":"Evolutionary agent lead"},
        {"id":"HYB-001","target":"HIV_INTEGRASE",
         "smiles":"Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2ncccc2c1",
         "dock_affinity":-7.40,"notes":"Gnina CNN=7.120, efficient MW=334"},
    ]

    results = []
    for lead in KNOWN_LEADS:
        smiles = lead['smiles']
        if not validate_smiles(smiles):
            warn(f"Invalid SMILES for {lead['id']}, skipping")
            continue
        results.append({
            'smiles':       smiles,
            'id':           lead['id'],
            'dock_affinity': lead['dock_affinity'],
            'ligand_eff':   0.0,
            'confidence':   75,
            'hERG':         0.0,
            'DILI':         0.0,
            'AMES':         0.0,
            'notes':        lead.get('notes', ''),
            'target_override': lead.get('target', ''),
            'source':       'whitepaper',
        })
    return results

# ══════════════════════════════════════════════════════════════════════
# DATABASE LOADER
# ══════════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS compounds (
    id TEXT PRIMARY KEY, smiles TEXT NOT NULL, inchi_key TEXT,
    campaign_id TEXT, target TEXT, cancer_type TEXT, disease_area TEXT,
    dock_affinity REAL, ligand_eff REAL, mw REAL, logp REAL,
    hbd INTEGER, hba INTEGER, tpsa REAL, rotbonds INTEGER, rings INTEGER,
    hERG REAL, DILI REAL, AMES REAL, sigma_label TEXT, sigma_value REAL,
    is_discovery INTEGER, is_evidence INTEGER, confidence INTEGER,
    is_novel INTEGER, chembl_match TEXT, pubchem_cid INTEGER,
    tanimoto_max REAL, fragment_parent TEXT, grow_generation INTEGER,
    timestamp TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY, target TEXT, cancer_type TEXT,
    n_fragments INTEGER, n_grown INTEGER, n_hits INTEGER, n_discoveries INTEGER,
    best_affinity REAL, best_sigma REAL, null_mean REAL, null_std REAL,
    sigma_5_thresh REAL, sigma_3_thresh REAL, duration_min REAL, timestamp TEXT
);
CREATE INDEX IF NOT EXISTS idx_target ON compounds(target);
CREATE INDEX IF NOT EXISTS idx_affinity ON compounds(dock_affinity);
"""

def load_to_db(compounds: list, db_path: str, dry_run: bool = False) -> int:
    """Load compound list into SQLite library."""
    if dry_run:
        return len(compounds)

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    n_added = 0
    ts = datetime.now().isoformat()

    # Build existing SMILES set for dedup
    existing = set(r[0] for r in
                   conn.execute("SELECT smiles FROM compounds").fetchall())

    for c in compounds:
        smiles = c['smiles']
        if smiles in existing:
            continue

        target = c.get('target_override') or c.get('target', 'UNKNOWN')
        disease_info = DISEASE_MAP.get(target, ('Unknown', 'Unknown'))
        disease_area = disease_info[0]
        cancer_type  = disease_info[1]

        aff  = c.get('dock_affinity', 0) or 0
        null_mean = -3.5  # conservative HIV null
        null_std  = 0.4
        z = (null_mean - aff) / (null_std + 1e-6)

        # Per-target null distribution estimates
        null_params = {
            'EGFR': (-5.49, 0.63), 'HIV': (-3.44, 0.37),
            'HIV_INTEGRASE': (-3.44, 0.37), 'BACE1': (-3.34, 0.32),
            'COVID_MPRO': (-4.33, 0.37), 'THROMBIN': (-3.56, 0.44),
        }
        if target in null_params:
            nm, ns = null_params[target]
            z = (nm - aff) / (ns + 1e-6)

        props = calc_props(smiles)

        comp_id = c.get('id', make_compound_id(smiles))
        # Ensure unique ID
        base_id = comp_id
        suffix  = 0
        while conn.execute("SELECT 1 FROM compounds WHERE id=?",
                           (comp_id,)).fetchone():
            suffix += 1
            comp_id = f"{base_id}_{suffix}"

        row = (
            comp_id, smiles, props.get('inchi_key'),
            f"{target}_{datetime.now().strftime('%Y%m%d')}",
            target, cancer_type, disease_area,
            aff, c.get('ligand_eff', 0),
            props.get('mw'), props.get('logp'),
            props.get('hbd'), props.get('hba'),
            props.get('tpsa'), props.get('rotbonds'), props.get('rings'),
            c.get('hERG', 0), c.get('DILI', 0), c.get('AMES', 0),
            c.get('sigma_label', f"{z:.2f}s"), round(z, 3),
            int(z >= 5.0), int(z >= 3.0),
            c.get('confidence', 0),
            0,  # is_novel - computed separately
            '', 0, 0.0, '', 0,
            ts, c.get('notes', f"source={c.get('source','?')}")
        )

        try:
            conn.execute("""INSERT OR IGNORE INTO compounds VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                row)
            n_added += 1
            existing.add(smiles)
        except Exception as e:
            warn(f"DB insert failed for {comp_id}: {e}")

    conn.commit()
    conn.close()
    return n_added

# ══════════════════════════════════════════════════════════════════════
# MAIN SCANNER
# ══════════════════════════════════════════════════════════════════════

def scan_folder(folder: str, dry_run: bool = False,
                show_formats: bool = False) -> dict:
    """
    Scan folder for all discoverable result files and harvest them.
    """
    folder = Path(folder)
    stats  = defaultdict(int)
    all_compounds = []

    # File patterns to scan
    patterns = {
        'agent_csv':    list(folder.glob("agent_results_*.csv")),
        'gnina_json':   list(folder.glob("gnina_results*.json")) +
                        list(folder.glob("gnina_results*.csv")) +
                        list(folder.glob("*gnina*.json")),
        'cure_json':    list(folder.glob("cure_*.json")) +
                        list(folder.glob("*cure*.json")),
        'hiv_json':     list(folder.glob("hiv_*.json")) +
                        list(folder.glob("*hiv*.json")),
        'quantum_json': list(folder.glob("quantum_*.json")) +
                        list(folder.glob("*qubit*.json")) +
                        list(folder.glob("*quantum*.json")),
        'results_json': list(folder.glob("*results*.json")) +
                        list(folder.glob("*discoveries*.json")) +
                        list(folder.glob("*candidates*.json")) +
                        list(folder.glob("*leads*.json")),
    }

    if show_formats:
        print(f"\n{BLD}Files found by category:{RST}")
        for fmt, files in patterns.items():
            print(f"  {fmt:<15} {len(files):>4} files")
        return stats

    # Load whitepapered known leads first
    wp_compounds = parse_whitepaper_smiles()
    print(f"\n{BLD}Harvesting previous campaigns...{RST}")
    print(f"  Whitepaper leads: {len(wp_compounds)} compounds")

    # Process each category
    seen_paths = set()
    file_count = 0

    for fmt, files in patterns.items():
        for path in files:
            if path in seen_paths: continue
            seen_paths.add(path)

            fname = path.name
            target = infer_target_from_filename(fname)

            if fmt == 'agent_csv':
                compounds = parse_agent_results_csv(str(path))
            elif fmt in ('gnina_json',):
                compounds = parse_gnina_results(str(path))
            else:
                compounds = parse_json_results(str(path))

            # Assign target to all compounds from this file
            for c in compounds:
                if not c.get('target_override'):
                    c['target'] = target

            if compounds:
                all_compounds.extend(compounds)
                stats[fmt] += len(compounds)
                file_count += 1

    # Add whitepaper compounds
    all_compounds.extend(wp_compounds)
    stats['whitepaper'] = len(wp_compounds)

    # Deduplicate by SMILES
    seen_smiles = set()
    deduped = []
    for c in all_compounds:
        s = c.get('smiles', '')
        if s and s not in seen_smiles:
            seen_smiles.add(s)
            deduped.append(c)

    total = len(deduped)
    print(f"\n  Files scanned:     {file_count}")
    print(f"  Raw compounds:     {len(all_compounds)}")
    print(f"  After dedup:       {total}")

    if dry_run:
        print(f"\n  {YLW}DRY RUN — not writing to database{RST}")
        by_target = defaultdict(int)
        for c in deduped:
            by_target[c.get('target','?')] += 1
        print(f"\n  Would add by target:")
        for t, n in sorted(by_target.items(), key=lambda x: -x[1]):
            print(f"    {t:<20} {n:>4}")
        return stats

    # Load into DB
    db_path = str(folder / "fragment_library.db")
    n_added = load_to_db(deduped, db_path)
    stats['added'] = n_added

    # Print summary
    conn = sqlite3.connect(db_path)
    total_db   = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    disc_db    = conn.execute("SELECT COUNT(*) FROM compounds WHERE is_discovery=1").fetchone()[0]
    targets_db = conn.execute("SELECT COUNT(DISTINCT target) FROM compounds").fetchone()[0]
    conn.close()

    print(f"\n{BLD}{GRN}HARVEST COMPLETE{RST}")
    print(f"  New compounds added: {n_added}")
    print(f"  Library total:       {total_db}")
    print(f"  5-sigma discoveries: {disc_db}")
    print(f"  Targets covered:     {targets_db}")

    return stats

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Universal Campaign Harvester")
    parser.add_argument("--folder", default=".",
        help="Project folder to scan (default: current directory)")
    parser.add_argument("--dry-run", action="store_true",
        help="Preview what would be added without writing")
    parser.add_argument("--show-formats", action="store_true",
        help="Show file format breakdown without parsing")
    args = parser.parse_args()

    print(f"\n{BLD}{CYN}PhysicsChem Universal Campaign Harvester{RST}")
    print(f"{CYN}Scanning all previous discovery campaigns...{RST}")
    print("=" * 60)

    scan_folder(args.folder, args.dry_run, args.show_formats)

if __name__ == "__main__":
    main()
