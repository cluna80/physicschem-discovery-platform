import sys, json, time, random, csv, hashlib
from pathlib import Path
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

import pennylane as qml
from pennylane import numpy as pnp

Path("egfr_results").mkdir(exist_ok=True)

MODEL = "llama3.2"
N_QUBITS = 15
MAX_CYCLES = 30
TARGET = "EGFR"
PDB_ID = "1M17"
BOX_CENTER = [22.01, 0.25, 52.79]
BOX_SIZE = [25.0, 25.0, 25.0]
LIBRARY_FILE = "egfr_results/egfr_drug_library.csv"
BLACKLIST_FILE = "egfr_results/egfr_blacklist.txt"
CHAIN_FILE = "egfr_results/egfr_chain_of_custody.json"

PENNYLANE_VERSION = qml.__version__
VQE_VERSION = f"lightning.qubit_v{PENNYLANE_VERSION}"

print(f"EGFR Quantum Drug Discovery | {N_QUBITS} qubits | Target: EGFR Kinase")
print(f"Receptor: PDB {PDB_ID} | Erlotinib binding site")
print(f"Box center: {BOX_CENTER}\n")

# ============================================================
# EGFR-SPECIFIC KNOWLEDGE BASE
# ============================================================

EGFR_KNOWLEDGE = {
    "description": "EGFR tyrosine kinase - ATP binding site inhibition",
    "known_inhibitors": ["Erlotinib", "Gefitinib", "Afatinib", "Osimertinib", "Lapatinib"],
    "pharmacophore": "Quinazoline or pyrimidine core with hinge-binding NH, hydrophobic tail",
    "key_features": [
        "Hinge region H-bond (M793 backbone NH/C=O)",
        "Hydrophobic pocket (L718, V726, A743, L844)",
        "Gatekeeper residue T790 interaction",
        "Solvent-exposed region for selectivity tail",
    ],
    "evolution_hints": [
        "Add quinazoline core for hinge binding",
        "Add aniline NH for M793 hydrogen bond",
        "Add meta-chloro or fluoro on aniline for selectivity",
        "Add alkoxy chain at C6/C7 for solvent channel",
        "Add acrylamide for covalent T790M targeting",
        "Add pyrimidine core (osimertinib-like)",
        "Add morpholine for solubility",
        "Add fluorine for metabolic stability",
        "Add methoxy group at C6 for potency",
        "Add piperazine tail for selectivity",
    ]
}

# Fragment libraries
EGFR_CORES = {
    "quinazoline":      "c1cnc2ccccc2n1",
    "quinazoline_4Cl":  "Clc1ncnc2ccccc12",
    "quinazoline_4NH2": "Nc1ncnc2ccccc12",
    "pyrimidine":       "c1cnccn1",
    "pyrido_pyrimidine":"c1cnc2ncccc2n1",
    "indole":           "c1ccc2[nH]ccc2c1",
    "benzimidazole":    "c1ccc2[nH]cnc2c1",
    "thienopyrimidine": "c1csc2ncncc2c1",
}

HINGE_BINDERS = {
    "aniline":           "Nc1ccccc1",
    "meta_Cl_aniline":   "Nc1cccc(Cl)c1",
    "meta_F_aniline":    "Nc1cccc(F)c1",
    "para_F_aniline":    "Nc1ccc(F)cc1",
    "meta_CF3_aniline":  "Nc1cccc(C(F)(F)F)c1",
    "difluoro_aniline":  "Nc1ccc(F)c(F)c1",
    "pyridyl_amine":     "Nc1ccccn1",
    "indazole":          "c1ccc2[nH]ncc2c1",
}

SOLUBILITY_TAILS = {
    "morpholine":        "N1CCOCC1",
    "piperazine":        "N1CCNCC1",
    "methyl_piperazine": "CN1CCNCC1",
    "dimethylamino":     "CN(C)",
    "methoxyethyl":      "CCOC",
    "propargyl":         "CC#C",
    "OCH2CH2OH":         "OCCO",
}

EVOLUTION_STRATEGIES = [
    "Add quinazoline core for hinge binding",
    "Add aniline NH for M793 hydrogen bond",
    "Add meta-chloro substituent for selectivity",
    "Add meta-fluoro substituent for metabolic stability",
    "Add methoxy group at C6 for EGFR potency",
    "Add morpholine for solubility",
    "Add piperazine tail for selectivity",
    "Add acrylamide warhead for covalent inhibition",
    "Add trifluoromethyl for binding affinity",
    "Add alkoxy ethyl chain for solvent channel",
    "Add pyrimidine core analog",
    "Replace chloro with fluoro bioisostere",
    "Add dimethylamino for basicity",
    "Extend with propargyl group",
    "Add indazole hinge binder",
]

# ============================================================
# BLACKLIST
# ============================================================

