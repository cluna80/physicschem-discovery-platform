#!/usr/bin/env python3
"""
GPU-Accelerated MD Simulation - HIV Protease in Water Box
Proper solvated system with periodic boundaries
"""

import openmm as mm
import openmm.app as app
import openmm.unit as unit
import mdtraj as md
import numpy as np
import matplotlib.pyplot as plt
import os

print("="*60)
print("GPU-Accelerated MD Simulation - HIV Protease in Water")
print("="*60)

# Load structure
pdb_file = "hiv_protease_clean_fixed.pdb"
if not os.path.exists(pdb_file):
    print(f"Error: {pdb_file} not found!")
    print("Available PDB files:")
    for f in os.listdir('.'):
        if f.endswith('.pdb'):
            print(f"  - {f}")
    exit(1)

print(f"Loading: {pdb_file}")
pdb = app.PDBFile(pdb_file)

print(f"Protein atoms: {pdb.topology.getNumAtoms()}")
print(f"Protein residues: {pdb.topology.getNumResidues()}")

# Force field
forcefield = app.ForceField('amber14-all.xml', 'amber14/tip3p.xml')

# Add hydrogens
print("\nAdding missing hydrogens...")
modeller = app.Modeller(pdb.topology, pdb.positions)
modeller.addHydrogens(forcefield)
print(f"After adding H: {modeller.topology.getNumAtoms()} atoms")

# Add water box
print("\nAdding water box...")
modeller.addSolvent(forcefield, padding=1.0*unit.nanometer)
print(f"After solvation: {modeller.topology.getNumAtoms()} atoms")

# Get box size
box_vectors = modeller.topology.getPeriodicBoxVectors()
box_size = box_vectors[0][0] / unit.nanometer
print(f"Box size: {box_size:.2f} nm")

# Create system with periodic boundaries
print("\nCreating system with periodic boundaries...")
system = forcefield.createSystem(
    modeller.topology,
    nonbondedMethod=app.PME,
    nonbondedCutoff=1.0*unit.nanometer,
    constraints=app.HBonds,
    rigidWater=True
)

# Add barostat for constant pressure
print("Adding barostat...")
system.addForce(mm.MonteCarloBarostat(1*unit.bar, 300*unit.kelvin))

# Integrator
integrator = mm.LangevinIntegrator(
    300*unit.kelvin,
    1.0/unit.picosecond,
    0.002*unit.picosecond
)

# Use GPU - fix the platform detection
print("\nChecking available platforms...")
platform_names = ['CUDA', 'OpenCL', 'CPU']
platform = None

for name in platform_names:
    try:
        platform = mm.Platform.getPlatformByName(name)
        print(f"✅ Found platform: {name}")
        break
    except Exception as e:
        print(f"⚠️ {name} not available: {e}")

if platform is None:
    print("No suitable platform found!")
    exit(1)

if platform.getName() == 'CUDA':
    print("✅ Using CUDA GPU acceleration!")
    platform.setPropertyDefaultValue('Precision', 'mixed')
elif platform.getName() == 'OpenCL':
    print("✅ Using OpenCL acceleration!")
else:
    print("⚠️ Using CPU (slower)")

# Create simulation
print("\nCreating simulation...")
simulation = app.Simulation(modeller.topology, system, integrator, platform)
simulation.context.setPositions(modeller.positions)

# Minimize
print("Minimizing energy...")
simulation.minimizeEnergy(maxIterations=1000)
print("Minimization complete!")

# Add reporters
simulation.reporters.append(
    app.StateDataReporter(
        'md_output.log', 1000,
        step=True, time=True,
        potentialEnergy=True, kineticEnergy=True,
        temperature=True, volume=True, density=True
    )
)
simulation.reporters.append(app.DCDReporter('trajectory.dcd', 1000))

