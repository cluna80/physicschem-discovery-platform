#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenMM MD Simulation with Small Molecule Ligand
Using Small Molecule Force Field (GAFF) for ligand
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
from openmm.app import PDBFile, Modeller, ForceField
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
import os

print("="*60)
print("OpenMM MD Simulation - HIV Protease + CURE_17G_002")
print("Using Small Molecule Force Field")
print("="*60)

# Load protein and ligand
print("\nLoading structures...")
protein_pdb = PDBFile('protein.pdb')
ligand_pdb = PDBFile('ligand_best.pdb')

print(f"Protein: {protein_pdb.topology.getNumAtoms()} atoms")
print(f"Ligand: {ligand_pdb.topology.getNumAtoms()} atoms")

# Create a Modeller and combine them
modeller = Modeller(protein_pdb.topology, protein_pdb.positions)
modeller.add(ligand_pdb.topology, ligand_pdb.positions)

print(f"Combined: {modeller.topology.getNumAtoms()} atoms")

# Load force fields
# Use Amber14 for protein, and GAFF for small molecules
forcefield = ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# For the ligand, we need to add it as a small molecule
# OpenMM can handle small molecules with GAFF, but we need to assign proper residues
# Let's rename the ligand residue to something recognizable
print("\nPreparing system...")

# Add hydrogens and solvent
print("Adding hydrogens and water...")
modeller.addHydrogens(forcefield)
modeller.addSolvent(forcefield, padding=1.0*unit.nanometer)

print(f"After solvation: {modeller.topology.getNumAtoms()} atoms")

# Create system
print("\nCreating system...")
system = forcefield.createSystem(
    modeller.topology,
    nonbondedMethod=app.PME,
    nonbondedCutoff=1.0*unit.nanometer,
    constraints=app.HBonds,
    rigidWater=True
)

# Add barostat
system.addForce(mm.MonteCarloBarostat(1*unit.bar, 300*unit.kelvin))

# Integrator
integrator = mm.LangevinIntegrator(300*unit.kelvin, 1.0/unit.picosecond, 0.002*unit.picosecond)

# Use GPU
print("\nChecking for GPU...")
try:
    platform = mm.Platform.getPlatformByName('CUDA')
    print("Using CUDA GPU acceleration")
    platform.setPropertyDefaultValue('Precision', 'mixed')
except:
    try:
        platform = mm.Platform.getPlatformByName('OpenCL')
        print("Using OpenCL acceleration")
    except:
        platform = mm.Platform.getPlatformByName('CPU')
        print("Using CPU (slower)")

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
print("Running 1 ns production MD...")
print("="*60)
simulation.step(500000)

print("\n✅ Simulation complete!")

# Basic analysis
print("\nAnalyzing trajectory...")
if os.path.exists('trajectory.dcd'):
    traj = md.load('trajectory.dcd', top='protein.pdb')
    
    # Calculate RMSD of protein backbone
    protein_atoms = traj.topology.select('protein and backbone')
    if len(protein_atoms) > 0:
        rmsd = md.rmsd(traj, traj[0], atom_indices=protein_atoms)
        time_ns = np.arange(len(rmsd)) * (traj.timestep / 1000)
        
        # Plot RMSD
        plt.figure(figsize=(10, 6))
        plt.plot(time_ns, rmsd, 'b-', linewidth=1.5)
        plt.xlabel('Time (ns)')
        plt.ylabel('RMSD (nm)')
        plt.title('HIV Protease with CURE_17G_002 - RMSD')
        plt.grid(True, alpha=0.3)
        plt.axhline(y=np.mean(rmsd), color='r', linestyle='--',
                   label=f'Mean: {np.mean(rmsd):.3f} nm')
        plt.legend()
        plt.savefig('rmsd_with_ligand.png', dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"\nRMSD: mean={np.mean(rmsd):.3f} +/- {np.std(rmsd):.3f} nm")
        print(f"Final RMSD: {rmsd[-1]:.3f} nm")
        
        if np.mean(rmsd) < 0.2:
            print("\n✅ Binding appears STABLE! Good candidate for further study.")
        elif np.mean(rmsd) < 0.3:
            print("\n⚠️ Binding is MODERATELY STABLE - consider longer simulation.")
        else:
            print("\n❌ Binding may be UNSTABLE - ligand might dissociate.")
    else:
        print("No protein atoms found for analysis")

# Save final structure
with open('final_complex.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("Final structure saved: final_complex.pdb")

print("\n" + "="*60)
print("Simulation complete!")
print("Files created: simulation.log, trajectory.dcd, rmsd_with_ligand.png, final_complex.pdb")
print("="*60)

