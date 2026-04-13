# analyze_molecule_structure_updated.py
# Drop-in replacement for synthesis analysis functions in complete_quantum_drug_discovery.py
#
# CHANGES vs original:
#   1. _is_endocyclic_match() — checks if FG atom is IN a ring (fixes lactam misclassification)
#   2. Endocyclic check for lactam/lactone/oxazolone (no more false "Macrolactam" on exo-amides)
#   3. Clean "MacroX" prefix — no "Macromacrolactone" double-prefix bug
#   4. Complexity: macrocycles get hard categorical floor (+15), not linear ring count
#   5. _deterministic_noise() replaces random.uniform() — same SMILES = same score always
#   6. Removed dead get_synthetic_challenges() (was never called)
#   7. next_steps and synthesis_note are structure-specific

import hashlib
import random
from rdkit import Chem
from rdkit.Chem import Descriptors


def _is_endocyclic_match(mol, smarts: str, atom_index_in_match: int) -> bool:
    """
    Returns True if the atom at position `atom_index_in_match` in any SMARTS
    match is inside a ring — i.e. the functional group is endocyclic.
    Distinguishes e.g. lactam (N in ring) from exocyclic amide (N outside ring).
    """
    ring_atoms: set = set()
    for ring in mol.GetRingInfo().AtomRings():
        ring_atoms.update(ring)
    pattern = Chem.MolFromSmarts(smarts)
    if pattern is None:
        return False
    for match in mol.GetSubstructMatches(pattern):
        if match[atom_index_in_match] in ring_atoms:
            return True
    return False


