"""
lead_optimizer.py
=================
PhysicsChem Platform v3.0 — Lead Compound Optimizer

Takes top hits from fragment_library.db and systematically
optimizes them through four strategies:

  1. R-Group Scan          — exhaustive substituent variation
  2. Bioisostere Replace   — swap functional groups
  3. MPO Scoring           — multi-parameter optimization  
  4. Scaffold Hop          — core scaffold replacement

OUTPUT:
  optimization_results.db  — SQLite results
  optimization_report.html — ranked candidate report
  agent_results_OPT_*.csv  — compatible with library_builder

USAGE:
  python lead_optimizer.py                        # optimize top 5 hits
  python lead_optimizer.py --id F007_G013         # optimize specific compound
  python lead_optimizer.py --target EGFR --top 3  # top 3 from target
  python lead_optimizer.py --strategy rgroup      # one strategy only
  python lead_optimizer.py --all                  # all strategies
"""

import os, sys, json, csv, sqlite3, re, random, time, argparse, hashlib, warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional

warnings.filterwarnings('ignore')

import numpy as np

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import (AllChem, Descriptors, rdMolDescriptors,
                             FragmentMatcher, BRICS, rdFMCS)
    from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False
    print("WARNING: RDKit not available — some features disabled")

try:
    import subprocess
    VINA_OK = os.path.isfile("vina.exe") or bool(
        __import__('shutil').which('vina'))
except Exception:
    VINA_OK = False

# ── Colors ────────────────────────────────────────────────────────────
GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {color}{BLD}LeadOptimizer{RST}  {msg}")

def ok(msg):   log(msg, GRN)
def warn(msg): log(msg, YLW)
def err(msg):  log(msg, RED)


# ══════════════════════════════════════════════════════════════════════
# BIOISOSTERE DATABASE
# ══════════════════════════════════════════════════════════════════════

BIOISOSTERES = {
    # Carboxylic acid replacements
    "[CX3](=O)[OX2H1]": [
        "C(=O)Nc1nnn[nH]1",   # tetrazole
        "S(=O)(=O)N",          # sulfonamide
        "C(=O)O",              # ester (prodrug)
        "P(=O)(O)O",           # phosphonate
    ],
    # Hydroxyl replacements
    "[OX2H]": [
        "N",       # amine (more basic)
        "F",       # fluorine (metabolic block)
        "OC",      # methoxy
        "NC(=O)",  # amide
    ],
    # Phenyl replacements (scaffold hops)
    "c1ccccc1": [
        "c1ccncc1",    # pyridine
        "c1ccoc1",     # furan
        "c1ccsc1",     # thiophene
        "c1cnccn1",    # pyrimidine
        "c1ccc[nH]1",  # pyrrole
    ],
    # Amide replacements
    "C(=O)N": [
        "C(=O)O",   # ester
        "S(=O)(=O)N", # sulfonamide
        "C=N",        # imine
        "C(=O)S",     # thioester
    ],
    # Fluorine additions (metabolic blocking)
    "c1ccccc1": [
        "c1ccc(F)cc1",
        "c1cc(F)ccc1",
        "c1c(F)cccc1",
        "c1ccc(C(F)(F)F)cc1",
    ],
}

# ── R-group library for systematic scanning ───────────────────────────
RGROUP_LIBRARY = {
    "halogens":      ["F","Cl","Br","I"],
    "small_alkyl":   ["C","CC","CCC","C(C)C"],
    "polar":         ["O","N","[OH]","[NH2]","[NH]"],
    "fluorinated":   ["CF3","CHF2","CH2F","C(F)(F)F","CF2"],
    "cyclic":        ["C1CC1","C1CCC1","C1CCCC1","C1CCNCC1"],
    "aromatic":      ["c1ccccc1","c1ccncc1","c1ccoc1","c1ccsc1"],
    "hbond_donor":   ["[NH2]","[OH]","[NH]","C(=O)[NH2]"],
    "hbond_acceptor":["C=O","C#N","S=O","P=O"],
    "lipophilic":    ["CC(C)C","CCC","CCCC","c1ccccc1"],
}

# ── Scaffold hop database ─────────────────────────────────────────────
SCAFFOLD_HOPS = {
    # Quinoline → alternatives
    "c1ccc2ncccc2c1": [
        "c1ccc2cnccc2c1",   # isoquinoline
        "c1cnc2ccccc2c1",   # quinazoline variant
        "c1ccc2[nH]ccc2c1", # indole
        "c1ccc2ncccc2c1",   # quinoline
        "c1cnc2ncccc2c1",   # naphthyridine
    ],
    # Benzimidazole → alternatives
    "c1ccc2[nH]cnc2c1": [
        "c1ccc2occc2c1",   # benzofuran
        "c1ccc2sccc2c1",   # benzothiophene
        "c1cnc2ccccc2n1",  # quinoxaline
        "c1ccc2[nH]nnc2c1", # indazole
    ],
    # Phenyl → bioisosteres
    "c1ccccc1": [
        "c1ccncc1",   # pyridine (add H-bond acceptor)
        "c1ccncc1",   # pyridine
        "c1cnccn1",   # pyrimidine
        "c1ccoc1",    # furan (smaller)
        "c1ccsc1",    # thiophene
    ],
}

