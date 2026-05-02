"""
patch_final2.py
===============
Applies the last 2 remaining patches:
  1. Upgrade PHARMA_TAILS["HIV_DIP"] with INSTI halobenzyl/pyridone tails
  2. Add HIV_DIP to HiggsSignificanceTester historical null distribution

Run:
    python patch_final2.py
"""
import shutil, os, sys, ast

AGENT = "autonomous_drug_agent.py"
if not os.path.isfile(AGENT):
    print(f"ERROR: {AGENT} not found"); sys.exit(1)

shutil.copy(AGENT, AGENT + ".bak_f2")

with open(AGENT, "r", encoding="utf-8") as f:
    src = f.read()

applied = 0

# ── PATCH 1: Upgrade HIV_DIP PHARMA_TAILS ─────────────────────────────
# The file has the new tails already if previous patches ran, or the old
# ones. We search for the HIV_DIP entry by scanning line by line and
# replacing whatever is there with the upgraded version.

import re

# Find the HIV_DIP tails block — match from "HIV_DIP": [ to the closing ],
# being careful not to grab HIV_INTEGRASE
dip_tails_pattern = re.compile(
    r'("HIV_DIP":\s*\[)[^\]]*?(\],)',
    re.DOTALL
)

NEW_DIP_TAILS_BODY = '''
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
        '''

if "Cc1ccc(F)cc1F" in src:
    print("[patch] 1. Halobenzyl tails already present — skipping")
else:
    m = dip_tails_pattern.search(src)
    if m:
        src = src[:m.start()] + '"HIV_DIP": [' + NEW_DIP_TAILS_BODY + '],' + src[m.end():]
        print("[patch] 1. PHARMA_TAILS HIV_DIP upgraded with INSTI halobenzyl/pyridone tails")
        applied += 1
    else:
        # Fallback: find by line scan
        lines = src.splitlines(keepends=True)
        in_dip = False
        bracket_depth = 0
        start_line = end_line = -1
        for i, line in enumerate(lines):
            if '"HIV_DIP":' in line and '[' in line and not in_dip:
                in_dip = True
                start_line = i
                bracket_depth = line.count('[') - line.count(']')
                continue
            if in_dip:
                bracket_depth += line.count('[') - line.count(']')
                if bracket_depth <= 0:
                    end_line = i
                    break
        if start_line >= 0 and end_line >= 0:
            new_block = (
                '        "HIV_DIP": [\n'
                + NEW_DIP_TAILS_BODY.strip('\n') + '\n'
                + '        ],\n'
            )
            lines[start_line:end_line+1] = [new_block]
            src = ''.join(lines)
            print("[patch] 1. PHARMA_TAILS HIV_DIP upgraded (line-scan fallback)")
            applied += 1
        else:
            print("[patch] 1. WARNING: could not locate HIV_DIP tails block")

# ── PATCH 2: Add HIV_DIP to historical null ────────────────────────────
# The HISTORICAL_NULL dict may have slightly different formatting.
# Search line by line for the dict definition and insert HIV_DIP before
# HIV_INTEGRASE (or any other first entry).

if '"HIV_DIP":       (-5.52' in src or '"HIV_DIP": (-5.52' in src:
    print("[patch] 2. HIV_DIP historical null already present — skipping")
else:
    # Find HISTORICAL_NULL = { and insert HIV_DIP as first entry
    hist_pattern = re.compile(
        r'(HISTORICAL_NULL\s*=\s*\{)\s*\n(\s*")',
        re.MULTILINE
    )
    m2 = hist_pattern.search(src)
    if m2:
        # group(2) is the indentation + opening quote of first entry
        # We insert BEFORE it, keeping it intact
        indent = re.match(r'^(\s*)', m2.group(2)).group(1)
        insert = m2.group(1) + '\n' + indent + '"HIV_DIP":       (-5.52, 0.61),\n' + m2.group(2)
        src = src[:m2.start()] + insert + src[m2.end():]
        print("[patch] 2. HIV_DIP added to Higgs historical null")
        applied += 1
    else:
        # Line-by-line fallback
        lines = src.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if 'HISTORICAL_NULL' in line and '=' in line and '{' in line:
                # Insert after this line
                # Detect indentation from next non-empty line
                next_line = lines[i+1] if i+1 < len(lines) else '            '
                indent_m = re.match(r'^(\s*)', next_line)
                indent_str = indent_m.group(1) if indent_m else '            '
                lines.insert(i+1, f'{indent_str}"HIV_DIP":       (-5.52, 0.61),\n')
                src = ''.join(lines)
                print("[patch] 2. HIV_DIP historical null added (line-scan fallback)")
                applied += 1
                break
        else:
            print("[patch] 2. WARNING: could not locate HISTORICAL_NULL dict")

# ── Write + verify ─────────────────────────────────────────────────────
with open(AGENT, "w", encoding="utf-8") as f:
    f.write(src)
print(f"\n[patch] {AGENT} written ({applied} patches applied)")

try:
    ast.parse(src)
    print("[patch] Syntax check: OK")
except SyntaxError as e:
    print(f"[patch] SYNTAX ERROR line {e.lineno}: {e.msg}")
    sys.exit(1)

checks = [
    ("Cc1ccc(F)cc1F",           "Halobenzyl INSTI tail"),
    ('"HIV_DIP":       (-5.52', "HIV_DIP historical null"),
    ("dip_competitive_advantage", "DIP columns present"),
    ("_dip_score",               "DIP scoring method"),
    ("target_key",               "target_key in ValidatorAgent"),
]

print()
print("[patch] Verification:")
all_ok = True
for needle, label in checks:
    found = needle in src
    status = "OK " if found else "MISSING"
    if not found: all_ok = False
    print(f"  [{status}] {label}")

print()
if all_ok:
    print("[patch] ALL CHECKS PASSED. Pipeline fully upgraded.")
    print()
    print("  Run:  streamlit run dashboard.py")
    print("  Select: Infectious Disease > HIV_DIP")
    print("  Mode: Standard, exhaustiveness 12")
    print("  Expected: DIP=STRONG(+X.XX) in leaderboard")
else:
    print("[patch] Still missing items. Backup: .bak_f2")
