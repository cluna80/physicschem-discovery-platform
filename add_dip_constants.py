"""Add the missing DIP constants to ValidatorAgent.__init__"""
import shutil, ast

shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_dip_const")

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# Find the line that currently sets self.target_key in the new __init__,
# and append the DIP constants right after it.
anchor = '        self.target_key = target_key.upper() if isinstance(target_key, str) else "EGFR"'

dip_constants = '''        self.target_key = target_key.upper() if isinstance(target_key, str) else "EGFR"

        # ── DIP framework constants (HIV integrase therapeutic competition) ──
        self.DIP_REFERENCE_AFFINITY = -9.43   # Dolutegravir baseline (kcal/mol)
        self.DIP_TIER_STRONG        =  2.0    # competitive advantage ≥ 2.0 = STRONG
        self.DIP_TIER_MODERATE      =  1.0    # competitive advantage ≥ 1.0 = MODERATE
        self.DIP_TIER_MARGINAL      =  0.0    # competitive advantage ≥ 0.0 = MARGINAL
        self.DIP_MW_IDEAL           =  450.0  # ideal MW for CD4 sparing
        self.DIP_MW_CEILING         =  600.0  # max MW for DIP candidate'''

if "DIP_REFERENCE_AFFINITY" in content and "self.DIP_REFERENCE_AFFINITY = -9.43" in content:
    print("[skip] DIP constants already present")
elif anchor in content:
    content = content.replace(anchor, dip_constants, 1)
    print("[ok] inserted DIP constants into __init__")
else:
    print("[fail] anchor line not found — paste sed -n '1370,1410p' so I can adjust")
    raise SystemExit(1)

# Syntax check
try:
    ast.parse(content)
    print("[ok] syntax check passed")
except SyntaxError as e:
    print(f"[fail] syntax error: {e}")
    raise SystemExit(1)

with open("autonomous_drug_agent.py", "w", encoding="utf-8") as f:
    f.write(content)
print("[done] rerun: python test_validate_directly.py")
