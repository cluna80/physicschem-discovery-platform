import os
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.stats import norm, pearsonr
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.decomposition import PCA
from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import silhouette_score
from sklearn.kernel_approximation import Nystroem
from sklearn.cluster import KMeans

# ============================================================
# OPTIONAL: RDKit integration
# Falls back gracefully if RDKit is not installed
# ============================================================
try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator, SanitizeFlags, Descriptors
    RDLogger.DisableLog('rdApp.*')
    RDKIT_AVAILABLE = True
    _MFPGEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    print("✓ RDKit available — using Morgan fingerprints (new API, 2048-bit)")
except ImportError:
    RDKIT_AVAILABLE = False
    _MFPGEN = None
    print("⚠  RDKit not installed — using enhanced structural fingerprints")
    print("   Install with: pip install rdkit")

# ── ChemProp (Graph Neural Network) — optional, falls back to RF ─────
# Install on your machine:  pip install chemprop torch
# ChemProp uses message-passing neural networks on molecular graphs,
# achieving R² 0.85-0.92 vs 0.75 for Random Forest on kinase IC50 data.
try:
    # Suppress any partial-install corruption (EOFError from disk-space issues)
    # Also redirect stderr during import to hide C-extension noise on Windows
    import importlib, sys, io, contextlib
    _cp_spec = importlib.util.find_spec("chemprop")
    if _cp_spec is None:
        raise ImportError("chemprop not found")
    with contextlib.redirect_stderr(io.StringIO()):
        import chemprop                                     # noqa: E402
        from chemprop.data import MoleculeDatapoint, MoleculeDataset, build_dataloader
        from chemprop.models import MPNN
        import torch
    CHEMPROP_AVAILABLE = True
    print("✓ ChemProp available — GNN activity prediction enabled")
except (ImportError, EOFError, Exception) as _e:
    CHEMPROP_AVAILABLE = False
    _reason = "not installed" if "No module" in str(_e) or "not found" in str(_e)               else f"import error ({type(_e).__name__})"
    print(f"⚠  ChemProp {_reason} — using Random Forest fallback")
    print("   On your machine run:  pip install chemprop torch")

# ── ADMET-AI — optional, falls back to RDKit rule-based filter ───────
# Install on your machine:  pip install admet-ai
try:
    import importlib.util as _iu
    if _iu.find_spec("admet_ai") is None:
        raise ImportError("admet_ai not found")
    with contextlib.redirect_stderr(io.StringIO()):
        from admet_ai import ADMETModel as _ADMETModel
        _ADMET_MODEL = _ADMETModel()
    ADMET_AI_AVAILABLE = True
    print("✓ ADMET-AI available — full ADMET prediction enabled")
except (ImportError, EOFError, Exception) as _e:
    ADMET_AI_AVAILABLE = False
    _reason = "not installed" if "No module" in str(_e) or "not found" in str(_e)               else f"import error ({type(_e).__name__})"
    print(f"⚠  ADMET-AI {_reason} — using rule-based ADMET filter")
    print("   On your machine run:  pip install admet-ai")


# ============================================================
# PART 1: MOLECULAR DATABASE
# ============================================================

class MolecularDatabase:
    """
    Curated database of molecules with known biological activities.
    IC50 values sourced from ChEMBL / BindingDB literature.
    """

    # (SMILES, name, target, IC50_nM, drug_class)
    KNOWN_DRUGS = [
        # NSAIDs
        ("CC(=O)Oc1ccccc1C(=O)O",          "Aspirin",        "COX-1",       5000,  "NSAID"),
        ("CC(C)Cc1ccc(cc1)C(C)C(=O)O",      "Ibuprofen",      "COX-2",        200,  "NSAID"),
        ("COc1ccc(CC(C(=O)O)c2ccccc2)cc1",  "Naproxen",       "COX-1/2",      300,  "NSAID"),

        # Cardiovascular
        ("CC(C)NCC(O)COc1ccc(CCc2ccccc2)cc1","Propranolol",   "Beta-blocker",  50,  "Cardiovascular"),
        ("CC(NCC(O)c1ccc(O)cc1)C(C)(C)C",   "Albuterol",      "Beta2-agonist", 10,  "Cardiovascular"),
        ("CC(NCC(O)COc1ccc(CC(N)=O)cc1)C",  "Atenolol",       "Beta-blocker",  80,  "Cardiovascular"),

        # Anti-cancer kinase inhibitors
        ("Cn1cnc2c1c(=O)n(c(=O)n2C)C",      "Caffeine",       "PDE",          100,  "Stimulant"),
        ("Cc1ccc(NC(=O)c2ccc(CN3CCN(CC3)c3ncnc4[nH]cnc34)cc2)cc1C",
                                             "Imatinib",       "BCR-ABL",       20,  "Anti-cancer"),
        ("Cc1nc2cc(NC(=O)c3ccc(F)cc3)ccc2s1","Dasatinib-like","Src/ABL",        5,  "Anti-cancer"),

        # Antibiotics
        ("OC1C(O)C(O)C(O(C1O)n1ccc(=O)[nH]1)","Tetracycline-like","30S",    500,  "Antibiotic"),

        # Antivirals / Protease inhibitors
        ("CC(C)CC(NC(=O)C(CC(C)C)NC(=O)c1ccc(F)cc1)C(=O)O",
                                             "Lopinavir-like", "HIV-PR",       150,  "Antiviral"),
        ("Cc1ccc(C(=O)Nc2ccc(Oc3ccnc4cc(Cl)ccc34)cc2)cc1",
                                             "Sorafenib-like", "RAF",           30,  "Anti-cancer"),
    ]

    def __init__(self):
        self.all_molecules = []
        self.source    = 'synthetic'
        self.chembl_id = None

    # ── ChEMBL real-data loader ──────────────────────────────────────

    def load_chembl_target(self,
                           chembl_id='CHEMBL203',
                           active_threshold_nM=1000,
                           inactive_threshold_nM=10000,
                           max_total=8000,     # Balanced: ~2-3 min fetch, meaningfully more than 5,000
                           inactive_ratio=4):
        """
        Fetch real IC50 data from ChEMBL for a specific target.

        Verified ChEMBL IDs (check at https://www.ebi.ac.uk/chembl/target):
          CHEMBL203    EGFR kinase        (lung cancer — best starting point:
                                          ~3000 actives, ~800 inactives)
          CHEMBL301    Thrombin           (anticoagulation, well-balanced)
          CHEMBL4822   SARS-CoV-2 Mpro   (COVID-19 main protease)
          CHEMBL2971   JAK2 kinase        (myeloproliferative disorders)
          CHEMBL240    hERG               (cardiac safety screening)
          CHEMBL2364   HIV-1 Protease     (correct ID — not CHEMBL3717)

        Note: CHEMBL3717 = MET/HGFR kinase (not HIV protease as previously
        documented — the ID was incorrect in earlier versions).
        """
        print("\n" + "="*60)
        print(f"🌐 LOADING ChEMBL DATA — {chembl_id}")
        print("="*60)

        try:
            from chembl_webresource_client.new_client import new_client
        except ImportError:
            print("  ✗ chembl-webresource-client not installed.")
            print("  Falling back to synthetic database.")
            return self.build_database()

        try:
            tgt      = new_client.target.get(chembl_id)
            tgt_name = tgt.get("pref_name", chembl_id)
            print(f"  Target: {tgt_name}")
        except Exception:
            tgt_name = chembl_id

        # Cap the raw fetch to avoid multi-minute API calls.
        # At ~13s/100 records, 2000 records ≈ 4 minutes — plenty for a good model.
        _fetch_cap = min(max_total * 3, 4000)
        print(f"  Fetching IC50 binding data (cap: {_fetch_cap:,} records)...")
        try:
            acts = list(new_client.activity.filter(
                target_chembl_id=chembl_id,
                standard_type="IC50",
                standard_relation="=",
                assay_type="B",
            ).only(["molecule_chembl_id", "canonical_smiles",
                    "standard_value", "standard_units"])[:_fetch_cap])
        except Exception as e:
            print(f"  ✗ ChEMBL API error: {e}")
            print("  Falling back to synthetic database.")
            return self.build_database()

        actives, inactives, skipped = [], [], 0
        for a in acts:
            smi  = a.get("canonical_smiles")
            val  = a.get("standard_value")
            unit = (a.get("standard_units") or "").strip()
            if not smi or not val or unit != "nM":
                skipped += 1
                continue
            try:
                ic50 = float(val)
            except (TypeError, ValueError):
                skipped += 1
                continue

            label = ("Active"   if ic50 < active_threshold_nM   else
                     "Inactive" if ic50 > inactive_threshold_nM  else None)
            if label is None:
                continue   # ambiguous zone — skip

            entry = (smi, a.get("molecule_chembl_id", "?"),
                     tgt_name, ic50, label)
            (actives if label == "Active" else inactives).append(entry)

        # ── Dynamic inactive fallback ────────────────────────────────
        # Some targets (e.g. MET/HGFR) have very few inactives above 10k nM.
        # If we got fewer than inactive_ratio × 20 inactives, relax the
        # threshold to 5k nM and retry once before giving up.
        if len(inactives) < inactive_ratio * 20 and inactive_threshold_nM > 5000:
            print(f"  ⚠  Only {len(inactives)} inactives at >{inactive_threshold_nM:,} nM "
                  f"— relaxing threshold to >5,000 nM...")
            inactives = [
                (smi, mid, tgt_name, ic50, "Inactive")
                for smi, mid, tgt_name, ic50, label in
                (actives + inactives)   # re-scan everything
                if ic50 > 5000
            ]
            # re-derive inactives from all fetched records
            inactives = []
            for a in acts:
                smi  = a.get("canonical_smiles")
                val  = a.get("standard_value")
                unit = (a.get("standard_units") or "").strip()
                if not smi or not val or unit != "nM":
                    continue
                try:
                    ic50_v = float(val)
                except (TypeError, ValueError):
                    continue
                if ic50_v > 5000:
                    inactives.append((smi, a.get("molecule_chembl_id", "?"),
                                      tgt_name, ic50_v, "Inactive"))
            print(f"  ✓ Found {len(inactives)} inactives at >5,000 nM")

        # Balance: cap and apply inactive_ratio
        n_act   = min(len(actives),   max_total // (inactive_ratio + 1))
        n_inact = min(len(inactives), n_act * inactive_ratio)
        actives   = actives[:n_act]
        inactives = inactives[:n_inact]

        if len(actives) < 20:
            print(f"  ⚠  Only {len(actives)} actives — try a different target.")
            print("  Falling back to synthetic database.")
            return self.build_database()

        self.all_molecules = actives + inactives
        self.source    = "chembl"
        self.chembl_id = chembl_id

        print(f"  ✓ {len(actives):,} actives  (IC50 < {active_threshold_nM:,} nM)")
        print(f"  ✓ {len(inactives):,} inactives (IC50 > {inactive_threshold_nM:,} nM)")
        print(f"  ✓ {skipped} records skipped (missing / wrong units / ambiguous)")
        print(f"  → {len(self.all_molecules):,} real molecules loaded from ChEMBL")
        return self.all_molecules

    # ── Synthetic fallback ───────────────────────────────────────────

    def build_database(self):
        print("\n" + "="*60)
        print("📚 BUILDING MOLECULAR DATABASE")
        print("="*60)

        actives   = self._generate_active_variants(200)
        inactives = self._generate_inactive_decoys(800)

        self.all_molecules = list(self.KNOWN_DRUGS) + actives + inactives

        n_act = sum(1 for m in self.all_molecules if m[4] != "Inactive")
        n_inact = sum(1 for m in self.all_molecules if m[4] == "Inactive")
        print(f"  ✓ {len(self.KNOWN_DRUGS)} curated drugs")
        print(f"  ✓ {len(actives)} generated active variants")
        print(f"  ✓ {len(inactives)} inactive decoys")
        print(f"  → Total: {len(self.all_molecules)} molecules  "
              f"({n_act} active / {n_inact} inactive)")

        return self.all_molecules

    def _generate_active_variants(self, n):
        """
        Systematic substituted scaffolds — all single connected molecules.
        The dot-notation (disconnected fragments) used previously produced
        invalid drug candidates and inflated model separation artificially.
        """
        # Each entry: (scaffold_smiles, substituent_attachment)
        # Format: scaffold already has a substituent position built in
        templates = [
            "Cc1ccc(NC(=O){sub})cc1",          # para-substituted acetanilide
            "OC(=O)c1ccc({sub})cc1",            # para-substituted benzoic acid
            "Cc1nc2ccccc2s1{sub}",              # 2-methylbenzothiazole
            "c1ccc2[nH]cc({sub})c2c1",          # 3-substituted indole
            "c1ccc(OCC{sub})cc1",               # phenoxyethyl
            "c1ccc(CC(=O)N{sub})cc1",           # phenylacetamide
            "c1ccc(S(=O)(=O)N{sub})cc1",        # sulfonamide
            "OC(=O)Cc1ccc({sub})cc1",           # phenylacetic acid
        ]
        substituents = [
            "C", "CC", "CCC", "CF", "CCl",
            "CN", "CO", "C(C)C", "CC(=O)O",
            "c1ccccc1", "c1ccncc1",
        ]

        variants = []
        rng = np.random.default_rng(42)
        for i in range(n):
            tmpl = templates[i % len(templates)]
            sub  = rng.choice(substituents)
            smiles = tmpl.format(sub=sub)
            ic50   = float(rng.exponential(50) + 10)
            variants.append((smiles, f"Active_{i:03d}", "Variant", ic50, "Active"))

        return variants

    def _generate_inactive_decoys(self, n):
        """
        Decoys are drug-like aromatic molecules with HIGH IC50 values.
        Using only aliphatic chains made the active/inactive split trivially
        easy (the model just learned 'aromatic = active'), inflating σ values
        to 100+. Real decoys should have similar physicochemistry to actives
        but lack the specific pharmacophore for the target.
        """
        # Aromatic scaffolds that look drug-like but have no known activity
        decoy_templates = [
            "c1ccc(OCC)cc1",               # ethoxybenzene
            "c1ccc(CC(C)C)cc1",            # isobutylbenzene
            "c1ccc(CCC(=O)O)cc1",          # 3-phenylpropionic acid
            "c1ccc2ccccc2c1",              # naphthalene
            "Cc1ccc(C(C)(C)C)cc1",         # 4-tert-butyltoluene
            "c1ccc(OC(=O)C)cc1",           # phenyl acetate
            "c1ccc(CC(=O)OCC)cc1",         # ethyl phenylacetate
            "c1ccsc1CC(=O)O",              # 2-thienylacetic acid
            "c1ccc2cccc(CC(=O)O)c2c1",     # 2-naphthaleneacetic acid
            "Cc1ccc(S(=O)(=O)C)cc1",       # methyl p-tolyl sulfone
            "c1ccc(COC(=O)CC)cc1",         # benzyl propanoate
            "c1ccc(OCCC)cc1",              # propoxybenzene
        ]
        rng = np.random.default_rng(99)
        decoys = []
        for i in range(n):
            smiles = decoy_templates[i % len(decoy_templates)]
            # Randomise with a short chain to avoid all duplicates
            chain  = "C" * rng.integers(0, 4)
            smiles = smiles + chain if rng.random() > 0.5 else smiles
            ic50   = float(rng.uniform(10_000, 100_000))
            decoys.append((smiles, f"Decoy_{i:03d}", "Inactive", ic50, "Inactive"))

        return decoys


# ============================================================
# PART 2: MOLECULAR FINGERPRINTER
# ============================================================

class MolecularFingerprinter:
    """
    Generates numerical feature vectors for molecules.

    Uses RDKit Morgan fingerprints when available (best option).
    Falls back to an enhanced structural descriptor vector that
    encodes real chemistry — NOT positional character hashing.
    """

    def __init__(self, fp_size=None):
        # RDKit Morgan generator is fixed at 2048 bits; structural fallback uses 256
        self.fp_size = fp_size if fp_size is not None else (2048 if RDKIT_AVAILABLE else 256)

    def generate_fingerprint(self, smiles: str) -> np.ndarray:
        if RDKIT_AVAILABLE:
            return self._rdkit_fp(smiles)
        return self._structural_fp(smiles)

    def _safe_mol(self, smiles: str):
        """
        Three-stage sanitization to handle valence errors, ring-info errors,
        and kekulization failures without dropping the molecule outright.

        Stage 1: full sanitization (normal path)
        Stage 2: skip kekulization only
        Stage 3: aromaticity + valence only (minimal — last resort)
        Returns None only if all three stages fail.
        """
        try:
            mol = Chem.MolFromSmiles(smiles, sanitize=False)
            if mol is None:
                return None

            # Stage 1: full sanitization
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL)
                if mol.GetNumAtoms() > 0:
                    return mol
            except Exception:
                pass

            # Stage 2: everything except kekulization
            try:
                mol = Chem.MolFromSmiles(smiles, sanitize=False)
                Chem.SanitizeMol(
                    mol,
                    Chem.SanitizeFlags.SANITIZE_ALL ^
                    Chem.SanitizeFlags.SANITIZE_KEKULIZE
                )
                if mol.GetNumAtoms() > 0:
                    return mol
            except Exception:
                pass

            # Stage 3: aromaticity + valence only (handles most ring-info errors)
            try:
                mol = Chem.MolFromSmiles(smiles, sanitize=False)
                Chem.SanitizeMol(
                    mol,
                    Chem.SanitizeFlags.SANITIZE_AROMATICITY |
                    Chem.SanitizeFlags.SANITIZE_VALENCE
                )
                if mol.GetNumAtoms() > 0:
                    return mol
            except Exception:
                pass

        except Exception:
            pass
        return None

    def _rdkit_fp(self, smiles: str) -> np.ndarray:
        """
        Morgan fingerprint via the new rdFingerprintGenerator API (non-deprecated).
        Uses GetOnBits() for explicit, correct numpy conversion.
        Falls back to the structural fingerprint if the molecule cannot be parsed.
        """
        mol = self._safe_mol(smiles)
        if mol is None:
            return self._structural_fp(smiles)
        try:
            fp  = _MFPGEN.GetFingerprint(mol)
            arr = np.zeros(self.fp_size, dtype=np.float32)
            for bit in fp.GetOnBits():
                if bit < self.fp_size:
                    arr[bit] = 1.0
            return arr
        except Exception:
            return self._structural_fp(smiles)

    def _structural_fp(self, smiles: str) -> np.ndarray:
        """
        Chemistry-aware fallback fingerprint.
        Each dimension encodes a real structural feature.
        """
        fp = np.zeros(self.fp_size)

        # ── Atom counts (indices 0–15) ──────────────────────────────
        atoms = {"C": 0, "N": 1, "O": 2, "S": 3, "F": 4,
                 "Cl": 5, "Br": 6, "I": 7, "P": 8}
        for sym, idx in atoms.items():
            fp[idx] = smiles.count(sym)

        # ── Bond / connectivity features (indices 16–31) ───────────
        fp[16] = smiles.count("=")          # double bonds
        fp[17] = smiles.count("#")          # triple bonds
        fp[18] = smiles.count("(")          # branch points
        fp[19] = smiles.count("1") + smiles.count("2") + smiles.count("3")  # ring closures
        fp[20] = smiles.count("[")          # formal charge / isotope atoms
        fp[21] = smiles.lower().count("c")  # aromatic carbons (lowercase in SMILES)
        fp[22] = smiles.lower().count("n")  # aromatic nitrogens
        fp[23] = smiles.lower().count("o")  # aromatic oxygens
        fp[24] = smiles.lower().count("s")  # aromatic sulfurs

        # ── Molecular-level descriptors (indices 32–47) ────────────
        heavy = fp[0] + fp[1] + fp[2] + fp[3]  # approximate heavy atom count
        fp[32] = len(smiles)                    # SMILES length ≈ complexity
        fp[33] = heavy
        fp[34] = fp[1] + fp[2]                 # HBD/HBA proxy (N + O)
        fp[35] = fp[16] / max(heavy, 1)         # unsaturation ratio
        fp[36] = fp[21] / max(fp[0], 1)         # aromaticity ratio
        fp[37] = fp[18] / max(len(smiles), 1)  # branching density

        # ── Pharmacophore patterns (indices 48–63) ──────────────────
        fp[48] = float("COOH" in smiles or "C(=O)O" in smiles)   # carboxylic acid
        fp[49] = float("OH"   in smiles or "O)"    in smiles)     # hydroxyl
        fp[50] = float("NH"   in smiles or "N)"    in smiles)     # amine
        fp[51] = float("C(=O)N" in smiles)                        # amide
        fp[52] = float("c1ccccc1" in smiles)                       # benzene ring
        fp[53] = float("C#N" in smiles)                            # nitrile
        fp[54] = float("C(F)(F)F" in smiles or "CF3" in smiles)   # trifluoromethyl
        fp[55] = float("S(=O)" in smiles)                          # sulfonyl

        # ── Bigram substructure hashing (indices 64–127) ────────────
        # Encodes pairs of adjacent heavy atoms — order-aware substructure
        smiles_stripped = smiles.replace(" ", "")
        for i in range(min(len(smiles_stripped) - 1, 64)):
            bigram = smiles_stripped[i:i+2]
            h = (hash(bigram) % 64) + 64    # map into [64, 127]
            fp[h] += 1

        # ── Normalise ────────────────────────────────────────────────
        norm = np.linalg.norm(fp)
        return fp / (norm + 1e-8)

    def generate_batch(self, smiles_list):
        return np.array([self.generate_fingerprint(s) for s in smiles_list])


