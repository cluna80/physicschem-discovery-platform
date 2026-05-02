"""
Enhanced FBDD Dataset Builder v2
==================================
Combines:
1. Your existing docking results (agent_results_*.csv, JSON files)
2. ChEMBL bioactivity data (IC50/Ki from real experiments)
3. Chain-of-thought reasoning examples
4. Fragment growing examples with rationale

Usage:
    python build_fbdd_dataset_v2.py --data_dir "." --output_dir "./qwen_fbdd_dataset_v2"
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
    from rdkit.Chem import Descriptors, QED, rdMolDescriptors, AllChem
    from rdkit.Chem import DataStructs
    RDKIT_AVAILABLE = True
except ImportError:
    print("WARNING: RDKit not available")
    RDKIT_AVAILABLE = False

try:
    from chembl_webresource_client.new_client import new_client
    CHEMBL_AVAILABLE = True
except ImportError:
    print("WARNING: ChEMBL client not available")
    CHEMBL_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# TARGET METADATA
# ─────────────────────────────────────────────────────────────────────────────

TARGET_INFO = {
    "EGFR": {
        "full_name": "Epidermal Growth Factor Receptor",
        "chembl_id": "CHEMBL203",
        "disease": "Non-small cell lung cancer",
        "pocket": "ATP-binding kinase domain, hinge region C-Met-Thr790",
        "good_affinity": -9.0,
        "excellent_affinity": -10.0,
        "known_drugs": ["Erlotinib", "Gefitinib", "Osimertinib"],
        "key_residues": ["Thr790", "Met793", "Lys745", "Cys797"],
        "binding_features": [
            "H-bond to hinge Met793 backbone",
            "Salt bridge with Lys745",
            "Hydrophobic contact with Phe856",
            "Covalent bond to Cys797 (irreversible inhibitors)",
        ],
    },
    "HIV": {
        "full_name": "HIV-1 Protease",
        "chembl_id": "CHEMBL243",
        "disease": "HIV/AIDS",
        "pocket": "Catalytic aspartate dyad Asp25/Asp25'",
        "good_affinity": -7.0,
        "excellent_affinity": -8.5,
        "known_drugs": ["Darunavir", "Lopinavir", "Ritonavir"],
        "key_residues": ["Asp25", "Asp25'", "Gly27", "Ile50", "Val82"],
        "binding_features": [
            "H-bond network with catalytic Asp25/Asp25'",
            "Hydrophobic contacts with Ile50/Ile50' flap residues",
            "bis-THF P2 ligand engages Asp29/Asp30",
            "Sulfonamide P2' fills S2' subpocket",
        ],
    },
    "HIV_INTEGRASE": {
        "full_name": "HIV-1 Integrase",
        "chembl_id": "CHEMBL3717",
        "disease": "HIV/AIDS",
        "pocket": "Catalytic core domain with Mg2+ cofactors",
        "good_affinity": -7.5,
        "excellent_affinity": -9.0,
        "known_drugs": ["Raltegravir", "Dolutegravir", "Bictegravir"],
        "key_residues": ["Asp64", "Asp116", "Glu152", "Lys159"],
        "binding_features": [
            "Chelation of Mg2+ cofactor with diketo acid motif",
            "Stacking interactions with viral DNA bases",
            "H-bonds to Glu92 and Thr66",
            "Halobenzyl group in hydrophobic pocket",
        ],
    },
    "BACE1": {
        "full_name": "Beta-secretase 1",
        "chembl_id": "CHEMBL4822",
        "disease": "Alzheimer's disease",
        "pocket": "Aspartyl protease active site",
        "good_affinity": -8.0,
        "excellent_affinity": -9.5,
        "known_drugs": ["Verubecestat", "Lanabecestat"],
        "key_residues": ["Asp32", "Asp228", "Thr231", "Ser35"],
        "binding_features": [
            "Transition state mimicry at Asp32/Asp228",
            "Flap closure over bound inhibitor",
            "S1/S3 subpocket hydrophobic contacts",
        ],
    },
    "COVID_MPRO": {
        "full_name": "SARS-CoV-2 Main Protease",
        "chembl_id": "CHEMBL4523582",
        "disease": "COVID-19",
        "pocket": "Cys145/His41 catalytic dyad",
        "good_affinity": -7.5,
        "excellent_affinity": -9.0,
        "known_drugs": ["Nirmatrelvir", "Ensitrelvir"],
        "key_residues": ["Cys145", "His41", "Glu166", "His163"],
        "binding_features": [
            "Covalent bond to Cys145 (electrophilic warhead)",
            "H-bond network at Glu166 S1 subsite",
            "P2 group in S2 hydrophobic pocket",
        ],
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# MOLECULE UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def validate_smiles(smiles):
    if not RDKIT_AVAILABLE:
        return smiles if smiles and len(smiles) > 3 else None
    try:
        mol = Chem.MolFromSmiles(str(smiles))
        if mol is None:
            return None
        return Chem.MolToSmiles(mol)
    except:
        return None

def get_mol_properties(smiles):
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
            "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
            "tpsa": round(Descriptors.TPSA(mol), 2),
        }
    except:
        return {}

def classify_affinity(score, target_key):
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    if score <= info["excellent_affinity"]:
        return "excellent"
    elif score <= info["good_affinity"]:
        return "good"
    elif score <= -6.0:
        return "moderate"
    else:
        return "weak"

def nM_to_affinity_class(nM_value):
    """Convert IC50/Ki in nM to affinity class."""
    if nM_value <= 10:
        return "excellent"
    elif nM_value <= 100:
        return "good"
    elif nM_value <= 1000:
        return "moderate"
    else:
        return "weak"

# ─────────────────────────────────────────────────────────────────────────────
# CHAIN OF THOUGHT REASONING GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_cot_reasoning(smiles, target_key, affinity_class, score=None, props=None):
    """Generate chain-of-thought reasoning for a molecule-target pair."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    props = props or get_mol_properties(smiles)

    mw = props.get("mw", 0)
    logp = props.get("logp", 0)
    hbd = props.get("hbd", 0)
    hba = props.get("hba", 0)
    qed = props.get("qed", 0)
    rings = props.get("rings", 0)
    arom = props.get("aromatic_rings", 0)
    tpsa = props.get("tpsa", 0)

    ro5_ok = mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10
    fragment_like = mw <= 300 and logp <= 3 and hbd <= 3

    # Build reasoning steps
    reasoning = f"""Let me analyze this molecule against {info['full_name']}:

**Step 1 — Molecular Size & Drug-likeness:**
- Molecular weight: {mw} Da ({'✓ drug-like' if mw <= 500 else '✗ too large'})
- LogP: {logp} ({'✓ good permeability' if logp <= 5 else '✗ too lipophilic'})
- H-bond donors: {hbd}, acceptors: {hba}
- QED score: {qed} ({'excellent' if qed > 0.7 else 'good' if qed > 0.5 else 'moderate'})
- {'Fragment-like (Ro3 compliant)' if fragment_like else 'Lead/drug-sized molecule'}

**Step 2 — Structural Features for {target_key}:**
- Aromatic rings: {arom} (key for π-π stacking in {info['pocket']})
- Rotatable bonds: {props.get('rotatable_bonds', 'N/A')} (flexibility for pocket adaptation)
- TPSA: {tpsa} Å² ({'good oral absorption' if tpsa <= 140 else 'limited oral absorption'})

**Step 3 — Target Pocket Complementarity:**
- {info['pocket']}
- Key binding features: {info['binding_features'][0]}
- {'The scaffold shows features consistent with ' + info['known_drugs'][0] + ' pharmacophore' if rings >= 2 else 'Simple scaffold may need elaboration for full pocket engagement'}

**Step 4 — Binding Affinity Assessment:**
{f'- Predicted Vina score: {score:.2f} kcal/mol' if score else ''}
- Classification: **{affinity_class.upper()}** binder
- {'Excellent lead candidate for further optimization' if affinity_class == 'excellent' else 'Good starting point for medicinal chemistry' if affinity_class == 'good' else 'Moderate activity, significant optimization needed' if affinity_class == 'moderate' else 'Weak binder, scaffold redesign recommended'}

**Conclusion:** {affinity_class.capitalize()} binding affinity against {info['full_name']}."""

    return reasoning


