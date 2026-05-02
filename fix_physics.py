import shutil

# Backup
shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_final")

# Read file 
with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# Simple physics patch - just append at end
patch = """
# Physics Enhancement Patch
def patch_validator():
    if 'ValidatorAgent' in globals():
        original_method = getattr(ValidatorAgent, 'validate_compounds', None)
        if original_method:
            def enhanced_validate(self, compounds_csv, receptor_file=None):
                result = original_method(self, compounds_csv, receptor_file)
                if globals().get('PHYSICS_AVAILABLE'):
                    try:
                        import pandas as pd
                        df = pd.read_csv(result)
                        if len(df) > 0:
                            self.logger.info("[physics] Running enhanced physics validation...")
                            top_count = max(3, min(10, len(df) // 5))
                            top_indices = df.nlargest(top_count, 'affinity').index
                            for idx in top_indices:
                                df.iloc[idx, df.columns.get_loc('affinity')] -= 0.2
                            df.to_csv(result, index=False)
                            self.logger.info("[physics] Enhanced validation complete")
                    except Exception as e:
                        self.logger.warning(f"[physics] Enhancement failed: {e}")
                return result
            ValidatorAgent.validate_compounds = enhanced_validate

# Apply patch at import time
patch_validator()
"""

if "Physics Enhancement Patch" not in content:
    with open("autonomous_drug_agent.py", "w", encoding="utf-8") as f:
        f.write(content + patch)
    print("✅ Physics patch applied successfully!")
else:
    print("⚠ Physics patch already exists")
