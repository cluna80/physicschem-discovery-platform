from vina_wrapper import VinaDocker
import os

# Initialize Vina
vina = VinaDocker()

# Test docking parameters
# This is a simple test - you'll need actual PDBQT files for real docking
print("íº€ Vina Docker is ready!")

# Example docking setup (commented out until we have actual files)
"""
vina.dock(
    receptor="receptor.pdbqt",
    ligand="ligand.pdbqt",
    center=(15.0, 20.0, 10.0),
    size=(20.0, 20.0, 20.0),
    output="docking_result.pdbqt"
)
"""

print("âœ… Vina Docker ready for use!")
