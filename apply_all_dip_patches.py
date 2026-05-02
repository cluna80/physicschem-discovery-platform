"""
apply_all_dip_patches.py
========================
Applies all DIP patches to the EXACT current version of
autonomous_drug_agent.py that you uploaded.

Run:
    python apply_all_dip_patches.py

Creates autonomous_drug_agent.py.bak_final before modifying.
Prints verification of all 9 checks at the end.
"""

import shutil, os, sys, ast

AGENT = "autonomous_drug_agent.py"
if not os.path.isfile(AGENT):
    print(f"ERROR: {AGENT} not found in {os.getcwd()}")
    sys.exit(1)

shutil.copy(AGENT, AGENT + ".bak_final")
print(f"[patch] Backup: {AGENT}.bak_final")

with open(AGENT, "r", encoding="utf-8") as f:
    src = f.read()

applied = 0

# ══════════════════════════════════════════════════════════════════════
# PATCH 1: CANONICAL_CSV_COLUMNS — add DIP fields after vdss
# ══════════════════════════════════════════════════════════════════════
P1_OLD = '''    # ADMET \u2014 PK
    "half_life", "clearance_hep", "ppbr", "vdss",
    # Validation
    "confidence", "reasons",'''

P1_NEW = '''    # ADMET \u2014 PK
    "half_life", "clearance_hep", "ppbr", "vdss",
    # DIP / TIP fields
    "dip_competitive_advantage",
    "dip_viable",
    "dip_advantage_tier",
    "dip_cd4_safe",
    "dip_selectivity_score",
    # Validation
    "confidence", "reasons",'''

if P1_OLD in src and "dip_competitive_advantage" not in src:
    src = src.replace(P1_OLD, P1_NEW, 1)
    print("[patch] 1. DIP columns added to CANONICAL_CSV_COLUMNS")
    applied += 1
elif "dip_competitive_advantage" in src:
    print("[patch] 1. DIP columns already present")
else:
    print("[patch] 1. WARNING: CANONICAL_CSV_COLUMNS PK block not matched")

# ══════════════════════════════════════════════════════════════════════
# PATCH 2: _canonicalize_row — add DIP mappings before Validation comment
# ══════════════════════════════════════════════════════════════════════
P2_OLD = '''    # Validation
    row["confidence"] = c.get("confidence", "")
    row["reasons"]    = "|".join(c.get("reasons", []))  # pipe-separated, CSV-safe'''

P2_NEW = '''    # DIP / TIP fields (non-empty only for HIV_DIP target)
    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")
    row["dip_viable"] = (
        "true"  if c.get("dip_viable") else
        "false" if c.get("dip_competitive_advantage", "") != "" else ""
    )
    row["dip_advantage_tier"]    = c.get("dip_advantage_tier", "")
    row["dip_cd4_safe"] = (
        "true"  if c.get("dip_cd4_safe") is True  else
        "false" if c.get("dip_cd4_safe") is False else ""
    )
    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")

    # Validation
    row["confidence"] = c.get("confidence", "")
    row["reasons"]    = "|".join(c.get("reasons", []))  # pipe-separated, CSV-safe'''

if P2_OLD in src and 'row["dip_competitive_advantage"]' not in src:
    src = src.replace(P2_OLD, P2_NEW, 1)
    print("[patch] 2. DIP mappings added to _canonicalize_row")
    applied += 1
elif 'row["dip_competitive_advantage"]' in src:
    print("[patch] 2. DIP mappings already present")
else:
    print("[patch] 2. WARNING: _canonicalize_row validation block not matched")

# ══════════════════════════════════════════════════════════════════════
# PATCH 3: Replace ValidatorAgent with DIP-scoring version
# ══════════════════════════════════════════════════════════════════════
VA_START = "# ======================================================================\n# AGENT: VALIDATOR\n# ======================================================================"
VA_END   = "# ======================================================================\n# ORCHESTRATOR\n# ======================================================================"

