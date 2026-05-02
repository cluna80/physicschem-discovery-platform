"""
dip_patch.py
============
PhysicsChem Discovery Pipeline — DIP/TIP Patch
================================================
Drop-in replacements for:
  - CANONICAL_CSV_COLUMNS  (adds DIP fields)
  - _canonicalize_row()    (maps DIP fields)
  - ValidatorAgent         (DIP competition scoring)
  - DISEASE_DB entry       (dashboard.py addition)
  - TARGET_PROFILES entry  (already in agent, shown here for reference)

HOW TO APPLY
────────────
Option A — Manual merge (recommended for first-time):
  1. Replace CANONICAL_CSV_COLUMNS in autonomous_drug_agent.py
     with the one below.
  2. Replace _canonicalize_row() with the one below.
  3. Replace ValidatorAgent class with the one below.
  4. Add HIV_DIP_DASHBOARD_ENTRY to DISEASE_DB in dashboard.py.
  5. Add "HIV_DIP":"hiv_integrase.pdbqt" to the known dict
     inside _load_receptor_status() in dashboard.py.

Option B — Auto-patch (runs this file directly):
  python dip_patch.py

  The script will locate autonomous_drug_agent.py and dashboard.py
  in the current working directory and apply the patches in-place,
  creating .bak backups first.
"""

# ══════════════════════════════════════════════════════════════════════
# 1.  CANONICAL_CSV_COLUMNS  — drop-in replacement
# ══════════════════════════════════════════════════════════════════════

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
    # ── DIP / TIP fields (new) ─────────────────────────────────────
    "dip_competitive_advantage",   # float  — (ref_aff - compound_aff); positive = better than WT HIV
    "dip_viable",                  # bool   — True if competitive_advantage >= 0
    "dip_advantage_tier",          # str    — STRONG / MODERATE / MARGINAL / FAIL
    "dip_cd4_safe",                # bool   — compound unlikely to harm host CD4+ T-cells
    "dip_selectivity_score",       # float  — advantage / MW ratio (efficiency metric)
    # ──────────────────────────────────────────────────────────────
    # Validation
    "confidence", "reasons",
    # Context
    "target", "reference_drug", "reference_affinity", "run_id", "timestamp",
]


# ══════════════════════════════════════════════════════════════════════
# 2.  _canonicalize_row()  — drop-in replacement
# ══════════════════════════════════════════════════════════════════════

def _canonicalize_row(c: dict, *, target: str, ref_drug: str,
                      ref_aff: float, run_id: str,
                      timestamp: str) -> dict:
    """
    Map an agent-internal candidate dict to the canonical schema.
    All DIP fields default to empty string when target != HIV_DIP so
    existing downstream consumers see no change.
    """
    row = {col: "" for col in CANONICAL_CSV_COLUMNS}

    # ── Identity ──────────────────────────────────────────────────────
    row["id"]     = c.get("id", "")
    row["smiles"] = c.get("smiles", "")
    row["name"]   = c.get("name", "")
    row["parent"] = c.get("parent", "")

    # ── Docking ───────────────────────────────────────────────────────
    row["dock_affinity"] = c.get("dock_affinity", "")
    row["n_poses"]       = c.get("dock_poses", "")

    # ── Physicochem (translate legacy mixed-case keys) ─────────────────
    row["mw"]   = c.get("MW",   c.get("mw",   ""))
    row["logp"] = c.get("LogP", c.get("logp", ""))
    row["hac"]  = c.get("HAC",  c.get("hac",  ""))
    row["le"]   = c.get("LE",   c.get("le",   ""))

    # ── Higgs significance ────────────────────────────────────────────
    row["z_score"]      = c.get("z_score", "")
    row["sigma_label"]  = c.get("sigma_label", "-")
    row["sigma_status"] = c.get("sigma_status", "")
    row["is_discovery"] = "true" if c.get("is_discovery") else "false"
    row["is_evidence"]  = "true" if c.get("is_evidence")  else "false"

    # ── ADMET core ────────────────────────────────────────────────────
    row["admet_pass"]      = "true" if c.get("admet_pass") else "false"
    row["hERG"]            = c.get("hERG", "")
    row["DILI"]            = c.get("DILI", "")
    row["AMES"]            = c.get("AMES", "")
    row["ClinTox"]         = c.get("ClinTox", "")
    row["bioavailability"] = c.get("Bioavailability", c.get("bioavailability", ""))
    row["solubility"]      = c.get("Solubility",      c.get("solubility", ""))
    row["hia"]             = c.get("HIA",             c.get("hia", ""))

    # ── CYP450 ────────────────────────────────────────────────────────
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

    # ── PK ────────────────────────────────────────────────────────────
    row["half_life"]     = c.get("half_life", "")
    row["clearance_hep"] = c.get("clearance_hep", "")
    row["ppbr"]          = c.get("ppbr", "")
    row["vdss"]          = c.get("vdss", "")

    # ── DIP / TIP fields (non-empty only for HIV_DIP target) ──────────
    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")
    row["dip_viable"]                = (
        "true"  if c.get("dip_viable") else
        "false" if c.get("dip_competitive_advantage", "") != "" else ""
    )
    row["dip_advantage_tier"]   = c.get("dip_advantage_tier", "")
    row["dip_cd4_safe"]         = (
        "true"  if c.get("dip_cd4_safe") is True  else
        "false" if c.get("dip_cd4_safe") is False else ""
    )
    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")

    # ── Validation ────────────────────────────────────────────────────
    row["confidence"] = c.get("confidence", "")
    row["reasons"]    = "|".join(c.get("reasons", []))

    # ── Context ───────────────────────────────────────────────────────
    row["target"]             = target
    row["reference_drug"]     = ref_drug or ""
    row["reference_affinity"] = ref_aff if ref_aff is not None else ""
    row["run_id"]             = run_id
    row["timestamp"]          = timestamp

    return row


