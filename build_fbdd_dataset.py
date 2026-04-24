"""
FBDD Qwen Fine-Tuning Dataset Builder
======================================
Harvests all docking results from the autonomous AI quantum lab agent project
and converts them into instruction-tuning JSONL format for Qwen fine-tuning.

Usage:
    python build_fbdd_dataset.py --data_dir "." --output_dir "./qwen_dataset"

Requirements:
    pip install rdkit pandas tqdm scikit-learn
"""

import os
import json
import glob
import random
import argparse
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED, rdMolDescriptors
    RDKIT_AVAILABLE = True
except ImportError:
    print("WARNING: RDKit not available. SMILES validation will be skipped.")
    RDKIT_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# TARGET METADATA
# ─────────────────────────────────────────────────────────────────────────────

TARGET_INFO = {
    "EGFR": {
        "full_name": "Epidermal Growth Factor Receptor",
        "disease": "Non-small cell lung cancer",
        "pocket": "ATP-binding kinase domain, hinge region C-Met-Thr790",
        "good_affinity": -9.0,
        "excellent_affinity": -10.0,
        "known_drugs": ["Erlotinib", "Gefitinib", "Osimertinib"],
    },
    "HIV": {
        "full_name": "HIV-1 Protease",
        "disease": "HIV/AIDS",
        "pocket": "Catalytic aspartate dyad Asp25/Asp25'",
        "good_affinity": -7.0,
        "excellent_affinity": -8.5,
        "known_drugs": ["Darunavir", "Lopinavir", "Ritonavir"],
    },
    "HIV_INTEGRASE": {
        "full_name": "HIV-1 Integrase",
        "disease": "HIV/AIDS",
        "pocket": "Catalytic core domain with Mg2+ cofactors",
        "good_affinity": -7.5,
        "excellent_affinity": -9.0,
        "known_drugs": ["Raltegravir", "Dolutegravir", "Bictegravir"],
    },
    "HIV_DIP": {
        "full_name": "HIV-1 Protease (DIP series)",
        "disease": "HIV/AIDS",
        "pocket": "Flap region and catalytic dyad",
        "good_affinity": -7.0,
        "excellent_affinity": -8.5,
        "known_drugs": ["Darunavir", "Lopinavir"],
    },
    "BACE1": {
        "full_name": "Beta-secretase 1",
        "disease": "Alzheimer's disease",
        "pocket": "Aspartyl protease active site",
        "good_affinity": -8.0,
        "excellent_affinity": -9.5,
        "known_drugs": ["Verubecestat", "Lanabecestat"],
    },
    "COVID_MPRO": {
        "full_name": "SARS-CoV-2 Main Protease (Mpro)",
        "disease": "COVID-19",
        "pocket": "Cys145/His41 catalytic dyad",
        "good_affinity": -7.5,
        "excellent_affinity": -9.0,
        "known_drugs": ["Nirmatrelvir", "Ensitrelvir"],
    },
    "THROMBIN": {
        "full_name": "Thrombin (coagulation factor IIa)",
        "disease": "Thrombosis / anticoagulation",
        "pocket": "S1/S2/S3 substrate binding pockets",
        "good_affinity": -8.0,
        "excellent_affinity": -9.5,
        "known_drugs": ["Dabigatran", "Argatroban"],
    },
    "OPT": {
        "full_name": "Lead Optimization Series",
        "disease": "Multi-target",
        "pocket": "Optimized binding cavity",
        "good_affinity": -8.0,
        "excellent_affinity": -9.5,
        "known_drugs": [],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SMILES UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def validate_smiles(smiles):
    """Returns canonical SMILES or None if invalid."""
    if not RDKIT_AVAILABLE:
        return smiles if smiles and len(smiles) > 3 else None
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)
    except Exception:
        return None

def get_mol_properties(smiles):
    """Compute basic drug-likeness properties."""
    if not RDKIT_AVAILABLE:
        return {}
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {}
        return {
            "mw": round(Descriptors.MolWt(mol), 2),
            "logp": round(Descriptors.MolLogP(mol), 2),
            "hbd": rdMolDescriptors.CalcNumHBD(mol),
            "hba": rdMolDescriptors.CalcNumHBA(mol),
            "qed": round(QED.qed(mol), 3),
            "rotatable_bonds": rdMolDescriptors.CalcNumRotatableBonds(mol),
            "rings": rdMolDescriptors.CalcNumRings(mol),
        }
    except Exception:
        return {}

def classify_affinity(score, target_key):
    """Classify docking score into categorical label."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    if score <= info["excellent_affinity"]:
        return "excellent"
    elif score <= info["good_affinity"]:
        return "good"
    elif score <= -6.0:
        return "moderate"
    else:
        return "weak"

# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────────────────────────────────────

def load_csv_results(data_dir):
    """Load all agent_results_*.csv files."""
    records = []
    pattern = os.path.join(data_dir, "agent_results_*.csv")
    files = glob.glob(pattern)
    print(f"Found {len(files)} agent result CSV files")

    for fpath in tqdm(files, desc="Loading CSVs"):
        fname = Path(fpath).stem  # e.g. agent_results_EGFR_20260402_170628
        parts = fname.split("_")
        # Determine target key
        target_key = "UNKNOWN"
        for key in TARGET_INFO:
            if key in fname.upper():
                target_key = key
                break

        try:
            df = pd.read_csv(fpath)
            df.columns = [c.strip().lower() for c in df.columns]

            # Flexible column name mapping
            smiles_col = next((c for c in df.columns if "smiles" in c), None)
            score_col = next((c for c in df.columns if any(x in c for x in
                              ["affinity", "score", "docking", "vina", "energy", "binding"])), None)
            name_col = next((c for c in df.columns if any(x in c for x in
                             ["name", "id", "compound", "mol", "candidate"])), None)

            if smiles_col is None or score_col is None:
                continue

            for _, row in df.iterrows():
                smiles = str(row[smiles_col]).strip()
                try:
                    score = float(row[score_col])
                except (ValueError, TypeError):
                    continue

                canonical = validate_smiles(smiles)
                if canonical is None:
                    continue

                name = str(row[name_col]).strip() if name_col else f"CPD_{len(records)}"
                props = get_mol_properties(canonical)

                records.append({
                    "smiles": canonical,
                    "name": name,
                    "target": target_key,
                    "docking_score": score,
                    "affinity_class": classify_affinity(score, target_key),
                    "source_file": Path(fpath).name,
                    "properties": props,
                })
        except Exception as e:
            print(f"  Warning: could not parse {fpath}: {e}")

    return records


def load_json_results(data_dir):
    """Load key JSON result files."""
    records = []
    json_patterns = [
        "agent_leaderboard_*.json",
        "cure_top_candidates*.json",
        "valid_docking_results.json",
        "hiv_drug_discovery_final.json",
        "final_hiv_results.json",
        "optimization_results_*.json",
        "gnina_results.json",
        "meeko_docking_results.json",
        "meeko_reevaluation.json",
        "quantum_cure_7g.json",
        "cure_quantum_results.json",
        "quantum_hiv_cure_candidates.json",
        "real_drug_library.json",
        "complete_drug_library.json",
        "valid_candidates.json",
        "next_gen_candidates.json",
        "expanded_docking_results.json",
        "bis_thf_results.json",
        "cure_7g_results.json",
        "cure_6g_results.json",
    ]

    for pattern in json_patterns:
        files = glob.glob(os.path.join(data_dir, pattern))
        for fpath in files:
            try:
                with open(fpath) as f:
                    data = json.load(f)

                # Determine target
                fname = Path(fpath).name.upper()
                target_key = "EGFR"
                for key in TARGET_INFO:
                    if key in fname:
                        target_key = key
                        break

                # Normalize data formats
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # Could be {candidates: [...]} or flat dict
                    for k in ["candidates", "results", "molecules", "compounds", "hits"]:
                        if k in data and isinstance(data[k], list):
                            items = data[k]
                            break
                    if not items:
                        # Flat dict with SMILES keys
                        for k, v in data.items():
                            if isinstance(v, dict):
                                items.append({**v, "name": k})

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    smiles = item.get("smiles") or item.get("SMILES") or item.get("smi")
                    score = item.get("affinity") or item.get("score") or item.get("docking_score") \
                            or item.get("vina_score") or item.get("binding_affinity")

                    if not smiles or score is None:
                        continue

                    try:
                        score = float(score)
                    except (ValueError, TypeError):
                        continue

                    canonical = validate_smiles(str(smiles))
                    if canonical is None:
                        continue

                    name = item.get("name") or item.get("id") or item.get("compound_id") or f"J_{len(records)}"
                    props = get_mol_properties(canonical)

                    records.append({
                        "smiles": canonical,
                        "name": str(name),
                        "target": target_key,
                        "docking_score": score,
                        "affinity_class": classify_affinity(score, target_key),
                        "source_file": Path(fpath).name,
                        "properties": props,
                    })
            except Exception as e:
                print(f"  Warning: could not parse {fpath}: {e}")

    print(f"Loaded {len(records)} records from JSON files")
    return records


def load_fragment_library(data_dir):
    """Load fragment_library.csv for FBDD-specific fragment data."""
    records = []
    fpath = os.path.join(data_dir, "fragment_library.csv")
    if not os.path.exists(fpath):
        return records
    try:
        df = pd.read_csv(fpath)
        df.columns = [c.strip().lower() for c in df.columns]
        smiles_col = next((c for c in df.columns if "smiles" in c), None)
        if smiles_col:
            for _, row in df.iterrows():
                smiles = str(row[smiles_col]).strip()
                canonical = validate_smiles(smiles)
                if canonical:
                    props = get_mol_properties(canonical)
                    records.append({
                        "smiles": canonical,
                        "name": str(row.get("name", row.get("id", f"FRAG_{len(records)}"))),
                        "target": "FRAGMENT",
                        "docking_score": None,
                        "affinity_class": "fragment",
                        "source_file": "fragment_library.csv",
                        "properties": props,
                    })
        print(f"Loaded {len(records)} fragments from fragment_library.csv")
    except Exception as e:
        print(f"  Warning: could not load fragment_library.csv: {e}")
    return records

# ─────────────────────────────────────────────────────────────────────────────
# INSTRUCTION TEMPLATE GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def make_affinity_prediction_prompt(record):
    """Task: predict binding affinity class from SMILES + target."""
    target_key = record["target"]
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    props = record.get("properties", {})
    props_str = ""
    if props:
        props_str = (f" MW={props.get('mw','?')}, LogP={props.get('logp','?')}, "
                     f"QED={props.get('qed','?')}")

    instruction = (
        f"You are an expert computational medicinal chemist specializing in "
        f"fragment-based drug design (FBDD) and structure-based drug discovery."
    )
    user = (
        f"Predict the binding affinity category for this molecule against "
        f"{info['full_name']} ({target_key}), a key target in {info['disease']}.\n\n"
        f"Molecule SMILES: {record['smiles']}\n"
        f"Molecular properties:{props_str}\n"
        f"Target binding pocket: {info['pocket']}\n\n"
        f"Categories: excellent (≤{info['excellent_affinity']} kcal/mol), "
        f"good (≤{info['good_affinity']} kcal/mol), moderate (≤-6.0), weak (>-6.0)\n\n"
        f"Predicted affinity category:"
    )
    assistant = (
        f"{record['affinity_class']} "
        f"(estimated Vina score: {record['docking_score']:.2f} kcal/mol)"
    )
    return instruction, user, assistant


def make_docking_score_regression_prompt(record):
    """Task: predict numeric docking score."""
    target_key = record["target"]
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    props = record.get("properties", {})

    instruction = (
        "You are an expert in molecular docking and drug-target binding prediction. "
        "Predict AutoDock Vina binding affinity scores for small molecules."
    )
    user = (
        f"Predict the AutoDock Vina docking score (kcal/mol) for this molecule "
        f"against {info['full_name']}.\n\n"
        f"SMILES: {record['smiles']}\n"
        f"Target: {target_key} — {info['disease']}\n"
        f"Pocket: {info['pocket']}\n"
        f"Known reference drugs: {', '.join(info['known_drugs']) if info['known_drugs'] else 'N/A'}\n\n"
        f"Provide the predicted Vina score in kcal/mol (more negative = stronger binding):"
    )
    assistant = f"{record['docking_score']:.3f} kcal/mol"
    return instruction, user, assistant


def make_fragment_growing_prompt(records_by_target, target_key, n_examples=3):
    """Task: given a weak fragment, suggest growing directions toward better affinity."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    target_records = [r for r in records_by_target.get(target_key, [])
                      if r["docking_score"] is not None]
    if len(target_records) < 4:
        return None

    # Sort by score ascending (best = most negative)
    sorted_records = sorted(target_records, key=lambda x: x["docking_score"])
    best = sorted_records[:3]   # top binders
    weak = [r for r in sorted_records if r["affinity_class"] in ("moderate", "weak")]

    if not weak or not best:
        return None

    fragment = random.choice(weak[:max(1, len(weak)//2)])
    good_examples = random.sample(best, min(n_examples, len(best)))

    instruction = (
        "You are an expert medicinal chemist specializing in fragment-based drug design (FBDD). "
        "Your task is to suggest fragment growing strategies to improve binding affinity "
        "toward a protein target."
    )
    examples_str = "\n".join(
        [f"  - {ex['smiles']} → {ex['docking_score']:.2f} kcal/mol ({ex['name']})"
         for ex in good_examples]
    )
    user = (
        f"Starting fragment for {info['full_name']} ({target_key}):\n"
        f"SMILES: {fragment['smiles']}\n"
        f"Current docking score: {fragment['docking_score']:.2f} kcal/mol ({fragment['affinity_class']} binder)\n\n"
        f"Target pocket: {info['pocket']}\n"
        f"Disease: {info['disease']}\n\n"
        f"High-affinity reference compounds for this target:\n{examples_str}\n\n"
        f"Suggest 3 fragment growing strategies (SMILES modifications) that could improve "
        f"binding affinity. Consider: (1) H-bond donors/acceptors matching pocket residues, "
        f"(2) hydrophobic filling of lipophilic sub-pockets, (3) covalent warheads if applicable.\n\n"
        f"For each suggestion provide: the modified SMILES, the rationale, and predicted "
        f"affinity improvement."
    )
    # Answer is derived from the best compounds as inspiration
    assistant = (
        f"Based on the {target_key} binding pocket ({info['pocket']}) and the reference "
        f"high-affinity compounds, here are three growing strategies:\n\n"
        f"Strategy 1 — H-bond extension: Add a hydrogen bond acceptor group (e.g., "
        f"fluorine, carbonyl, or sulfonamide) to engage key pocket residues. "
        f"Expected improvement: 1-2 kcal/mol.\n\n"
        f"Strategy 2 — Hydrophobic tail: Introduce a lipophilic substituent (e.g., "
        f"trifluoromethyl, cyclopropyl, or halogenated aryl) to fill the hydrophobic "
        f"sub-pocket. Reference: {good_examples[0]['smiles'][:40]}...\n\n"
        f"Strategy 3 — Ring expansion: Merge with a known pharmacophore from "
        f"{info['known_drugs'][0] if info['known_drugs'] else 'approved inhibitors'} "
        f"scaffold to reach deeper binding cavity regions. "
        f"Target affinity: ≤{info['excellent_affinity']} kcal/mol."
    )
    return instruction, user, assistant


def make_admet_assessment_prompt(record):
    """Task: assess drug-likeness from SMILES."""
    props = record.get("properties", {})
    if not props:
        return None

    mw = props.get("mw", 0)
    logp = props.get("logp", 0)
    hbd = props.get("hbd", 0)
    hba = props.get("hba", 0)
    qed = props.get("qed", 0)
    rot = props.get("rotatable_bonds", 0)

    # Lipinski rule of 5 check
    ro5_violations = sum([
        mw > 500,
        logp > 5,
        hbd > 5,
        hba > 10,
    ])
    ro3_fragment = (mw <= 300 and logp <= 3 and hbd <= 3)

    instruction = (
        "You are a drug discovery ADMET specialist. Assess the drug-likeness "
        "and ADMET profile of small molecules based on their structure and properties."
    )
    user = (
        f"Assess the drug-likeness of this compound:\n\n"
        f"SMILES: {record['smiles']}\n"
        f"Molecular Weight: {mw} Da\n"
        f"LogP: {logp}\n"
        f"H-bond donors: {hbd}\n"
        f"H-bond acceptors: {hba}\n"
        f"QED score: {qed}\n"
        f"Rotatable bonds: {rot}\n\n"
        f"Provide: (1) Lipinski Ro5 compliance, (2) fragment-likeness (Ro3), "
        f"(3) predicted oral bioavailability, (4) potential ADMET liabilities, "
        f"(5) overall drug-likeness verdict."
    )

    verdict = "drug-like" if ro5_violations == 0 and qed > 0.5 else \
              "borderline" if ro5_violations <= 1 else "problematic"
    ro5_str = f"compliant (0 violations)" if ro5_violations == 0 else \
              f"{ro5_violations} violation(s)"

    assistant = (
        f"ADMET Assessment:\n\n"
        f"1. Lipinski Ro5: {ro5_str} — MW={mw}, LogP={logp}, HBD={hbd}, HBA={hba}\n"
        f"2. Fragment-likeness (Ro3): {'✓ Fragment-like' if ro3_fragment else '✗ Lead/drug-sized'} "
        f"— suitable as {'FBDD starting point' if ro3_fragment else 'lead compound'}\n"
        f"3. Oral bioavailability: {'Likely good' if ro5_violations == 0 else 'May be limited'} "
        f"based on physicochemical profile\n"
        f"4. Potential liabilities: {'Low concern' if logp < 3 else 'High LogP may cause solubility issues'}; "
        f"{'Rotatable bond count acceptable' if rot <= 10 else 'High flexibility may hurt binding entropy'}\n"
        f"5. Overall verdict: QED={qed} — {verdict.upper()} "
        f"({'proceed to optimization' if verdict == 'drug-like' else 'structural revision recommended'})"
    )
    return instruction, user, assistant


def make_target_identification_prompt(record):
    """Task: given SMILES, identify likely therapeutic target."""
    target_key = record["target"]
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])

    instruction = (
        "You are a computational medicinal chemist. Identify likely protein targets "
        "for small molecule compounds based on their structural features and pharmacophores."
    )
    user = (
        f"Analyze this molecule and identify its most likely primary therapeutic target:\n\n"
        f"SMILES: {record['smiles']}\n\n"
        f"Consider: scaffold features, functional groups, size, pharmacophore pattern, "
        f"and structural similarity to known drug classes. "
        f"Suggest the top target with rationale."
    )
    assistant = (
        f"Primary target: {info['full_name']} ({target_key})\n"
        f"Disease indication: {info['disease']}\n"
        f"Rationale: The molecular scaffold and pharmacophore pattern are consistent with "
        f"{target_key} inhibitors. Key features include the binding pocket complementarity "
        f"to {info['pocket']}. "
        f"Structural analogy to {info['known_drugs'][0] if info['known_drugs'] else 'known inhibitors'} "
        f"supports this target assignment.\n"
        f"Predicted binding affinity: {record['docking_score']:.2f} kcal/mol "
        f"({record['affinity_class']} binder)"
    )
    return instruction, user, assistant


# ─────────────────────────────────────────────────────────────────────────────
# DATASET ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def build_instruction_dataset(all_records, output_dir):
    """Convert all records into instruction-tuning JSONL entries."""
    os.makedirs(output_dir, exist_ok=True)
    dataset = []

    # Deduplicate by canonical SMILES + target
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r["smiles"], r["target"])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    print(f"\nUnique records after deduplication: {len(unique_records)}")

    # Group by target for fragment growing prompts
    records_by_target = defaultdict(list)
    for r in unique_records:
        records_by_target[r["target"]].append(r)

    print("\nRecords per target:")
    for t, recs in sorted(records_by_target.items(), key=lambda x: -len(x[1])):
        print(f"  {t}: {len(recs)}")

    # Build prompts for each docked record
    docked_records = [r for r in unique_records if r["docking_score"] is not None]
    print(f"\nBuilding instruction pairs from {len(docked_records)} docked records...")

    for record in tqdm(docked_records):
        # Task 1: Affinity classification
        inst, user, asst = make_affinity_prediction_prompt(record)
        dataset.append({
            "messages": [
                {"role": "system", "content": inst},
                {"role": "user", "content": user},
                {"role": "assistant", "content": asst},
            ],
            "task": "affinity_classification",
            "target": record["target"],
            "docking_score": record["docking_score"],
        })

        # Task 2: Regression score prediction
        inst, user, asst = make_docking_score_regression_prompt(record)
        dataset.append({
            "messages": [
                {"role": "system", "content": inst},
                {"role": "user", "content": user},
                {"role": "assistant", "content": asst},
            ],
            "task": "affinity_regression",
            "target": record["target"],
            "docking_score": record["docking_score"],
        })

        # Task 3: ADMET assessment (only if properties available)
        if record.get("properties"):
            result = make_admet_assessment_prompt(record)
            if result:
                inst, user, asst = result
                dataset.append({
                    "messages": [
                        {"role": "system", "content": inst},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": asst},
                    ],
                    "task": "admet_assessment",
                    "target": record["target"],
                    "docking_score": record["docking_score"],
                })

        # Task 4: Target identification (1 in 4 records to avoid imbalance)
        if random.random() < 0.25:
            inst, user, asst = make_target_identification_prompt(record)
            dataset.append({
                "messages": [
                    {"role": "system", "content": inst},
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": asst},
                ],
                "task": "target_identification",
                "target": record["target"],
                "docking_score": record["docking_score"],
            })

    # Task 5: Fragment growing prompts (one per target × multiple random draws)
    print("Building fragment growing prompts...")
    for target_key in records_by_target:
        if target_key == "FRAGMENT":
            continue
        for _ in range(min(50, len(records_by_target[target_key]))):
            result = make_fragment_growing_prompt(records_by_target, target_key)
            if result:
                inst, user, asst = result
                dataset.append({
                    "messages": [
                        {"role": "system", "content": inst},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": asst},
                    ],
                    "task": "fragment_growing",
                    "target": target_key,
                    "docking_score": None,
                })

    print(f"\nTotal instruction pairs generated: {len(dataset)}")

    # ── Task distribution summary ──
    task_counts = defaultdict(int)
    for item in dataset:
        task_counts[item["task"]] += 1
    print("\nTask distribution:")
    for task, count in sorted(task_counts.items(), key=lambda x: -x[1]):
        print(f"  {task}: {count} ({count/len(dataset)*100:.1f}%)")

    # ── Train / Val split (90/10) ──
    random.shuffle(dataset)
    split_idx = int(len(dataset) * 0.9)
    train_data = dataset[:split_idx]
    val_data = dataset[split_idx:]

    # ── Write JSONL files ──
    train_path = os.path.join(output_dir, "train.jsonl")
    val_path = os.path.join(output_dir, "val.jsonl")

    with open(train_path, "w") as f:
        for item in train_data:
            f.write(json.dumps(item) + "\n")

    with open(val_path, "w") as f:
        for item in val_data:
            f.write(json.dumps(item) + "\n")

    # ── Write HF-compatible format (no metadata fields) ──
    hf_train_path = os.path.join(output_dir, "hf_train.jsonl")
    hf_val_path = os.path.join(output_dir, "hf_val.jsonl")

    with open(hf_train_path, "w") as f:
        for item in train_data:
            f.write(json.dumps({"messages": item["messages"]}) + "\n")

    with open(hf_val_path, "w") as f:
        for item in val_data:
            f.write(json.dumps({"messages": item["messages"]}) + "\n")

    # ── Stats summary ──
    stats = {
        "total_records_loaded": len(all_records),
        "unique_records": len(unique_records),
        "docked_records": len(docked_records),
        "total_instruction_pairs": len(dataset),
        "train_size": len(train_data),
        "val_size": len(val_data),
        "task_distribution": dict(task_counts),
        "targets": {t: len(r) for t, r in records_by_target.items()},
    }

    with open(os.path.join(output_dir, "dataset_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n✅ Dataset saved to: {output_dir}")
    print(f"   Train: {train_path} ({len(train_data)} examples)")
    print(f"   Val:   {val_path} ({len(val_data)} examples)")
    print(f"   HF-ready: hf_train.jsonl / hf_val.jsonl")
    print(f"   Stats: dataset_stats.json")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build FBDD fine-tuning dataset for Qwen")
    parser.add_argument("--data_dir", default=".",
                        help="Path to autonomous AI quantum lab agent folder")
    parser.add_argument("--output_dir", default="./qwen_fbdd_dataset",
                        help="Output directory for JSONL dataset files")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 60)
    print("  FBDD Qwen Fine-Tuning Dataset Builder")
    print("=" * 60)
    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}\n")

    # Load all data sources
    csv_records = load_csv_results(args.data_dir)
    json_records = load_json_results(args.data_dir)
    frag_records = load_fragment_library(args.data_dir)

    all_records = csv_records + json_records + frag_records
    print(f"\nTotal records loaded: {len(all_records)}")
    print(f"  From CSVs: {len(csv_records)}")
    print(f"  From JSONs: {len(json_records)}")
    print(f"  From fragment library: {len(frag_records)}")

    if len(all_records) == 0:
        print("\nERROR: No records loaded. Check that --data_dir points to your project folder.")
        return

    # Build dataset
    stats = build_instruction_dataset(all_records, args.output_dir)

    print("\n" + "=" * 60)
    print("  NEXT STEPS FOR AMD HACKATHON")
    print("=" * 60)
    print("1. Upload hf_train.jsonl + hf_val.jsonl to Hugging Face Hub:")
    print("   from datasets import load_dataset")
    print("   dataset = load_dataset('json', data_files={'train': 'hf_train.jsonl', 'validation': 'hf_val.jsonl'})")
    print("")
    print("2. On AMD Dev Cloud (ROCm), fine-tune Qwen2.5-7B with:")
    print("   pip install transformers peft accelerate datasets bitsandbytes")
    print("   Use LoRA rank=16, alpha=32, target_modules=['q_proj','v_proj']")
    print("   Batch size 4, lr 2e-4, 3 epochs should fit in $100 credits")
    print("")
    print("3. Serve with vLLM on MI300X:")
    print("   vllm serve ./qwen-fbdd-finetuned --dtype float16")
    print("")
    print(f"Dataset ready. {stats['total_instruction_pairs']} instruction pairs built.")


if __name__ == "__main__":
    main()
