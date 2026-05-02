"""
fix_line479.py
==============
Fixes the missing comma after HIV_INTEGRASE entry on line 479
of dashboard.py. Direct line-level edit, no regex.

Run:
    python fix_line479.py
"""
import shutil, os, sys, ast

DASH = "dashboard.py"
if not os.path.isfile(DASH):
    print(f"ERROR: {DASH} not found. CWD: {os.getcwd()}")
    sys.exit(1)

shutil.copy(DASH, DASH + ".bak6")

with open(DASH, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Find and fix the exact bad line:
#   "HIV":"hiv_protease.pdbqt","HIV_INTEGRASE":"hiv_integrase.pdbqt"
# It's missing a comma at the end — needs to become:
#   "HIV":"hiv_protease.pdbqt","HIV_INTEGRASE":"hiv_integrase.pdbqt",
fixed_count = 0
for i, line in enumerate(lines):
    stripped = line.rstrip()
    if ('"HIV_INTEGRASE":"hiv_integrase.pdbqt"' in line
            and not stripped.endswith(",")):
        lines[i] = stripped + ",\n"
        fixed_count += 1
        print(f"[fix] Line {i+1} fixed: added missing comma")
        print(f"      Before: {stripped}")
        print(f"      After:  {lines[i].rstrip()}")

if fixed_count == 0:
    print("[fix] Target line not found by content — scanning for any dict")
    print("      entry ending without comma before HIV_DIP line...")
    for i, line in enumerate(lines):
        if '"HIV_DIP":"hiv_integrase.pdbqt"' in line:
            # Check the line above
            prev = lines[i-1].rstrip()
            if not prev.endswith(","):
                lines[i-1] = prev + ",\n"
                fixed_count += 1
                print(f"[fix] Line {i} fixed: {lines[i-1].rstrip()}")
            break

with open(DASH, "w", encoding="utf-8") as f:
    f.writelines(lines)

# Verify
with open(DASH, "r", encoding="utf-8") as f:
    src = f.read()

try:
    ast.parse(src)
    print()
    print("[fix] dashboard.py parses OK — no syntax errors.")
    print("[fix] Run:  streamlit run dashboard.py")
except SyntaxError as e:
    print(f"\n[fix] Still a syntax error at line {e.lineno}: {e.msg}")
    ctx = src.splitlines()
    for j in range(max(0, e.lineno-3), min(len(ctx), e.lineno+2)):
        print(f"  L{j+1:>4}: {ctx[j]}")
