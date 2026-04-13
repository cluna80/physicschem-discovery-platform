# ===========================================
# VINA DOCKING PIPELINE
# HIV-1 Integrase Lead Candidates
# ===========================================

import os
import sys
import urllib.request
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

try:
    from meeko import MoleculePreparation, PDBQTMolecule
    from vina import Vina
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install vina meeko")
    sys.exit(1)

# ===========================================
# LEAD CANDIDATES
# ===========================================

LEADS = {
    "HIV-022": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1",
    "HIV-020": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1",
    "HIV-010": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1",
}

# Reference drug for comparison
REFERENCES = {
    "Dolutegravir": "O=C1/C(=C/[C@@H]2CC(=C(C(=O)O)C2=O)c2ccc(F)cc2)CN1Cc1ccc(F)cc1",
}

WORK_DIR = Path("docking_results")
WORK_DIR.mkdir(exist_ok=True)

# ===========================================
# HIV-1 INTEGRASE RECEPTOR
# PDB: 3L2T (Raltegravir-bound, 2.2A resolution)
# ===========================================

PDB_ID = "3L2T"
RECEPTOR_PDB = WORK_DIR / f"{PDB_ID}.pdb"
RECEPTOR_PDBQT = WORK_DIR / f"{PDB_ID}_receptor.pdbqt"

# Docking box centered on INSTI binding site (Mg2+ chelation site)
# Coordinates from 3L2T active site
BOX_CENTER = [13.0, 4.5, 12.0]
BOX_SIZE   = [20.0, 20.0, 20.0]

# ===========================================
# STEP 1: DOWNLOAD RECEPTOR
# ===========================================

def download_receptor():
    if RECEPTOR_PDB.exists():
        print(f"‚úÖ Receptor already downloaded: {RECEPTOR_PDB}")
        return True
    
    print(f"Ì≥• Downloading HIV-1 Integrase ({PDB_ID}) from RCSB...")
    url = f"https://files.rcsb.org/download/{PDB_ID}.pdb"
    try:
        urllib.request.urlretrieve(url, RECEPTOR_PDB)
        print(f"‚úÖ Downloaded: {RECEPTOR_PDB}")
        return True
    except Exception as e:
        print(f"‚ùå Download failed: {e}")
        return False

# ===========================================
# STEP 2: PREPARE RECEPTOR (strip water/ligand)
# ===========================================

def prepare_receptor():
    if RECEPTOR_PDBQT.exists():
        print(f"‚úÖ Receptor PDBQT ready: {RECEPTOR_PDBQT}")
        return True

    print("Ì¥ß Preparing receptor (stripping waters, heteroatoms)...")
    
    # Read and strip non-protein lines
    with open(RECEPTOR_PDB, 'r') as f:
        lines = f.readlines()
    
    protein_lines = []
    for line in lines:
        record = line[:6].strip()
        if record in ("ATOM", "TER", "END"):
            protein_lines.append(line)
        elif record == "HETATM":
            # Keep Mg2+ for reference but skip everything else
            if "MG" in line:
                protein_lines.append(line)
    
    clean_pdb = WORK_DIR / f"{PDB_ID}_clean.pdb"
    with open(clean_pdb, 'w') as f:
        f.writelines(protein_lines)
    
    # Use Vina's built-in receptor prep
    v = Vina(sf_name='vina', verbosity=0)
    try:
        v.set_receptor(str(clean_pdb))
        v.write_pdbqt_file(str(RECEPTOR_PDBQT), is_receptor=True)
        print(f"‚úÖ Receptor prepared: {RECEPTOR_PDBQT}")
        return True
    except Exception as e:
        print(f"‚ö†Ô∏è  Vina receptor prep failed: {e}")
        print("    Trying fallback: saving clean PDB as PDBQT...")
        # Fallback: rename clean pdb as pdbqt (Vina can sometimes handle it)
        import shutil
        shutil.copy(clean_pdb, RECEPTOR_PDBQT)
        return True

# ===========================================
# STEP 3: PREPARE LIGAND PDBQT
# ===========================================

