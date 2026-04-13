#!/usr/bin/env python3
"""
Simple GPU-Accelerated MD Simulation of HIV Protease (Clean Structure)
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
import os

print("="*60)
print("GPU-Accelerated MD Simulation - HIV Protease (Clean)")
print("="*60)

# Load structure
pdb_file = "hiv_protease_clean_fixed.pdb"
if not os.path.exists(pdb_file):
    print(f"Error: {pdb_file} not found!")
    exit(1)

print(f"Loading: {pdb_file}")
pdb = app.PDBFile(pdb_file)

print(f"Atoms: {pdb.topology.getNumAtoms()}")
print(f"Residues: {pdb.topology.getNumResidues()}")

# Force field
forcefield = app.ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# Add hydrogens
print("\nAdding missing hydrogens...")
modeller = app.Modeller(pdb.topology, pdb.positions)
modeller.addHydrogens(forcefield)
print(f"After adding H: {modeller.topology.getNumAtoms()} atoms")

# Create system
print("Creating system...")
system = forcefield.createSystem(
    modeller.topology,
    nonbondedMethod=app.PME,
    nonbondedCutoff=1.0*unit.nanometer,
    constraints=app.HBonds,
    rigidWater=True
)

# Add barostat for NPT
system.addForce(mm.MonteCarloBarostat(1*unit.bar, 300*unit.kelvin))

# Integrator
integrator = mm.LangevinIntegrator(
    300*unit.kelvin,
    1.0/unit.picosecond,
    0.002*unit.picosecond
)

# Use GPU if available
platforms = {p.getName(): p for p in mm.Platform.getPlatforms()}
print(f"Available platforms: {list(platforms.keys())}")

if 'CUDA' in platforms:
    platform = platforms['CUDA']
    print("✅ Using CUDA GPU acceleration!")
    platform.setPropertyDefaultValue('Precision', 'mixed')
elif 'OpenCL' in platforms:
    platform = platforms['OpenCL']
    print("✅ Using OpenCL acceleration!")
else:
    platform = platforms['CPU']
    print("⚠️ Using CPU (no GPU detected)")

# Create simulation
simulation = app.Simulation(modeller.topology, system, integrator, platform)
simulation.context.setPositions(modeller.positions)

# Minimize
print("\nMinimizing energy...")
simulation.minimizeEnergy(maxIterations=1000)
print("Minimization complete!")

# Add reporters
simulation.reporters.append(
    app.StateDataReporter(
        'md_output.log', 1000,
        step=True, time=True,
        potentialEnergy=True, kineticEnergy=True,
        temperature=True, volume=True
    )
)
simulation.reporters.append(app.DCDReporter('trajectory.dcd', 1000))

# Run
print("\n" + "="*60)
print("Running 1 ns simulation on GPU...")
print("="*60)

simulation.step(500000)  # 1 ns

print("✅ Simulation complete!")

# Analyze
print("\n📊 Analyzing trajectory...")

if os.path.exists('trajectory.dcd'):
    traj = md.load('trajectory.dcd', top=pdb_file)
    
    protein_atoms = traj.topology.select('protein')
    if len(protein_atoms) == 0:
        protein_atoms = traj.topology.select('backbone')
    
    rmsd = md.rmsd(traj, traj[0], atom_indices=protein_atoms)
    time_ns = np.arange(len(rmsd)) * (traj.timestep / 1000)
    
    residues = np.unique([a.residue.index for a in traj.topology.atoms if a.index in protein_atoms])
    rmsf = md.rmsf(traj, traj[0], atom_indices=protein_atoms)
    rg = md.compute_rg(traj, atom_indices=protein_atoms)
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('HIV Protease MD Analysis', fontsize=14)
    
    axes[0,0].plot(time_ns, rmsd, 'b-', lw=1.5)
    axes[0,0].set_xlabel('Time (ns)'); axes[0,0].set_ylabel('RMSD (nm)')
    axes[0,0].set_title('Protein RMSD'); axes[0,0].grid(True, alpha=0.3)
    axes[0,0].axhline(y=np.mean(rmsd), color='r', ls='--', label=f'Mean: {np.mean(rmsd):.3f}')
    axes[0,0].legend()
    
    axes[0,1].plot(residues, rmsf[:len(residues)], 'r-', lw=1.5)
    axes[0,1].set_xlabel('Residue'); axes[0,1].set_ylabel('RMSF (nm)')
    axes[0,1].set_title('Residue Fluctuations'); axes[0,1].grid(True, alpha=0.3)
    
    axes[1,0].plot(time_ns, rg, 'g-', lw=1.5)
    axes[1,0].set_xlabel('Time (ns)'); axes[1,0].set_ylabel('Rg (nm)')
    axes[1,0].set_title('Radius of Gyration'); axes[1,0].grid(True, alpha=0.3)
    
    axes[1,1].hist(rmsd, bins=50, color='blue', alpha=0.7, edgecolor='black')
    axes[1,1].set_xlabel('RMSD (nm)'); axes[1,1].set_ylabel('Frequency')
    axes[1,1].set_title('RMSD Distribution'); axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('hiv_md_analysis.png', dpi=150)
    plt.close()
    
    print("\n" + "="*60)
    print("📈 Analysis Results:")
    print("="*60)
    print(f"RMSD: {np.mean(rmsd):.3f} ± {np.std(rmsd):.3f} nm")
    print(f"RMSF: {np.mean(rmsf[:len(residues)]):.3f} ± {np.std(rmsf[:len(residues)]):.3f} nm")
    print(f"Rg:   {np.mean(rg):.3f} ± {np.std(rg):.3f} nm")
    print("\n✅ Plot saved: hiv_md_analysis.png")

# Save final structure
with open('final_structure.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("✅ Final structure saved: final_structure.pdb")
print("\n✨ Complete!")
