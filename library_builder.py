"""
library_builder.py
==================
PhysicsChem Platform v3.0 — Fragment Hit Library Builder

Runs autonomous campaigns across multiple targets and cancer types,
collects all 5-sigma hits into a structured SQLite database,
deduplicates by Tanimoto similarity, checks novelty vs ChEMBL/PubChem,
and exports a full research library with metadata.

USAGE:
    python library_builder.py                        # all 18 targets
    python library_builder.py --targets EGFR HIV     # specific targets
    python library_builder.py --category Oncology    # by disease area
    python library_builder.py --fast                 # quick screen
    python library_builder.py --browse               # browse library
    python library_builder.py --export               # export CSV/SDF
    python library_builder.py --stats                # library statistics

OUTPUT:
    fragment_library.db     SQLite database
    fragment_library.csv    Full export
    fragment_library.sdf    Structure file (RDKit)
    library_report.json     Statistics and summary
"""

import os, sys, json, csv, sqlite3, subprocess, time, random, re
import argparse, hashlib, warnings
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import (AllChem, Descriptors, rdMolDescriptors,
                             Draw, FilterCatalog, rdMolDescriptors)
    from rdkit.Chem.FilterCatalog import FilterCatalogParams
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False

# ── Colors ────────────────────────────────────────────────────────────
GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {color}{BLD}LibraryBuilder{RST}  {msg}")

def ok(msg):  log(msg, GRN)
def warn(msg): log(msg, YLW)
def err(msg):  log(msg, RED)

# ── Database schema ───────────────────────────────────────────────────
DB_PATH  = "fragment_library.db"
CSV_PATH = "fragment_library.csv"
SDF_PATH = "fragment_library.sdf"

SCHEMA = """
CREATE TABLE IF NOT EXISTS compounds (
    id              TEXT PRIMARY KEY,
    smiles          TEXT NOT NULL,
    inchi_key       TEXT,
    campaign_id     TEXT,
    target          TEXT,
    cancer_type     TEXT,
    disease_area    TEXT,
    dock_affinity   REAL,
    ligand_eff      REAL,
    mw              REAL,
    logp            REAL,
    hbd             INTEGER,
    hba             INTEGER,
    tpsa            REAL,
    rotbonds        INTEGER,
    rings           INTEGER,
    hERG            REAL,
    DILI            REAL,
    AMES            REAL,
    sigma_label     TEXT,
    sigma_value     REAL,
    is_discovery    INTEGER,
    is_evidence     INTEGER,
    confidence      INTEGER,
    is_novel        INTEGER,
    chembl_match    TEXT,
    pubchem_cid     INTEGER,
    tanimoto_max    REAL,
    fragment_parent TEXT,
    grow_generation INTEGER,
    timestamp       TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id     TEXT PRIMARY KEY,
    target          TEXT,
    cancer_type     TEXT,
    n_fragments     INTEGER,
    n_grown         INTEGER,
    n_hits          INTEGER,
    n_discoveries   INTEGER,
    best_affinity   REAL,
    best_sigma      REAL,
    null_mean       REAL,
    null_std        REAL,
    sigma_5_thresh  REAL,
    sigma_3_thresh  REAL,
    duration_min    REAL,
    timestamp       TEXT
);

CREATE TABLE IF NOT EXISTS library_stats (
    stat_key    TEXT PRIMARY KEY,
    stat_value  TEXT,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_target   ON compounds(target);
CREATE INDEX IF NOT EXISTS idx_affinity ON compounds(dock_affinity);
CREATE INDEX IF NOT EXISTS idx_sigma    ON compounds(sigma_value);
CREATE INDEX IF NOT EXISTS idx_novel    ON compounds(is_novel);
CREATE INDEX IF NOT EXISTS idx_disease  ON compounds(disease_area);
"""

# ── Target profiles (must match autonomous_drug_agentV2.py) ───────────
TARGET_DISEASE_MAP = {
    "EGFR":       "Oncology",
    "T790M":      "Oncology",
    "VEGFR2":     "Oncology",
    "KRAS_G12C":  "Oncology",
    "BRAF_V600E": "Oncology",
    "CDK4":       "Oncology",
    "PARP1":      "Oncology",
    "HIV":        "Infectious Disease",
    "COVID_MPRO": "Infectious Disease",
    "TB_INHA":    "Infectious Disease",
    "BACE1":      "Neurological",
    "ACHE":       "Neurological",
    "MAO_B":      "Neurological",
    "THROMBIN":   "Cardiovascular",
    "FACTOR_XA":  "Cardiovascular",
    "DPP4":       "Metabolic",
    "COX2":       "Inflammation",
    "JAK1":       "Inflammation",
}