# ─────────────────────────────────────────────────────────────────────────────
# CHEMBL DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_chembl_data(target_key, max_records=2000):
    """Load bioactivity data from ChEMBL."""
    if not CHEMBL_AVAILABLE:
        print(f"ChEMBL client not available, skipping {target_key}")
        return []

    # Check for cached data
    cache_file = f"chembl_{target_key.lower()}.json"
    if os.path.exists(cache_file):
        print(f"Loading cached ChEMBL data: {cache_file}")
        with open(cache_file) as f:
            return json.load(f)

    info = TARGET_INFO.get(target_key)
    if not info or not info.get("chembl_id"):
        return []

    print(f"Fetching ChEMBL data for {target_key} ({info['chembl_id']})...")
    try:
        activity = new_client.activity
        results = activity.filter(
            target_chembl_id=info["chembl_id"],
            standard_type__in=["IC50", "Ki", "Kd"],
            standard_relation="=",
            standard_units="nM",
        ).only([
            "molecule_chembl_id",
            "canonical_smiles",
            "standard_value",
            "standard_type",
            "pchembl_value",
        ])

        data = []
        for r in list(results[:max_records]):
            smiles = r.get("canonical_smiles")
            value = r.get("standard_value")
            if not smiles or not value:
                continue
            try:
                nM = float(value)
                canonical = validate_smiles(smiles)
                if canonical is None:
                    continue
                data.append({
                    "smiles": canonical,
                    "nM_value": nM,
                    "assay_type": r.get("standard_type", "IC50"),
                    "pchembl": r.get("pchembl_value"),
                    "chembl_id": r.get("molecule_chembl_id"),
                })
            except:
                continue

        print(f"Got {len(data)} {target_key} compounds from ChEMBL")

        # Cache it
        with open(cache_file, "w") as f:
            json.dump(data, f)

        return data
    except Exception as e:
        print(f"ChEMBL fetch failed for {target_key}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING DATA LOADERS (from v1)
# ─────────────────────────────────────────────────────────────────────────────

def load_csv_results(data_dir):
    records = []
    for fpath in glob.glob(os.path.join(data_dir, "agent_results_*.csv")):
        fname = Path(fpath).stem.upper()
        target_key = next((k for k in TARGET_INFO if k in fname), "EGFR")
        try:
            df = pd.read_csv(fpath)
            df.columns = [c.strip().lower() for c in df.columns]
            smiles_col = next((c for c in df.columns if "smiles" in c), None)
            score_col = next((c for c in df.columns if any(x in c for x in ["affinity","score","docking","vina","energy","binding"])), None)
            if not smiles_col or not score_col:
                continue
            for _, row in df.iterrows():
                smiles = str(row[smiles_col]).strip()
                try:
                    score = float(row[score_col])
                except:
                    continue
                canonical = validate_smiles(smiles)
                if canonical is None:
                    continue
                records.append({
                    "smiles": canonical,
                    "target": target_key,
                    "docking_score": score,
                    "affinity_class": classify_affinity(score, target_key),
                    "properties": get_mol_properties(canonical),
                    "source": "docking",
                })
        except Exception as e:
            continue
    return records


# ─────────────────────────────────────────────────────────────────────────────
# INSTRUCTION PAIR GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def make_cot_affinity_prompt(record):
    """Chain-of-thought affinity prediction."""
    target_key = record["target"]
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])

    instruction = (
        "You are an expert computational medicinal chemist. "
        "Analyze molecules step-by-step before predicting binding affinity."
    )
    user = (
        f"Analyze this molecule against {info['full_name']} ({target_key}) "
        f"for {info['disease']} treatment.\n\n"
        f"SMILES: {record['smiles']}\n\n"
        f"Think through: (1) molecular properties, (2) structural features, "
        f"(3) pocket complementarity, (4) predicted affinity category.\n\n"
        f"Categories: excellent (≤{info['excellent_affinity']} kcal/mol), "
        f"good (≤{info['good_affinity']} kcal/mol), moderate (≤-6.0), weak (>-6.0)"
    )
    assistant = generate_cot_reasoning(
        record["smiles"], target_key,
        record["affinity_class"],
        record.get("docking_score"),
        record.get("properties", {})
    )
    return instruction, user, assistant


