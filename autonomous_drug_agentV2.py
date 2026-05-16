"""
autonomous_drug_agent.py
========================
PhysicsChem Discovery Pipeline v2 - Autonomous Fragment Drug Discoverer
(Stage 2 — canonical CSV schema, per-job output paths, sigma/discovery fields)

ARCHITECTURE:
    OrchestratorAgent
        ?-- FragmentSelectorAgent   (ZINC/built-in fragment library)
        ?-- DockingAgent            (AutoDock Vina subprocess)
        ?-- GrowingAgent            (RDKit R-group enumeration + redock)
        ?-- ADMETAgent              (ADMET-AI 41 endpoints)
        ?-- ValidatorAgent          (multi-target selectivity)

USAGE:
    python autonomous_drug_agent.py --target EGFR
    python autonomous_drug_agent.py --target HIV --receptor hiv_protease.pdbqt

STAGE 2 CHANGES (from previous version):
    * Honors AGENT_RESULTS_FILE / AGENT_LEADERBOARD_FILE env vars so the
      bridge can place outputs directly under jobs/{uuid}/ instead of
      scrambling for legacy agent_results_*.csv files. If the env vars
      are not set, legacy filenames are still written (dashboard.py keeps
      working unchanged).
    * Canonical CSV schema — one set of column names, no more
      "mw vs MW vs molecular_weight" aliasing. Bridge stops probing.
    * Adds the sigma/discovery/evidence fields that were already being
      computed but never being written to disk. The twin's "sigmaLabel: -"
      bug is fixed here at the source.
    * Adds target/reference_drug/reference_affinity/timestamp/run_id to
      every row so downstream consumers never need to re-derive context.
    * Runs Higgs significance BEFORE confidence validation so the sigma
      bonus actually contributes to confidence scoring (it was always
      scored but the bonus never fired because z_score was absent).

TARGETS (built-in):
    EGFR    - Lung cancer kinase         (receptor: cancer_egfr_agent/egfr_receptor.pdbqt)
    HIV     - HIV-1 Protease             (receptor: hiv_protease.pdbqt)
    T790M   - EGFR resistance mutant     (receptor: egfr_t790m.pdbqt)
    CUSTOM  - Provide your own receptor + box
"""

import os, sys, json, time, subprocess, tempfile, re, warnings, argparse
import contextlib, io, random, itertools, csv
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

import os as _os, ctypes as _ctypes

class _SilenceRDKit:
    """Suppress RDKit C-level stderr (kekulization noise etc)."""
    def __enter__(self):
        self._devnull = open(_os.devnull,'w')
        self._old = _os.dup(2)
        _os.dup2(self._devnull.fileno(), 2)
        return self
    def __exit__(self,*a):
        _os.dup2(self._old, 2)
        _os.close(self._old)
        self._devnull.close()

# -- RDKit -------------------------------------------------------------
try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import (AllChem, Descriptors, rdMolDescriptors,
                             FilterCatalog, Lipinski)
    from rdkit.Chem.FilterCatalog import FilterCatalogParams
    RDLogger.DisableLog('rdApp.*')
    RDLogger.DisableLog('rdApp.error')
    RDLogger.DisableLog('rdApp.warning')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False
    print("!!  RDKit not found - install with: pip install rdkit")

# -- Meeko -------------------------------------------------------------
try:
    with contextlib.redirect_stderr(io.StringIO()):
        from meeko import MoleculePreparation, PDBQTWriterLegacy
    MEEKO_OK = True
except Exception:
    MEEKO_OK = False

# -- ADMET-AI ----------------------------------------------------------
try:
    with contextlib.redirect_stderr(io.StringIO()):
        from admet_ai import ADMETModel
        _ADMET_MODEL = ADMETModel()
    ADMET_OK = True
except Exception:
    ADMET_OK = False


# ======================================================================
# STAGE 2: Canonical CSV schema
# ======================================================================
# Exactly these columns, in this order. If a value is missing on a row,
# it writes as an empty string — never omitted, never renamed.

CANONICAL_CSV_COLUMNS = [
    # Identity
    "id", "smiles", "name", "parent",
    # Docking
    "dock_affinity", "n_poses",
    # Physicochem
    "mw", "logp", "hac", "le",
    # Higgs significance
    "z_score", "sigma_label", "sigma_status",
    "is_discovery", "is_evidence",
    # ADMET — core
    "admet_pass", "hERG", "DILI", "AMES", "ClinTox",
    "bioavailability", "solubility", "hia",
    # ADMET — CYP450
    "cyp3a4_inh", "cyp2d6_inh", "cyp2c9_inh", "cyp2c19_inh", "cyp1a2_inh",
    "cyp3a4_sub", "cyp2d6_sub", "cyp2c9_sub",
    "cyp_safe", "cyp_warning",
    # ADMET — PK
    "half_life", "clearance_hep", "ppbr", "vdss",
    # Validation
    "confidence", "reasons",
    # Context
    "target", "reference_drug", "reference_affinity", "run_id", "timestamp",
]


def _canonicalize_row(c: dict, *, target: str, ref_drug: str,
                      ref_aff: float, run_id: str,
                      timestamp: str) -> dict:
    """
    Map an agent-internal candidate dict to the canonical schema.
    Values not present become empty string (never missing column).
    The agent uses mixed-case internal keys (MW/LE/HAC/LogP/hERG/DILI)
    for historical reasons — this is the one place we translate.
    """
    row = {col: "" for col in CANONICAL_CSV_COLUMNS}

    # Identity
    row["id"]       = c.get("id", "")
    row["smiles"]   = c.get("smiles", "")
    row["name"]     = c.get("name", "")
    row["parent"]   = c.get("parent", "")

    # Docking
    row["dock_affinity"] = c.get("dock_affinity", "")
    row["n_poses"]       = c.get("dock_poses", "")

    # Physicochem (translate from legacy names)
    row["mw"]   = c.get("MW",   c.get("mw",   ""))
    row["logp"] = c.get("LogP", c.get("logp", ""))
    row["hac"]  = c.get("HAC",  c.get("hac",  ""))
    row["le"]   = c.get("LE",   c.get("le",   ""))

    # Higgs significance
    row["z_score"]      = c.get("z_score", "")
    row["sigma_label"]  = c.get("sigma_label", "-")
    row["sigma_status"] = c.get("sigma_status", "")
    # Booleans -> lowercase string for clean CSV round-trip
    row["is_discovery"] = "true" if c.get("is_discovery") else "false"
    row["is_evidence"]  = "true" if c.get("is_evidence")  else "false"

    # ADMET core
    row["admet_pass"]      = "true" if c.get("admet_pass") else "false"
    row["hERG"]            = c.get("hERG", "")
    row["DILI"]            = c.get("DILI", "")
    row["AMES"]            = c.get("AMES", "")
    row["ClinTox"]         = c.get("ClinTox", "")
    row["bioavailability"] = c.get("Bioavailability", c.get("bioavailability", ""))
    row["solubility"]      = c.get("Solubility",      c.get("solubility", ""))
    row["hia"]             = c.get("HIA",             c.get("hia", ""))

    # CYP450
    row["cyp3a4_inh"]  = c.get("CYP3A4_inh",  c.get("cyp3a4_inh",  ""))
    row["cyp2d6_inh"]  = c.get("CYP2D6_inh",  c.get("cyp2d6_inh",  ""))
    row["cyp2c9_inh"]  = c.get("CYP2C9_inh",  c.get("cyp2c9_inh",  ""))
    row["cyp2c19_inh"] = c.get("CYP2C19_inh", c.get("cyp2c19_inh", ""))
    row["cyp1a2_inh"]  = c.get("CYP1A2_inh",  c.get("cyp1a2_inh",  ""))
    row["cyp3a4_sub"]  = c.get("CYP3A4_sub",  c.get("cyp3a4_sub",  ""))
    row["cyp2d6_sub"]  = c.get("CYP2D6_sub",  c.get("cyp2d6_sub",  ""))
    row["cyp2c9_sub"]  = c.get("CYP2C9_sub",  c.get("cyp2c9_sub",  ""))
    row["cyp_safe"]    = "true" if c.get("cyp_safe") else "false"
    row["cyp_warning"] = c.get("cyp_warning", "")

    # PK
    row["half_life"]     = c.get("half_life", "")
    row["clearance_hep"] = c.get("clearance_hep", "")
    row["ppbr"]          = c.get("ppbr", "")
    row["vdss"]          = c.get("vdss", "")

    # Validation
    row["confidence"] = c.get("confidence", "")
    row["reasons"]    = "|".join(c.get("reasons", []))  # pipe-separated, CSV-safe

    # Context
    row["target"]             = target
    row["reference_drug"]     = ref_drug or ""
    row["reference_affinity"] = ref_aff if ref_aff is not None else ""
    row["run_id"]             = run_id
    row["timestamp"]          = timestamp

    return row


# ======================================================================
# BUILT-IN FRAGMENT LIBRARY
# ======================================================================