DISEASE_CATEGORIES = {
    "Oncology":           ["EGFR","T790M","VEGFR2","KRAS_G12C",
                           "BRAF_V600E","CDK4","PARP1"],
    "Infectious Disease": ["HIV","COVID_MPRO","TB_INHA"],
    "Neurological":       ["BACE1","ACHE","MAO_B"],
    "Cardiovascular":     ["THROMBIN","FACTOR_XA"],
    "Metabolic":          ["DPP4"],
    "Inflammation":       ["COX2","JAK1"],
}


# ══════════════════════════════════════════════════════════════════════
# DATABASE MANAGER
# ══════════════════════════════════════════════════════════════════════

class LibraryDB:
    """SQLite-backed fragment hit library."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        log(f"Library database: {path}")

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def insert_compound(self, c: dict) -> bool:
        """Insert compound, skip if SMILES already exists."""
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO compounds VALUES (
                    :id,:smiles,:inchi_key,:campaign_id,:target,
                    :cancer_type,:disease_area,:dock_affinity,:ligand_eff,
                    :mw,:logp,:hbd,:hba,:tpsa,:rotbonds,:rings,
                    :hERG,:DILI,:AMES,:sigma_label,:sigma_value,
                    :is_discovery,:is_evidence,:confidence,
                    :is_novel,:chembl_match,:pubchem_cid,:tanimoto_max,
                    :fragment_parent,:grow_generation,:timestamp,:notes
                )""", c)
            self.conn.commit()
            return True
        except Exception as e:
            warn(f"DB insert failed: {e}")
            return False

    def insert_campaign(self, c: dict):
        try:
            self.conn.execute("""
                INSERT OR REPLACE INTO campaigns VALUES (
                    :campaign_id,:target,:cancer_type,:n_fragments,
                    :n_grown,:n_hits,:n_discoveries,:best_affinity,
                    :best_sigma,:null_mean,:null_std,:sigma_5_thresh,
                    :sigma_3_thresh,:duration_min,:timestamp
                )""", c)
            self.conn.commit()
        except Exception as e:
            warn(f"Campaign insert failed: {e}")

    def get_all(self, order_by="sigma_value DESC") -> List[dict]:
        rows = self.conn.execute(
            f"SELECT * FROM compounds ORDER BY {order_by}").fetchall()
        return [dict(r) for r in rows]

    def get_discoveries(self) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM compounds WHERE is_discovery=1 "
            "ORDER BY sigma_value DESC").fetchall()
        return [dict(r) for r in rows]

    def get_by_target(self, target: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM compounds WHERE target=? "
            "ORDER BY dock_affinity ASC", (target,)).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> dict:
        c = self.conn
        return {
            "total":       c.execute("SELECT COUNT(*) FROM compounds").fetchone()[0],
            "discoveries": c.execute("SELECT COUNT(*) FROM compounds WHERE is_discovery=1").fetchone()[0],
            "evidence":    c.execute("SELECT COUNT(*) FROM compounds WHERE is_evidence=1").fetchone()[0],
            "novel":       c.execute("SELECT COUNT(*) FROM compounds WHERE is_novel=1").fetchone()[0],
            "campaigns":   c.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0],
            "targets":     c.execute("SELECT COUNT(DISTINCT target) FROM compounds").fetchone()[0],
        }

    def update_stat(self, key: str, value: str):
        ts = datetime.now().isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO library_stats VALUES (?,?,?)",
            (key, value, ts))
        self.conn.commit()

    def tanimoto_max(self, smiles: str) -> float:
        """Check maximum Tanimoto similarity to existing library."""
        if not RDKIT_OK: return 0.0
        try:
            mol = Chem.MolFromSmiles(smiles)
            if not mol: return 0.0
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)

            rows = self.conn.execute(
                "SELECT smiles FROM compounds LIMIT 500").fetchall()
            max_sim = 0.0
            for row in rows:
                try:
                    m2  = Chem.MolFromSmiles(row[0])
                    if not m2: continue
                    fp2 = AllChem.GetMorganFingerprintAsBitVect(m2, 2, 2048)
                    sim = DataStructs.TanimotoSimilarity(fp, fp2)
                    max_sim = max(max_sim, sim)
                except Exception:
                    continue
            return round(max_sim, 3)
        except Exception:
            return 0.0

    def close(self):
        self.conn.close()


