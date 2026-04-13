# -*- coding: utf-8 -*-
"""
Fixed step-by-step optimization toward bis-THF scaffold.
All SMILES validated — fluorine is terminal only (1 bond max).
"""

import json, subprocess, os
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem

CURRENT_SMILES   = "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCF"
CURRENT_AFFINITY = -5.365

# ── F must always be TERMINAL (one bond only) ────────────────────────────────
# Core pharmacophore kept: trifluorophenyl-CO-NH-CH2-CH(OH)-CH2-NH-CO-...
# Optimization strategy: grow the right-hand tail toward bis-THF

DESIGNS = [
    {
        "name": "CURE_5G_001",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)CCCO",
        "mod": "Replace terminal F with OH (ether anchor)",
        "note": "Adds H-bond donor, removes valence error",
        "boost": 0.5,
    },
    {
        "name": "CURE_5G_002",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)C1CCCO1",
        "mod": "THF ring on right tail",
        "note": "Single THF — Darunavir-like, locks conformation",
        "boost": 1.0,
    },
    {
        "name": "CURE_5G_003",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)[C@@H]1CCO[C@H]1CO",
        "mod": "THF ring + hydroxymethyl (toward bis-THF)",
        "note": "Adds second H-bond anchor off THF",
        "boost": 1.4,
    },
    {
        "name": "CURE_5G_004",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)[C@H]1CO[C@@H]2OCCO[C@@H]12",
        "mod": "Bis-THF bicyclic scaffold (Darunavir P2 mimic)",
        "note": "Two fused THF rings — maximum H-bond to Asp29/Asp30",
        "boost": 2.1,
    },
    {
        "name": "CURE_5G_005",
        "smiles": "c1c(F)c(F)cc(F)c1C(=O)N[C@@H](CO)CNC(=O)[C@H]1CO[C@@H]2OCCO[C@@H]12",
        "mod": "Bis-THF + chiral center on linker",
        "note": "Stereocontrol for better fit in protease cleft",
        "boost": 2.4,
    },
]


def validate_smiles(smiles):
    mol = Chem.MolFromSmiles(smiles)
    return mol


def smiles_to_pdbqt(smiles, name, out_dir="ligand_pdbqt"):
    os.makedirs(out_dir, exist_ok=True)
    pdbqt = os.path.join(out_dir, f"{name}.pdbqt")
    if os.path.exists(pdbqt):
        return pdbqt
    try:
        mol = Chem.MolFromSmiles(smiles)
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0:
            AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        prep   = MoleculePreparation()
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        open(pdbqt, "w").write(pdbqt_str)
        return pdbqt
    except Exception as e:
        print(f"    [!] Prep error: {e}")
        return None


def dock(ligand_pdbqt, name, center, size=25, exhaustiveness=16):
    out = f"docking_results/{name}_out.pdbqt"
    os.makedirs("docking_results", exist_ok=True)
    cmd = [
        "./bin/vina.exe",
        "--receptor",       "hiv_protease.pdbqt",
        "--ligand",         ligand_pdbqt,
        "--center_x",       str(center[0]),
        "--center_y",       str(center[1]),
        "--center_z",       str(center[2]),
        "--size_x",         str(size),
        "--size_y",         str(size),
        "--size_z",         str(size),
        "--out",            out,
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes",      "9",
        "--cpu",            "6",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        for line in r.stdout.splitlines():
            if line.strip().startswith("1 "):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1]), out
    except Exception as e:
        print(f"    [!] Vina error: {e}")
    return None, None


def main():
    # Load binding site
    coords = open("hiv_binding_site.txt").read().strip().split(",")
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

    print("=" * 70)
    print("  HIV PROTEASE OPTIMIZATION — BIS-THF SCAFFOLD")
    print(f"  Baseline: CURE_4G_003  {CURRENT_AFFINITY:.3f} kcal/mol")
    print(f"  Target:   -9.0 kcal/mol")
    print(f"  Binding site: {center}")
    print("=" * 70)

    # Validate all SMILES first
    print("\n[VALIDATION]")
    valid = []
    for d in DESIGNS:
        mol = validate_smiles(d["smiles"])
        if mol:
            d["mw"]   = round(Descriptors.MolWt(mol), 1)
            d["logp"] = round(Descriptors.MolLogP(mol), 2)
            d["pred"] = round(CURRENT_AFFINITY - d["boost"], 3)
            valid.append(d)
            print(f"  ✓ {d['name']:<16} MW={d['mw']:>6.0f}  LogP={d['logp']:>5.2f}  "
                  f"Predicted={d['pred']:>7.3f}  {d['mod']}")
        else:
            print(f"  ✗ {d['name']:<16} INVALID SMILES — skipping")

    if not valid:
        print("\n[ERROR] No valid designs."); return

    # Dock each
    print(f"\n[DOCKING {len(valid)} COMPOUNDS]")
    results = []
    for d in valid:
        print(f"\n  [{d['name']}] {d['mod']}")
        pdbqt = smiles_to_pdbqt(d["smiles"], d["name"])
        if not pdbqt:
            print(f"    [-] Prep failed"); continue
        aff, pose = dock(pdbqt, d["name"], center)
        if aff is not None:
            d["affinity"] = aff
            d["pose"]     = pose
            results.append(d)
            delta = aff - CURRENT_AFFINITY
            print(f"    Affinity: {aff:.3f} kcal/mol  ({delta:+.3f} vs baseline)")
            if   aff < -9.0: print(f"    ★★★ DRUG CANDIDATE RANGE!")
            elif aff < -8.0: print(f"    ★★  Excellent binder!")
            elif aff < -7.0: print(f"    ★   Strong binder!")
            elif aff < -6.0: print(f"        Good progress")
        else:
            print(f"    [-] Docking failed")

    if not results:
        print("\n[!] No docking results."); return

    results.sort(key=lambda x: x["affinity"])
    best = results[0]

    # Summary
    print("\n" + "=" * 70)
    print("  RESULTS RANKED BY AFFINITY")
    print("=" * 70)
    print(f"  {'Name':<16} {'Affinity':>10}  {'vs Baseline':>12}  Modification")
    print("  " + "-" * 65)
    print(f"  {'CURE_4G_003':<16} {CURRENT_AFFINITY:>10.3f}  {'(baseline)':>12}")
    for r in results:
        delta = r["affinity"] - CURRENT_AFFINITY
        print(f"  {r['name']:<16} {r['affinity']:>10.3f}  {delta:>+12.3f}  {r['mod']}")

    print(f"\n  BEST: {best['name']}  {best['affinity']:.3f} kcal/mol")
    print(f"  Gap to -9.0: {best['affinity'] - (-9.0):.3f} kcal/mol remaining")

    # Save
    with open("bis_thf_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: bis_thf_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()