"""
fix_remaining.py
================
Handles the two patches that dip_patch.py couldn't auto-apply:
  1. CANONICAL_CSV_COLUMNS  — insert 5 new DIP columns
  2. _canonicalize_row()    — insert DIP field mappings

Run from your project folder:
    python fix_remaining.py

Creates .bak2 backup before touching anything.
"""

import shutil, re, os, sys

AGENT_FILE = "autonomous_drug_agent.py"

if not os.path.isfile(AGENT_FILE):
    print(f"ERROR: {AGENT_FILE} not found in current directory.")
    print(f"  CWD: {os.getcwd()}")
    sys.exit(1)

shutil.copy(AGENT_FILE, AGENT_FILE + ".bak2")
print(f"[fix] Backup: {AGENT_FILE}.bak2")

with open(AGENT_FILE, "r", encoding="utf-8") as f:
    src = f.read()

# ══════════════════════════════════════════════════════════════════════
# PATCH 1 — CANONICAL_CSV_COLUMNS
# Strategy: find the list by looking for the "vdss" entry (always last
# PK field), then insert our 5 DIP columns right after it, before the
# "confidence" entry.
# ══════════════════════════════════════════════════════════════════════

DIP_COLUMNS_BLOCK = '''\
    # ── DIP / TIP fields ──────────────────────────────────────────────
    "dip_competitive_advantage",
    "dip_viable",
    "dip_advantage_tier",
    "dip_cd4_safe",
    "dip_selectivity_score",
'''

already_has_dip = '"dip_competitive_advantage"' in src

if already_has_dip:
    print("[fix] DIP columns already present in CANONICAL_CSV_COLUMNS — skipping patch 1")
else:
    # Find   "vdss",   and insert after it, before   # Validation
    # We look for a line containing "vdss", followed later by "# Validation"
    pattern = re.compile(
        r'("vdss",\s*\n)'          # group 1: the vdss line
        r'(\s*#\s*Validation)',     # group 2: the Validation comment
        re.MULTILINE
    )
    m = pattern.search(src)
    if m:
        replacement = m.group(1) + DIP_COLUMNS_BLOCK + m.group(2)
        src = src[:m.start()] + replacement + src[m.end():]
        print("[fix] CANONICAL_CSV_COLUMNS: DIP columns inserted after 'vdss'")
    else:
        # Fallback: look for the "confidence" line in the columns list
        pattern2 = re.compile(
            r'(\n\s*"confidence",\s*\n)',
            re.MULTILINE
        )
        m2 = pattern2.search(src)
        if m2:
            src = src[:m2.start()] + "\n" + DIP_COLUMNS_BLOCK + m2.group(1) + src[m2.end():]
            print("[fix] CANONICAL_CSV_COLUMNS: DIP columns inserted before 'confidence' (fallback)")
        else:
            print("[fix] WARNING: Could not auto-patch CANONICAL_CSV_COLUMNS.")
            print("       Add manually — see MANUAL_MERGE.txt")

# ══════════════════════════════════════════════════════════════════════
# PATCH 2 — _canonicalize_row(): insert DIP field mappings
# Strategy: find the line that writes row["confidence"] and insert
# the DIP block immediately before it.
# ══════════════════════════════════════════════════════════════════════

DIP_ROW_BLOCK = '''\
    # ── DIP / TIP fields (non-empty only for HIV_DIP target) ──────────
    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")
    row["dip_viable"] = (
        "true"  if c.get("dip_viable") else
        "false" if c.get("dip_competitive_advantage", "") != "" else ""
    )
    row["dip_advantage_tier"]    = c.get("dip_advantage_tier", "")
    row["dip_cd4_safe"]          = (
        "true"  if c.get("dip_cd4_safe") is True  else
        "false" if c.get("dip_cd4_safe") is False else ""
    )
    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")

'''

already_has_dip_row = '"dip_competitive_advantage"' in src and 'row["dip_competitive_advantage"]' in src

if already_has_dip_row:
    print("[fix] DIP row mappings already in _canonicalize_row — skipping patch 2")