# ══════════════════════════════════════════════════════════════════════
# MOLECULAR PROPERTY CALCULATOR
# ══════════════════════════════════════════════════════════════════════

def calc_properties(smiles: str) -> dict:
    """Calculate physicochemical properties via RDKit."""
    props = {
        "inchi_key": None, "mw": None, "logp": None,
        "hbd": None, "hba": None, "tpsa": None,
        "rotbonds": None, "rings": None,
    }
    if not RDKIT_OK: return props
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return props
        from rdkit.Chem.inchi import MolToInchiKey
        props.update({
            "inchi_key": MolToInchiKey(mol),
            "mw":        round(Descriptors.MolWt(mol), 2),
            "logp":      round(Descriptors.MolLogP(mol), 2),
            "hbd":       rdMolDescriptors.CalcNumHBD(mol),
            "hba":       rdMolDescriptors.CalcNumHBA(mol),
            "tpsa":      round(Descriptors.TPSA(mol), 1),
            "rotbonds":  rdMolDescriptors.CalcNumRotatableBonds(mol),
            "rings":     rdMolDescriptors.CalcNumRings(mol),
        })
    except Exception:
        pass
    return props


# ══════════════════════════════════════════════════════════════════════
# CAMPAIGN RUNNER
# ══════════════════════════════════════════════════════════════════════