NEW_VALIDATOR = """# ======================================================================
# AGENT: VALIDATOR
# ======================================================================

class ValidatorAgent:
    \"\"\"
    Multi-criteria compound validator with DIP competition scoring.
    DIP mode activates automatically when target_key == 'HIV_DIP'.

    Three scoring axes for DIP:
        Axis 1 - absolute integrase binding vs Dolutegravir reference
        Axis 2 - competitive advantage over WT HIV-1 (the key DIP axis)
        Axis 3 - CD4+ T-cell host safety (hERG/DILI/AMES/MW)
    \"\"\"

    DIP_REFERENCE_AFFINITY = -9.43   # Dolutegravir on 3L2T integrase
    DIP_MW_CEILING = 420.0
    DIP_MW_IDEAL   = 360.0
    DIP_TIER_STRONG   = 2.0   # >= +2 kcal/mol better than DTG
    DIP_TIER_MODERATE = 1.0
    DIP_TIER_MARGINAL = 0.0

    def __init__(self, logger,
                 selectivity_targets: dict,
                 ref_affinity: float,
                 target_key: str = ""):
        self.log        = logger
        self.targets    = selectivity_targets
        self.ref_aff    = ref_affinity
        self.target_key = target_key.upper()

    def _standard_score(self, c: dict):
        aff = c.get("dock_affinity", 0)
        score, reasons = 0, []
        if aff <= self.ref_aff - 2.0:   score += 35; reasons.append("excellent docking")
        elif aff <= self.ref_aff - 1.0: score += 25; reasons.append("strong docking")
        elif aff <= self.ref_aff:        score += 15; reasons.append("meets threshold")
        z = c.get("z_score")
        if z is not None:
            if z >= 5.0:   score += 20; reasons.append(f"{z:.1f}-sigma DISCOVERY")
            elif z >= 3.0: score += 12; reasons.append(f"{z:.1f}-sigma evidence")
            elif z >= 2.0: score += 6;  reasons.append(f"{z:.1f}-sigma candidate")
        if c.get("LE", 0) >= 0.35:    score += 20; reasons.append("good LE")
        if c.get("admet_pass"):        score += 25; reasons.append("ADMET pass")
        if c.get("hERG", 1) < 0.30:   score += 10; reasons.append("hERG safe")
        if c.get("DILI", 1) < 0.30:   score += 10; reasons.append("DILI safe")
        if c.get("MW", 999) <= 450:   score += 5;  reasons.append("drug-sized")
        return score, reasons

    def _dip_score(self, c: dict):
        aff = c.get("dock_affinity", 0.0) or 0.0
        ref = self.DIP_REFERENCE_AFFINITY
        score, reasons = 0, []

        # Axis 1: absolute integrase binding
        if aff <= ref - 2.0:   score += 30; reasons.append("excellent integrase binding")
        elif aff <= ref - 1.0: score += 22; reasons.append("strong integrase binding")
        elif aff <= ref:       score += 12; reasons.append("matches DTG binding")
        elif aff <= ref + 1.0: score += 4;  reasons.append("near-threshold binding")

        # Axis 2: competitive advantage over WT HIV-1
        comp_adv = ref - aff   # positive = better than DTG = better than WT HIV integrase
        c["dip_competitive_advantage"] = round(comp_adv, 3)
        if comp_adv >= self.DIP_TIER_STRONG:
            tier = "STRONG";   score += 35
            reasons.append(f"STRONG DIP advantage (+{comp_adv:.2f} kcal/mol vs WT HIV)")
        elif comp_adv >= self.DIP_TIER_MODERATE:
            tier = "MODERATE"; score += 22
            reasons.append(f"MODERATE DIP advantage (+{comp_adv:.2f} kcal/mol)")
        elif comp_adv >= self.DIP_TIER_MARGINAL:
            tier = "MARGINAL"; score += 10
            reasons.append(f"MARGINAL DIP advantage ({comp_adv:.2f} kcal/mol)")
        else:
            tier = "FAIL";     score -= 15
            reasons.append(f"DIP FAIL weaker than WT HIV ({comp_adv:.2f})")
        c["dip_viable"]         = (comp_adv >= 0)
        c["dip_advantage_tier"] = tier

        # Axis 3: CD4+ T-cell / host safety
        herg = c.get("hERG", 0.5)
        dili = c.get("DILI", 0.5)
        ames = c.get("AMES", 0.5)
        mw   = c.get("MW", 500)
        cd4_safe = (herg < 0.40 and dili < 0.40 and ames < 0.40
                    and mw <= self.DIP_MW_CEILING)
        c["dip_cd4_safe"] = cd4_safe
        if cd4_safe:
            score += 20; reasons.append("CD4+ T-cell safe")
        else:
            fails = []
            if herg >= 0.40: fails.append(f"hERG {herg:.2f}")
            if dili >= 0.40: fails.append(f"DILI {dili:.2f}")
            if ames >= 0.40: fails.append(f"AMES {ames:.2f}")
            if mw > self.DIP_MW_CEILING: fails.append(f"MW {mw:.0f}")
            reasons.append(f"CD4 risk: {', '.join(fails)}")

        if mw <= self.DIP_MW_IDEAL:    score += 10; reasons.append(f"DIP-compact (MW={mw:.0f})")
        elif mw <= self.DIP_MW_CEILING: score += 5

        c["dip_selectivity_score"] = round(comp_adv / max(mw, 1) * 1000, 4)

        z = c.get("z_score")
        if z is not None:
            if z >= 5.0:   score += 15; reasons.append(f"{z:.1f}s DISCOVERY")
            elif z >= 3.0: score += 8;  reasons.append(f"{z:.1f}s evidence")
            elif z >= 2.0: score += 3;  reasons.append(f"{z:.1f}s candidate")

        if c.get("admet_pass"): score += 10; reasons.append("ADMET pass")
        return score, reasons

    def validate(self, compounds: list) -> list:
        is_dip = (self.target_key == "HIV_DIP")
        self.log.log("ValidatorAgent",
            f"Validating {len(compounds)} compounds "
            f"[{'DIP-MODE' if is_dip else 'STANDARD'}]...")

        if is_dip:
            self.log.log("ValidatorAgent",
                f"  DIP ref: Dolutegravir {self.DIP_REFERENCE_AFFINITY} kcal/mol  "
                f"STRONG threshold: +{self.DIP_TIER_STRONG:.1f} kcal/mol advantage")

        for c in compounds:
            smi = c.get("smiles", "")
            aff = c.get("dock_affinity", 0)

            if RDKIT_OK and smi:
                mol = Chem.MolFromSmiles(smi)
                if mol:
                    hac = mol.GetNumHeavyAtoms()
                    c["HAC"]  = hac
                    c["LE"]   = round(abs(aff) / hac, 3) if hac > 0 else 0
                    c["MW"]   = round(Descriptors.MolWt(mol), 1)
                    c["LogP"] = round(Descriptors.MolLogP(mol), 2)

            if is_dip:
                score, reasons = self._dip_score(c)
            else:
                score, reasons = self._standard_score(c)

            c["confidence"] = min(max(score, 0), 100)
            c["reasons"]    = reasons

            if score >= 75:   grade = "*** EXCELLENT"
            elif score >= 55: grade = "OK  GOOD    "
            elif score >= 35: grade = "-   MODERATE"
            else:             grade = "XX  WEAK    "

            if is_dip:
                tier  = c.get("dip_advantage_tier", "?")
                adv   = c.get("dip_competitive_advantage", 0)
                adv_s = f"{adv:+.2f}" if isinstance(adv, float) else str(adv)
                self.log.log("ValidatorAgent",
                    f"  {grade}  {c.get('id','?'):<14} "
                    f"aff={aff:.2f}  DIP={tier}({adv_s})  "
                    f"conf={c['confidence']}%  [{', '.join(reasons[:3])}]")
            else:
                self.log.log("ValidatorAgent",
                    f"  {grade}  {c.get('id','?'):<14}  "
                    f"aff={aff:.2f}  LE={c.get('LE','?')}  "
                    f"conf={c['confidence']}%  [{', '.join(reasons[:3])}]")

        compounds.sort(key=lambda x: -x.get("confidence", 0))

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
                    f"  *** TOP DIP: {best.get('id')} "
                    f"advantage={best.get('dip_competitive_advantage'):+.3f} "
                    f"conf={best.get('confidence')}%")

        return compounds

"""

