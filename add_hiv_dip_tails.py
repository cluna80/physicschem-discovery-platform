"""
add_hiv_dip_tails.py
--------------------
Inserts a HIV_DIP entry into the PHARMA_TAILS dict by tracking brace depth
to find the dict's closing brace. No regex, format-independent.
"""
from pathlib import Path
import ast
import shutil

FILE = "autonomous_drug_agent.py"
src = Path(FILE).read_text(encoding="utf-8")
lines = src.splitlines(keepends=True)

# 1. Locate `PHARMA_TAILS = {`
start = None
for i, ln in enumerate(lines):
    stripped = ln.lstrip()
    if stripped.startswith("PHARMA_TAILS") and "=" in ln and "{" in ln:
        start = i
        break

if start is None:
    print("[fail] PHARMA_TAILS dict opening not found")
    raise SystemExit(1)
print(f"[ok] PHARMA_TAILS opens at L{start+1}")

# 2. Walk forward tracking brace depth to find matching `}` at depth 0
depth = 0
end = None
in_str = False
str_ch = None
escape = False
for i in range(start, len(lines)):
    ln = lines[i]
    for ch in ln:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if in_str:
            if ch == str_ch:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is not None:
        break

if end is None:
    print("[fail] could not find matching close brace for PHARMA_TAILS")
    raise SystemExit(1)
print(f"[ok] PHARMA_TAILS closes at L{end+1}")

# 3. Skip if already present
dict_text = "".join(lines[start:end+1])
if '"HIV_DIP"' in dict_text or "'HIV_DIP'" in dict_text:
    print("[skip] HIV_DIP entry already present in PHARMA_TAILS")
    raise SystemExit(0)

# 4. Detect indentation from first key entry inside the dict
indent = "        "  # sensible default
for i in range(start + 1, end):
    s = lines[i]
    if (s.lstrip().startswith('"') or s.lstrip().startswith("'")) and ":" in s and "[" in s:
        indent = s[: len(s) - len(s.lstrip())]
        break
sub = indent + "    "
print(f"[ok] detected key indent: {len(indent)} spaces")

# 5. Build entry (15 INSTI-class tails: Dolutegravir/Bictegravir/Raltegravir scaffolds)
entry = (
    f'{indent}"HIV_DIP": [\n'
    f'{sub}# Halobenzyl tails (Dolutegravir / Bictegravir INSTI class)\n'
    f'{sub}"Cc1ccc(F)cc1F",\n'
    f'{sub}"Cc1cc(F)cc(F)c1",\n'
    f'{sub}"OCC(O)Cc1cc(F)cc(F)c1",\n'
    f'{sub}"NCC(O)Cc1cc(F)cc(F)c1",\n'
    f'{sub}# Naphthyridine carboxamide (Raltegravir class)\n'
    f'{sub}"c1cnc2ccccc2c1C(=O)N",\n'
    f'{sub}"c1ccc2ncccc2c1C(=O)O",\n'
    f'{sub}# Oxadiazole / triazole INSTI warheads\n'
    f'{sub}"c1nnco1",\n'
    f'{sub}"c1nncn1C",\n'
    f'{sub}"CC1=CC(=O)N(Cc2ccccc2)N1",\n'
    f'{sub}# Carbamoyl pyridone (Bictegravir core extension)\n'
    f'{sub}"O=C1CC(=O)c2ccc(F)cc2N1",\n'
    f'{sub}"O=C1CC(=O)c2cc(F)ccc2N1",\n'
    f'{sub}# Diketo extension tails (chelator + halobenzyl)\n'
    f'{sub}"O=C(O)C(=O)Cc1cc(F)cc(F)c1",\n'
    f'{sub}"O=C(O)C(=O)Cc1ccc(F)c(F)c1",\n'
    f'{indent}],\n'
)

# 6. Backup, insert, write
shutil.copy(FILE, FILE + ".bak_dip_tails")
lines.insert(end, entry)
Path(FILE).write_text("".join(lines), encoding="utf-8")
print(f"[ok] inserted HIV_DIP entry (15 INSTI tails) before L{end+1}")
print(f"[ok] backup: {FILE}.bak_dip_tails")

# 7. Syntax check
try:
    ast.parse(Path(FILE).read_text(encoding="utf-8"))
    print("[ok] syntax check passed")
except SyntaxError as e:
    print(f"[fail] syntax error after edit: {e}")
    print("       restoring backup")
    shutil.copy(FILE + ".bak_dip_tails", FILE)
    raise SystemExit(1)

# 8. Verify
text = Path(FILE).read_text(encoding="utf-8")
checks = [
    ("HIV_DIP key in PHARMA_TAILS",   '"HIV_DIP":' in text),
    ("Halobenzyl INSTI tail",          "Cc1cc(F)cc(F)c1" in text),
    ("Naphthyridine warhead",          "c1cnc2ccccc2c1C(=O)N" in text),
    ("Carbamoyl pyridone",             "O=C1CC(=O)c2ccc(F)cc2N1" in text),
    ("Diketo halobenzyl",              "O=C(O)C(=O)Cc1cc(F)cc(F)c1" in text),
]
print()
all_ok = True
for name, ok in checks:
    tag = "OK " if ok else "MISSING"
    if not ok:
        all_ok = False
    print(f"  [{tag}] {name}")

if all_ok:
    print("\n[DONE] HIV_DIP INSTI tails active.")
    print("       Next: streamlit run dashboard.py  →  Standard mode, exhaustiveness 12")
else:
    print("\n[fail] some checks missing — see backup .bak_dip_tails")