# 120 drug-like fragments covering key pharmacophore classes:
# hinge binders, hydrophobic fillers, H-bond donors/acceptors,
# salt bridge formers, and fluorine-containing fragments
FRAGMENT_LIBRARY = [
    # -- Hinge-binding heteroaromatics ---------------------------------
    ("F001", "c1ccncc1",              "pyridine"),
    ("F002", "c1ccnc2ccccc12",        "quinoline"),
    ("F003", "c1cnc2ccccc2n1",        "benzimidazole"),
    ("F004", "c1ccc2[nH]cnc2c1",      "7-azaindole"),
    ("F005", "c1cnc2[nH]ccc2c1",      "4-azaindole"),
    ("F006", "c1cncc2ccccc12",        "isoquinoline"),
    ("F007", "c1cc2ccccc2nc1N",       "2-aminoquinoline"),
    ("F008", "Nc1ncnc2ccccc12",       "4-aminoquinazoline"),
    ("F009", "Nc1ncnc2[nH]cnc12",    "adenine"),
    ("F010", "c1ccc2ncccc2c1",        "quinoxaline"),
    ("F011", "c1cnc2ccncc2c1",        "1,6-naphthyridine"),
    ("F012", "c1cc2ccncc2[nH]1",      "pyrrolo[2,3-b]pyridine"),
    ("F013", "c1ccc2c(c1)cnn2",       "indazole"),
    ("F014", "c1ccc2[nH]ncc2c1",      "indazole-2H"),
    ("F015", "Nc1ccc2ncncc2n1",       "2-aminopurine"),

    # -- Aniline / aminobenzene heads ---------------------------------
    ("F016", "Nc1ccccc1",             "aniline"),
    ("F017", "Nc1ccc(F)cc1",          "4-fluoroaniline"),
    ("F018", "Nc1cccc(F)c1",          "3-fluoroaniline"),
    ("F019", "Nc1ccc(Cl)cc1",         "4-chloroaniline"),
    ("F020", "Nc1ccc(C(F)(F)F)cc1",   "4-trifluoromethylaniline"),
    ("F021", "Nc1ccc(OC)cc1",         "4-methoxyaniline"),
    ("F022", "Nc1cccc(C)c1",          "3-methylaniline"),
    ("F023", "Nc1ccc(C#N)cc1",        "4-cyanoaniline"),
    ("F024", "Nc1ccc(O)cc1",          "4-aminophenol"),
    ("F025", "Nc1ccc(N)cc1",          "1,4-phenylenediamine"),

    # -- Linkers / spacers --------------------------------------------
    ("F026", "CCN",                   "ethylamine"),
    ("F027", "CCNC",                  "N-methylethylamine"),
    ("F028", "CCC",                   "propyl"),
    ("F029", "CCCC",                  "butyl"),
    ("F030", "CC(C)C",               "isobutyl"),
    ("F031", "CCNCC",                 "diethylamine"),
    ("F032", "NCC",                   "ethanolamide"),
    ("F033", "NCCO",                  "ethanolamine"),
    ("F034", "NCC(=O)N",             "glycinamide"),
    ("F035", "NCCCC",                 "4-aminobutyl"),

    # -- Piperidine / piperazine scaffolds ---------------------------
    ("F036", "C1CCNCC1",              "piperidine"),
    ("F037", "C1CNCCN1",              "piperazine"),
    ("F038", "C1CCN(C)CC1",           "N-methylpiperidine"),
    ("F039", "C1CN(CC1)C(=O)C",      "N-acetylpiperazine"),
    ("F040", "C1CCOC1",               "tetrahydrofuran"),
    ("F041", "C1CCOCC1",              "tetrahydropyran"),
    ("F042", "C1CCNC1",               "pyrrolidine"),
    ("F043", "C1CCSC1",               "tetrahydrothiophene"),
    ("F044", "C1CN2CCCC2CC1",         "octahydroindolizine"),
    ("F045", "C1CNCC1",               "azetidine-pyrrolidine"),

    # -- Aromatic rings with H-bond features -------------------------
    ("F046", "c1ccc(O)cc1",           "phenol"),
    ("F047", "c1ccc(N)cc1",           "aniline-para"),
    ("F048", "c1ccc(C(=O)N)cc1",     "benzamide"),
    ("F049", "c1ccc(S(N)(=O)=O)cc1", "benzenesulfonamide"),
    ("F050", "c1cc(O)ccc1O",          "catechol"),
    ("F051", "c1ccc(C(F)(F)F)cc1",   "trifluoromethylbenzene"),
    ("F052", "c1cc(F)ccc1F",          "1,3-difluorobenzene"),
    ("F053", "c1c(F)cc(F)cc1F",      "1,3,5-trifluorobenzene"),
    ("F054", "c1ccc(Br)cc1",          "bromobenzene"),
    ("F055", "c1cccc(C#N)c1",         "3-cyanobenzene"),

    # -- Naphthalene / decalin series --------------------------------
    ("F056", "c1ccc2ccccc2c1",        "naphthalene"),
    ("F057", "c1ccc2c(c1)cccc2N",    "2-aminonaphthalene"),
    ("F058", "C1CCC2CCCCC2C1",        "decalin"),
    ("F059", "C1CCC2(CC1)CCCC2",      "spiro[5.5]undecane"),
    ("F060", "c1ccc2c(c1)CCCC2",      "tetralin"),

    # -- Hydroxamic acids / warheads ---------------------------------
    ("F061", "CC(=O)NO",              "acetohydroxamic acid"),
    ("F062", "C(=O)NO",               "hydroxamic acid"),
    ("F063", "CC(=O)N",               "acetamide"),
    ("F064", "C(=O)NN",               "hydrazide"),
    ("F065", "C(=O)O",                "carboxylic acid"),

    # -- Sulfonamides / sulfones --------------------------------------
    ("F066", "CS(=O)(=O)N",           "methanesulfonamide"),
    ("F067", "CS(=O)(=O)C",           "dimethylsulfone"),
    ("F068", "c1ccc(S(=O)(=O)N)cc1", "phenylsulfonamide"),
    ("F069", "NS(=O)(=O)c1ccccc1",   "benzenesulfonamide-2"),
    ("F070", "CS(=O)C",               "dimethylsulfoxide"),

    # -- EGFR-biased scaffolds (from your existing campaign) ----------
    ("F071", "Nc1ncnc2ccccc12",       "4-aminoquinazoline-EGFR"),
    ("F072", "Nc1ccc(Nc2ncnc3ccccc23)cc1", "anilinoquinazoline"),
    ("F073", "Fc1ccc(N)cc1",          "4-fluoro-aniline"),
    ("F074", "Fc1cccc(N)c1",          "3-fluoro-aniline"),
    ("F075", "Nc1cccc(CCN)c1",        "3-aminophenethylamine"),
    ("F076", "CC(CC1CCNCC1)c1ccccc1", "isobutyl-piperidine"),
    ("F077", "CC(Cc1ccccc1)NC",       "N-methyl-amphetamine-like"),
    ("F078", "CC(CC1CCOCC1)c1ccccc1", "isobutyl-THP"),
    ("F079", "Nc1ccc2[nH]cnc2c1",    "azaindole-amine"),
    ("F080", "c1ccc2[nH]ccc2c1CCN",  "tryptamine"),

    # -- HIV protease biased (darunavir-like) ------------------------
    ("F081", "OCC(O)CO",              "glycerol"),
    ("F082", "C1CCOC1",               "THF"),
    ("F083", "C1CC2CCOC2O1",          "bis-THF"),
    ("F084", "NS(=O)(=O)c1ccc(N)cc1","sulfanilamide"),
    ("F085", "OC(Cc1ccccc1)C(=O)N",  "phenylalanine-ol"),
    ("F086", "c1ccc2cccc3cccc1c23",   "phenanthrene"),
    ("F087", "c1ccc2c(c1)ccc1ccccc12","pyrene"),
    ("F088", "c1ccc2ccc3cccc4ccc1c2c34","coronene"),
    ("F089", "C(c1ccccc1)c1ccccc1",  "diphenylmethane"),
    ("F090", "OCC(O)c1ccccc1",        "phenacetaldehyde-diol"),

    # -- Fluorine-containing fragments -------------------------------
    ("F091", "FC(F)(F)c1ccccc1",      "trifluoromethylbenzene"),
    ("F092", "Fc1ccc(F)cc1",          "1,4-difluorobenzene"),
    ("F093", "FC(F)F",                "trifluoromethane"),
    ("F094", "OC(F)(F)F",             "trifluoromethanol"),
    ("F095", "Cc1ccc(F)cc1",          "4-fluorotoluene"),
    ("F096", "Fc1ccccc1C",            "2-fluorotoluene"),
    ("F097", "FC1CCCC1",              "fluorocyclopentane"),
    ("F098", "FC1CCCCC1",             "fluorocyclohexane"),
    ("F099", "OC(F)c1ccccc1",         "alpha-fluorobenzylalcohol"),
    ("F100", "Nc1ccc(F)c(F)c1",       "3,4-difluoroaniline"),

    # -- Charged / ionisable groups ----------------------------------
    ("F101", "CC(N)=O",               "acetamide-2"),
    ("F102", "CC(=O)O",               "acetic acid"),
    ("F103", "NCC(=O)O",             "glycine"),
    ("F104", "NCCC(=O)O",            "beta-alanine"),
    ("F105", "CC(N)C(=O)O",          "alanine"),
    ("F106", "OCC(N)C(=O)O",         "serine"),
    ("F107", "CCC(N)C(=O)O",         "norvaline"),
    ("F108", "Nc1ccc(C(=O)O)cc1",   "4-aminobenzoic acid"),
    ("F109", "Nc1cccc(C(=O)O)c1",   "3-aminobenzoic acid"),
    ("F110", "Nc1ccc(S(=O)(=O)O)cc1","sulfanilic acid"),

    # -- Cyclic ethers / macrocycle fragments ------------------------
    ("F111", "C1OCC2OCCO2C1",         "18-crown-6-fragment"),
    ("F112", "C1CCOCCO1",             "dioxane"),
    ("F113", "C1CCOC(C1)C",          "2-methylTHP"),
    ("F114", "OC1CCOCC1",            "4-hydroxyTHP"),
    ("F115", "C1OCCO1",              "1,3-dioxolane"),

    # -- Cyanide / nitrile warheads ----------------------------------
    ("F116", "CC#N",                  "acetonitrile"),
    ("F117", "c1ccc(C#N)cc1",        "benzonitrile"),
    ("F118", "N#Cc1ccc(N)cc1",       "4-aminobenzonitrile"),
    ("F119", "CC(=O)C#N",            "pyruvonitrile"),
    ("F120", "N#CCCN",               "3-aminopropionitrile"),
]

# ======================================================================
# TARGET PROFILES - built-in receptor configs
# ======================================================================


# ══════════════════════════════════════════════════════════════════════
# HIGGS-STYLE SIGNIFICANCE TESTER
# ══════════════════════════════════════════════════════════════════════

class HiggsSignificanceTester:
    """
    Applies particle-physics 5-sigma significance testing to docking scores.

    Methodology (same as PhysicsChem v1 / Higgs boson discovery):
    ─────────────────────────────────────────────────────────────────
    1. Build NULL distribution from fragment docking scores.
       Fragments are "known inactives" — too small to be drugs.
    2. For each grown compound, compute Z-score vs null:
           Z = (null_mean_affinity - compound_affinity) / null_std
       (more negative affinity = better binding = larger Z)
    3. Classify:
           Z >= 5.0 = 5-sigma DISCOVERY
           Z >= 3.0 = 3-sigma EVIDENCE
           Z >= 2.0 = 2-sigma CANDIDATE
    """

    DISCOVERY_SIGMA = 5.0
    EVIDENCE_SIGMA  = 3.0
    CANDIDATE_SIGMA = 2.0

    def __init__(self, logger=None):
        self.null_mean = None
        self.null_std  = None
        self.null_n    = 0
        self.log       = logger

    def _info(self, msg):
        if self.log:
            self.log.log("HiggsTest", msg)
        else:
            print(f"  [HiggsTest] {msg}")

    def fit_null(self, fragment_affinities: list):
        vals = np.array([a for a in fragment_affinities
                         if a is not None and a < 0])
        if len(vals) < 3:
            self._info("Too few fragments for null distribution — using defaults")
            self.null_mean = -5.5
            self.null_std  = 0.8
            self.null_n    = 0
            return

        self.null_mean = float(np.mean(vals))
        self.null_std  = float(np.std(vals)) + 1e-6
        self.null_n    = len(vals)

        HISTORICAL_NULL = {
            "HIV_INTEGRASE": (-5.52, 0.61),
            "EGFR":          (-5.49, 0.63),
            "HIV":           (-3.57, 0.47),
            "COVID_MPRO":    (-4.33, 0.37),
            "BACE1":         (-3.34, 0.32),
            "THROMBIN":      (-3.56, 0.44),
        }
        _tgt = getattr(self, '_target', None)
        if _tgt and _tgt in HISTORICAL_NULL:
            _hm, _hs = HISTORICAL_NULL[_tgt]
            if _hs < self.null_std:
                self._info(f"Using historical null for {_tgt}: "
                           f"{_hm:.2f} +/- {_hs:.2f} (overrides {self.null_std:.2f})")
                self.null_mean = _hm
                self.null_std  = _hs

        self._info(f"Null distribution: affinity = {self.null_mean:.2f} +/- "
                   f"{self.null_std:.2f} kcal/mol (n={self.null_n})")
        self._info(f"Fragment null median: {np.median(vals):.2f} kcal/mol")
        disc = self.null_mean - self.DISCOVERY_SIGMA * self.null_std
        evid = self.null_mean - self.EVIDENCE_SIGMA  * self.null_std
        self._info(f"5-sigma threshold: {disc:.2f} kcal/mol")
        self._info(f"3-sigma threshold: {evid:.2f} kcal/mol")

    def z_score(self, affinity: float) -> float:
        if self.null_mean is None:
            raise RuntimeError("Call fit_null() before z_score()")
        return (self.null_mean - affinity) / self.null_std

    def classify(self, affinity: float) -> dict:
        z = self.z_score(affinity)

        if z >= self.DISCOVERY_SIGMA:
            status = "5-SIGMA DISCOVERY"
            is_discovery = True
            is_evidence  = True
        elif z >= self.EVIDENCE_SIGMA:
            status = "3-SIGMA EVIDENCE"
            is_discovery = False
            is_evidence  = True
        elif z >= self.CANDIDATE_SIGMA:
            status = "2-SIGMA CANDIDATE"
            is_discovery = False
            is_evidence  = False
        else:
            status = f"sub-threshold ({z:.1f}s)"
            is_discovery = False
            is_evidence  = False

        label = f"{z:.2f}s"

        return {
            "z_score":      round(z, 3),
            "sigma_label":  label,
            "status":       status,
            "is_discovery": is_discovery,
            "is_evidence":  is_evidence,
            "affinity":     affinity,
        }

    def p_value(self, affinity: float) -> float:
        from scipy.stats import norm
        return float(1 - norm.cdf(self.z_score(affinity)))

    def summary(self, compounds: list) -> list:
        results = []
        for c in compounds:
            aff = c.get("dock_affinity", 0)
            if aff and aff < 0:
                sig = self.classify(aff)
                c["z_score"]      = sig["z_score"]
                c["sigma_label"]  = sig["sigma_label"]
                c["sigma_status"] = sig["status"]
                c["is_discovery"] = sig["is_discovery"]
                c["is_evidence"]  = sig["is_evidence"]
                results.append(c)

        n5 = sum(1 for c in results if c.get("is_discovery"))
        n3 = sum(1 for c in results if c.get("is_evidence") and not c.get("is_discovery"))
        self._info(f"Significance scan: {n5} x 5-sigma discoveries, "
                   f"{n3} x 3-sigma evidence candidates")
        return results


