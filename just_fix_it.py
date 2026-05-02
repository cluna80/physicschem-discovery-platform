"""
just_fix_it.py
==============
Scans the file, shows exactly what it finds, then patches.
Run:  python just_fix_it.py
"""
import shutil, os, ast

AGENT = "autonomous_drug_agent.py"
shutil.copy(AGENT, AGENT + ".bak_jfi")

with open(AGENT, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"File: {len(lines)} lines\n")

# ── Show all lines containing HIV_DIP ────────────────────────────────
print("=== All lines with HIV_DIP ===")
for i, l in enumerate(lines):
    if "HIV_DIP" in l:
        print(f"  L{i+1:>4}: {l.rstrip()}")

print()
print("=== All lines with HISTORICAL_NULL ===")
for i, l in enumerate(lines):
    if "HISTORICAL_NULL" in l:
        print(f"  L{i+1:>4}: {l.rstrip()}")
        if i+1 < len(lines): print(f"  L{i+2:>4}: {lines[i+1].rstrip()}")
        if i+2 < len(lines): print(f"  L{i+3:>4}: {lines[i+2].rstrip()}")

print()
print("=== All lines with PHARMA_TAILS ===")
for i, l in enumerate(lines):
    if "PHARMA_TAILS" in l:
        print(f"  L{i+1:>4}: {l.rstrip()}")

print()

# ── Check if already done ─────────────────────────────────────────────
src = "".join(lines)
if "Cc1ccc(F)cc1F" in src:
    print("Halobenzyl tails: ALREADY PRESENT")
else:
    print("Halobenzyl tails: MISSING — will insert")

if '"HIV_DIP"' in src and "(-5.52" in src:
    # Check if it's specifically in HISTORICAL_NULL context
    idx = src.find("HISTORICAL_NULL")
    nearby = src[idx:idx+300] if idx >= 0 else ""
    if "HIV_DIP" in nearby:
        print("HIV_DIP historical null: ALREADY PRESENT")
    else:
        print("HIV_DIP historical null: MISSING — will insert")
else:
    print("HIV_DIP historical null: MISSING — will insert")

print()

# ── PATCH: Find HIV_DIP tails by looking for the pattern more broadly ──
# Strategy: find "HIV_DIP" line that's inside PHARMA_TAILS
# PHARMA_TAILS block is between "PHARMA_TAILS = {" and the matching "}"

pharma_start = -1
for i, l in enumerate(lines):
    if "PHARMA_TAILS" in l and "=" in l and "{" in l:
        pharma_start = i
        break

if pharma_start < 0:
    # It might be defined as a class variable without =
    for i, l in enumerate(lines):
        if "PHARMA_TAILS" in l:
            pharma_start = i
            break

print(f"PHARMA_TAILS at L{pharma_start+1 if pharma_start>=0 else 'NOT FOUND'}")

# Find HIV_DIP entry inside PHARMA_TAILS
dip_tails_line = -1
if pharma_start >= 0:
    for i in range(pharma_start, min(pharma_start+200, len(lines))):
        if '"HIV_DIP"' in lines[i] and "[" in lines[i]:
            dip_tails_line = i
            print(f"HIV_DIP tails entry at L{i+1}: {lines[i].rstrip()}")
            break

# PATCH 1: Insert halobenzyl tails
if "Cc1ccc(F)cc1F" not in src and dip_tails_line >= 0:
    # Find the closing ] of this entry
    depth = 0
    close_line = -1
    for i in range(dip_tails_line, min(dip_tails_line+50, len(lines))):
        depth += lines[i].count("[") - lines[i].count("]")
        if depth <= 0 and i > dip_tails_line:
            close_line = i
            break

    if close_line > 0:
        # Get indent from existing entries
        ind = "            "
        for i in range(dip_tails_line+1, close_line):
            if lines[i].lstrip().startswith('"'):
                ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                break

        new_tails = [
            f'{ind}# Halobenzyl tails (Dolutegravir/Bictegravir class)\n',
            f'{ind}"Cc1ccc(F)cc1F",\n',
            f'{ind}"Cc1cc(F)cc(F)c1",\n',
            f'{ind}"OCC(O)Cc1cc(F)cc(F)c1",\n',
            f'{ind}"NCC(O)Cc1cc(F)cc(F)c1",\n',
            f'{ind}# Carbamoyl pyridone (Bictegravir core)\n',
            f'{ind}"O=C1CC(=O)c2ccc(F)cc2N1",\n',
            f'{ind}"O=C1CC(=O)c2cc(F)ccc2N1",\n',
            f'{ind}# Diketo extension tails\n',
            f'{ind}"O=C(O)C(=O)Cc1cc(F)cc(F)c1",\n',
            f'{ind}"O=C(O)C(=O)Cc1ccc(F)c(F)c1",\n',
        ]
        # Insert BEFORE closing bracket line
        lines[close_line:close_line] = new_tails
        print(f"[patch] 1. Halobenzyl tails inserted before L{close_line+1}")
    else:
        print("[patch] 1. Could not find closing ] of HIV_DIP tails")
elif "Cc1ccc(F)cc1F" in src:
    print("[patch] 1. Already present — skip")
else:
    print("[patch] 1. Could not find HIV_DIP tails entry in PHARMA_TAILS")

# Rebuild src after potential line insertions
src = "".join(lines)

# PATCH 2: HIV_DIP historical null
# Find HISTORICAL_NULL and insert after opening {
hist_line = -1
for i, l in enumerate(lines):
    if "HISTORICAL_NULL" in l and "=" in l and "{" in l:
        hist_line = i
        break

already_in_null = False
if hist_line >= 0:
    null_block = "".join(lines[hist_line:hist_line+15])
    already_in_null = "HIV_DIP" in null_block

if already_in_null:
    print("[patch] 2. HIV_DIP already in HISTORICAL_NULL — skip")
elif hist_line >= 0:
    # Insert as first entry
    next_l = lines[hist_line+1] if hist_line+1 < len(lines) else "            \n"
    ind2 = next_l[:len(next_l) - len(next_l.lstrip())]
    lines.insert(hist_line+1, f'{ind2}"HIV_DIP":       (-5.52, 0.61),\n')
    print(f"[patch] 2. HIV_DIP null inserted after L{hist_line+1}")
else:
    print("[patch] 2. HISTORICAL_NULL not found")

# ── Write ─────────────────────────────────────────────────────────────
src = "".join(lines)
with open(AGENT, "w", encoding="utf-8") as f:
    f.write(src)

try:
    ast.parse(src)
    print("\n[patch] Syntax: OK")
except SyntaxError as e:
    print(f"\n[patch] SYNTAX ERROR L{e.lineno}: {e.msg} — {e.text}")

# ── Verify ────────────────────────────────────────────────────────────
checks = [
    ("Cc1ccc(F)cc1F",            "Halobenzyl tail"),
    ('"HIV_DIP":       (-5.52',  "HIV_DIP historical null"),
    ("dip_competitive_advantage","DIP columns"),
    ("_dip_score",               "DIP scoring"),
    ("target_key",               "target_key param"),
]
print("\nVerification:")
all_ok = True
for needle, label in checks:
    ok = needle in src
    if not ok: all_ok = False
    print(f"  [{'OK ' if ok else 'MISS'}] {label}")

if all_ok:
    print("\nALL CHECKS PASSED — run:  streamlit run dashboard.py")
else:
    print("\nStill missing. Paste the scan output above here so we can fix manually.")
