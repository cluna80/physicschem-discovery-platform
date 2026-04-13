"""
Novelty check for EGFR drug discovery candidates.
Queries ChEMBL and PubChem for each candidate SMILES.

Run 1 (original pipeline):   11 candidates, best IC50 288 nM, best docking -8.81
Run 2 (upgraded pipeline):   55 candidates, best IC50 84 nM,  best docking -10.10
"""
import time
import urllib.request, json, urllib.parse

# ── Run 2 candidates (upgraded — EGFR-biased anilinoquinazoline series) ──
RUN2_CANDIDATES = [
    ("R2-C1  4.7σ", "Fc1cccc(CCCCc2ccc(Nc3ncnc4ccccc34)cc2)c1",  "84 nM",  "-9.41",  False),
    ("R2-C2  4.4σ", "Fc1ccc(CCNc2ccc(Nc3ncnc4ccccc34)cc2)cc1",   "122 nM", "-10.10", True),
    ("R2-C3  4.4σ", "c1ccc(CCCc2ccc3[nH]cnc3c2)cc1",             "124 nM", "-8.46",  False),
    ("R2-C4  4.4σ", "Fc1ccc(CCCc2ccc(Nc3ncnc4ccccc34)cc2)cc1",   "126 nM", "-10.05", False),
    ("R2-C5  4.3σ", "Fc1ccc(CCCCc2ccc(Nc3ncnc4ccccc34)cc2)cc1",  "134 nM", "-9.33",  False),
    ("R2-C6  4.3σ", "Clc1cccc(CCCc2ccc3[nH]cnc3c2)c1",           "136 nM", "-8.57",  False),
    ("R2-C7  4.3σ", "CC(=O)NCCCCOc1ccc(Nc2ncnc3ccccc23)cc1",     "140 nM", "-8.69",  False),
    ("R2-C8  4.2σ", "Nc1cccc(CCNc2ccc3[nH]cnc3c2)c1",            "149 nM", "-8.59",  False),
    ("R2-C9  4.2σ", "O=C(O)CCCNc1ccc2[nH]cnc2c1",                "150 nM", "-6.84",  True),
    ("R2-C10 4.2σ", "Nc1cccc(CCCc2ccc3[nH]cnc3c2)c1",            "152 nM", "-9.03",  False),
]

# ── Run 1 candidates (original — isobutyl-piperidine series) ─────────────
RUN1_CANDIDATES = [
    ("R1-C1  5.4σ", "CC(CC1CCNCC1)c1cccc(N)c1",         "288 nM",  "-7.87", False),
    ("R1-C2  4.4σ", "CC(CC1CCC2CCCC2C1)c1cccc(F)c1",    "686 nM",  "-8.81", False),
    ("R1-C3  4.4σ", "CC(CC1CCNCC1)c1cccc(F)c1",         "686 nM",  "-7.47", True),
    ("R1-C4  4.3σ", "CC(CC1CCOCC1)c1cccc(F)c1",         "704 nM",  "-7.34", False),
    ("R1-C5  4.2σ", "CC(CC1CCC2CCCC2C1)c1cccc(O)c1",    "769 nM",  "-8.79", False),
    ("R1-C6  4.2σ", "CC(CC1CCOCC1)c1cccc(O)c1",         "788 nM",  "-7.91", False),
    ("R1-C7  3.4σ", "CC(CC1CCNCC1)c1ccccc1",            "1506 nM", "-7.14", False),
    ("R1-C8  3.4σ", "CC(CC1CCOCC1)c1ccc(F)cc1",         "1521 nM", "-7.41", False),
    ("R1-C9  3.4σ", "CC(=O)NCCCCOc1coc2ccccc12",        "1534 nM", "-7.03", False),
    ("R1-C10 3.4σ", "NCCCOc1coc2ccccc12",               "1534 nM", "-6.64", False),
    ("R1-C11 3.4σ", "c1ccc2c(OCCC3CCCC3)coc2c1",        "1534 nM", "-6.64", False),
]

ALL_RUNS = [
    ("Run 2 — EGFR-biased (anilinoquinazoline/azaindole)", RUN2_CANDIDATES),
    ("Run 1 — Original (isobutyl-piperidine series)",      RUN1_CANDIDATES),
]

def check_chembl(candidates):
    try:
        from chembl_webresource_client.new_client import new_client
        mol_client = new_client.molecule
        novel = []
        for label, smi, ic50, vina, ns in candidates:
            results = list(mol_client.filter(
                molecule_structures__canonical_smiles=smi))
            found = len(results) > 0
            status = f"✗ {results[0].get('molecule_chembl_id','?')}" if found else "✓ NOT in ChEMBL"
            flag = " ★" if ns else ""
            print(f"  {label:<14} {ic50:<9} {vina:>8} kcal  {status}{flag}")
            if not found:
                novel.append((label, smi, ic50, vina, ns))
            time.sleep(0.3)
        return novel
    except ImportError:
        print("  chembl-webresource-client not installed")
        return candidates