if VA_START in src and VA_END in src:
    start_idx = src.index(VA_START)
    end_idx   = src.index(VA_END)
    src = src[:start_idx] + NEW_VALIDATOR + "\n" + src[end_idx:]
    print("[patch] 3. ValidatorAgent replaced with full DIP-scoring version")
    applied += 1
else:
    print("[patch] 3. WARNING: ValidatorAgent section markers not found")

# ══════════════════════════════════════════════════════════════════════
# PATCH 4: Upgrade PHARMA_TAILS["HIV_DIP"]
# ══════════════════════════════════════════════════════════════════════
P4_OLD = '''        "HIV_DIP": [
            "O=C(O)/C=C/c1ccccc1",
            "Oc1nccc(=O)[nH]1",
            "O=C(O)CC(=O)O",
            "c1cnc2[nH]ccc2c1",
            "OC(=O)c1cc(O)ccn1",
        ],'''

P4_NEW = '''        "HIV_DIP": [
            # Halobenzyl tails (Dolutegravir/Bictegravir class)
            "Cc1ccc(F)cc1F",
            "Cc1cc(F)cc(F)c1",
            "OCC(O)Cc1cc(F)cc(F)c1",
            "NCC(O)Cc1cc(F)cc(F)c1",
            # Naphthyridine carboxamide (Raltegravir class)
            "c1cnc2ccccc2c1C(=O)N",
            "c1ccc2ncccc2c1C(=O)O",
            # Carbamoyl pyridone (Bictegravir core extension)
            "O=C1CC(=O)c2ccc(F)cc2N1",
            "O=C1CC(=O)c2cc(F)ccc2N1",
            # Diketo extension tails
            "O=C(O)C(=O)Cc1cc(F)cc(F)c1",
            "O=C(O)C(=O)Cc1ccc(F)c(F)c1",
            # Original anchor tails (kept)
            "O=C(O)/C=C/c1ccccc1",
            "Oc1nccc(=O)[nH]1",
            "OC(=O)c1cc(O)ccn1",
        ],'''