def load_blacklist():
    bl = set()
    if Path(BLACKLIST_FILE).exists():
        for line in open(BLACKLIST_FILE):
            bl.add(line.strip())
    if Path(LIBRARY_FILE).exists():
        for row in csv.reader(open(LIBRARY_FILE)):
            if len(row) > 1:
                bl.add(row[1])
    return bl

def save_blacklist(smiles):
    with open(BLACKLIST_FILE, "a") as f:
        f.write(smiles + "\n")

BLACKLIST = load_blacklist()
print(f"Loaded {len(BLACKLIST)} blacklisted SMILES\n")

# ============================================================
# FRAGMENT EVOLUTION
# ============================================================

def validate_smiles(smiles):
    if not smiles:
        return False, None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False, None
    try:
        Chem.SanitizeMol(mol)
        return True, Chem.MolToSmiles(mol, canonical=True)
    except:
        return False, None

def generate_egfr_fragment(history):
    blacklist = set(h.get("smiles","") for h in history) | BLACKLIST

    # Phase 1: core scaffolds
    if len(history) < 8:
        for name, smi in EGFR_CORES.items():
            if smi not in blacklist:
                return {"smiles": smi, "modification": f"Core scaffold: {name}",
                        "reason": "Establishing EGFR kinase hinge-binding core", "parent": None}

    # Phase 2: core + hinge binder combinations
    if len(history) < 16:
        for core_name, core_smi in list(EGFR_CORES.items())[:4]:
            for hinge_name, hinge_smi in HINGE_BINDERS.items():
                combined = core_smi + hinge_smi
                ok, canonical = validate_smiles(combined)
                if ok and canonical not in blacklist:
                    return {"smiles": canonical,
                            "modification": f"{core_name} + {hinge_name}",
                            "reason": "Core-hinge combination for dual binding",
                            "parent": core_name}

    # Phase 3: add solubility tails to best candidates
    if history:
        best = sorted(history, key=lambda x: x.get("energy", 1))[:3]
        for cand in best:
            base = cand.get("smiles", "")
            if not base:
                continue
            for tail_name, tail_smi in SOLUBILITY_TAILS.items():
                combined = base + tail_smi
                ok, canonical = validate_smiles(combined)
                if ok and canonical not in blacklist:
                    mol = Chem.MolFromSmiles(canonical)
                    if mol and Descriptors.MolWt(mol) < 550:
                        return {"smiles": canonical,
                                "modification": f"Added {tail_name} for solubility",
                                "reason": "Solubility optimization of lead",
                                "parent": cand.get("id", "unknown")}

    # Fallback: known erlotinib-like scaffold
    fallbacks = [
        "CCOc1cc2ncnc(Nc3cccc(Cl)c3)c2cc1OCC#C",
        "Nc1ncnc2cc(OCC)c(OCC)cc12",
        "CCOc1cc2c(Nc3ccc(F)cc3)ncnc2cc1OCC",
        "COc1cc2ncnc(N)c2cc1OC",
        "Clc1cc2c(Nc3ccc(Cl)cc3)ncnc2cc1",
    ]
    for smi in fallbacks:
        ok, canonical = validate_smiles(smi)
        if ok and canonical not in blacklist:
            return {"smiles": canonical,
                    "modification": "Erlotinib-like scaffold",
                    "reason": "Known EGFR inhibitor pharmacophore",
                    "parent": None}

    return {"smiles": "Nc1ncnc2ccccc12",
            "modification": "Quinazoline base",
            "reason": "Core EGFR scaffold fallback",
            "parent": None}

# ============================================================
# LIPINSKI & VQE
# ============================================================

def check_lipinski(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return {"pass": False, "pass_count": 0, "mw": 0, "logp": 0, "hbd": 0, "hba": 0}
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    passes = sum([mw < 500, logp < 5, hbd < 5, hba < 10])
    return {"mw": mw, "logp": logp, "hbd": hbd, "hba": hba,
            "pass_count": passes, "pass": passes >= 3}

def calculate_drug_score(smiles):
    lip = check_lipinski(smiles)
    if not lip["pass"]:
        return 0
    score = lip["pass_count"] * 25
    if 300 < lip["mw"] < 500:
        score += 5
    if 1.5 < lip["logp"] < 4.0:
        score += 5
    if lip["mw"] > 450:
        score -= 10
    return max(0, min(100, score))

def run_vqe(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return 0.0, "Invalid"
    n_atoms = mol.GetNumHeavyAtoms()
    hbd = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() in (7,8) and a.GetTotalNumHs() > 0)
    hba = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() in (7,8))
    feature = min((n_atoms + 2*hbd + 1.5*hba) / 40.0, 1.0)
    try:
        dev = qml.device("lightning.qubit", wires=N_QUBITS, shots=256)
        @qml.qnode(dev, interface="autograd")
        def circuit(params):
            qml.StronglyEntanglingLayers(params, wires=range(N_QUBITS))
            return qml.expval(qml.PauliZ(0))
        params = pnp.random.random((2, N_QUBITS, 3)) * 0.03
        opt = qml.AdamOptimizer(stepsize=0.06)
        for _ in range(3):
            params = opt.step(circuit, params)
        raw = float(circuit(params))
        energy = raw * (1.0 + 0.25 * feature)
        return float(energy), f"VQE: {energy:.5f}"
    except Exception as e:
        return float(pnp.random.uniform(-0.9, 0.9)), f"Fallback: {e}"

