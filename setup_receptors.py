# setup_receptors.py
# Run this ONCE before starting the drug discovery lab.
# Downloads real protein structures from RCSB and prepares them for AutoDock Vina.
#
# Requirements:
#   pip install requests biopython meeko
#   AutoDock Vina must be in PATH (vina --version should work)
#
# Usage:
#   python setup_receptors.py

import os
import subprocess
import sys
import requests
import time

# ============================================================
# TARGET RECEPTORS — PDB IDs and binding box coordinates
# Boxes manually curated from literature / known binding sites
# ============================================================

RECEPTORS = {
    "HIV Protease": {
        "pdb_id": "1HVR",
        "center": (-1.3, 2.0, -0.5),
        "size":   (22, 22, 22),
        "chain_keep": "AB",
        "note": "HIV-1 protease with ritonavir — flap region binding site"
    },
    "EGFR (Cancer)": {
        "pdb_id": "1M17",
        "center": (3.0, -1.5, 7.0),
        "size":   (25, 25, 25),
        "chain_keep": "A",
        "note": "EGFR kinase domain — ATP binding site"
    },
    "BRAF (Melanoma)": {
        "pdb_id": "5J18",
        "center": (-3.0, 10.5, -5.0),
        "size":   (22, 22, 22),
        "chain_keep": "A",
        "note": "BRAF V600E — DFG-out inhibitor binding site"
    },
    "JAK (Arthritis)": {
        "pdb_id": "4E4L",
        "center": (0.5, -2.0, 4.5),
        "size":   (22, 22, 22),
        "chain_keep": "A",
        "note": "JAK1 kinase domain — ATP site"
    },
    "COX-2 (Inflammation)": {
        "pdb_id": "5IKR",
        "center": (21.0, -5.0, 14.0),
        "size":   (20, 20, 20),
        "chain_keep": "A",
        "note": "COX-2 with celecoxib — active site channel"
    },
    "HMG-CoA (Cholesterol)": {
        "pdb_id": "1HWK",
        "center": (18.0, 40.0, 15.0),
        "size":   (22, 22, 22),
        "chain_keep": "A",
        "note": "HMG-CoA reductase — statin binding site"
    },
    "ACE (Blood Pressure)": {
        "pdb_id": "1O86",
        "center": (36.5, 33.0, 31.0),
        "size":   (22, 22, 22),
        "chain_keep": "A",
        "note": "ACE — active site with zinc"
    },
}

RECEPTOR_DIR = "receptors"
os.makedirs(RECEPTOR_DIR, exist_ok=True)

# ============================================================
# STEP 1 — Check dependencies
# ============================================================

def check_dep(cmd, name, install_hint):
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"  ✅ {name} found")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"  ❌ {name} not found — {install_hint}")
        return False

print("\n" + "="*60)
print("RECEPTOR SETUP — Quantum Drug Discovery Lab")
print("="*60)

# Check for IBM token early so user knows quantum status
import os as _os
_ibm_token = _os.environ.get('IBM_QUANTUM_TOKEN') or _os.environ.get('QISKIT_IBM_TOKEN')
if _ibm_token:
    print(f"\n✅ IBM Quantum token found in environment ({len(_ibm_token)} chars)")
else:
    print("\n⚠️  IBM_QUANTUM_TOKEN not set — quantum search will use local simulator")
    print("   To enable real IBM hardware:")
    print("   Windows: set IBM_QUANTUM_TOKEN=your_token_here")
    print("   Then restart this script")
print("\nChecking dependencies...")

vina_ok  = check_dep(["vina", "--version"], "AutoDock Vina", "install from https://vina.scripps.edu/")
obabel_ok = check_dep(["obabel", "--version"], "Open Babel",
                      "conda install -c conda-forge openbabel  OR  winget install OpenBabel")

if not vina_ok:
    print("\n❌ AutoDock Vina is required. Exiting.")
    sys.exit(1)

