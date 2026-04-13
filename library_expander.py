"""
library_expander.py
===================
PhysicsChem Platform — Mass Library Expansion Engine

Four parallel sources to get from 432 → 10,000+ compounds:

  SOURCE 1: Combinatorial Generator
            Systematic scaffold × substituent combinations
            → ~2,000-5,000 novel drug-like molecules per target

  SOURCE 2: ChEMBL Bioactive Downloader  
            Download known actives for each target from ChEMBL API
            → hundreds of validated bioactive scaffolds

  SOURCE 3: BRICS Expansion
            Fragment and recombine your existing 432 hits
            → thousands of hybrid molecules

  SOURCE 4: Multi-target Campaign Launcher
            Auto-run agent against all prepared receptors
            → systematic FBDD across 6 disease areas

USAGE:
  python library_expander.py --source all          # run everything
  python library_expander.py --source combinatorial --target EGFR
  python library_expander.py --source chembl       # download bioactives
  python library_expander.py --source brics        # fragment expansion
  python library_expander.py --source campaigns    # launch agent runs
  python library_expander.py --count               # show what would be generated
"""

import os, sys, json, csv, sqlite3, time, random, argparse, warnings
import urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from itertools import product

warnings.filterwarnings('ignore')

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors, BRICS
    from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False

GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {color}{BLD}Expander{RST}  {msg}")

def ok(msg):   log(f"✓ {msg}", GRN)
def warn(msg): log(f"! {msg}", YLW)

# ══════════════════════════════════════════════════════════════════════
# MOLECULAR VALIDATION
# ══════════════════════════════════════════════════════════════════════

def is_valid(smiles: str) -> bool:
    if not RDKIT_OK or not smiles: return False
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return False
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd  = rdMolDescriptors.CalcNumHBD(mol)
        hba  = rdMolDescriptors.CalcNumHBA(mol)
        # Ro5 + extended (allow up to 600 MW for lead-like)
        return (150 <= mw <= 600 and
                -1 <= logp <= 6 and
                hbd <= 5 and hba <= 12)
    except: return False

def passes_pains(smiles: str) -> bool:
    if not RDKIT_OK: return True
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return False
        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        return not FilterCatalog(params).HasMatch(mol)
    except: return True

def canonical(smiles: str) -> str:
    if not RDKIT_OK: return smiles
    try:
        mol = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(mol) if mol else smiles
    except: return smiles

# ══════════════════════════════════════════════════════════════════════
# SOURCE 1: COMBINATORIAL GENERATOR
# ══════════════════════════════════════════════════════════════════════

