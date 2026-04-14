"""
admet_profiler.py
=================
PhysicsChem Platform — Real ADMET Profiling Module

Profiles compounds using ADMET-AI (104 properties) + RDKit SA Score.
Can be run standalone or imported by dashboard/agent.

USAGE:
    python admet_profiler.py --id SEED_INT_RAL_G004
    python admet_profiler.py --smiles "O=C(NCC..."
    python admet_profiler.py --top 10 --target HIV_INTEGRASE
    python admet_profiler.py --update-library   # batch update DB
"""

import os, sys, json, sqlite3, argparse, warnings, csv
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')

GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; RST="\033[0m"; BLD="\033[1m"

# ── Key ADMET properties to display ──────────────────────────────────
ADMET_PANEL = {
    # Absorption
    "Bioavailability_Ma":           ("Oral Bioavailability",    ">0.5 good",  True),
    "HIA_Hou":                      ("GI Absorption",           ">0.7 good",  True),
    "Caco2_Wang":                   ("Caco2 Permeability",      ">-5.15 good",True),
    "PAMPA_NCATS":                  ("PAMPA Permeability",      ">0.5 good",  True),
    "Solubility_AqSolDB":           ("Aqueous Solubility",      ">-4 good",   True),
    # Distribution
    "BBB_Martins":                  ("BBB Penetration",         "<0.3 good",  False),
    "PPBR_AZ":                      ("Plasma Protein Binding",  "<90% good",  False),
    "VDss_Lombardo":                ("Volume of Distribution",  "0.1-20 good",True),
    # Metabolism
    "CYP3A4_Substrate_CarbonMangels":("CYP3A4 Substrate",      "<0.5 good",  False),
    "CYP2C9_Veith":                 ("CYP2C9 Inhibition",       "<0.5 good",  False),
    "CYP2C19_Veith":                ("CYP2C19 Inhibition",      "<0.5 good",  False),
    "CYP3A4_Veith":                 ("CYP3A4 Inhibition",       "<0.5 good",  False),
    "Half_Life_Obach":              ("Half-Life (h)",            ">2h good",   True),
    "Clearance_Microsome_AZ":       ("Microsomal Clearance",    "<50 good",   False),
    # Excretion / Toxicity
    "hERG":                         ("hERG Cardiotoxicity",     "<0.5 safe",  False),
    "DILI":                         ("DILI Liver Toxicity",     "<0.5 safe",  False),
    "AMES":                         ("AMES Mutagenicity",       "<0.3 safe",  False),
    "Carcinogens_Lagunin":          ("Carcinogenicity",         "<0.3 safe",  False),
    "ClinTox":                      ("Clinical Toxicity",       "<0.3 safe",  False),
    "Pgp_Broccatelli":              ("P-gp Efflux",             "<0.5 good",  False),
    # Drug-likeness
    "QED":                          ("Drug-likeness (QED)",     ">0.5 good",  True),
    "Lipinski":                     ("Lipinski Violations",     "0 good",     True),
}

def get_admet_scores(smiles: str) -> dict:
    """Get full ADMET-AI profile for a SMILES string."""
    try:
        import contextlib, io
        with contextlib.redirect_stderr(io.StringIO()):
            from admet_ai import ADMETModel
            model = ADMETModel()
        results = model.predict(smiles=smiles)
        return results
    except Exception as e:
        print(f"{RED}ADMET-AI error: {e}{RST}")
        return {}

