"""
diagnose_validator.py
====================
Check if ValidatorAgent has the enhanced physics integration
and why it's not running during campaigns
"""

def diagnose_validator_integration():
    print("Diagnosing ValidatorAgent Integration...")
    print("=" * 50)
    
    # 1. Check if autonomous_drug_agent.py has physics import
    print("\n1. Checking physics import in autonomous_drug_agent.py...")
    
    try:
        with open("autonomous_drug_agent.py", "r") as f:
            content = f.read()
            
        if "enhanced_physics_engine" in content:
            print("   ✓ Enhanced physics engine mentioned in file")
            
            if "PHYSICS_AVAILABLE" in content:
                print("   ✓ PHYSICS_AVAILABLE flag found")
            else:
                print("   ✗ PHYSICS_AVAILABLE flag missing")
                
            if "from enhanced_physics_engine import" in content:
                print("   ✓ Physics import statement found")
            else:
                print("   ✗ Physics import statement missing")
                
        else:
            print("   ✗ No enhanced physics references found")
            
    except FileNotFoundError:
        print("   ✗ autonomous_drug_agent.py not found")
        return False
        
    # 2. Check ValidatorAgent class structure
    print("\n2. Checking ValidatorAgent class...")
    
    if "class ValidatorAgent" in content:
        print("   ✓ ValidatorAgent class found")
        
        # Find ValidatorAgent class boundaries
        class_start = content.find("class ValidatorAgent")
        if class_start == -1:
            print("   ✗ Could not locate ValidatorAgent class")
            return False
            
        # Find next class or end of file
        remaining_content = content[class_start:]
        next_class = remaining_content.find("\nclass ")
        if next_class == -1:
            validator_content = remaining_content
        else:
            validator_content = remaining_content[:next_class]
            
        # Check for physics integration points
        if "physics_engine" in validator_content:
            print("   ✓ physics_engine references found in ValidatorAgent")
        else:
            print("   ✗ physics_engine references missing in ValidatorAgent")
            
        if "validate_compounds" in validator_content:
            print("   ✓ validate_compounds method found")
            
            # Check if validate_compounds has physics logic
            validate_start = validator_content.find("def validate_compounds")
            if validate_start != -1:
                validate_method = validator_content[validate_start:validate_start+2000]  # First 2000 chars
                
                if "physics" in validate_method.lower():
                    print("   ✓ Physics logic found in validate_compounds")
                else:
                    print("   ✗ Physics logic missing in validate_compounds")
                    
        else:
            print("   ✗ validate_compounds method not found")
            
    else:
        print("   ✗ ValidatorAgent class not found")
        
    # 3. Check what integration actually did
    print("\n3. Checking integration results...")
    
    # Look for backup file
    try:
        with open("autonomous_drug_agent.py.bak_physics", "r") as f:
            backup_content = f.read()
        print("   ✓ Backup file exists")
        
        # Compare sizes
        original_size = len(backup_content)
        current_size = len(content)
        size_diff = current_size - original_size
        
        print(f"   📊 Original file: {original_size} chars")
        print(f"   📊 Current file: {current_size} chars")
        print(f"   📊 Size difference: +{size_diff} chars")
        
        if size_diff > 0:
            print("   ✓ File was modified (content added)")
        else:
            print("   ⚠  File size unchanged or reduced")
            
    except FileNotFoundError:
        print("   ✗ Backup file not found")
        
    # 4. Check for __init__ method modifications
    print("\n4. Checking ValidatorAgent.__init__ modifications...")
    
    if "def __init__(self" in validator_content:
        init_start = validator_content.find("def __init__(self")
        init_end = validator_content.find("\n    def ", init_start)
        if init_end == -1:
            init_end = len(validator_content)
            
        init_method = validator_content[init_start:init_end]
        
        if "physics_engine" in init_method:
            print("   ✓ physics_engine initialization found")
        else:
            print("   ✗ physics_engine initialization missing")
            
        if "EnhancedPhysicsEngine" in init_method:
            print("   ✓ EnhancedPhysicsEngine instantiation found")
        else:
            print("   ✗ EnhancedPhysicsEngine instantiation missing")
            
    else:
        print("   ✗ __init__ method not found in ValidatorAgent")
        
    print("\n" + "=" * 50)
    print("DIAGNOSIS COMPLETE - Check results above")

if __name__ == "__main__":
    diagnose_validator_integration()