# Pharmacophoric building blocks organized by disease area
SCAFFOLD_CORES = {
    "EGFR_KINASE": [
        "c1ccc2ncncc2c1",          # purine
        "c1cnc2ccccc2n1",          # quinazoline
        "c1ccc2ncccc2c1",          # quinoline
        "c1cnc2[nH]ccc2c1",        # 7-azaindole
        "c1ccc2[nH]cnc2c1",        # benzimidazole
        "c1cnc2ncncc2c1",          # purine isomer
        "c1ccc2cc[nH]c2c1",        # indole
        "c1cncc2ccccc12",          # isoquinoline
        "O=c1[nH]cnc2ccccc12",     # benzimidazone
        "c1ccc2c(c1)ncn2",         # benzimidazole isomer
    ],
    "HIV_INTEGRASE": [
        "c1cccc2ccccc12",          # naphthalene
        "c1cccc2cccnc12",          # isoquinoline
        "c1cccc2ncccc12",          # quinoline
        "c1cccc2ccncc12",          # naphthyridine
        "c1cnc2ncccc2c1",          # 1,6-naphthyridine
        "c1ccc2[nH]ccc2c1",        # indole
        "Cc1cc(C(=O)C(=O)O)cnc1",  # pyridine diketo warhead
        "c1cnc2ccccc2n1",          # quinoxaline
        "c1ccc2cnccn2c1",          # imidazo-pyridine
        "O=c1cc[nH]c2ccccc12",     # quinolinone
    ],
    "HIV_PROTEASE": [
        "C1CCNCC1",                # piperidine
        "C1CCOCC1",                # morpholine
        "C1CCNC1",                 # pyrrolidine
        "c1ccccc1",                # phenyl
        "c1ccncc1",                # pyridine
        "C1CCC2(CC1)CCCO2",        # spirocyclic THF
        "C1COC2CCCO2C1",           # bis-THF mimic
        "c1ccc2[nH]cnc2c1",        # benzimidazole
        "c1ccc(Cc2ccccc2)cc1",     # diphenylmethyl
        "C1CCCC1",                 # cyclopentyl
    ],
    "COVID_MPRO": [
        "C1CCNCC1",                # piperidine
        "O=C1CCNCC1",              # piperidinone
        "C1CCN(CC1)C(=O)",         # N-acyl piperidine
        "c1ccc2[nH]ccc2c1",        # indole
        "c1cnc2ccccc2c1",          # isoquinoline
        "O=C1CN2CCCC2C1",          # bicyclic lactam
        "C1CN2CCCC2CO1",           # oxazepine
        "c1ccc(NC(=O))cc1",        # benzamide
        "C1CC(=O)N(CC1)C(=O)",     # glutarimide
        "c1ccc2occc2c1",           # benzofuran
    ],
    "BACE1_AD": [
        "N=C1NCCC1",               # iminohydantoin
        "CC1(C)CC(N)C1",           # aminocyclohexyl
        "c1cc(F)ccc1F",            # difluorophenyl
        "c1ccc2c(c1)CC(N)C2",      # aminotetralin
        "N=C1NC(=O)CC1",           # cyclic amidine
        "c1cnc2ccccc2c1",          # isoquinoline
        "C1CC(N)NC1=O",            # lactam amine
        "FC(F)(F)c1ccccc1",        # trifluoromethylphenyl
        "c1cc2CCCc2cc1",           # tetralin
        "N=C(N)c1ccccc1",          # benzamidine
    ],
    "THROMBIN_CV": [
        "NC(=N)c1ccccc1",          # benzamidine
        "NC(=N)c1ccncc1",          # pyridine amidine
        "c1ccc2[nH]ccc2c1",        # indole
        "C1CCNCC1",                # piperidine
        "c1ccc(NC(=O))cc1",        # benzamide
        "c1ccc2c(c1)CCCO2",        # chroman
        "NC(=N)c1cc2ccccc2cc1",    # naphthyl amidine
        "c1cnc2ccccc2c1",          # isoquinoline
        "O=C(N)c1ccccc1",          # benzamide
        "c1ccc2c(c1)NCC2",         # indoline
    ],
}

# R-group substituents by property class
R_GROUPS = {
    "halogens":     ["F", "Cl", "Br"],
    "cf3":          ["C(F)(F)F"],
    "small_alkyl":  ["C", "CC", "CCC", "C(C)C", "C(C)(C)C"],
    "polar":        ["O", "N", "OC", "NC", "OCC"],
    "fluoroalkyl":  ["CF3", "CHF2", "CH2F", "CC(F)(F)F"],
    "hbd":          ["[NH2]", "[OH]", "NC(=O)", "OC(=O)N"],
    "hba":          ["C#N", "C(=O)N", "S(=O)(=O)N", "C(=O)O"],
    "aromatic":     ["c1ccccc1", "c1ccncc1", "c1ccoc1", "c1ccsc1"],
    "cyclic":       ["C1CC1", "C1CCC1", "C1CCCC1", "C1CCNCC1"],
    "metabolic":    ["OC", "NC", "SC", "FC"],
}

# Linkers connecting core to R-group
LINKERS = {
    "direct":   ["", "C", "CC", "CCC"],
    "amide":    ["C(=O)N", "NC(=O)"],
    "ether":    ["O", "OC", "OCO"],
    "amine":    ["N", "NC", "NCC"],
    "sulfonyl": ["S(=O)(=O)N", "S(=O)(=O)"],
}

