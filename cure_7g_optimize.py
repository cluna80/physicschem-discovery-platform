# -*- coding: utf-8 -*-
"""
CURE_7G — Combine best left arm (naphthalene) with best right arm (THF)
Best so far: CURE_6G_002 naphthalene at -6.772 kcal/mol
Strategy:
  LEFT  = naphthalene (proven -6.772) → extend / substitute
  RIGHT = single THF (proven -6.122) → combine with naphthalene
  GOAL  = -8.0+ kcal/mol
"""

import json, subprocess, os
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem

BASELINE = {"name": "CURE_6G_002", "affinity": -6.772,
            "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1"}

DESIGNS = [
    # ── Core combination: naphthalene LEFT + THF RIGHT ───────────────────────
    {
        "name": "CURE_7G_001",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1",
        "mod": "Naphthalene + single THF (combine both winners)",
        "note": "Direct combination of CURE_6G_002 scaffold with THF right arm",
    },
    # ── Naphthyl + chiral center on linker ──────────────────────────────────
    {
        "name": "CURE_7G_002",
        "smiles": "c1ccc2cc(C(=O)N[C@@H](CO)CNC(=O)C3CCCO3)ccc2c1",
        "mod": "Naphthalene + THF + chiral hydroxymethyl linker",
        "note": "Stereocontrol on linker matches protease geometry",
    },
    # ── Naphthyl + bis-THF (correct SMILES this time) ───────────────────────
    {
        "name": "CURE_7G_003",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)[C@@H]3CO[C@H]4OCCO[C@H]34)ccc2c1",
        "mod": "Naphthalene + bis-THF (fixed ring numbering)",
        "note": "Uses unique ring numbers 3,4 — avoids previous conflict",
    },
    # ── 2-Naphthyl isomer (different pi-stack orientation) ──────────────────
    {
        "name": "CURE_7G_004",
        "smiles": "c1ccc2ccc(C(=O)NCC(O)CNC(=O)C3CCCO3)cc2c1",
        "mod": "2-Naphthyl isomer + THF (different binding angle)",
        "note": "2-position may access deeper S2 pocket",
    },
    # ── Naphthyl + fluorine on naphthalene (tune binding) ───────────────────
    {
        "name": "CURE_7G_005",
        "smiles": "c1cc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2cc1F",
        "mod": "Fluoronaphthyl + THF (F tunes electron density)",
        "note": "F at 6-position of naphthalene, improves S2 contacts",
    },
    # ── Naphthyl + extend hydroxyl to diol ──────────────────────────────────
    {
        "name": "CURE_7G_006",
        "smiles": "c1ccc2cc(C(=O)NCC(O)C(O)CNC(=O)C3CCCO3)ccc2c1",
        "mod": "Naphthalene + THF + diol linker",
        "note": "Second OH for additional H-bond to Asp25 catalytic dyad",
    },
    # ── Naphthyl + methylated THF (fill hydrophobic P2 pocket) ─────────────
    {
        "name": "CURE_7G_007",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCCO3)ccc2c1",
        "mod": "Naphthalene + THP ring (6-membered O-ring)",
        "note": "Slightly larger ring may fill P2 more completely",
    },
    # ── Naphthyl + isobutyl tail (Lopinavir P1 mimic) ───────────────────────
    {
        "name": "CURE_7G_008",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)CC(C)C)ccc2c1",
        "mod": "Naphthalene + isobutyl (P1 hydrophobic fill)",
        "note": "Replaces THF with isobutyl — tests P1 vs P2 preference",
    },
    # ── Naphthyl + benzyl (Saquinavir full mimic) ────────────────────────────
    {
        "name": "CURE_7G_009",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)Cc3ccccc3)ccc2c1",
        "mod": "Naphthalene + benzyl (Saquinavir P1 mimic)",
        "note": "Two aromatic systems — tests dual pi-stacking",
    },
    # ── BEST GUESS: Naphthyl + THF + extend left arm with OH ────────────────
    {
        "name": "CURE_7G_010",
        "smiles": "Oc1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1",
        "mod": "Hydroxynaphthyl + THF (H-bond donor on naphthalene)",
        "note": "OH on naphthalene reaches Asp29/30 directly",
    },
]


def smiles_to_pdbqt(smiles, name, out_dir="ligand_pdbqt"):
    os.makedirs(out_dir, exist_ok=True)
    pdbqt = os.path.join(out_dir, f"{name}.pdbqt")
    if os.path.exists(pdbqt):
        return pdbqt
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None: return None
        mol = Chem.AddHs(mol)
        if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0:
            AllChem.EmbedMolecule(mol, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol)
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        prep = MoleculePreparation()
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
        open(pdbqt, "w").write(pdbqt_str)
        return pdbqt
    except Exception as e:
        print(f"    [!] {e}")
        return None