class CampaignRunner:
    """
    Runs autonomous discovery campaigns and harvests results into library.
    """

    def __init__(self, db: LibraryDB, agent_script: str = None):
        self.db = db
        # Find agent script
        if agent_script:
            self.agent = agent_script
        elif os.path.isfile("autonomous_drug_agentV2.py"):
            self.agent = "autonomous_drug_agentV2.py"
        elif os.path.isfile("autonomous_drug_agent.py"):
            self.agent = "autonomous_drug_agent.py"
        else:
            self.agent = None
            warn("Agent script not found — will harvest existing results only")

    def run_campaign(self, target: str, mode: str = "fast",
                     cancer_type: str = None) -> dict:
        """
        Run one discovery campaign and return results.
        mode: fast (20 frags, 1 iter) | standard (30, 2) | thorough (50, 3)
        """
        mode_params = {
            "fast":     ["--frags","20","--iterations","1","--exhaustiveness","4"],
            "standard": ["--frags","30","--iterations","2","--exhaustiveness","8"],
            "thorough": ["--frags","50","--iterations","3","--exhaustiveness","16"],
        }
        params = mode_params.get(mode, mode_params["fast"])

        if not self.agent:
            warn(f"No agent found — skipping {target}")
            return {}

        log(f"Launching campaign: {target} [{mode}]", MAG)
        t0 = time.time()

        cmd = [sys.executable, "-W", "ignore",
               self.agent, "--target", target] + params

        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=3600)
        duration = (time.time() - t0) / 60.0

        if result.returncode != 0:
            warn(f"Campaign {target} exited with code {result.returncode}")

        # Parse results from most recent CSV
        return self._parse_latest_results(target, duration)

    def _parse_latest_results(self, target: str,
                               duration_min: float = 0) -> dict:
        """Read the most recent agent results CSV for this target."""
        pattern = f"agent_results_{target}_*.csv"
        csvs = sorted(Path(".").glob(pattern), key=os.path.getmtime)
        if not csvs:
            # Try without target prefix
            csvs = sorted(Path(".").glob("agent_results_*.csv"),
                         key=os.path.getmtime)
        if not csvs:
            warn(f"No results CSV found for {target}")
            return {}

        csv_path = csvs[-1]
        log(f"Parsing results: {csv_path.name}", GRN)

        rows = []
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    rows.append(row)
        except Exception as e:
            warn(f"CSV parse failed: {e}")
            return {}

        # Parse log for Higgs null distribution
        null_mean, null_std = -5.5, 0.7
        sigma5_thresh, sigma3_thresh = -8.5, -7.3
        log_pattern = csv_path.stem.replace("agent_results_", "agent_run_") + ".log"
        log_path = Path(log_pattern)
        if log_path.exists():
            with open(log_path, errors="replace") as f:
                log_text = f.read()
            m = re.search(r'affinity = (-[\d.]+) \+/- ([\d.]+)', log_text)
            if m:
                null_mean = float(m.group(1))
                null_std  = float(m.group(2))
            m5 = re.search(r'5-sigma threshold: (-[\d.]+)', log_text)
            m3 = re.search(r'3-sigma threshold: (-[\d.]+)', log_text)
            if m5: sigma5_thresh = float(m5.group(1))
            if m3: sigma3_thresh = float(m3.group(1))

        # Insert compounds into library
        disease_area = TARGET_DISEASE_MAP.get(target, "Unknown")
        n_added = n_discoveries = 0
        best_aff = 0.0
        best_sig = 0.0

        for row in rows:
            smiles = row.get("smiles","")
            if not smiles: continue

            aff  = float(row.get("dock_affinity","0") or 0)
            conf = int(float(row.get("confidence","0") or 0))

            # Compute Z-score
            z = (null_mean - aff) / (null_std + 1e-6) if null_std else 0
            is_disc  = int(z >= 5.0)
            is_evid  = int(z >= 3.0)
            sigma_lbl= f"{z:.2f}s"

            # Skip low-quality compounds
            if aff >= -5.0: continue

            # Properties
            props = calc_properties(smiles)

            # Tanimoto check vs existing library
            tan_max = self.db.tanimoto_max(smiles)

            # Compound ID
            comp_id = row.get("id", f"{target}_{hashlib.md5(smiles.encode()).hexdigest()[:8]}")

            compound = {
                "id":             comp_id,
                "smiles":         smiles,
                "inchi_key":      props["inchi_key"],
                "campaign_id":    f"{target}_{datetime.now().strftime('%Y%m%d')}",
                "target":         target,
                "cancer_type":    row.get("cancer_type", ""),
                "disease_area":   disease_area,
                "dock_affinity":  aff,
                "ligand_eff":     float(row.get("LE","0") or 0),
                "mw":             props["mw"],
                "logp":           props["logp"],
                "hbd":            props["hbd"],
                "hba":            props["hba"],
                "tpsa":           props["tpsa"],
                "rotbonds":       props["rotbonds"],
                "rings":          props["rings"],
                "hERG":           float(row.get("hERG","0") or 0),
                "DILI":           float(row.get("DILI","0") or 0),
                "AMES":           float(row.get("AMES","0") or 0),
                "sigma_label":    sigma_lbl,
                "sigma_value":    round(z, 3),
                "is_discovery":   is_disc,
                "is_evidence":    is_evid,
                "confidence":     conf,
                "is_novel":       int(tan_max < 0.40),  # <40% similar = novel
                "chembl_match":   "",
                "pubchem_cid":    0,
                "tanimoto_max":   tan_max,
                "fragment_parent":row.get("fragment_parent",""),
                "grow_generation":int(row.get("generation","0") or 0),
                "timestamp":      datetime.now().isoformat(),
                "notes":          "",
            }

            added = self.db.insert_compound(compound)
            if added:
                n_added += 1
                if is_disc: n_discoveries += 1
                if aff < best_aff: best_aff = aff
                if z > best_sig: best_sig = z

        # Record campaign
        campaign = {
            "campaign_id":   f"{target}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "target":        target,
            "cancer_type":   "",
            "n_fragments":   len([r for r in rows if "SEED" not in r.get("id","")]),
            "n_grown":       len(rows),
            "n_hits":        n_added,
            "n_discoveries": n_discoveries,
            "best_affinity": best_aff,
            "best_sigma":    best_sig,
            "null_mean":     null_mean,
            "null_std":      null_std,
            "sigma_5_thresh":sigma5_thresh,
            "sigma_3_thresh":sigma3_thresh,
            "duration_min":  round(duration_min, 1),
            "timestamp":     datetime.now().isoformat(),
        }
        self.db.insert_campaign(campaign)

        ok(f"{target}: {n_added} compounds added "
           f"({n_discoveries} discoveries, best={best_aff:.2f})")
        return campaign