# ══════════════════════════════════════════════════════════════════════
# 3.  ValidatorAgent  — drop-in replacement
#     Includes full DIP competition scoring when target == HIV_DIP
# ══════════════════════════════════════════════════════════════════════

class ValidatorAgent:
    """
    Multi-criteria compound validator.

    For HIV_DIP targets, scoring uses a three-axis DIP fitness function:

        DIP_score = w_binding  * f(affinity vs WT HIV integrase)
                  + w_compete  * competitive_advantage
                  + w_cd4safe  * cd4_safety_bonus
                  - w_size     * size_penalty (DIP genome constraint)

    The competitive advantage axis is the key innovation:
    a compound must bind integrase BETTER than Dolutegravir (-9.43)
    to give a benign DIP particle a meaningful competitive edge over
    wild-type HIV-1 in the same infected CD4+ T-cell.
    """

    # Reference affinity for WT HIV integrase (Dolutegravir benchmark)
    DIP_REFERENCE_AFFINITY = -9.43   # kcal/mol (Dolutegravir, 3L2T)

    # MW ceiling for DIP-compatible ligands
    # (defective genome encodes smaller proteins → favor compact binders)
    DIP_MW_CEILING = 420.0
    DIP_MW_IDEAL   = 360.0

    # Competitive advantage tiers
    DIP_TIER_STRONG   = 2.0    # ≥ +2 kcal/mol better than DTG → STRONG
    DIP_TIER_MODERATE = 1.0    # ≥ +1 kcal/mol → MODERATE
    DIP_TIER_MARGINAL = 0.0    # ≥  0 kcal/mol (matches DTG) → MARGINAL
    # < 0 → FAIL (weaker than WT HIV integrase)

    def __init__(self, logger, selectivity_targets: dict, ref_affinity: float,
                 target_key: str = ""):
        self.log      = logger
        self.targets  = selectivity_targets
        self.ref_aff  = ref_affinity
        self.target_key = target_key.upper()

    # ── Internal helpers ──────────────────────────────────────────────

    def _standard_score(self, c: dict) -> tuple[int, list]:
        """Original scoring logic for non-DIP targets. Returns (score, reasons)."""
        aff     = c.get("dock_affinity", 0)
        score   = 0
        reasons = []

        # Binding affinity vs reference drug
        if aff <= self.ref_aff - 2.0:
            score += 35; reasons.append("excellent docking")
        elif aff <= self.ref_aff - 1.0:
            score += 25; reasons.append("strong docking")
        elif aff <= self.ref_aff:
            score += 15; reasons.append("meets threshold")

        # Higgs sigma bonus
        z = c.get("z_score")
        if z is not None:
            if z >= 5.0:
                score += 20; reasons.append(f"{z:.1f}-sigma DISCOVERY")
            elif z >= 3.0:
                score += 12; reasons.append(f"{z:.1f}-sigma evidence")
            elif z >= 2.0:
                score += 6;  reasons.append(f"{z:.1f}-sigma candidate")

        # Ligand efficiency
        if c.get("LE", 0) >= 0.35:
            score += 20; reasons.append("good LE")

        # ADMET
        if c.get("admet_pass"):
            score += 25; reasons.append("ADMET pass")
        if c.get("hERG", 1.0) < 0.30:
            score += 10; reasons.append("hERG safe")
        if c.get("DILI", 1.0) < 0.30:
            score += 10; reasons.append("DILI safe")
        if c.get("MW", 999) <= 450:
            score += 5;  reasons.append("drug-sized")

        return score, reasons

    def _dip_score(self, c: dict) -> tuple[int, list]:
        """
        DIP / TIP-specific three-axis scoring.

        Axis 1 — Absolute integrase binding:
            How well does this compound bind HIV-1 integrase?
            (same as standard scoring vs ref_aff = -9.43)

        Axis 2 — Competitive advantage over WT HIV-1:
            Does it bind BETTER than Dolutegravir, i.e. better than
            what the wild-type virus integrase achieves?
            This is the core DIP requirement — the benign particle
            must crowd out the pathogenic one.

        Axis 3 — Host cell safety (CD4+ T-cell protection):
            Low hERG + low DILI + low MW = compound safe to express
            inside infected CD4+ T-cells via DIP genome.
        """
        aff     = c.get("dock_affinity", 0.0) or 0.0
        score   = 0
        reasons = []
        ref     = self.DIP_REFERENCE_AFFINITY  # -9.43

        # ── AXIS 1: Absolute integrase binding ────────────────────────
        if aff <= ref - 2.0:
            score += 30; reasons.append("excellent integrase binding")
        elif aff <= ref - 1.0:
            score += 22; reasons.append("strong integrase binding")
        elif aff <= ref:
            score += 12; reasons.append("matches DTG binding")
        elif aff <= ref + 1.0:
            score += 4;  reasons.append("near-threshold binding")
        # weaker than ref+1.0 → no binding points

        # ── AXIS 2: Competitive advantage (the DIP-unique axis) ───────
        comp_adv = ref - aff          # positive = better than DTG/WT HIV integrase
        c["dip_competitive_advantage"] = round(comp_adv, 3)

        if comp_adv >= self.DIP_TIER_STRONG:
            tier = "STRONG"
            score += 35
            reasons.append(f"STRONG DIP advantage (+{comp_adv:.2f} kcal/mol vs WT HIV)")
        elif comp_adv >= self.DIP_TIER_MODERATE:
            tier = "MODERATE"
            score += 22
            reasons.append(f"MODERATE DIP advantage (+{comp_adv:.2f} kcal/mol)")
        elif comp_adv >= self.DIP_TIER_MARGINAL:
            tier = "MARGINAL"
            score += 10
            reasons.append(f"MARGINAL DIP advantage ({comp_adv:.2f} kcal/mol — matches WT)")
        else:
            tier = "FAIL"
            score -= 15
            reasons.append(f"DIP FAIL — weaker than WT HIV integrase ({comp_adv:.2f})")

        c["dip_viable"]         = (comp_adv >= 0)
        c["dip_advantage_tier"] = tier

        # ── AXIS 3: CD4+ T-cell / host safety ────────────────────────
        herg   = c.get("hERG",  0.5)
        dili   = c.get("DILI",  0.5)
        ames   = c.get("AMES",  0.5)
        mw     = c.get("MW",    500)

        cd4_safe = (
            (herg  < 0.40) and   # low cardiac risk (expressed inside T-cells)
            (dili  < 0.40) and   # low liver toxicity
            (ames  < 0.40) and   # not mutagenic
            (mw    <= self.DIP_MW_CEILING)
        )
        c["dip_cd4_safe"] = cd4_safe

        if cd4_safe:
            score += 20
            reasons.append("CD4+ T-cell safe (hERG/DILI/AMES pass)")
        else:
            fails = []
            if herg >= 0.40:  fails.append(f"hERG {herg:.2f}")
            if dili >= 0.40:  fails.append(f"DILI {dili:.2f}")
            if ames >= 0.40:  fails.append(f"AMES {ames:.2f}")
            if mw > self.DIP_MW_CEILING: fails.append(f"MW {mw:.0f}>{self.DIP_MW_CEILING:.0f}")
            reasons.append(f"CD4 risk: {', '.join(fails)}")

        # ── Size efficiency (DIP genome encodes compact proteins) ──────
        if mw <= self.DIP_MW_IDEAL:
            score += 10; reasons.append(f"DIP-compact (MW={mw:.0f})")
        elif mw <= self.DIP_MW_CEILING:
            score += 5;  reasons.append(f"DIP-sized (MW={mw:.0f})")
        else:
            score -= 5;  reasons.append(f"DIP-oversized (MW={mw:.0f})")

        # ── DIP selectivity score (advantage per dalton) ──────────────
        dip_sel = round(comp_adv / max(mw, 1) * 1000, 4)  # kcal/mol per kDa
        c["dip_selectivity_score"] = dip_sel

        # ── Higgs sigma bonus (still applies) ─────────────────────────
        z = c.get("z_score")
        if z is not None:
            if z >= 5.0:
                score += 15; reasons.append(f"{z:.1f}σ DISCOVERY")
            elif z >= 3.0:
                score += 8;  reasons.append(f"{z:.1f}σ evidence")
            elif z >= 2.0:
                score += 3;  reasons.append(f"{z:.1f}σ candidate")

        # ── ADMET pass bonus (general safety) ─────────────────────────
        if c.get("admet_pass"):
            score += 10; reasons.append("ADMET pass")

        return score, reasons

    # ── Public interface ──────────────────────────────────────────────

    def validate(self, compounds: list) -> list:
        self.log.log("ValidatorAgent",
            f"Validating {len(compounds)} compounds "
            f"[{'DIP-MODE' if self.target_key == 'HIV_DIP' else 'STANDARD'}]...")

        is_dip = (self.target_key == "HIV_DIP")

        if is_dip:
            self.log.log("ValidatorAgent",
                f"  DIP reference: Dolutegravir {self.DIP_REFERENCE_AFFINITY} kcal/mol")
            self.log.log("ValidatorAgent",
                f"  Competitive advantage threshold: ≥ {self.DIP_TIER_STRONG:.1f} kcal/mol = STRONG")
            self.log.log("ValidatorAgent",
                f"  CD4+ safety: hERG<0.40, DILI<0.40, AMES<0.40, MW≤{self.DIP_MW_CEILING:.0f}")

        for c in compounds:
            smi = c.get("smiles", "")
            aff = c.get("dock_affinity", 0)

            # ── Compute physicochem properties if RDKit available ──────
            try:
                from rdkit import Chem
                from rdkit.Chem import Descriptors, Lipinski
                if smi:
                    mol = Chem.MolFromSmiles(smi)
                    if mol:
                        hac = mol.GetNumHeavyAtoms()
                        c["HAC"]  = hac
                        c["LE"]   = round(abs(aff) / hac, 3) if hac > 0 else 0
                        c["MW"]   = round(Descriptors.MolWt(mol), 1)
                        c["LogP"] = round(Descriptors.MolLogP(mol), 2)
            except ImportError:
                pass

            # ── Score ──────────────────────────────────────────────────
            if is_dip:
                score, reasons = self._dip_score(c)
            else:
                score, reasons = self._standard_score(c)

            c["confidence"] = min(max(score, 0), 100)
            c["reasons"]    = reasons

            # ── Log line ───────────────────────────────────────────────
            if score >= 75: grade = "*** EXCELLENT"
            elif score >= 55: grade = "OK  GOOD    "
            elif score >= 35: grade = "-   MODERATE"
            else:             grade = "XX  WEAK    "

            if is_dip:
                tier = c.get("dip_advantage_tier", "?")
                adv  = c.get("dip_competitive_advantage", "?")
                adv_s = f"{adv:+.2f}" if isinstance(adv, float) else str(adv)
                self.log.log("ValidatorAgent",
                    f"  {grade}  {c.get('id','?'):<14} "
                    f"aff={aff:.2f}  DIP={tier}({adv_s})  "
                    f"conf={c['confidence']}%  "
                    f"[{', '.join(reasons[:3])}]")
            else:
                self.log.log("ValidatorAgent",
                    f"  {grade}  {c.get('id','?'):<14}  "
                    f"aff={aff:.2f}  LE={c.get('LE','?')}  "
                    f"conf={c['confidence']}%  "
                    f"[{', '.join(reasons[:3])}]")

        compounds.sort(key=lambda x: -x.get("confidence", 0))

        # Summary for DIP mode
        if is_dip:
            strong   = sum(1 for c in compounds if c.get("dip_advantage_tier") == "STRONG")
            moderate = sum(1 for c in compounds if c.get("dip_advantage_tier") == "MODERATE")
            marginal = sum(1 for c in compounds if c.get("dip_advantage_tier") == "MARGINAL")
            fail     = sum(1 for c in compounds if c.get("dip_advantage_tier") == "FAIL")
            cd4_safe = sum(1 for c in compounds if c.get("dip_cd4_safe"))
            self.log.log("ValidatorAgent",
                f"  DIP summary: STRONG={strong} MODERATE={moderate} "
                f"MARGINAL={marginal} FAIL={fail} | CD4-safe={cd4_safe}")
            if strong > 0:
                best = next(c for c in compounds if c.get("dip_advantage_tier") == "STRONG")
                self.log.log("ValidatorAgent",
                    f"  *** TOP DIP CANDIDATE: {best.get('id')} "
                    f"advantage={best.get('dip_competitive_advantage'):+.3f} kcal/mol "
                    f"conf={best.get('confidence')}%")

        return compounds