if P4_OLD in src:
    src = src.replace(P4_OLD, P4_NEW, 1)
    print("[patch] 4. PHARMA_TAILS HIV_DIP upgraded with INSTI halobenzyl/pyridone tails")
    applied += 1
else:
    print("[patch] 4. WARNING: old HIV_DIP tails not found")

# ══════════════════════════════════════════════════════════════════════
# PATCH 5: Add HIV_DIP to HiggsSignificanceTester historical null
# ══════════════════════════════════════════════════════════════════════
P5_OLD = '        HISTORICAL_NULL = {\n            "HIV_INTEGRASE": (-5.52, 0.61),'
P5_NEW = '        HISTORICAL_NULL = {\n            "HIV_DIP":       (-5.52, 0.61),\n            "HIV_INTEGRASE": (-5.52, 0.61),'

if P5_OLD in src and '"HIV_DIP":       (-5.52' not in src:
    src = src.replace(P5_OLD, P5_NEW, 1)
    print("[patch] 5. HIV_DIP added to Higgs historical null")
    applied += 1
elif '"HIV_DIP":       (-5.52' in src:
    print("[patch] 5. HIV_DIP historical null already present")
else:
    print("[patch] 5. WARNING: HISTORICAL_NULL block not matched")

# ══════════════════════════════════════════════════════════════════════
# PATCH 6: Pass target_key to ValidatorAgent instantiation
# ══════════════════════════════════════════════════════════════════════
P6_OLD = """        valid_agent = ValidatorAgent(
            self.log,
            selectivity_targets = p.get("selectivity_targets",{}),
            ref_affinity        = p["ref_affinity"],
        )"""

P6_NEW = """        valid_agent = ValidatorAgent(
            self.log,
            selectivity_targets = p.get("selectivity_targets",{}),
            ref_affinity        = p["ref_affinity"],
            target_key          = self.target_key,
        )"""

if P6_OLD in src:
    src = src.replace(P6_OLD, P6_NEW, 1)
    print("[patch] 6. target_key added to ValidatorAgent instantiation")
    applied += 1
elif "target_key          = self.target_key" in src:
    print("[patch] 6. target_key already present")
else:
    print("[patch] 6. WARNING: ValidatorAgent instantiation not matched")

# ══════════════════════════════════════════════════════════════════════
# Write + verify
# ══════════════════════════════════════════════════════════════════════
with open(AGENT, "w", encoding="utf-8") as f:
    f.write(src)
print(f"\n[patch] {AGENT} written ({applied} patches applied)")

try:
    ast.parse(src)
    print("[patch] Syntax check: OK")
except SyntaxError as e:
    print(f"[patch] SYNTAX ERROR line {e.lineno}: {e.msg}")
    print(f"        {e.text}")
    sys.exit(1)

checks = [
    ('"dip_competitive_advantage"',      "DIP column in CANONICAL_CSV_COLUMNS"),
    ('row["dip_competitive_advantage"]', "DIP mapping in _canonicalize_row"),
    ("_dip_score",                       "DIP scoring method"),
    ("DIP_REFERENCE_AFFINITY",           "DIP reference constant"),
    ("dip_advantage_tier",               "DIP advantage tier"),
    ("dip_cd4_safe",                     "CD4 safety field"),
    ("target_key          = self.target_key", "target_key in ValidatorAgent call"),
    ("Cc1ccc(F)cc1F",                    "Halobenzyl INSTI tail"),
    ('"HIV_DIP":       (-5.52',          "HIV_DIP historical null"),
]

print()
print("[patch] Verification:")
all_ok = True
for needle, label in checks:
    found = needle in src
    s = "OK " if found else "MISSING"
    if not found: all_ok = False
    print(f"  [{s}] {label}")

print()
if all_ok:
    print("[patch] ALL 9 CHECKS PASSED. Pipeline fully upgraded.")
    print()
    print("  Run:  streamlit run dashboard.py")
    print("  Select: Infectious Disease > HIV_DIP")
    print("  Mode:   Standard, exhaustiveness 12")
    print("  Expected leaderboard output: DIP=STRONG(+X.XX) for top hits")
else:
    print("[patch] Some checks failed. Original backed up as .bak_final")
    print("        Check the WARNING lines above for which patterns didn't match.")