def get_sa_score(smiles: str) -> float:
    """Calculate synthetic accessibility score (1=easy, 10=hard)."""
    try:
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcNumRings
        import sys
        # Try SA score from RDKit contrib
        try:
            sys.path.append(os.path.join(
                __import__('rdkit').RDConfig.RDContribDir, 'SA_Score'))
            import sascorer
            mol = Chem.MolFromSmiles(smiles)
            return round(sascorer.calculateScore(mol), 2) if mol else None
        except Exception:
            # Fallback: estimate from molecular complexity
            from rdkit.Chem import Descriptors, rdMolDescriptors
            mol = Chem.MolFromSmiles(smiles)
            if not mol: return None
            rings    = rdMolDescriptors.CalcNumRings(mol)
            stereo   = rdMolDescriptors.CalcNumAtomStereoCenters(mol)
            mw       = Descriptors.MolWt(mol)
            # Rough estimate
            sa = 1 + (rings * 0.5) + (stereo * 1.0) + (max(0, mw-300) * 0.005)
            return round(min(10, max(1, sa)), 1)
    except Exception:
        return None

def format_admet_report(smiles: str, compound_id: str = "COMPOUND") -> dict:
    """Generate full ADMET + SA report for a compound."""
    print(f"\n{BLD}{CYN}ADMET Profile: {compound_id}{RST}")
    print(f"{CYN}{'═'*52}{RST}")

    scores = get_admet_scores(smiles)
    sa     = get_sa_score(smiles)

    if not scores:
        return {}

    report = {"id": compound_id, "smiles": smiles,
              "sa_score": sa, "timestamp": datetime.now().isoformat()}

    # Categorize
    flags = {"PASS": [], "WARN": [], "FAIL": []}

    print(f"\n{'Property':<28} {'Value':>8}  {'Status':<10} {'Note'}")
    print("─"*65)

    for key, (label, note, higher_better) in ADMET_PANEL.items():
        if key not in scores: continue
        val = scores[key]

        # Determine pass/warn/fail
        if key in ("hERG","DILI","AMES","Carcinogens_Lagunin","ClinTox"):
            # Toxicity — lower is better
            status = "PASS" if val < 0.3 else "WARN" if val < 0.6 else "FAIL"
        elif key in ("Bioavailability_Ma","HIA_Hou","PAMPA_NCATS","QED"):
            status = "PASS" if val > 0.7 else "WARN" if val > 0.4 else "FAIL"
        elif key == "Solubility_AqSolDB":
            status = "PASS" if val > -4 else "WARN" if val > -5.5 else "FAIL"
        elif key == "Lipinski":
            status = "PASS" if val >= 4 else "WARN" if val >= 3 else "FAIL"
        elif key in ("CYP2C9_Veith","CYP2C19_Veith","CYP3A4_Veith","Pgp_Broccatelli"):
            status = "PASS" if val < 0.4 else "WARN" if val < 0.7 else "FAIL"
        elif key == "PPBR_AZ":
            status = "PASS" if val < 85 else "WARN" if val < 95 else "FAIL"
        else:
            status = "PASS"

        color = GRN if status=="PASS" else YLW if status=="WARN" else RED
        flags[status].append(label)

        val_str = f"{val:.3f}" if isinstance(val,float) else str(val)
        print(f"  {label:<26} {val_str:>8}  "
              f"{color}{status:<10}{RST} {note}")

        report[key] = val

    # SA Score
    if sa:
        sa_status = "PASS" if sa < 3 else "WARN" if sa < 5 else "FAIL"
        sa_color  = GRN if sa_status=="PASS" else YLW if sa_status=="WARN" else RED
        print(f"  {'Synthetic Accessibility':<26} {sa:>8.1f}  "
              f"{sa_color}{sa_status:<10}{RST} <3 easy synth")
        flags[sa_status].append("Synthetic Accessibility")

    # Summary
    print(f"\n{BLD}Summary:{RST}")
    print(f"  {GRN}✓ PASS{RST}: {len(flags['PASS'])} properties")
    print(f"  {YLW}⚠ WARN{RST}: {len(flags['WARN'])} — {', '.join(flags['WARN'][:3])}")
    print(f"  {RED}✗ FAIL{RST}: {len(flags['FAIL'])} — {', '.join(flags['FAIL'][:3])}")

    # Overall score
    total = len(flags['PASS']) + len(flags['WARN']) + len(flags['FAIL'])
    score = (len(flags['PASS'])*1.0 + len(flags['WARN'])*0.5) / total * 100
    print(f"\n  {BLD}ADMET Score: {score:.0f}/100{RST} "
          f"{'★★★' if score>80 else '★★' if score>60 else '★'}")

    report["admet_score"]  = round(score, 1)
    report["pass_count"]   = len(flags["PASS"])
    report["warn_count"]   = len(flags["WARN"])
    report["fail_count"]   = len(flags["FAIL"])
    report["admet_flags"]  = flags

    return report