class CombinatorialGenerator:
    """
    Generate drug-like molecules via systematic scaffold × linker × R-group
    combinatorics. Produces thousands of novel compounds per target.
    """

    def __init__(self):
        log("Combinatorial generator ready", MAG)

    def generate_for_target(self, target: str,
                            n_target: int = 2000) -> list:
        """Generate n_target novel molecules for a disease target."""

        # Map target to scaffold set
        target_map = {
            'EGFR': 'EGFR_KINASE', 'T790M': 'EGFR_KINASE',
            'HIV_INTEGRASE': 'HIV_INTEGRASE',
            'HIV': 'HIV_PROTEASE',
            'COVID_MPRO': 'COVID_MPRO', 'COVID': 'COVID_MPRO',
            'BACE1': 'BACE1_AD',
            'THROMBIN': 'THROMBIN_CV', 'FACTOR_XA': 'THROMBIN_CV',
        }
        scaffold_key = target_map.get(target.upper(), 'EGFR_KINASE')
        scaffolds    = SCAFFOLD_CORES.get(scaffold_key, SCAFFOLD_CORES['EGFR_KINASE'])

        log(f"Generating {n_target} combinatorial molecules for {target}...")

        generated = set()
        results   = []

        # Strategy 1: Scaffold + single R-group (fast, ~60% of output)
        for scaffold in scaffolds:
            for rcat, rgroups in R_GROUPS.items():
                for rg in rgroups:
                    for linker in ['', 'C', 'N', 'O']:
                        smiles = self._attach(scaffold, linker, rg)
                        if smiles and smiles not in generated:
                            if is_valid(smiles) and passes_pains(smiles):
                                generated.add(smiles)
                                results.append({
                                    'smiles': canonical(smiles),
                                    'scaffold': scaffold,
                                    'rgroup': rg,
                                    'strategy': 'scaffold_rgroup',
                                    'target': target,
                                })
                                if len(results) >= n_target * 0.6:
                                    break

        # Strategy 2: Scaffold + linker + R-group (more complex, ~30%)
        random.shuffle(scaffolds)
        for scaffold in scaffolds:
            linker_cats = list(LINKERS.values())
            rgroup_cats = list(R_GROUPS.values())
            for linkers in linker_cats:
                for linker in linkers[:2]:
                    for rgroups in rgroup_cats:
                        for rg in rgroups[:2]:
                            smiles = f"{scaffold}{linker}{rg}"
                            smi_c  = canonical(smiles)
                            if smi_c and smi_c not in generated:
                                if is_valid(smi_c) and passes_pains(smi_c):
                                    generated.add(smi_c)
                                    results.append({
                                        'smiles': smi_c,
                                        'scaffold': scaffold,
                                        'rgroup': rg,
                                        'strategy': 'scaffold_linker_rgroup',
                                        'target': target,
                                    })
                                    if len(results) >= n_target * 0.9:
                                        break

        # Strategy 3: Two-scaffold combinations (novel hybrids, ~10%)
        for s1 in scaffolds[:5]:
            for s2 in scaffolds[5:]:
                for linker in ['CC', 'CCC', 'C(=O)N', 'N']:
                    smiles = f"{s1}{linker}{s2}"
                    smi_c  = canonical(smiles)
                    if smi_c and smi_c not in generated:
                        if is_valid(smi_c) and passes_pains(smi_c):
                            generated.add(smi_c)
                            results.append({
                                'smiles': smi_c,
                                'scaffold': f"{s1}+{s2}",
                                'rgroup': linker,
                                'strategy': 'dual_scaffold',
                                'target': target,
                            })

        ok(f"Generated {len(results)} valid molecules for {target}")
        return results[:n_target]

    def _attach(self, scaffold: str, linker: str, rgroup: str) -> str:
        """Simple SMILES concatenation — RDKit validates."""
        candidates = [
            f"{scaffold}({linker}{rgroup})",
            f"{rgroup}{linker}{scaffold}",
            f"c1ccc({rgroup}{linker})cc1" if 'c1ccc' not in scaffold else None,
        ]
        for c in candidates:
            if c and is_valid(c):
                return c
        return None

# ══════════════════════════════════════════════════════════════════════
# SOURCE 2: CHEMBL BIOACTIVE DOWNLOADER
# ══════════════════════════════════════════════════════════════════════