# ══════════════════════════════════════════════════════════════════════
# 4.  dashboard.py additions
#     Paste HIV_DIP_DASHBOARD_ENTRY into DISEASE_DB in dashboard.py
#     Paste HIV_DIP_RECEPTOR_ENTRY into the `known` dict inside
#     _load_receptor_status() in dashboard.py
# ══════════════════════════════════════════════════════════════════════

HIV_DIP_DASHBOARD_ENTRY = {
    "HIV_DIP": {
        "disease":   "HIV/AIDS — Therapeutic Interfering Particle",
        "ref":       "Dolutegravir -9.43",
        "category":  "Infectious Disease",
        "mechanism": (
            "DIP integrase competitive binding — benign defective particle "
            "outcompetes pathogenic HIV-1 for D64/D116/E152 catalytic Mg²⁺ site. "
            "Based on Weinberger Lab TIP strategy (UCSF / OHSU, Science 2024)."
        ),
        "pdb":       "3L2T",
        "clinical":  "Experimental — TIP strategy (NHP 1,000-fold reduction 2024)",
    }
}

HIV_DIP_RECEPTOR_ENTRY = {
    "HIV_DIP": "hiv_integrase.pdbqt"
}

# ══════════════════════════════════════════════════════════════════════
# 5.  OrchestratorAgent._print_certificate() DIP addendum
#     Add this block inside _print_certificate() right after the main
#     certificate print, before self.log.separator("=")
# ══════════════════════════════════════════════════════════════════════

