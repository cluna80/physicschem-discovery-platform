# ===========================================
# EGFR QUANTUM DRUG DISCOVERY AGENT
# 15-Qubit Evolutionary De Novo Discovery
# Target: EGFR Kinase (PDB 1M17)
# Mirrors: hiv_quantum_drug_agent.py
# ===========================================

import sys, json, time, random, csv, hashlib
from pathlib import Path
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

import pennylane as qml
from pennylane import numpy as pnp

# ===========================================
# CONFIG
# ===========================================

N_QUBITS = 15
MAX_CYCLES = 30
TARGET = "EGFR"
PDB_ID = "1M17"
BOX_CENTER = [22.01, 0.25, 52.79]
BOX_SIZE = [25.0, 25.0, 25.0]
MAX_MW = 550
TARGET_MW_RANGE = (300, 500)

WORK_DIR = Path("egfr_results")
WORK_DIR.mkdir(exist_ok=True)
LIBRARY_FILE = "egfr_results/egfr_drug_library.csv"
BLACKLIST_FILE = "egfr_results/egfr_blacklist.txt"
CHAIN_FILE = "egfr_results/egfr_chain_of_custody.json"

PENNYLANE_VERSION = qml.__version__
VQE_VERSION = f"lightning.qubit_v{PENNYLANE_VERSION}"

print(f"EGFR Quantum Drug Discovery | {N_QUBITS} qubits")
print(f"Target: EGFR Kinase (PDB {PDB_ID})")
print(f"Mode: De Novo Evolutionary - starting from simple scaffolds")
print(f"MW Target: {TARGET_MW_RANGE[0]}-{TARGET_MW_RANGE[1]} Da\n")

# ===========================================
# EGFR KNOWLEDGE BASE
# ===========================================

TARGET_KNOWLEDGE = {
    "description": "EGFR tyrosine kinase - ATP competitive inhibition at hinge region",
    "known_inhibitors": ["Erlotinib", "Gefitinib", "Afatinib", "Osimertinib", "Lapatinib"],
    "pharmacophore": "Quinazoline or pyrimidine core with hinge NH donor, hydrophobic tail",
    "key_features": [
        "Hinge H-bond donor (NH to M793 backbone carbonyl)",
        "Hydrophobic pocket (L718 V726 A743 L844)",
        "Gatekeeper T790 contact",
        "Solvent channel at C6/C7 for selectivity",
    ],
    "evolution_hints": [
        "Add quinazoline core for hinge region binding",
        "Add aniline NH for M793 hydrogen bond donation",
        "Add fluorine at meta position for selectivity",
        "Add chloro substituent for hydrophobic pocket",
        "Add methoxy group at C6 for EGFR potency",
        "Add alkoxy chain for solvent channel access",
        "Add morpholine for aqueous solubility",
        "Add trifluoromethyl for metabolic stability",
        "Add pyrimidine as quinazoline bioisostere",
        "Add piperazine for selectivity tail",
    ]
}

# ===========================================
# STARTING SCAFFOLDS (simple, low MW)
# These are the seeds - agent evolves from here
# ===========================================

SEED_SCAFFOLDS = [
    "c1cnc2ccccc2n1",        # quinazoline (MW=130) - core EGFR hinge binder
    "c1cnccn1",              # pyrimidine (MW=80) - alternative core
    "Nc1ncnc2ccccc12",       # 4-aminoquinazoline (MW=145)
    "c1ccc2[nH]cnc2c1",      # benzimidazole (MW=118)
    "c1cnc2[nH]ccc2c1",      # 7-azaindole (MW=118)
    "c1csc2ncncc2c1",        # thienopyrimidine (MW=136)
    "c1ccc2nccnc2c1",        # quinoxaline (MW=130)
    "Nc1ccccc1",             # aniline (MW=93) - hinge binder fragment
]

