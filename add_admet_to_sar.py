"""Insert ADMET profiling step into sar_optimize.py between docking and validation."""
import shutil

shutil.copy("sar_optimize.py", "sar_optimize.py.bak_admet")

with open("sar_optimize.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add the admet_profile function after dock_analogs and before validate_and_score
admet_func = '''
def admet_profile(docked, ada):
    """Run docked compounds through ADMETAgent — annotates hERG/DILI/AMES, filters."""
    if not docked:
        return []
    log.info(f"[admet] profiling {len(docked)} docked compounds...")
    admet = ada.ADMETAgent(logger=CLILog())
    # ADMETAgent.profile expects 'id' field for log lines; we already set it
    passed = admet.profile(docked)
    log.info(f"[admet] {len(passed)}/{len(docked)} passed ADMET")
    return passed


'''

# Insert before "def validate_and_score"
marker = "def validate_and_score(docked, target_key, ref_aff, ada):"
if "def admet_profile" in content:
    print("[skip] admet_profile already present")
elif marker in content:
    content = content.replace(marker, admet_func + marker, 1)
    print("[ok] inserted admet_profile() function")
else:
    print("[fail] could not find validate_and_score marker"); raise SystemExit(1)

# 2. Wire it into main() between dock_analogs and validate_and_score
old_flow = """    docked = dock_analogs(analogs, args.receptor, ada, args.exhaustiveness)
    validated = validate_and_score(docked, args.target, args.reference_affinity, ada)"""

new_flow = """    docked = dock_analogs(analogs, args.receptor, ada, args.exhaustiveness)
    profiled = admet_profile(docked, ada)
    validated = validate_and_score(profiled, args.target, args.reference_affinity, ada)"""

if old_flow in content:
    content = content.replace(old_flow, new_flow, 1)
    print("[ok] wired admet_profile into pipeline")
else:
    # If the exact match fails, find dock_analogs line and insert after it
    if "admet_profile(docked, ada)" not in content:
        idx = content.find("validated = validate_and_score(docked,")
        if idx != -1:
            content = (content[:idx]
                       + "profiled = admet_profile(docked, ada)\n    "
                       + content[idx:].replace("validate_and_score(docked,",
                                                "validate_and_score(profiled,", 1))
            print("[ok] wired admet_profile into pipeline (fallback path)")
        else:
            print("[fail] could not wire admet_profile"); raise SystemExit(1)

# Syntax check
import ast
try:
    ast.parse(content)
    print("[ok] syntax check passed")
except SyntaxError as e:
    print(f"[fail] syntax error: {e}")
    shutil.copy("sar_optimize.py.bak_admet", "sar_optimize.py")
    raise SystemExit(1)

with open("sar_optimize.py", "w", encoding="utf-8") as f:
    f.write(content)

print("[done] ADMET integrated. Re-run optimization to see real confidence scores.")
