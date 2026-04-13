#!/bin/bash
# ============================================================
# GROMACS MD Setup — Clean Version
# Run from: gromacs_md_simulation/
# Requires: protein_clean.pdb in the working directory
# ============================================================
set -e  # Stop on first error so you know exactly what failed

FORCE_FIELD="amber99sb-ildn"
WATER_MODEL="tip3p"
BOX_DIST=1.2
ION_CONC=0.15
WORKDIR=$(pwd)

echo "========================================"
echo " GROMACS MD Setup"
echo " Working dir: $WORKDIR"
echo "========================================"

# ── Sanity check ──────────────────────────────────────────────
if [ ! -f "protein_clean.pdb" ]; then
    echo "ERROR: protein_clean.pdb not found in $(pwd)"
    echo "Run this script from the gromacs_md_simulation/ directory."
    exit 1
fi

mkdir -p scripts

# ── Step 0: Create MDP files if they don't exist ──────────────
echo ""
echo "[Step 0] Writing MDP parameter files..."

cat > scripts/ions.mdp << 'MDP'
; ions.mdp — minimal run for genion
integrator  = steep
nsteps      = 0
nstlist     = 1
cutoff-scheme = Verlet
ns-type     = grid
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
MDP

cat > scripts/minim.mdp << 'MDP'
; minim.mdp — energy minimization
integrator  = steep
emtol       = 1000.0
emstep      = 0.01
nsteps      = 50000
nstlist     = 10
cutoff-scheme = Verlet
ns-type     = grid
coulombtype = PME
rcoulomb    = 1.0
rvdw        = 1.0
pbc         = xyz
MDP

cat > scripts/nvt.mdp << 'MDP'
; nvt.mdp — NVT equilibration (100 ps)
define      = -DPOSRES
integrator  = md
dt          = 0.002
nsteps      = 50000
nstvout     = 500
nstfout     = 500
nstlog      = 500
nstxout-compressed = 500
continuation = no
constraint_algorithm = lincs
constraints = h-bonds
lincs_iter  = 1
lincs_order = 4
cutoff-scheme = Verlet
ns-type     = grid
nstlist     = 10
rcoulomb    = 1.0
rvdw        = 1.0
coulombtype = PME
pme_order   = 4
fourierspacing = 0.16
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = no
pbc         = xyz
dispCorr    = EnerPres
gen_vel     = yes
gen_temp    = 300
gen_seed    = -1
MDP

cat > scripts/npt.mdp << 'MDP'
; npt.mdp — NPT equilibration (100 ps)
define      = -DPOSRES
integrator  = md
dt          = 0.002
nsteps      = 50000
nstvout     = 500
nstfout     = 500
nstlog      = 500
nstxout-compressed = 500
continuation = yes
constraint_algorithm = lincs
constraints = h-bonds
lincs_iter  = 1
lincs_order = 4
cutoff-scheme = Verlet
ns-type     = grid
nstlist     = 10
rcoulomb    = 1.0
rvdw        = 1.0
coulombtype = PME
pme_order   = 4
fourierspacing = 0.16
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
refcoord_scaling = com
pbc         = xyz
dispCorr    = EnerPres
gen_vel     = no
MDP

cat > scripts/md.mdp << 'MDP'
; md.mdp — production run (1 ns, adjust nsteps for longer)
integrator  = md
dt          = 0.002
nsteps      = 500000
nstvout     = 5000
nstfout     = 5000
nstlog      = 5000
nstxout-compressed = 5000
continuation = yes
constraint_algorithm = lincs
constraints = h-bonds
lincs_iter  = 1
lincs_order = 4
cutoff-scheme = Verlet
ns-type     = grid
nstlist     = 10
rcoulomb    = 1.0
rvdw        = 1.0
coulombtype = PME
pme_order   = 4
fourierspacing = 0.16
tcoupl      = V-rescale
tc-grps     = Protein Non-Protein
tau_t       = 0.1 0.1
ref_t       = 300 300
pcoupl      = Parrinello-Rahman
pcoupltype  = isotropic
tau_p       = 2.0
ref_p       = 1.0
compressibility = 4.5e-5
pbc         = xyz
dispCorr    = EnerPres
gen_vel     = no
MDP