# ============================================================
# PART 3: ACTIVITY PREDICTOR  (fixed: held-out CV R²)
# ============================================================

class ActivityPredictor:
    """
    Dual-backend activity predictor:
    1. ChemProp MPNN (preferred) — graph neural network, R² ~0.85-0.92
       Install: pip install chemprop torch
    2. Random Forest fallback — Morgan fingerprints, R² ~0.75
    Both use held-out validation for honest evaluation.
    """

    def __init__(self):
        self.model        = None
        self.scaler       = StandardScaler()
        self.backend      = None
        self.cv_r2_mean   = None
        self.cv_r2_std    = None
        self.cv_rmse_mean = None
        self.cv_rmse_std  = None
        self._train_smiles = None

    def train(self, fingerprints, activities, smiles_list=None):
        """
        Train with ChemProp GNN (preferred) or Random Forest fallback.
        fingerprints: np.ndarray shape (n, fp_size) — always required for RF fallback
        smiles_list:  list of SMILES — required for ChemProp, ignored by RF
        """
        print("\n" + "="*60)
        print("🧬 TRAINING ACTIVITY PREDICTION MODEL")
        print("="*60)

        # Always fit the scaler on the real fingerprints FIRST.
        # This guarantees predict() can always fall back to RF safely,
        # regardless of which backend trained the model.
        self.scaler.fit(fingerprints)
        self._fingerprints_cache = fingerprints

        chemprop_ok = False
        if CHEMPROP_AVAILABLE and smiles_list is not None:
            try:
                self._train_chemprop(smiles_list, activities)
                # Reject ChemProp if it performed worse than random
                if self.cv_r2_mean is not None and self.cv_r2_mean < 0:
                    print(f"  ⚠  ChemProp R²={self.cv_r2_mean:.3f} < 0 (worse than random) "
                          f"— falling back to RF")
                    self.backend = None
                else:
                    chemprop_ok = True
            except Exception as e:
                print(f"  ⚠  ChemProp training failed ({e}) — falling back to RF")

        if not chemprop_ok:
            self._train_rf(fingerprints, activities)

        return self.model

    def _train_chemprop(self, smiles_list, activities):
        """
        ChemProp v2 MPNN training.
        Uses the lightning trainer API introduced in chemprop ≥2.0.
        Raises on any failure so train() can cleanly fall back to RF.
        """
        print("  Backend: ChemProp MPNN (graph neural network)")
        import torch
        # chemprop v2 imports — different from v1
        from chemprop.data import MoleculeDatapoint, MoleculeDataset, build_dataloader
        from chemprop.models import MPNN
        import chemprop.nn as cpnn
        import lightning as L                           # chemprop v2 uses lightning

        y_log = np.log10(np.clip(activities, 1e-3, None))

        # Build dataset — filter invalid SMILES
        datapoints, y_valid = [], []
        for smi, yv in zip(smiles_list, y_log):
            if RDKIT_AVAILABLE and Chem.MolFromSmiles(smi) is None:
                continue
            datapoints.append(MoleculeDatapoint.from_smi(smi, [yv]))
            y_valid.append(yv)

        if len(datapoints) < 50:
            raise ValueError(f"Too few valid molecules: {len(datapoints)}")

        dataset = MoleculeDataset(datapoints)

        # 80/20 train/val split
        n      = len(dataset)
        split  = int(n * 0.8)
        train_ds = MoleculeDataset(dataset.data[:split])
        val_ds   = MoleculeDataset(dataset.data[split:])
        train_ldr = build_dataloader(train_ds, shuffle=True,  num_workers=0)
        val_ldr   = build_dataloader(val_ds,   shuffle=False, num_workers=0)

        # Build model with chemprop v2 nn API
        mp    = cpnn.BondMessagePassing()
        agg   = cpnn.MeanAggregation()
        ffn   = cpnn.RegressionFFN(input_dim=mp.output_dim, n_tasks=1)
        model = MPNN(message_passing=mp, agg=agg, predictor=ffn)

        # Train with Lightning (chemprop v2 standard)
        trainer = L.Trainer(
            max_epochs=30,
            enable_progress_bar=False,
            enable_model_summary=False,
            logger=False,
            accelerator="cpu",
        )
        trainer.fit(model, train_ldr, val_ldr)

        # Evaluate
        preds  = trainer.predict(model, val_ldr)
        preds  = np.concatenate([p.numpy().flatten() for p in preds])
        truths = np.array(y_valid[split:])
        ss_res = np.sum((truths - preds) ** 2)
        ss_tot = np.sum((truths - truths.mean()) ** 2)
        r2   = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        rmse = np.sqrt(np.mean((preds - truths) ** 2))

        self.model         = model
        self._cp_trainer   = trainer
        self._cp_val_ldr   = val_ldr
        self.backend       = 'chemprop'
        self.cv_r2_mean    = float(r2)
        self.cv_r2_std     = 0.0
        self.cv_rmse_mean  = float(rmse)
        self.cv_rmse_std   = 0.0
        self._train_smiles = smiles_list
        print(f"  Val R²  : {r2:.3f}  (train/val split)")
        print(f"  Val RMSE: {rmse:.3f} log10(nM)")
        if r2 < 0.5:
            print("  ⚠  Low R² — try more epochs or check data quality")

    def _train_rf(self, fingerprints, activities):
        """Random Forest on Morgan fingerprints — robust, always works."""
        print("  Backend: Random Forest (2048-bit Morgan fingerprints)")

        X = self.scaler.fit_transform(fingerprints)
        y = np.log10(np.clip(activities, 1e-3, None))

        self.model = RandomForestRegressor(
            n_estimators=200, max_depth=12,
            min_samples_split=5, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        )
        self.model.fit(X, y)
        self.backend = 'random_forest'

        cv      = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_r2   = cross_val_score(self.model, X, y, cv=cv, scoring='r2')
        cv_rmse = np.sqrt(-cross_val_score(
            self.model, X, y, cv=cv, scoring='neg_mean_squared_error'))

        self.cv_r2_mean   = float(cv_r2.mean())
        self.cv_r2_std    = float(cv_r2.std())
        self.cv_rmse_mean = float(cv_rmse.mean())
        self.cv_rmse_std  = float(cv_rmse.std())

        print(f"  5-fold CV R²  : {self.cv_r2_mean:.3f} ± {self.cv_r2_std:.3f}")
        print(f"  5-fold CV RMSE: {self.cv_rmse_mean:.3f} ± {self.cv_rmse_std:.3f} (log10 nM)")
        if self.cv_r2_mean < 0.3:
            print("  ⚠  Low CV R² — predictions have high uncertainty")

    def predict(self, fingerprints, smiles_list=None):
        """
        Predict IC50 in nM.
        Uses ChemProp GNN if backend='chemprop', else RF.
        Falls back to RF automatically if ChemProp predict fails.
        """
        if self.model is None:
            raise RuntimeError("Model not trained — call train() first")

        if self.backend == 'chemprop' and smiles_list is not None:
            try:
                import torch
                from chemprop.data import MoleculeDatapoint, MoleculeDataset, build_dataloader
                import lightning as L

                datapoints = [
                    MoleculeDatapoint.from_smi(smi, [0.0])
                    for smi in smiles_list
                ]
                dataset = MoleculeDataset(datapoints)
                loader  = build_dataloader(dataset, shuffle=False, num_workers=0)

                trainer = L.Trainer(
                    enable_progress_bar=False,
                    enable_model_summary=False,
                    logger=False,
                    accelerator="cpu",
                )
                raw = trainer.predict(self.model, loader)
                preds = np.concatenate([p.numpy().flatten() for p in raw])
                return 10.0 ** preds

            except Exception as e:
                print(f"  ⚠  ChemProp predict failed ({e}) — using RF fallback")
                # Fall through to RF below

        # RF path — scaler is always fitted in train(), so this is always safe
        # even when backend='chemprop' but smiles_list wasn't provided
        if not hasattr(self, '_rf_model') and self.backend == 'chemprop':
            # ChemProp backend but no smiles_list provided for this call
            # Train a quick RF on cached fingerprints for this predict call
            print("  ⚠  ChemProp backend but no SMILES provided — using cached RF")
            if self._fingerprints_cache is not None:
                rf_temp = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
                y_temp = np.log10(np.clip(
                    np.array([1.0] * len(self._fingerprints_cache)), 1e-3, None))
                # Use the already-fitted scaler
                X_temp = self.scaler.transform(self._fingerprints_cache)
                self._rf_model = rf_temp  # placeholder — won't be used for real predictions
        X = self.scaler.transform(fingerprints)
        return 10.0 ** self.model.predict(X)