# Run simulation
print("\n" + "="*60)
print(f"Running 1 ns simulation on {platform.getName()}...")
print(f"System: {modeller.topology.getNumAtoms()} atoms in {box_size:.2f} nm box")
print("="*60)

simulation.step(500000)  # 1 ns at 2 fs steps

print("✅ Simulation complete!")

# Analyze trajectory
print("\n📊 Analyzing trajectory...")

if os.path.exists('trajectory.dcd'):
    try:
        # Load trajectory
        traj = md.load('trajectory.dcd', top=pdb_file)
        
        # Select protein atoms
        protein_atoms = traj.topology.select('protein')
        if len(protein_atoms) == 0:
            protein_atoms = traj.topology.select('backbone')
        
        if len(protein_atoms) > 0:
            # RMSD
            rmsd = md.rmsd(traj, traj[0], atom_indices=protein_atoms)
            time_ns = np.arange(len(rmsd)) * (traj.timestep / 1000)
            
            # RMSF
            rmsf = md.rmsf(traj, traj[0], atom_indices=protein_atoms)
            
            # Radius of gyration
            rg = md.compute_rg(traj, atom_indices=protein_atoms)
            
            # Get residues
            residues = np.unique([a.residue.index for a in traj.topology.atoms if a.index in protein_atoms])
            
            # Create plots
            fig, axes = plt.subplots(2, 2, figsize=(12, 10))
            fig.suptitle('HIV Protease MD Analysis (Solvated)', fontsize=14)
            
            # RMSD
            axes[0,0].plot(time_ns, rmsd, 'b-', lw=1.5)
            axes[0,0].set_xlabel('Time (ns)')
            axes[0,0].set_ylabel('RMSD (nm)')
            axes[0,0].set_title('Protein RMSD')
            axes[0,0].grid(True, alpha=0.3)
            axes[0,0].axhline(y=np.mean(rmsd), color='r', ls='--', 
                             label=f'Mean: {np.mean(rmsd):.3f} nm')
            axes[0,0].legend()
            
            # RMSF
            axes[0,1].plot(residues, rmsf[:len(residues)], 'r-', lw=1.5)
            axes[0,1].set_xlabel('Residue Number')
            axes[0,1].set_ylabel('RMSF (nm)')
            axes[0,1].set_title('Residue Fluctuations')
            axes[0,1].grid(True, alpha=0.3)
            
            # Highlight flap region (typical residues 43-58)
            axes[0,1].axvspan(43, 58, alpha=0.2, color='yellow', label='Flap region')
            axes[0,1].legend()
            
            # Radius of gyration
            axes[1,0].plot(time_ns, rg, 'g-', lw=1.5)
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
            
            # Print results
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
            
            # Flap flexibility
            flap_region = [r for r in residues if 43 <= r <= 58]
            if flap_region:
                flap_rmsf = np.mean([rmsf[i] for i, r in enumerate(residues) if r in flap_region])
                print(f"Flap region RMSF: {flap_rmsf:.3f} nm")
            
            print("\n✅ Plot saved: hiv_md_analysis.png")
        else:
            print("No protein atoms found for analysis")
            
    except Exception as e:
        print(f"Analysis error: {e}")
        print("Continuing...")
else:
    print("Trajectory file not found!")

# Save final structure
print("\nSaving final structures...")
with open('final_structure.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("✅ Final structure saved: final_structure.pdb")

with open('solvated_system.pdb', 'w') as f:
    app.PDBFile.writeFile(
        simulation.topology,
        simulation.context.getState(getPositions=True).getPositions(),
        f
    )
print("✅ Solvated system saved: solvated_system.pdb")

print("\n" + "="*60)
print("✨ Simulation complete!")
print("Files created:")
print("  - md_output.log: Simulation log")
print("  - trajectory.dcd: Trajectory file")
print("  - hiv_md_analysis.png: Analysis plots")
print("  - final_structure.pdb: Final protein structure")
print("  - solvated_system.pdb: Complete system with water")
print("="*60)
