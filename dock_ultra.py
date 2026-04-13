# -*- coding: utf-8 -*-
"""
Ultra-Potent HIV Inhibitor Design + Docking
Target: -8.5 to -10.0 kcal/mol (Darunavir-level and beyond)

Strategy:
  - Base scaffold: best confirmed CURE_13G compound
  - Extensions: P2' pocket, flap water H-bonds, dimer interface
  - All SMILES validated before docking
  - Meeko prep only — no obabel

Usage:
    python dock_ultra.py
    python dock_ultra.py --exhaustiveness 32
"""

import os, json, subprocess, argparse
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, QED
from meeko import MoleculePreparation, PDBQTWriterLegacy

# ─────────────────────────────────────────────────────────────
# BEST CONFIRMED SCAFFOLD
# CURE_13G_001: naphthalene + meta-F-benzyl + R-OH + bis-THF
# ─────────────────────────────────────────────────────────────
BASE = {
    "name":     "CURE_13G_001",
    "affinity": -7.333,
    "smiles":   "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
}

# ─────────────────────────────────────────────────────────────
# ULTRA DESIGNS — all ring numbers verified unique per SMILES
# Ring map: 1,2=naphthalene  3=fluorobenzyl  4,5=bis-THF
# ─────────────────────────────────────────────────────────────
DESIGNS = [

    # ── P2' pocket extensions ────────────────────────────────
    {
        "name": "ULTRA_001",
        "smiles": "O=S(=O)(N)c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "feature": "Sulfonamide on naphthalene",
        "mechanism": "SO2NH2 H-bonds to Asp29/Asp30 in P2' pocket",
        "expected_boost": 0.7,
    },
    {
        "name": "ULTRA_002",
        "smiles": "Nc1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "feature": "Amino-naphthalene",
        "mechanism": "NH2 donor to Asp30 backbone carbonyl",
        "expected_boost": 0.5,
    },

    # ── Flap water network ───────────────────────────────────
    {
        "name": "ULTRA_003",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@H](O)[C@@H]45)ccc2c1",
        "feature": "Hydroxy-bis-THF",
        "mechanism": "OH inside bis-THF ring bridges flap water to Ile50",
        "expected_boost": 0.6,
    },
    {
        "name": "ULTRA_004",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@@H](O)[C@@H]45)ccc2c1",
        "feature": "Hydroxy-bis-THF (S config on OH)",
        "mechanism": "Alternative OH stereochemistry for flap water",
        "expected_boost": 0.5,
    },

    # ── Extended P1 subsite ──────────────────────────────────
    {
        "name": "ULTRA_005",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3ccc(F)c(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "feature": "3,4-difluorobenzyl P1",
        "mechanism": "Adjacent F atoms fill S1 pocket electronically",
        "expected_boost": 0.4,
    },
    {
        "name": "ULTRA_006",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3ccc(F)cc3F)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1",
        "feature": "2,4-difluorobenzyl P1",
        "mechanism": "Ortho+para F for tight S1 fit",
        "expected_boost": 0.4,
    },

    # ── Combined winners ─────────────────────────────────────
    {
        "name": "ULTRA_007",
        "smiles": "O=S(=O)(N)c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@H](O)[C@@H]45)ccc2c1",
        "feature": "Sulfonamide + hydroxy-bis-THF",
        "mechanism": "P2' SO2NH2 + flap water bridge combined",
        "expected_boost": 1.2,
    },
    {
        "name": "ULTRA_008",
        "smiles": "Nc1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@H](O)[C@@H]45)ccc2c1",
        "feature": "Amino-naphthalene + hydroxy-bis-THF",
        "mechanism": "NH2 + flap water combined",
        "expected_boost": 1.0,
    },
    {
        "name": "ULTRA_009",
        "smiles": "c1ccc2ccc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@H](O)[C@@H]45)nc2c1",
        "feature": "Isoquinoline + hydroxy-bis-THF",
        "mechanism": "Ring N + flap water bridge",
        "expected_boost": 1.1,
    },

    # ── Ultimate combination ──────────────────────────────────
    {
        "name": "ULTRA_010",
        "smiles": "O=S(=O)(N)c1ccc2ccc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]4CO[C@@H]5OC[C@H](O)[C@@H]45)nc2c1",
        "feature": "Isoquinoline + sulfonamide + hydroxy-bis-THF",
        "mechanism": "Triple action: ring N + SO2NH2 + flap water",
        "expected_boost": 1.6,
    },
]


