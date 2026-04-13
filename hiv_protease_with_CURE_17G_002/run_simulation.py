#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple OpenMM Simulation with CURE_17G_002
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
import os

print("="*60)
print("OpenMM MD Simulation - HIV Protease + CURE_17G_002")
print("="*60)

# Check if complex exists
if not os.path.exists('complex.pdb'):
    print("Error: complex.pdb not found!")
    exit(1)

# Load complex
print("Loading complex.pdb...")
pdb = app.PDBFile('complex.pdb')
print(f"Atoms: {pdb.topology.getNumAtoms()}")
print(f"Residues: {pdb.topology.getNumResidues()}")

# Force field
forcefield = app.ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# Add hydrogens and solvent
print("\nAdding hydrogens and water...")
modeller = app.Modeller(pdb.topology, pdb.positions)
modeller.addHydrogens(forcefield)
modeller.addSolvent(forcefield, padding=1.0*unit.nanometer)

print(f"After solvation: {modeller.topology.getNumAtoms()} atoms")

# Create system
print("\nCreating system...")
system = forcefield.createSystem(
    modeller.topology,
    nonbondedMethod=app.PME,
    nonbondedCutoff=1.0*unit.nanometer,
    constraints=app.HBonds
)

# Add barostat
system.addForce(mm.MonteCarloBarostat(1*unit.bar, 300*unit.kelvin))

# Integrator
integrator = mm.LangevinIntegrator(300*unit.kelvin, 1.0/unit.picosecond, 0.002*unit.picosecond)

# Use GPU if available
try:
    platform = mm.Platform.getPlatformByName('CUDA')
    print("Using CUDA GPU")
except:
    try:
        platform = mm.Platform.getPlatformByName('OpenCL')
        print("Using OpenCL")
    except:
        platform = mm.Platform.getPlatformByName('CPU')
        print("Using CPU")

# Create simulation
simulation = app.Simulation(modeller.topology, system, integrator, platform)
simulation.context.setPositions(modeller.positions)

# Minimize
print("\nMinimizing energy...")
simulation.minimizeEnergy(maxIterations=1000)
print("Minimization complete!")

# Add reporters
simulation.reporters.append(
    app.StateDataReporter('simulation.log', 1000, step=True, time=True, 
                         potentialEnergy=True, temperature=True)
)
simulation.reporters.append(
    app.DCDReporter('trajectory.dcd', 1000)
)

# Run simulation
print("\n" + "="*60)
print("Running 1 ns simulation...")
print("="*60)
simulation.step(500000)

print("\n✅ Simulation complete!")

# Save final structure
with open('final_complex.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("Final structure saved: final_complex.pdb")

print("\nFiles created:")
print("  - simulation.log")
print("  - trajectory.dcd")
print("  - final_complex.pdb")