def make_chembl_affinity_prompt(chembl_record, target_key):
    """Affinity prediction from ChEMBL experimental data."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    nM = chembl_record["nM_value"]
    affinity_class = nM_to_affinity_class(nM)
    props = get_mol_properties(chembl_record["smiles"])

    instruction = (
        "You are an expert medicinal chemist with deep knowledge of "
        "experimental binding assays and structure-activity relationships."
    )
    user = (
        f"This molecule has been experimentally tested against {info['full_name']}.\n\n"
        f"SMILES: {chembl_record['smiles']}\n"
        f"Assay type: {chembl_record['assay_type']}\n\n"
        f"Based on the structure, predict the experimental potency category.\n"
        f"Categories: excellent (≤10 nM), good (≤100 nM), moderate (≤1000 nM), weak (>1000 nM)"
    )
    pchembl = chembl_record.get("pchembl")
    assistant = (
        f"{affinity_class.upper()} — {chembl_record['assay_type']}: {nM:.1f} nM"
        f"{f' (pChEMBL: {pchembl})' if pchembl else ''}\n\n"
        f"This {affinity_class} {info['full_name']} inhibitor shows "
        f"{'sub-nanomolar to low nanomolar' if nM <= 10 else 'nanomolar' if nM <= 100 else 'micromolar range'} "
        f"potency experimentally. "
        f"{'Suitable as a clinical candidate.' if affinity_class == 'excellent' else 'Suitable as a lead compound.' if affinity_class == 'good' else 'Requires optimization before advancing.'}"
    )
    return instruction, user, assistant


def make_sar_comparison_prompt(records_by_target, target_key):
    """Structure-Activity Relationship comparison between molecules."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    target_records = [r for r in records_by_target.get(target_key, [])
                     if r.get("docking_score") is not None]
    if len(target_records) < 6:
        return None

    sorted_records = sorted(target_records, key=lambda x: x["docking_score"])
    best = sorted_records[:3]
    worst = sorted_records[-3:]

    instruction = (
        "You are an expert medicinal chemist specializing in "
        "structure-activity relationship (SAR) analysis."
    )

    best_str = "\n".join([f"  - {r['smiles']} → {r['docking_score']:.2f} kcal/mol" for r in best])
    worst_str = "\n".join([f"  - {r['smiles']} → {r['docking_score']:.2f} kcal/mol" for r in worst])

    user = (
        f"Analyze the SAR for these {info['full_name']} ({target_key}) inhibitors:\n\n"
        f"HIGH AFFINITY compounds:\n{best_str}\n\n"
        f"LOW AFFINITY compounds:\n{worst_str}\n\n"
        f"Identify: (1) key pharmacophore features in high-affinity compounds, "
        f"(2) structural liabilities in low-affinity compounds, "
        f"(3) modification strategy to improve the weak binders."
    )

    best_props = [get_mol_properties(r["smiles"]) for r in best]
    avg_mw = sum(p.get("mw", 0) for p in best_props) / max(len(best_props), 1)
    avg_logp = sum(p.get("logp", 0) for p in best_props) / max(len(best_props), 1)

    assistant = (
        f"SAR Analysis for {info['full_name']}:\n\n"
        f"**Key pharmacophore features in high-affinity compounds (avg MW={avg_mw:.0f}, LogP={avg_logp:.1f}):**\n"
        f"1. Structural complementarity to {info['pocket']}\n"
        f"2. H-bond interactions: {info['binding_features'][0]}\n"
        f"3. Hydrophobic contacts matching {info['key_residues'][0]} environment\n\n"
        f"**Structural liabilities in weak binders:**\n"
        f"1. Insufficient engagement of key pocket residues\n"
        f"2. Suboptimal size/shape for binding cavity\n"
        f"3. Missing critical H-bond donors/acceptors\n\n"
        f"**Optimization strategy:**\n"
        f"1. Add H-bond acceptor targeting {info['key_residues'][0]}\n"
        f"2. Introduce hydrophobic group to fill {info['key_residues'][1] if len(info['key_residues']) > 1 else 'sub-pocket'}\n"
        f"3. Reference scaffold: {info['known_drugs'][0]} provides validated pharmacophore\n"
        f"4. Target affinity: ≤{info['excellent_affinity']} kcal/mol"
    )
    return instruction, user, assistant