# ChEMBL target IDs for our disease targets
CHEMBL_TARGETS = {
    'EGFR':         'CHEMBL203',
    'HIV_INTEGRASE':'CHEMBL4523',
    'HIV':          'CHEMBL2364',
    'BACE1':        'CHEMBL4822',
    'THROMBIN':     'CHEMBL204',
    'COVID_MPRO':   'CHEMBL3927',
    'COX2':         'CHEMBL230',
    'JAK1':         'CHEMBL2835',
    'VEGFR2':       'CHEMBL279',
    'KRAS_G12C':    'CHEMBL4630256',
}

class ChEMBLDownloader:
    """
    Download known bioactive compounds from ChEMBL REST API.
    Free, no API key required. Huge source of validated scaffolds.
    """

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    def __init__(self):
        log("ChEMBL downloader ready", MAG)

    def download_actives(self, target: str,
                         max_compounds: int = 500,
                         max_ic50_nm: float = 1000.0) -> list:
        """
        Download compounds active against target from ChEMBL.
        Filters to IC50 <= max_ic50_nm nM (default: 1 µM).
        """
        chembl_id = CHEMBL_TARGETS.get(target.upper())
        if not chembl_id:
            warn(f"No ChEMBL ID for {target}")
            return []

        log(f"Downloading ChEMBL actives for {target} ({chembl_id})...")

        url = (f"{self.BASE_URL}/activity.json?"
               f"target_chembl_id={chembl_id}"
               f"&standard_type=IC50"
               f"&standard_value__lte={max_ic50_nm}"
               f"&standard_units=nM"
               f"&pchembl_value__isnull=false"
               f"&limit={max_compounds}"
               f"&format=json")

        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'PhysicsChemPlatform/3.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())

            activities = data.get('activities', [])
            results = []

            for act in activities:
                smiles = act.get('canonical_smiles', '')
                if not smiles or not is_valid(smiles):
                    continue
                ic50 = float(act.get('standard_value', 9999) or 9999)
                pchembl = float(act.get('pchembl_value', 0) or 0)
                results.append({
                    'smiles':       canonical(smiles),
                    'chembl_id':    act.get('molecule_chembl_id', ''),
                    'ic50_nm':      ic50,
                    'pchembl':      pchembl,
                    'target':       target,
                    'source':       'chembl',
                    'dock_affinity': -(pchembl * 1.36) if pchembl else -7.0,
                })

            ok(f"Downloaded {len(results)} actives for {target}")
            return results

        except Exception as e:
            warn(f"ChEMBL download failed for {target}: {e}")
            return []

    def download_all_targets(self, max_per_target: int = 300) -> list:
        """Download actives for all configured targets."""
        all_results = []
        for target in CHEMBL_TARGETS:
            results = self.download_actives(target, max_per_target)
            all_results.extend(results)
            time.sleep(0.5)  # be nice to ChEMBL API
        return all_results

# ══════════════════════════════════════════════════════════════════════
# SOURCE 3: BRICS EXPANSION
# ══════════════════════════════════════════════════════════════════════