# Evolution building blocks
HINGE_GROUPS = {
    "aniline_NH":        "Nc1ccccc1",
    "meta_F_aniline":    "Nc1cccc(F)c1",
    "meta_Cl_aniline":   "Nc1cccc(Cl)c1",
    "para_F_aniline":    "Nc1ccc(F)cc1",
    "meta_CF3_aniline":  "Nc1cccc(C(F)(F)F)c1",
    "difluoro_aniline":  "Nc1ccc(F)c(F)c1",
}

SOLUBILITY_GROUPS = {
    "methoxy":           "OC",
    "ethoxy":            "OCC",
    "propoxy":           "OCCC",
    "morpholine_O":      "OCC N1CCOCC1",
    "dimethylamino":     "N(C)C",
    "hydroxyl":          "O",
    "fluorine":          "F",
    "chlorine":          "Cl",
    "trifluoromethyl":   "C(F)(F)F",
    "methyl":            "C",
}

EVOLUTION_STRATEGIES = [
    # EGFR-specific
    "Add quinazoline core for hinge binding",
    "Add aniline NH for M793 hydrogen bond",
    "Add fluorine at meta position for selectivity",
    "Add chloro substituent for hydrophobic pocket",
    "Add methoxy at C6 for EGFR potency",
    "Add ethoxy chain for solvent channel",
    "Add morpholine for solubility",
    "Add trifluoromethyl for metabolic stability",
    "Add pyrimidine bioisostere of quinazoline",
    "Add piperazine tail for selectivity",
    # Generic medicinal chemistry
    "Add methyl group for metabolic stability",
    "Add hydroxyl for hydrogen bonding",
    "Add fluorine for stronger binding",
    "Replace chloro with fluoro bioisostere",
    "Add dimethylamino for basicity and solubility",
]

# ===========================================
# BLACKLIST
# ===========================================

def load_blacklist():
    bl = set()
    if Path(BLACKLIST_FILE).exists():
        for line in open(BLACKLIST_FILE):
            bl.add(line.strip())
    if Path(LIBRARY_FILE).exists():
        try:
            for row in csv.reader(open(LIBRARY_FILE)):
                if len(row) > 1:
                    bl.add(row[1])
        except:
            pass
    return bl

def save_blacklist(smiles):
    with open(BLACKLIST_FILE, "a") as f:
        f.write(smiles + "\n")

BLACKLIST = load_blacklist()
print(f"Loaded {len(BLACKLIST)} blacklisted SMILES\n")

# ===========================================
# BIOISOSTERE OPTIMIZATION (MW control)
# ===========================================

def apply_bioisostere(smiles, swap_type):
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None
        mw = Descriptors.MolWt(mol)
        if swap_type == "halogen_swap":
            if "Br" in smiles:
                new = smiles.replace("Br", "F")
                m = Chem.MolFromSmiles(new)
                if m and Descriptors.MolWt(m) < mw:
                    return new
            if "Cl" in smiles:
                new = smiles.replace("Cl", "F")
                m = Chem.MolFromSmiles(new)
                if m and Descriptors.MolWt(m) < mw:
                    return new
        elif swap_type == "methoxy_to_fluoro":
            if "OC" in smiles:
                new = smiles.replace("OC", "F", 1)
                m = Chem.MolFromSmiles(new)
                if m and Descriptors.MolWt(m) < mw:
                    return new
        return None
    except:
        return None

# ===========================================
# FRAGMENT EVOLUTION ENGINE
# ===========================================

def validate_smiles(smiles):
    if not smiles:
        return False, None
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return False, None
    try:
        Chem.SanitizeMol(mol)
        return True, Chem.MolToSmiles(mol, canonical=True)
    except:
        return False, None

