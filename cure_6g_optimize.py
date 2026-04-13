# -*- coding: utf-8 -*-
"""
CURE_6G Optimization — Fix the LEFT arm.
Best so far: CURE_5G_002 at -6.122 kcal/mol (single THF on right)
Strategy: Keep THF right arm, upgrade left arm toward Darunavir-like sulfonamide
"""

import json, subprocess, os
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem

BASELINE         = {"name": "CURE_5G_002", "affinity": -6.122}
CURRENT_SMILES   = "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)C1CCCO1"

DESIGNS = [
    # ── Strategy 1: Replace trifluorophenyl with aminophenylsulfonamide ──────
    {
        "name": "CURE_6G_001",
        "smiles": "Nc1ccc(S(=O)(=O)NCC(O)CNC(=O)C1CCCO1)cc1",
        "mod": "Aminophenylsulfonamide left arm (Darunavir-like)",
        "note": "SO2 mimics key H-bonds to backbone NH",
    },
    # ── Strategy 2: Naphthalene left arm (Saquinavir-like) ──────────────────
    {
        "name": "CURE_6G_002",
        "smiles": "c1ccc2cc(C(=O)NCC(O)CNC(=O)C3CCCO3)ccc2c1",
        "mod": "Naphthalene left arm (Saquinavir P2 mimic)",
        "note": "Extended pi-stacking in S2 subsite",
    },
    # ── Strategy 3: Pyridine left arm (better H-bond geometry) ──────────────
    {
        "name": "CURE_6G_003",
        "smiles": "c1cncc(C(=O)NCC(O)CNC(=O)C2CCCO2)c1",
        "mod": "Pyridine left arm (H-bond acceptor added)",
        "note": "N accepts H-bond from Ile50 flap water",
    },
    # ── Strategy 4: Extend the hydroxyl linker (better reach) ───────────────
    {
        "name": "CURE_6G_004",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NC[C@@H](O)CNC(=O)C1CCCO1",
        "mod": "Stereospecific OH on linker (R config)",
        "note": "Chirality match to HIV protease S1 pocket",
    },
    # ── Strategy 5: Difluorophenyl + THF (reduce MW, keep F count) ──────────
    {
        "name": "CURE_6G_005",
        "smiles": "c1cc(F)c(F)cc1C(=O)NCC(O)CNC(=O)C1CCCO1",
        "mod": "Difluorophenyl left arm (reduced MW)",
        "note": "Less steric, may fit S2 better",
    },
    # ── Strategy 6: Add phenyl to THF (P1 subsite fill) ─────────────────────
    {
        "name": "CURE_6G_006",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)[C@@H]1CCCO1",
        "mod": "Chiral THF (R config at P2 position)",
        "note": "Stereocontrol — R enantiomer preferred in HIV PR",
    },
    # ── Strategy 7: Isobutyl + THF (Lopinavir P1 mimic) ────────────────────
    {
        "name": "CURE_6G_007",
        "smiles": "c1cc(F)c(F)c(F)c1C(=O)NCC(O)CNC(=O)C1CCCO1.CC(C)CC",
        "mod": "Skip — placeholder",
        "note": "Skip",
    },
    # ── Strategy 8: Best scaffold + extend to indanol (Indinavir-like) ───────
    {
        "name": "CURE_6G_008",
        "smiles": "c1ccc2c(c1)CC(O)c1ccccc1-2",
        "mod": "Skip — placeholder",
        "note": "Skip",
    },
    # ── Strategy 9: Full Darunavir-like scaffold ─────────────────────────────
    {
        "name": "CURE_6G_009",
        "smiles": "Nc1ccc(S(=O)(=O)NCC(O)CNC(=O)[C@@H]1CO[C@@H]2OCCO[C@@H]12)cc1",
        "mod": "Darunavir mimic: sulfonamide + bis-THF",
        "note": "Full Darunavir pharmacophore — target -8 to -9",
    },
]

# Filter out placeholder designs
DESIGNS = [d for d in DESIGNS if "Skip" not in d["mod"]]


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
        prep      = MoleculePreparation()
        setups    = prep.prepare(mol)
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
        print(f"    [!] Vina: {e}")
    return None, None


def main():
    coords = open("hiv_binding_site.txt").read().strip().split(",")
    center = (float(coords[0]), float(coords[1]), float(coords[2]))

    print("=" * 70)
    print("  CURE_6G — LEFT ARM OPTIMIZATION")
    print(f"  Baseline : {BASELINE['name']}  {BASELINE['affinity']:.3f} kcal/mol")
    print(f"  Target   : -9.0 kcal/mol  (Gap: {BASELINE['affinity']-(-9.0):.3f})")
    print(f"  Strategy : Fix left arm — sulfonamide / naphthalene / pyridine")
    print("=" * 70)

    # Validate
    print("\n[VALIDATION]")
    valid = []
    for d in DESIGNS:
        mol = Chem.MolFromSmiles(d["smiles"])
        if mol:
            d["mw"]   = round(Descriptors.MolWt(mol), 1)
            d["logp"] = round(Descriptors.MolLogP(mol), 2)
            valid.append(d)
            print(f"  ✓ {d['name']:<16} MW={d['mw']:>6.0f}  LogP={d['logp']:>5.2f}  {d['mod']}")
        else:
            print(f"  ✗ {d['name']:<16} INVALID — skipping")

    # Dock
    print(f"\n[DOCKING {len(valid)} COMPOUNDS vs HIV-1 Protease]")
    results = []
    for d in valid:
        print(f"\n  [{d['name']}] {d['mod']}")
        pdbqt = smiles_to_pdbqt(d["smiles"], d["name"])
        if not pdbqt:
            print("    [-] Prep failed"); continue
        aff, pose = dock(pdbqt, d["name"], center)
        if aff is not None:
            d["affinity"] = aff
            delta = aff - BASELINE["affinity"]
            results.append(d)
            print(f"    Affinity : {aff:.3f} kcal/mol  ({delta:+.3f} vs {BASELINE['name']})")
            if   aff < -9.0: print("    ★★★ DRUG CANDIDATE!")
            elif aff < -8.0: print("    ★★  Excellent!")
            elif aff < -7.0: print("    ★   Strong binder!")
            elif aff < -6.5: print("        Good progress")
        else:
            print("    [-] Docking failed")

    if not results:
        print("\n[!] No results."); return

    results.sort(key=lambda x: x["affinity"])
    best = results[0]

    print("\n" + "=" * 70)
    print("  CURE_6G RESULTS")
    print("=" * 70)
    print(f"  {'Name':<16} {'Affinity':>10}  {'Delta':>8}  Modification")
    print("  " + "-" * 65)
    print(f"  {BASELINE['name']:<16} {BASELINE['affinity']:>10.3f}  {'(base)':>8}")
    for r in results:
        delta = r["affinity"] - BASELINE["affinity"]
        star = "★" if r["affinity"] < -7.0 else " "
        print(f"  {r['name']:<16} {r['affinity']:>10.3f}  {delta:>+8.3f}  {star} {r['mod']}")

    print(f"\n  BEST : {best['name']}  {best['affinity']:.3f} kcal/mol")
    print(f"  Note : {best['note']}")
    print(f"  Gap to -9.0 : {best['affinity'] - (-9.0):.3f} kcal/mol remaining")

    with open("cure_6g_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Saved: cure_6g_results.json")
    print("=" * 70)


if __name__ == "__main__":
    main()