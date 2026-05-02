"""
fix_comma.py
============
Fixes the double-comma syntax error on line 480 of dashboard.py.
Run:
    python fix_comma.py
"""
import re, shutil, os, sys, ast

DASH = "dashboard.py"
if not os.path.isfile(DASH):
    print(f"ERROR: {DASH} not found. CWD: {os.getcwd()}")
    sys.exit(1)

shutil.copy(DASH, DASH + ".bak5")
print(f"[fix] Backup: {DASH}.bak5")

with open(DASH, "r", encoding="utf-8") as f:
    src = f.read()

# Remove any doubled commas like ,,
fixed = re.sub(r',\s*,', ',', src)

changed = src.count(',,') + src.count(', ,')
print(f"[fix] Double-commas found and fixed: {src.count(',,')}")

with open(DASH, "w", encoding="utf-8") as f:
    f.write(fixed)

# Verify it now parses
try:
    ast.parse(fixed)
    print("[fix] dashboard.py parses OK — no syntax errors.")
    print()
    print("[fix] Run:  streamlit run dashboard.py")
except SyntaxError as e:
    print(f"[fix] Still a syntax error at line {e.lineno}: {e.msg}")
    print(f"       {e.text}")
    print("[fix] Showing lines around the error:")
    lines = fixed.splitlines()
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        print(f"  L{i+1:>4}: {lines[i]}")