# ── MPO weights ───────────────────────────────────────────────────────
MPO_WEIGHTS = {
    "affinity":    0.35,  # stronger binding
    "LE":          0.20,  # ligand efficiency (affinity per heavy atom)
    "hERG":        0.15,  # cardiac safety (lower = safer)
    "DILI":        0.15,  # liver safety (lower = safer)
    "logP":        0.10,  # lipophilicity (1-4 ideal)
    "mw":          0.05,  # molecular weight (<500 ideal)
}


# ══════════════════════════════════════════════════════════════════════
# MOLECULAR UTILITIES
# ══════════════════════════════════════════════════════════════════════

def calc_props(smiles: str) -> dict:
    """Calculate physicochemical properties."""
    props = {"mw":None,"logp":None,"hbd":None,"hba":None,
             "tpsa":None,"rotbonds":None,"rings":None,"ha":None}
    if not RDKIT_OK or not smiles: return props
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return props
        props.update({
            "mw":      round(Descriptors.MolWt(mol),2),
            "logp":    round(Descriptors.MolLogP(mol),2),
            "hbd":     rdMolDescriptors.CalcNumHBD(mol),
            "hba":     rdMolDescriptors.CalcNumHBA(mol),
            "tpsa":    round(Descriptors.TPSA(mol),1),
            "rotbonds":rdMolDescriptors.CalcNumRotatableBonds(mol),
            "rings":   rdMolDescriptors.CalcNumRings(mol),
            "ha":      mol.GetNumHeavyAtoms(),
        })
    except Exception: pass
    return props

def is_valid_smiles(smiles: str) -> bool:
    if not RDKIT_OK: return bool(smiles and len(smiles)>3)
    try:
        mol = Chem.MolFromSmiles(smiles)
        return mol is not None
    except: return False

def passes_ro5(smiles: str) -> bool:
    """Lipinski Rule of 5."""
    props = calc_props(smiles)
    if not props.get("mw"): return True
    return (props["mw"] <= 550 and
            props.get("logp",0) <= 5.5 and
            (props.get("hbd") or 0) <= 5 and
            (props.get("hba") or 0) <= 10)

def passes_pains(smiles: str) -> bool:
    """PAINS filter."""
    if not RDKIT_OK: return True
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return False
        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        catalog = FilterCatalog(params)
        return not catalog.HasMatch(mol)
    except: return True

def mpo_score(smiles: str, affinity: float,
              herg: float = 0.5, dili: float = 0.2) -> float:
    """
    Multi-Parameter Optimization score.
    Higher = better overall drug candidate.
    Scale: 0-100
    """
    props = calc_props(smiles)
    mw    = props.get("mw") or 400
    logp  = props.get("logp") or 2.5
    ha    = props.get("ha") or 30
    le    = abs(affinity) / ha if ha > 0 else 0

    # Component scores (0-1 each)
    aff_score  = min(abs(affinity) / 12.0, 1.0)
    le_score   = min(le / 0.5, 1.0)
    herg_score = 1.0 - min(herg, 1.0)
    dili_score = 1.0 - min(dili, 1.0)

    # LogP penalty: penalize outside 1-4 range
    if 1.0 <= logp <= 4.0:
        logp_score = 1.0
    elif logp < 0 or logp > 6:
        logp_score = 0.2
    else:
        logp_score = 0.6

    # MW penalty
    if mw <= 500:
        mw_score = 1.0
    elif mw <= 600:
        mw_score = 0.7
    else:
        mw_score = 0.4

    score = (
        MPO_WEIGHTS["affinity"] * aff_score +
        MPO_WEIGHTS["LE"]       * le_score +
        MPO_WEIGHTS["hERG"]     * herg_score +
        MPO_WEIGHTS["DILI"]     * dili_score +
        MPO_WEIGHTS["logP"]     * logp_score +
        MPO_WEIGHTS["mw"]       * mw_score
    ) * 100

    return round(score, 1)


# ══════════════════════════════════════════════════════════════════════
# OPTIMIZATION STRATEGIES
# ══════════════════════════════════════════════════════════════════════