echo "  MDP files written to scripts/"

# ── Step 1: Protein topology ───────────────────────────────────
echo ""
echo "[Step 1] Generating protein topology..."

# Force field selection: amber99sb-ildn = option 1 in most builds
# -ignh ignores existing hydrogens (GROMACS will add its own)
echo "1" | gmx pdb2gmx \
    -f protein_clean.pdb \
    -o protein.gro \
    -p topol.top \
    -i posre.itp \
    -ignh \
    -ff ${FORCE_FIELD} \
    -water ${WATER_MODEL}

echo "  → protein.gro, topol.top, posre.itp generated"

# ── Step 2: Define simulation box ─────────────────────────────
echo ""
echo "[Step 2] Defining cubic box (${BOX_DIST} nm from protein)..."

gmx editconf \
    -f protein.gro \
    -o box.gro \
    -c \
    -d ${BOX_DIST} \
    -bt cubic

echo "  → box.gro generated"

# ── Step 3: Solvate ───────────────────────────────────────────
echo ""
echo "[Step 3] Solvating with TIP3P water..."

gmx solvate \
    -cp box.gro \
    -cs spc216.gro \
    -o solv.gro \
    -p topol.top

echo "  → solv.gro generated"

# ── Step 4: Add ions ──────────────────────────────────────────
echo ""
echo "[Step 4] Adding ions (${ION_CONC} M NaCl, neutralizing)..."

# Pre-process to get ions.tpr
gmx grompp \
    -f scripts/ions.mdp \
    -c solv.gro \
    -p topol.top \
    -o ions.tpr \
    -maxwarn 1

# Replace SOL molecules with ions; "13" = SOL group (may vary — check your output)
echo "SOL" | gmx genion \
    -s ions.tpr \
    -o solv_ions.gro \
    -p topol.top \
    -pname NA \
    -nname CL \
    -neutral \
    -conc ${ION_CONC}

echo "  → solv_ions.gro generated"

# ── Step 5: Energy minimization ───────────────────────────────
echo ""
echo "[Step 5] Energy minimization..."

gmx grompp \
    -f scripts/minim.mdp \
    -c solv_ions.gro \
    -p topol.top \
    -o em.tpr

gmx mdrun -v -deffnm em

echo "  → em.gro, em.edr generated"

# ── Step 6: NVT equilibration ─────────────────────────────────
echo ""
echo "[Step 6] NVT equilibration (100 ps)..."

gmx grompp \
    -f scripts/nvt.mdp \
    -c em.gro \
    -r em.gro \
    -p topol.top \
    -o nvt.tpr

gmx mdrun -v -deffnm nvt

echo "  → nvt.gro, nvt.edr generated"

# ── Step 7: NPT equilibration ─────────────────────────────────
echo ""
echo "[Step 7] NPT equilibration (100 ps)..."

gmx grompp \
    -f scripts/npt.mdp \
    -c nvt.gro \
    -r nvt.gro \
    -t nvt.cpt \
    -p topol.top \
    -o npt.tpr

gmx mdrun -v -deffnm npt

echo "  → npt.gro, npt.edr generated"

# ── Step 8: Production MD ─────────────────────────────────────
echo ""
echo "[Step 8] Production MD (1 ns)..."

gmx grompp \
    -f scripts/md.mdp \
    -c npt.gro \
    -t npt.cpt \
    -p topol.top \
    -o md.tpr

gmx mdrun -v -deffnm md

echo ""
echo "========================================"
echo " Simulation complete!"
echo " Key output files:"
echo "   md.xtc  — trajectory"
echo "   md.edr  — energy"
echo "   md.gro  — final structure"
echo "========================================"
