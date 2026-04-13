"""
stress_test.py
==============
PhysicsChem Platform — Full End-to-End Stress Test

Tests every component of the platform in sequence,
simulating the complete new user workflow.

USAGE:
    python stress_test.py              # full test
    python stress_test.py --quick      # skip long docking tests
    python stress_test.py --component library
    python stress_test.py --component optimizer
    python stress_test.py --component validator
    python stress_test.py --component expander
    python stress_test.py --component agent
"""

import os, sys, json, csv, sqlite3, subprocess, time, argparse, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')

# ── Colors ────────────────────────────────────────────────────────────
GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

PASS = f"{GRN}{BLD}PASS{RST}"
FAIL = f"{RED}{BLD}FAIL{RST}"
SKIP = f"{YLW}{BLD}SKIP{RST}"
WARN = f"{YLW}{BLD}WARN{RST}"

results = []

def test(name, fn, skip_if=None):
    """Run a single test and record result."""
    if skip_if and skip_if():
        results.append((name, "SKIP", "-"))
        print(f"  {SKIP}  {name}")
        return None
    try:
        t0 = time.time()
        result = fn()
        elapsed = time.time() - t0
        status = "PASS" if result else "FAIL"
        icon   = PASS if result else FAIL
        results.append((name, status, f"{elapsed:.1f}s"))
        print(f"  {icon}  {name}  {CYN}({elapsed:.1f}s){RST}")
        return result
    except Exception as e:
        results.append((name, "FAIL", str(e)[:60]))
        print(f"  {FAIL}  {name}  {RED}{e}{RST}")
        return False