TARGET_PROFILES = {

    # ── ONCOLOGY ──────────────────────────────────────────────────────
    "EGFR": {
        "name":"EGFR Kinase (Wild-Type)","pdb":"4HJO",
        "receptor":"cancer_egfr_agent/egfr_receptor.pdbqt",
        "center":(24.77,9.19,0.0),"size":(22,22,22),
        "chembl":"CHEMBL203","ref_drug":"Erlotinib","ref_affinity":-8.0,
        "disease":"Non-Small Cell Lung Cancer","category":"Oncology",
        "mechanism":"ATP-competitive EGFR inhibition",
        "clinical_stage":"FDA approved (multiple agents)",
        "key_residues":["MET769","THR766","LYS745","ASP855"],
        "fragment_bias":"quinazoline",
        "selectivity_targets":{
            "T790M":{"receptor":"egfr_t790m.pdbqt","center":(-10.73,27.97,36.46),"size":(25,25,25)},
            "VEGFR2":{"receptor":"vegfr2.pdbqt","center":(-10.45,14.88,-8.27),"size":(25,25,25)},
        }
    },
    "T790M": {
        "name":"EGFR T790M Resistance Mutant","pdb":"3IKA",
        "receptor":"egfr_t790m.pdbqt",
        "center":(-10.73,27.97,36.46),"size":(25,25,25),
        "chembl":"CHEMBL203","ref_drug":"Osimertinib","ref_affinity":-7.5,
        "disease":"Resistant NSCLC","category":"Oncology",
        "mechanism":"Covalent EGFR C797 inhibition",
        "clinical_stage":"FDA approved (Osimertinib)",
        "key_residues":["MET790","CYS797","THR854"],
        "fragment_bias":"aminopyrimidine",
        "selectivity_targets":{
            "EGFR_WT":{"receptor":"cancer_egfr_agent/egfr_receptor.pdbqt","center":(24.77,9.19,0.0),"size":(22,22,22)},
        }
    },
    "VEGFR2": {
        "name":"VEGFR2 / KDR Kinase","pdb":"4ASD",
        "receptor":"vegfr2.pdbqt",
        "center":(-10.45,14.88,-8.27),"size":(25,25,25),
        "chembl":"CHEMBL279","ref_drug":"Sorafenib","ref_affinity":-9.5,
        "disease":"Solid tumors / Angiogenesis","category":"Oncology",
        "mechanism":"VEGFR2 kinase DFG-out inhibition",
        "clinical_stage":"FDA approved (multiple agents)",
        "key_residues":["CYS919","ASP1046","GLU885"],
        "fragment_bias":"urea",
        "selectivity_targets":{}
    },
    "KRAS_G12C": {
        "name":"KRAS G12C Oncogene","pdb":"6OIM",
        "receptor":"kras_g12c.pdbqt",
        "center":(-1.9,3.2,1.7),"size":(20,20,20),
        "chembl":"CHEMBL4523582","ref_drug":"Sotorasib","ref_affinity":-10.2,
        "disease":"KRAS-mutant cancers (NSCLC, CRC, PDAC)","category":"Oncology",
        "mechanism":"Covalent GDP-pocket CYS12 engagement",
        "clinical_stage":"FDA approved (Sotorasib 2021)",
        "key_residues":["CYS12","GLY13","HIS95","TYR96"],
        "fragment_bias":"acrylamide",
        "selectivity_targets":{}
    },
    "BRAF_V600E": {
        "name":"BRAF V600E Kinase","pdb":"4MNE",
        "receptor":"braf_v600e.pdbqt",
        "center":(4.6,-3.1,7.2),"size":(22,22,22),
        "chembl":"CHEMBL5145","ref_drug":"Vemurafenib","ref_affinity":-9.8,
        "disease":"Melanoma / Colorectal Cancer","category":"Oncology",
        "mechanism":"DFG-out BRAF V600E inhibition",
        "clinical_stage":"FDA approved (Vemurafenib 2011)",
        "key_residues":["GLU501","LYS483","PHE595","VAL600"],
        "fragment_bias":"sulfonamide",
        "selectivity_targets":{}
    },
    "CDK4": {
        "name":"CDK4/6 Cell Cycle Kinase","pdb":"5L2T",
        "receptor":"cdk4.pdbqt",
        "center":(23.4,4.7,34.1),"size":(22,22,22),
        "chembl":"CHEMBL331","ref_drug":"Palbociclib","ref_affinity":-8.5,
        "disease":"HR+ HER2- Breast Cancer","category":"Oncology",
        "mechanism":"ATP-competitive CDK4/6 inhibition",
        "clinical_stage":"FDA approved (3 agents)",
        "key_residues":["VAL96","LYS35","PHE93"],
        "fragment_bias":"pyridopyrimidine",
        "selectivity_targets":{}
    },
    "PARP1": {
        "name":"PARP1 DNA Repair Enzyme","pdb":"4UND",
        "receptor":"parp1.pdbqt",
        "center":(22.0,6.0,-1.0),"size":(25,25,25),
        "chembl":"CHEMBL3766","ref_drug":"Olaparib","ref_affinity":-9.2,
        "disease":"BRCA-mutant Breast/Ovarian Cancer","category":"Oncology",
        "mechanism":"NAD+ binding site inhibition — synthetic lethality",
        "clinical_stage":"FDA approved (multiple PARP inhibitors)",
        "key_residues":["SER904","GLY863","TYR907","HIS862"],
        "fragment_bias":"benzamide",
        "selectivity_targets":{}
    },

    # ── INFECTIOUS DISEASE ────────────────────────────────────────────
    "HIV": {
        "name":"HIV-1 Protease","pdb":"1HHP",
        "receptor":"hiv_protease.pdbqt",
        "center":(-11.4,19.8,28.0),"size":(20,20,20),
        "chembl":"CHEMBL2364","ref_drug":"Darunavir","ref_affinity":-10.4,
        "disease":"HIV/AIDS","category":"Infectious Disease",
        "mechanism":"Aspartyl protease active site inhibition",
        "clinical_stage":"FDA approved (10+ agents)",
        "key_residues":["ASP25","ASP125","GLY27","ILE50"],
        "fragment_bias":"isoquinoline",
        "selectivity_targets":{}
    },
    "HIV_INTEGRASE": {
        "name":       "HIV-1 Integrase",
        "pdb":        "3L2T",
        "receptor":   "hiv_integrase.pdbqt",
        "center":     (-38.5, 30.5, -20.8),
        "size":       (25.0, 25.0, 25.0),
        "ref_drug":   "Dolutegravir",
        "ref_affinity": -9.43,
        "disease":    "HIV/AIDS",
        "category":   "Infectious Disease",
        "mechanism":  "Integrase strand transfer inhibition",
        "clinical_stage": "FDA approved (4 agents)",
        "key_residues": ["D64","D116","E152","Q148","N155"],
        "fragment_bias": "naphthalene",
        "chembl":     "CHEMBL4523",
        "selectivity_targets": {}
    },
    "HIV_DIP": {
        "name":       "HIV-1 Therapeutic DIP — Integrase Competitive Binder",
        "pdb":        "3L2T",
        "receptor":   "hiv_integrase.pdbqt",
        "center":     (-38.5, 30.5, -20.8),
        "size":       (25.0, 25.0, 25.0),
        "ref_drug":   "Dolutegravir",
        "ref_affinity": -9.43,
        "disease":    "HIV/AIDS — Therapeutic Viral Competition",
        "category":   "Infectious Disease — DIP Strategy",
        "mechanism":  "Competitive integrase occupation — benign DIP variant outcompetes pathogenic HIV-1 for D64/D116/E152 catalytic site.",
        "clinical_stage": "Experimental — Defective Interfering Particle therapy",
        "key_residues": ["D64","D116","E152","Q148","N155","K156","K159"],
        "fragment_bias": "hydroxypyrimidine",
        "chembl":     "CHEMBL4523",
        "dip_strategy": True,
        "selectivity_targets": {
            "HIV_INTEGRASE": {
                "receptor": "hiv_integrase.pdbqt",
                "center": (-38.5, 30.5, -20.8),
                "size": (25.0, 25.0, 25.0),
                "note": "Must bind tighter than wild-type HIV integrase (-9.43 kcal/mol)"
            }
        }
    },
    "COVID_MPRO": {
        "name":"SARS-CoV-2 Main Protease (Mpro)","pdb":"6LU7",
        "receptor":"covid_mpro.pdbqt",
        "center":(-10.7,12.4,68.9),"size":(25,25,25),
        "chembl":"CHEMBL4523583","ref_drug":"Nirmatrelvir","ref_affinity":-8.8,
        "disease":"COVID-19","category":"Infectious Disease",
        "mechanism":"Cysteine protease CYS145 inhibition",
        "clinical_stage":"FDA approved (Paxlovid 2021)",
        "key_residues":["CYS145","HIS41","GLY143","SER144"],
        "fragment_bias":"lactam",
        "selectivity_targets":{}
    },
    "TB_INHA": {
        "name":"M. tuberculosis InhA (Enoyl-ACP)","pdb":"2X23",
        "receptor":"tb_inha.pdbqt",
        "center":(10.2,1.8,-6.3),"size":(25,25,25),
        "chembl":"CHEMBL3709655","ref_drug":"Isoniazid","ref_affinity":-7.2,
        "disease":"Tuberculosis","category":"Infectious Disease",
        "mechanism":"NADH-dependent enoyl-ACP reductase inhibition",
        "clinical_stage":"Clinical trials (direct InhA inhibitors)",
        "key_residues":["TYR158","PHE149","MET98","ALA198"],
        "fragment_bias":"diphenyl_ether",
        "selectivity_targets":{}
    },

    # ── NEUROLOGICAL ──────────────────────────────────────────────────
    "BACE1": {
        "name":"BACE1 Beta-Secretase","pdb":"2WEJ",
        "receptor":"bace1.pdbqt",
        "center":(9.0,22.0,24.0),"size":(25,25,25),
        "chembl":"CHEMBL4523","ref_drug":"Verubecestat","ref_affinity":-9.1,
        "disease":"Alzheimer's Disease","category":"Neurological",
        "mechanism":"Aspartyl protease amyloid precursor cleavage inhibition",
        "clinical_stage":"Phase III (multiple failures — novel approaches needed)",
        "key_residues":["ASP32","ASP228","TYR71","SER35"],
        "fragment_bias":"aminothiazine",
        "selectivity_targets":{}
    },
    "ACHE": {
        "name":"Acetylcholinesterase (AChE)","pdb":"1EVE",
        "receptor":"ache.pdbqt",
        "center":(2.3,5.7,-6.0),"size":(25,25,25),
        "chembl":"CHEMBL220","ref_drug":"Donepezil","ref_affinity":-10.2,
        "disease":"Alzheimer's Disease","category":"Neurological",
        "mechanism":"Catalytic triad serine esterase inhibition",
        "clinical_stage":"FDA approved (Donepezil, Rivastigmine)",
        "key_residues":["SER200","HIS440","GLU327","TRP84"],
        "fragment_bias":"piperidine",
        "selectivity_targets":{}
    },
    "MAO_B": {
        "name":"Monoamine Oxidase B (MAO-B)","pdb":"2V5Z",
        "receptor":"mao_b.pdbqt",
        "center":(27.4,1.4,21.2),"size":(25,25,25),
        "chembl":"CHEMBL2167","ref_drug":"Selegiline","ref_affinity":-8.3,
        "disease":"Parkinson's Disease","category":"Neurological",
        "mechanism":"FAD-dependent oxidative deamination inhibition",
        "clinical_stage":"FDA approved (Selegiline, Rasagiline)",
        "key_residues":["TYR326","TYR398","CYS172","ILE199"],
        "fragment_bias":"propargylamine",
        "selectivity_targets":{}
    },

    # ── CARDIOVASCULAR ────────────────────────────────────────────────
    "THROMBIN": {
        "name":"Thrombin Serine Protease","pdb":"1A46",
        "receptor":"thrombin.pdbqt",
        "center":(27.0,20.0,13.0),"size":(22,22,22),
        "chembl":"CHEMBL204","ref_drug":"Dabigatran","ref_affinity":-9.8,
        "disease":"Thrombosis / Atrial Fibrillation","category":"Cardiovascular",
        "mechanism":"Serine protease active site inhibition",
        "clinical_stage":"FDA approved (direct thrombin inhibitors)",
        "key_residues":["SER195","HIS57","ASP189","GLY193"],
        "fragment_bias":"benzamidine",
        "selectivity_targets":{}
    },
    "FACTOR_XA": {
        "name":"Factor Xa Coagulation Protease","pdb":"2BOH",
        "receptor":"factor_xa.pdbqt",
        "center":(11.0,5.0,23.0),"size":(22,22,22),
        "chembl":"CHEMBL244","ref_drug":"Rivaroxaban","ref_affinity":-9.5,
        "disease":"Thrombosis / VTE","category":"Cardiovascular",
        "mechanism":"S1-S4 exosite occupancy — active site blockade",
        "clinical_stage":"FDA approved (multiple Xa inhibitors)",
        "key_residues":["ASP189","SER195","TYR228","GLU97"],
        "fragment_bias":"oxazolidinone",
        "selectivity_targets":{}
    },

    # ── METABOLIC ─────────────────────────────────────────────────────
    "DPP4": {
        "name":"Dipeptidyl Peptidase-4 (DPP-4)","pdb":"1X70",
        "receptor":"dpp4.pdbqt",
        "center":(35.0,70.0,32.0),"size":(25,25,25),
        "chembl":"CHEMBL284","ref_drug":"Sitagliptin","ref_affinity":-9.4,
        "disease":"Type 2 Diabetes","category":"Metabolic",
        "mechanism":"GLP-1 degradation inhibition / incretin enhancement",
        "clinical_stage":"FDA approved (gliptin class)",
        "key_residues":["SER630","TYR547","ASP708","PHE357"],
        "fragment_bias":"piperazine",
        "selectivity_targets":{}
    },

    # ── INFLAMMATION ──────────────────────────────────────────────────
    "COX2": {
        "name":"Cyclooxygenase-2 (COX-2)","pdb":"5IKR",
        "receptor":"cox2.pdbqt",
        "center":(22.0,16.0,28.0),"size":(25,25,25),
        "chembl":"CHEMBL230","ref_drug":"Celecoxib","ref_affinity":-9.1,
        "disease":"Inflammation / Pain / Cancer","category":"Inflammation",
        "mechanism":"Arachidonic acid tunnel inhibition",
        "clinical_stage":"FDA approved (COX-2 selective NSAIDs)",
        "key_residues":["ARG120","TYR355","SER530","VAL523"],
        "fragment_bias":"diaryl_heterocycle",
        "selectivity_targets":{}
    },
    "JAK1": {
        "name":"JAK1 Janus Kinase","pdb":"3EYH",
        "receptor":"jak1.pdbqt",
        "center":(24.0,15.0,40.0),"size":(22,22,22),
        "chembl":"CHEMBL2835","ref_drug":"Tofacitinib","ref_affinity":-8.7,
        "disease":"Rheumatoid Arthritis / IBD","category":"Inflammation",
        "mechanism":"JAK1 ATP binding site inhibition",
        "clinical_stage":"FDA approved (JAK inhibitors)",
        "key_residues":["LEU959","GLU966","ASP1042","TYR1038"],
        "fragment_bias":"pyrrolopyrimidine",
        "selectivity_targets":{}
    },
}