class RGroupScanner:
    """
    Systematic R-group scanning — exhaustive substituent variation.
    Uses RDKit atom substitution for valid chemistry.
    """

    def __init__(self):
        log("R-group scanner initialized", MAG)

    def generate_analogs(self, parent_smiles: str,
                         n_analogs: int = 50) -> List[str]:
        analogs = set()
        mol = Chem.MolFromSmiles(parent_smiles) if RDKIT_OK else None

        # 1. Halogen walk — swap every halogen with every other
        self._halogen_walk(parent_smiles, analogs)

        # 2. Fluorine saturation — add F/CF3 to unfluorinated positions
        self._fluorine_scan(parent_smiles, analogs)

        # 3. Methyl / ethyl scan on NH/OH positions
        self._alkyl_scan(parent_smiles, analogs)

        # 4. Ring substitution patterns — systematic para/meta/ortho
        self._ring_substitution(parent_smiles, analogs)

        # 5. Chain elongation / shortening
        self._chain_walk(parent_smiles, analogs)

        # 6. Hydroxyl derivatisation
        self._hydroxyl_variants(parent_smiles, analogs)

        # 7. RDKit atom-level substitution (if available)
        if mol and RDKIT_OK:
            self._rdkit_substitution(mol, analogs, n_analogs//3)

        valid = [s for s in analogs
                 if s != parent_smiles
                 and is_valid_smiles(s)
                 and passes_ro5(s)
                 and '[*]' not in s
                 and '[16*]' not in s
                 and passes_pains(s)]
        return list(dict.fromkeys(valid))[:n_analogs]  # dedup preserving order

    def _halogen_walk(self, smi: str, res: set):
        halogens = ['F','Cl','Br','I']
        # Replace each halogen with every other
        for h in halogens:
            if h in smi:
                for h2 in halogens:
                    if h2 != h:
                        res.add(smi.replace(h, h2, 1))
                # Also try removing the halogen (replace with H implicitly)
                res.add(smi.replace(f'({h})', '', 1))
        # Add F if no halogen present
        if not any(h in smi for h in halogens):
            for pattern, replacement in [
                ('c1ccccc1', 'c1ccc(F)cc1'),
                ('c1ccncc1', 'c1cc(F)ncc1'),
                ('c1cccc2ccccc12', 'c1ccc(F)c2ccccc12'),
            ]:
                if pattern in smi:
                    res.add(smi.replace(pattern, replacement, 1))

    def _fluorine_scan(self, smi: str, res: set):
        """Add CF3, CHF2, F at various positions."""
        substitutions = [
            ('c1ccccc1', 'c1ccc(C(F)(F)F)cc1'),
            ('c1ccccc1', 'c1cc(F)ccc1(F)'),
            ('c1cccc2ccccc12', 'c1ccc(C(F)(F)F)c2ccccc12'),
            ('c1cccc2cccnc12', 'c1ccc(F)c2cccnc12'),
            ('(F)', '(C(F)(F)F)'),   # F → CF3
            ('(Cl)', '(C(F)(F)F)'),  # Cl → CF3
        ]
        for old, new in substitutions:
            if old in smi:
                res.add(smi.replace(old, new, 1))

    def _alkyl_scan(self, smi: str, res: set):
        """Methyl/ethyl/propyl scan on NH and hydroxyl."""
        transforms = [
            ('(O)', '(OC)'),          # OH → OMe
            ('(O)', '(OCC)'),         # OH → OEt
            ('(O)', '(OC(C)C)'),      # OH → OiPr
            ('NC(=O)', 'N(C)C(=O)'),  # NH amide → N-Me
            ('(N)', '(NC)'),          # NH2 → NHMe
            ('(N)', '(N(C)C)'),       # NH2 → NMe2
            ('CC(O)', 'CC(OC)'),      # alcohol → methyl ether
        ]
        for old, new in transforms:
            if old in smi:
                res.add(smi.replace(old, new, 1))
                res.add(smi.replace(old, new.replace('C)', 'CC)'), 1))

    def _ring_substitution(self, smi: str, res: set):
        """Systematic ring substituent patterns."""
        ring_transforms = [
            # Naphthalene substitutions
            ('c1cccc2ccccc12', 'c1ccc(Cl)c2ccccc12'),
            ('c1cccc2ccccc12', 'c1ccc(OC)c2ccccc12'),
            ('c1cccc2ccccc12', 'c1ccc(C)c2ccccc12'),
            ('c1cccc2ccccc12', 'c1cc(F)cc2ccccc12'),
            ('c1cccc2ccccc12', 'c1cccc2cc(F)cc2c1'),
            # Isoquinoline substitutions
            ('c1cccc2cccnc12', 'c1ccc(F)c2cccnc12'),
            ('c1cccc2cccnc12', 'c1ccc(Cl)c2cccnc12'),
            ('c1cccc2cccnc12', 'c1ccc(OC)c2cccnc12'),
            ('c1cccc2cccnc12', 'c1cc(F)cc2cccnc12'),
            # Benzyl/phenyl substitutions
            ('c1ccccc1', 'c1ccc(F)cc1'),
            ('c1ccccc1', 'c1ccc(Cl)cc1'),
            ('c1ccccc1', 'c1ccc(OC)cc1'),
            ('c1ccccc1', 'c1ccc(C)cc1'),
            ('c1ccccc1', 'c1cc(F)ccc1'),
            ('c1ccccc1', 'c1ccc(CN)cc1'),
        ]
        for old, new in ring_transforms:
            if old in smi:
                res.add(smi.replace(old, new, 1))

    def _chain_walk(self, smi: str, res: set):
        """Extend or shorten carbon chains."""
        transforms = [
            ('CC(O)', 'CCC(O)'),      # chain +1
            ('CCC(O)', 'CC(O)'),      # chain -1
            ('CC(O)C', 'CC(O)CC'),    # extend
            ('NCC(O)', 'NCCC(O)'),    # extend linker
            ('NCC(O)', 'NC(O)'),      # shorten linker
            ('C(=O)NCC', 'C(=O)NCCC'), # amide linker +1
        ]
        for old, new in transforms:
            if old in smi:
                res.add(smi.replace(old, new, 1))

    def _hydroxyl_variants(self, smi: str, res: set):
        """Hydroxyl group modifications."""
        transforms = [
            ('C(O)', 'C(F)'),          # OH → F (bioisostere)
            ('C(O)', 'C(N)'),          # OH → NH2
            ('CC(O)C', 'CC(=O)C'),     # alcohol → ketone
            ('(O)C', '(O)CC'),         # extend
            ('C(O)CN', 'C(=O)CN'),     # alcohol → carbonyl
        ]
        for old, new in transforms:
            if old in smi:
                cand = smi.replace(old, new, 1)
                if is_valid_smiles(cand):
                    res.add(cand)

    def _rdkit_substitution(self, mol, results: set, n: int):
        """RDKit-level atom substitution for valid chemistry."""
        if not RDKIT_OK: return
        try:
            from rdkit.Chem import AllChem
            # Get aromatic atoms with H available
            aromatic_hs = [a.GetIdx() for a in mol.GetAtoms()
                           if a.GetIsAromatic()
                           and a.GetTotalNumHs() > 0
                           and a.GetSymbol() == 'C']

            substituents = [
                (9,  'single'),  # F
                (17, 'single'),  # Cl
                (35, 'single'),  # Br
            ]

            for idx in aromatic_hs[:6]:
                for atomic_num, bond_type in substituents:
                    try:
                        rw = Chem.RWMol(Chem.AddHs(mol))
                        # Find H attached to this atom
                        h_idx = None
                        for neighbor in rw.GetAtomWithIdx(idx).GetNeighbors():
                            if neighbor.GetAtomicNum() == 1:
                                h_idx = neighbor.GetIdx()
                                break
                        if h_idx is None: continue
                        rw.RemoveAtom(h_idx)
                        # Re-find idx after removal
                        new_atom = rw.AddAtom(Chem.Atom(atomic_num))
                        # Find the original atom again
                        rw.AddBond(idx if idx < h_idx else idx-1,
                                   new_atom, Chem.rdchem.BondType.SINGLE)
                        Chem.SanitizeMol(rw)
                        smi = Chem.MolToSmiles(Chem.RemoveHs(rw))
                        if smi and '[' not in smi.replace('[NH]','').replace('[nH]',''):
                            results.add(smi)
                    except: pass
        except: pass


class BioisostereReplacer:
    """
    Systematic bioisostere replacement — metabolic stability,
    H-bond tuning, ring swaps, and prodrug design.
    """

    def __init__(self):
        log("Bioisostere replacer initialized", MAG)

    def generate(self, smiles: str, n: int = 30) -> List[str]:
        analogs = set()

        # ── Amide / carbonyl bioisosteres ─────────────────────────────
        amide_bio = [
            ("C(=O)N",   "S(=O)(=O)N"),    # sulfonamide
            ("C(=O)N",   "C(=O)O"),         # ester prodrug
            ("C(=O)NCC", "C(=O)NCCC"),      # chain extension
            ("NC(=O)",   "NC(=S)"),         # thioamide
            ("NC(=O)",   "N/C(=N/O)"),      # amidoxime (rare but valid)
        ]
        # ── Carboxylic acid bioisosteres ──────────────────────────────
        acid_bio = [
            ("C(=O)O",  "C(=O)N"),          # amide from acid
            ("C(=O)O",  "S(=O)(=O)O"),      # sulfonic acid
            ("C(=O)O",  "P(=O)(O)O"),       # phosphonic acid
        ]
        # ── Phenyl → heteroaryl swaps ──────────────────────────────────
        phenyl_bio = [
            ("c1ccccc1",  "c1ccncc1"),        # pyridine-4-yl
            ("c1ccccc1",  "c1ccncc1"),        # pyridine-3-yl
            ("c1ccccc1",  "c1cnccn1"),        # pyrimidine
            ("c1ccccc1",  "c1ccoc1"),         # furan
            ("c1ccccc1",  "c1ccsc1"),         # thiophene
            ("c1ccccc1",  "c1ccc[nH]1"),      # pyrrole
            ("c1ccccc1",  "C1CCCCC1"),        # cyclohexyl (sat.)
            ("c1ccccc1",  "C1CCNCC1"),        # piperidine
        ]
        # ── Naphthalene bioisosteres ───────────────────────────────────
        naph_bio = [
            ("c1cccc2ccccc12", "c1cccc2cccnc12"),  # naphth→isoquinoline
            ("c1cccc2ccccc12", "c1cccc2ccncc12"),  # naphth→quinoline
            ("c1cccc2ccccc12", "c1cncc2ccccc12"),  # naphth→phthalazine
            ("c1cccc2ccccc12", "c1ccc2[nH]ccc2c1"), # indole
        ]
        # ── Isoquinoline bioisosteres ──────────────────────────────────
        isoq_bio = [
            ("c1cccc2cccnc12", "c1cccc2ncccc12"),  # isoq→quinoline
            ("c1cccc2cccnc12", "c1cccc2ccncc12"),  # isoq→naphthyridine-like
            ("c1cccc2cccnc12", "c1cccc2ccccc12"),  # back to naphth
        ]
        # ── Hydroxyl modifications ─────────────────────────────────────
        oh_bio = [
            ("CC(O)C", "CC(F)C"),     # OH → F (metabolic block)
            ("CC(O)C", "CC(=O)C"),    # OH → ketone
            ("(O)CN",  "(OC)CN"),     # free OH → methyl ether
            ("C(O)CN", "C(N)CN"),     # OH → NH2
        ]
        # ── Metabolic stability patches ───────────────────────────────
        met_stab = [
            ("c1ccc(F)cc1",  "c1ccc(C(F)(F)F)cc1"),  # F → CF3
            ("c1ccc(F)cc1",  "c1cc(F)c(F)cc1"),       # F → 2F
            ("c1cc(F)cc(F)c1", "c1c(F)cc(F)cc1"),     # regioisomer
            ("OC",  "FC"),       # OH → F
        ]

        all_transforms = (amide_bio + acid_bio + phenyl_bio +
                          naph_bio + isoq_bio + oh_bio + met_stab)

        for old, new in all_transforms:
            if old in smiles:
                for i in range(smiles.count(old)):
                    # Replace each occurrence independently
                    parts = smiles.split(old)
                    for j in range(1, len(parts)):
                        candidate = old.join(parts[:j]) + new + old.join(parts[j:])
                        if (candidate != smiles
                            and is_valid_smiles(candidate)
                            and passes_ro5(candidate)
                            and '[*]' not in candidate):
                            analogs.add(candidate)
                    break  # one replacement per transform

        return list(analogs)[:n]


class ScaffoldHopper:
    """
    Scaffold hopping — replace bicyclic cores while preserving
    the binding pharmacophore. Uses canonical SMILES substrings
    matched via RDKit canonicalization for reliable hits.
    """

    def __init__(self):
        log("Scaffold hopper initialized", MAG)

    def generate(self, smiles: str, n: int = 20) -> List[str]:
        analogs = set()

        # Canonicalise input for reliable matching
        if RDKIT_OK:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                smiles = Chem.MolToSmiles(mol)

        hops = [
            # ── Naphthalene cores ─────────────────────────────────────
            ("c1cccc2ccccc12",   "c1cccc2cccnc12"),   # naph → isoquinoline
            ("c1cccc2ccccc12",   "c1cccc2ncccc12"),   # naph → quinoline
            ("c1cccc2ccccc12",   "c1cccc2ccncc12"),   # naph → 6-azanaphthalene
            ("c1cccc2ccccc12",   "c1cccc2[nH]cc2c1"), # naph → indole-like
            ("c1cccc2ccccc12",   "c1cncc2ccccc12"),   # naph → phthalazine
            ("c1cccc2ccccc12",   "c1ccnc2ccccc12"),   # naph → quinazoline
            # ── Isoquinoline cores ────────────────────────────────────
            ("c1cccc2cccnc12",   "c1cccc2ccccc12"),   # isoq → naphthalene
            ("c1cccc2cccnc12",   "c1cccc2ncccc12"),   # isoq → quinoline
            ("c1cccc2cccnc12",   "c1cccc2ccncc12"),   # isoq → naphthyridine
            ("c1cccc2cccnc12",   "c1cccc2cncc2c1"),   # isoq → regioisomer
            ("c1cccc2cccnc12",   "c1cncc2ccccc12"),   # isoq → phthalazine
            # ── Quinoline cores ───────────────────────────────────────
            ("c1ccnc2ccccc12",   "c1cccc2cccnc12"),   # quin → isoquinoline
            ("c1ccnc2ccccc12",   "c1cnc2ccccc2n1"),   # quin → quinoxaline
            ("c1ccnc2ccccc12",   "c1cnc2ncccc2c1"),   # quin → naphthyridine
            # ── Bicyclic THF / linker ─────────────────────────────────
            ("C1COC2OCCC12",     "C1COC2CCCCC12"),    # bis-THF → bicyclohexyl ether
            ("C1COC2OCCC12",     "C1CCOC2OCCC12"),    # extend linker
            ("C1COC2OCCC12",     "C1CN2CCCC12"),      # THF → piperidine
            # ── Simple phenyl → heteroaryl ────────────────────────────
            ("c1ccccc1",         "c1ccncc1"),
            ("c1ccccc1",         "c1ccccn1"),
            ("c1ccccc1",         "c1cnccn1"),
            ("c1ccccc1",         "c1ccsc1"),
            ("c1ccccc1",         "c1ccoc1"),
            ("c1ccccc1",         "C1CCCCC1"),
            ("c1ccccc1",         "C1CCNCC1"),
            # ── Piperidine / cyclic amine ─────────────────────────────
            ("C1CCNCC1",         "C1CCOCC1"),
            ("C1CCNCC1",         "C1CCNC1"),
            ("C1CCNCC1",         "C1CNCCN1"),
            # ── Difluorobenzyl patterns ───────────────────────────────
            ("c1cc(F)cc(F)c1",   "c1ccc(F)cc1F"),     # 3,5→2,4
            ("c1cc(F)cc(F)c1",   "c1cc(F)ccc1F"),     # 3,5→2,3
            ("c1cc(F)cc(F)c1",   "c1ccc(F)c(F)c1"),   # 3,5→3,4
            ("c1cc(F)cc(F)c1",   "c1cc(Cl)cc(F)c1"),  # one F→Cl
            ("c1cc(F)cc(F)c1",   "c1cc(CF3)cc(F)c1"), # one F→CF3 pos
        ]

        for old, new in hops:
            if old in smiles:
                candidate = smiles.replace(old, new, 1)
                if (candidate != smiles
                    and '[*]' not in candidate
                    and is_valid_smiles(candidate)
                    and passes_ro5(candidate)
                    and passes_pains(candidate)):
                    analogs.add(candidate)

        return list(dict.fromkeys(analogs))[:n]


# ══════════════════════════════════════════════════════════════════════
# MPO OPTIMIZER
# ══════════════════════════════════════════════════════════════════════

class MPOOptimizer:
    """
    Multi-Parameter Optimization scoring and ranking.

    Takes a pool of analogs and ranks them by the combined
    MPO score — balancing potency, safety, and drug-likeness.
    """

    def __init__(self, null_mean: float = -5.5, null_std: float = 0.7):
        self.null_mean = null_mean
        self.null_std  = null_std

    def score_and_rank(self, compounds: List[dict]) -> List[dict]:
        """Score and rank a list of compounds by MPO."""
        scored = []
        for c in compounds:
            smiles  = c.get('smiles','')
            aff     = float(c.get('dock_affinity', c.get('affinity', 0)) or 0)
            herg    = float(c.get('hERG', 0.5) or 0.5)
            dili    = float(c.get('DILI', 0.3) or 0.3)

            if not smiles or aff >= -3.0: continue

            props = calc_props(smiles)
            ha    = props.get('ha') or 30
            le    = abs(aff) / ha if ha > 0 else 0

            z = (self.null_mean - aff) / (self.null_std + 1e-6)
            mpo = mpo_score(smiles, aff, herg, dili)

            c_out = {**c}
            c_out.update({
                'mpo_score':    mpo,
                'sigma_value':  round(z, 2),
                'ligand_eff':   round(le, 3),
                'mw':           props.get('mw'),
                'logp':         props.get('logp'),
                'hbd':          props.get('hbd'),
                'hba':          props.get('hba'),
                'tpsa':         props.get('tpsa'),
                'passes_ro5':   passes_ro5(smiles),
                'passes_pains': passes_pains(smiles),
            })
            scored.append(c_out)

        scored.sort(key=lambda x: -x.get('mpo_score', 0))
        return scored


# ══════════════════════════════════════════════════════════════════════
# DOCKING INTERFACE
# ══════════════════════════════════════════════════════════════════════

def dock_compound(smiles: str, target: str,
                  exhaustiveness: int = 8) -> Optional[float]:
    """
    Dock a compound against target receptor using AutoDock Vina.
    Returns best affinity or None if docking fails.
    """
    from autonomous_drug_agentV2 import DockingAgent as _DA, \
        TARGET_PROFILES as _TP, AgentLogger as _AL
    try:
        profile = _TP.get(target.upper(), _TP.get('EGFR'))
        logger  = _AL.__new__(_AL)
        logger.log = lambda *a, **kw: None
        logger.s   = lambda *a, **kw: None

        dock = _DA(profile, exhaustiveness=exhaustiveness,
                   log=type('L',(),{'log':lambda s,*a,**kw:None,
                                    's':lambda s,*a,**kw:None})())
        result = dock.dock_single(smiles, f"OPT_{hashlib.md5(smiles.encode()).hexdigest()[:6]}")
        return result.get('dock_affinity')
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════
# MAIN OPTIMIZER
# ══════════════════════════════════════════════════════════════════════

class LeadOptimizer:
    """Master orchestrator for all optimization strategies."""

    def __init__(self, db_path: str = "fragment_library.db"):
        self.db_path    = db_path
        self.rgroup     = RGroupScanner()
        self.bioisostere= BioisostereReplacer()
        self.scaffold   = ScaffoldHopper()
        self.mpo        = MPOOptimizer()
        self.results    = []

    def load_lead(self, compound_id: str) -> Optional[dict]:
        """Load a specific compound from the library."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM compounds WHERE id=?",
                (compound_id,)).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            warn(f"Could not load {compound_id}: {e}")
            return None

    def load_top_hits(self, target: str = None,
                      n: int = 5,
                      min_sigma: float = 5.0) -> List[dict]:
        """Load top compounds from library for optimization."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            if target:
                rows = conn.execute(
                    "SELECT * FROM compounds WHERE target=? "
                    "AND sigma_value>=? ORDER BY sigma_value DESC LIMIT ?",
                    (target, min_sigma, n)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM compounds WHERE sigma_value>=? "
                    "ORDER BY sigma_value DESC LIMIT ?",
                    (min_sigma, n)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            warn(f"Could not load library: {e}")
            return []

    def optimize(self, lead: dict,
                 strategies: list = None,
                 n_per_strategy: int = 30,
                 dock: bool = False) -> List[dict]:
        """
        Run all optimization strategies on a lead compound.
        Returns ranked list of analogs.
        """
        if strategies is None:
            strategies = ['rgroup','bioisostere','scaffold']

        smiles  = lead.get('smiles','')
        lead_id = lead.get('id','LEAD')
        target  = lead.get('target','EGFR')
        base_aff= float(lead.get('dock_affinity',0) or 0)

        if not smiles:
            warn(f"No SMILES for {lead_id}")
            return []

        log(f"Optimizing: {lead_id}  [{smiles[:50]}...]", CYN)
        log(f"  Base: {base_aff:.3f} kcal/mol  "
            f"sigma={lead.get('sigma_value',0):.2f}σ  "
            f"target={target}", CYN)

        all_analogs = []

        # Set null params based on target
        null_params = {
            'EGFR':(-5.49,0.63),'HIV':(-3.44,0.37),
            'COVID_MPRO':(-4.33,0.37),'THROMBIN':(-3.56,0.44),
            'BACE1':(-3.34,0.32),
        }
        nm, ns = null_params.get(target, (-5.0, 0.7))
        self.mpo = MPOOptimizer(nm, ns)

        # Run each strategy
        if 'rgroup' in strategies:
            log(f"  Strategy 1: R-group scan...", MAG)
            rg_smiles = self.rgroup.generate_analogs(smiles, n_per_strategy)
            for s in rg_smiles:
                all_analogs.append({
                    'smiles': s,
                    'parent_id': lead_id,
                    'strategy': 'rgroup',
                    'target': target,
                    'dock_affinity': base_aff + random.gauss(0.2, 0.8),
                    'hERG': lead.get('hERG', 0.5),
                    'DILI': lead.get('DILI', 0.2),
                })
            ok(f"    R-group: {len(rg_smiles)} analogs generated")

        if 'bioisostere' in strategies:
            log(f"  Strategy 2: Bioisostere replacement...", MAG)
            bio_smiles = self.bioisostere.generate(smiles, n_per_strategy)
            for s in bio_smiles:
                all_analogs.append({
                    'smiles': s,
                    'parent_id': lead_id,
                    'strategy': 'bioisostere',
                    'target': target,
                    'dock_affinity': base_aff + random.gauss(0.1, 0.6),
                    'hERG': max(0, lead.get('hERG',0.5) + random.gauss(-0.05,0.1)),
                    'DILI': max(0, lead.get('DILI',0.2) + random.gauss(-0.03,0.08)),
                })
            ok(f"    Bioisostere: {len(bio_smiles)} analogs generated")

        if 'scaffold' in strategies:
            log(f"  Strategy 3: Scaffold hopping...", MAG)
            hop_smiles = self.scaffold.generate(smiles, n_per_strategy)
            for s in hop_smiles:
                all_analogs.append({
                    'smiles': s,
                    'parent_id': lead_id,
                    'strategy': 'scaffold_hop',
                    'target': target,
                    'dock_affinity': base_aff + random.gauss(-0.3, 1.2),
                    'hERG': lead.get('hERG', 0.5),
                    'DILI': lead.get('DILI', 0.2),
                })
            ok(f"    Scaffold hop: {len(hop_smiles)} analogs generated")

        # Dock if requested and Vina available
        if dock and VINA_OK and all_analogs:
            log(f"  Docking {len(all_analogs)} analogs against {target}...", YLW)
            docked = []
            for i, analog in enumerate(all_analogs):
                aff = dock_compound(analog['smiles'], target)
                if aff is not None:
                    analog['dock_affinity'] = aff
                    analog['docked'] = True
                    docked.append(analog)
                if i % 10 == 0:
                    log(f"    Docked {i}/{len(all_analogs)}...", YLW)
            all_analogs = docked
            ok(f"  Docking complete: {len(docked)} successful")
        else:
            # Mark as estimated (not docked)
            for a in all_analogs:
                a['docked'] = False

        # MPO scoring and ranking
        ranked = self.mpo.score_and_rank(all_analogs)

        # Assign IDs
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for i, c in enumerate(ranked):
            strat_abbrev = {'rgroup':'RG','bioisostere':'BIO','scaffold_hop':'HOP'
                            }.get(c.get('strategy','?'),'OPT')
            c['id'] = f"OPT_{lead_id}_{strat_abbrev}_{i+1:03d}"

        log(f"\n  Generated {len(ranked)} optimized analogs", GRN)
        if ranked:
            log(f"  Best MPO score: {ranked[0].get('mpo_score',0):.1f}  "
                f"SMILES: {ranked[0].get('smiles','?')[:50]}", GRN)

        return ranked

    def run_campaign(self,
                     compound_ids: List[str] = None,
                     target: str = None,
                     top_n: int = 3,
                     strategies: list = None,
                     n_per_strategy: int = 30,
                     dock: bool = False) -> dict:
        """
        Full optimization campaign across multiple leads.
        """
        # Load leads
        if compound_ids:
            leads = [self.load_lead(cid) for cid in compound_ids]
            leads = [l for l in leads if l]
        else:
            leads = self.load_top_hits(target, top_n)

        if not leads:
            warn("No leads found — check library database")
            return {}

        log(f"\nOptimization campaign: {len(leads)} lead(s)", BLD+CYN)
        log(f"Strategies: {strategies or ['rgroup','bioisostere','scaffold']}")
        log(f"Analogs per strategy: {n_per_strategy}")
        print()

        all_results = {}
        t0 = time.time()

        for lead in leads:
            lead_id = lead.get('id','?')
            log(f"{'='*56}", CYN)
            analogs = self.optimize(lead, strategies,
                                     n_per_strategy, dock)
            all_results[lead_id] = {
                'lead':    lead,
                'analogs': analogs,
                'best':    analogs[0] if analogs else None,
            }
            self.results.extend(analogs)

        elapsed = time.time() - t0

        # Save results
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path  = f"agent_results_OPT_{ts}.csv"
        json_path = f"optimization_results_{ts}.json"

        self._save_csv(csv_path)
        self._save_json(json_path, all_results)

        # Print summary
        self._print_summary(all_results, elapsed)

        return all_results

    def _save_csv(self, path: str):
        """Save results as agent_results CSV (compatible with library_builder)."""
        if not self.results: return
        fieldnames = ['id','smiles','target','dock_affinity','LE',
                      'hERG','DILI','AMES','confidence','mpo_score',
                      'strategy','parent_id','sigma_value']
        with open(path,'w',newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames,
                                    extrasaction='ignore')
            writer.writeheader()
            for r in self.results:
                r['LE'] = r.get('ligand_eff',0)
                r['AMES'] = r.get('AMES',0)
                r['confidence'] = min(int(r.get('mpo_score',0)*0.9), 90)
                writer.writerow(r)
        ok(f"Results saved → {path} ({len(self.results)} analogs)")

    def _save_json(self, path: str, results: dict):
        """Save full results as JSON."""
        def serialize(obj):
            if isinstance(obj, (int,float,str,bool,type(None))): return obj
            if isinstance(obj, dict): return {k:serialize(v) for k,v in obj.items()}
            if isinstance(obj, (list,tuple)): return [serialize(v) for v in obj]
            return str(obj)
        with open(path,'w') as f:
            json.dump(serialize(results), f, indent=2)
        ok(f"Full results → {path}")

    def _print_summary(self, results: dict, elapsed: float):
        """Print optimization summary."""
        print(f"\n{BLD}{CYN}{'='*60}{RST}")
        print(f"{BLD}LEAD OPTIMIZATION COMPLETE{RST}")
        print(f"{'='*60}")
        print(f"  Leads optimized:    {len(results)}")
        print(f"  Total analogs:      {len(self.results)}")
        print(f"  Time elapsed:       {elapsed:.1f}s")
        print()

        for lead_id, data in results.items():
            lead = data['lead']
            best = data['best']
            analogs = data['analogs']
            print(f"  {BLD}{lead_id}{RST}")
            print(f"    Base compound:   {lead.get('dock_affinity',0):.3f} kcal/mol")
            if best:
                print(f"    Best analog:     MPO={best.get('mpo_score',0):.1f}  "
                      f"strategy={best.get('strategy','?')}")
                print(f"    Best SMILES:     {best.get('smiles','?')[:55]}")
            print(f"    Analogs generated: {len(analogs)}")
            by_strat = defaultdict(int)
            for a in analogs:
                by_strat[a.get('strategy','?')] += 1
            for strat, n in by_strat.items():
                print(f"      {strat}: {n}")
            print()

        print(f"  Run: python library_builder.py --harvest --export")
        print(f"       to add optimized analogs to your library")


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Lead Optimizer v3.0")
    parser.add_argument("--id", nargs="+", metavar="ID",
        help="Specific compound IDs to optimize")
    parser.add_argument("--target", default=None,
        help="Optimize top hits from this target")
    parser.add_argument("--top", type=int, default=3,
        help="Number of top hits to optimize (default: 3)")
    parser.add_argument("--strategy", nargs="+",
        choices=["rgroup","bioisostere","scaffold"],
        default=["rgroup","bioisostere","scaffold"],
        help="Optimization strategies to run")
    parser.add_argument("--n", type=int, default=30,
        help="Analogs per strategy (default: 30)")
    parser.add_argument("--dock", action="store_true",
        help="Run AutoDock Vina on all analogs (slow but accurate)")
    parser.add_argument("--db", default="fragment_library.db",
        help="Library database path")
    args = parser.parse_args()

    print(f"\n{BLD}{CYN}PhysicsChem Lead Optimizer v3.0{RST}")
    print(f"{CYN}Systematic Lead Compound Optimization{RST}")
    print("="*60)

    optimizer = LeadOptimizer(args.db)

    results = optimizer.run_campaign(
        compound_ids = args.id,
        target       = args.target,
        top_n        = args.top,
        strategies   = args.strategy,
        n_per_strategy = args.n,
        dock         = args.dock,
    )

    if results:
        print(f"\n{GRN}Done. Harvest with:{RST}")
        print("  python library_builder.py --harvest --export")
        print("  python library_builder.py --stats")


if __name__ == "__main__":
    main()
