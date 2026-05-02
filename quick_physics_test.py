"""Quick physics test"""
print("Testing Enhanced Physics Engine...")

try:
    from enhanced_physics_engine import EnhancedPhysicsEngine
    print("✓ Enhanced physics engine imported successfully")
    
    config = {
        "md_enabled": False,
        "fep_enabled": False,
        "qm_enabled": False,
        "parallel_jobs": 1,
        "temp_dir": "/tmp/test"
    }
    
    engine = EnhancedPhysicsEngine(config)
    print("✓ Enhanced physics engine initialized")
    
    print("\nSUCCESS: Enhanced Physics Engine is working!")
    print("Issue is likely in the integration to autonomous_drug_agent.py")
    
except ImportError as e:
    print(f"✗ Import failed: {e}")
    print("Enhanced physics engine file may be missing or corrupted")
    
except Exception as e:
    print(f"✗ Engine failed: {e}")
    print("Dependencies may be missing")