def dock(pdbqt, name, center, size=25, exhaustiveness=16):
    os.makedirs("docking_results", exist_ok=True)
    out = f"docking_results/{name}_out.pdbqt"
    cmd = ["./bin/vina.exe",
           "--receptor", "hiv_protease.pdbqt",
           "--ligand", pdbqt,
           "--center_x", str(center[0]),
           "--center_y", str(center[1]),
           "--center_z", str(center[2]),
           "--size_x", str(size), "--size_y", str(size), "--size_z", str(size),
           "--out", out,
           "--exhaustiveness", str(exhaustiveness),
           "--num_modes", "9", "--cpu", "6"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        for line in r.stdout.splitlines():
            if line.strip().startswith("1 "):
                parts = line.split()
                if len(parts) >= 2:
                    return float(parts[1]), out
    except Exception as e:
        print(f"    [!] {e}")
    return None, None


def main():
    coords = open("hiv_binding_site.txt").read().strip().split(",")
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

    print("=" * 70)
    print("  CURE_7G — NAPHTHALENE + THF COMBINATION")
    print(f"  Baseline : {BASELINE['name']}  {BASELINE['affinity']:.3f} kcal/mol")
    print(f"  Target   : -8.0 kcal/mol this round, -9.0 final")
    print(f"  Strategy : Naphthalene left + THF right + variations")
    print("=" * 70)

    print("\n[VALIDATION]")
    valid = []
    for d in DESIGNS:
        mol = Chem.MolFromSmiles(d["smiles"])
        if mol:
            d["mw"]   = round(Descriptors.MolWt(mol), 1)
            d["logp"] = round(Descriptors.MolLogP(mol), 2)
            hbd = sum(1 for a in mol.GetAtoms() if a.GetSymbol() in ("O","N") and a.GetTotalNumHs() > 0)
            hba = sum(1 for a in mol.GetAtoms() if a.GetSymbol() in ("O","N"))
            d["hbd"] = hbd
            d["hba"] = hba
            valid.append(d)
            print(f"  ✓ {d['name']:<16} MW={d['mw']:>6.0f}  LogP={d['logp']:>5.2f}  "
                  f"HBD={hbd}  HBA={hba}  {d['mod']}")
        else:
            print(f"  ✗ {d['name']:<16} INVALID — skipping")

    print(f"\n[DOCKING {len(valid)} COMPOUNDS]")
    results = []
    for d in valid:
        print(f"\n  [{d['name']}] {d['mod']}")
        pdbqt = smiles_to_pdbqt(d["smiles"], d["name"])
        if not pdbqt:
            print("    [-] Prep failed"); continue
        aff, pose = dock(pdbqt, d["name"], center)
        if aff is not None:
            d["affinity"] = aff
            d["pose"] = pose
            delta = aff - BASELINE["affinity"]
            results.append(d)
            print(f"    Affinity : {aff:.3f} kcal/mol  ({delta:+.3f} vs baseline)")
            if   aff < -9.0: print("    ★★★ DRUG CANDIDATE!")
            elif aff < -8.0: print("    ★★  Excellent — clinical territory!")
            elif aff < -7.5: print("    ★   Very strong binder!")
            elif aff < -7.0: print("        Strong binder")
        else:
            print("    [-] Docking failed")

    if not results:
        print("\n[!] No results."); return

    results.sort(key=lambda x: x["affinity"])
    best = results[0]

    print("\n" + "=" * 70)
    print("  CURE_7G FINAL RANKINGS")
    print("=" * 70)
    print(f"  {'Name':<16} {'Affinity':>10}  {'Delta':>8}  {'MW':>6}  Modification")
    print("  " + "-" * 68)
    print(f"  {BASELINE['name']:<16} {BASELINE['affinity']:>10.3f}  {'(base)':>8}")
    for r in results:
        delta = r["affinity"] - BASELINE["affinity"]
        star = "★" if r["affinity"] < -7.5 else ("·" if r["affinity"] < -7.0 else " ")
        print(f"  {r['name']:<16} {r['affinity']:>10.3f}  {delta:>+8.3f}  {r['mw']:>6.0f}  {star} {r['mod']}")

    print(f"\n  ╔══════════════════════════════════════════════════╗")
    print(f"  ║  BEST : {best['name']}  {best['affinity']:.3f} kcal/mol")
    print(f"  ║  Note : {best['note']}")
    print(f"  ║  Gap to -9.0 : {best['affinity']-(-9.0):.3f} kcal/mol remaining")
    print(f"  ╚══════════════════════════════════════════════════╝")

    with open("cure_7g_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: cure_7g_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()