def section(title):
    print(f"\n{BLD}{CYN}{'─'*56}{RST}")
    print(f"{BLD}{CYN}  {title}{RST}")
    print(f"{BLD}{CYN}{'─'*56}{RST}")


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 1: IMPORTS & DEPENDENCIES
# ══════════════════════════════════════════════════════════════════════
def test_imports():
    section("1. DEPENDENCIES")

    test("Python >= 3.10",
         lambda: sys.version_info >= (3, 10))

    test("RDKit available",
         lambda: __import__('rdkit') is not None)

    test("Streamlit available",
         lambda: __import__('streamlit') is not None)

    test("Pandas available",
         lambda: __import__('pandas') is not None)

    test("Plotly available",
         lambda: __import__('plotly') is not None)

    test("Meeko available",
         lambda: __import__('meeko') is not None)

    test("ADMET-AI available",
         lambda: __import__('admet_ai') is not None)

    test("NumPy available",
         lambda: __import__('numpy') is not None)

    test("SQLite3 available",
         lambda: __import__('sqlite3') is not None)


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 2: FILES & RECEPTORS
# ══════════════════════════════════════════════════════════════════════
def test_files():
    section("2. PLATFORM FILES")

    required_files = [
        ("autonomous_drug_agentV2.py", "FBDD Agent"),
        ("dashboard.py",               "Streamlit Dashboard"),
        ("library_builder.py",         "Library Builder"),
        ("lead_optimizer.py",          "Lead Optimizer"),
        ("validate_leads.py",          "Vina Validator"),
        ("library_expander.py",        "Library Expander"),
        ("harvest_all.py",             "Universal Harvester"),
        ("higgs_whitepaper.py",        "Whitepaper Generator"),
        ("fragment_library.db",        "Library Database"),
    ]

    for fname, label in required_files:
        test(f"{label} ({fname})",
             lambda f=fname: os.path.isfile(f) and os.path.getsize(f) > 100)

    section("2b. RECEPTORS")

    receptors = [
        ("hiv_integrase.pdbqt",  "HIV Integrase (3L2T)"),
        ("hiv_protease.pdbqt",   "HIV Protease"),
        ("egfr.pdbqt",           "EGFR Kinase"),
        ("covid_mpro.pdbqt",     "COVID-19 Mpro"),
        ("bace1.pdbqt",          "BACE1 Alzheimer's"),
        ("thrombin.pdbqt",       "Thrombin"),
    ]

    for fname, label in receptors:
        test(f"Receptor: {label}",
             lambda f=fname: os.path.isfile(f) and os.path.getsize(f) > 10000)

    test("Vina executable",
         lambda: os.path.isfile("./bin/vina.exe") or
                 bool(__import__('shutil').which('vina')))


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 3: LIBRARY DATABASE
# ══════════════════════════════════════════════════════════════════════
def test_library():
    section("3. FRAGMENT LIBRARY DATABASE")

    def check_db_schema():
        conn = sqlite3.connect("fragment_library.db")
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        return 'compounds' in tables

    test("DB schema valid",
         check_db_schema,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))

    def check_lib_size():
        conn = sqlite3.connect("fragment_library.db")
        n = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
        conn.close()
        print(f"       Library size: {n:,} compounds")
        return n > 0

    test("Library has compounds", check_lib_size,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))

    def check_discoveries():
        conn = sqlite3.connect("fragment_library.db")
        n5   = conn.execute("SELECT COUNT(*) FROM compounds WHERE is_discovery=1").fetchone()[0]
        tgts = conn.execute("SELECT COUNT(DISTINCT target) FROM compounds").fetchone()[0]
        best = conn.execute("SELECT MIN(dock_affinity) FROM compounds").fetchone()[0]
        conn.close()
        print(f"       5σ discoveries: {n5:,} | Targets: {tgts} | Best: {best:.3f}")
        return n5 > 0

    test("5σ discoveries present", check_discoveries,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))

    def check_integrase():
        conn = sqlite3.connect("fragment_library.db")
        n = conn.execute(
            "SELECT COUNT(*) FROM compounds WHERE target='HIV_INTEGRASE'").fetchone()[0]
        best = conn.execute(
            "SELECT MIN(dock_affinity) FROM compounds WHERE target='HIV_INTEGRASE'").fetchone()[0]
        conn.close()
        print(f"       HIV_INTEGRASE: {n} compounds, best={best:.3f if best else 0}")
        return n > 0

    test("HIV Integrase in library", check_integrase,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))

    def check_validated():
        conn = sqlite3.connect("fragment_library.db")
        n = conn.execute(
            "SELECT COUNT(*) FROM compounds WHERE notes LIKE '%Vina-validated%'").fetchone()[0]
        conn.close()
        print(f"       Vina-validated: {n} compounds")
        return True  # warn not fail

    test("Validated compounds tracked", check_validated,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 4: SYNTAX CHECK ALL MODULES
# ══════════════════════════════════════════════════════════════════════
def test_syntax():
    section("4. SYNTAX CHECK ALL MODULES")
    import ast

    modules = [
        "autonomous_drug_agentV2.py",
        "dashboard.py",
        "library_builder.py",
        "lead_optimizer.py",
        "validate_leads.py",
        "library_expander.py",
        "harvest_all.py",
        "higgs_whitepaper.py",
    ]

    for mod in modules:
        def check(f=mod):
            with open(f, encoding='utf-8') as fh:
                src = fh.read()
            ast.parse(src)
            lines = src.count('\n')
            print(f"       {lines} lines")
            return True

        test(f"Syntax: {mod}",
             check,
             skip_if=lambda f=mod: not os.path.isfile(f))


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 5: RDKIT MOLECULAR OPERATIONS
# ══════════════════════════════════════════════════════════════════════
def test_rdkit():
    section("5. RDKIT MOLECULAR OPERATIONS")

    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem, Descriptors
    RDLogger.DisableLog('rdApp.*')

    # Test molecules - your validated leads
    test_smiles = [
        ("SEED_INT_RAL_G004", "O=C(NCC(O)c1cc(F)cc(F)c1)c1cc(C(=O)Cc2ccccc2F)on1"),
        ("F007_G013",         "COc1cc2ncnc(Nc3cccc(F)c3)c2cc1OCC1CCCO1"),
        ("naph_metaCF3",      "O=C(NCC(O)CNC(=O)C1COC2OCCC12)c1cccc2ccccc12"),
        ("HYB-005",           "Cc1cnc(C(=O)C(=O)O)cc1C(=O)Nc1ccc2cccnc2c1Cc1cc(F)cc(F)c1"),
    ]

    def check_smiles(smi):
        mol = Chem.MolFromSmiles(smi)
        if not mol: return False
        mw   = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        print(f"       MW={mw:.1f}, LogP={logp:.2f}")
        return True

    for name, smi in test_smiles:
        test(f"Parse & props: {name}",
             lambda s=smi: check_smiles(s))

    def check_3d():
        mol = Chem.MolFromSmiles("O=C(NCC(O)c1cc(F)cc(F)c1)c1cc(C(=O)Cc2ccccc2F)on1")
        mol = Chem.AddHs(mol)
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        return result == 0

    test("3D conformer generation", check_3d)

    def check_meeko():
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        mol = Chem.MolFromSmiles("c1ccccc1")
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        prep   = MoleculePreparation()
        setups = prep.prepare(mol)
        pdbqt, ok, err = PDBQTWriterLegacy.write_string(setups[0])
        return ok and len(pdbqt) > 10

    test("Meeko PDBQT preparation", check_meeko)


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 6: LEAD OPTIMIZER
# ══════════════════════════════════════════════════════════════════════
def test_optimizer():
    section("6. LEAD OPTIMIZER")

    def check_rgroup():
        sys.path.insert(0, '.')
        # Quick import test
        result = subprocess.run(
            [sys.executable, 'lead_optimizer.py', '--top', '1',
             '--strategy', 'rgroup', '--n', '5'],
            capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and 'Generated' in result.stdout

    test("R-group scan (1 compound, 5 analogs)", check_rgroup,
         skip_if=lambda: not os.path.isfile("lead_optimizer.py"))

    def check_bioisostere():
        result = subprocess.run(
            [sys.executable, 'lead_optimizer.py', '--top', '1',
             '--strategy', 'bioisostere', '--n', '5'],
            capture_output=True, text=True, timeout=30)
        return result.returncode == 0

    test("Bioisostere replacement", check_bioisostere,
         skip_if=lambda: not os.path.isfile("lead_optimizer.py"))

    def check_opt_csv():
        csvs = sorted(Path('.').glob('agent_results_OPT_*.csv'),
                      key=os.path.getmtime, reverse=True)
        if not csvs: return False
        with open(csvs[0]) as f:
            rows = list(csv.DictReader(f))
        print(f"       Latest OPT CSV: {len(rows)} analogs")
        return len(rows) > 0

    test("OPT CSV output exists", check_opt_csv)


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 7: VINA VALIDATOR
# ══════════════════════════════════════════════════════════════════════
def test_validator():
    section("7. VINA VALIDATOR")

    def check_vina_exists():
        return (os.path.isfile('./bin/vina.exe') or
                bool(__import__('shutil').which('vina')))

    test("Vina binary found", check_vina_exists)

    def check_validator_runs():
        result = subprocess.run(
            [sys.executable, 'validate_leads.py', '--help'],
            capture_output=True, text=True, timeout=10)
        return result.returncode == 0

    test("Validator --help runs",
         check_validator_runs,
         skip_if=lambda: not os.path.isfile("validate_leads.py"))

    def check_validation_results():
        csvs = sorted(Path('.').glob('validation_results_*.csv'),
                      key=os.path.getmtime, reverse=True)
        if not csvs: return False
        with open(csvs[0]) as f:
            rows = list(csv.DictReader(f))
        validated = [r for r in rows if r.get('validated','') == 'True']
        print(f"       Latest validation: {len(validated)}/{len(rows)} confirmed")
        if validated:
            affs = [float(r['vina_affinity']) for r in validated if r.get('vina_affinity')]
            if affs:
                print(f"       Best Vina: {min(affs):.3f} kcal/mol")
        return len(validated) > 0

    test("Previous validation results", check_validation_results)

    def check_beats_drug():
        conn = sqlite3.connect("fragment_library.db")
        n = conn.execute(
            "SELECT COUNT(*) FROM compounds "
            "WHERE notes LIKE '%BEATS Dolutegravir%' "
            "OR notes LIKE '%beats Dolutegravir%'"
        ).fetchone()[0]
        conn.close()
        print(f"       Compounds beating Dolutegravir: {n}")
        return True

    test("Dolutegravir-beating compounds tracked", check_beats_drug,
         skip_if=lambda: not os.path.isfile("fragment_library.db"))


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 8: LIBRARY EXPANDER
# ══════════════════════════════════════════════════════════════════════
def test_expander():
    section("8. LIBRARY EXPANDER")

    def check_combinatorial():
        result = subprocess.run(
            [sys.executable, 'library_expander.py',
             '--source', 'combinatorial', '--target', 'EGFR',
             '--n', '50', '--dry-run'],
            capture_output=True, text=True, timeout=60)
        return result.returncode == 0 and 'compounds' in result.stdout.lower()

    test("Combinatorial generator (50 mols, dry run)", check_combinatorial,
         skip_if=lambda: not os.path.isfile("library_expander.py"))

    def check_brics():
        result = subprocess.run(
            [sys.executable, 'library_expander.py',
             '--source', 'brics', '--dry-run'],
            capture_output=True, text=True, timeout=60)
        return result.returncode == 0

    test("BRICS expander (dry run)", check_brics,
         skip_if=lambda: not os.path.isfile("library_expander.py"))


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 9: WHITEPAPER GENERATOR
# ══════════════════════════════════════════════════════════════════════
def test_whitepaper():
    section("9. WHITEPAPER & EXPORTS")

    def check_whitepaper():
        result = subprocess.run(
            [sys.executable, 'higgs_whitepaper.py'],
            capture_output=True, text=True, timeout=30)
        return (result.returncode == 0 and
                os.path.isfile('higgs_whitepaper.html') and
                os.path.getsize('higgs_whitepaper.html') > 5000)

    test("Whitepaper HTML generation", check_whitepaper,
         skip_if=lambda: not os.path.isfile("higgs_whitepaper.py"))

    def check_library_csv():
        return (os.path.isfile('fragment_library.csv') and
                os.path.getsize('fragment_library.csv') > 1000)

    test("Library CSV export exists", check_library_csv)

    def check_library_sdf():
        return (os.path.isfile('fragment_library.sdf') and
                os.path.getsize('fragment_library.sdf') > 1000)

    test("Library SDF export exists", check_library_sdf)


# ══════════════════════════════════════════════════════════════════════
# COMPONENT 10: DASHBOARD SYNTAX & IMPORTS
# ══════════════════════════════════════════════════════════════════════
def test_dashboard():
    section("10. DASHBOARD")

    def check_syntax():
        import ast
        with open('dashboard.py', encoding='utf-8') as f:
            src = f.read()
        ast.parse(src)
        lines = src.count('\n')
        tabs  = src.count('with _tab_')
        print(f"       {lines} lines | {tabs} tabs")
        return tabs >= 4

    test("Dashboard syntax & tab count", check_syntax,
         skip_if=lambda: not os.path.isfile("dashboard.py"))

    def check_no_deprecated():
        with open('dashboard.py', encoding='utf-8') as f:
            src = f.read()
        ucw = src.count('use_container_width')
        scv = src.count('st.components.v1.html')
        if ucw > 0: print(f"       WARNING: {ucw}x use_container_width")
        if scv > 0: print(f"       WARNING: {scv}x st.components.v1.html")
        return ucw == 0 and scv == 0

    test("No deprecated Streamlit calls", check_no_deprecated,
         skip_if=lambda: not os.path.isfile("dashboard.py"))

    def check_hiv_integrase():
        with open('dashboard.py', encoding='utf-8') as f:
            src = f.read()
        return '"HIV_INTEGRASE"' in src and 'hiv_integrase.pdbqt' in src

    test("HIV_INTEGRASE in DISEASE_DB", check_hiv_integrase,
         skip_if=lambda: not os.path.isfile("dashboard.py"))

    def check_all_tabs():
        with open('dashboard.py', encoding='utf-8') as f:
            src = f.read()
        return all(t in src for t in [
            'Discovery Agent', 'Fragment Library',
            'Lead Optimizer', 'Hit Packages'])

    test("All 4 tabs present", check_all_tabs,
         skip_if=lambda: not os.path.isfile("dashboard.py"))

    def check_workflow_guide():
        with open('dashboard.py', encoding='utf-8') as f:
            src = f.read()
        return 'Getting Started' in src and 'Workflow Progress' in src

    test("Getting Started guide & progress tracker", check_workflow_guide,
         skip_if=lambda: not os.path.isfile("dashboard.py"))


# ══════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════
def print_summary():
    passed  = sum(1 for _,s,_ in results if s == "PASS")
    failed  = sum(1 for _,s,_ in results if s == "FAIL")
    skipped = sum(1 for _,s,_ in results if s == "SKIP")
    total   = len(results)

    print(f"\n{BLD}{'═'*56}{RST}")
    print(f"{BLD}  STRESS TEST SUMMARY{RST}")
    print(f"{'═'*56}")
    print(f"  {GRN}PASS{RST}  {passed:>3}/{total}")
    print(f"  {RED}FAIL{RST}  {failed:>3}/{total}")
    print(f"  {YLW}SKIP{RST}  {skipped:>3}/{total}")

    if failed > 0:
        print(f"\n{RED}Failed tests:{RST}")
        for name, status, detail in results:
            if status == "FAIL":
                print(f"  ✗ {name}")
                if detail and detail != "False":
                    print(f"    → {detail}")

    pct = passed / (total - skipped) * 100 if (total - skipped) > 0 else 0
    bar_len = 40
    filled  = int(bar_len * pct / 100)
    bar     = f"{GRN}{'█'*filled}{RST}{'░'*(bar_len-filled)}"
    print(f"\n  [{bar}] {pct:.0f}%")

    if pct >= 95:
        print(f"\n  {GRN}{BLD}★ Platform is production-ready{RST}")
    elif pct >= 80:
        print(f"\n  {YLW}{BLD}⚠ Platform is mostly ready — fix failing tests{RST}")
    else:
        print(f"\n  {RED}{BLD}✗ Platform needs attention before deployment{RST}")

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "timestamp": ts,
        "passed": passed, "failed": failed,
        "skipped": skipped, "total": total,
        "pct": round(pct,1),
        "tests": [{"name":n,"status":s,"detail":d} for n,s,d in results]
    }
    with open(f"stress_test_report_{ts}.json","w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → stress_test_report_{ts}.json")

    return failed == 0


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Platform Stress Test")
    parser.add_argument("--quick", action="store_true",
        help="Skip slow docking/agent tests")
    parser.add_argument("--component", default="all",
        choices=["all","imports","files","library","syntax",
                 "rdkit","optimizer","validator","expander",
                 "whitepaper","dashboard"],
        help="Test specific component only")
    args = parser.parse_args()

    print(f"\n{BLD}{CYN}PhysicsChem Platform — Full Stress Test{RST}")
    print(f"{CYN}Simulating complete new user workflow{RST}")
    print(f"{'═'*56}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Dir:  {os.getcwd()}")

    comp = args.component

    if comp in ("all","imports"):     test_imports()
    if comp in ("all","files"):       test_files()
    if comp in ("all","library"):     test_library()
    if comp in ("all","syntax"):      test_syntax()
    if comp in ("all","rdkit"):       test_rdkit()
    if comp in ("all","optimizer"):   test_optimizer()
    if comp in ("all","validator"):   test_validator()
    if comp in ("all","expander"):    test_expander()
    if comp in ("all","whitepaper"):  test_whitepaper()
    if comp in ("all","dashboard"):   test_dashboard()

    return print_summary()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
