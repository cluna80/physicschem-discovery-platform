# de_novo_egfr_agent_fixed.py
# Fixed & Improved Fragment-Based EGFR De Novo Discovery
# v3: aromatic-safe crossover + diversity enforcement + single-molecule filter

import sys, json, random, copy
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, FragmentOnBonds, GetMolFrags, SanitizeMol
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# ===========================================
# CONFIG
# ===========================================

POPULATION_SIZE   = 120
GENERATIONS       = 40
ELITE_SIZE        = 8          # Reduced — fewer elites = less clonal pressure
TOURNAMENT_SIZE   = 5
MUTATION_RATE     = 0.55       # Higher — need more exploration
CROSSOVER_RATE    = 0.60
IMMIGRANT_RATE    = 0.12       # 12% fresh random molecules injected each generation
DIVERSITY_PENALTY = 8.0        # Fitness penalty per near-duplicate in population

WORK_DIR = Path("egfr_fragment_based_fixed")
WORK_DIR.mkdir(exist_ok=True)

# ===========================================
# EGFR FRAGMENT LIBRARY
# ===========================================

FRAGMENT_LIBRARY = [
    Chem.MolFromSmiles(s) for s in [
        # Hinge-binding cores
        "c1ncnc2ccccc12",           # quinazoline
        "c1ccnc(N)nc1",             # aminopyrimidine
        "c1ccc2ncncc2c1",           # quinoline
        "c1cnc2ccccc2n1",           # quinoxaline
        "c1ccc2[nH]cnc2c1",         # benzimidazole
        "c1ccc2nccnc2c1",           # phthalazine
        # Aniline / aryl warheads
        "Nc1ccccc1",
        "Nc1ccc(F)cc1",
        "Nc1ccc(Cl)cc1",
        "Nc1cccc(OC)c1",
        "COc1ccccc1",
        "c1ccc(F)cc1",
        "c1ccc(Cl)cc1",
        # Acrylamide warhead (covalent EGFR)
        "C=CC(=O)N",
        "C=CC(=O)NCCN",
        # Linkers / solubilizers
        "OCCOC",
        "OCCCN1CCOCC1",
        "CN(C)CCN",
        "NCCO",
        "COCCN",
        "N1CCOCC1",
        "CNCCNC",
        # Simple aliphatics
        "C#C",
        "c1ccccc1",
    ]
]
FRAGMENT_LIBRARY = [m for m in FRAGMENT_LIBRARY if m is not None]

# ===========================================
# UTILITIES
# ===========================================

def clean_molecule(mol):
    """
    Sanitize molecule, remove dummy atoms, and REJECT multi-fragment SMILES.
    Returns (mol, smiles) or (None, "") on failure.
    """
    if not mol:
        return None, ""
    try:
        rw = Chem.RWMol(mol)
        dummies = [a.GetIdx() for a in rw.GetAtoms() if a.GetAtomicNum() == 0]
        for idx in sorted(dummies, reverse=True):
            rw.RemoveAtom(idx)

        mol = rw.GetMol()
        Chem.SanitizeMol(mol)
        smiles = Chem.MolToSmiles(mol, canonical=True)

        # *** Reject disconnected multi-fragment molecules ***
        if '.' in smiles:
            return None, ""

        return mol, smiles
    except Exception:
        return None, ""


def create_random_molecule_from_fragments():
    """Build a diverse starting molecule by chaining fragments."""
    core = random.choice(FRAGMENT_LIBRARY)
    mol = Chem.Mol(core)

    n_additions = random.randint(2, 5)
    for _ in range(n_additions):
        frag = random.choice(FRAGMENT_LIBRARY)
        combined = Chem.CombineMols(mol, frag)
        rw = Chem.RWMol(combined)
        a1 = random.randint(0, mol.GetNumAtoms() - 1)
        a2 = mol.GetNumAtoms() + random.randint(0, frag.GetNumAtoms() - 1)
        rw.AddBond(a1, a2, Chem.BondType.SINGLE)
        candidate = rw.GetMol()
        cleaned, smiles = clean_molecule(candidate)
        if cleaned:
            mol = cleaned  # only accept clean intermediates

    return clean_molecule(mol)


