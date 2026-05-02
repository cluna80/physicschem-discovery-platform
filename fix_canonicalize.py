"""
fix_canonicalize.py
===================
Final targeted fix: inserts DIP field mappings into _canonicalize_row().
Run from your project folder:
    python fix_canonicalize.py
"""

import shutil, re, os, sys

AGENT_FILE = "autonomous_drug_agent.py"

if not os.path.isfile(AGENT_FILE):
    print(f"ERROR: {AGENT_FILE} not found. CWD: {os.getcwd()}")
    sys.exit(1)

shutil.copy(AGENT_FILE, AGENT_FILE + ".bak3")
print(f"[fix] Backup: {AGENT_FILE}.bak3")

with open(AGENT_FILE, "r", encoding="utf-8") as f:
    src = f.read()

# Already done?
if 'row["dip_competitive_advantage"]' in src:
    print("[fix] DIP mappings already present in _canonicalize_row -- nothing to do.")
    print("[fix] You are fully patched. Run:  streamlit run dashboard.py")
    sys.exit(0)

DIP_BLOCK = (
    '    # -- DIP / TIP fields (non-empty only for HIV_DIP target) --\n'
    '    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")\n'
    '    row["dip_viable"] = (\n'
    '        "true"  if c.get("dip_viable") else\n'
    '        "false" if c.get("dip_competitive_advantage", "") != "" else ""\n'
    '    )\n'
    '    row["dip_advantage_tier"]    = c.get("dip_advantage_tier", "")\n'
    '    row["dip_cd4_safe"] = (\n'
    '        "true"  if c.get("dip_cd4_safe") is True  else\n'
    '        "false" if c.get("dip_cd4_safe") is False else ""\n'
    '    )\n'
    '    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")\n'
    '\n'
)

# Strategy: scan line by line inside _canonicalize_row for the
# validation section or the return statement, insert before it.
# This is more robust than regex on indented blocks.

lines = src.splitlines(keepends=True)

# Find _canonicalize_row function start
fn_start = None
for i, line in enumerate(lines):
    if 'def _canonicalize_row(' in line:
        fn_start = i
        break

if fn_start is None:
    print("[fix] ERROR: _canonicalize_row not found in file.")
    print("[fix] Please add the DIP block manually - see instructions below.")
    _print_manual()
    sys.exit(1)

print(f"[fix] Found _canonicalize_row at line {fn_start + 1}")

# Find insertion point: first line containing row["confidence"] or
# row["reasons"] inside the function, or the return statement.
insert_at = None
search_targets = [
    'row["confidence"]',
    "row['confidence']",
    'row["reasons"]',
    "row['reasons']",
    '    return row',
]

for i in range(fn_start + 1, len(lines)):
    stripped = lines[i].strip()
    # Stop if we've left the function (next def/class at col 0)
    if i > fn_start + 1 and (lines[i].startswith('def ') or lines[i].startswith('class ')):
        break
    for target in search_targets:
        if target in lines[i]:
            insert_at = i
            print(f"[fix] Insertion point: line {i + 1}  ({lines[i].rstrip()})")
            break
    if insert_at is not None:
        break

if insert_at is None:
    print("[fix] ERROR: Could not find insertion point inside _canonicalize_row.")
    _print_manual()
    sys.exit(1)

# Insert the block
lines.insert(insert_at, DIP_BLOCK)
new_src = ''.join(lines)

with open(AGENT_FILE, "w", encoding="utf-8") as f:
    f.write(new_src)
print(f"[fix] {AGENT_FILE} written")

# Verify
checks = [
    ('"dip_competitive_advantage"',      "DIP column in CANONICAL_CSV_COLUMNS"),
    ('row["dip_competitive_advantage"]', "DIP mapping in _canonicalize_row"),
    ('dip_cd4_safe',                     "CD4 safety field"),
    ('dip_advantage_tier',               "Advantage tier field"),
    ('target_key',                       "ValidatorAgent target_key param"),
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

print()
if all_ok:
    print("[fix] ALL CHECKS PASSED.")
    print("[fix] Run:  streamlit run dashboard.py")
    print("[fix] Then: Infectious Disease > HIV_DIP")
else:
    print("[fix] One item still missing. Manual steps:")
    print()
    print("  In autonomous_drug_agent.py, find _canonicalize_row().")
    print("  Locate the line:  row[\"confidence\"] = c.get(\"confidence\", \"\")")
    print("  Insert this block ABOVE it:")
    print()
    print('    row["dip_competitive_advantage"] = c.get("dip_competitive_advantage", "")')
    print('    row["dip_viable"] = (')
    print('        "true"  if c.get("dip_viable") else')
    print('        "false" if c.get("dip_competitive_advantage", "") != "" else ""')
    print('    )')
    print('    row["dip_advantage_tier"]    = c.get("dip_advantage_tier", "")')
    print('    row["dip_cd4_safe"] = (')
    print('        "true"  if c.get("dip_cd4_safe") is True  else')
    print('        "false" if c.get("dip_cd4_safe") is False else ""')
    print('    )')
    print('    row["dip_selectivity_score"] = c.get("dip_selectivity_score", "")')
