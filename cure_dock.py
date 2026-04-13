# -*- coding: utf-8 -*-
"""
CURE Drug Discovery — Meeko-Only Docking Pipeline
All ligand prep uses Meeko. Never obabel.

Usage:
    python cure_dock.py                    # dock DESIGNS list below
    python cure_dock.py --gen 8            # auto-label as CURE_8G
    python cure_dock.py --exhaustiveness 16

Add new compounds to DESIGNS and run.
"""

import os, json, subprocess, argparse
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from meeko import MoleculePreparation, PDBQTWriterLegacy

# ─────────────────────────────────────────────────────────────────────────────
# ADD YOUR COMPOUNDS HERE
# ─────────────────────────────────────────────────────────────────────────────

DESIGNS = [
    # CURE_12G: Build on CURE_11G_007 (naphthalene + meta-F-benzyl + bis-THF)
    # Best: -7.265. Strategy: double down on meta-F, tune every position
    {
        "name": "CURE_12G_001",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "11G_007 + chiral OH (R) — stereooptimize the winner",
    },
    {
        "name": "CURE_12G_002",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "11G_007 chiral S OH — test other enantiomer",
    },
    {
        "name": "CURE_12G_003",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "11G_007 exact — reconfirm with fresh pdbqt",
    },
    {
        "name": "CURE_12G_004",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cc(F)cc(F)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "3,5-difluorobenzyl P1 — two F atoms at meta positions",
    },
    {
        "name": "CURE_12G_005",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(Cl)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "meta-chlorobenzyl + bis-THF — Cl vs F at meta",
    },
    {
        "name": "CURE_12G_006",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(C(F)(F)F)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "meta-trifluoromethylbenzyl — CF3 at meta, max electron withdrawal",
    },
    {
        "name": "CURE_12G_007",
        "smiles": "Oc1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "note": "Hydroxynaphthyl + meta-F-benzyl + bis-THF — combine 11G_007 + 11G_008",
    },
    {
        "name": "CURE_12G_008",
        "smiles": "c1ccc2ccc(C(=O)N[C@@H](Cc3cccc(F)c3)C(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)nc2c1",
        "note": "Isoquinoline + meta-F-benzyl + bis-THF — swap ring keep F",
    },
    {
        "name": "CURE_12G_009",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)C(O)CNC(=O)[C@@H]3CO[C@@H]4OCCO[C@@H]34)ccc2c1",
        "note": "11G_007 + inverted bis-THF stereo — test other bis-THF enantiomer",
    },
    {
        "name": "CURE_12G_010",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)C(O)CNC(=O)[C@H]3CO[C@@H]4OCCO[C@@H]34)ccc2c1",
        "note": "11G_007 + mixed bis-THF stereo — third stereoisomer",
    },
]

BASELINE = {"name": "CURE_11G_007", "affinity": -7.265}

# ─────────────────────────────────────────────────────────────────────────────
# MEEKO PREP — single function used everywhere
# ─────────────────────────────────────────────────────────────────────────────

def to_pdbqt(smiles, name, out_dir="ligand_meeko"):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.pdbqt")
    if os.path.exists(path):
        return path
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"    [!] Invalid SMILES"); return None
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0:
            if AllChem.EmbedMolecule(mol, randomSeed=42) != 0:
                print(f"    [!] 3D embedding failed"); return None
        AllChem.MMFFOptimizeMolecule(mol)
        prep = MoleculePreparation()
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        open(path, "w").write(pdbqt_str)
        return path
    except Exception as e:
        print(f"    [!] Meeko error: {e}"); return None


# ─────────────────────────────────────────────────────────────────────────────
# VINA DOCKING
# ─────────────────────────────────────────────────────────────────────────────