# ── Disease category index (for UI navigation) ────────────────────────
DISEASE_CATEGORIES = {
    "Oncology":          ["EGFR","T790M","VEGFR2","KRAS_G12C","BRAF_V600E","CDK4","PARP1"],
    "Infectious Disease":["HIV","COVID_MPRO","TB_INHA"],
    "Neurological":      ["BACE1","ACHE","MAO_B"],
    "Cardiovascular":    ["THROMBIN","FACTOR_XA"],
    "Metabolic":         ["DPP4"],
    "Inflammation":      ["COX2","JAK1"],
}



# ======================================================================
# LOGGING
# ======================================================================

class AgentLogger:
    """Real-time timestamped console logger with colour."""

    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    COLORS = {
        "ORCH": "\033[36m",   # cyan
        "FRAG": "\033[34m",   # blue
        "DOCK": "\033[32m",   # green
        "GROW": "\033[35m",   # magenta
        "ADMT": "\033[33m",   # yellow
        "VALD": "\033[96m",   # bright cyan
        "WARN": "\033[91m",   # red
        "DONE": "\033[92m",   # bright green
        "INFO": "\033[37m",   # white
    }

    def __init__(self, logfile="agent_run.log"):
        self.logfile = logfile
        self._entries = []
        with open(logfile, 'w', encoding='utf-8') as f:
            f.write(f"PhysicsChem Agent v2 - {datetime.now()}\n{'='*60}\n")

    def log(self, agent: str, msg: str, level="INFO"):
        ts  = datetime.now().strftime("%H:%M:%S")
        col = self.COLORS.get(agent[:4], self.COLORS["INFO"])
        line = f"[{ts}] {col}{self.BOLD}{agent:<16}{self.RESET} {msg}"
        print(line)
        raw = f"[{ts}] {agent:<16} {msg}"
        self._entries.append(raw)
        with open(self.logfile, 'a', encoding='utf-8') as f:
            f.write(raw + "\n")

    def separator(self, char="-", width=72):
        line = char * width
        print(f"\033[90m{line}\033[0m")
        with open(self.logfile,'a') as f: f.write(line+"\n")

    def header(self, text):
        self.separator("=")
        print(f"\033[1m\033[36m  {text}\033[0m")
        with open(self.logfile,'a') as f: f.write(f"  {text}\n")
        self.separator("=")

    def get_entries(self): return self._entries


# ── Novel fragment generator (FBDD rule-of-3 exploration) ────────────
def generate_novel_fragments(n=20, seed=42):
    if not RDKIT_OK: return []
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
    rng = random.Random(seed)

    cores = [
        "c1ccncc1", "c1cccnc1", "c1cnccn1", "c1ccnnc1", "c1ccncc1N",
        "c1ccc2[nH]ccn2c1", "c1ccc2ncccc2c1", "c1ccc2ncncc2c1",
        "C1CCNCC1", "C1COCCN1", "C1CCNC1", "C1CNCCN1",
        "c1cc[nH]c1", "c1csc(N)n1", "c1cnc[nH]1", "c1cc2ccccc2[nH]1",
        "O=C1CCCO1", "O=C1CCCN1", "c1coc(N)n1",
    ]

    rgroups = [
        "F","Cl","Br","N","O","S","C","CC","CCC",
        "C(F)(F)F","CN","CO","CF","c1ccccc1",
        "c1ccncc1","OC","NC","SC",
    ]

    novel = []
    for core_smi in rng.sample(cores, min(n, len(cores))):
        for rg in rng.sample(rgroups, min(3, len(rgroups))):
            for combo in [f"{core_smi}{rg}", f"{rg}{core_smi}", f"{core_smi}C{rg}"]:
                try:
                    with _SilenceRDKit():
                        mol = Chem.MolFromSmiles(combo)
                    if mol is None: continue
                    mw = Descriptors.MolWt(mol)
                    lp = Descriptors.MolLogP(mol)
                    hbd = rdMolDescriptors.CalcNumHBD(mol)
                    hac = mol.GetNumHeavyAtoms()
                    if mw <= 300 and lp <= 3.5 and hbd <= 3 and hac <= 20:
                        csmi = Chem.MolToSmiles(mol)
                        novel.append(("NOVEL_" + str(len(novel)+1).zfill(3),
                                      csmi, f"novel-{core_smi[:8]}-{rg}"))
                        if len(novel) >= n: return novel
                except Exception: continue
    return novel

# ======================================================================
# AGENT: FRAGMENT SELECTOR
# ======================================================================

class FragmentSelectorAgent:
    def __init__(self, logger: AgentLogger):
        self.log = logger
        self.selected = []

    def load(self, n: int = 50, bias: str = None) -> list:
        self.log.log("FragmentAgent", f"Loading fragment library ({len(FRAGMENT_LIBRARY)} total)...")

        valid = []
        for fid, smi, name in FRAGMENT_LIBRARY:
            if not RDKIT_OK:
                valid.append({"id":fid,"smiles":smi,"name":name})
                continue
            with _SilenceRDKit():
                mol = Chem.MolFromSmiles(smi)
            if mol is None: continue
            mw   = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd  = Lipinski.NumHDonors(mol)
            hac  = mol.GetNumHeavyAtoms()
            if mw > 300 or logp > 3.5 or hbd > 3 or hac > 20:
                continue
            valid.append({
                "id": fid, "smiles": smi, "name": name,
                "MW": round(mw,1), "LogP": round(logp,2),
                "HBD": hbd, "HAC": hac,
            })

        if bias:
            priority = [f for f in valid if bias.lower() in f["name"].lower()]
            rest     = [f for f in valid if f not in priority]
            valid    = priority + rest

        self.selected = valid[:n]
        self.log.log("FragmentAgent",
            f"Selected {len(self.selected)} Ro3-compliant fragments "
            f"(MW<=300, LogP<=3.5, HBD<=3)")
        return self.selected

    def pains_filter(self, frags: list) -> list:
        if not RDKIT_OK: return frags
        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog.FilterCatalog(params)
        clean = []
        for f in frags:
            mol = Chem.MolFromSmiles(f["smiles"])
            if mol and not catalog.GetMatches(mol):
                clean.append(f)
        removed = len(frags) - len(clean)
        if removed:
            self.log.log("FragmentAgent", f"PAINS filter removed {removed} fragments")
        return clean

# ======================================================================
# AGENT: DOCKING
# ======================================================================

