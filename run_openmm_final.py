#!/usr/bin/env python3
"""
GPU-Accelerated MD Simulation of HIV Protease with Fixed Residues
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
import os

print("="*60)
print("GPU-Accelerated MD Simulation - HIV Protease (Fixed Residues)")
print("="*60)

# Load fixed structure
pdb_file = "hiv_protease_fixed_residues.pdb"
if not os.path.exists(pdb_file):
    pdb_file = "hiv_protease_simple.pdb"
    if not os.path.exists(pdb_file):
        print("Error: No valid PDB file found!")
        exit(1)

print(f"Loading protein structure from: {pdb_file}")
pdb = app.PDBFile(pdb_file)

print(f"Protein has {pdb.topology.getNumAtoms()} atoms")
print(f"Protein has {pdb.topology.getNumResidues()} residues")

# Show residue names to verify
print("\nFirst 10 residues:")
for i, res in enumerate(pdb.topology.residues()):
    if i >= 10:
        break
    print(f"  {i}: {res.name}")

# Force field
forcefield = app.ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# Add missing hydrogens if needed
modeller = app.Modeller(pdb.topology, pdb.positions)
print("\nChecking for missing hydrogens...")
modeller.addHydrogens(forcefield)
print(f"After adding hydrogens: {modeller.topology.getNumAtoms()} atoms")

# Create system
print("\nCreating system...")
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

# Use GPU
platforms = {p.getName(): p for p in mm.Platform.getPlatforms()}
print(f"Available platforms: {list(platforms.keys())}")

if 'CUDA' in platforms:
    platform = platforms['CUDA']
    print("✅ Using CUDA GPU acceleration!")
    # Set precision for better performance
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
print("Energy minimization complete!")

# Add reporters
simulation.reporters.append(
    app.StateDataReporter(
        'md_output.log', 1000,
        step=True,
        time=True,
        potentialEnergy=True,
        kineticEnergy=True,
        temperature=True,
        volume=True,
        density=True
    )
)

simulation.reporters.append(
    app.DCDReporter('trajectory.dcd', 1000)
)

# Run simulation
print("\n" + "="*60)
print("Running 1 ns simulation...")
print("This will take about 15-20 minutes on GPU...")
print("="*60)

simulation.step(500000)  # 1 ns at 2 fs steps

print("✅ Simulation complete!")

# Analyze trajectory
print("\n📊 Analyzing trajectory...")

if os.path.exists('trajectory.dcd'):
    traj = md.load('trajectory.dcd', top=pdb_file)
    
    # RMSD
    protein_atoms = traj.topology.select('protein')
    if len(protein_atoms) == 0:
        protein_atoms = traj.topology.select('backbone')
    rmsd = md.rmsd(traj, traj[0], atom_indices=protein_atoms)
    time_ns = np.arange(len(rmsd)) * (traj.timestep / 1000)
    
    # RMSF
    rmsf = md.rmsf(traj, traj[0], atom_indices=protein_atoms)
    
    # Radius of gyration
    rg = md.compute_rg(traj, atom_indices=protein_atoms)
    
    # Create plots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('HIV Protease MD Analysis (GPU)', fontsize=14)
    
    # RMSD
    axes[0,0].plot(time_ns, rmsd, 'b-', linewidth=1.5)
    axes[0,0].set_xlabel('Time (ns)')
    axes[0,0].set_ylabel('RMSD (nm)')
    axes[0,0].set_title('Protein RMSD')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].axhline(y=np.mean(rmsd), color='r', linestyle='--', alpha=0.5, label=f'Mean: {np.mean(rmsd):.3f}')
    axes[0,0].legend()
    
    # RMSF
    residues = np.unique([a.residue.index for a in traj.topology.atoms if a.index in protein_atoms])
    axes[0,1].plot(residues, rmsf[:len(residues)], 'r-', linewidth=1.5)
    axes[0,1].set_xlabel('Residue Number')
    axes[0,1].set_ylabel('RMSF (nm)')
    axes[0,1].set_title('Residue Fluctuations')
    axes[0,1].grid(True, alpha=0.3)
    
    # Rg
    axes[1,0].plot(time_ns, rg, 'g-', linewidth=1.5)
    axes[1,0].set_xlabel('Time (ns)')
    axes[1,0].set_ylabel('Rg (nm)')
    axes[1,0].set_title('Radius of Gyration')
    axes[1,0].grid(True, alpha=0.3)
    
    # RMSD histogram
    axes[1,1].hist(rmsd, bins=50, color='blue', alpha=0.7, edgecolor='black')
    axes[1,1].set_xlabel('RMSD (nm)')
    axes[1,1].set_ylabel('Frequency')
    axes[1,1].set_title('RMSD Distribution')
    axes[1,1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('hiv_md_analysis.png', dpi=150)
    plt.close()
    
    # Report
    print("\n" + "="*60)
    print("📈 Analysis Results:")
    print("="*60)
    print(f"RMSD: {np.mean(rmsd):.3f} ± {np.std(rmsd):.3f} nm")
    print(f"RMSF: {np.mean(rmsf[:len(residues)]):.3f} ± {np.std(rmsf[:len(residues)]):.3f} nm")
    print(f"Rg:   {np.mean(rg):.3f} ± {np.std(rg):.3f} nm")
    
    # Stability assessment
    if np.mean(rmsd) < 0.2:
        status = "Excellent - very stable"
    elif np.mean(rmsd) < 0.3:
        status = "Good - stable"
    elif np.mean(rmsd) < 0.4:
        status = "Moderate - partially stable"
    else:
        status = "Unstable - consider more equilibration"
    
    print(f"\nStability assessment: {status}")
    print("\n✅ Plot saved: hiv_md_analysis.png")
else:
    print("Trajectory file not found!")

# Save final structure
with open('final_structure.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("✅ Final structure saved: final_structure.pdb")

print("\n✨ Simulation complete! Check hiv_md_analysis.png for results.")
