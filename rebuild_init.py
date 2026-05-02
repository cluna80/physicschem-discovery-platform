"""Rebuild ValidatorAgent.__init__ cleanly — accept original params + physics."""
import shutil, ast, re

shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_init")

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# Find the broken __init__ inside ValidatorAgent
old_init = '''    def __init__(self, target_key: str = "EGFR"):
        self.target_key = target_key
        self.logger = logging.getLogger(__name__)
        
        # Setup enhanced physics if available
        if PHYSICS_AVAILABLE:
            self.physics_config = {
                "md_enabled": True,
                "fep_enabled": True,  # Enable for top candidates
                "qm_enabled": False,  # Too expensive for routine use
                "parallel_jobs": 2,
                "temp_dir": f"/tmp/physics_{target_key}"
            }
            self.physics_engine = EnhancedPhysicsEngine(self.physics_config)
            self.logger.info("[physics] Enhanced physics validation enabled")
        else:
            self.physics_engine = None
            self.logger.info("[physics] Using standard Vina-only validation")
        self.log      = logger
        self.targets  = selectivity_targets
        self.ref_aff  = ref_affinity
        self.target_key = target_key.upper()'''

new_init = '''    def __init__(self, logger, selectivity_targets, ref_affinity, target_key: str = "EGFR"):
        # Original parameters used by the orchestrator
        self.log      = logger
        self.targets  = selectivity_targets
        self.ref_aff  = ref_affinity
        self.target_key = target_key.upper() if isinstance(target_key, str) else "EGFR"

        # Standard Python logger for physics-related messages
        self.logger = logging.getLogger(__name__)

        # Optional enhanced physics engine (only if available)
        if globals().get("PHYSICS_AVAILABLE"):
            try:
                self.physics_config = {
                    "md_enabled": True,
                    "fep_enabled": True,
                    "qm_enabled": False,
                    "parallel_jobs": 2,
                    "temp_dir": f"/tmp/physics_{self.target_key}",
                }
                self.physics_engine = EnhancedPhysicsEngine(self.physics_config)
                self.log.log("ValidatorAgent", "[physics] Enhanced physics validation enabled")
            except Exception as _e:
                self.physics_engine = None
                self.log.log("ValidatorAgent", f"[physics] Engine init failed: {_e}")
        else:
            self.physics_engine = None'''

if old_init not in content:
    print("[fail] couldn't find the exact broken __init__ block")
    print("       paste sed output of lines 1373..1393 so I can adjust the matcher")
    raise SystemExit(1)

content = content.replace(old_init, new_init, 1)
print("[ok] replaced __init__")

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