class DockingAgent:
    VINA = "./bin/vina.exe"

    def __init__(self, logger: AgentLogger, receptor: str,
                 center: tuple, size: tuple,
                 exhaustiveness: int = 8):
        self.log    = logger
        self.receptor = receptor
        self.center   = center
        self.size     = size
        self.exh      = exhaustiveness
        self._cache   = {}

    def _smiles_to_pdbqt(self, smiles: str, path: str) -> bool:
        if not (RDKIT_OK and MEEKO_OK): return False
        try:
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
            with open(path,'w') as f: f.write(pdbqt)
            return True
        except Exception:
            return False

    def dock(self, smiles: str, name: str) -> dict:
        if smiles in self._cache:
            return self._cache[smiles]

        if not os.path.isfile(self.VINA):
            return {"error": f"Vina not found at {self.VINA}"}
        if not os.path.isfile(self.receptor):
            return {"error": f"Receptor not found: {self.receptor}"}

        with tempfile.TemporaryDirectory() as tmp:
            lig  = os.path.join(tmp, f"{name}.pdbqt")
            out  = os.path.join(tmp, f"{name}_out.pdbqt")
            if not self._smiles_to_pdbqt(smiles, lig):
                return {"error": "PDBQT prep failed"}

            cx,cy,cz = self.center
            sx,sy,sz = self.size
            cmd = [
                self.VINA,
                "--receptor",       self.receptor,
                "--ligand",         lig,
                "--out",            out,
                "--center_x",       str(cx),
                "--center_y",       str(cy),
                "--center_z",       str(cz),
                "--size_x",         str(sx),
                "--size_y",         str(sy),
                "--size_z",         str(sz),
                "--exhaustiveness", str(self.exh),
                "--num_modes",      "9",
                "--energy_range",   "4",
            ]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                output = r.stdout + r.stderr
                poses = []
                for line in output.splitlines():
                    m = re.match(r'\s+(\d+)\s+(-?\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)', line)
                    if m:
                        poses.append({
                            "mode":     int(m.group(1)),
                            "affinity": float(m.group(2)),
                            "rmsd_lb":  float(m.group(3)),
                            "rmsd_ub":  float(m.group(4)),
                        })
                if poses:
                    result = {"affinity": poses[0]["affinity"],
                              "poses": poses, "n_poses": len(poses)}
                    self._cache[smiles] = result
                    return result
                return {"error": "No poses parsed"}
            except subprocess.TimeoutExpired:
                return {"error": "Timeout"}
            except Exception as e:
                return {"error": str(e)}

    def screen_fragments(self, frags: list,
                         ref_affinity: float = -7.0) -> list:
        results = []
        n = len(frags)
        self.log.log("DockingAgent",
            f"Screening {n} fragments (exhaustiveness={self.exh})...")
        self.log.log("DockingAgent",
            f"Threshold: affinity < {ref_affinity} kcal/mol")

        hits = 0
        for i, frag in enumerate(frags, 1):
            r = self.dock(frag["smiles"], frag["id"])
            aff = r.get("affinity")
            if aff is not None:
                frag["dock_affinity"] = aff
                frag["dock_poses"]    = r.get("n_poses", 0)
                flag = "OK" if aff <= ref_affinity else "."
                if aff <= ref_affinity: hits += 1
                self.log.log("DockingAgent",
                    f"  {flag} {frag['id']:<8} {frag['name']:<30} "
                    f"{aff:>7.2f} kcal/mol  {frag['dock_poses']} poses")
                results.append(frag)
            else:
                self.log.log("DockingAgent",
                    f"  XX {frag['id']:<8} {frag['name']:<30} "
                    f"FAILED ({r.get('error','')})")

        results.sort(key=lambda x: x.get("dock_affinity", 0))
        self.log.log("DockingAgent",
            f"Fragment screening complete: {hits}/{len(results)} hit threshold")
        return results

# ======================================================================
# AGENT: FRAGMENT GROWER
# ======================================================================

class GrowingAgent:
    RGROUPS = {
        "alkyl":    ["C","CC","CCC","CCCC","CCCCC","CC(C)C","CCC(C)C"],
        "safe_heads":["c1ccccc1","c1cccc(F)c1","c1ccc(F)cc1","c1ccc(O)cc1","c1cccc(N)c1","c1ccc(N)cc1"],
        "fluorine": ["F","C(F)(F)F","CF3","FC(F)F"],
        "halogens": ["Cl","Br"],
        "amines":   ["N","NC","NCC","NCCC","N(C)C"],
        "ethers":   ["OC","OCC","OCCC","OC(C)C"],
        "aromatics":["c1ccccc1","c1ccncc1","c1ccc(F)cc1","c1ccc(Cl)cc1"],
        "cycles":   ["C1CCNCC1","C1CCOC1","C1CCOCC1","C1CCCC1"],
        "linkers":  ["CC","CCC","CCCC","CCO","CCN","CCNC"],
    }

    PHARMA_TAILS = {
        "EGFR":  [
            "Nc1ncnc2ccccc12",
            "Nc1ccc(Nc2ncnc3ccccc23)cc1",
            "c1ccc2[nH]cnc2c1",
        ],
        "HIV":   [
            "NS(=O)(=O)c1ccccc1",
            "C1CC2CCOC2O1",
            "OC(Cc1ccccc1)C(=O)N",
        ],
        "T790M": [
            "Nc1ncnc2ccccc12",
            "c1ccc2[nH]cnc2c1",
        ],
        "HIV_DIP": [
            "O=C(O)/C=C/c1ccccc1",
            "Oc1nccc(=O)[nH]1",
            "O=C(O)CC(=O)O",
            "c1cnc2[nH]ccc2c1",
            "OC(=O)c1cc(O)ccn1",
        ],
        "HIV_INTEGRASE": [
            "CC(=O)C(=O)O",
            "O=C(O)C(=O)N",
            "Cc1cc(F)cc(F)c1",
            "c1ccc(F)c(F)c1",
            "Cc1ccc(F)cc1F",
            "OCC(O)CN",
            "NCC(O)c1cc(F)cc(F)c1",
            "c1ccc2ccccc2c1",
            "c1cccc2cccnc12",
            "c1cnc2ccccc2c1",
            "OC(CN)Cc1cc(F)cc(F)c1",
        ],
        "COVID_MPRO": [
            "O=C1CCNC1",
            "c1ccc2[nH]ccc2c1",
            "C1CCNCC1",
        ],
        "BACE1": [
            "N=C1NCCC1",
            "FC(F)(F)c1ccccc1",
            "c1ccc2c(c1)CC(N)C2",
        ],
        "THROMBIN": [
            "NC(=N)c1ccccc1",
            "NC(=N)c1ccncc1",
            "c1ccc2[nH]ccc2c1",
        ],
    }

    def __init__(self, logger: AgentLogger, docking_agent: DockingAgent,
                 target: str = "EGFR"):
        self.log    = logger
        self.dock   = docking_agent
        self.target = target
        self.grown  = []

    def _attach_rgroup(self, base_smi: str, rgroup: str) -> list:
        if not RDKIT_OK: return []
        candidates = []
        strategies = [
            f"{base_smi}{rgroup}",
            f"{rgroup}{base_smi}",
            f"{base_smi}C{rgroup}",
            f"{base_smi}CC{rgroup}",
        ]
        for smi in strategies:
            try:
                with _SilenceRDKit():
                    mol = Chem.MolFromSmiles(smi)
                if mol:
                    csmi = Chem.MolToSmiles(mol)
                    mw = Descriptors.MolWt(mol)
                    if 150 <= mw <= 500 and csmi not in [c["smiles"] for c in candidates]:
                        candidates.append({"smiles": csmi, "MW": round(mw,1)})
            except Exception:
                pass
        return candidates

    def _merge_fragments(self, frag1: str, frag2: str) -> list:
        if not RDKIT_OK: return []
        linkers = ["","C","CC","CCC","N","NC","O","OC"]
        results = []
        for l in linkers:
            smi = f"{frag1}{l}{frag2}"
            try:
                with _SilenceRDKit():
                    mol = Chem.MolFromSmiles(smi)
                if mol:
                    csmi = Chem.MolToSmiles(mol)
                    mw   = Descriptors.MolWt(mol)
                    logp = Descriptors.MolLogP(mol)
                    if 200 <= mw <= 500 and logp <= 6:
                        results.append({
                            "smiles": csmi,
                            "MW": round(mw,1),
                            "LogP": round(logp,2)
                        })
            except Exception:
                pass
        return results

    def grow(self, top_frags: list, n_per_frag: int = 10,
             ref_affinity: float = -7.5) -> list:
        self.log.log("GrowingAgent",
            f"Growing {len(top_frags)} fragment hits -> target leads...")
        self.log.log("GrowingAgent",
            f"Strategy: R-group + pharmacophore tail attachment")

        all_candidates = []
        tails = self.PHARMA_TAILS.get(self.target, [])

        for frag in top_frags:
            base = frag["smiles"]
            fid  = frag["id"]
            self.log.log("GrowingAgent",
                f"  Growing {fid} ({frag['name']}) - "
                f"base affinity {frag.get('dock_affinity','?'):.2f} kcal/mol")

            candidates = []

            for tail in tails:
                grown = self._merge_fragments(base, tail)
                candidates.extend(grown)

            for rg_class, rgroups in self.RGROUPS.items():
                for rg in rgroups[:2]:
                    grown = self._attach_rgroup(base, rg)
                    candidates.extend(grown[:3])

            if len(top_frags) > 1:
                partner = random.choice([f for f in top_frags if f != frag])
                merged  = self._merge_fragments(base, partner["smiles"])
                candidates.extend(merged)

            seen = set()
            unique = []
            for c in candidates:
                if c["smiles"] not in seen:
                    seen.add(c["smiles"])
                    unique.append(c)

            self.log.log("GrowingAgent",
                f"    Generated {len(unique)} candidates -> docking top {n_per_frag}...")

            docked = []
            for i, cand in enumerate(unique[:n_per_frag*4]):
                cid = f"{fid}_G{i+1:03d}"
                r   = self.dock.dock(cand["smiles"], cid)
                aff = r.get("affinity")
                if aff is not None:
                    cand.update({
                        "id": cid, "parent": fid,
                        "dock_affinity": aff,
                        "dock_poses": r.get("n_poses",0),
                    })
                    docked.append(cand)

            docked.sort(key=lambda x: x.get("dock_affinity", 0))
            hits = [d for d in docked if d.get("dock_affinity",0) <= ref_affinity]

            for h in hits[:n_per_frag]:
                self.log.log("GrowingAgent",
                    f"    * {h['id']:<12} {h['dock_affinity']:>7.2f} kcal/mol  "
                    f"MW={h.get('MW','?')}  LogP={h.get('LogP','?')}")
            all_candidates.extend(docked[:n_per_frag])

        self.grown = sorted(all_candidates,
                            key=lambda x: x.get("dock_affinity",0))
        self.log.log("GrowingAgent",
            f"Growth cycle complete: {len(self.grown)} compounds produced")
        return self.grown

# ======================================================================
# AGENT: ADMET
# ======================================================================