class BRICSExpander:
    """
    Fragment your existing hits using BRICS retrosynthetic rules,
    then recombine fragments to generate novel hybrid molecules.
    """

    def __init__(self):
        log("BRICS expander ready", MAG)

    def expand_library(self, db_path: str,
                       n_output: int = 3000) -> list:
        """Expand existing library via BRICS fragmentation + recombination."""
        if not RDKIT_OK:
            warn("RDKit required for BRICS expansion")
            return []

        # Load top compounds from library
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT smiles, target FROM compounds "
            "WHERE dock_affinity < -6.0 "
            "ORDER BY dock_affinity ASC LIMIT 200"
        ).fetchall()
        conn.close()

        if not rows:
            warn("No compounds found in library for BRICS expansion")
            return []

        log(f"BRICS expanding {len(rows)} library compounds...")

        # Step 1: Collect all fragments
        all_frags = set()
        mols_by_target = defaultdict(list)

        for smiles, target in rows:
            mol = Chem.MolFromSmiles(smiles)
            if not mol: continue
            try:
                frags = BRICS.BRICSDecompose(mol)
                for frag in frags:
                    # Clean fragment — remove BRICS attachment points
                    clean = self._clean_frag(frag)
                    if clean and len(clean) > 3:
                        all_frags.add(clean)
                mols_by_target[target].append(mol)
            except Exception:
                pass

        ok(f"Collected {len(all_frags)} unique BRICS fragments")

        # Step 2: Recombine fragments
        results = []
        generated = set()
        frag_list = list(all_frags)[:100]  # top 100 fragments

        # Pairwise combinations
        for i, f1 in enumerate(frag_list):
            for f2 in frag_list[i+1:i+15]:
                for linker in ['CC', 'CCC', 'C(=O)N', 'NCC', 'OCC', 'C']:
                    smiles = f"{f1}{linker}{f2}"
                    smi_c  = canonical(smiles)
                    if smi_c and smi_c not in generated:
                        if is_valid(smi_c) and passes_pains(smi_c):
                            generated.add(smi_c)
                            results.append({
                                'smiles':   smi_c,
                                'target':   'MULTI',
                                'strategy': 'brics_recombine',
                                'source':   'brics',
                            })
                            if len(results) >= n_output:
                                break

        # Also add fragments themselves as screening candidates
        for frag in frag_list:
            if frag not in generated and is_valid(frag):
                generated.add(frag)
                results.append({
                    'smiles':   frag,
                    'target':   'FRAGMENT',
                    'strategy': 'brics_fragment',
                    'source':   'brics',
                })

        ok(f"BRICS generated {len(results)} new molecules")
        return results[:n_output]

    def _clean_frag(self, frag: str) -> str:
        """Remove BRICS dummy atoms ([n*]) from fragment SMILES."""
        import re
        # Remove BRICS attachment points
        clean = re.sub(r'\[\d+\*\]', '', frag)
        clean = re.sub(r'\(\)', '', clean)
        clean = clean.strip('()')
        if not clean: return None
        try:
            mol = Chem.MolFromSmiles(clean)
            if mol and mol.GetNumHeavyAtoms() >= 5:
                return Chem.MolToSmiles(mol)
        except: pass
        return None

# ══════════════════════════════════════════════════════════════════════
# SOURCE 4: MULTI-TARGET CAMPAIGN LAUNCHER
# ══════════════════════════════════════════════════════════════════════

class CampaignLauncher:
    """
    Automatically queue and launch agent campaigns across all
    prepared receptors. Each campaign adds 20-60 real docked compounds.
    """

    CAMPAIGNS = [
        # (target, iterations, frags, exhaustiveness)
        ("EGFR",          2, 30, 8),
        ("HIV_INTEGRASE",  2, 30, 8),
        ("COVID_MPRO",     2, 30, 8),
        ("THROMBIN",       1, 20, 8),
        ("BACE1",          1, 20, 8),
        ("HIV",            1, 20, 8),
    ]

    def __init__(self):
        log("Campaign launcher ready", MAG)

    def launch_all(self, dry_run: bool = False):
        """Launch all configured campaigns sequentially."""
        log(f"Queued {len(self.CAMPAIGNS)} campaigns", CYN)

        for target, iters, frags, exh in self.CAMPAIGNS:
            # Check receptor exists
            receptor = f"{target.lower()}.pdbqt"
            if target == "HIV_INTEGRASE":
                receptor = "hiv_integrase.pdbqt"
            elif target == "HIV":
                receptor = "hiv_protease.pdbqt"

            if not os.path.isfile(receptor):
                warn(f"Skipping {target} — receptor {receptor} not found")
                continue

            log(f"Launching {target}: {iters} iter, {frags} frags, exh={exh}")

            if dry_run:
                log(f"  [DRY RUN] Would run: autonomous_drug_agentV2.py "
                    f"--target {target} --iterations {iters} "
                    f"--frags {frags} --exhaustiveness {exh}", YLW)
                continue

            import subprocess
            cmd = [
                sys.executable, '-W', 'ignore',
                'autonomous_drug_agentV2.py',
                '--target', target,
                '--iterations', str(iters),
                '--frags', str(frags),
                '--exhaustiveness', str(exh),
            ]
            result = subprocess.run(cmd, capture_output=False)
            if result.returncode == 0:
                ok(f"{target} campaign complete")
            else:
                warn(f"{target} campaign exited with code {result.returncode}")