def analyze_molecule_structure(smiles: str) -> dict | None:
    """
    Analyze a molecule by SMILES and return a structure-specific synthesis
    assessment dict ready for the /api/synthesis_plan JSON response.
    Returns None if the SMILES is invalid.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    # Ring information
    ring_info      = mol.GetRingInfo()
    n_rings        = ring_info.NumRings()
    ring_sizes     = [len(r) for r in ring_info.AtomRings()]
    largest_ring   = max(ring_sizes) if ring_sizes else 0
    has_macrocycle = largest_ring > 8

    # Atom counts
    n_hetero   = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() not in (6, 1))
    n_nitrogen = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 7)
    n_oxygen   = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 8)
    n_sulfur   = sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() == 16)
    rotatable  = Descriptors.NumRotatableBonds(mol)

    # Functional group detection
    # (display_name, smarts, check_endocyclic, key_atom_idx_in_match)
    fg_patterns = [
        ("Lactam",          "C(=O)N",     True,  2),
        ("Lactone",         "C(=O)O",     True,  2),
        ("Oxazolone",       "C(=O)OC=N",  True,  4),
        ("Amide",           "C(=O)N",     False, None),
        ("Ester",           "C(=O)OC",    False, None),
        ("Carboxylic Acid", "C(=O)O",     False, None),
        ("Ketone",          "CC(=O)C",    False, None),
        ("Aldehyde",        "[CH]=O",     False, None),
        ("Alcohol",         "[OH]",       False, None),
        ("Amine",           "[NH2]",      False, None),
        ("Sulfonamide",     "S(=O)(=O)N", False, None),
        ("Sulfone",         "S(=O)(=O)",  False, None),
        ("Ether",           "COC",        False, None),
        ("Alkene",          "C=C",        False, None),
        ("Alkyne",          "C#C",        False, None),
        ("Nitrile",         "C#N",        False, None),
        ("Halide",          "[F,Cl,Br,I]",False, None),
        ("Benzene",         "c1ccccc1",   False, None),
        ("Pyridine",        "c1ccncc1",   False, None),
        ("Pyrimidine",      "c1cncnc1",   False, None),
        ("Imidazole",       "c1cnc[nH]1", False, None),
    ]

    detected:   list = []
    seen_names: set  = set()

    for name, smarts, check_endo, key_idx in fg_patterns:
        patt = Chem.MolFromSmarts(smarts)
        if patt is None or not mol.HasSubstructMatch(patt):
            continue
        if check_endo:
            if _is_endocyclic_match(mol, smarts, key_idx):
                display = f"Macro{name}" if has_macrocycle else name
                if display not in seen_names:
                    detected.append(display)
                    seen_names.add(display)
        else:
            if name == "Amide" and any("Lactam" in d for d in detected):
                continue
            if name == "Ester" and any("Lactone" in d for d in detected):
                continue
            if name not in seen_names:
                detected.append(name)
                seen_names.add(name)

    # Complexity scoring — macrocycles get a hard categorical floor
    complexity_score = 0.0
    if has_macrocycle:
        complexity_score += 15.0
        complexity_score += float(largest_ring - 9)
    else:
        complexity_score += n_rings * 2.0
    complexity_score += n_hetero  * 0.8
    complexity_score += rotatable / 4.0
    complexity_score += n_sulfur  * 1.5

    if complexity_score > 18 or (has_macrocycle and largest_ring > 11):
        complexity = "Very High"
    elif complexity_score > 12 or has_macrocycle:
        complexity = "High"
    elif complexity_score > 6:
        complexity = "Medium"
    else:
        complexity = "Low"

    # Realistic estimates
    if has_macrocycle:
        if largest_ring > 12:
            base_yield, yield_range, cost, steps = 8,  "5-12%",  "20,000-40,000", 12
        else:
            base_yield, yield_range, cost, steps = 12, "8-18%",  "12,000-25,000", 10
    elif n_rings > 3:
        base_yield, yield_range, cost, steps = 30, "20-40%", "8,000-15,000",  9
    elif n_rings > 2:
        base_yield, yield_range, cost, steps = 45, "35-55%", "4,000-8,000",   7
    elif n_rings == 2:
        base_yield, yield_range, cost, steps = 55, "45-65%", "2,500-5,000",   6
    else:
        base_yield, yield_range, cost, steps = 65, "55-75%", "1,500-3,500",   4
    if n_hetero > 5: steps += 2
    if n_sulfur  > 1: steps += 1

    # Synthetic challenges (structure-specific)
    challenges = []
    if has_macrocycle:
        challenges.append(
            f"Macrocyclization — {largest_ring}-membered ring requires high-dilution "
            f"(0.1-1 mM), slow addition 12-24 h, typical yield 8-18%. "
            f"Risk of oligomerization."
        )
        if any("Lactam" in d for d in detected):
            challenges.append(
                "Endocyclic lactam closure — use HATU/DIPEA or Mukaiyama reagent "
                "under high-dilution; avoid DCC (poor for macrolactams)."
            )
        if any("Lactone" in d for d in detected):
            challenges.append(
                "Endocyclic lactone closure — Yamaguchi or Corey-Nicolaou conditions "
                "recommended; try template assistance if yield <10%."
            )
    if any("Oxazolone" in d for d in detected):
        challenges.append(
            "Oxazolone ring — moisture-sensitive; anhydrous conditions at 0C to RT."
        )
    if n_nitrogen > 2:
        challenges.append(
            f"Multiple nitrogens ({n_nitrogen}) — selective Boc/Cbz/Fmoc "
            f"protection strategy required."
        )
    if n_sulfur > 0:
        challenges.append(
            f"Sulfur ({n_sulfur} atom{'s' if n_sulfur > 1 else ''}) — "
            f"oxidation state control critical; protect thiols if present."
        )
    if "Alkene" in detected and has_macrocycle:
        challenges.append(
            "Endocyclic alkene — consider ring-closing metathesis "
            "(Grubbs 2nd gen) as alternative macrocyclization strategy."
        )
    elif "Alkene" in detected:
        challenges.append("Alkene — control E/Z geometry; may isomerize under acid.")
    if n_rings > 3 and not has_macrocycle:
        challenges.append(
            f"Polycyclic ({n_rings} rings) — stereo control at ring junctions critical; "
            f"verify by X-ray or 2D NMR."
        )
    if not challenges:
        challenges.append(
            "Standard organic synthesis — no unusual challenges detected."
        )

    # Structure-aware synthesis note
    if has_macrocycle:
        synthesis_note = (
            f"{largest_ring}-membered macrocycle. Key challenge: ring closure. "
            f"Consider RCM (if alkene), macrolactamization (if N in ring), "
            f"or macrolactonization (if O in ring). High-dilution is non-negotiable."
        )
    elif n_rings > 2:
        synthesis_note = (
            f"Polycyclic scaffold ({n_rings} rings). Build rings in the correct "
            f"sequence; verify stereochemistry at each ring-forming step."
        )
    else:
        synthesis_note = (
            "Standard scaffold — linear retrosynthesis likely sufficient. "
            "Literature search for analogues recommended before starting."
        )

    # Structure-aware next steps
    next_steps = [
        "Search SciFinder/Reaxys for analogous scaffolds and precedent reactions",
        "Run AiZynthFinder retrosynthetic analysis on this exact SMILES",
        "Consult a medicinal chemist to validate the proposed route",
        "Test the most challenging step first at mg scale",
    ]
    if has_macrocycle:
        next_steps.append(
            f"Screen macrocyclization conditions for the {largest_ring}-membered "
            f"ring closure: solvents (THF/DMF/DCM), temperature, concentration"
        )
    elif n_rings > 2:
        next_steps.append("Map full stereochemical requirements before synthesis")
    else:
        next_steps.append(
            "Confirm building block availability (Sigma-Aldrich / Combi-Blocks)"
        )

    return {
        "smiles":            smiles,
        "n_rings":           n_rings,
        "ring_sizes":        ring_sizes,
        "largest_ring":      largest_ring,
        "has_macrocycle":    has_macrocycle,
        "detected_features": detected,
        "n_heteroatoms":     n_hetero,
        "n_nitrogen":        n_nitrogen,
        "n_oxygen":          n_oxygen,
        "n_sulfur":          n_sulfur,
        "rotatable_bonds":   rotatable,
        "complexity":        complexity,
        "complexity_score":  round(complexity_score, 1),
        "estimated_steps":   steps,
        "estimated_yield":   f"{base_yield}% ({yield_range})",
        "estimated_cost":    f"${cost}",
        "challenges":        challenges,
        "synthesis_note":    synthesis_note,
        "next_steps":        next_steps,
    }


def _deterministic_noise(smiles: str, target_name: str) -> float:
    """
    Deterministic float in [-0.5, 0.5] seeded on smiles+target.
    Replace random.uniform(-0.5, 0.5) in predict_binding() with this.
    Same compound always produces the same binding score across server restarts.

    Usage:
        # OLD: adj += random.uniform(-0.5, 0.5)
        # NEW: adj += _deterministic_noise(smiles, target_name)
    """
    seed = int(hashlib.md5(f"{smiles}:{target_name}".encode()).hexdigest()[:8], 16)
    return random.Random(seed).uniform(-0.5, 0.5)


if __name__ == "__main__":
    test_cases = [
        ("QDD-84903EE9 — 8-ring ether, exo-amide",
         "CC(=O)NC1=CC=COCC=C1",                                       False),
        ("QDD-D55A1B12 — 11+9 macrocycle",
         "O=C1C=C2C=CC=NC(C=CCCC=C2)O1",                              True),
        ("QDD-99A0DD89 — 10+6 bicyclic",
         "O=C1C=CNc2ccccc2CS(=O)(=O)CO1",                             True),
        ("QDD-86DDDBDF — 12+6 bicyclic",
         "O=NC[SH]1(=O)CCS(=O)C=CC=Nc2ccccc2CN1",                    True),
        ("QDD-4399f716 — original, 4 small rings",
         "CC1=CC=C(C=C1)NS(=O)(=O)C2=CC=C(C=C2)C3=CC=NN3C4=CC=NC=C4", False),
    ]

    print("=" * 65)
    print("VALIDATION")
    print("=" * 65)
    all_pass = True
    for label, smiles, expect_macro in test_cases:
        r  = analyze_molecule_structure(smiles)
        ok = r["has_macrocycle"] == expect_macro
        if not ok: all_pass = False
        print(f"\n{'✅' if ok else '❌'}  {label}")
        print(f"   rings        : {r['ring_sizes']}")
        print(f"   macrocycle   : {r['has_macrocycle']}  (expected {expect_macro})")
        print(f"   complexity   : {r['complexity']}  (score {r['complexity_score']})")
        print(f"   features     : {r['detected_features']}")
        print(f"   yield/cost   : {r['estimated_yield']} / {r['estimated_cost']}")
        print(f"   challenge[0] : {r['challenges'][0][:72]}...")

    print(f"\n{'ALL PASS ✅' if all_pass else 'SOME FAILURES ❌'}")

    print("\n── Deterministic noise ──────────────────────────────────────")
    s = "O=C1C=CNc2ccccc2CS(=O)(=O)CO1"
    v1 = _deterministic_noise(s, "HIV Protease")
    v2 = _deterministic_noise(s, "HIV Protease")
    v3 = _deterministic_noise(s, "JAK (Arthritis)")
    print(f"   same call x2   : {v1:.4f} == {v2:.4f}  {'✅' if v1==v2 else '❌'}")
    print(f"   diff target    : {v1:.4f} != {v3:.4f}  {'✅' if v1!=v3 else '❌'}")