def update_library_admet(db_path: str = "fragment_library.db",
                          limit: int = 50) -> int:
    """Batch update top library compounds with real ADMET scores."""
    import contextlib, io
    print(f"\n{BLD}{CYN}Batch ADMET Update — Top {limit} compounds{RST}")

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, smiles FROM compounds "
        "WHERE dock_affinity < -7.0 "
        "AND (hERG IS NULL OR hERG = 0.0) "
        "ORDER BY dock_affinity ASC LIMIT ?",
        (limit,)).fetchall()
    conn.close()

    if not rows:
        print("No compounds need ADMET update")
        return 0

    print(f"Profiling {len(rows)} compounds...")

    try:
        with contextlib.redirect_stderr(io.StringIO()):
            from admet_ai import ADMETModel
            model = ADMETModel()
    except Exception as e:
        print(f"{RED}ADMET-AI not available: {e}{RST}")
        return 0

    n_updated = 0
    conn = sqlite3.connect(db_path)

    for cid, smiles in rows:
        try:
            results = model.predict(smiles=smiles)
            if not results: continue

            sa = get_sa_score(smiles)

            conn.execute("""
                UPDATE compounds SET
                    hERG = ?,
                    DILI = ?,
                    notes = COALESCE(notes,'') ||
                        ' [ADMET: QED=' || ? ||
                        ' Bio=' || ? ||
                        ' SA=' || ? || ']'
                WHERE id = ?
            """, (
                round(results.get('hERG', 0), 4),
                round(results.get('DILI', 0), 4),
                round(results.get('QED', 0), 3),
                round(results.get('Bioavailability_Ma', 0), 3),
                sa or 0,
                cid
            ))
            n_updated += 1

            if n_updated % 10 == 0:
                conn.commit()
                print(f"  Updated {n_updated}/{len(rows)}...")

        except Exception as e:
            pass

    conn.commit()
    conn.close()
    print(f"{GRN}✓ Updated {n_updated} compounds with real ADMET scores{RST}")
    return n_updated