DIP_CERTIFICATE_ADDENDUM = '''
        # ── DIP addendum ──────────────────────────────────────────────
        if self.target_key == "HIV_DIP" and best:
            comp_adv  = best.get("dip_competitive_advantage", "N/A")
            tier      = best.get("dip_advantage_tier", "N/A")
            cd4_safe  = "YES" if best.get("dip_cd4_safe") else "NO"
            sel_score = best.get("dip_selectivity_score", "N/A")
            viable    = "VIABLE" if best.get("dip_viable") else "NOT VIABLE"
            adv_s = f"{comp_adv:+.3f}" if isinstance(comp_adv, float) else str(comp_adv)
            print(f"""
  +==============================================================+
  |  DIP / TIP COMPETITION CERTIFICATE                           |
  |  Therapeutic Interfering Particle Strategy                   |
  +==============================================================+
  |  Strategy  : Integrase competitive displacement              |
  |  Reference : Dolutegravir = -9.43 kcal/mol (WT HIV-1)       |
  +==============================================================+
  |  DIP Status     : {viable:<43}|
  |  Comp Advantage : {adv_s+" kcal/mol vs WT HIV-1":<43}|
  |  Advantage Tier : {tier:<43}|
  |  CD4+ T-cell    : {"Safe — expressed inside infected cells" if cd4_safe=="YES" else "Risk — check hERG/DILI":<43}|
  |  DIP Selectivity: {str(sel_score)+" kcal/mol per kDa":<43}|
  +==============================================================+
  |  Interpretation:                                             |
  |  A DIP particle carrying this integrase-binding moiety       |
  |  would outcompete wild-type HIV-1 for the D64/D116/E152     |
  |  catalytic site, stealing packaging machinery at the         |
  |  expense of pathogenic virus replication.                    |
  |                                                              |
  |  Based on: Pitchai et al. Science 385 eadn5866 (2024)        |
  |  Weinberger Lab UCSF / Haigwood Lab OHSU — 1000-fold NHP    |
  +==============================================================+
  Research use only. Computational predictions require           |
  experimental validation (cell culture → NHP → clinical).      |
  +==============================================================+
""")
'''