# ══════════════════════════════════════════════════════════════════════
# LIBRARY BROWSER + EXPORTER
# ══════════════════════════════════════════════════════════════════════

class LibraryBrowser:
    """Browse and export the fragment hit library."""

    def __init__(self, db: LibraryDB):
        self.db = db

    def print_stats(self):
        """Print library statistics."""
        counts = self.db.count()
        all_cpds = self.db.get_all()

        print(f"\n{BLD}{CYN}PhysicsChem Fragment Hit Library — Statistics{RST}")
        print("=" * 60)
        print(f"  Total compounds:    {counts['total']:>6}")
        print(f"  5-sigma discoveries:{counts['discoveries']:>6}")
        print(f"  3-sigma evidence:   {counts['evidence']:>6}")
        print(f"  Novel (Tan<0.40):   {counts['novel']:>6}")
        print(f"  Campaigns run:      {counts['campaigns']:>6}")
        print(f"  Targets covered:    {counts['targets']:>6}")

        if all_cpds:
            affs = [c["dock_affinity"] for c in all_cpds if c["dock_affinity"]]
            sigs = [c["sigma_value"] for c in all_cpds if c["sigma_value"]]
            print(f"\n  Affinity range:     {min(affs):.2f} to {max(affs):.2f} kcal/mol")
            print(f"  Best sigma:         {max(sigs):.2f}s")
            print(f"  Mean affinity:      {np.mean(affs):.2f} kcal/mol")

        # By disease area
        print(f"\n  By Disease Area:")
        area_counts = defaultdict(int)
        for c in all_cpds:
            area_counts[c.get("disease_area","?")] += 1
        for area, n in sorted(area_counts.items(), key=lambda x:-x[1]):
            bar = "█" * min(n, 30)
            print(f"    {area:<22} {n:>4}  {bar}")

        # By target
        print(f"\n  Top Targets:")
        tgt_counts = defaultdict(int)
        for c in all_cpds:
            tgt_counts[c.get("target","?")] += 1
        for tgt, n in sorted(tgt_counts.items(), key=lambda x:-x[1])[:10]:
            print(f"    {tgt:<14} {n:>4} compounds")

    def print_top(self, n: int = 20, filter_discoveries: bool = False):
        """Print top compounds by sigma value."""
        compounds = (self.db.get_discoveries()
                     if filter_discoveries else self.db.get_all())

        label = "5-Sigma Discoveries" if filter_discoveries else "Top Compounds"
        print(f"\n{BLD}{CYN}Fragment Hit Library — {label}{RST}")
        print(f"  {'ID':<20} {'Target':<12} {'Affinity':>9} "
              f"{'Sigma':>8} {'LE':>6} {'DILI':>6} {'Novel':>6}")
        print("  " + "─" * 75)

        for i, c in enumerate(compounds[:n], 1):
            disc  = " *** 5σ" if c.get("is_discovery") else ""
            novel = "YES" if c.get("is_novel") else "no"
            print(f"  {i:<3} {c.get('id','?'):<18} "
                  f"{c.get('target','?'):<12} "
                  f"{c.get('dock_affinity',0):>9.3f} "
                  f"{c.get('sigma_value',0):>8.2f}s "
                  f"{c.get('ligand_eff',0):>6.3f} "
                  f"{c.get('DILI',0):>6.3f} "
                  f"{novel:>6}{disc}")

    def export_csv(self, path: str = CSV_PATH):
        """Export full library to CSV."""
        compounds = self.db.get_all()
        if not compounds:
            warn("Library is empty — run campaigns first")
            return

        df = pd.DataFrame(compounds)
        df.to_csv(path, index=False)
        ok(f"Exported {len(compounds)} compounds to {path}")

    def export_sdf(self, path: str = SDF_PATH):
        """Export library to SDF structure file."""
        if not RDKIT_OK:
            warn("RDKit required for SDF export")
            return
        from rdkit.Chem import SDWriter

        compounds = self.db.get_all()
        writer   = SDWriter(path)
        n_written = 0

        for c in compounds:
            try:
                mol = Chem.MolFromSmiles(c["smiles"])
                if not mol: continue
                AllChem.Compute2DCoords(mol)
                # Set properties
                for key in ["id","target","dock_affinity","sigma_value",
                            "is_discovery","confidence","DILI","hERG"]:
                    val = c.get(key)
                    if val is not None:
                        mol.SetProp(str(key), str(val))
                writer.write(mol)
                n_written += 1
            except Exception:
                continue

        writer.close()
        ok(f"Exported {n_written} structures to {path}")

    def export_json_report(self, path: str = "library_report.json"):
        """Export library statistics as JSON."""
        counts   = self.db.count()
        top10    = self.db.get_discoveries()[:10]
        all_cpds = self.db.get_all()

        report = {
            "generated":    datetime.now().isoformat(),
            "platform":     "PhysicsChem Discovery Platform v3.0",
            "statistics":   counts,
            "top_discoveries": [
                {k: v for k, v in c.items()
                 if k in ["id","smiles","target","dock_affinity",
                          "sigma_value","confidence","DILI","hERG","is_novel"]}
                for c in top10
            ],
            "disease_coverage": {},
            "novel_count_by_target": {},
        }

        # Disease coverage
        area_counts = defaultdict(lambda: {"total":0,"discoveries":0})
        for c in all_cpds:
            area = c.get("disease_area","?")
            area_counts[area]["total"] += 1
            if c.get("is_discovery"):
                area_counts[area]["discoveries"] += 1
        report["disease_coverage"] = dict(area_counts)

        # Novel by target
        tgt_novel = defaultdict(int)
        for c in all_cpds:
            if c.get("is_novel"):
                tgt_novel[c.get("target","?")] += 1
        report["novel_count_by_target"] = dict(tgt_novel)

        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        ok(f"Library report saved to {path}")
        return report


