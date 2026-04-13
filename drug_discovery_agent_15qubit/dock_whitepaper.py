import sys, json
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

try:
    from meeko import MoleculePreparation, PDBQTWriterLegacy
    from vina import Vina
except ImportError as e:
    print("Missing dep:", e)
    sys.exit(1)

LEADS = {
    "HIV-022": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OCC1CC1",
    "HIV-020": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1OC1CC1c1ccccc1",
    "HIV-010": "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc(F)cc1",
    "Dolutegravir": "O=C1/C(=C/[C@@H]2CC(=C(C(=O)O)C2=O)c2ccc(F)cc2)CN1Cc1ccc(F)cc1",
}

WORK_DIR = Path("whitepaper_docking")
WORK_DIR.mkdir(exist_ok=True)

RECEPTOR_PDBQT = str(WORK_DIR / "3L2T_receptor.pdbqt")
BOX_CENTER = [-38.5, 30.5, -20.8]
BOX_SIZE = [25.0, 25.0, 25.0]

def smiles_to_pdbqt(name, smiles):
    out = WORK_DIR / f"{name}.pdbqt"
    if out.exists():
        return str(out)
    print("  Preparing ligand:", name)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print("  Invalid SMILES:", name)
        return None
    mol = Chem.AddHs(mol)
    res = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if res != 0:
        AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)
    try:
        prep = MoleculePreparation()
        mol_setups = prep.prepare(mol)
        pdbqt_string, is_ok, error = PDBQTWriterLegacy.write_string(mol_setups[0])
        if not is_ok:
            print("  PDBQT write error:", error)
            return None
        with open(out, "w") as f:
            f.write(pdbqt_string)
        print("  Ligand ready:", out)
        return str(out)
    except Exception as e:
        print("  Meeko error for", name, e)
        return None

def dock(name, pdbqt):
    out = WORK_DIR / f"{name}_docked.pdbqt"
    print("  Docking", name)
    try:
        v = Vina(sf_name="vina", verbosity=0)
        v.set_receptor(RECEPTOR_PDBQT)
        v.set_ligand_from_file(pdbqt)
        v.compute_vina_maps(center=BOX_CENTER, box_size=BOX_SIZE)
        v.dock(exhaustiveness=16, n_poses=5)
        v.write_poses(str(out), n_poses=5, overwrite=True)
        energies = v.energies(n_poses=5)
        best = float(energies[0][0])
        all_poses = [float(e[0]) for e in energies]
        print("  Best affinity:", round(best, 2), "kcal/mol")
        print("  All poses:", [round(e, 2) for e in all_poses])
        return best, all_poses
    except Exception as e:
        print("  Docking failed for", name, e)
        return None, None

results = {}
for name, smiles in LEADS.items():
    mol = Chem.MolFromSmiles(smiles)
    mw = Descriptors.MolWt(mol) if mol else 0
    print("\n[" + name + "] MW=" + str(round(mw)))
    pdbqt = smiles_to_pdbqt(name, smiles)
    if pdbqt:
        aff, poses = dock(name, pdbqt)
        results[name] = {"affinity": aff, "all_poses": poses or []}

print("\n" + "="*55)
print("DOCKING RESULTS - HIV-1 Integrase (3L2T)")
print("="*55)
sorted_r = sorted(
    [(n, d) for n, d in results.items() if d["affinity"] is not None],
    key=lambda x: x[1]["affinity"]
)
for name, data in sorted_r:
    aff = data["affinity"]
    tag = "EXCELLENT" if aff <= -9.0 else "GOOD" if aff <= -7.5 else "MODERATE"
    print(f"{name:<20} {aff:.2f} kcal/mol  [{tag}]")
print("-"*55)
print("Reference: Dolutegravir typically -10 to -12 kcal/mol")

out_json = WORK_DIR / "whitepaper_docking_results.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print("Results saved to", out_json)