# ══════════════════════════════════════════════════════════════════════
# 6.  OrchestratorAgent.__init__() patch
#     The existing code already instantiates ValidatorAgent without
#     passing target_key. Change this line in run():
#
#   BEFORE:
#       valid_agent = ValidatorAgent(
#           self.log,
#           selectivity_targets = p.get("selectivity_targets",{}),
#           ref_affinity        = p["ref_affinity"],
#       )
#
#   AFTER (add target_key= kwarg):
#       valid_agent = ValidatorAgent(
#           self.log,
#           selectivity_targets = p.get("selectivity_targets",{}),
#           ref_affinity        = p["ref_affinity"],
#           target_key          = self.target_key,
#       )
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# 7.  AUTO-PATCHER  — python dip_patch.py
# ══════════════════════════════════════════════════════════════════════

def _auto_patch():
    import shutil, re, os

    agent_file     = "autonomous_drug_agent.py"
    dashboard_file = "dashboard.py"

    for fname in [agent_file, dashboard_file]:
        if not os.path.isfile(fname):
            print(f"[PATCH] WARNING: {fname} not found in CWD — skipping")

    # ── Patch autonomous_drug_agent.py ──────────────────────────────
    if os.path.isfile(agent_file):
        shutil.copy(agent_file, agent_file + ".bak")
        print(f"[PATCH] Backup: {agent_file}.bak")

        with open(agent_file, "r", encoding="utf-8") as f:
            src = f.read()

        # 1. Replace CANONICAL_CSV_COLUMNS block
        old_cols_pattern = re.compile(
            r'CANONICAL_CSV_COLUMNS\s*=\s*\[.*?\]',
            re.DOTALL
        )
        import inspect
        new_cols_src = (
            "CANONICAL_CSV_COLUMNS = [\n"
            + "".join(f'    "{c}",\n' for c in CANONICAL_CSV_COLUMNS)
            + "]"
        )
        if old_cols_pattern.search(src):
            src = old_cols_pattern.sub(new_cols_src, src, count=1)
            print("[PATCH] CANONICAL_CSV_COLUMNS replaced")
        else:
            print("[PATCH] WARNING: Could not locate CANONICAL_CSV_COLUMNS — manual merge needed")

        # 2. Replace _canonicalize_row function
        old_fn_pattern = re.compile(
            r'def _canonicalize_row\(.*?(?=\n^(?:def |class |\Z))',
            re.DOTALL | re.MULTILINE
        )
        new_fn_src = inspect.getsource(_canonicalize_row)
        if old_fn_pattern.search(src):
            src = old_fn_pattern.sub(new_fn_src + "\n\n", src, count=1)
            print("[PATCH] _canonicalize_row replaced")
        else:
            print("[PATCH] WARNING: Could not locate _canonicalize_row — manual merge needed")

        # 3. Replace ValidatorAgent class
        old_va_pattern = re.compile(
            r'class ValidatorAgent:.*?(?=\n^class |\Z)',
            re.DOTALL | re.MULTILINE
        )
        new_va_src = inspect.getsource(ValidatorAgent)
        if old_va_pattern.search(src):
            src = old_va_pattern.sub(new_va_src + "\n\n", src, count=1)
            print("[PATCH] ValidatorAgent replaced")
        else:
            print("[PATCH] WARNING: Could not locate ValidatorAgent — manual merge needed")

        # 4. Patch ValidatorAgent instantiation in run() to pass target_key
        old_vi = (
            "valid_agent = ValidatorAgent(\n"
            "            self.log,\n"
            "            selectivity_targets = p.get(\"selectivity_targets\",{}),\n"
            "            ref_affinity        = p[\"ref_affinity\"],\n"
            "        )"
        )
        new_vi = (
            "valid_agent = ValidatorAgent(\n"
            "            self.log,\n"
            "            selectivity_targets = p.get(\"selectivity_targets\",{}),\n"
            "            ref_affinity        = p[\"ref_affinity\"],\n"
            "            target_key          = self.target_key,\n"
            "        )"
        )
        if old_vi in src:
            src = src.replace(old_vi, new_vi, 1)
            print("[PATCH] ValidatorAgent instantiation patched (target_key added)")
        else:
            print("[PATCH] WARNING: ValidatorAgent instantiation pattern not matched — add target_key manually")

        with open(agent_file, "w", encoding="utf-8") as f:
            f.write(src)
        print(f"[PATCH] {agent_file} written")

    # ── Patch dashboard.py ───────────────────────────────────────────
    if os.path.isfile(dashboard_file):
        shutil.copy(dashboard_file, dashboard_file + ".bak")
        print(f"[PATCH] Backup: {dashboard_file}.bak")

        with open(dashboard_file, "r", encoding="utf-8") as f:
            dsrc = f.read()

        # 1. Add HIV_DIP to DISEASE_DB (after HIV_INTEGRASE entry)
        hiv_int_marker = '"HIV_INTEGRASE":'
        dip_entry_str = (
            '    "HIV_DIP": {\n'
            '        "disease":   "HIV/AIDS — Therapeutic Interfering Particle",\n'
            '        "ref":       "Dolutegravir -9.43",\n'
            '        "category":  "Infectious Disease",\n'
            '        "mechanism": "DIP integrase competitive binding — benign defective particle outcompetes pathogenic HIV-1 for D64/D116/E152 catalytic Mg²⁺ site.",\n'
            '        "pdb":       "3L2T",\n'
            '        "clinical":  "Experimental — TIP (Weinberger/Haigwood, Science 2024)",\n'
            '    },\n'
        )
        if '"HIV_DIP"' not in dsrc and hiv_int_marker in dsrc:
            # Find end of HIV_INTEGRASE block and insert after it
            idx = dsrc.find(hiv_int_marker)
            # Find the closing brace of this entry
            brace_end = dsrc.find('},', idx)
            if brace_end != -1:
                insert_pos = brace_end + 2
                dsrc = dsrc[:insert_pos] + "\n" + dip_entry_str + dsrc[insert_pos:]
                print("[PATCH] HIV_DIP added to DISEASE_DB in dashboard.py")
        elif '"HIV_DIP"' in dsrc:
            print("[PATCH] HIV_DIP already in DISEASE_DB — skipping")
        else:
            print("[PATCH] WARNING: Could not locate HIV_INTEGRASE in DISEASE_DB — add HIV_DIP manually")

        # 2. Add HIV_DIP to receptor status known dict
        known_marker = '"HIV_INTEGRASE":"hiv_integrase.pdbqt"'
        dip_rec = '"HIV_DIP":"hiv_integrase.pdbqt",'
        if dip_rec not in dsrc and known_marker in dsrc:
            dsrc = dsrc.replace(
                known_marker,
                known_marker + "\n        " + dip_rec
            )
            print("[PATCH] HIV_DIP receptor entry added to _load_receptor_status")
        elif dip_rec in dsrc:
            print("[PATCH] HIV_DIP receptor entry already present — skipping")
        else:
            print("[PATCH] WARNING: Could not locate HIV_INTEGRASE receptor entry — add manually")

        with open(dashboard_file, "w", encoding="utf-8") as f:
            f.write(dsrc)
        print(f"[PATCH] {dashboard_file} written")

    print("\n[PATCH] Done. Review .bak files if anything looks wrong.")
    print("[PATCH] Then run:  streamlit run dashboard.py")
    print("[PATCH] Select target: Infectious Disease > HIV_DIP")
    print("[PATCH] The leaderboard will show DIP advantage tiers instead of plain LE.")


if __name__ == "__main__":
    _auto_patch()