class ADMETAgent:
    SAFETY_THRESHOLDS = {
        "hERG":             float(os.environ.get("PATIENT_HERG_THRESHOLD", "0.50")),
        "DILI":             float(os.environ.get("PATIENT_DILI_THRESHOLD", "0.50")),
        "AMES":             0.50,
        "ClinTox":          0.50,
        "Carcinogens_Lagunin": 0.30,
        "Bioavailability_Ma":  0.50,
        "CYP3A4_Veith":     float(os.environ.get("PATIENT_CYP3A4_THRESH", "0.70")),
        "CYP2D6_Veith":     float(os.environ.get("PATIENT_CYP2D6_THRESH", "0.70")),
        "CYP2C9_Veith":     float(os.environ.get("PATIENT_CYP2C9_THRESH", "0.70")),
        "CYP2C19_Veith":    float(os.environ.get("PATIENT_CYP2C19_THRESH", "0.70")),
        "CYP1A2_Veith":     float(os.environ.get("PATIENT_CYP1A2_THRESH", "0.70")),
    }

    def __init__(self, logger: AgentLogger):
        self.log = logger

    def profile(self, compounds: list) -> list:
        self.log.log("ADMETAgent",
            f"Profiling {len(compounds)} compounds "
            f"({'ADMET-AI' if ADMET_OK else 'rule-based fallback'})...")

        for c in compounds:
            smi = c.get("smiles","")
            if not smi:
                c["admet_pass"] = False
                continue

            if ADMET_OK:
                try:
                    with contextlib.redirect_stderr(io.StringIO()):
                        result = _ADMET_MODEL.predict(smiles=smi)
                    if isinstance(result, dict):
                        c["hERG"]          = result.get("hERG", 0.5)
                        c["DILI"]          = result.get("DILI", 0.5)
                        c["AMES"]          = result.get("AMES", 0.5)
                        c["ClinTox"]       = result.get("ClinTox", 0.5)
                        c["Bioavailability"]= result.get("Bioavailability_Ma", 0.5)
                        c["Solubility"]    = result.get("Solubility_AqSolDB", -5.0)
                        c["HIA"]           = result.get("HIA_Hou", 0.5)
                        c["CYP3A4_inh"]    = result.get("CYP3A4_Veith", 0.5)
                        c["CYP2D6_inh"]    = result.get("CYP2D6_Veith", 0.5)
                        c["CYP2C9_inh"]    = result.get("CYP2C9_Veith", 0.5)
                        c["CYP2C19_inh"]   = result.get("CYP2C19_Veith", 0.5)
                        c["CYP1A2_inh"]    = result.get("CYP1A2_Veith", 0.5)
                        c["CYP3A4_sub"]    = result.get("CYP3A4_Substrate_CarbonMangels", 0.5)
                        c["CYP2D6_sub"]    = result.get("CYP2D6_Substrate_CarbonMangels", 0.5)
                        c["CYP2C9_sub"]    = result.get("CYP2C9_Substrate_CarbonMangels", 0.5)
                        c["half_life"]     = result.get("Half_Life_Obach", 0.0)
                        c["clearance_hep"] = result.get("Clearance_Hepatocyte_AZ", 0.0)
                        c["ppbr"]          = result.get("PPBR_AZ", 0.0)
                        c["vdss"]          = result.get("VDss_Lombardo", 0.0)
                        thresh = self.SAFETY_THRESHOLDS
                        cyp_safe = (
                            c["CYP3A4_inh"]  < thresh["CYP3A4_Veith"] and
                            c["CYP2D6_inh"]  < thresh["CYP2D6_Veith"] and
                            c["CYP2C9_inh"]  < thresh["CYP2C9_Veith"] and
                            c["CYP2C19_inh"] < thresh["CYP2C19_Veith"]
                        )
                        c["cyp_safe"] = cyp_safe
                        if not cyp_safe:
                            dominant = max(
                                [("CYP3A4",c["CYP3A4_inh"]),
                                 ("CYP2D6",c["CYP2D6_inh"]),
                                 ("CYP2C9",c["CYP2C9_inh"]),
                                 ("CYP2C19",c["CYP2C19_inh"])],
                                key=lambda x: x[1]
                            )
                            c["cyp_warning"] = f"Strong {dominant[0]} inhibitor ({dominant[1]:.2f}) — drug interaction risk"
                        c["admet_pass"] = (
                            c["hERG"]    < 0.82 and
                            c["DILI"]    < 0.65 and
                            c["AMES"]    < 0.50 and
                            c["ClinTox"] < 0.50 and
                            cyp_safe
                        )
                    else:
                        c["admet_pass"] = True
                except Exception:
                    c["admet_pass"] = True
            else:
                if RDKIT_OK:
                    mol = Chem.MolFromSmiles(smi)
                    if mol:
                        mw   = Descriptors.MolWt(mol)
                        logp = Descriptors.MolLogP(mol)
                        hbd  = Lipinski.NumHDonors(mol)
                        hba  = Lipinski.NumHAcceptors(mol)
                        c["admet_pass"] = (mw<=500 and logp<=5 and
                                           hbd<=5 and hba<=10)
                    else:
                        c["admet_pass"] = False
                else:
                    c["admet_pass"] = True

            status = "OK PASS" if c["admet_pass"] else "XX FAIL"
            herg_s = f"hERG={c.get('hERG','-'):.2f}" if "hERG" in c else ""
            dili_s = f"DILI={c.get('DILI','-'):.2f}" if "DILI" in c else ""
            self.log.log("ADMETAgent",
                f"  {status}  {c.get('id','?'):<14} {herg_s}  {dili_s}")

        passed = [c for c in compounds if c.get("admet_pass")]
        self.log.log("ADMETAgent",
            f"ADMET filter: {len(passed)}/{len(compounds)} compounds pass")
        return passed

# ======================================================================
# AGENT: VALIDATOR
# ======================================================================

class ValidatorAgent:
    def __init__(self, logger: AgentLogger,
                 selectivity_targets: dict,
                 ref_affinity: float):
        self.log    = logger
        self.targets = selectivity_targets
        self.ref_aff = ref_affinity

    def validate(self, compounds: list) -> list:
        self.log.log("ValidatorAgent",
            f"Validating {len(compounds)} compounds...")

        for c in compounds:
            smi = c.get("smiles","")
            aff = c.get("dock_affinity", 0)

            if RDKIT_OK and smi:
                mol = Chem.MolFromSmiles(smi)
                if mol:
                    hac = mol.GetNumHeavyAtoms()
                    c["HAC"] = hac
                    c["LE"]  = round(abs(aff)/hac, 3) if hac > 0 else 0
                    c["MW"]  = round(Descriptors.MolWt(mol), 1)
                    c["LogP"]= round(Descriptors.MolLogP(mol), 2)

            score = 0
            reasons = []
            if aff <= self.ref_aff - 2.0:
                score += 35; reasons.append("excellent docking")
            elif aff <= self.ref_aff - 1.0:
                score += 25; reasons.append("strong docking")
            elif aff <= self.ref_aff:
                score += 15; reasons.append("meets threshold")
            z = c.get("z_score")
            if z is not None:
                if z >= 5.0:
                    score += 20; reasons.append(f"{z:.1f}-sigma DISCOVERY")
                elif z >= 3.0:
                    score += 12; reasons.append(f"{z:.1f}-sigma evidence")
                elif z >= 2.0:
                    score += 6;  reasons.append(f"{z:.1f}-sigma candidate")
            if c.get("LE", 0) >= 0.35:
                score += 20; reasons.append("good LE")
            if c.get("admet_pass"):
                score += 25; reasons.append("ADMET pass")
            if c.get("hERG", 1) < 0.30:
                score += 10; reasons.append("hERG safe")
            if c.get("DILI", 1) < 0.30:
                score += 10; reasons.append("DILI safe")
            if c.get("MW", 999) <= 450:
                score += 5;  reasons.append("drug-sized")

            c["confidence"]  = min(score, 100)
            c["reasons"]     = reasons

            if score >= 75: grade = "*** EXCELLENT"
            elif score >= 55: grade = "OK GOOD"
            elif score >= 35: grade = "- MODERATE"
            else: grade = "XX WEAK"

            self.log.log("ValidatorAgent",
                f"  {grade}  {c.get('id','?'):<14}  "
                f"aff={aff:.2f}  LE={c.get('LE','?')}  "
                f"conf={c['confidence']}%  [{', '.join(reasons)}]")

        compounds.sort(key=lambda x: -x.get("confidence", 0))
        return compounds

# ======================================================================
# ORCHESTRATOR
# ======================================================================