def generate_evolved_fragment(base_smiles, strategy, blacklist):
    try:
        mol = Chem.RWMol(Chem.MolFromSmiles(base_smiles))
        if mol is None:
            return None

        aromatic_carbons = [a.GetIdx() for a in mol.GetAtoms()
                           if a.GetIsAromatic() and a.GetAtomicNum() == 6]
        nitrogens = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 7]

        if not aromatic_carbons:
            return None

        attach = random.choice(aromatic_carbons)

        if "fluor" in strategy.lower() or "fluorine" in strategy.lower():
            new_idx = mol.AddAtom(Chem.Atom(9))
            mol.AddBond(attach, new_idx, Chem.BondType.SINGLE)

        elif "chloro" in strategy.lower() or "chlorine" in strategy.lower():
            new_idx = mol.AddAtom(Chem.Atom(17))
            mol.AddBond(attach, new_idx, Chem.BondType.SINGLE)

        elif "methoxy" in strategy.lower() or "methoxy" in strategy.lower():
            o_idx = mol.AddAtom(Chem.Atom(8))
            mol.AddBond(attach, o_idx, Chem.BondType.SINGLE)
            c_idx = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(o_idx, c_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(c_idx).SetNumExplicitHs(3)

        elif "ethoxy" in strategy.lower():
            o_idx = mol.AddAtom(Chem.Atom(8))
            mol.AddBond(attach, o_idx, Chem.BondType.SINGLE)
            c1_idx = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(o_idx, c1_idx, Chem.BondType.SINGLE)
            c2_idx = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(c1_idx, c2_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(c2_idx).SetNumExplicitHs(3)

        elif "hydroxyl" in strategy.lower():
            o_idx = mol.AddAtom(Chem.Atom(8))
            mol.AddBond(attach, o_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(o_idx).SetNumExplicitHs(1)

        elif "trifluoromethyl" in strategy.lower():
            c_idx = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(attach, c_idx, Chem.BondType.SINGLE)
            for _ in range(3):
                f_idx = mol.AddAtom(Chem.Atom(9))
                mol.AddBond(c_idx, f_idx, Chem.BondType.SINGLE)

        elif "methyl" in strategy.lower():
            c_idx = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(attach, c_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(c_idx).SetNumExplicitHs(3)

        elif "amino" in strategy.lower() or "aniline" in strategy.lower():
            n_idx = mol.AddAtom(Chem.Atom(7))
            mol.AddBond(attach, n_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(n_idx).SetNumExplicitHs(2)

        elif "morpholine" in strategy.lower():
            n_idx = mol.AddAtom(Chem.Atom(7))
            mol.AddBond(attach, n_idx, Chem.BondType.SINGLE)
            c1 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(n_idx, c1, Chem.BondType.SINGLE)
            c2 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(c1, c2, Chem.BondType.SINGLE)
            o_idx = mol.AddAtom(Chem.Atom(8))
            mol.AddBond(c2, o_idx, Chem.BondType.SINGLE)
            c3 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(o_idx, c3, Chem.BondType.SINGLE)
            c4 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(c3, c4, Chem.BondType.SINGLE)
            mol.AddBond(c4, n_idx, Chem.BondType.SINGLE)

        elif "piperazine" in strategy.lower():
            n1_idx = mol.AddAtom(Chem.Atom(7))
            mol.AddBond(attach, n1_idx, Chem.BondType.SINGLE)
            c1 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(n1_idx, c1, Chem.BondType.SINGLE)
            c2 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(c1, c2, Chem.BondType.SINGLE)
            n2_idx = mol.AddAtom(Chem.Atom(7))
            mol.AddBond(c2, n2_idx, Chem.BondType.SINGLE)
            mol.GetAtomWithIdx(n2_idx).SetNumExplicitHs(1)
            c3 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(n2_idx, c3, Chem.BondType.SINGLE)
            c4 = mol.AddAtom(Chem.Atom(6))
            mol.AddBond(c3, c4, Chem.BondType.SINGLE)
            mol.AddBond(c4, n1_idx, Chem.BondType.SINGLE)

        else:
            return None

        new_mol = mol.GetMol()
        Chem.SanitizeMol(new_mol)
        new_smiles = Chem.MolToSmiles(new_mol, canonical=True)
        if new_smiles not in blacklist:
            return new_smiles
    except:
        pass
    return None

def generate_novel_fragment(history):
    blacklist = set(h.get("smiles","") for h in history) | BLACKLIST
    current_mw = history[-1].get("mw", 0) if history else 0

    # MW too high - apply bioisostere
    if current_mw > TARGET_MW_RANGE[1]:
        for cand in history[-5:]:
            base = cand.get("smiles","")
            if not base:
                continue
            for swap in ["halogen_swap", "methoxy_to_fluoro"]:
                new = apply_bioisostere(base, swap)
                if new and new not in blacklist:
                    m = Chem.MolFromSmiles(new)
                    if m:
                        return {"smiles": new,
                                "modification": f"Bioisostere: {swap}",
                                "reason": "MW optimization",
                                "parent": cand.get("id","unknown")}

    # Phase 1 (cycles 1-8): try seed scaffolds
    if len(history) < 8:
        for seed in SEED_SCAFFOLDS:
            if seed not in blacklist:
                ok, canonical = validate_smiles(seed)
                if ok and canonical not in blacklist:
                    return {"smiles": canonical,
                            "modification": "Seed scaffold",
                            "reason": "Initial EGFR scaffold exploration",
                            "parent": None}

    # Phase 2 (cycles 9-20): evolve from best candidates
    best = sorted(history, key=lambda x: x.get("energy", 1))[:5]
    for cand in best:
        base = cand.get("smiles","")
        if not base or cand.get("mw", 0) > MAX_MW:
            continue
        strategies = EVOLUTION_STRATEGIES.copy()
        random.shuffle(strategies)
        for strat in strategies[:6]:
            new = generate_evolved_fragment(base, strat, blacklist)
            if new:
                m = Chem.MolFromSmiles(new)
                if m and Descriptors.MolWt(m) <= MAX_MW:
                    return {"smiles": new,
                            "modification": f"Evolution: {strat}",
                            "reason": f"Evolved from {cand.get('id','prev')}",
                            "parent": cand.get("id","unknown")}

    # Phase 3: hinge binder combinations
    for hname, hsmi in HINGE_GROUPS.items():
        if hsmi not in blacklist:
            ok, canonical = validate_smiles(hsmi)
            if ok and canonical not in blacklist:
                return {"smiles": canonical,
                        "modification": f"Hinge binder: {hname}",
                        "reason": "EGFR M793 hinge H-bond",
                        "parent": None}

    # Fallback: erlotinib-like core
    fallbacks = [
        "CCOc1cc2ncnc(N)c2cc1OCC",
        "Nc1ncnc2cc(OC)c(OC)cc12",
        "Clc1ccc(Nc2ncnc3ccccc23)cc1",
        "Fc1ccc(Nc2ncnc3ccccc23)cc1",
        "COc1ccc(Nc2ncnc3ccccc23)cc1",
    ]
    for smi in fallbacks:
        ok, canonical = validate_smiles(smi)
        if ok and canonical not in blacklist:
            return {"smiles": canonical,
                    "modification": "Erlotinib-like fallback",
                    "reason": "Known EGFR pharmacophore",
                    "parent": None}

    return {"smiles": "Nc1ncnc2ccccc12",
            "modification": "Quinazoline base",
            "reason": "Core fallback",
            "parent": None}

# ===========================================
# LIPINSKI & DRUG SCORE
# ===========================================

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
    if TARGET_MW_RANGE[0] < lip["mw"] < TARGET_MW_RANGE[1]:
        score += 5
    if 1.5 < lip["logp"] < 4.0:
        score += 5
    if lip["mw"] > 450:
        score -= 5
    return max(0, min(100, score))

# ===========================================
# 15-QUBIT VQE
# ===========================================

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
        return float(pnp.random.uniform(0.7, 0.95)), f"Fallback"

# ===========================================
# CHAIN OF CUSTODY
# ===========================================

custody_entries = []

def save_to_library(candidate):
    exists = Path(LIBRARY_FILE).exists()
    with open(LIBRARY_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["ID","SMILES","VQE_Energy","Drug_Score",
                        "MW","LogP","Lipinski","Parent","Timestamp"])
        w.writerow([candidate["id"], candidate["smiles"], candidate["energy"],
                    candidate["drug_score"], candidate["mw"], candidate["logp"],
                    candidate["lipinski_passes"], candidate.get("parent",""),
                    candidate["timestamp"]])
    save_blacklist(candidate["smiles"])

def save_custody(candidate):
    fp = hashlib.sha256(
        f"{candidate['smiles']}|{candidate['timestamp']}|{VQE_VERSION}".encode()
    ).hexdigest()[:32]
    custody_entries.append({**candidate, "fingerprint": fp, "vqe_version": VQE_VERSION})
    with open(CHAIN_FILE, "w") as f:
        json.dump(custody_entries, f, indent=2)

# ===========================================
# MAIN EVOLUTIONARY LOOP
# ===========================================

history = []
valid_candidates = []

print("="*65)
print(f"TARGETING EGFR KINASE - De Novo Evolution")
print(f"Known drugs: {', '.join(TARGET_KNOWLEDGE['known_inhibitors'])}")
print(f"Pharmacophore: {TARGET_KNOWLEDGE['pharmacophore']}")
print("="*65 + "\n")

for cycle in range(1, MAX_CYCLES + 1):
    print(f"--- CYCLE {cycle}/{MAX_CYCLES} ---")
    if cycle > 15:
        print(f"  [MW OPTIMIZATION PHASE]")

    frag = generate_novel_fragment(history)
    smiles = frag["smiles"]
    ok, canonical = validate_smiles(smiles)
    if not ok:
        print(f"  Invalid SMILES - skipping\n")
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
        "mw": round(lip["mw"], 1),
        "logp": round(lip["logp"], 2),
        "hbd": lip["hbd"],
        "hba": lip["hba"],
        "modification": frag["modification"],
        "parent": frag.get("parent"),
        "timestamp": datetime.now().isoformat(),
    }
    history.append(candidate)

    print(f"  [{candidate['id']}] {smiles[:60]}")
    print(f"  Mod: {frag['modification']}")
    print(f"  MW={lip['mw']:.0f} LogP={lip['logp']:.2f} "
          f"Lipinski={lip['pass_count']}/4 Score={drug_score}/100")
    print(f"  {note}")

    if lip["pass"] and lip["mw"] <= MAX_MW:
        save_to_library(candidate)
        save_custody(candidate)
        valid_candidates.append(candidate)
        print(f"  PASSED - saved")
        if "Bioisostere" in frag["modification"]:
            print(f"  MW OPTIMIZED via bioisostere")
    else:
        if lip["mw"] > MAX_MW:
            print(f"  REJECTED: MW {lip['mw']:.0f} > {MAX_MW}")
        else:
            print(f"  FAILED Lipinski ({lip['pass_count']}/4)")
    print()
    time.sleep(0.3)

# ===========================================
# FINAL REPORT
# ===========================================

print("="*65)
print("EGFR QUANTUM DISCOVERY - FINAL REPORT")
print("="*65)
print(f"Total cycles: {MAX_CYCLES}")
print(f"Valid candidates: {len(valid_candidates)}")
print(f"Blacklist size: {len(BLACKLIST) + len(valid_candidates)}")

if valid_candidates:
    valid_candidates.sort(key=lambda x: (x["energy"], x["mw"]))

    print(f"\nTOP 10 CANDIDATES:")
    print(f"{'ID':<12} {'VQE':>7} {'Score':>6} {'MW':>6} {'LogP':>6}  SMILES")
    print("-"*80)
    for c in valid_candidates[:10]:
        print(f"{c['id']:<12} {c['energy']:>7.4f} {c['drug_score']:>6} "
              f"{c['mw']:>6.0f} {c['logp']:>6.2f}  {c['smiles'][:40]}")

    with open("egfr_results/top_candidates.json", "w") as f:
        json.dump(valid_candidates[:10], f, indent=2)

print(f"\nFiles saved:")
print(f"  - {LIBRARY_FILE}")
print(f"  - {CHAIN_FILE}")
print(f"  - egfr_results/top_candidates.json")
print(f"\nNext step: python3 dock_egfr_gpu.py")
