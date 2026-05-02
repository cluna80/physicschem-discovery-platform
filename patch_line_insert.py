"""
patch_line_insert.py
====================
Finds HIV_DIP tails and HISTORICAL_NULL by scanning line by line,
prints what it finds, then inserts directly.

Run:
    python patch_line_insert.py
"""
import shutil, os, sys, ast

AGENT = "autonomous_drug_agent.py"
if not os.path.isfile(AGENT):
    print(f"ERROR: {AGENT} not found"); sys.exit(1)

shutil.copy(AGENT, AGENT + ".bak_li")

with open(AGENT, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"[scan] File: {len(lines)} lines")

# ── Find HIV_DIP tails block ──────────────────────────────────────────
dip_start = dip_end = -1
for i, line in enumerate(lines):
    if '"HIV_DIP"' in line and '[' in line and 'PHARMA' not in line:
        # Make sure we're inside PHARMA_TAILS (look for context)
        # Check 10 lines back for PHARMA_TAILS
        context = ''.join(lines[max(0,i-20):i])
        if 'PHARMA_TAILS' in context or 'EGFR' in ''.join(lines[i:i+30]):
            dip_start = i
            print(f"[scan] HIV_DIP tails start: L{i+1}: {line.rstrip()}")
            break

if dip_start >= 0:
    # Find closing ], after dip_start
    depth = 0
    for i in range(dip_start, min(dip_start+30, len(lines))):
        depth += lines[i].count('[') - lines[i].count(']')
        if depth <= 0 and i > dip_start:
            dip_end = i
            print(f"[scan] HIV_DIP tails end:   L{i+1}: {lines[i].rstrip()}")
            break

# ── Find HISTORICAL_NULL dict ─────────────────────────────────────────
hist_line = -1
for i, line in enumerate(lines):
    if 'HISTORICAL_NULL' in line and '=' in line and '{' in line:
        hist_line = i
        print(f"[scan] HISTORICAL_NULL:        L{i+1}: {line.rstrip()}")
        # Show next line for context
        if i+1 < len(lines):
            print(f"[scan]   next line:            L{i+2}: {lines[i+1].rstrip()}")
        break

print()

# ── Find both locations BEFORE any insertion ──────────────────────────
already_halobenzyl = "Cc1ccc(F)cc1F" in ''.join(lines)
already_null = any('"HIV_DIP"' in l and '5.52' in l for l in lines)

# Collect insertion specs: (line_index_to_insert_after, new_lines)
# Apply in REVERSE order so earlier insertions don't shift later line numbers
insertions = []

# Spec for patch 2: HISTORICAL_NULL
if not already_null:
    for i, line in enumerate(lines):
        if 'HISTORICAL_NULL' in line and '=' in line and '{' in line:
            next_line = lines[i+1] if i+1 < len(lines) else '            \n'
            ind = next_line[:len(next_line) - len(next_line.lstrip())]
            insertions.append((i, [f'{ind}"HIV_DIP":       (-5.52, 0.61),\n']))
            print(f"[patch] 2. Will insert HIV_DIP null after L{i+1}")
            break

# Spec for patch 1: HIV_DIP tails
if not already_halobenzyl and dip_start >= 0 and dip_end >= 0:
    ind = "            "
    for i in range(dip_start+1, dip_end):
        s = lines[i].lstrip()
        if s.startswith('"'):
            ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
            break
    new_tails = [
        f'{ind}# Halobenzyl tails (Dolutegravir/Bictegravir class)\n',
        f'{ind}"Cc1ccc(F)cc1F",\n',
        f'{ind}"Cc1cc(F)cc(F)c1",\n',
        f'{ind}"OCC(O)Cc1cc(F)cc(F)c1",\n',
        f'{ind}"NCC(O)Cc1cc(F)cc(F)c1",\n',
        f'{ind}# Naphthyridine carboxamide (Raltegravir class)\n',
        f'{ind}"c1cnc2ccccc2c1C(=O)N",\n',
        f'{ind}"c1ccc2ncccc2c1C(=O)O",\n',
        f'{ind}# Carbamoyl pyridone (Bictegravir core extension)\n',
        f'{ind}"O=C1CC(=O)c2ccc(F)cc2N1",\n',
        f'{ind}"O=C1CC(=O)c2cc(F)ccc2N1",\n',
        f'{ind}# Diketo extension tails\n',
        f'{ind}"O=C(O)C(=O)Cc1cc(F)cc(F)c1",\n',
        f'{ind}"O=C(O)C(=O)Cc1ccc(F)c(F)c1",\n',
        f'{ind}# Original anchor tails (kept)\n',
    ]
    insertions.append((dip_start, new_tails))
    print(f"[patch] 1. Will insert halobenzyl tails after L{dip_start+1}")

# Apply insertions in REVERSE order (highest line number first)
insertions.sort(key=lambda x: -x[0])
for insert_after, new_lines in insertions:
    lines[insert_after+1:insert_after+1] = new_lines

if already_halobenzyl:
    print("[patch] 1. Halobenzyl tails already present")
elif not any(x[0] == dip_start for x in insertions):
    print("[patch] 1. FAILED — could not locate HIV_DIP tails block")

if already_null:
    print("[patch] 2. HIV_DIP historical null already present")
elif not any('HIV_DIP' in ''.join(nl) for _, nl in insertions):
    print("[patch] 2. FAILED — could not locate HISTORICAL_NULL")

# ── Write + verify ─────────────────────────────────────────────────────
src = ''.join(lines)
with open(AGENT, "w", encoding="utf-8") as f:
    f.write(src)

try:
    ast.parse(src)
    print("\n[patch] Syntax check: OK")
except SyntaxError as e:
    print(f"\n[patch] SYNTAX ERROR line {e.lineno}: {e.msg}")
    print(f"        {e.text}")
    sys.exit(1)

checks = [
    ("Cc1ccc(F)cc1F",            "Halobenzyl INSTI tail"),
    ('"HIV_DIP":       (-5.52',  "HIV_DIP historical null"),
    ("dip_competitive_advantage","DIP columns present"),
    ("_dip_score",               "DIP scoring method"),
    ("target_key",               "target_key in ValidatorAgent"),
]

print("\n[patch] Verification:")
all_ok = True
for needle, label in checks:
    found = needle in src
    status = "OK " if found else "MISSING"
    if not found: all_ok = False
    print(f"  [{status}] {label}")

print()
if all_ok:
    print("[patch] ALL CHECKS PASSED — fully upgraded!")
    print()
    print("  streamlit run dashboard.py")
    print("  Select: Infectious Disease > HIV_DIP")
    print("  Standard mode, exhaustiveness 12")
else:
    print("[patch] Still missing items. Check scan output above for line numbers.")
    print("        Add manually using the line numbers shown.")
