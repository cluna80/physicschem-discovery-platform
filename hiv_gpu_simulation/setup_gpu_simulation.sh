#!/bin/bash
echo "========================================="
echo "Setting up HIV Protease for GPU Simulation"
echo "========================================="

# Use the GPU-enabled GROMACS (once built)
# For now, use system GROMACS for setup, then we'll run with GPU version
GMX_GPU="/usr/local/gromacs-gpu/bin/gmx"

# If GPU version exists, use it for everything
if [ -f "$GMX_GPU" ]; then
    GMX="$GMX_GPU"
    echo "Using GPU-enabled GROMACS for all steps"
else
    GMX="gmx"
    echo "Using system GROMACS for setup (GPU version will be used for MD)"
fi

# 1. Generate topology
echo "Step 1: Generating protein topology..."
echo "1" | $GMX pdb2gmx -f hiv_protease_clean_fixed.pdb -o protein.gro -p topol.top -ignh -ff amber99sb-ildn -water tip3p

# 2. Define box
echo "Step 2: Setting up simulation box..."
echo "0" | $GMX editconf -f protein.gro -o box.gro -c -d 1.0 -bt cubic

# 3. Add water
echo "Step 3: Adding water..."
$GMX solvate -cp box.gro -cs -o solv.gro -p topol.top

# 4. Create ion mdp
cat > ions.mdp << 'MDP'
integrator  = steep
emtol       = 1000.0
emstep      = 0.01
nsteps      = 50000
nstlist     = 1
ns_type     = grid
rlist       = 1.0
coulombtype = cutoff
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
MDP

# 5. Add ions
echo "Step 4: Adding ions to neutralize..."
$GMX grompp -f ions.mdp -c solv.gro -p topol.top -o ions.tpr -maxwarn 1
echo "SOL" | $GMX genion -s ions.tpr -o solv_ions.gro -p topol.top -pname NA -nname CL -neutral -conc 0.15

# 6. Minimization mdp
cat > minim.mdp << 'MDP'
integrator  = steep
emtol       = 1000.0
emstep      = 0.01
nsteps      = 50000
nstlist     = 1
ns_type     = grid
rlist       = 1.0
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
MDP

# 7. Energy minimization
echo "Step 5: Energy minimization..."
$GMX grompp -f minim.mdp -c solv_ions.gro -p topol.top -o em.tpr -maxwarn 1
$GMX mdrun -v -deffnm em

# 8. NPT equilibration mdp
cat > npt.mdp << 'MDP'
title       = NPT equilibration
integrator  = md
dt          = 0.002
nsteps      = 50000
nstxout     = 5000
nstvout     = 5000
nstlog      = 5000
nstenergy   = 5000
nstcalcenergy = 100
nstlist     = 10
ns_type     = grid
rlist       = 1.0
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
gen_vel     = no
constraints = h-bonds
MDP

# 9. NPT equilibration
echo "Step 6: NPT equilibration..."
$GMX grompp -f npt.mdp -c em.gro -p topol.top -o npt.tpr -maxwarn 1
$GMX mdrun -deffnm npt

# 10. Production MD mdp (optimized for GPU)
cat > md_gpu.mdp << 'MDP'
title       = Production MD with GPU
integrator  = md
dt          = 0.002
nsteps      = 500000
nstxout     = 1000
nstvout     = 1000
nstlog      = 1000
nstenergy   = 1000
nstcalcenergy = 100
nstlist     = 10
ns_type     = grid
rlist       = 1.0
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
gen_vel     = no
constraints = h-bonds
DispCorr    = EnerPres
MDP

echo "========================================="
echo "Setup complete!"
echo "System has:"
echo "  Protein: 758 atoms"
echo "  Water: ~22,000 atoms"
echo "  Total: ~23,000 atoms"
echo "========================================="
echo ""
echo "To run with GPU:"
echo "  gmx mdrun -deffnm md -v -gpu_id 0 -nb gpu -pme gpu -bonded cpu -update cpu -ntomp 12"
echo ""