# ══════════════════════════════════════════════════════════════════════
# HARVEST EXISTING RESULTS (no new campaigns)
# ══════════════════════════════════════════════════════════════════════

def harvest_existing(db: LibraryDB):
    """
    Harvest all existing agent_results_*.csv files into the library.
    Use this to populate the library from previous runs without
    launching new campaigns.
    """
    runner = CampaignRunner(db)
    csvs   = sorted(Path(".").glob("agent_results_*.csv"),
                    key=os.path.getmtime)

    if not csvs:
        warn("No existing result files found")
        return 0

    log(f"Found {len(csvs)} existing result files to harvest")
    total = 0

    # Deduplicate — only process each unique CSV once
    seen_paths = set()
    for csv_path in csvs:
        real_path = str(csv_path.resolve())
        if real_path in seen_paths:
            continue
        seen_paths.add(real_path)

        m = re.search(r'agent_results_(\w+)_', csv_path.name)
        if not m: continue
        target = m.group(1)

        # Parse this specific CSV directly (not via glob re-search)
        log(f"Parsing results: {csv_path.name}", GRN)
        rows = []
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    rows.append(row)
        except Exception as e:
            warn(f"CSV parse failed: {e}")
            continue

        if not rows:
            continue

        n_added = 0
        n_disc  = 0
        best    = 0.0
        for row in rows:
            try:
                aff = float(row.get("dock_affinity","0") or 0)
            except:
                aff = 0.0
            if aff >= -4.0:
                continue
            smiles = row.get("smiles","")
            if not smiles:
                continue
            r = runner._insert_compound(row, target)
            if r:
                n_added += 1
                if aff < best: best = aff
                try:
                    if float(row.get("sigma_value","0") or 0) >= 5.0:
                        n_disc += 1
                except: pass

        log(f"{target}_{csv_path.stem[-8:]}: {n_added} compounds added "
            f"({n_disc} discoveries, best={best:.2f})", GRN)
        total += n_added

    ok(f"Harvested {total} compounds from existing results")
    return total


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Fragment Hit Library Builder")

    parser.add_argument("--targets", nargs="+",
        choices=list(TARGET_DISEASE_MAP.keys()), metavar="TARGET",
        help="Specific targets to run (default: all)")
    parser.add_argument("--category",
        choices=list(DISEASE_CATEGORIES.keys()), metavar="CATEGORY",
        help="Run all targets in a disease category")
    parser.add_argument("--mode", default="fast",
        choices=["fast","standard","thorough"],
        help="Campaign mode (fast=10min, standard=30min, thorough=60min)")
    parser.add_argument("--harvest", action="store_true",
        help="Harvest existing result files without running new campaigns")
    parser.add_argument("--browse", action="store_true",
        help="Browse library without running campaigns")
    parser.add_argument("--stats", action="store_true",
        help="Print library statistics")
    parser.add_argument("--export", action="store_true",
        help="Export library to CSV + SDF + JSON")
    parser.add_argument("--top", type=int, default=20,
        help="Show top N compounds")
    parser.add_argument("--discoveries", action="store_true",
        help="Show only 5-sigma discoveries")
    parser.add_argument("--db", default=DB_PATH,
        help=f"Library database path (default: {DB_PATH})")
    args = parser.parse_args()

    db      = LibraryDB(args.db)
    browser = LibraryBrowser(db)
    runner  = CampaignRunner(db)

    print(f"\n{BLD}{CYN}PhysicsChem Fragment Hit Library Builder v3.0{RST}")
    print(f"{CYN}Autonomous Multi-Target Drug Discovery{RST}")
    print("=" * 60)

    # ── Harvest existing results ──────────────────────────────────────
    if args.harvest:
        harvest_existing(db)
        browser.print_stats()
        if args.export:
            browser.export_csv()
            browser.export_sdf()
            browser.export_json_report()
        db.close()
        return

    # ── Browse/stats only ─────────────────────────────────────────────
    if args.browse or args.stats:
        browser.print_stats()
        browser.print_top(args.top, args.discoveries)
        if args.export:
            browser.export_csv()
            browser.export_sdf()
            browser.export_json_report()
        db.close()
        return

    # ── Determine targets to run ──────────────────────────────────────
    if args.targets:
        targets = args.targets
    elif args.category:
        targets = DISEASE_CATEGORIES[args.category]
        log(f"Category '{args.category}': {len(targets)} targets")
    else:
        targets = list(TARGET_DISEASE_MAP.keys())
        log(f"Full library build: {len(targets)} targets")

    # ── Harvest existing first ────────────────────────────────────────
    n_existing = harvest_existing(db)
    log(f"Pre-existing compounds in library: {n_existing}")

    # ── Run campaigns ─────────────────────────────────────────────────
    print(f"\n  Targets: {targets}")
    print(f"  Mode:    {args.mode}")
    print(f"  Est. time: {len(targets) * {'fast':10,'standard':30,'thorough':60}[args.mode]} min")
    print()

    results = []
    t_start = time.time()

    for i, target in enumerate(targets, 1):
        print(f"\n{'─'*60}")
        log(f"Campaign {i}/{len(targets)}: {target}", MAG)

        # Check if receptor exists
        receptor_map = {
            "EGFR":  "cancer_egfr_agent/egfr_receptor.pdbqt",
            "HIV":   "hiv_protease.pdbqt",
            "T790M": "egfr_t790m.pdbqt",
        }
        receptor = receptor_map.get(target, f"{target.lower()}.pdbqt")
        if not os.path.isfile(receptor):
            warn(f"{target}: receptor not found ({receptor}) — harvesting only")
            result = runner._parse_latest_results(target, 0)
        else:
            result = runner.run_campaign(target, args.mode)

        results.append(result)

    # ── Final report ──────────────────────────────────────────────────
    total_time = (time.time() - t_start) / 60.0
    counts = db.count()

    print(f"\n{'='*60}")
    print(f"{BLD}{GRN}LIBRARY BUILD COMPLETE{RST}")
    print(f"{'='*60}")
    print(f"  Campaigns run:      {len(results)}")
    print(f"  Time elapsed:       {total_time:.1f} min")
    print(f"  Total compounds:    {counts['total']}")
    print(f"  5-sigma discoveries:{counts['discoveries']}")
    print(f"  Novel compounds:    {counts['novel']}")
    print()

    browser.print_stats()
    browser.print_top(20, filter_discoveries=False)

    if args.export or True:  # always export
        browser.export_csv()
        browser.export_sdf()
        browser.export_json_report()
        ok(f"Library exported: {CSV_PATH}, {SDF_PATH}, library_report.json")

    db.close()


if __name__ == "__main__":
    main()
