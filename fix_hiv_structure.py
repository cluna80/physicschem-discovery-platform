#!/usr/bin/env python3
"""
Fix HIV protease PDB for OpenMM simulation
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
from openmm.app import PDBFile, Modeller
import mdtraj as md
import os

print("="*60)
print("Fixing HIV Protease Structure for OpenMM")
print("="*60)

# Load original PDB
pdb_file = "hiv_protease.pdb"
print(f"Loading {pdb_file}...")
pdb = PDBFile(pdb_file)

print(f"Original protein: {pdb.topology.getNumAtoms()} atoms, {pdb.topology.getNumResidues()} residues")

# Create a modeller to add missing atoms
modeller = Modeller(pdb.topology, pdb.positions)

# Add missing hydrogens
print("Adding missing hydrogens...")
modeller.addHydrogens()

# Add solvent if needed (but we'll skip for now)
print(f"Fixed protein: {modeller.topology.getNumAtoms()} atoms, {modeller.topology.getNumResidues()} residues")

# Save the fixed structure
with open('hiv_protease_fixed.pdb', 'w') as f:
    PDBFile.writeFile(modeller.topology, modeller.positions, f)

print("✅ Fixed structure saved as: hiv_protease_fixed.pdb")

# Now let's test if this works with force field
print("\n" + "="*60)
print("Testing force field with fixed structure...")
print("="*60)

forcefield = app.ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# Create system
try:
    system = forcefield.createSystem(
        modeller.topology,
        nonbondedMethod=app.PME,
        nonbondedCutoff=1.0*unit.nanometer,
        constraints=app.HBonds,
        rigidWater=True
    )
    print("✅ Force field successfully applied!")
    print(f"System has {system.getNumParticles()} particles")
except Exception as e:
    print(f"Error: {e}")

print("\n✅ Structure preparation complete!")