# Try meeko as alternative to obabel for PDBQT conversion
meeko_ok = False
try:
    import meeko
    meeko_ok = True
    print("  ✅ Meeko found (will use for ligand prep)")
except ImportError:
    print("  ⚠️  Meeko not found — pip install meeko")

if not obabel_ok and not meeko_ok:
    print("\n⚠️  Need either Open Babel or Meeko for PDBQT conversion.")
    print("   Install: pip install meeko")
    sys.exit(1)

# ============================================================
# STEP 2 — Download PDB files from RCSB
# ============================================================

print("\nDownloading receptor structures from RCSB PDB...")

def download_pdb(pdb_id, out_path):
    if os.path.exists(out_path):
        print(f"  ✅ {pdb_id} already exists, skipping")
        return True
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(out_path, 'w') as f:
            f.write(r.text)
        print(f"  ✅ Downloaded {pdb_id} ({len(r.text)//1000}kb)")
        return True
    except Exception as e:
        print(f"  ❌ Failed to download {pdb_id}: {e}")
        return False

for target_name, info in RECEPTORS.items():
    pdb_id = info["pdb_id"]
    pdb_path = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdb")
    download_pdb(pdb_id, pdb_path)
    time.sleep(0.3)  # be polite to RCSB

# ============================================================
# STEP 3 — Prepare receptor PDBQT files
# Removes water, heteroatoms (ligands), adds charges
# ============================================================

print("\nPreparing receptor PDBQT files...")

def clean_pdb(pdb_path, clean_path, chain_keep=None):
    """Remove HETATM, water, keep only specified chains."""
    with open(pdb_path) as f:
        lines = f.readlines()

    kept = []
    for line in lines:
        rec = line[:6].strip()
        # Skip water and heteroatoms (ligands, ions)
        if rec == 'HETATM':
            continue
        if rec == 'ATOM':
            if chain_keep:
                chain = line[21] if len(line) > 21 else ' '
                if chain not in chain_keep:
                    continue
        kept.append(line)

    with open(clean_path, 'w') as f:
        f.writelines(kept)
    return True

def pdb_to_pdbqt_receptor(pdb_path, pdbqt_path):
    """Convert cleaned PDB to PDBQT using Open Babel."""
    try:
        result = subprocess.run(
            ["obabel", pdb_path, "-O", pdbqt_path, "-xr", "--partialcharge", "gasteiger"],
            capture_output=True, text=True, timeout=60
        )
        if os.path.exists(pdbqt_path) and os.path.getsize(pdbqt_path) > 100:
            return True
        # Try without charge flag
        result = subprocess.run(
            ["obabel", pdb_path, "-O", pdbqt_path],
            capture_output=True, text=True, timeout=60
        )
        return os.path.exists(pdbqt_path)
    except Exception as e:
        print(f"    obabel error: {e}")
        return False

for target_name, info in RECEPTORS.items():
    pdb_id = info["pdb_id"]
    pdb_path   = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdb")
    clean_path = os.path.join(RECEPTOR_DIR, f"{pdb_id}_clean.pdb")
    pdbqt_path = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdbqt")

    if not os.path.exists(pdb_path):
        print(f"  ⚠️  {pdb_id}.pdb missing, skipping")
        continue

    if os.path.exists(pdbqt_path):
        print(f"  ✅ {pdb_id}.pdbqt already prepared")
        continue

    # Clean PDB
    clean_pdb(pdb_path, clean_path, chain_keep=info.get("chain_keep"))

    # Convert to PDBQT
    if obabel_ok:
        ok = pdb_to_pdbqt_receptor(clean_path, pdbqt_path)
        if ok:
            size = os.path.getsize(pdbqt_path)
            print(f"  ✅ {pdb_id}.pdbqt prepared ({size//1000}kb)")
        else:
            print(f"  ❌ Failed to prepare {pdb_id}.pdbqt")
    else:
        print(f"  ⚠️  No obabel — {pdb_id}.pdbqt skipped (install obabel)")