def vina_dock(pdbqt, name, center, size=25, exhaustiveness=16, cpu=6):
    os.makedirs("docking_results", exist_ok=True)
    out = f"docking_results/{name}_out.pdbqt"
    cmd = [
        "./bin/vina.exe",
        "--receptor",       "hiv_protease.pdbqt",
        "--ligand",         pdbqt,
        "--center_x",       str(center[0]),
        "--center_y",       str(center[1]),
        "--center_z",       str(center[2]),
        "--size_x",         str(size),
        "--size_y",         str(size),
        "--size_z",         str(size),
        "--out",            out,
        "--exhaustiveness", str(exhaustiveness),
        "--num_modes",      "9",
        "--cpu",            str(cpu),
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
                        if aff < 5:           # filter +10.0 errors
                            modes.append(aff)
                    except ValueError:
                        pass
        return (min(modes), out) if modes else (None, None)
    except Exception as e:
        print(f"    [!] Vina error: {e}"); return None, None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exhaustiveness", type=int, default=16)
    parser.add_argument("--size",           type=int, default=25)
    parser.add_argument("--cpu",            type=int, default=6)
    args = parser.parse_args()

    coords = open("hiv_binding_site.txt").read().strip().split(",")
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

    print("=" * 68)
    print("  CURE DRUG DISCOVERY — MEEKO PIPELINE")
    print(f"  Baseline : {BASELINE['name']}  {BASELINE['affinity']:.3f} kcal/mol  (meeko)")
    print(f"  Target   : -9.0 kcal/mol")
    print(f"  Center   : {center}")
    print(f"  Box      : {args.size} Å  |  Exhaustiveness: {args.exhaustiveness}")
    print("=" * 68)

    # Validate SMILES
    print("\n[VALIDATION]")
    valid = []
    for d in DESIGNS:
        mol = Chem.MolFromSmiles(d["smiles"])
        if mol:
            d["mw"]   = round(Descriptors.MolWt(mol), 1)
            d["logp"] = round(Descriptors.MolLogP(mol), 2)
            d["hbd"]  = Descriptors.NumHDonors(mol)
            d["hba"]  = Descriptors.NumHAcceptors(mol)
            valid.append(d)
            print(f"  ✓ {d['name']:<16} MW={d['mw']:>6.0f}  "
                  f"LogP={d['logp']:>5.2f}  HBD={d['hbd']}  HBA={d['hba']}  {d['note']}")
        else:
            print(f"  ✗ {d['name']:<16} INVALID SMILES")

    # Dock
    print(f"\n[DOCKING {len(valid)} COMPOUNDS — Meeko prep only]")
    results = []
    for d in valid:
        print(f"\n  [{d['name']}] {d['note']}")
        pdbqt = to_pdbqt(d["smiles"], d["name"])
        if not pdbqt:
            print("    [-] Prep failed"); continue
        print(f"    Prep: ✓  |  Running Vina...")
        aff, pose = vina_dock(pdbqt, d["name"], center,
                              args.size, args.exhaustiveness, args.cpu)
        if aff is not None:
            d["affinity"] = aff
            d["pose"]     = pose
            delta = aff - BASELINE["affinity"]
            results.append(d)
            print(f"    Affinity : {aff:.3f} kcal/mol  ({delta:+.3f} vs baseline)")
            if   aff < -9.0: print("    ★★★ DRUG CANDIDATE!")
            elif aff < -8.0: print("    ★★  Excellent!")
            elif aff < -7.5: print("    ★   Very strong!")
            elif aff < -7.0: print("        Strong binder")
            elif aff < -6.8: print("        Above baseline")
        else:
            print("    [-] Docking failed")

    if not results:
        print("\n[!] No results."); return

    results.sort(key=lambda x: x["affinity"])
    best = results[0]

    # Results table
    print("\n" + "=" * 68)
    print("  FINAL RANKINGS")
    print("=" * 68)
    print(f"  {'Name':<16} {'Affinity':>10}  {'Delta':>8}  {'MW':>6}  Note")
    print("  " + "-" * 65)
    print(f"  {BASELINE['name']:<16} {BASELINE['affinity']:>10.3f}  {'(base)':>8}")
    for r in results:
        delta = r["affinity"] - BASELINE["affinity"]
        star  = "★" if r["affinity"] < -7.5 else ("·" if r["affinity"] < BASELINE["affinity"] else " ")
        print(f"  {r['name']:<16} {r['affinity']:>10.3f}  {delta:>+8.3f}  "
              f"{r['mw']:>6.0f}  {star} {r['note'][:35]}")

    print(f"\n  ╔══════════════════════════════════════════════════════╗")
    print(f"  ║  BEST  : {best['name']}  {best['affinity']:.3f} kcal/mol")
    print(f"  ║  Note  : {best['note']}")
    print(f"  ║  Gap   : {best['affinity']-(-9.0):.3f} kcal/mol to -9.0")
    print(f"  ╚══════════════════════════════════════════════════════╝")

    with open("cure_meeko_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: cure_meeko_results.json")
    print("=" * 68)


if __name__ == "__main__":
    main()