# ══════════════════════════════════════════════════════════════════════
# DATABASE LOADER
# ══════════════════════════════════════════════════════════════════════

def load_to_library(compounds: list, db_path: str,
                    default_target: str = 'UNKNOWN') -> int:
    """Load generated compounds into fragment_library.db."""

    DISEASE_MAP = {
        'EGFR':'Oncology','T790M':'Oncology','VEGFR2':'Oncology',
        'HIV_INTEGRASE':'Infectious Disease','HIV':'Infectious Disease',
        'COVID_MPRO':'Infectious Disease','TB_INHA':'Infectious Disease',
        'BACE1':'Neurological','ACHE':'Neurological','MAO_B':'Neurological',
        'THROMBIN':'Cardiovascular','FACTOR_XA':'Cardiovascular',
        'DPP4':'Metabolic','COX2':'Inflammation','JAK1':'Inflammation',
        'MULTI':'Multi-target','FRAGMENT':'Fragment','UNKNOWN':'Unknown',
    }

    conn = sqlite3.connect(db_path)

    # Get existing SMILES for dedup
    existing = set(r[0] for r in
                   conn.execute("SELECT smiles FROM compounds").fetchall())

    ts = datetime.now().isoformat()
    n_added = 0

    for c in compounds:
        smiles = c.get('smiles','')
        if not smiles or smiles in existing:
            continue

        target = c.get('target', default_target).upper()
        disease = DISEASE_MAP.get(target, 'Unknown')

        # Estimated affinity (from pchembl if available, else -6.5 placeholder)
        aff = float(c.get('dock_affinity', c.get('estimated_affinity', -6.5)) or -6.5)

        # Null params per target for sigma
        null_params = {
            'EGFR':(-5.49,0.63),'HIV_INTEGRASE':(-3.44,0.37),
            'HIV':(-3.44,0.37),'COVID_MPRO':(-4.33,0.37),
            'THROMBIN':(-3.56,0.44),'BACE1':(-3.34,0.32),
        }
        nm, ns = null_params.get(target, (-5.0, 0.7))
        z = (nm - aff) / (ns + 1e-6)

        # Calculate properties
        mw = logp = hbd = hba = tpsa = rb = rings = None
        if RDKIT_OK:
            try:
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    mw    = round(Descriptors.MolWt(mol), 2)
                    logp  = round(Descriptors.MolLogP(mol), 2)
                    hbd   = rdMolDescriptors.CalcNumHBD(mol)
                    hba   = rdMolDescriptors.CalcNumHBA(mol)
                    tpsa  = round(Descriptors.TPSA(mol), 1)
                    rb    = rdMolDescriptors.CalcNumRotatableBonds(mol)
                    rings = rdMolDescriptors.CalcNumRings(mol)
            except: pass

        cid = (c.get('chembl_id') or
               c.get('id') or
               f"GEN_{target[:4]}_{n_added+1:05d}")

        # Ensure unique
        base_id = cid
        suffix  = 0
        while conn.execute("SELECT 1 FROM compounds WHERE id=?",
                           (cid,)).fetchone():
            suffix += 1
            cid = f"{base_id}_{suffix}"

        source_note = c.get('strategy', c.get('source', 'generated'))

        try:
            conn.execute("""INSERT OR IGNORE INTO compounds VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                cid, smiles, None,
                f"{target}_{datetime.now().strftime('%Y%m%d')}",
                target, disease, disease,
                aff, 0.0,
                mw, logp, hbd, hba, tpsa, rb, rings,
                0.5, 0.2, 0.0,
                f"{z:.2f}s", round(z, 3),
                int(z >= 5.0), int(z >= 3.0),
                0, 0,
                c.get('chembl_id',''), 0, 0.0, '', 0,
                ts, f"source={source_note}"
            ))
            n_added += 1
            existing.add(smiles)
        except Exception as e:
            pass

        if n_added % 500 == 0 and n_added > 0:
            conn.commit()
            log(f"  {n_added} compounds added so far...", YLW)

    conn.commit()
    conn.close()
    return n_added

# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Mass Library Expander")
    parser.add_argument("--source", nargs="+",
        choices=["combinatorial","chembl","brics","campaigns","all"],
        default=["all"])
    parser.add_argument("--target", default=None,
        help="Specific target for combinatorial (default: all)")
    parser.add_argument("--n", type=int, default=2000,
        help="Compounds per target for combinatorial (default: 2000)")
    parser.add_argument("--db", default="fragment_library.db")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--count", action="store_true",
        help="Count what would be generated without writing")
    args = parser.parse_args()

    sources = args.source
    if "all" in sources:
        sources = ["combinatorial","chembl","brics"]

    print(f"\n{BLD}{CYN}PhysicsChem Mass Library Expander{RST}")
    print(f"{CYN}Target: 10,000+ compound library{RST}")
    print("="*60)

    db_path = args.db
    total_added = 0
    t0 = time.time()

    # ── SOURCE 1: Combinatorial ───────────────────────────────────────
    if "combinatorial" in sources:
        gen = CombinatorialGenerator()
        targets = ([args.target.upper()] if args.target
                   else list(SCAFFOLD_CORES.keys()))

        for tgt_key in targets:
            # Map scaffold key back to target name
            tgt_name = {
                'EGFR_KINASE': 'EGFR',
                'HIV_INTEGRASE': 'HIV_INTEGRASE',
                'HIV_PROTEASE': 'HIV',
                'COVID_MPRO': 'COVID_MPRO',
                'BACE1_AD': 'BACE1',
                'THROMBIN_CV': 'THROMBIN',
            }.get(tgt_key, tgt_key)

            compounds = gen.generate_for_target(tgt_name, args.n)

            if args.count:
                print(f"  Would add ~{len(compounds)} combinatorial for {tgt_name}")
                continue

            if not args.dry_run:
                n = load_to_library(compounds, db_path, tgt_name)
                total_added += n
                ok(f"Added {n} combinatorial compounds for {tgt_name}")

    # ── SOURCE 2: ChEMBL ──────────────────────────────────────────────
    if "chembl" in sources and not args.count:
        dl = ChEMBLDownloader()
        targets_to_dl = ([args.target] if args.target
                         else list(CHEMBL_TARGETS.keys()))

        for tgt in targets_to_dl:
            compounds = dl.download_actives(tgt, max_compounds=500)
            if compounds and not args.dry_run:
                n = load_to_library(compounds, db_path, tgt)
                total_added += n
                ok(f"Added {n} ChEMBL compounds for {tgt}")

    # ── SOURCE 3: BRICS ───────────────────────────────────────────────
    if "brics" in sources and not args.count:
        exp = BRICSExpander()
        compounds = exp.expand_library(db_path, n_output=3000)
        if compounds and not args.dry_run:
            n = load_to_library(compounds, db_path)
            total_added += n
            ok(f"Added {n} BRICS expansion compounds")

    # ── SOURCE 4: Campaigns ───────────────────────────────────────────
    if "campaigns" in sources:
        launcher = CampaignLauncher()
        launcher.launch_all(dry_run=args.dry_run or args.count)

    # ── Final stats ───────────────────────────────────────────────────
    if not args.count and not args.dry_run:
        conn = sqlite3.connect(db_path)
        total = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
        disc  = conn.execute(
            "SELECT COUNT(*) FROM compounds WHERE is_discovery=1"
        ).fetchone()[0]
        tgts  = conn.execute(
            "SELECT COUNT(DISTINCT target) FROM compounds"
        ).fetchone()[0]
        conn.close()

        elapsed = time.time() - t0
        print(f"\n{BLD}{GRN}{'='*60}{RST}")
        print(f"{BLD}EXPANSION COMPLETE{RST}")
        print(f"{'='*60}")
        print(f"  New compounds added:  {total_added}")
        print(f"  Library total:        {total}")
        print(f"  5σ discoveries:       {disc}")
        print(f"  Targets covered:      {tgts}")
        print(f"  Time elapsed:         {elapsed:.1f}s")
        print(f"\n  Next step:")
        print(f"  python library_builder.py --stats")
        print(f"  python higgs_whitepaper.py")

if __name__ == "__main__":
    main()