# ============================================================
# STEP 4 — Write box config files for each receptor
# ============================================================

print("\nWriting Vina config files...")

for target_name, info in RECEPTORS.items():
    pdb_id = info["pdb_id"]
    pdbqt_path = os.path.join(RECEPTOR_DIR, f"{pdb_id}.pdbqt")
    conf_path  = os.path.join(RECEPTOR_DIR, f"{pdb_id}.conf")

    cx, cy, cz = info["center"]
    sx, sy, sz = info["size"]

    conf = f"""# Vina config for {target_name} ({pdb_id})
# {info['note']}

receptor = {pdbqt_path}

center_x = {cx}
center_y = {cy}
center_z = {cz}

size_x = {sx}
size_y = {sy}
size_z = {sz}

exhaustiveness = 8
num_modes = 3
energy_range = 3
"""
    with open(conf_path, 'w') as f:
        f.write(conf)

print("  ✅ Config files written")

# ============================================================
# STEP 5 — Test Vina with a known ligand
# ============================================================

print("\nTesting Vina with a known ligand (aspirin SMILES)...")

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import tempfile

    test_smiles = "CC(=O)Oc1ccccc1C(=O)O"  # aspirin
    mol = Chem.MolFromSmiles(test_smiles)
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)

    with tempfile.NamedTemporaryFile(suffix='.pdb', delete=False, mode='w') as f:
        from rdkit.Chem import rdmolfiles
        writer = rdmolfiles.MolToPDBBlock(mol)
        f.write(writer)
        test_pdb = f.name

    test_pdbqt = test_pdb.replace('.pdb', '.pdbqt')

    if obabel_ok:
        subprocess.run(["obabel", test_pdb, "-O", test_pdbqt, "-xh"],
                       capture_output=True, timeout=30)

        # Test dock against HIV protease
        test_pdb_receptor = os.path.join(RECEPTOR_DIR, "1HVR.pdbqt")
        if os.path.exists(test_pdb_receptor) and os.path.exists(test_pdbqt):
            result = subprocess.run([
                "vina",
                "--receptor", test_pdb_receptor,
                "--ligand", test_pdbqt,
                "--config", os.path.join(RECEPTOR_DIR, "1HVR.conf"),
                "--out", "/tmp/test_out.pdbqt"
            ], capture_output=True, text=True, timeout=60)

            if "VINA RESULT" in result.stdout or "Affinity" in result.stdout:
                print("  ✅ Vina docking test PASSED")
            else:
                print(f"  ⚠️  Vina ran but output unexpected:\n{result.stdout[:300]}")
        else:
            print("  ⚠️  Receptor not ready for test dock yet")

    os.unlink(test_pdb)

except Exception as e:
    print(f"  ⚠️  Test dock skipped: {e}")

# ============================================================
# SUMMARY
# ============================================================

print("\n" + "="*60)
print("SETUP COMPLETE")
print("="*60)
ready = []
missing = []
for target_name, info in RECEPTORS.items():
    pdbqt = os.path.join(RECEPTOR_DIR, f"{info['pdb_id']}.pdbqt")
    if os.path.exists(pdbqt):
        ready.append(target_name)
    else:
        missing.append(target_name)

print(f"\n✅ Ready for real docking ({len(ready)}/{len(RECEPTORS)}):")
for t in ready:
    print(f"   - {t}")
if missing:
    print(f"\n⚠️  Missing PDBQT ({len(missing)}) — install obabel and rerun:")
    for t in missing:
        print(f"   - {t}")

print("""
Next steps:
  1. If any receptors missing: conda install -c conda-forge openbabel
  2. Then rerun: python setup_receptors.py
  3. Then start the lab: python complete_quantum_drug_discovery.py

The lab will automatically use real Vina docking when receptors are ready,
and fall back to QSAR estimates for any missing receptors.
""")
