"""
final_fix.py
============
Inserts CANONICAL_CSV_COLUMNS and _canonicalize_row() back into
autonomous_drug_agent.py at the exact correct position.

The scan confirmed these were removed during the first patch run.
ValidatorAgent and all DIP scoring logic is already present and correct.

Run:
    python final_fix.py
"""

import shutil, os, sys

AGENT_FILE = "autonomous_drug_agent.py"

if not os.path.isfile(AGENT_FILE):
    print(f"ERROR: {AGENT_FILE} not found. CWD: {os.getcwd()}")
    sys.exit(1)

shutil.copy(AGENT_FILE, AGENT_FILE + ".bak4")
print(f"[fix] Backup: {AGENT_FILE}.bak4")

with open(AGENT_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"[fix] File loaded: {len(lines)} lines")

# ── Verify nothing already there ──────────────────────────────────────
already_cols = any("CANONICAL_CSV_COLUMNS" in l for l in lines)
already_fn   = any("def _canonicalize_row" in l for l in lines)

if already_cols and already_fn:
    print("[fix] Both CANONICAL_CSV_COLUMNS and _canonicalize_row already present.")
    print("[fix] Nothing to do. Run:  streamlit run dashboard.py")
    sys.exit(0)

# ── Find insertion point ───────────────────────────────────────────────
# Insert just before class AgentLogger (confirmed at L648 by scanner).
# We search by content to be position-independent.
insert_before = None
for i, line in enumerate(lines):
    if line.strip().startswith("class AgentLogger"):
        insert_before = i
        break

if insert_before is None:
    # Fallback: insert before generate_novel_fragments
    for i, line in enumerate(lines):
        if "def generate_novel_fragments" in line:
            insert_before = i
            break

if insert_before is None:
    print("[fix] ERROR: Could not find insertion anchor (AgentLogger or generate_novel_fragments).")
    print("[fix] Please paste the block from MANUAL_MERGE_FINAL.txt manually.")
else:
    print(f"[fix] Insertion point: line {insert_before + 1}  ({lines[insert_before].rstrip()})")

# ── The block to insert ────────────────────────────────────────────────
INSERT_BLOCK = '''
# ======================================================================
# STAGE 2: Canonical CSV schema
# ======================================================================

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
    # ADMET -- core
    "admet_pass", "hERG", "DILI", "AMES", "ClinTox",
    "bioavailability", "solubility", "hia",
    # ADMET -- CYP450
    "cyp3a4_inh", "cyp2d6_inh", "cyp2c9_inh", "cyp2c19_inh", "cyp1a2_inh",
    "cyp3a4_sub", "cyp2d6_sub", "cyp2c9_sub",
    "cyp_safe", "cyp_warning",
    # ADMET -- PK
    "half_life", "clearance_hep", "ppbr", "vdss",
    # DIP / TIP fields
    "dip_competitive_advantage",
    "dip_viable",
    "dip_advantage_tier",
    "dip_cd4_safe",
    "dip_selectivity_score",
    # Validation
    "confidence", "reasons",
    # Context
    "target", "reference_drug", "reference_affinity", "run_id", "timestamp",
]


def _canonicalize_row(c: dict, *, target: str, ref_drug: str,
                      ref_aff: float, run_id: str,
                      timestamp: str) -> dict:
    """Map an agent-internal candidate dict to the canonical schema."""
    row = {col: "" for col in CANONICAL_CSV_COLUMNS}

    # Identity
    row["id"]     = c.get("id", "")
    row["smiles"] = c.get("smiles", "")
    row["name"]   = c.get("name", "")
    row["parent"] = c.get("parent", "")

    # Docking
    row["dock_affinity"] = c.get("dock_affinity", "")
    row["n_poses"]       = c.get("dock_poses", "")

    # Physicochem (translate legacy mixed-case keys)
    row["mw"]   = c.get("MW",   c.get("mw",   ""))
    row["logp"] = c.get("LogP", c.get("logp", ""))
    row["hac"]  = c.get("HAC",  c.get("hac",  ""))
    row["le"]   = c.get("LE",   c.get("le",   ""))

    # Higgs significance
    row["z_score"]      = c.get("z_score", "")
    row["sigma_label"]  = c.get("sigma_label", "-")
    row["sigma_status"] = c.get("sigma_status", "")
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

    # DIP / TIP fields
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
    row["reasons"]    = "|".join(c.get("reasons", []))

    # Context
    row["target"]             = target
    row["reference_drug"]     = ref_drug or ""
    row["reference_affinity"] = ref_aff if ref_aff is not None else ""
    row["run_id"]             = run_id
    row["timestamp"]          = timestamp

    return row

'''

# ── Apply ─────────────────────────────────────────────────────────────
if insert_before is not None:
    lines.insert(insert_before, INSERT_BLOCK)
    with open(AGENT_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"[fix] Block inserted. {AGENT_FILE} written ({len(lines)} lines)")
else:
    # Write manual merge file as fallback
    with open("MANUAL_MERGE_FINAL.txt", "w", encoding="utf-8") as f:
        f.write("Paste the following block into autonomous_drug_agent.py\n")
        f.write("just before the line:  class AgentLogger:\n\n")
        f.write(INSERT_BLOCK)
    print("[fix] MANUAL_MERGE_FINAL.txt written — paste its contents before class AgentLogger")

# ── Verify ────────────────────────────────────────────────────────────
checks = [
    ("CANONICAL_CSV_COLUMNS",            "CANONICAL_CSV_COLUMNS defined"),
    ("def _canonicalize_row(",           "_canonicalize_row defined"),
    ('"dip_competitive_advantage"',      "DIP column in schema"),
    ('row["dip_competitive_advantage"]', "DIP mapping in _canonicalize_row"),
    ("dip_cd4_safe",                     "CD4 safety field"),
    ("dip_advantage_tier",               "Advantage tier field"),
    ("target_key",                       "ValidatorAgent target_key param"),
    ("_dip_score",                       "DIP scoring method"),
    ("_save_results",                    "_save_results present"),
]

print()
print("[fix] Verification:")
with open(AGENT_FILE, "r", encoding="utf-8") as f:
    final = f.read()

all_ok = True
for needle, label in checks:
    found = needle in final
    status = "OK " if found else "MISSING"
    if not found:
        all_ok = False
    print(f"  [{status}] {label}")

print()
if all_ok:
    print("[fix] ALL CHECKS PASSED - you are fully patched.")
    print()
    print("[fix] Run:  streamlit run dashboard.py")
    print("[fix] Then select:  Infectious Disease > HIV_DIP")
else:
    print("[fix] Something still missing.")
    print("[fix] Check MANUAL_MERGE_FINAL.txt for copy-paste instructions.")