# ─────────────────────────────────────────────────────────────
# MEEKO PREP
# ─────────────────────────────────────────────────────────────
def to_pdbqt(smiles, name, out_dir="ligand_ultra"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.pdbqt")
    if os.path.exists(path):
        return path
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0:
            AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
        prep = MoleculePreparation()
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        open(path, "w").write(pdbqt_str)
        return path
    except Exception as e:
        print(f"    Meeko error: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# VINA DOCK
# ─────────────────────────────────────────────────────────────
def vina_dock(pdbqt, name, center, size=25, exhaustiveness=16, cpu=6):
    os.makedirs("docking_results", exist_ok=True)
    out = f"docking_results/{name}_out.pdbqt"
    cmd = [
        "./bin/vina.exe",
        "--receptor", "hiv_protease.pdbqt",
        "--ligand", pdbqt,
        "--center_x", str(center[0]),
        "--center_y", str(center[1]),
        "--center_z", str(center[2]),
        "--size_x", str(size),
        "--size_y", str(size),
        "--size_z", str(size),
        "--out", out,
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes", "9",
        "--cpu", str(cpu),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        modes = []
        for line in r.stdout.splitlines():
            s = line.strip()
            if s and s[0].isdigit():
                parts = s.split()
                if len(parts) >= 2:
                    try:
                        aff = float(parts[1])
                        if aff < 5:
                            modes.append(aff)
                    except:
                        pass
        return (min(modes), out) if modes else (None, None)
    except Exception as e:
        print(f"    Vina error: {e}")
        return None, None


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exhaustiveness", type=int, default=16)
    parser.add_argument("--size",           type=int, default=25)
    parser.add_argument("--cpu",            type=int, default=6)
    args = parser.parse_args()

    coords = open("hiv_binding_site.txt").read().strip().split(",")
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

    print("=" * 70)
    print("  ULTRA-POTENT HIV INHIBITOR SCREEN")
    print(f"  Base     : {BASE['name']}  {BASE['affinity']:.3f} kcal/mol")
    print(f"  Target   : -9.0 kcal/mol  (Darunavir level)")
    print(f"  Stretch  : -10.0 kcal/mol (beyond Darunavir)")
    print(f"  Center   : {center}")
    print("=" * 70)

    # Validate
    print("\n[VALIDATION]")
    valid = []
    for d in DESIGNS:
        mol = Chem.MolFromSmiles(d["smiles"])
        if mol:
            d["mw"]   = round(Descriptors.MolWt(mol), 1)
            d["logp"] = round(Descriptors.MolLogP(mol), 2)
            d["qed"]  = round(QED.qed(mol), 3)
            d["pred"] = round(BASE["affinity"] - d["expected_boost"], 3)
            valid.append(d)
            print(f"  ✓ {d['name']:<12} MW={d['mw']:>6.0f}  LogP={d['logp']:>5.2f}  "
                  f"QED={d['qed']:.3f}  Pred={d['pred']:>7.3f}  {d['feature']}")
        else:
            print(f"  ✗ {d['name']:<12} INVALID SMILES — skipping")

    # Dock
    print(f"\n[DOCKING {len(valid)} ULTRA COMPOUNDS — Meeko only]")
    results = []
    for d in valid:
        print(f"\n  [{d['name']}] {d['feature']}")
        print(f"    Mechanism: {d['mechanism']}")
        pdbqt = to_pdbqt(d["smiles"], d["name"])
        if not pdbqt:
            print("    [-] Prep failed"); continue
        print("    Prep: OK  |  Running Vina...")
        aff, pose = vina_dock(pdbqt, d["name"], center,
                              args.size, args.exhaustiveness, args.cpu)
        if aff is not None:
            d["affinity"] = aff
            d["pose"]     = pose
            delta = aff - BASE["affinity"]
            results.append(d)
            print(f"    Affinity : {aff:.3f} kcal/mol  ({delta:+.3f} vs base)")
            if   aff < -10.0: print("    ★★★★ BEYOND DARUNAVIR!")
            elif aff <  -9.0: print("    ★★★  DRUG CANDIDATE! Darunavir-level!")
            elif aff <  -8.5: print("    ★★   Excellent — near clinical territory!")
            elif aff <  -8.0: print("    ★    Very strong binder!")
            elif aff <  -7.5: print("         Strong binder")
        else:
            print("    [-] Docking failed")

    if not results:
        print("\n[!] No results."); return

    results.sort(key=lambda x: x["affinity"])
    best = results[0]

    print("\n" + "=" * 70)
    print("  ULTRA RANKINGS")
    print("=" * 70)
    print(f"  {'Name':<12} {'Affinity':>10}  {'Delta':>8}  {'MW':>6}  {'QED':>6}  Feature")
    print("  " + "-" * 67)
    print(f"  {BASE['name']:<12} {BASE['affinity']:>10.3f}  {'(base)':>8}")
    for r in results:
        delta = r["affinity"] - BASE["affinity"]
        star = "★" if r["affinity"] < -8.0 else ("·" if r["affinity"] < BASE["affinity"] else " ")
        print(f"  {r['name']:<12} {r['affinity']:>10.3f}  {delta:>+8.3f}  "
              f"{r['mw']:>6.0f}  {r['qed']:>6.3f}  {star} {r['feature'][:30]}")

    print(f"\n  ╔══════════════════════════════════════════════════════════╗")
    print(f"  ║  BEST     : {best['name']}  {best['affinity']:.3f} kcal/mol")
    print(f"  ║  Feature  : {best['feature']}")
    print(f"  ║  Mechanism: {best['mechanism']}")
    print(f"  ║  Gap -9.0 : {best['affinity']-(-9.0):.3f} kcal/mol")
    print(f"  ║  Gap -10.0: {best['affinity']-(-10.0):.3f} kcal/mol")
    print(f"  ╚══════════════════════════════════════════════════════════╝")

    with open("ultra_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: ultra_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()