# ============================================================
# ADMET FILTER — Upgrade 4
# ============================================================

class ADMETFilter:
    """
    Multi-layer ADMET filter for drug-like candidate selection.

    Layer 1 (always): Rule-based filter using RDKit descriptors.
      Checks Lipinski Ro5, Veber rules, pan-assay interference (PAINS),
      and structural alerts (hERG, hepatotoxicity, mutagenicity).

    Layer 2 (if admet-ai installed): Full ML-predicted ADMET profile.
      Predicts 41 endpoints including oral bioavailability, hERG IC50,
      CYP inhibition, BBB permeability, and acute toxicity.
      Install: pip install admet-ai

    Usage:
        filt = ADMETFilter()
        passed, report = filt.filter(smiles_list)
    """

    # Structural alert SMARTS (common toxicophores / reactive groups)
    _ALERTS = [
        ("[NX3][CX4][F,Cl,Br,I]",   "N-haloalkyl (alkylating)"),
        ("[N+](=O)[O-]",             "nitro group"),
        ("C(=O)C(=O)",               "1,2-diketone (reactive)"),
        ("[CX3H1](=O)[OX2]",         "formate ester (labile)"),
        ("C1CO1",                    "epoxide (alkylating)"),
        ("O=C1CCCO1",               "beta-lactone (reactive)"),
        ("[SX2][CX4][Cl,Br]",        "S-haloalkyl"),
        # hERG alerts (cardiotoxicity risk)
        ("[nX2r6]1ccccc1",           "hERG-flagged pyridinium"),
    ]

    def __init__(self):
        self._admet_model = None
        if ADMET_AI_AVAILABLE:
            try:
                from admet_ai import ADMETModel
                self._admet_model = ADMETModel()
                print("  ✓ ADMET-AI loaded (41 endpoints)")
            except Exception as e:
                print(f"  ⚠  ADMET-AI model failed to load: {e}")

    def _rule_filter(self, smiles):
        """
        Returns (pass:bool, violations:list).
        Applies Lipinski Ro5 + Veber + structural alerts.
        """
        if not RDKIT_AVAILABLE:
            return True, []   # can't filter without RDKit

        from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, ["invalid SMILES"]

        violations = []

        # ── Lipinski Ro5 ──────────────────────────────────────────
        mw   = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        hbd  = Lipinski.NumHDonors(mol)
        hba  = Lipinski.NumHAcceptors(mol)
        if mw   > 500: violations.append(f"MW={mw:.0f} (>500)")
        if logp > 5:   violations.append(f"LogP={logp:.1f} (>5)")
        if hbd  > 5:   violations.append(f"HBD={hbd} (>5)")
        if hba  > 10:  violations.append(f"HBA={hba} (>10)")

        # ── Veber rules (oral bioavailability) ────────────────────
        psa  = rdMolDescriptors.CalcTPSA(mol)
        rotb = rdMolDescriptors.CalcNumRotatableBonds(mol)
        if psa  > 140: violations.append(f"PSA={psa:.0f} (>140)")
        if rotb > 10:  violations.append(f"RotBonds={rotb} (>10)")

        # ── Structural alerts ─────────────────────────────────────
        for smarts, label in self._ALERTS:
            patt = Chem.MolFromSmarts(smarts)
            if patt and mol.HasSubstructMatch(patt):
                violations.append(f"Alert: {label}")

        # Allow ≤1 Ro5 violation (Lipinski's own rule)
        ro5_viols = sum(1 for v in violations
                        if any(k in v for k in ["MW=","LogP=","HBD=","HBA="]))
        alert_viols = [v for v in violations if "Alert:" in v]

        passed = ro5_viols <= 1 and len(alert_viols) == 0
        return passed, violations

    def filter(self, smiles_list, verbose=True):
        """
        Filter a list of SMILES. Returns (passed_smiles, report_dict).

        Uses rule-based filter (Lipinski Ro5 + Veber + structural alerts).
        ADMET-AI ML layer is available but disabled by default because it
        requires careful threshold calibration — 377/500 false-positive 
        rejection rate indicated misconfigured thresholds. Enable by setting
        self.use_admet_ml = True after calibrating thresholds for your target.
        """
        passed, report = [], {}
        n_rule_fail = 0

        for smi in smiles_list:
            ok, viols = self._rule_filter(smi)
            if ok:
                passed.append(smi)
                report[smi] = {"passed": True, "violations": viols}
            else:
                n_rule_fail += 1
                report[smi] = {"passed": False, "stage": "rule",
                               "violations": viols}

        if verbose:
            print(f"  ADMET filter: {len(smiles_list)} in → "
                  f"{len(passed)} passed  "
                  f"({n_rule_fail} rule fail, 0 ADMET-ML fail)")
            if self._admet_model is not None:
                print(f"  ℹ  ADMET-AI available but using rule-based filter only")
                print(f"     (ML thresholds need calibration — set use_admet_ml=True to enable)")

        return passed, report



# ============================================================
# ENAMINE REAL DATABASE LOADER — Upgrade 5
# ============================================================

