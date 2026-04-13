# -*- coding: utf-8 -*-
from vina_wrapper import VinaDocker

vina = VinaDocker()
print("Testing Vina wrapper...")

if vina.test_vina():
    print("Vina is ready")
    print(f"   Location: {vina.vina_path}")
    
    print("\nExample docking command:")
    print("""
    result = vina.dock(
        receptor="protein.pdbqt",
        ligand="drug.pdbqt", 
        center=(10.0, 15.0, 20.0),
        size=(20.0, 20.0, 20.0),
        output="results.pdbqt"
    )
    """)
else:
    print("Vina not found")

print("\nYou're ready for molecular docking!")