else:
    # Find the confidence assignment inside _canonicalize_row
    # Look for the pattern:   row["confidence"] = c.get("confidence", "")
    pattern3 = re.compile(
        r'(\n)([ \t]+row\["confidence"\]\s*=\s*c\.get\("confidence")',
        re.MULTILINE
    )
    m3 = pattern3.search(src)
    if m3:
        insert_pos = m3.start(2)  # right before the confidence line
        src = src[:insert_pos] + DIP_ROW_BLOCK + src[insert_pos:]
        print("[fix] _canonicalize_row: DIP mappings inserted before row['confidence']")
    else:
        # Fallback: find row["reasons"] assignment
        pattern4 = re.compile(
            r'(\n)([ \t]+row\["reasons"\]\s*=)',
            re.MULTILINE
        )
        m4 = pattern4.search(src)
        if m4:
            insert_pos = m4.start(2)
            src = src[:insert_pos] + DIP_ROW_BLOCK + src[insert_pos:]
            print("[fix] _canonicalize_row: DIP mappings inserted before row['reasons'] (fallback)")
        else:
            print("[fix] WARNING: Could not auto-patch _canonicalize_row.")
            print("       Add manually — see MANUAL_MERGE.txt")

# ══════════════════════════════════════════════════════════════════════
# Write back
# ══════════════════════════════════════════════════════════════════════
with open(AGENT_FILE, "w", encoding="utf-8") as f:
    f.write(src)
print(f"[fix] {AGENT_FILE} written")

# ══════════════════════════════════════════════════════════════════════
# Quick verification
# ══════════════════════════════════════════════════════════════════════
checks = [
    ('"dip_competitive_advantage"',  "DIP column in CANONICAL_CSV_COLUMNS"),
    ('row["dip_competitive_advantage"]', "DIP mapping in _canonicalize_row"),
    ('dip_cd4_safe',                 "CD4 safety field present"),
    ('dip_advantage_tier',           "Advantage tier field present"),
    ('target_key',                   "ValidatorAgent target_key param"),
]

print()
print("[fix] Verification:")
all_ok = True
with open(AGENT_FILE, "r", encoding="utf-8") as f:
    final = f.read()
for needle, label in checks:
    found = needle in final
    status = "OK " if found else "MISSING"
    if not found:
        all_ok = False
    print(f"  [{status}] {label}")

if all_ok:
    print()
    print("[fix] All checks passed.")
    print("[fix] You're ready:  streamlit run dashboard.py")
    print("[fix] Select:  Infectious Disease > HIV_DIP")
else:
    print()
    print("[fix] Some items missing — check MANUAL_MERGE.txt for instructions.")
    # Write manual merge guide
    with open("MANUAL_MERGE.txt", "w") as f:
        f.write("""MANUAL MERGE GUIDE — dip_patch remaining items
================================================

1. CANONICAL_CSV_COLUMNS
   In autonomous_drug_agent.py, find the CANONICAL_CSV_COLUMNS list.
   After the "vdss" entry and before the "# Validation" comment, add:

    # ── DIP / TIP fields ────────────────────────────────────────
    "dip_competitive_advantage",
    "dip_viable",
    "dip_advantage_tier",
    "dip_cd4_safe",
    "dip_selectivity_score",


2. _canonicalize_row()
   In the same file, inside _canonicalize_row(), find:

       row["confidence"] = c.get("confidence", "")

   Insert this block ABOVE it:

    # ── DIP / TIP fields ────────────────────────────────────────
    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")
    row["dip_viable"] = (
        "true"  if c.get("dip_viable") else
        "false" if c.get("dip_competitive_advantage", "") != "" else ""
    )
    row["dip_advantage_tier"]    = c.get("dip_advantage_tier", "")
    row["dip_cd4_safe"]          = (
        "true"  if c.get("dip_cd4_safe") is True  else
        "false" if c.get("dip_cd4_safe") is False else ""
    )
    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")


Both changes are purely additive — nothing is removed.
""")
    print("[fix] MANUAL_MERGE.txt written to current directory.")