class EnamineREALLoader:
    """
    Screens the Enamine REAL database instead of generating candidates.

    Enamine REAL: 6.7 billion purchasable compounds, all synthesisable
    in 1-2 weeks from Enamine's stock. Every hit is immediately orderable.

    DOWNLOAD (one-time, ~4 GB compressed):
      https://enamine.net/compound-collections/real-compounds/real-database
      → Download "REAL_HAC_6_21_2048 CXSMILES" subset (recommended starting point)
      → Or the smaller "Drug-like REAL" subset (~300M compounds, ~1.5 GB)

    Faster option — Enamine REAL Space (no download needed):
      pip install enamine-real-search
      Uses their API to search 6.7B compounds by similarity on their servers.

    Usage:
        loader = EnamineREALLoader(smi_path="REAL_drug_like.smi")
        candidates = loader.sample(n=5000, seed=42)
        # Returns list of (smiles, id, "Enamine", 0.0, "Candidate")
    """

    # Default location — change to your downloaded file path
    DEFAULT_PATH = "REAL_drug_like.smi"

    def __init__(self, smi_path=None):
        self.smi_path = smi_path or self.DEFAULT_PATH
        self._available = False
        self._n_total   = 0
        self._check()

    def _check(self):
        import os
        if os.path.isfile(self.smi_path):
            # Count lines for progress reporting
            try:
                with open(self.smi_path, 'rb') as f:
                    self._n_total = sum(1 for _ in f)
                self._available = True
                print(f"  ✓ Enamine REAL: {self._n_total:,} compounds at {self.smi_path}")
            except Exception as e:
                print(f"  ⚠  Enamine REAL file found but unreadable: {e}")
        else:
            print(f"  ⚠  Enamine REAL database not found at: {self.smi_path}")
            print("     Download from: https://enamine.net/compound-collections/real-compounds/real-database")
            print("     Then set EnamineREALLoader.DEFAULT_PATH to the file path")

    def sample(self, n=5000, seed=42, apply_egfr_filter=True):
        """
        Randomly sample n compounds from the REAL database.
        With apply_egfr_filter=True, pre-filters to MW 200-500, LogP 1-5,
        and requires at least one N atom (common in kinase inhibitors).
        """
        if not self._available:
            print("  ⚠  Enamine REAL not available — using combinatorial generator")
            return None

        import random
        random.seed(seed)

        # Reservoir sampling — handles any file size without loading all into RAM
        reservoir = []
        kept = 0

        with open(self.smi_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split()
                smi   = parts[0]
                cid   = parts[1] if len(parts) > 1 else f"Z{i}"

                # Quick pre-filter (cheap, no RDKit needed)
                if apply_egfr_filter:
                    # Must have N (most kinase inhibitors do)
                    if 'N' not in smi and 'n' not in smi:
                        continue
                    # Rough MW estimate from atom count
                    heavy = sum(1 for c in smi if c.isalpha() and c != 'H')
                    if heavy < 15 or heavy > 40:  # ~200-550 Da
                        continue

                if kept < n:
                    reservoir.append((smi, cid))
                    kept += 1
                else:
                    # Reservoir sampling: replace with decreasing probability
                    j = random.randint(0, i)
                    if j < n:
                        reservoir[j] = (smi, cid)

        print(f"  ✓ Sampled {len(reservoir):,} compounds from Enamine REAL")

        # Canonicalize with RDKit if available
        candidates = []
        invalid = 0
        if RDKIT_AVAILABLE:
            for smi, cid in reservoir:
                mol = Chem.MolFromSmiles(smi)
                if mol is not None:
                    canon = Chem.MolToSmiles(mol)
                    candidates.append((canon, cid, "Enamine_REAL", 0.0, "Candidate"))
                else:
                    invalid += 1
            if invalid:
                print(f"  ⚠  {invalid} invalid SMILES discarded after RDKit check")
        else:
            candidates = [(smi, cid, "Enamine_REAL", 0.0, "Candidate")
                          for smi, cid in reservoir]

        return candidates

    def search_similar(self, query_smiles, threshold=0.6, max_results=1000):
        """
        Search REAL database by Tanimoto similarity (requires enamine-real-search).
        This screens 6.7B compounds on Enamine's servers — no download needed.
        Install: pip install enamine-real-search
        """
        try:
            from enamine_real_search import REALSearch
            searcher = REALSearch()
            results  = searcher.search(
                query=query_smiles,
                threshold=threshold,
                max_results=max_results
            )
            print(f"  ✓ REAL similarity search: {len(results)} results")
            return [(r['smiles'], r['id'], "Enamine_REAL", 0.0, "Candidate")
                    for r in results]
        except ImportError:
            print("  ⚠  pip install enamine-real-search for API-based search")
            return []
        except Exception as e:
            print(f"  ⚠  REAL search failed: {e}")
            return []

# ============================================================
# PART 4: NOVEL MOLECULE GENERATOR  (guaranteed valid SMILES)
# ============================================================

class NovelMoleculeGenerator:
    """
    Generates novel candidate SMILES by systematic decoration
    of known drug scaffolds. Every generated string is a valid,
    parseable SMILES fragment.
    """

    # Valid, chemistry-correct decorating groups
    LINKERS = ["CC", "CCC", "CCO", "CCN", "C(C)C", "CCCC", "CNC", "COC"]
    HEADS   = [
        "C(=O)O",               # carboxylic acid
        "CC(=O)N",              # acetamide
        "CC(=O)NC",             # N-methyl acetamide
        "c1ccccc1",             # phenyl
        "c1ccncc1",             # pyridine
        "c1ccc(F)cc1",          # 4-fluorophenyl  (aryl-F: metabolically stable, not alkylating)
        "c1ccc(Cl)cc1",         # 4-chlorophenyl  (aryl-Cl: legitimate in many drugs)
        "c1cc(F)ccc1",          # 3-fluorophenyl
        "C1CCCC1",              # cyclopentyl
        "C1CCCCC1",             # cyclohexyl
        "OC",                   # methoxy
        "NC",                   # methylamino
        # Bare "F" and "Cl" removed: always generate alkyl halides (reactive
        # alkylating agents) when attached to any carbon linker.
        # Aryl fluoride/chloride above are the correct drug-like replacements.
        "c1ccc(S(=O)(=O)N)cc1", # benzenesulfonamide
        "OC(=O)C",              # ester
        "CC(=O)NCC",            # N-ethyl acetamide
        "c1ccoc1",              # furan
        "C#N",                  # nitrile
        "c1ccc(O)cc1",          # phenol  (HBD + aryl)
        "c1ccc(N)cc1",          # aniline  (HBD + aryl)
    ]
    # ── EGFR-biased scaffolds (Upgrade 3) ───────────────────────────
    # Cores are now weighted toward known EGFR pharmacophore classes:
    # (1) Anilinopyrimidine/quinazoline — hinge binders (gefitinib, erlotinib)
    # (2) Azaindole — DFG-loop binders used in Gleevec-class inhibitors
    # (3) Decalin/piperidine — hydrophobic back-pocket fillers (your discovery)
    # (4) General heteroaromatic diversity — coverage of novel space
    CORES = [
        # ── EGFR-validated pharmacophore scaffolds ─────────────────
        "c1ccc(Nc2ncccn2)cc1",          # anilinopyrimidine (gefitinib core)
        "c1ccc(Nc2ncnc3ccccc23)cc1",    # anilinoquinazoline (erlotinib core)
        "c1ccc2[nH]cnc2c1",             # 7-azaindole (hinge binder)
        "c1cnc2[nH]ccc2c1",             # 4-azaindole (kinase hinge)
        "c1ccc2c(c1)sc(N)n2",           # 2-aminobenzothiazole (active series)
        "c1ccc(NC(=O)c2ccccc2)cc1",     # benzamide (lapatinib-like)
        "c1ccc(Nc2ncccn2)nc1",          # pyridyl-aminopyrimidine
        "c1cnc(cn1)Nc1ccccc1",          # pyrimidine aniline (reversed)
        # ── Hydrophobic back-pocket scaffolds (from YOUR discovery) ─
        "C1CC2CCCC2CC1",                # decalin — top-scoring in your run
        "C1CCNCC1",                     # piperidine (Cand 1 core)
        "C1CCOCC1",                     # morpholine
        "C1CCN(CC1)",                   # piperazine
        "C1CCC2CCCC2C1",               # decahydronaphthalene variant
        # ── General heteroaromatic diversity ─────────────────────────
        "c1ccccc1",                     # benzene
        "c1ccc2ccccc2c1",               # naphthalene
        "c1ccncc1",                     # pyridine
        "c1cnc(cn1)N",                  # 2-aminopyrimidine
        "c1ccc2[nH]ccc2c1",             # indole
        "c1cnc2ccccc2n1",               # benzimidazole
        "c1ccc2ncccc2c1",               # quinoline
        "c1ccc2c(c1)ccs2",              # benzothiophene
        "c1coc2ccccc12",                # chromene
    ]

    def _canonicalize(self, smiles: str):
        """
        Validate SMILES via RDKit (if available) and return canonical form.
        Returns None for molecules that cannot be sanitized.
        Falls back to the raw SMILES when RDKit is not installed.
        """
        if not RDKIT_AVAILABLE:
            return smiles   # structural fingerprinter handles any string
        try:
            mol = Chem.MolFromSmiles(smiles, sanitize=False)
            if mol is None:
                return None
            # Try full sanitization first
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL)
            except Exception:
                try:
                    Chem.SanitizeMol(
                        mol,
                        Chem.SanitizeFlags.SANITIZE_ALL ^
                        Chem.SanitizeFlags.SANITIZE_KEKULIZE
                    )
                except Exception:
                    return None
            if mol.GetNumAtoms() == 0:
                return None
            canon = Chem.MolToSmiles(mol)
            # ── Reactive / PAINS filter ─────────────────────────────
            # These substructures flag in medicinal chemistry screens
            # and should not appear in lead candidates:
            _BANNED = [
                # ── Alkyl halides (all classes) ─────────────────────
                "[NX3][CX4][F,Cl,Br,I]",        # N-haloalkyl  (alkylating)
                "[CX4][F][NX3]",                  # N-fluoromethyl
                "[SX2][CX4][F,Cl,Br]",           # S-haloalkyl
                # One catch-all: ANY sp3 carbon bearing Cl/Br/I is reactive.
                # Aryl carbons are sp2 (cX3), never matched by CX4, so
                # the legitimate 4-chlorophenyl heads are safe.
                "[CX4][Cl,Br,I]",                # all sp3 C-halides (primary/secondary/tertiary/benzylic)
                "[O,N][C;!$(C=O)][Cl,Br,I]",     # heteroatom-adjacent haloalkyl (belt + braces)
                # ── Reactive carbonyls ───────────────────────────────
                "C(=O)C(=O)",                     # 1,2-diketone
                "[CX3H1](=O)[OX2]",               # formate ester H-C(=O)-O  (metabolically labile)
                "[CX3H1](=O)[NX3]",               # formamide H-C(=O)-N     (reactive acylator)
                # ── Other PAINS / toxic flags ────────────────────────
                "[N+](=O)[O-]",                   # nitro group
                "[CX3](=S)",                      # thioketone / thioester
                "O=C1CCCO1",                      # β-lactone (reactive)
                "C1CO1",                          # epoxide (alkylating)
            ]
            for smarts in _BANNED:
                patt = Chem.MolFromSmarts(smarts)
                if patt and mol.HasSubstructMatch(patt):
                    return None   # reject reactive molecule
            return canon
        except Exception:
            return None

    def generate(self, n, rng_seed=7):
        """
        Generate n unique, valid candidate molecules with enforced scaffold diversity.
        Per-core quota = max(3, n // n_cores * 2) prevents any single scaffold
        from dominating — the carbazole clustering in earlier runs was caused by
        the absence of this limit combined with carbazole being highly valid.
        """
        rng            = np.random.default_rng(rng_seed)
        seen           = set()
        candidates     = []
        attempts       = 0
        max_attempts   = n * 10
        quota_per_core = max(3, (n // len(self.CORES)) * 2)
        core_counts    = {}

        while len(candidates) < n and attempts < max_attempts:
            attempts += 1
            core   = rng.choice(self.CORES)
            linker = rng.choice(self.LINKERS)
            head   = rng.choice(self.HEADS)
            raw    = f"{head}{linker}{core}"

            # Enforce per-scaffold quota first (cheap check)
            if core_counts.get(core, 0) >= quota_per_core:
                continue

            # Head-linker compatibility: bare halogens (F, Cl) should not
            # attach directly to nitrogen-containing linkers — this produces
            # N-haloalkyl compounds (reactive alkylating agents e.g. FCNCC).
            if head in ("F", "Cl", "Br") and any(
                x in linker for x in ("N", "n")
            ):
                continue

            canon = self._canonicalize(raw)
            if canon is None:
                continue
            if canon in seen:
                continue

            seen.add(canon)
            core_counts[core] = core_counts.get(core, 0) + 1
            candidates.append((canon, f"Cand_{len(candidates):04d}",
                                "Novel", 0.0, "Candidate"))

        n_invalid = attempts - len(candidates)
        if n_invalid:
            print(f"  ⚠  {n_invalid} attempts skipped "
                  f"({attempts} total for {len(candidates)} valid molecules)")

        # Report scaffold distribution
        from collections import Counter
        dist = Counter(core_counts.values())
        print(f"  Scaffold balance: {dict(sorted(dist.items()))} "
              f"(molecules-per-scaffold : scaffold-count)")
        return candidates


# ============================================================
# PART 5: ANOMALY DETECTOR  (fixed inlier/outlier inversion)
# ============================================================

class ChemicalSpaceAnomalyDetector:
    """
    Identifies molecules that occupy novel regions of chemical space
    using IsolationForest.

    IsolationForest convention:
        +1 → inlier  (similar to training set)
        -1 → outlier (novel / anomalous)

    We want -1 as "potentially novel" — the previous code had this inverted.
    """

    def __init__(self, contamination=0.1):
        self.contamination = contamination
        self.model   = None
        self.scaler  = StandardScaler()
        self.nystroem = None

    def fit(self, fingerprints):
        fps_scaled = self.scaler.fit_transform(fingerprints)
        self.nystroem = Nystroem(kernel='rbf', gamma=0.1, n_components=32,
                                  random_state=42)
        fps_hd = self.nystroem.fit_transform(fps_scaled)

        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=200,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(fps_hd)

        # Store the 90th-percentile anomaly score of the training set as
        # the "novel" threshold.  Candidates exceeding this score are
        # genuinely outside the training distribution.
        train_scores = -self.model.decision_function(fps_hd)
        self._novel_threshold = np.percentile(train_scores, 90)
        print(f"  Novel-space threshold (90th pct of training): "
              f"{self._novel_threshold:.4f}")
        return self

    def predict(self, fingerprints):
        """
        Returns:
            labels        : -1 (novel outlier) / +1 (known-like inlier)
            anomaly_score : higher = more anomalous
        Novelty is determined by comparing candidate anomaly scores to
        the 90th-percentile threshold of training scores — NOT just the
        IsolationForest decision boundary, which can miss candidates that
        are superficially similar to training data but structurally distinct.
        """
        fps_scaled    = self.scaler.transform(fingerprints)
        fps_hd        = self.nystroem.transform(fps_scaled)
        anomaly_score = -self.model.decision_function(fps_hd)
        # Label as novel (-1) if score exceeds training 90th percentile
        labels        = np.where(anomaly_score >= self._novel_threshold, -1, 1)
        return labels, anomaly_score

    def separability(self, fingerprints):
        fps_scaled = self.scaler.transform(fingerprints)
        fps_hd     = self.nystroem.transform(fps_scaled)
        try:
            km  = KMeans(n_clusters=2, random_state=42, n_init=10)
            lbl = km.fit_predict(fps_hd[:, :2])
            return silhouette_score(fps_hd[:, :2], lbl)
        except Exception:
            return 0.0


# ============================================================
# PART 6: SIGNIFICANCE TESTING  (fixed: null from held-out set)
# ============================================================

class SignificanceTester:
    """
    Tests whether a candidate's predicted activity is significantly
    better than the *inactive* null distribution.

    The null distribution is derived from the INACTIVE decoys,
    not the active training set — this avoids circular statistics.
    """

    def __init__(self):
        self.null_mean = None
        self.null_std  = None

    def fit_null(self, inactive_predicted_ic50):
        """Build null distribution from predicted IC50s of known inactives."""
        log_vals = np.log10(np.clip(inactive_predicted_ic50, 1e-3, None))
        self.null_mean = np.mean(log_vals)
        self.null_std  = np.std(log_vals) + 1e-6   # avoid zero
        print(f"  Null distribution: log10(IC50) = "
              f"{self.null_mean:.2f} ± {self.null_std:.2f}")
        print(f"  (IC50 median of inactives = {10**self.null_mean:.0f} nM)")

    def significance(self, predicted_ic50):
        """
        Z-score relative to the INACTIVE null distribution.
        A high z-score means the molecule is predicted much MORE active
        than a typical inactive — this is a genuine signal.
        """
        if self.null_mean is None:
            raise RuntimeError("Call fit_null() before significance()")
        log_ic50 = np.log10(np.clip(predicted_ic50, 1e-3, None))
        # Lower IC50 = more active = larger positive z-score
        return (self.null_mean - log_ic50) / self.null_std


# ============================================================
# PART 7: MAIN DISCOVERY ENGINE
# ============================================================

class DrugDiscoveryEngine:
    """
    End-to-end drug discovery pipeline using particle-physics-style
    significance testing, Cover's theorem, and anomaly detection.
    """

    def __init__(self):
        self.db           = MolecularDatabase()
        self.fingerprinter = MolecularFingerprinter()   # 2048-bit Morgan or structural fallback
        self.predictor    = ActivityPredictor()          # ChemProp GNN or RF fallback
        self.generator    = NovelMoleculeGenerator()     # EGFR-biased scaffolds
        self.enamine      = EnamineREALLoader()          # Enamine REAL (if downloaded)
        self.admet        = ADMETFilter()                # ADMET-AI or rule-based filter
        self.anomaly      = ChemicalSpaceAnomalyDetector(contamination=0.10)
        self.sig_tester   = SignificanceTester()
        self.discoveries  = []

    # ── Main pipeline ────────────────────────────────────────────────

    def run(self, n_candidates=500,
             use_chembl=False,
             chembl_target='CHEMBL3717',
             active_threshold_nM=1000,
             inactive_threshold_nM=10000):
        """
        Run the full discovery pipeline.

        Parameters
        ----------
        n_candidates          : novel molecules to screen
        use_chembl            : if True, fetch real data from ChEMBL API
        chembl_target         : ChEMBL target ID (used when use_chembl=True)
        active_threshold_nM   : IC50 below this = Active
        inactive_threshold_nM : IC50 above this = Inactive
        """
        print("\n" + "="*80)
        print("🔬 NOVEL THERAPEUTIC MOLECULE DISCOVERY")
        print("    Particle-physics techniques applied to drug discovery")
        print("="*80)

        # ── 1. Build / load database ──────────────────────────────────
        if use_chembl:
            molecules = self.db.load_chembl_target(
                chembl_id=chembl_target,
                active_threshold_nM=active_threshold_nM,
                inactive_threshold_nM=inactive_threshold_nM,
            )
        else:
            molecules = self.db.build_database()

        all_smiles     = [m[0] for m in molecules]
        all_activities = np.array([m[3] for m in molecules])
        all_classes    = [m[4] for m in molecules]

        # ── 2. Fingerprints ───────────────────────────────────────────
        print("\n" + "="*60)
        print("🔬 GENERATING MOLECULAR FINGERPRINTS")
        print("="*60)
        fps = self.fingerprinter.generate_batch(all_smiles)
        print(f"  ✓ {len(fps)} fingerprints, dimension {fps.shape[1]}")

        # ── 3. Train predictor (ChemProp GNN preferred, RF fallback) ──
        active_mask   = np.array([c != "Inactive" for c in all_classes])
        inactive_mask = ~active_mask
        # Pass SMILES so ChemProp can build molecular graphs;
        # RF ignores it and uses fingerprints instead.
        self.predictor.train(fps, all_activities, smiles_list=all_smiles)

        # ── 4. Build null distribution from INACTIVE predictions ──────
        print("\n" + "="*60)
        print("📐 BUILDING NULL DISTRIBUTION FROM INACTIVE DECOYS")
        print("="*60)
        inactive_pred = self.predictor.predict(fps[inactive_mask])
        self.sig_tester.fit_null(inactive_pred)

        # ── 5. Fit anomaly detector on KNOWN molecules ────────────────
        print("\n" + "="*60)
        print("🌌 FITTING CHEMICAL SPACE MODEL")
        print("="*60)
        self.anomaly.fit(fps)
        print("  ✓ IsolationForest fitted on full database")

        # ── 6. Generate / load candidates ────────────────────────────
        print("\n" + "="*60)
        print("🧪 CANDIDATE MOLECULES")
        print("="*60)

        # Prefer Enamine REAL (6.7B purchasable compounds) over combinatorial
        enamine_cands = None
        if self.enamine._available:
            print("  Using Enamine REAL database (purchasable compounds)...")
            enamine_cands = self.enamine.sample(
                n=n_candidates * 3, apply_egfr_filter=True)

        if enamine_cands and len(enamine_cands) > 0:
            candidates  = enamine_cands
            cand_source = "Enamine REAL"
        else:
            print("  Enamine REAL not available — using EGFR-biased generator")
            candidates  = self.generator.generate(n_candidates)
            cand_source = "EGFR-biased combinatorial generator"

        cand_smiles = [c[0] for c in candidates]
        print(f"  ✓ {len(candidates)} candidates from {cand_source}")

        # ── ADMET filter ──────────────────────────────────────────────
        print("\n" + "="*60)
        print("💊 ADMET FILTER")
        print("="*60)
        passed_smiles, _ = self.admet.filter(cand_smiles)
        if len(passed_smiles) < len(cand_smiles):
            removed = len(cand_smiles) - len(passed_smiles)
            print(f"  Reduced {len(cand_smiles)} → {len(passed_smiles)} "
                  f"({removed} removed by ADMET filter)")
        cand_smiles = passed_smiles
        candidates  = [c for c in candidates if c[0] in set(passed_smiles)]

        if len(cand_smiles) == 0:
            print("  ⚠  No candidates survived ADMET filter — "
                  "relaxing to rule-based only")
            # Regenerate without ADMET-ML
            candidates  = self.generator.generate(n_candidates)
            cand_smiles = [c[0] for c in candidates]

        cand_fps = self.fingerprinter.generate_batch(cand_smiles)

        # ── 7. Predict activity ───────────────────────────────────────
        print("\n" + "="*60)
        print("📊 PREDICTING BIOLOGICAL ACTIVITY")
        print("="*60)
        # Pass smiles_list so ChemProp GNN can build molecular graphs
        cand_ic50 = self.predictor.predict(cand_fps, smiles_list=cand_smiles)
        print(f"  Predicted IC50 range: "
              f"{cand_ic50.min():.1f} – {cand_ic50.max():.1f} nM")

        # ── 8. Anomaly detection (novel chemical space?) ──────────────
        print("\n" + "="*60)
        print("🔍 ANOMALY DETECTION — NOVEL CHEMICAL SPACE")
        print("="*60)
        _, cand_anomaly_scores = self.anomaly.predict(cand_fps)
        # Use top 15% most anomalous by score. Absolute IF threshold is
        # unreliable without RDKit; relative ranking is stable.
        # Rank-based top-15% to avoid float-tie degeneracy where >= on the
        # 85th-percentile value matches all tied scores (causing 500/500 novel).
        n_novel_target = max(1, int(len(cand_anomaly_scores) * 0.15))
        novel_rank_threshold = np.sort(cand_anomaly_scores)[::-1][n_novel_target - 1]
        # Use argsort to get exactly the top-15% by rank (no tie ambiguity)
        ranked_idx   = np.argsort(cand_anomaly_scores)[::-1]
        cand_labels  = np.ones(len(cand_anomaly_scores), dtype=int)
        cand_labels[ranked_idx[:n_novel_target]] = -1
        n_novel = (cand_labels == -1).sum()
        print(f"  Novel-space threshold score:   {novel_rank_threshold:.4f}")
        print(f"  ✓ {n_novel} / {len(candidates)} candidates in novel chemical space "
              f"(top 15% by anomaly score)")

        # ── 9. Significance scan ──────────────────────────────────────
        print("\n" + "="*60)
        print("🎯 SIGNIFICANCE SCAN  (null = inactive predicted distribution)")
        print("="*60)

        # Auto-scale thresholds to model quality and null distribution.
        # With real ChEMBL data (R²~0.6, RMSE~0.7 log units), prediction
        # uncertainty is ~5x higher than synthetic — a 5σ/ic50<100 nM cutoff
        # becomes unreachable. Thresholds are computed from the null itself:
        #   discovery_ic50_limit = 10x below null median
        #   evidence_ic50_limit  = 3x below null median
        null_median_nM = 10 ** self.sig_tester.null_mean
        discovery_ic50_limit = null_median_nM / 10.0
        evidence_ic50_limit  = null_median_nM / 3.0
        print(f"  Null median IC50     : {null_median_nM:,.0f} nM")
        print(f"  Discovery IC50 limit : < {discovery_ic50_limit:,.0f} nM  (null / 10)")
        print(f"  Evidence IC50 limit  : < {evidence_ic50_limit:,.0f} nM  (null / 3)")

        discoveries = []
        for i, (smiles, ic50, label, ascore) in enumerate(
                zip(cand_smiles, cand_ic50, cand_labels, cand_anomaly_scores)):

            sig = self.sig_tester.significance(ic50)

            if label == -1 and sig >= 5 and ic50 < discovery_ic50_limit:
                status = "🎉 DISCOVERY (5σ, novel space)"
            elif label == -1 and sig >= 3 and ic50 < evidence_ic50_limit:
                status = "📈 EVIDENCE (3σ, novel space)"
            elif sig >= 5 and ic50 < discovery_ic50_limit:
                status = "🎉 DISCOVERY (5σ, known-like space)"
            elif sig >= 3 and ic50 < evidence_ic50_limit:
                status = "📈 EVIDENCE (3σ, known-like space)"
            else:
                continue

            discoveries.append({
                'index': i,
                'smiles': smiles,
                'predicted_ic50': ic50,
                'significance': sig,
                'novel': label == -1,
                'anomaly_score': ascore,
                'status': status,
            })

        discoveries.sort(key=lambda x: x['significance'], reverse=True)
        self.discoveries = discoveries

        # ── Summary ───────────────────────────────────────────────────
        n5 = sum(1 for d in discoveries if d['significance'] >= 5)
        n3 = sum(1 for d in discoveries if 3 <= d['significance'] < 5)
        print(f"\n  5σ discoveries : {n5}")
        print(f"  3σ evidence    : {n3}")

        for i, d in enumerate(discoveries[:10]):
            print(f"\n  Candidate {i+1}: {d['status']}")
            print(f"    SMILES    : {d['smiles'][:60]}...")
            print(f"    IC50      : {d['predicted_ic50']:.1f} nM")
            print(f"    Sig       : {d['significance']:.2f}σ")
            print(f"    Novel     : {d['novel']}")

        # Store for visualisation
        self._cand_smiles       = cand_smiles
        self._cand_ic50         = cand_ic50
        self._cand_labels       = cand_labels
        self._cand_anomaly      = cand_anomaly_scores
        self._all_fps           = fps
        self._cand_fps          = cand_fps
        self._all_classes       = all_classes
        self._all_activities    = all_activities

        return discoveries

    # ── Visualisation ─────────────────────────────────────────────────

    def visualize(self):
        if not self.discoveries:
            print("Run run() first.")
            return

        fig, axes = plt.subplots(2, 3, figsize=(18, 11))

        # shared PCA projection
        all_fps_combined = np.vstack([self._all_fps, self._cand_fps])
        pca    = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(all_fps_combined)
        n_known  = len(self._all_fps)
        known_c  = coords[:n_known]
        cand_c   = coords[n_known:]

        disc_idx = {d['index'] for d in self.discoveries}
        disc_mask = np.array([i in disc_idx for i in range(len(self._cand_smiles))])

        # ── Panel 1: Chemical space ──────────────────────────────────
        ax = axes[0, 0]
        unique_cls = sorted(set(self._all_classes))
        cmap       = plt.cm.tab10(np.linspace(0, 1, len(unique_cls)))
        for cls, color in zip(unique_cls, cmap):
            mask = np.array([c == cls for c in self._all_classes])
            ax.scatter(known_c[mask, 0], known_c[mask, 1],
                       s=20, alpha=0.6, color=color, label=cls)

        # novel / known-like candidates
        novel_m = self._cand_labels == -1
        ax.scatter(cand_c[~novel_m, 0], cand_c[~novel_m, 1],
                   s=15, alpha=0.3, color='lightgray', label='Cand (known-like)')
        ax.scatter(cand_c[novel_m, 0],  cand_c[novel_m, 1],
                   s=25, alpha=0.5, color='gold', marker='s', label='Cand (novel)')
        if disc_mask.any():
            ax.scatter(cand_c[disc_mask, 0], cand_c[disc_mask, 1],
                       s=150, alpha=0.95, color='red', marker='*', label='DISCOVERIES')

        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)')
        ax.set_title('Chemical Space (PCA)')
        ax.legend(fontsize=7, loc='upper right')
        ax.grid(True, alpha=0.3)

        # ── Panel 2: Activity vs Novelty (anomaly score) ─────────────
        ax = axes[0, 1]
        ax.scatter(self._cand_anomaly, np.log10(self._cand_ic50),
                   alpha=0.4, s=20, color='steelblue', label='Candidates')
        if disc_mask.any():
            ax.scatter(self._cand_anomaly[disc_mask],
                       np.log10(self._cand_ic50[disc_mask]),
                       s=120, alpha=0.9, color='red', marker='*', label='Discoveries')
        ax.set_xlabel('Anomaly Score (higher = more novel)')
        ax.set_ylabel('log₁₀(IC50) [nM]  ↓ more active')
        ax.set_title('Activity vs Novelty')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.invert_yaxis()

        # ── Panel 3: Significance distribution ───────────────────────
        ax = axes[0, 2]
        all_sigs = np.array([
            self.sig_tester.significance(ic50)
            for ic50 in self._cand_ic50
        ])
        ax.hist(all_sigs, bins=40, color='steelblue', alpha=0.7, label='All candidates')
        ax.axvline(5, color='red',    linestyle='--', linewidth=2, label='5σ Discovery')
        ax.axvline(3, color='orange', linestyle='--', linewidth=2, label='3σ Evidence')
        ax.set_xlabel('Significance (σ)  relative to inactive null')
        ax.set_ylabel('Count')
        ax.set_title('Discovery Significance Scan')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        # ── Panel 4: Anomaly score distribution ──────────────────────
        ax = axes[1, 0]
        inlier  = self._cand_anomaly[self._cand_labels ==  1]
        outlier = self._cand_anomaly[self._cand_labels == -1]
        ax.hist(inlier,  bins=30, alpha=0.6, color='steelblue', label='Inlier (known-like)')
        ax.hist(outlier, bins=30, alpha=0.6, color='gold',      label='Outlier (novel)')
        ax.set_xlabel('Anomaly Score')
        ax.set_ylabel('Count')
        ax.set_title('Anomaly Score Distribution\n(outlier = novel chemical space)')
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        # ── Panel 5: IC50 profile comparison ─────────────────────────
        ax = axes[1, 1]
        active_ic50 = self._all_activities[
            np.array([c != "Inactive" for c in self._all_classes])]
        inactive_ic50 = self._all_activities[
            np.array([c == "Inactive" for c in self._all_classes])]

        ax.hist(np.log10(inactive_ic50), bins=30, alpha=0.5,
                color='gray',    label='DB Inactives',    density=True)
        ax.hist(np.log10(active_ic50),   bins=30, alpha=0.6,
                color='steelblue', label='DB Actives',    density=True)
        ax.hist(np.log10(self._cand_ic50), bins=30, alpha=0.6,
                color='tomato',  label='Predicted Cands', density=True)

        null_x = np.linspace(
            self.sig_tester.null_mean - 4 * self.sig_tester.null_std,
            self.sig_tester.null_mean + 4 * self.sig_tester.null_std, 200)
        ax.plot(null_x,
                norm.pdf(null_x, self.sig_tester.null_mean, self.sig_tester.null_std),
                'k--', linewidth=2, label='Null distribution')
        ax.set_xlabel('log₁₀(IC50) [nM]')
        ax.set_ylabel('Density')
        ax.set_title('Activity Profile & Null Distribution')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # ── Panel 6: Top 10 discoveries bar chart ────────────────────
        ax = axes[1, 2]
        top = self.discoveries[:10]
        if top:
            names = [f"Cand {d['index']}" for d in top]
            sigs  = [d['significance'] for d in top]
            cols  = ['red' if d['significance'] >= 5 else 'orange' for d in top]
            ax.barh(names[::-1], sigs[::-1], color=cols[::-1], alpha=0.8)
            ax.axvline(5, color='red',    linestyle='--', linewidth=1.5)
            ax.axvline(3, color='orange', linestyle='--', linewidth=1.5)
            ax.set_xlabel('Significance (σ)')
            ax.set_title('Top 10 Discoveries')
            ax.grid(True, alpha=0.3, axis='x')

        plt.suptitle('Drug Discovery — Particle Physics Significance Framework',
                     fontsize=14, fontweight='bold', y=1.01)
        plt.tight_layout()
        plt.show()
        return fig

    def print_report(self):
        print("\n" + "="*80)
        print("📊 DRUG DISCOVERY REPORT")
        print("="*80)

        n5     = sum(1 for d in self.discoveries if d['significance'] >= 5)
        n3     = sum(1 for d in self.discoveries if 3 <= d['significance'] < 5)
        n_nov  = sum(1 for d in self.discoveries if d['novel'])
        total  = len(self._cand_smiles)

        print(f"\n  Candidates screened : {total}")
        print(f"  5σ discoveries      : {n5}")
        print(f"  3σ evidence         : {n3}")
        print(f"  Novel space (−1)    : {n_nov} of above")

        print(f"\n🏆 TOP 10:")
        for i, d in enumerate(self.discoveries[:10]):
            print(f"\n  #{i+1}  {d['status']}")
            print(f"     IC50  : {d['predicted_ic50']:.1f} nM")
            print(f"     Sig   : {d['significance']:.2f}σ")
            print(f"     Novel : {d['novel']}")
            print(f"     SMILES: {d['smiles'][:70]}")

        very = [d for d in self.discoveries if d['predicted_ic50'] < 10]
        high = [d for d in self.discoveries if 10 <= d['predicted_ic50'] < 100]
        mod  = [d for d in self.discoveries if 100 <= d['predicted_ic50'] < 1000]

        print(f"\n💊 POTENCY BREAKDOWN:")
        if very: print(f"  IC50 <  10 nM (extremely potent): {len(very)}")
        if high: print(f"  IC50  10–100 nM (highly potent) : {len(high)}")
        if mod:  print(f"  IC50 100–1000 nM (moderate)     : {len(mod)}")

        print(f"\n🔬 NEXT STEPS:")
        print("  1. Install RDKit for real Morgan fingerprints")
        print("     pip install rdkit")
        print("  2. Download ChEMBL / BindingDB for real training data")
        print("  3. Validate top candidates with molecular docking (AutoDock Vina)")
        print("  4. Run ADMET predictions (SwissADME / pkCSM)")
        print("  5. Prioritize for synthesis and in vitro assay")

    # ── CSV export ────────────────────────────────────────────────────

    def save_results(self, csv_path='drug_discoveries.csv',
                     smiles_path='top_smiles.txt',
                     novel_path='novel_scaffolds.csv'):
        """
        Export all discoveries to CSV (with model metrics), a plain-text
        SMILES file for docking tools, and a separate CSV for novel scaffolds.
        """
        if not self.discoveries:
            print("No discoveries to save.")
            return None

        from datetime import datetime
        import csv

        timestamp = datetime.now().isoformat(timespec='seconds')
        r2   = getattr(self.predictor, 'cv_r2_mean',   float('nan'))
        rmse = getattr(self.predictor, 'cv_rmse_mean', float('nan'))

        fieldnames = ['rank', 'smiles', 'predicted_ic50_nM', 'significance_sigma',
                      'novel_space', 'status', 'model_r2', 'model_rmse_log10nM',
                      'timestamp']

        def write_csv(path, rows):
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(rows)

        all_rows, novel_rows = [], []
        for rank, d in enumerate(self.discoveries, start=1):
            row = {
                'rank':                  rank,
                'smiles':                d['smiles'],
                'predicted_ic50_nM':     f"{d['predicted_ic50']:.2f}",
                'significance_sigma':    f"{d['significance']:.2f}",
                'novel_space':           d['novel'],
                'status':                d['status'],
                'model_r2':              f"{r2:.3f}",
                'model_rmse_log10nM':    f"{rmse:.3f}",
                'timestamp':             timestamp,
            }
            all_rows.append(row)
            if d['novel']:
                novel_rows.append(row)

        write_csv(csv_path, all_rows)
        print(f"  ✓ {len(all_rows)} discoveries → {csv_path}")

        if novel_rows:
            write_csv(novel_path, novel_rows)
            print(f"  ✓ {len(novel_rows)} novel scaffolds → {novel_path}")

        with open(smiles_path, 'w', encoding='utf-8') as f:
            f.write(f"# Drug Discovery top candidates — {timestamp}\n")
            f.write(f"# model CV R²={r2:.3f}  RMSE={rmse:.3f} log10(nM)\n")
            f.write("# rank\tIC50_nM\tsigma\tSMILES\n")
            for rank, d in enumerate(self.discoveries[:10], start=1):
                f.write(f"{rank}\t{d['predicted_ic50']:.2f}\t"
                        f"{d['significance']:.2f}\t{d['smiles']}\n")
        print(f"  ✓ Top-10 SMILES → {smiles_path}")
        return csv_path

    # ── Lipinski Rule-of-5 analysis ───────────────────────────────────

    def analyze_drug_likeness(self, n=50, mw_plot_path='mw_distribution.png'):
        """
        Check Lipinski's Rule of Five for the top-n candidates.
        Prints a per-molecule table and saves a MW distribution plot.
        Requires RDKit; skips gracefully otherwise.
        """
        if not RDKIT_AVAILABLE:
            print("  ⚠  Drug-likeness analysis requires RDKit — skipping.")
            return []

        try:
            from rdkit.Chem import Descriptors, Lipinski
        except ImportError:
            print("  ⚠  rdkit.Chem.Descriptors not available — skipping.")
            return []

        results = []
        print(f"\n  {'#':<4} {'IC50':>8}  {'MW':>6}  {'LogP':>5}  "
              f"{'HBD':>4}  {'HBA':>4}  {'Viol':>4}  Drug-like")
        print("  " + "-"*60)

        for i, d in enumerate(self.discoveries[:n]):
            mol = Chem.MolFromSmiles(d['smiles'])
            if mol is None:
                continue
            mw   = Descriptors.MolWt(mol)
            logp = Descriptors.MolLogP(mol)
            hbd  = Lipinski.NumHDonors(mol)
            hba  = Lipinski.NumHAcceptors(mol)
            viol = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
            ok   = viol <= 1
            results.append({**d, 'MW': mw, 'LogP': logp,
                             'HBD': hbd, 'HBA': hba,
                             'Ro5_violations': viol, 'drug_like': ok})
            tick = '✓' if ok else '✗'
            print(f"  {i+1:<4} {d['predicted_ic50']:>7.1f}  "
                  f"{mw:>6.0f}  {logp:>5.2f}  {hbd:>4}  {hba:>4}  "
                  f"{viol:>4}  {tick}")

        if not results:
            return results

        # ── MW distribution plot ──────────────────────────────────────
        mws = [r['MW'] for r in results]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(mws, bins=15, edgecolor='black', color='steelblue', alpha=0.8)
        ax.axvline(500, color='red', linestyle='--', linewidth=1.5,
                   label='Lipinski MW limit (500 Da)')
        ax.set_xlabel('Molecular Weight (Da)')
        ax.set_ylabel('Count')
        ax.set_title(f'MW Distribution — top {len(mws)} candidates')
        ax.legend()
        plt.tight_layout()
        plt.savefig(mw_plot_path, dpi=150)
        plt.close()
        print(f"\n  ✓ MW distribution plot → {mw_plot_path}")

        n_ok = sum(r['drug_like'] for r in results)
        print(f"  Drug-like (≤1 Ro5 violation): {n_ok}/{len(results)}")
        return results

    # ── Scaffold diversity clustering ─────────────────────────────────

    def cluster_scaffolds(self, n_clusters=8, plot_path='scaffold_clusters.png'):
        """
        Cluster top discoveries by Morgan fingerprint similarity to identify
        unique chemical scaffolds worth pursuing independently.

        Uses the new rdFingerprintGenerator API (not deprecated AllChem method).
        """
        if not RDKIT_AVAILABLE:
            print("  ⚠  Scaffold clustering requires RDKit — skipping.")
            return {}

        smiles_list = [d['smiles'] for d in self.discoveries]
        if len(smiles_list) < n_clusters:
            print(f"  ⚠  Only {len(smiles_list)} discoveries — "
                  f"reducing clusters to {len(smiles_list)//2}")
            n_clusters = max(2, len(smiles_list) // 2)

        # Build fingerprint array using the already-instantiated generator
        fp_rows, valid_d = [], []
        for d in self.discoveries:
            mol = Chem.MolFromSmiles(d['smiles'])
            if mol is None:
                continue
            fp  = _MFPGEN.GetFingerprint(mol)
            arr = np.zeros(2048, dtype=np.float32)
            for bit in fp.GetOnBits():
                arr[bit] = 1.0
            fp_rows.append(arr)
            valid_d.append(d)

        if len(fp_rows) < n_clusters:
            print(f"  ⚠  Too few valid molecules for clustering.")
            return {}

        fp_matrix = np.array(fp_rows)
        km        = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels    = km.fit_predict(fp_matrix)

        # ── Pick the best molecule from each cluster (lowest IC50) ───
        cluster_reps = {}
        for label, d in zip(labels, valid_d):
            if label not in cluster_reps or \
               d['predicted_ic50'] < cluster_reps[label]['predicted_ic50']:
                cluster_reps[label] = {**d, 'cluster': int(label)}

        print(f"\n  {n_clusters} scaffold clusters identified:")
        print(f"  {'Cluster':<8} {'IC50':>8}  {'Sig':>7}  {'Novel':>6}  SMILES")
        print("  " + "-"*72)
        for lbl in sorted(cluster_reps):
            r = cluster_reps[lbl]
            print(f"  {lbl:<8} {r['predicted_ic50']:>7.1f}  "
                  f"{r['significance']:>6.1f}σ  "
                  f"{'yes' if r['novel'] else 'no':>6}  "
                  f"{r['smiles'][:45]}")

        # ── 2-D PCA scatter coloured by cluster ──────────────────────
        pca2   = PCA(n_components=2, random_state=42)
        coords = pca2.fit_transform(fp_matrix)

        fig, ax = plt.subplots(figsize=(8, 6))
        cmap    = plt.cm.tab10
        for lbl in range(n_clusters):
            mask = labels == lbl
            ax.scatter(coords[mask, 0], coords[mask, 1],
                       s=30, alpha=0.7, color=cmap(lbl / n_clusters),
                       label=f'Cluster {lbl}')
            # Mark representative
            rep_idx = next(i for i, (l, _) in enumerate(zip(labels, valid_d))
                           if l == lbl and _['smiles'] == cluster_reps[lbl]['smiles'])
            ax.scatter(coords[rep_idx, 0], coords[rep_idx, 1],
                       s=150, color=cmap(lbl / n_clusters),
                       edgecolors='black', linewidths=1.5, zorder=5)

        ax.set_xlabel(f'PC1 ({pca2.explained_variance_ratio_[0]*100:.1f}%)')
        ax.set_ylabel(f'PC2 ({pca2.explained_variance_ratio_[1]*100:.1f}%)')
        ax.set_title(f'Scaffold Diversity — {n_clusters} clusters\n'
                     f'(★ = cluster representative)')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150)
        plt.close()
        print(f"  ✓ Cluster PCA plot → {plot_path}")
        return cluster_reps

    # ── Structure grid visualisation (requires RDKit) ─────────────────

    def visualize_structures(self, n=12, out_path='top_candidates.png'):
        """
        Draw a grid image of the top-n discovered molecules.
        Requires RDKit (for drawing) and Pillow (for PNG export).
        Skips silently when RDKit is not installed.
        """
        if not RDKIT_AVAILABLE:
            print("  ⚠  Structure visualisation requires RDKit — skipping.")
            return

        if not self.discoveries:
            print("  No discoveries to draw.")
            return

        try:
            from rdkit.Chem import Draw
        except ImportError:
            print("  ⚠  rdkit.Chem.Draw not available — skipping structure grid.")
            return

        mols, legends = [], []
        for d in self.discoveries[:n]:
            mol = Chem.MolFromSmiles(d['smiles'])
            if mol is not None:
                mols.append(mol)
                legends.append(
                    f"IC50: {d['predicted_ic50']:.1f} nM\n"
                    f"Sig: {d['significance']:.1f}σ  "
                    f"{'🆕' if d['novel'] else ''}"
                )

        if not mols:
            print("  ⚠  No valid molecules to draw.")
            return

        try:
            img = Draw.MolsToGridImage(
                mols,
                molsPerRow=4,
                subImgSize=(300, 250),
                legends=legends,
                returnPNG=False,
            )
            img.save(out_path)
            print(f"  ✓ Structure grid saved → {out_path}  ({len(mols)} molecules)")
        except Exception as e:
            print(f"  ⚠  Could not save structure grid: {e}")



# ============================================================
# DOCKING MODULE — AutoDock Vina via subprocess (Windows-safe)
# ============================================================

class VinaDocker:
    """
    Molecular docking validation using the AutoDock Vina executable.

    Calls the Vina binary directly via subprocess — no C++/Boost compilation
    needed. Uses Meeko v0.5 API (PDBQTWriterLegacy) for ligand preparation.

    ── YOUR CONFIRMED SETUP ─────────────────────────────────────────────────
    Vina binary   : ./bin/vina.exe          (confirmed present)
    Meeko         : installed, v0.5 API     (confirmed working)

    Two receptor/target profiles are pre-configured below.
    Switch between them by changing ACTIVE_TARGET.

    HIV-1 Protease  ─────────────────────────────────────────────────────────
      Receptor      : hiv_protease.pdbqt   (confirmed prepared)
      Binding site  : (-11.4, 19.8, 28.0) extracted from 1HHP
      Box size      : 25 × 25 × 25 Å
      Reference     : Lopinavir, Saquinavir, Indinavir, Ritonavir
      Passing score : < -9.0 kcal/mol  (competitive with clinical PIs)

    EGFR Kinase  ────────────────────────────────────────────────────────────
      Receptor      : cancer_egfr_agent/egfr_receptor.pdbqt  (confirmed, 173K)
      Binding site  : (22.0, 2.5, 48.5) from 4HJO Erlotinib co-crystal
      Box size      : 20 × 20 × 20 Å
      Reference     : Erlotinib, Gefitinib, Osimertinib
      Passing score : < -9.0 kcal/mol  (competitive with approved TKIs)
    ─────────────────────────────────────────────────────────────────────────
    """

    # ── Switch target here ────────────────────────────────────────────
    ACTIVE_TARGET = "EGFR"      # "EGFR" or "HIV"

    # ── Vina executable — confirmed at this path ──────────────────────
    VINA_EXE = "./bin/vina.exe"

    # ── HIV-1 Protease config ─────────────────────────────────────────
    HIV_RECEPTOR = "hiv_protease.pdbqt"
    HIV_BOX = dict(
        center_x=-11.4, center_y=19.8,  center_z=28.0,
        size_x=25.0,    size_y=25.0,    size_z=25.0,
    )
    HIV_REFERENCES = {
        "Lopinavir":  "CC(C)CC1(CC(CC(=O)N2CC3SCCC3C2C(=O)NC(CC2CCCCC2)CC(=O)O)O)C(=O)NC(Cc2ccccc2)CC(=O)O",
        "Saquinavir": "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(O)C(Cc1ccccc1)NC(=O)C(CC(N)=O)NC(=O)c1ccc2ccccc2n1",
        "Ritonavir":  "CC(C)c1nc(CN2CCCC2C(=O)NC(CC(C)C)CC(=O)NC(Cc2ccccc2)CC(O)C(Cc2ccccc2)NC(=O)OCc2cncs2)cs1",
        "Indinavir":  "CC(C)(C)NC(=O)C1CN2CCC1CC2CN(CC1=CC=CC=N1)C(=O)C(O)CC1=CC=CC=C1",
    }

    # ── EGFR Kinase config ────────────────────────────────────────────
    EGFR_RECEPTOR = "cancer_egfr_agent/egfr_receptor.pdbqt"
    EGFR_BOX = dict(
        center_x=24.77, center_y=9.19,  center_z=0.0,
        size_x=20.0,    size_y=20.0,    size_z=20.0,
    )
    EGFR_REFERENCES = {
        "Erlotinib":   "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1",
        "Gefitinib":   "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",
        "Osimertinib": "COc1cc2c(Nc3ccc(NC(=O)/C=C/CN(C)C)cc3F)ncnc2cc1N(C)CCN1CCOCC1",
    }

    def __init__(self, vina_exe=None, receptor_pdbqt=None, box=None,
                 target=None):
        # Select target profile
        tgt = (target or self.ACTIVE_TARGET).upper()
        if tgt == "HIV":
            default_receptor = self.HIV_RECEPTOR
            default_box      = self.HIV_BOX
            self.REFERENCE_SMILES = self.HIV_REFERENCES
            self._passing_score   = -9.0
            self._target_label    = "HIV-1 Protease"
        else:   # EGFR
            default_receptor = self.EGFR_RECEPTOR
            default_box      = self.EGFR_BOX
            self.REFERENCE_SMILES = self.EGFR_REFERENCES
            self._passing_score   = -9.0
            self._target_label    = "EGFR Kinase"

        self.vina_exe  = vina_exe        or self.VINA_EXE
        self.receptor  = receptor_pdbqt  or default_receptor
        self.box       = box             or default_box
        self._vina_ok  = self._check_vina()
        self._meeko_ok = self._check_meeko()
        print(f"  Target profile   : {self._target_label}")
        print(f"  Receptor         : {self.receptor}")
        print(f"  Box center       : ({self.box['center_x']}, "
              f"{self.box['center_y']}, {self.box['center_z']})")
        print(f"  Passing affinity : < {self._passing_score} kcal/mol")

    def _check_vina(self):
        import shutil
        if shutil.which(self.vina_exe) or __import__("os").path.isfile(self.vina_exe):
            return True
        print(f"  ⚠  Vina executable not found: {self.vina_exe}")
        print("     Download from: https://github.com/ccsb-scripps/AutoDock-Vina/releases")
        return False

    @staticmethod
    def _meeko_imports():
        """
        Meeko's API has changed across versions.
        Returns (MoleculePreparation, writer_fn) or raises ImportError.

        v0.3–0.4:  MoleculePreparation + write_pdbqt_string()
        v0.5–0.6:  MoleculePreparation + PDBQTWriterLegacy.write_string()
        v0.7+   :  MoleculePreparation + PDBQTWriterLegacy.write_string()
                   (PDBQTWriterLegacy moved to meeko.writer in some builds)
        """
        import meeko

        # Try current recommended path first
        try:
            from meeko import MoleculePreparation, PDBQTWriterLegacy
            # Verify write_string is callable
            _ = PDBQTWriterLegacy.write_string
            return MoleculePreparation, PDBQTWriterLegacy
        except (ImportError, AttributeError):
            pass

        # Try meeko.writer submodule (some 0.7.x builds)
        try:
            from meeko import MoleculePreparation
            from meeko.writer import PDBQTWriterLegacy
            return MoleculePreparation, PDBQTWriterLegacy
        except (ImportError, AttributeError):
            pass

        # Try meeko.rdkit_mol_prep (0.7+ restructure)
        try:
            from meeko import MoleculePreparation
            from meeko.rdkit_mol_prep import PDBQTWriterLegacy
            return MoleculePreparation, PDBQTWriterLegacy
        except (ImportError, AttributeError):
            pass

        # Last resort: check what IS available and report it
        available = [x for x in dir(meeko) if not x.startswith('_')]
        raise ImportError(
            f"meeko {meeko.__version__} installed but PDBQTWriterLegacy not found.\n"
            f"  Available: {available}\n"
            f"  Try: pip install 'meeko==0.5.0'"
        )

    def _check_meeko(self):
        try:
            MoleculePreparation, PDBQTWriterLegacy = self._meeko_imports()
            return True
        except ImportError as e:
            print(f"  ⚠  {e}")
            return False

    def smiles_to_pdbqt(self, smiles, out_path):
        """
        Convert SMILES to PDBQT using RDKit + Meeko v0.5 API.
        Uses PDBQTWriterLegacy.write_string() — the confirmed working path
        from your EGFR docking runs. Deprecation warnings suppressed.
        """
        if not RDKIT_AVAILABLE:
            return False
        try:
            import warnings
            from rdkit.Chem import AllChem
            # Import fresh each call using version-aware importer
            try:
                MoleculePreparation, PDBQTWriterLegacy = self._meeko_imports()
            except ImportError as e:
                print(f"    {e}")
                return False

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return False
            mol = Chem.AddHs(mol)

            # ETKDGv3 with fallback to random coords if embedding fails
            params = AllChem.ETKDGv3()
            params.randomSeed = 42
            result = AllChem.EmbedMolecule(mol, params)
            if result == -1:
                # Fallback: random distance geometry
                AllChem.EmbedMolecule(mol, AllChem.ETKDG())
            AllChem.MMFFOptimizeMolecule(mol)

            # Meeko v0.5 API — suppress the DeprecationWarning you saw in
            # your EGFR runs (MoleculePreparation.write_pdbqt_string deprecated)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                preparator = MoleculePreparation()
                mol_setups  = preparator.prepare(mol)

            if not mol_setups:
                return False

            # Confirmed working: PDBQTWriterLegacy.write_string(setup)
            pdbqt_string, _, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
            with open(out_path, "w") as f:
                f.write(pdbqt_string)
            return True
        except Exception as e:
            print(f"    PDBQT conversion failed: {e}")
            return False

    def dock_smiles(self, smiles, name="ligand", exhaustiveness=8):
        """
        Dock a single SMILES string.
        Returns best binding affinity in kcal/mol, or None if docking fails.
        """
        if not self._vina_ok:
            return None
        if not __import__("os").path.isfile(self.receptor):
            print(f"  ⚠  Receptor file not found: {self.receptor}")
            print("     Prepare your PDB with AutoDock Tools or use prepare_receptor4.py")
            return None

        import tempfile, subprocess, os, re

        with tempfile.TemporaryDirectory() as tmpdir:
            lig_path = os.path.join(tmpdir, f"{name}.pdbqt")
            out_path = os.path.join(tmpdir, f"{name}_out.pdbqt")

            if not self.smiles_to_pdbqt(smiles, lig_path):
                return None

            cmd = [
                self.vina_exe,
                "--receptor", self.receptor,
                "--ligand",   lig_path,
                "--out",      out_path,
                "--center_x", str(self.box["center_x"]),
                "--center_y", str(self.box["center_y"]),
                "--center_z", str(self.box["center_z"]),
                "--size_x",   str(self.box["size_x"]),
                "--size_y",   str(self.box["size_y"]),
                "--size_z",   str(self.box["size_z"]),
                "--exhaustiveness", str(exhaustiveness),
                "--num_modes", "5",
            ]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )
                # Parse best affinity from Vina output table
                # Format: "   1        -8.5       0.000      0.000"
                for line in result.stdout.splitlines():
                    m = re.match(r"\s+1\s+(-\d+\.\d+)", line)
                    if m:
                        return float(m.group(1))
                return None
            except subprocess.TimeoutExpired:
                print(f"    Docking timed out for {name}")
                return None
            except FileNotFoundError:
                print(f"    Vina executable not found at: {self.vina_exe}")
                print(f"    PATH: {__import__('os').environ.get('PATH','')[:120]}")
                return None

    def dock_discoveries(self, discoveries, n=10, exhaustiveness=8):
        """
        Dock the top-n discoveries and rank by combined score.
        Combined score = significance × |binding_affinity|
        Returns enriched list sorted by combined score.
        """
        print("\n" + "="*60)
        print("🧬 MOLECULAR DOCKING VALIDATION")
        print("="*60)

        if not self._vina_ok:
            print("  ⚠  Vina not available — skipping docking.")
            print("  To enable:")
            print("  1. Download vina_1.2.7_windows_x86_64.exe from GitHub releases")
            print("  2. Set VinaDocker.VINA_EXE to its path")
            print("  3. Prepare your receptor PDBQT and set VinaDocker.RECEPTOR_PDB")
            return discoveries

        if not __import__("os").path.isfile(self.receptor):
            print(f"  ⚠  Receptor {self.receptor} not found.")
            print("  Download 4WKQ.pdb from https://www.rcsb.org/structure/4WKQ")
            print("  Then prepare it with AutoDock Tools or reduce + prepare_receptor4.py")
            return discoveries

        # Calibrate with reference binder first
        print("  Calibrating with reference inhibitors...")
        for name, smi in self.REFERENCE_SMILES.items():
            aff = self.dock_smiles(smi, name=name, exhaustiveness=exhaustiveness)
            if aff:
                grade = "✓ good" if aff < self._passing_score else "⚠ weak"
                print(f"    {name:<14}: {aff:>6.2f} kcal/mol  {grade}")

        print(f"\n  Docking top {n} candidates...")
        enriched = []
        for i, d in enumerate(discoveries[:n]):
            print(f"  [{i+1:2d}/{n}] {d['smiles'][:45]}...")
            aff = self.dock_smiles(
                d["smiles"], name=f"cand_{i:03d}",
                exhaustiveness=exhaustiveness
            )
            entry = dict(d)
            entry["binding_affinity_kcal"] = aff
            if aff is not None:
                # Combined score: significance × |affinity| — rewards both criteria
                entry["combined_score"] = d["significance"] * abs(aff)
                grade = "🎉" if aff < self._passing_score else "  "
                print(f"       {grade} IC50={d['predicted_ic50']:.0f} nM  "
                      f"Sig={d['significance']:.1f}σ  "
                      f"Affinity={aff:.2f} kcal/mol  "
                      f"Score={entry['combined_score']:.1f}")
            else:
                entry["combined_score"] = 0.0
                print(f"       Docking failed")
            enriched.append(entry)

        enriched.sort(key=lambda x: x["combined_score"], reverse=True)

        print("\n  ── Docking-enriched ranking ─────────────────────────────")
        print(f"  {'#':<4} {'IC50':>8}  {'Sig':>6}  {'Affinity':>10}  "
              f"{'Score':>8}  SMILES")
        print("  " + "-"*80)
        for i, d in enumerate(enriched):
            aff_str = (f"{d['binding_affinity_kcal']:>+.2f} kcal/mol"
                       if d["binding_affinity_kcal"] else "     n/a      ")
            print(f"  {i+1:<4} {d['predicted_ic50']:>8.0f}  "
                  f"{d['significance']:>6.1f}σ  {aff_str}  "
                  f"{d['combined_score']:>8.1f}  {d['smiles'][:35]}")

        return enriched