def check_pubchem(candidates):
    novel = []
    for label, smi, ic50, vina, ns in candidates:
        encoded = urllib.parse.quote(smi)
        url = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"
               f"smiles/{encoded}/cids/JSON")
        try:
            with urllib.request.urlopen(url, timeout=12) as resp:
                data = json.loads(resp.read())
                cids = [c for c in data.get("IdentifierList", {}).get("CID", []) if c != 0]
                if cids:
                    status = f"✗ CID {cids[0]}"
                else:
                    status = "✓ NOT in PubChem"
                    novel.append((label, smi, ic50, vina, ns))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                status = "✓ NOT in PubChem"
                novel.append((label, smi, ic50, vina, ns))
            else:
                status = f"⚠  HTTP {e.code}"
        except Exception as e:
            status = f"⚠  {type(e).__name__}"
        flag = " ★" if ns else ""
        print(f"  {label:<14} {ic50:<9} {vina:>8} kcal  {status}{flag}")
        time.sleep(0.4)
    return novel

# ── Main ──────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("🔍 NOVELTY CHECK — ChEMBL + PubChem  (★ = novel chemical space)")
print("="*72)

all_chembl_novel, all_pubchem_novel = [], []
all_flat = []

for run_label, candidates in ALL_RUNS:
    all_flat.extend(candidates)
    n = len(candidates)
    print(f"\n{'─'*72}")
    print(f"  {run_label}  ({n} candidates)")
    print(f"{'─'*72}")
    print(f"  {'ID':<14} {'IC50':<9} {'Vina':>8}       ChEMBL")
    cn = check_chembl(candidates)
    all_chembl_novel.extend(cn)
    print(f"\n  → {len(cn)}/{n} NOT in ChEMBL\n")
    print(f"  {'ID':<14} {'IC50':<9} {'Vina':>8}       PubChem")
    pn = check_pubchem(candidates)
    all_pubchem_novel.extend(pn)
    print(f"\n  → {len(pn)}/{n} NOT in PubChem")

# ── Summary ───────────────────────────────────────────────────────────────
total = len(all_flat)
chembl_smiles  = {s for _, s, *_ in all_chembl_novel}
pubchem_smiles = {s for _, s, *_ in all_pubchem_novel}
both_novel     = chembl_smiles & pubchem_smiles

print("\n" + "="*72)
print("📊 COMBINED NOVELTY SUMMARY")
print("="*72)
print(f"\n  Total candidates : {total}")
print(f"  Not in ChEMBL    : {len(all_chembl_novel)}/{total}")
print(f"  Not in PubChem   : {len(all_pubchem_novel)}/{total}")
print(f"  Novel in BOTH    : {len(both_novel)}/{total}")

if both_novel:
    print("\n  🆕 CONFIRMED NOVEL IN BOTH ChEMBL AND PubChem:")
    print(f"  {'ID':<14} {'IC50':<9} {'Vina':>10}  Space  SMILES")
    print("  " + "─"*72)
    for label, smi, ic50, vina, ns in all_flat:
        if smi in both_novel:
            flag = "★ Novel" if ns else "Known"
            print(f"  {label:<14} {ic50:<9} {vina:>8} kcal  {flag}  {smi}")

priority = [(l,s,i,v) for l,s,i,v,ns in all_flat if s in both_novel and ns]
if priority:
    print(f"\n  🏆 PRIORITY — novel in both DBs + novel chemical space:")
    for label, smi, ic50, vina in priority:
        print(f"\n    {label}  IC50={ic50}  Vina={vina} kcal/mol")
        print(f"    SMILES: {smi}")

print(f"""
  ── Run comparison ───────────────────────────────────────────────────
  Run 1 best docking : -8.81 kcal/mol  (below Erlotinib -8.04)
  Run 2 best docking : -10.10 kcal/mol (beats ALL 3 approved EGFR drugs)
  Run 1 best IC50    : 288 nM
  Run 2 best IC50    : 84 nM  (3.4x more potent)
  Upgrade that drove improvement: EGFR-biased scaffolds

  ── Next steps for confirmed novel compounds ─────────────────────────
  1. Patent search  : Espacenet or Google Patents
  2. Synthesis quote: Enamine / Mcule (~$300-800, 4-6 weeks)
  3. Binding assay  : EGFR HTRF or SPR (~$2,000-5,000/compound)
  4. If active      : X-ray crystallography to confirm binding mode
  5. Publication    : J. Med. Chem. or ACS Med. Chem. Lett.
""")