def smiles_fingerprint(smiles):
    """Morgan fingerprint as a bit set for Tanimoto similarity."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return set()
    from rdkit.Chem import AllChem
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=1024)
    return set(fp.GetOnBits())


def tanimoto(fp1, fp2):
    if not fp1 or not fp2:
        return 0.0
    inter = len(fp1 & fp2)
    union = len(fp1 | fp2)
    return inter / union if union else 0.0


# ===========================================
# GENETIC OPERATORS
# ===========================================

def _get_single_bonds(mol):
    """Return indices of all non-aromatic single bonds — safe to fragment."""
    return [
        b.GetIdx() for b in mol.GetBonds()
        if not b.GetIsAromatic() and b.GetBondTypeAsDouble() == 1.0
    ]


def _safe_fragment(mol, bond_idx):
    """
    Break a single bond and return sanitized fragment mols.
    Returns None if anything goes wrong.
    """
    try:
        broken = FragmentOnBonds(mol, [bond_idx], addDummies=False)
        frags = GetMolFrags(broken, asMols=True, sanitizeFrags=False)
        sanitized = []
        for f in frags:
            try:
                SanitizeMol(f)
                sanitized.append(f)
            except Exception:
                return None
        return sanitized if len(sanitized) >= 2 else None
    except Exception:
        return None


def crossover_molecules(p1, p2):
    """
    Fragment-based crossover cutting only non-aromatic single bonds.
    Falls back to parents if no valid cut found.
    """
    mol1 = p1['mol']
    mol2 = p2['mol']

    bonds1 = _get_single_bonds(mol1)
    bonds2 = _get_single_bonds(mol2)

    if len(bonds1) < 2 or len(bonds2) < 2:
        return Chem.Mol(mol1), Chem.Mol(mol2)

    random.shuffle(bonds1)
    random.shuffle(bonds2)

    for b1 in bonds1:
        frags1 = _safe_fragment(mol1, b1)
        if frags1 is None:
            continue
        for b2 in bonds2:
            frags2 = _safe_fragment(mol2, b2)
            if frags2 is None:
                continue
            try:
                raw_c1 = Chem.CombineMols(frags1[0], frags2[1])
                raw_c2 = Chem.CombineMols(frags2[0], frags1[1])
                c1, _ = clean_molecule(raw_c1)
                c2, _ = clean_molecule(raw_c2)
                if c1 and c2:
                    return c1, c2
            except Exception:
                continue

    return Chem.Mol(mol1), Chem.Mol(mol2)


MUTATION_OPS = ['attach_fragment', 'atom_swap', 'delete_atom', 'replace_fragment']

def mutate_molecule(mol):
    if random.random() > MUTATION_RATE:
        return mol

    op = random.choices(
        MUTATION_OPS,
        weights=[0.50, 0.20, 0.15, 0.15]
    )[0]

    new_mol = Chem.Mol(mol)

    try:
        if op == 'attach_fragment':
            frag = random.choice(FRAGMENT_LIBRARY)
            combined = Chem.CombineMols(new_mol, frag)
            rw = Chem.RWMol(combined)
            a1 = random.randint(0, mol.GetNumAtoms() - 1)
            a2 = mol.GetNumAtoms() + random.randint(0, frag.GetNumAtoms() - 1)
            rw.AddBond(a1, a2, Chem.BondType.SINGLE)
            new_mol = rw.GetMol()

        elif op == 'atom_swap':
            candidates = [
                a for a in new_mol.GetAtoms()
                if not a.GetIsAromatic() and a.GetAtomicNum() in [6, 7, 8]
            ]
            if candidates:
                rw = Chem.RWMol(new_mol)
                atom = rw.GetAtomWithIdx(random.choice(candidates).GetIdx())
                atom.SetAtomicNum(random.choice([6, 7, 8, 9, 17]))
                new_mol = rw.GetMol()

        elif op == 'delete_atom':
            candidates = [
                a.GetIdx() for a in new_mol.GetAtoms()
                if not a.GetIsAromatic()
                and not a.IsInRing()
                and a.GetDegree() == 1
                and new_mol.GetNumAtoms() > 10
            ]
            if candidates:
                rw = Chem.RWMol(new_mol)
                rw.RemoveAtom(random.choice(candidates))
                new_mol = rw.GetMol()

        elif op == 'replace_fragment':
            bonds = _get_single_bonds(new_mol)
            if bonds:
                bond_idx = random.choice(bonds)
                frags = _safe_fragment(new_mol, bond_idx)
                if frags and len(frags) >= 2:
                    keep = frags[0] if random.random() < 0.5 else frags[1]
                    new_frag = random.choice(FRAGMENT_LIBRARY)
                    combined = Chem.CombineMols(keep, new_frag)
                    rw = Chem.RWMol(combined)
                    a1 = random.randint(0, keep.GetNumAtoms() - 1)
                    a2 = keep.GetNumAtoms() + random.randint(0, new_frag.GetNumAtoms() - 1)
                    rw.AddBond(a1, a2, Chem.BondType.SINGLE)
                    new_mol = rw.GetMol()

    except Exception:
        return mol

    cleaned, _ = clean_molecule(new_mol)
    return cleaned or mol


# ===========================================
# FITNESS FUNCTION
# ===========================================

EGFR_HINGE_SMARTS = [
    Chem.MolFromSmarts("c1ccnc(N)nc1"),           # aminopyrimidine
    Chem.MolFromSmarts("c1ncnc2ccccc12"),          # quinazoline core
    Chem.MolFromSmarts("c1ccnc(Nc2ccccc2)nc1"),   # N-aryl aminopyrimidine
    Chem.MolFromSmarts("[nH]c1ncnc2ccccc12"),      # NH quinazoline
    Chem.MolFromSmarts("c1ccc2nccnc2c1"),          # quinoxaline
]

EGFR_WARHEAD_SMARTS = [
    Chem.MolFromSmarts("C=CC(=O)N"),              # acrylamide (covalent)
    Chem.MolFromSmarts("C#C"),                     # alkyne
]

def calculate_fitness(mol):
    if not mol:
        return 0.0

    score = 0.0

    # Pharmacophore: hinge binders
    hinge_hits = sum(1 for p in EGFR_HINGE_SMARTS if p and mol.HasSubstructMatch(p))
    score += hinge_hits * 40.0

    # Warhead bonus
    warhead_hits = sum(1 for w in EGFR_WARHEAD_SMARTS if w and mol.HasSubstructMatch(w))
    score += warhead_hits * 15.0

    # Aromaticity
    aromatic = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic())
    score += min(aromatic * 0.6, 6.0)

    # H-bond features
    hba = Lipinski.NumHAcceptors(mol)
    hbd = Lipinski.NumHDonors(mol)
    score += min(hba * 0.5 + hbd * 0.8, 5.0)

    # MW sweet spot 340-520
    mw = Descriptors.MolWt(mol)
    if 340 <= mw <= 520:
        score += 25.0
    elif mw < 340:
        score += (mw / 340) * 15
    else:
        score -= (mw - 520) * 1.5

    # LogP sweet spot 2-4
    try:
        logp = Descriptors.MolLogP(mol)
    except Exception:
        logp = 99.0
    if 1.5 <= logp <= 4.5:
        score += 20.0 - abs(logp - 3.0) * 4.0
    elif logp < 1.5:
        score += logp * 5
    else:
        score -= (logp - 4.5) * 10

    # Rotatable bonds
    rot_bonds = Descriptors.NumRotatableBonds(mol)
    if 3 <= rot_bonds <= 8:
        score += 8.0
    elif rot_bonds > 10:
        score -= (rot_bonds - 10) * 3

    # Lipinski violations
    violations = sum([mw >= 500, logp >= 5.5, hbd >= 5, hba >= 10])
    score -= violations * 15

    # Ring count
    ring_count = Chem.rdMolDescriptors.CalcNumRings(mol)
    if ring_count >= 2:
        score += 10.0
    elif ring_count == 0:
        score -= 20.0

    return max(0.0, score)


# ===========================================
# DIVERSITY HELPERS
# ===========================================

def deduplicate_population(population):
    """Remove exact SMILES duplicates, keeping first occurrence."""
    seen = set()
    unique = []
    for ind in population:
        if ind['smiles'] not in seen:
            seen.add(ind['smiles'])
            unique.append(ind)
    return unique


def apply_diversity_penalty(population):
    """Penalize molecules very similar to higher-ranked members."""
    fps = [smiles_fingerprint(ind['smiles']) for ind in population]
    for i in range(1, len(population)):
        if not fps[i]:
            continue
        max_sim = max((tanimoto(fps[i], fps[j]) for j in range(i) if fps[j]), default=0.0)
        if max_sim > 0.85:
            population[i]['fitness'] -= DIVERSITY_PENALTY * max_sim
    return population


# ===========================================
# EVOLUTION
# ===========================================

def initialize_population(size):
    print("Building diverse fragment-based population...")
    population = []
    attempts = 0
    while len(population) < size and attempts < size * 8:
        attempts += 1
        mol, smiles = create_random_molecule_from_fragments()
        if mol and smiles and len(smiles) > 15:
            population.append({
                'id': f"GEN0_{len(population):03d}",
                'mol': mol,
                'smiles': smiles,
                'generation': 0,
                'fitness': 0.0
            })
    print(f"Created {len(population)} valid starting molecules\n")
    return population


def make_individual(mol, gen, idx):
    _, smiles = clean_molecule(mol)
    if not smiles or len(smiles) < 15:
        return None
    return {
        'id': f"GEN{gen}_{idx:03d}",
        'mol': mol,
        'smiles': smiles,
        'generation': gen,
        'fitness': 0.0
    }


def run_evolutionary_discovery():
    print("=" * 85)
    print("FIXED FRAGMENT-BASED EGFR DE NOVO DISCOVERY AGENT")
    print("Aromatic-safe • Single-molecule filter • Diversity-enforced")
    print("=" * 85 + "\n")

    population = initialize_population(POPULATION_SIZE)
    all_best = []
    seen_smiles = set()

    n_immigrants = max(5, int(POPULATION_SIZE * IMMIGRANT_RATE))

    for gen in range(GENERATIONS):
        print(f"\n{'=' * 85}")
        print(f"GENERATION {gen + 1}/{GENERATIONS}")
        print(f"{'=' * 85}")

        # Evaluate
        for ind in population:
            ind['fitness'] = calculate_fitness(ind['mol'])

        # Deduplicate then rank
        population = deduplicate_population(population)
        population.sort(key=lambda x: x['fitness'], reverse=True)

        # Apply diversity penalty
        population = apply_diversity_penalty(population)
        population.sort(key=lambda x: x['fitness'], reverse=True)

        print(f"\nTop 5 (Gen {gen + 1}):")
        for i, ind in enumerate(population[:5]):
            mw = Descriptors.MolWt(ind['mol'])
            print(f"  {i+1}. {ind['smiles'][:70]:<70} Fitness={ind['fitness']:.1f} MW={mw:.0f}")

        # Record best unique candidate this generation
        for ind in population:
            if ind['smiles'] not in seen_smiles:
                seen_smiles.add(ind['smiles'])
                all_best.append({
                    'generation': gen + 1,
                    'smiles': ind['smiles'],
                    'fitness': calculate_fitness(ind['mol']),
                    'mw': Descriptors.MolWt(ind['mol']),
                    'logp': Descriptors.MolLogP(ind['mol'])
                })
                break

        # Elites
        next_population = population[:ELITE_SIZE]

        # Inject immigrants
        immigrant_count = 0
        for _ in range(n_immigrants * 6):
            if immigrant_count >= n_immigrants:
                break
            mol, smiles = create_random_molecule_from_fragments()
            if mol and smiles and len(smiles) > 15:
                ind = make_individual(mol, gen + 1, len(next_population))
                if ind:
                    next_population.append(ind)
                    immigrant_count += 1

        # Breed offspring
        pool = population[:max(POPULATION_SIZE // 2, ELITE_SIZE + 4)]
        if len(pool) < TOURNAMENT_SIZE:
            pool = population

        offspring_attempts = 0
        while len(next_population) < POPULATION_SIZE and offspring_attempts < POPULATION_SIZE * 4:
            offspring_attempts += 1

            t1 = random.sample(pool, min(TOURNAMENT_SIZE, len(pool)))
            parent1 = max(t1, key=lambda x: x['fitness'])
            t2 = random.sample(pool, min(TOURNAMENT_SIZE, len(pool)))
            parent2 = max(t2, key=lambda x: x['fitness'])

            if random.random() < CROSSOVER_RATE:
                child1_mol, child2_mol = crossover_molecules(parent1, parent2)
            else:
                child1_mol = Chem.Mol(parent1['mol'])
                child2_mol = Chem.Mol(parent2['mol'])

            child1_mol = mutate_molecule(child1_mol)
            child2_mol = mutate_molecule(child2_mol)

            for child_mol in [child1_mol, child2_mol]:
                ind = make_individual(child_mol, gen + 1, len(next_population))
                if ind:
                    next_population.append(ind)
                if len(next_population) >= POPULATION_SIZE:
                    break

        population = next_population[:POPULATION_SIZE]

        unique_in_pop = len(set(ind['smiles'] for ind in population))
        print(f"  [Diversity] {unique_in_pop}/{len(population)} unique | "
              f"{immigrant_count} immigrants injected")

    # ===========================================
    # FINAL REPORT
    # ===========================================
    print("\n" + "=" * 85)
    print("EVOLUTION COMPLETE — Top Unique Candidates")
    print("=" * 85)

    all_best.sort(key=lambda x: x['fitness'], reverse=True)

    seen = set()
    unique_best = []
    for c in all_best:
        if c['smiles'] not in seen:
            seen.add(c['smiles'])
            unique_best.append(c)

    print(f"\n{'Rank':<4} {'SMILES':<62} {'Fitness':>8} {'MW':>6} {'LogP':>6} {'Gen':>5}")
    print("-" * 95)
    for i, cand in enumerate(unique_best[:20]):
        print(f"{i+1:<4} {cand['smiles'][:62]:<62} {cand['fitness']:>8.1f} "
              f"{cand['mw']:>6.0f} {cand['logp']:>6.2f} {cand['generation']:>5}")

    with open(WORK_DIR / "results.json", "w") as f:
        json.dump(unique_best[:50], f, indent=2)

    print(f"\nResults saved to {WORK_DIR}/results.json")
    return unique_best


if __name__ == "__main__":
    results = run_evolutionary_discovery()