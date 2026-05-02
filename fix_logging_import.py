"""Add the missing 'import logging' to autonomous_drug_agent.py"""
import shutil, ast

shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_logging")

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

if "\nimport logging" in content or content.startswith("import logging"):
    print("[skip] 'import logging' already present")
else:
    # Insert after the first existing import line
    lines = content.split("\n")
    insert_at = 0
    for i, ln in enumerate(lines[:60]):
        if ln.startswith("import ") or ln.startswith("from "):
            insert_at = i + 1
            break
    lines.insert(insert_at, "import logging")
    content = "\n".join(lines)
    print(f"[ok] inserted 'import logging' at line {insert_at + 1}")

# Syntax check
try:
    ast.parse(content)
    print("[ok] syntax check passed")
except SyntaxError as e:
    print(f"[fail] syntax error: {e}")
    raise SystemExit(1)

with open("autonomous_drug_agent.py", "w", encoding="utf-8") as f:
    f.write(content)
print("[done]")