def run_selectivity_panel(smiles: str, compound_id: str,
                           targets: list = None) -> dict:
    """
    Test a compound against multiple targets to check selectivity.
    Returns affinity at each target.
    """
    if targets is None:
        targets = ["HIV_INTEGRASE", "EGFR", "THROMBIN", "BACE1", "COVID_MPRO"]

    print(f"\n{BLD}{CYN}Selectivity Panel: {compound_id}{RST}")
    print(f"Testing against {len(targets)} targets...")

    RECEPTOR_CONFIGS = {
        "HIV_INTEGRASE": ("hiv_integrase.pdbqt", [-38.5,30.5,-20.8], [25,25,25], -9.43, "Dolutegravir"),
        "EGFR":          ("egfr.pdbqt",          [-3.0,52.0,13.0],  [25,25,25], -8.0,  "Erlotinib"),
        "THROMBIN":      ("thrombin.pdbqt",       [15.0,26.0,-7.0],  [25,25,25], -9.8,  "Dabigatran"),
        "BACE1":         ("bace1.pdbqt",          [5.0,17.0,25.0],   [25,25,25], -8.5,  "Verubecestat"),
        "COVID_MPRO":    ("covid_mpro.pdbqt",     [-11.3,13.5,59.0], [25,25,25], -7.8,  "Nirmatrelvir"),
    }

    results = {}
    for target in targets:
        cfg = RECEPTOR_CONFIGS.get(target)
        if not cfg:
            print(f"  {YLW}No config for {target}{RST}")
            continue
        receptor, center, box, ref_aff, ref_drug = cfg
        if not os.path.isfile(receptor):
            print(f"  {YLW}Receptor missing: {receptor}{RST}")
            continue

        print(f"  Docking against {target}...")
        # Use validate_leads subprocess
        import subprocess
        py = '.venv/Scripts/python.exe' if os.path.isfile('.venv/Scripts/python.exe') else sys.executable
        r = subprocess.run(
            [py, 'validate_leads.py', '--smiles', smiles,
             '--name', compound_id, '--target', target,
             '--exhaustiveness', '8'],
            capture_output=True, text=True, timeout=300,
            env=dict(os.environ, PYTHONIOENCODING='utf-8'))

        # Parse affinity from output
        aff = None
        for line in r.stdout.splitlines():
            if 'Vina=' in line:
                try:
                    aff = float(line.split('Vina=')[1].split()[0])
                except: pass

        if aff:
            vs_ref = aff - ref_aff
            selective = aff <= ref_aff
            color = GRN if selective else YLW
            print(f"  {color}{target:<20} {aff:>8.3f}  "
                  f"(ref: {ref_drug} {ref_aff})  "
                  f"{'★ BEATS REF' if selective else ''}{RST}")
            results[target] = {
                "affinity": aff, "ref_affinity": ref_aff,
                "ref_drug": ref_drug, "beats_ref": selective,
                "selectivity_ratio": ref_aff / aff if aff != 0 else 0
            }

    # Print selectivity index
    if results:
        primary = "HIV_INTEGRASE"
        if primary in results:
            primary_aff = results[primary]["affinity"]
            print(f"\n{BLD}Selectivity Index vs {primary}:{RST}")
            for tgt, data in results.items():
                if tgt == primary: continue
                ratio = data["affinity"] / primary_aff if primary_aff else 0
                print(f"  {tgt}: {ratio:.2f}x "
                      f"({'selective' if ratio > 1.5 else 'non-selective'})")

    return results

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem ADMET Profiler")
    parser.add_argument("--id",     help="Compound ID from library")
    parser.add_argument("--smiles", help="Direct SMILES input")
    parser.add_argument("--top",    type=int, default=5)
    parser.add_argument("--target", default="HIV_INTEGRASE")
    parser.add_argument("--selectivity", action="store_true",
                        help="Run selectivity panel")
    parser.add_argument("--update-library", action="store_true",
                        help="Batch update library with real ADMET")
    parser.add_argument("--db", default="fragment_library.db")
    args = parser.parse_args()

    if args.update_library:
        update_library_admet(args.db, limit=100)
        return

    # Get SMILES
    smiles = args.smiles
    cid    = args.id or "COMPOUND"

    if args.id and not smiles:
        conn = sqlite3.connect(args.db)
        row  = conn.execute(
            "SELECT smiles FROM compounds WHERE id=?",
            (args.id,)).fetchone()
        conn.close()
        if row: smiles = row[0]
        else: print(f"Compound {args.id} not found"); return

    if not smiles:
        # Use best validated compound
        smiles = "O=C(NCC(O)c1cc(F)cc(F)c1)c1cc(C(=O)Cc2ccccc2F)on1"
        cid    = "SEED_INT_RAL_G004"

    report = format_admet_report(smiles, cid)

    if args.selectivity:
        sel_results = run_selectivity_panel(smiles, cid)
        report["selectivity"] = sel_results

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = f"admet_report_{cid}_{ts}.json"
    with open(outfile, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n{GRN}Report saved → {outfile}{RST}")

if __name__ == "__main__":
    main()