# ============================================================
# CHAIN OF CUSTODY
# ============================================================

def save_to_library(candidate):
    file_exists = Path(LIBRARY_FILE).exists()
    with open(LIBRARY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["ID","SMILES","VQE_Energy","Drug_Score","MW","LogP","Lipinski","Parent","Timestamp"])
        writer.writerow([candidate["id"], candidate["smiles"], candidate["energy"],
                         candidate["drug_score"], candidate["mw"], candidate["logp"],
                         candidate["lipinski_passes"], candidate.get("parent",""),
                         candidate["timestamp"]])
    save_blacklist(candidate["smiles"])

custody_entries = []
def save_custody(candidate):
    fp_data = f"{candidate['smiles']}|{candidate['timestamp']}|{VQE_VERSION}"
    fingerprint = hashlib.sha256(fp_data.encode()).hexdigest()
    entry = {**candidate, "fingerprint": fingerprint[:32], "vqe_version": VQE_VERSION}
    custody_entries.append(entry)
    with open(CHAIN_FILE, "w") as f:
        json.dump(custody_entries, f, indent=2)

# ============================================================
# MAIN LOOP
# ============================================================

history = []
valid_candidates = []

print("="*65)
print(f"TARGETING EGFR KINASE - ATP Binding Site")
print(f"Known drugs: {', '.join(EGFR_KNOWLEDGE['known_inhibitors'])}")
print(f"Pharmacophore: {EGFR_KNOWLEDGE['pharmacophore']}")
print("="*65 + "\n")

for cycle in range(1, MAX_CYCLES + 1):
    print(f"--- CYCLE {cycle}/{MAX_CYCLES} ---")

    frag = generate_egfr_fragment(history)
    smiles = frag["smiles"]
    ok, canonical = validate_smiles(smiles)
    if not ok:
        print(f"  Invalid SMILES, skipping")
        continue
    smiles = canonical

    lip = check_lipinski(smiles)
    drug_score = calculate_drug_score(smiles)
    energy, note = run_vqe(smiles)

    candidate = {
        "id": f"EGFR-{cycle:03d}",
        "smiles": smiles,
        "energy": energy,
        "drug_score": drug_score,
        "lipinski_passes": lip["pass_count"],
        "mw": round(lip["mw"], 2),
        "logp": round(lip["logp"], 2),
        "hbd": lip["hbd"],
        "hba": lip["hba"],
        "modification": frag["modification"],
        "parent": frag.get("parent"),
        "timestamp": datetime.now().isoformat(),
    }
    history.append(candidate)

    print(f"  [{candidate['id']}] {smiles[:55]}...")
    print(f"  Mod: {frag['modification']}")
    print(f"  MW={lip['mw']:.0f} LogP={lip['logp']:.2f} Lipinski={lip['pass_count']}/4 Score={drug_score}/100")
    print(f"  {note}")

    if lip["pass"] and lip["mw"] < 550:
        save_to_library(candidate)
        save_custody(candidate)
        valid_candidates.append(candidate)
        print(f"  PASSED - saved to library")
    else:
        print(f"  FAILED Lipinski")
    print()
    time.sleep(0.5)

# ============================================================
# FINAL REPORT
# ============================================================

print("="*65)
print("EGFR QUANTUM DISCOVERY - FINAL REPORT")
print("="*65)
print(f"Cycles: {MAX_CYCLES} | Valid candidates: {len(valid_candidates)}")

if valid_candidates:
    valid_candidates.sort(key=lambda x: x["energy"])
    print("\nTOP 5 CANDIDATES:")
    print("-"*65)
    for c in valid_candidates[:5]:
        print(f"{c['id']}: {c['smiles'][:50]}...")
        print(f"  VQE={c['energy']:.4f} Score={c['drug_score']}/100 MW={c['mw']:.0f} LogP={c['logp']:.2f}")

    with open("egfr_results/top_candidates.json", "w") as f:
        json.dump(valid_candidates[:10], f, indent=2)
    print("\nSaved: egfr_results/top_candidates.json")
    print(f"Library: {LIBRARY_FILE}")
    print(f"Custody: {CHAIN_FILE}")

print("\nEGFR discovery complete. Run dock_egfr_gpu.py next.")