def smiles_to_pdbqt(name, smiles):
    out_path = WORK_DIR / f"{name}.pdbqt"
    if out_path.exists():
        return str(out_path)

    print(f"  Ì∑™ Preparing ligand: {name}")
    
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"  ‚ùå Invalid SMILES for {name}")
        return None
    
    # Generate 3D coords
    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if result != 0:
        print(f"  ‚ö†Ô∏è  3D embedding failed for {name}, trying fallback...")
        AllChem.EmbedMolecule(mol, randomSeed=42)
    
    AllChem.MMFFOptimizeMolecule(mol)
    
    # Meeko prep
    try:
        preparator = MoleculePreparation()
        preparator.prepare(mol)
        pdbqt_string = preparator.write_pdbqt_string()
        
        with open(out_path, 'w') as f:
            f.write(pdbqt_string)
        
        print(f"  ‚úÖ Ligand ready: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"  ‚ùå Meeko failed for {name}: {e}")
        return None

# ===========================================
# STEP 4: RUN DOCKING
# ===========================================

def dock_ligand(name, ligand_pdbqt):
    out_pdbqt = WORK_DIR / f"{name}_docked.pdbqt"
    
    print(f"\n  ‚öõÔ∏è  Docking {name}...")
    
    try:
        v = Vina(sf_name='vina', verbosity=0)
        v.set_receptor(str(RECEPTOR_PDBQT))
        v.set_ligand_from_file(ligand_pdbqt)
        v.compute_vina_maps(
            center=BOX_CENTER,
            box_size=BOX_SIZE
        )
        
        # Exhaustiveness=16 is good balance of speed vs accuracy
        v.dock(exhaustiveness=16, n_poses=5)
        v.write_poses(str(out_pdbqt), n_poses=5, overwrite=True)
        
        energies = v.energies(n_poses=5)
        best_affinity = energies[0][0]  # kcal/mol
        
        print(f"  ÌæØ Best affinity: {best_affinity:.2f} kcal/mol")
        print(f"  Ì≥ä Top 5 poses: {[f'{e[0]:.2f}' for e in energies]}")
        
        return best_affinity, energies
        
    except Exception as e:
        print(f"  ‚ùå Docking failed for {name}: {e}")
        return None, None

# ===========================================
# STEP 5: REPORT
# ===========================================

def print_report(results):
    print("\n" + "="*65)
    print("ÌøÜ DOCKING RESULTS - HIV-1 Integrase (3L2T)")
    print("="*65)
    print(f"{'Compound':<15} {'Affinity (kcal/mol)':<22} {'Assessment'}")
    print("-"*65)
    
    # Sort by affinity (more negative = better)
    sorted_results = sorted(
        [(n, a) for n, a in results.items() if a is not None],
        key=lambda x: x[1]
    )
    
    for name, affinity in sorted_results:
        if affinity <= -9.0:
            assessment = "Ì¥• Excellent"
        elif affinity <= -7.5:
            assessment = "‚úÖ Good"
        elif affinity <= -6.0:
            assessment = "‚ö†Ô∏è  Moderate"
        else:
            assessment = "‚ùå Weak"
        print(f"{name:<15} {affinity:<22.2f} {assessment}")
    
    print("-"*65)
    print("Reference: Dolutegravir typically -10 to -12 kcal/mol vs Integrase")
    print(f"\nÌ≥Å Docked poses saved to: {WORK_DIR}/")
    print("    Open *_docked.pdbqt in PyMOL or UCSF Chimera to visualize")

# ===========================================
# MAIN
# ===========================================

if __name__ == "__main__":
    print("="*65)
    print("Ì∑¨ HIV-1 INTEGRASE DOCKING PIPELINE")
    print("   AutoDock Vina | Receptor: 3L2T")
    print("="*65 + "\n")
    
    # Step 1: Receptor
    if not download_receptor():
        sys.exit(1)
    
    if not prepare_receptor():
        sys.exit(1)
    
    # Step 2: Dock all leads + reference
    all_compounds = {**LEADS, **REFERENCES}
    results = {}
    
    print("\nÌ≥ã Preparing and docking compounds...")
    print("-"*65)
    
    for name, smiles in all_compounds.items():
        mw = Descriptors.MolWt(Chem.MolFromSmiles(smiles)) if Chem.MolFromSmiles(smiles) else 0
        print(f"\n[{name}] MW={mw:.0f}")
        
        ligand_pdbqt = smiles_to_pdbqt(name, smiles)
        if ligand_pdbqt:
            affinity, poses = dock_ligand(name, ligand_pdbqt)
            results[name] = affinity
        else:
            results[name] = None
    
    # Step 3: Report
    print_report(results)