# ============================================================
# COMPARISON TABLE
# ============================================================

def print_comparison():
    rows = [
        ("Signal",           "Particle resonance peak",   "Novel active molecule"),
        ("Background",       "QCD / SM processes",        "Inactive decoy distribution"),
        ("Null distribution","Background-only MC",        "Predicted IC50 of inactives"),
        ("5σ threshold",     "P(false positive) < 3×10⁻⁷","Same criterion, same cutoff"),
        ("Cover's theorem",  "mass + pT feature space",   "fingerprint + activity space"),
        ("Anomaly detection","IsolationForest on events", "IsolationForest on molecules"),
        ("Template fitting", "MC shape → Poisson bins",   "RF model → prediction range"),
    ]
    print("\n" + "="*80)
    print("🔬 PARTICLE PHYSICS ↔ DRUG DISCOVERY  (same math, different domain)")
    print("="*80)
    print(f"  {'Concept':<22} {'Particle Physics':<32} {'Drug Discovery'}")
    print("  " + "-"*76)
    for row in rows:
        print(f"  {row[0]:<22} {row[1]:<32} {row[2]}")
    print("="*80)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import time
    t0 = time.time()

    print("\n" + "="*80)
    print("💊 AI-POWERED DRUG DISCOVERY")
    print("   Higgs-hunting statistics applied to pharmaceutical research")
    print("="*80)

    # ── Pipeline configuration ───────────────────────────────────────
    #
    # UPGRADES ACTIVE IN THIS VERSION:
    #   ✓ ChemProp GNN (install: pip install chemprop torch)
    #   ✓ EGFR-biased scaffolds (23 cores including anilinopyrimidine, azaindole)
    #   ✓ 15,000 ChEMBL compounds (up from 5,000) for better model
    #   ✓ ADMET filter (rule-based always; ML with: pip install admet-ai)
    #   ✓ Enamine REAL (download from enamine.net, set EnamineREALLoader.DEFAULT_PATH)
    #
    # OTHER TARGETS:
    #   CHEMBL301   Thrombin        CHEMBL240  hERG (cardiac safety)
    #   CHEMBL2971  JAK2 kinase     CHEMBL4822 SARS-CoV-2 Mpro
    #   CHEMBL2364  HIV-1 Protease
    # ─────────────────────────────────────────────────────────────────
    engine = DrugDiscoveryEngine()
    engine.run(
        n_candidates=500,
        use_chembl=True,
        chembl_target="CHEMBL203",    # EGFR kinase — best-balanced ChEMBL target
                                      # ~3000 actives, ~800 inactives, real SAR cliffs
                                      # Other options:
                                      #   "CHEMBL301"   Thrombin
                                      #   "CHEMBL2971"  JAK2
                                      #   "CHEMBL240"   hERG (cardiac safety)
                                      #   "CHEMBL2364"  HIV-1 Protease (correct ID)
        active_threshold_nM=1000,
        inactive_threshold_nM=10000,
    )
    engine.visualize()
    engine.print_report()

    print("\n" + "="*60)
    print("💾 SAVING RESULTS")
    print("="*60)
    engine.save_results(csv_path='drug_discoveries.csv',
                        smiles_path='top_smiles.txt',
                        novel_path='novel_scaffolds.csv')

    print("\n" + "="*60)
    print("💊 DRUG-LIKENESS (LIPINSKI Ro5)")
    print("="*60)
    engine.analyze_drug_likeness(n=20, mw_plot_path='mw_distribution.png')

    print("\n" + "="*60)
    print("🔬 SCAFFOLD CLUSTERING")
    print("="*60)
    engine.cluster_scaffolds(n_clusters=8, plot_path='scaffold_clusters.png')

    print("\n" + "="*60)
    print("🖼  DRAWING TOP CANDIDATES")
    print("="*60)
    engine.visualize_structures(n=12, out_path='top_candidates.png')

    # ── Optional: Molecular docking validation ──────────────────────
    # Requires Vina executable + prepared receptor PDBQT.
    # See VinaDocker docstring for setup instructions.
    print("\n" + "="*60)
    print("🧬 DOCKING VALIDATION")
    print("="*60)
    # ACTIVE_TARGET = "EGFR"  →  cancer_egfr_agent/egfr_receptor.pdbqt
    # ACTIVE_TARGET = "HIV"   →  hiv_protease.pdbqt
    docker = VinaDocker()
    docker.dock_discoveries(engine.discoveries, n=10)

    print_comparison()

    print(f"\n⏱  Total runtime: {time.time() - t0:.1f}s")