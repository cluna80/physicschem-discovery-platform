"""Fixed diagnostic with proper encoding"""

def diagnose_validator_integration():
    print("Diagnosing ValidatorAgent Integration...")
    print("=" * 50)
    
    try:
        # Use UTF-8 encoding with error handling
        with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except UnicodeDecodeError:
        # Fallback to latin-1 if UTF-8 fails
        with open("autonomous_drug_agent.py", "r", encoding="latin-1") as f:
            content = f.read()
    
    print("\n1. Checking physics integration...")
    
    # Check for physics references
    has_import = "enhanced_physics_engine" in content
    has_flag = "PHYSICS_AVAILABLE" in content
    has_validator_physics = "physics_engine" in content
    
    print(f"   Enhanced physics mentioned: {'✓' if has_import else '✗'}")
    print(f"   PHYSICS_AVAILABLE flag: {'✓' if has_flag else '✗'}")
    print(f"   ValidatorAgent physics: {'✓' if has_validator_physics else '✗'}")
    
    # Check file size vs backup
    try:
        with open("autonomous_drug_agent.py.bak_physics", "r", encoding="utf-8", errors="ignore") as f:
            backup = f.read()
        
        size_diff = len(content) - len(backup)
        print(f"\n2. File comparison:")
        print(f"   Size difference: +{size_diff} characters")
        
    except FileNotFoundError:
        print("\n2. No backup file found")
    
    # Diagnosis
    print(f"\n{'='*50}")
    if has_import and has_flag:
        if has_validator_physics:
            print("🟡 PARTIAL INTEGRATION: Physics added but may not be in workflow")
        else:
            print("🟠 INCOMPLETE: Import added but ValidatorAgent not enhanced")
    else:
        print("🔴 FAILED: No physics integration detected")
    
    print("\nNext step: Manual ValidatorAgent enhancement needed")

if __name__ == "__main__":
    diagnose_validator_integration()