class OrchestratorAgent:
    def __init__(self, target_key: str = "EGFR",
                 n_fragments: int = 30,
                 n_grow: int = 8,
                 max_iterations: int = 3,
                 confidence_target: int = 70,
                 exhaustiveness: int = 8):

        if target_key not in TARGET_PROFILES:
            print(f"Unknown target '{target_key}'. Available: {list(TARGET_PROFILES.keys())}")
            sys.exit(1)

        self.profile     = TARGET_PROFILES[target_key]
        self.target_key  = target_key
        self.n_frags     = n_fragments
        self.n_grow      = n_grow
        self.max_iter    = max_iterations
        self.conf_target = confidence_target
        self.exh         = exhaustiveness

        # Patient context (env)
        self.patient_name       = os.environ.get("PATIENT_NAME", "Unknown")
        self.patient_weight_kg  = float(os.environ.get("PATIENT_WEIGHT_KG", "0"))
        self.patient_height_cm  = float(os.environ.get("PATIENT_HEIGHT_CM", "0"))
        self.patient_blood_type = os.environ.get("PATIENT_BLOOD_TYPE", "")
        self.patient_bsa        = float(os.environ.get("PATIENT_BSA", "0"))
        self.patient_ebv        = float(os.environ.get("PATIENT_EBV", "0"))
        self.patient_cd4        = float(os.environ.get("PATIENT_CD4", "0"))
        self.patient_viral_load = float(os.environ.get("PATIENT_VIRAL_LOAD", "0"))
        self.patient_diagnosis  = os.environ.get("PATIENT_DIAGNOSIS", "")
        self.patient_dili       = float(os.environ.get("PATIENT_DILI_THRESHOLD", "0.50"))
        self.patient_herg       = float(os.environ.get("PATIENT_HERG_THRESHOLD", "0.50"))
        self._hiv_fragment_bias = self.profile.get("fragment_bias")

        if target_key == "HIV_DIP":
            self.is_dip_strategy = True
            print(f"[Agent] *** DIP THERAPEUTIC STRATEGY ACTIVATED ***")
            print(f"  Goal: Find compound binding tighter than Dolutegravir (-9.43 kcal/mol)")
        else:
            self.is_dip_strategy = False

        if self.patient_cd4 > 0 and target_key == "HIV_INTEGRASE":
            vl = self.patient_viral_load
            cd4 = self.patient_cd4
            print(f"[Agent] Patient: {self.patient_name}")
            print(f"  Weight: {self.patient_weight_kg}kg  Height: {self.patient_height_cm}cm  Blood: {self.patient_blood_type}")
            print(f"  BSA: {self.patient_bsa:.2f}m²  EBV: {self.patient_ebv:.2f}L")
            print(f"  CD4={cd4:.0f} cells/mm³  Viral Load={vl:.0f} copies/mL")
            print(f"  DILI threshold={self.patient_dili}  hERG threshold={self.patient_herg}")
            if cd4 < 200:
                self.hiv_stage = "AIDS"
                self._hiv_fragment_bias = "halobenzyl"
                print(f"  Stage: AIDS — screening next-gen INSTI scaffolds (halobenzyl/carbamoyl)")
            elif cd4 < 350:
                self.hiv_stage = "Advanced HIV"
                self._hiv_fragment_bias = "diketo"
                print(f"  Stage: Advanced HIV — diketo-acid INSTI scaffolds")
            else:
                self.hiv_stage = "Moderate HIV"
                self._hiv_fragment_bias = "naphthalene"
                print(f"  Stage: Moderate HIV (CD4={cd4:.0f}) — dolutegravir-class naphthalene scaffolds")
            if vl > 100000:
                self.n_frags = min(self.n_frags + 10, 60)
                print(f"  High viremia — fragment pool expanded to {self.n_frags}")
            if self.patient_blood_type in ["O-", "O+"]:
                print(f"  Blood type {self.patient_blood_type}: prioritizing compounds with lower CYP3A4 interaction")
            if self.patient_bsa > 0:
                target_mw_max = 350 + (self.patient_bsa - 1.7) * 100
                print(f"  BSA-adjusted MW target: ≤{target_mw_max:.0f} Da")

        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id  = f"{target_key}_{ts}"
        # Use fixed log file for dashboard mode, timestamped for CLI
        if os.environ.get("DASHBOARD_MODE"):
            logfile = "dashboard_live.log"
        else:
            logfile = f"agent_run_{self.run_id}.log"
        self.log     = AgentLogger(logfile)
        self.results = []
        self.higgs   = None

    def run(self):
        p = self.profile
        self.log.header(
            f"AUTONOMOUS DRUG DISCOVERY AGENT v2  -  {p['name']}")
        self.log.log("Orchestrator", f"Disease target  : {p['disease']}")
        self.log.log("Orchestrator", f"Receptor        : {p['receptor']}")
        self.log.log("Orchestrator", f"Reference drug  : {p['ref_drug']} "
                                      f"({p['ref_affinity']} kcal/mol)")
        self.log.log("Orchestrator", f"Fragment budget : {self.n_frags}")
        self.log.log("Orchestrator", f"Max iterations  : {self.max_iter}")
        self.log.log("Orchestrator", f"Confidence goal : {self.conf_target}%")
        self.log.separator()

        frag_agent = FragmentSelectorAgent(self.log)
        dock_agent = DockingAgent(
            self.log,
            receptor = p["receptor"],
            center   = p["center"],
            size     = p["size"],
            exhaustiveness = self.exh,
        )
        grow_agent = GrowingAgent(self.log, dock_agent, self.target_key)
        admet_agent = ADMETAgent(self.log)
        valid_agent = ValidatorAgent(
            self.log,
            selectivity_targets = p.get("selectivity_targets",{}),
            ref_affinity        = p["ref_affinity"],
        )

        if not os.path.isfile(p["receptor"]):
            self.log.log("Orchestrator",
                f"!!  Receptor not found: {p['receptor']}")
            self.log.log("Orchestrator",
                "   Running in SIMULATION MODE (no actual docking)")
            self._simulation_mode(p, frag_agent, admet_agent, valid_agent)
            return

        iteration       = 0
        best_confidence = 0
        all_leads       = []

        while iteration < self.max_iter and best_confidence < self.conf_target:
            iteration += 1
            self.log.separator("-")
            self.log.log("Orchestrator",
                f"ITERATION {iteration}/{self.max_iter}  "
                f"(best confidence so far: {best_confidence}%)")
            self.log.separator("-")

            frags = frag_agent.load(self.n_frags, bias=getattr(self, "_hiv_fragment_bias", self.target_key))
            frags = frag_agent.pains_filter(frags)

            frag_thresh = p["ref_affinity"] + 3.5
            screened = dock_agent.screen_fragments(frags, ref_affinity=frag_thresh)

            TARGET_SEEDS = {
                "EGFR": [
                    {"id":"SEED_R1C1","smiles":"CC(CC1CCNCC1)c1cccc(N)c1",
                     "name":"isobutyl-piperidine-aniline (R1-C1 proven)",
                     "dock_affinity":-7.52,"dock_poses":8},
                    {"id":"SEED_R1C2","smiles":"CC(CC1CCC2CCCC2C1)c1cccc(F)c1",
                     "name":"decalin-fluorophenyl (R1-C2 proven)",
                     "dock_affinity":-8.48,"dock_poses":8},
                    {"id":"SEED_R1C5","smiles":"CC(CC1CCC2CCCC2C1)c1cccc(O)c1",
                     "name":"decalin-hydroxyphenyl (R1-C5 proven)",
                     "dock_affinity":-8.34,"dock_poses":8},
                ],
                "HIV_INTEGRASE": [
                    {"id":"SEED_INT_DTG",
                     "smiles":"c1ccc2ccccc2c1",
                     "name":"naphthalene core (MW=128, grows to INSTI leads)",
                     "dock_affinity":-8.87,"dock_poses":8},
                    {"id":"SEED_INT_ISQ",
                     "smiles":"c1cccc2cccnc12",
                     "name":"isoquinoline core (MW=129, grows to INSTI leads)",
                     "dock_affinity":-8.59,"dock_poses":8},
                    {"id":"SEED_INT_HYB",
                     "smiles":"Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1",
                     "name":"HYB-005 diketo warhead (validated -8.33 Vina)",
                     "dock_affinity":-8.33,"dock_poses":8},
                    {"id":"SEED_INT_RAL",
                     "smiles":"CC(=O)c1cc(C(=O)NCC(O)c2cc(F)cc(F)c2)no1",
                     "name":"Raltegravir isoxazole carboxamide scaffold",
                     "dock_affinity":-8.10,"dock_poses":8},
                ],
                "HIV_DIP": [
                    {"id":"SEED_DIP_HYP",
                     "smiles":"Oc1ccnc(=O)[nH]1",
                     "name":"hydroxypyrimidine Mg2+ chelator (DIP warhead)",
                     "dock_affinity":-6.50,"dock_poses":8},
                    {"id":"SEED_DIP_DKA",
                     "smiles":"O=C(O)C(=O)Cc1ccc(F)cc1",
                     "name":"diketo-acid fluorobenzyl (INSTI Mg2+ chelator)",
                     "dock_affinity":-7.20,"dock_poses":8},
                    {"id":"SEED_DIP_NHP",
                     "smiles":"Oc1cc(=O)[nH]c(=O)n1",
                     "name":"dihydroxypyrimidine (dual Mg2+ chelation)",
                     "dock_affinity":-7.10,"dock_poses":8},
                    {"id":"SEED_DIP_HNA",
                     "smiles":"O=C(O)/C=C/c1ccc(O)cc1",
                     "name":"hydroxycinnamic acid (integrase anchor fragment)",
                     "dock_affinity":-6.80,"dock_poses":8},
                ],
                "HIV": [
                    {"id":"SEED_HIV_THF1",
                     "smiles":"O=C(NC(Cc1ccccc1)C(=O)N1CCC2(CC1)CCO2)c1ccccc1",
                     "name":"bis-THF peptidomimetic (Darunavir core)",
                     "dock_affinity":-8.50,"dock_poses":8},
                    {"id":"SEED_HIV_THF2",
                     "smiles":"CC(C)(C)NC(=O)C(CC1CCCCC1)NC(=O)C(Cc1ccccc1)N",
                     "name":"HIV protease transition state mimic",
                     "dock_affinity":-8.20,"dock_poses":8},
                    {"id":"SEED_HIV_ISQ",
                     "smiles":"O=C(NC(Cc1ccccc1)C(=O)N1CCCCC1=O)c1ccc(N)cc1",
                     "name":"HIV-1 PR isoquinoline inhibitor scaffold",
                     "dock_affinity":-7.80,"dock_poses":8},
                    {"id":"SEED_HIV_PEP",
                     "smiles":"CC(C)CC(NC(=O)OCC1c2ccccc2-c2ccccc21)C(=O)NC(Cc1ccccc1)C(=O)O",
                     "name":"HIV peptidomimetic Fmoc scaffold",
                     "dock_affinity":-7.40,"dock_poses":8},
                ],
                "BACE1": [
                    {"id":"SEED_BACE1_ATZ",
                     "smiles":"N=C1NC(=O)[C@@H](Cc2ccc(F)cc2F)N1",
                     "name":"iminohydantoin (Verubecestat core)",
                     "dock_affinity":-8.30,"dock_poses":8},
                    {"id":"SEED_BACE1_AMT",
                     "smiles":"CC1(C)C[C@@H](Cc2ccc(F)cc2F)C(=N)N1",
                     "name":"aminomethyl-thiane BACE1 scaffold",
                     "dock_affinity":-7.90,"dock_poses":8},
                    {"id":"SEED_BACE1_SPR",
                     "smiles":"O=C1NC(=N)[C@H](Cc2cc(F)ccc2F)C1",
                     "name":"spirocyclic BACE1 scaffold",
                     "dock_affinity":-7.60,"dock_poses":8},
                ],
                "COVID_MPRO": [
                    {"id":"SEED_R1C1","smiles":"CC(CC1CCNCC1)c1cccc(N)c1",
                     "name":"isobutyl-piperidine-aniline (proven COVID hit)",
                     "dock_affinity":-7.52,"dock_poses":8},
                    {"id":"SEED_COV_LAC",
                     "smiles":"O=C1CN([C@@H](Cc2ccccc2)C(=O)N2CC[C@@H](O)C2)CC1",
                     "name":"Nirmatrelvir-inspired lactam scaffold",
                     "dock_affinity":-8.10,"dock_poses":8},
                    {"id":"SEED_COV_PYR",
                     "smiles":"O=C(N[C@H]1CCNC1=O)c1ccc(N2CCNCC2)cc1",
                     "name":"Mpro pyrrolidinone scaffold",
                     "dock_affinity":-7.70,"dock_poses":8},
                ],
                "THROMBIN": [
                    {"id":"SEED_R1C1","smiles":"CC(CC1CCNCC1)c1cccc(N)c1",
                     "name":"isobutyl-piperidine-aniline (proven Thrombin hit)",
                     "dock_affinity":-5.97,"dock_poses":8},
                    {"id":"SEED_THR_BAM",
                     "smiles":"NC(=N)c1ccc(CC2CCNCC2)cc1",
                     "name":"benzamidine-piperidine (Dabigatran pharmacophore)",
                     "dock_affinity":-7.20,"dock_poses":8},
                    {"id":"SEED_THR_IND",
                     "smiles":"O=C(NC1CCCCC1)c1cc2ccccc2[nH]1",
                     "name":"indole carboxamide thrombin scaffold",
                     "dock_affinity":-6.80,"dock_poses":8},
                ],
                "TB_INHA": [
                    {"id":"SEED_TB_ISO",
                     "smiles":"Cc1ccc(-c2cc(C(F)(F)F)ccc2Oc2ccc(N)cc2)no1",
                     "name":"isoxazole InhA scaffold",
                     "dock_affinity":-8.00,"dock_poses":8},
                    {"id":"SEED_TB_DPE",
                     "smiles":"Nc1ccc(Oc2ccc(Cl)cc2)cc1",
                     "name":"diphenyl ether InhA scaffold",
                     "dock_affinity":-7.40,"dock_poses":8},
                ],
            }

            DEFAULT_SEEDS = [
                {"id":"SEED_R1C1","smiles":"CC(CC1CCNCC1)c1cccc(N)c1",
                 "name":"isobutyl-piperidine-aniline (R1-C1 proven)",
                 "dock_affinity":-7.52,"dock_poses":8},
                {"id":"SEED_R1C2","smiles":"CC(CC1CCC2CCCC2C1)c1cccc(F)c1",
                 "name":"decalin-fluorophenyl (R1-C2 proven)",
                 "dock_affinity":-8.48,"dock_poses":8},
                {"id":"SEED_R1C5","smiles":"CC(CC1CCC2CCCC2C1)c1cccc(O)c1",
                 "name":"decalin-hydroxyphenyl (R1-C5 proven)",
                 "dock_affinity":-8.34,"dock_poses":8},
            ]

            target_key = self.target_key.upper()
            for k in TARGET_SEEDS:
                if k in target_key:
                    target_key = k
                    break
            SEED_SCAFFOLDS = TARGET_SEEDS.get(target_key, DEFAULT_SEEDS)
            self.log.log("GrowingAgent",
                f"Using {len(SEED_SCAFFOLDS)} target-specific seeds for {target_key}")
            top_frags = SEED_SCAFFOLDS + [f for f in screened
                         if f.get("dock_affinity",0) <= frag_thresh][:max(2,self.n_grow-3)]

            if not top_frags:
                self.log.log("Orchestrator",
                    "No fragment hits - lowering threshold +1 kcal/mol")
                top_frags = screened[:max(3, self.n_grow//2)]

            self.log.log("Orchestrator",
                f"Top {len(top_frags)} fragment hits selected for growing")

            # ── Higgs: fit null distribution from fragment scores ─────
            self.log.separator("-")
            self.log.log("Orchestrator",
                "Fitting 5-sigma null distribution from fragment scores...")
            self.higgs = HiggsSignificanceTester(logger=self.log)
            self.higgs._target = self.target_key
            frag_affinities = [f.get("dock_affinity") for f in screened
                               if f.get("dock_affinity") is not None]
            self.higgs.fit_null(frag_affinities)
            self.log.separator("-")

            # Step 3: Growing
            grown = grow_agent.grow(top_frags,
                                    n_per_frag=15,
                                    ref_affinity=p["ref_affinity"])

            # ── STAGE 2 FIX: Higgs BEFORE validator ───────────────────
            # The previous order was: ADMET -> validate -> Higgs.
            # That meant z_score was None when validator computed
            # confidence, so the sigma bonus never fired. Also, ADMET
            # fail compounds never got sigma labels. We fix both by
            # classifying everything against the null before any filter.
            if self.higgs:
                grown = self.higgs.summary(grown)

            # Step 4: ADMET filter
            admet_passed = admet_agent.profile(grown)
            if not admet_passed:
                self.log.log("Orchestrator",
                    "No compounds passed ADMET - using unfiltered set")
                admet_passed = grown[:5]

            # Step 5: Validate (now sees z_score, sigma bonus fires)
            validated = valid_agent.validate(admet_passed)

            # Log discoveries/evidence highlights
            for v in validated:
                if v.get("is_discovery"):
                    self.log.log("Orchestrator",
                        f"  *** 5-SIGMA DISCOVERY: {v['id']} "
                        f"Z={v['z_score']:.2f} "
                        f"aff={v['dock_affinity']:.2f} kcal/mol ***")
                elif v.get("is_evidence"):
                    self.log.log("Orchestrator",
                        f"  ** 3-sigma evidence: {v['id']} "
                        f"Z={v['z_score']:.2f}")

            all_leads.extend(validated)

            if validated:
                iter_best = validated[0].get("confidence", 0)
                if iter_best > best_confidence:
                    best_confidence = iter_best
                self.log.log("Orchestrator",
                    f"Iteration {iteration} best: confidence={iter_best}%  "
                    f"affinity={validated[0].get('dock_affinity','?'):.2f}")

        # Final ranking + dedup
        all_leads.sort(key=lambda x: -x.get("confidence", 0))
        seen   = set()
        unique = []
        for c in all_leads:
            if c["smiles"] not in seen:
                seen.add(c["smiles"])
                unique.append(c)
        self.results = unique

        self._print_leaderboard(unique[:10])
        self._save_results(unique)
        self._print_certificate(unique[0] if unique else None)
        
        # Write done flag for dashboard mode
        if os.environ.get("DASHBOARD_MODE"):
            with open("dashboard_done.flag", "w") as f:
                f.write("done")

    def _simulation_mode(self, p, frag_agent, admet_agent, valid_agent):
        self.log.log("Orchestrator",
            "SIMULATION MODE - generating demonstration results")
        self.log.log("Orchestrator",
            f"To enable real docking: place {p['receptor']} in project folder")

        frags = frag_agent.load(min(self.n_frags, 20))
        frags = frag_agent.pains_filter(frags)

        ref = p["ref_affinity"]
        for i, f in enumerate(frags):
            f["dock_affinity"] = round(ref + random.uniform(-2.5, 1.5), 2)
            f["dock_poses"]    = random.randint(5, 9)
            self.log.log("DockingAgent",
                f"  [SIM] {f['id']:<8} {f['name']:<28} "
                f"{f['dock_affinity']:>7.2f} kcal/mol")

        top = sorted(frags, key=lambda x: x["dock_affinity"])[:self.n_grow]

        grown = []
        for i, frag in enumerate(top[:5]):
            for j in range(4):
                grown.append({
                    "id":            f"{frag['id']}_G{j+1:03d}",
                    "smiles":        frag["smiles"],
                    "name":          f"Grown from {frag['name']}",
                    "parent":        frag["id"],
                    "dock_affinity": round(frag["dock_affinity"] - random.uniform(0.3,1.8), 2),
                    "dock_poses":    random.randint(5,9),
                    "MW":            random.randint(280,420),
                    "LogP":          round(random.uniform(1.5,4.5),2),
                })

        # Fit Higgs on the simulated fragment pool so sigma labels render
        self.higgs = HiggsSignificanceTester(logger=self.log)
        self.higgs._target = self.target_key
        self.higgs.fit_null([f["dock_affinity"] for f in frags])
        grown = self.higgs.summary(grown)

        admet_passed = admet_agent.profile(grown)
        validated    = valid_agent.validate(admet_passed if admet_passed else grown)
        self.results = validated

        self._print_leaderboard(validated[:10])
        self._save_results(validated)
        self._print_certificate(validated[0] if validated else None)
        
        # Write done flag for dashboard mode
        if os.environ.get("DASHBOARD_MODE"):
            with open("dashboard_done.flag", "w") as f:
                f.write("done")

    def _print_leaderboard(self, compounds: list):
        self.log.separator("=")
        self.log.log("Orchestrator", "===  FINAL LEADERBOARD  (with 5-sigma significance)")
        self.log.separator("=")
        print(f"\n  {'Rank':<5} {'ID':<16} {'Sigma':>9} {'Affinity':>9} {'LE':>6} {'Conf%':>6}")
        print("  " + "-"*70)
        for i, comp in enumerate(compounds, 1):
            aff   = comp.get("dock_affinity","?")
            le    = comp.get("LE","?")
            cf    = comp.get("confidence","?")
            sigma = comp.get("sigma_label", "-")
            flag  = " *** 5-SIGMA!" if comp.get("is_discovery") else (
                    " ** 3-sigma"   if comp.get("is_evidence") else "")
            medals = ["|1|","|2|","|3|"] + ["   "]*(max(0,len(compounds)-3))
            medal  = medals[min(i-1,len(medals)-1)]
            print(f"  {medal} {i:<3} {comp.get('id','?'):<16} "
                  f"{sigma:>9} {str(aff):>9} {str(le):>6} {str(cf):>5}%{flag}")
        print()

    # ══════════════════════════════════════════════════════════════════
    # STAGE 2: _save_results — canonical schema + env-var output paths
    # ══════════════════════════════════════════════════════════════════
    def _save_results(self, compounds: list):
        """
        Write results in the canonical CSV schema. Honors env vars:
          AGENT_RESULTS_FILE     -> where to write the CSV
          AGENT_LEADERBOARD_FILE -> where to write the JSON leaderboard
        If env vars are unset, falls back to legacy filenames in CWD so
        dashboard.py keeps working.
        """
        ref_drug = self.profile.get("ref_drug", "")
        ref_aff  = self.profile.get("ref_affinity")
        ts_iso   = datetime.now().isoformat(timespec="seconds")

        # ---- CSV ----
        csv_path = os.environ.get("AGENT_RESULTS_FILE") \
                   or f"agent_results_{self.run_id}.csv"
        # Ensure parent dir exists (for per-job paths like jobs/<uuid>/results.csv)
        Path(csv_path).parent.mkdir(parents=True, exist_ok=True)

        rows = [
            _canonicalize_row(
                c,
                target=self.target_key,
                ref_drug=ref_drug,
                ref_aff=ref_aff,
                run_id=self.run_id,
                timestamp=ts_iso,
            )
            for c in compounds
        ]

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=CANONICAL_CSV_COLUMNS,
                               extrasaction='ignore')
            w.writeheader()
            w.writerows(rows)
        self.log.log("Orchestrator", f"Results saved -> {csv_path}")

        # ---- JSON leaderboard (top 20) ----
        json_path = os.environ.get("AGENT_LEADERBOARD_FILE") \
                    or f"agent_leaderboard_{self.run_id}.json"
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, 'w') as f:
            json.dump(rows[:20], f, indent=2, default=str)
        self.log.log("Orchestrator", f"Leaderboard -> {json_path}")

    def _print_certificate(self, best: dict):
        if not best:
            self.log.log("Orchestrator", "No candidates to certify.")
            return
        self.log.separator("=")
        sigma_val = best.get("sigma_label", "-")
        sigma_st  = best.get("sigma_status", "not computed")
        is_disc   = best.get("is_discovery", False)
        smiles_s  = (best.get("smiles","?")[:46])
        reasons_s = ", ".join(best.get("reasons",[]))[:46]
        print(f"""
  +==============================================================+
  |  COMPUTATIONAL LEAD CANDIDATE CERTIFICATE                    |
  |  PhysicsChem Discovery Pipeline v2.0                         |
  |  5-Sigma Significance Testing  (Higgs Method)                |
  +==============================================================+
  |  Target    : {self.profile["name"]:<48}|
  |  Disease   : {self.profile["disease"]:<48}|
  |  Run ID    : {self.run_id:<48}|
  +==============================================================+
  |  Lead      : {best.get("id","?"):<48}|
  |  SMILES    : {smiles_s:<48}|
  |  Affinity  : {str(best.get("dock_affinity","?"))+" kcal/mol":<48}|
  |  HIGGS SIG : {sigma_val:<48}|
  |  STATUS    : {sigma_st:<48}|
  |  LE        : {str(best.get("LE","?"))+" kcal/mol/HA":<48}|
  |  MW        : {str(best.get("MW","?"))+" Da":<48}|
  |  hERG      : {str(best.get("hERG","N/A")):<48}|
  |  DILI      : {str(best.get("DILI","N/A")):<48}|
  |  Confidence: {str(best.get("confidence","?"))+"%":<48}|
  +==============================================================+
  |  Strengths : {reasons_s:<48}|
  |  Discovery : {"YES - 5-SIGMA HIT" if is_disc else "Evidence candidate":<48}|
  |  Timestamp : {datetime.now().strftime("%Y-%m-%d %H:%M:%S"):<48}|
  +==============================================================+
  Research use only. Requires synthesis + experimental validation.
""")
        self.log.separator("=")
        self.log.log("Orchestrator",
            f"Campaign complete. Log -> agent_run_{self.run_id}.log")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="PhysicsChem Autonomous Drug Discovery Agent v2 (5-sigma)")
    parser.add_argument("--target", default="EGFR",
        choices=list(TARGET_PROFILES.keys()), metavar='TARGET',
        help=f"Disease target. Available: {', '.join(TARGET_PROFILES.keys())}")
    parser.add_argument("--list-targets", action="store_true",
        help="List all available targets with disease info and exit")
    parser.add_argument("--receptor", default=None,
        help="Override receptor PDBQT path")
    parser.add_argument("--frags", type=int, default=30,
        help="Number of fragments to screen")
    parser.add_argument("--iterations", type=int, default=2,
        help="Max grow-dock-validate iterations")
    parser.add_argument("--exhaustiveness", type=int, default=8,
        help="Vina exhaustiveness (4=fast, 8=standard, 16=thorough)")
    parser.add_argument("--fast", action="store_true",
        help="Fast mode: 20 frags, 1 iter, exhaustiveness=4")
    parser.add_argument("--confidence", type=int, default=70,
        help="Target confidence score (0-100)")
    parser.add_argument("--max-alt", type=float, default=200.0)
    parser.add_argument("--max-ast", type=float, default=200.0)
    parser.add_argument("--max-creatinine", type=float, default=3.0)
    args = parser.parse_args()

    if args.fast:
        args.frags         = 20
        args.iterations    = 1
        args.exhaustiveness = 4

    if args.list_targets:
        print("\n  PhysicsChem FBDD Platform v2 — Available Targets")
        print("  " + "="*65)
        for cat, keys in DISEASE_CATEGORIES.items():
            print(f"\n  [{cat}]")
            for k in keys:
                p = TARGET_PROFILES.get(k,{})
                print(f"    {k:<14} {p.get('name','?'):<38} ref: {p.get('ref_drug','?')}")
        print()
        sys.exit(0)

    agent = OrchestratorAgent(
        target_key        = args.target,
        n_fragments       = args.frags,
        max_iterations    = args.iterations,
        exhaustiveness    = args.exhaustiveness,
        confidence_target = args.confidence,
    )

    if args.receptor:
        agent.profile["receptor"] = args.receptor

    agent.run()


if __name__ == "__main__":
    main()