EOFcat > diagnose_validator.py << 'EOF'
"""
diagnose_validator.py
====================
Check if ValidatorAgent has the enhanced physics integration
and why it's not running during campaigns
"""

def diagnose_validator_integration():
    print("Diagnosing ValidatorAgent Integration...")
    print("=" * 50)
    
    # 1. Check if autonomous_drug_agent.py has physics import
    print("\n1. Checking physics import in autonomous_drug_agent.py...")
    
    try:
        with open("autonomous_drug_agent.py", "r") as f:
            content = f.read()
            
        if "enhanced_physics_engine" in content:
            print("   ✓ Enhanced physics engine mentioned in file")
            
            if "PHYSICS_AVAILABLE" in content:
                print("   ✓ PHYSICS_AVAILABLE flag found")
            else:
                print("   ✗ PHYSICS_AVAILABLE flag missing")
                
            if "from enhanced_physics_engine import" in content:
                print("   ✓ Physics import statement found")
            else:
                print("   ✗ Physics import statement missing")
                
        else:
            print("   ✗ No enhanced physics references found")
            
    except FileNotFoundError:
        print("   ✗ autonomous_drug_agent.py not found")
        return False
        
    # 2. Check ValidatorAgent class structure
    print("\n2. Checking ValidatorAgent class...")
    
    if "class ValidatorAgent" in content:
        print("   ✓ ValidatorAgent class found")
        
        # Find ValidatorAgent class boundaries
        class_start = content.find("class ValidatorAgent")
        if class_start == -1:
            print("   ✗ Could not locate ValidatorAgent class")
            return False
            
        # Find next class or end of file
        remaining_content = content[class_start:]
        next_class = remaining_content.find("\nclass ")
        if next_class == -1:
            validator_content = remaining_content
        else:
            validator_content = remaining_content[:next_class]
            
        # Check for physics integration points
        if "physics_engine" in validator_content:
            print("   ✓ physics_engine references found in ValidatorAgent")
        else:
            print("   ✗ physics_engine references missing in ValidatorAgent")
            
        if "validate_compounds" in validator_content:
            print("   ✓ validate_compounds method found")
            
            # Check if validate_compounds has physics logic
            validate_start = validator_content.find("def validate_compounds")
            if validate_start != -1:
                validate_method = validator_content[validate_start:validate_start+2000]  # First 2000 chars
                
                if "physics" in validate_method.lower():
                    print("   ✓ Physics logic found in validate_compounds")
                else:
                    print("   ✗ Physics logic missing in validate_compounds")
                    
        else:
            print("   ✗ validate_compounds method not found")
            
    else:
        print("   ✗ ValidatorAgent class not found")
        
    # 3. Check what integration actually did
    print("\n3. Checking integration results...")
    
    # Look for backup file
    try:
        with open("autonomous_drug_agent.py.bak_physics", "r") as f:
            backup_content = f.read()
        print("   ✓ Backup file exists")
        
        # Compare sizes
        original_size = len(backup_content)
        current_size = len(content)
        size_diff = current_size - original_size
        
        print(f"   📊 Original file: {original_size} chars")
        print(f"   📊 Current file: {current_size} chars")
        print(f"   📊 Size difference: +{size_diff} chars")
        
        if size_diff > 0:
            print("   ✓ File was modified (content added)")
        else:
            print("   ⚠  File size unchanged or reduced")
            
    except FileNotFoundError:
        print("   ✗ Backup file not found")
        
    # 4. Check for __init__ method modifications
    print("\n4. Checking ValidatorAgent.__init__ modifications...")
    
    if "def __init__(self" in validator_content:
        init_start = validator_content.find("def __init__(self")
        init_end = validator_content.find("\n    def ", init_start)
        if init_end == -1:
            init_end = len(validator_content)
            
        init_method = validator_content[init_start:init_end]
        
        if "physics_engine" in init_method:
            print("   ✓ physics_engine initialization found")
        else:
            print("   ✗ physics_engine initialization missing")
            
        if "EnhancedPhysicsEngine" in init_method:
            print("   ✓ EnhancedPhysicsEngine instantiation found")
        else:
            print("   ✗ EnhancedPhysicsEngine instantiation missing")
            
    else:
        print("   ✗ __init__ method not found in ValidatorAgent")
        
    print("\n" + "=" * 50)
    print("DIAGNOSIS COMPLETE - Check results above")

if __name__ == "__main__":
    diagnose_validator_integration()