def make_lead_optimization_prompt(record, target_key):
    """Lead optimization suggestions."""
    info = TARGET_INFO.get(target_key, TARGET_INFO["EGFR"])
    props = record.get("properties", {})

    if not props:
        return None

    mw = props.get("mw", 0)
    logp = props.get("logp", 0)
    qed = props.get("qed", 0)

    issues = []
    suggestions = []

    if mw > 500:
        issues.append(f"High MW ({mw} Da) may limit oral bioavailability")
        suggestions.append("Remove peripheral substituents to reduce MW below 500 Da")
    if logp > 5:
        issues.append(f"High LogP ({logp}) may cause solubility/toxicity issues")
        suggestions.append("Add polar groups (OH, NH2, morpholine) to reduce LogP")
    if logp < 1:
        issues.append(f"Low LogP ({logp}) may limit membrane permeability")
        suggestions.append("Add small hydrophobic groups (methyl, F) to improve LogP")
    if qed < 0.5:
        issues.append(f"Low QED ({qed}) indicates poor drug-likeness")
        suggestions.append("Simplify scaffold while maintaining key pharmacophore")

    if not issues:
        issues.append("Compound shows good drug-like properties")
        suggestions.append("Focus optimization on potency and selectivity")

    instruction = "You are a lead optimization expert in drug discovery."
    user = (
        f"Optimize this {info['full_name']} ({record['affinity_class']} binder) for drug development:\n\n"
        f"SMILES: {record['smiles']}\n"
        f"Current affinity: {record.get('docking_score', 'N/A')} kcal/mol ({record['affinity_class']})\n"
        f"MW: {mw}, LogP: {logp}, QED: {qed}\n\n"
        f"Suggest specific modifications to improve: potency, ADMET, selectivity."
    )
    assistant = (
        f"Lead Optimization for {info['full_name']} inhibitor:\n\n"
        f"**Current Issues:**\n" +
        "\n".join([f"{i+1}. {issue}" for i, issue in enumerate(issues)]) +
        f"\n\n**Optimization Strategy:**\n" +
        "\n".join([f"{i+1}. {sug}" for i, sug in enumerate(suggestions)]) +
        f"\n\n**Potency Enhancement:**\n"
        f"- Target: {info['excellent_affinity']} kcal/mol or better\n"
        f"- Key interaction to add: {info['binding_features'][0]}\n"
        f"- Consider bioisosteres of {info['known_drugs'][0]} core scaffold\n\n"
        f"**Selectivity:**\n"
        f"- Profile against off-targets (hERG, CYP3A4) early\n"
        f"- {info['key_residues'][0]} selectivity determinant for {target_key}"
    )
    return instruction, user, assistant


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DATASET BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_dataset(all_records, chembl_records_by_target, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    dataset = []

    # Deduplicate docking records
    seen = set()
    unique_records = []
    for r in all_records:
        key = (r["smiles"], r["target"])
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    print(f"\nUnique docking records: {len(unique_records)}")

    records_by_target = defaultdict(list)
    for r in unique_records:
        records_by_target[r["target"]].append(r)

    print("Records per target:")
    for t, recs in sorted(records_by_target.items(), key=lambda x: -len(x[1])):
        print(f"  {t}: {len(recs)}")

    docked = [r for r in unique_records if r.get("docking_score") is not None]

    # ── Task 1: Standard affinity classification ──
    print("\nBuilding standard affinity pairs...")
    for record in tqdm(docked[:500]):
        inst, user, asst = (
            "You are an expert computational medicinal chemist specializing in FBDD.",
            f"Predict binding affinity for SMILES: {record['smiles']} against {TARGET_INFO.get(record['target'], TARGET_INFO['EGFR'])['full_name']}.\n"
            f"Categories: excellent, good, moderate, weak\nAnswer:",
            f"{record['affinity_class']} ({record['docking_score']:.2f} kcal/mol)"
        )
        dataset.append({"messages": [{"role": "system", "content": inst}, {"role": "user", "content": user}, {"role": "assistant", "content": asst}], "task": "affinity_classification"})

    # ── Task 2: Chain-of-thought reasoning ──
    print("Building chain-of-thought pairs...")
    for record in tqdm(random.sample(docked, min(400, len(docked)))):
        if not record.get("properties"):
            continue
        inst, user, asst = make_cot_affinity_prompt(record)
        dataset.append({"messages": [{"role": "system", "content": inst}, {"role": "user", "content": user}, {"role": "assistant", "content": asst}], "task": "cot_affinity"})

    # ── Task 3: ChEMBL experimental data ──
    print("Building ChEMBL experimental pairs...")
    for target_key, chembl_records in chembl_records_by_target.items():
        for rec in tqdm(chembl_records[:500], desc=target_key):
            inst, user, asst = make_chembl_affinity_prompt(rec, target_key)
            dataset.append({"messages": [{"role": "system", "content": inst}, {"role": "user", "content": user}, {"role": "assistant", "content": asst}], "task": "chembl_experimental"})

    # ── Task 4: SAR analysis ──
    print("Building SAR analysis pairs...")
    for target_key in records_by_target:
        for _ in range(min(30, len(records_by_target[target_key]) // 5)):
            result = make_sar_comparison_prompt(records_by_target, target_key)
            if result:
                inst, user, asst = result
                dataset.append({"messages": [{"role": "system", "content": inst}, {"role": "user", "content": user}, {"role": "assistant", "content": asst}], "task": "sar_analysis"})

    # ── Task 5: Lead optimization ──
    print("Building lead optimization pairs...")
    for record in tqdm(random.sample(docked, min(300, len(docked)))):
        if not record.get("properties"):
            continue
        result = make_lead_optimization_prompt(record, record["target"])
        if result:
            inst, user, asst = result
            dataset.append({"messages": [{"role": "system", "content": inst}, {"role": "user", "content": user}, {"role": "assistant", "content": asst}], "task": "lead_optimization"})

    print(f"\nTotal pairs: {len(dataset)}")

    task_counts = defaultdict(int)
    for item in dataset:
        task_counts[item["task"]] += 1
    print("\nTask distribution:")
    for task, count in sorted(task_counts.items(), key=lambda x: -x[1]):
        print(f"  {task}: {count} ({count/len(dataset)*100:.1f}%)")

    # Split and save
    random.shuffle(dataset)
    split = int(len(dataset) * 0.9)
    train, val = dataset[:split], dataset[split:]

    for fname, data in [("hf_train.jsonl", train), ("hf_val.jsonl", val), ("train.jsonl", train), ("val.jsonl", val)]:
        path = os.path.join(output_dir, fname)
        with open(path, "w") as f:
            for item in data:
                if fname.startswith("hf_"):
                    f.write(json.dumps({"messages": item["messages"]}) + "\n")
                else:
                    f.write(json.dumps(item) + "\n")

    stats = {
        "total_pairs": len(dataset),
        "train_size": len(train),
        "val_size": len(val),
        "task_distribution": dict(task_counts),
        "docking_records": len(docked),
        "chembl_records": sum(len(v) for v in chembl_records_by_target.values()),
    }
    with open(os.path.join(output_dir, "dataset_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\n✅ Dataset v2 saved to: {output_dir}")
    print(f"   Train: {len(train)} | Val: {len(val)}")
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", default=".")
    parser.add_argument("--output_dir", default="./qwen_fbdd_dataset_v2")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip_chembl", action="store_true", help="Skip ChEMBL download")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 60)
    print("  FBDD Dataset Builder v2 — Enhanced with ChEMBL + CoT")
    print("=" * 60)

    # Load docking data
    print("\nLoading docking results...")
    docking_records = load_csv_results(args.data_dir)
    print(f"Loaded {len(docking_records)} docking records")

    # Load ChEMBL data
    chembl_records_by_target = {}
    if not args.skip_chembl:
        print("\nLoading ChEMBL bioactivity data...")
        for target_key in ["EGFR", "HIV", "HIV_INTEGRASE", "BACE1"]:
            records = load_chembl_data(target_key, max_records=1000)
            if records:
                chembl_records_by_target[target_key] = records
    else:
        print("Skipping ChEMBL (--skip_chembl flag)")

    # Build dataset
    stats = build_dataset(docking_records, chembl_records_by_target, args.output_dir)

    print("\n" + "=" * 60)
    print(f"  DONE — {stats['total_pairs']} instruction pairs")
    print("  Next: upload to HF and retrain on MI300X")
    print("=" * 60)


if __name__ == "__main__":
    main()
