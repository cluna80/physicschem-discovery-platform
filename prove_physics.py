"""Add an unconditional log right before the physics if-block so we know if the code path even runs."""
import shutil
shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_prove")

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

marker = "# === Inline Physics Enhancement ==="
unconditional = """# === Inline Physics Enhancement ===
        self.log.log('ValidatorAgent', f\"[physics-debug] entered enhancement block, PHYSICS_AVAILABLE={globals().get('PHYSICS_AVAILABLE')}, compounds={len(compounds)}\")"""

if marker in content and "[physics-debug]" not in content:
    content = content.replace(marker, unconditional, 1)
    with open("autonomous_drug_agent.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("[ok] added unconditional debug log")
else:
    print("[skip] already added or marker missing")
