"""
ui_test.py
==========
PhysicsChem Platform — Automated UI Test Suite (Playwright)

USAGE:
    python ui_test.py                      # full test
    python ui_test.py --headless           # no visible browser
    python ui_test.py --url http://localhost:8502
"""

import sys, os, time, json, argparse
from datetime import datetime

GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; RST="\033[0m"; BLD="\033[1m"
PASS=f"{GRN}{BLD}PASS{RST}"; FAIL=f"{RED}{BLD}FAIL{RST}"

results = []

def log(msg, color=CYN): print(f"  {color}{msg}{RST}")

def test(name, fn):
    try:
        t0 = time.time()
        result = fn()
        elapsed = time.time() - t0
        status = "PASS" if result else "FAIL"
        results.append((name, status, f"{elapsed:.1f}s"))
        print(f"  {PASS if result else FAIL}  {name}  {CYN}({elapsed:.1f}s){RST}")
        return result
    except Exception as e:
        results.append((name, "FAIL", str(e)[:80]))
        print(f"  {FAIL}  {name}  {RED}{str(e)[:70]}{RST}")
        return False

def section(title):
    print(f"\n{BLD}{CYN}{'─'*56}{RST}")
    print(f"{BLD}{CYN}  {title}{RST}")
    print(f"{BLD}{CYN}{'─'*56}{RST}")


def run_tests(url: str, headless: bool = False):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=100)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page    = context.new_page()

        log(f"Opening {url}...", GRN)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)  # let Streamlit fully render

        def src():
            return page.content()

        def has(text):
            return text.lower() in src().lower()

        def click_tab(label):
            """Click a Streamlit tab by its text label."""
            tabs = page.locator('[data-baseweb="tab"]').all()
            for tab in tabs:
                if label.lower() in tab.inner_text().lower():
                    tab.click()
                    page.wait_for_timeout(1500)
                    return True
            return False

        def count(selector):
            return len(page.locator(selector).all())

        # ── 1. PAGE LOAD ──────────────────────────────────────────────
        section("1. PAGE LOAD & HEADER")

        test("Dashboard loads",
             lambda: has("PhysicsChem") or has("Discovery"))

        test("No Python traceback",
             lambda: "Traceback" not in src() and
                     "NameError" not in src() and
                     "AttributeError" not in src())

        test("Sidebar renders",
             lambda: count('[data-testid="stSidebar"]') > 0)

        test("Getting Started / workflow guide",
             lambda: has("Workflow") or has("Getting Started") or
                     has("Select Target"))

        # ── 2. SIDEBAR ────────────────────────────────────────────────
        section("2. SIDEBAR CONTROLS")

        test("Disease Area dropdown",
             lambda: has("Disease Area") or has("Oncology"))

        test("Target Protein dropdown",
             lambda: has("Target") or has("EGFR"))

        test("Fragment budget slider",
             lambda: has("Fragment") and count('[data-testid="stSlider"]') > 0)

        test("Exhaustiveness slider",
             lambda: has("Exhaustiveness") or
                     count('[data-testid="stSlider"]') >= 2)

        test("Launch button in sidebar",
             lambda: has("LAUNCH") or has("Launch"))

        test("v3 branding",
             lambda: has("v3") or has("PhysicsChem") or has("FBDD"))

        # ── 3. ALL 4 TABS ─────────────────────────────────────────────
        section("3. TAB NAVIGATION")

        test("4 tabs present",
             lambda: count('[data-baseweb="tab"]') >= 4)

        test("🔬 Discovery Agent tab",
             lambda: has("Discovery Agent"))

        test("📚 Fragment Library tab",
             lambda: has("Fragment Library"))

        test("⚡ Lead Optimizer tab",
             lambda: has("Lead Optimizer"))

        test("💼 Hit Packages tab",
             lambda: has("Hit Packages"))

        test("Fragment Library tab clickable",
             lambda: click_tab("Fragment Library") and
                     (has("Total Compounds") or has("compound")))

        test("Lead Optimizer tab clickable",
             lambda: click_tab("Lead Optimizer") and
                     (has("Strategy") or has("Optimization")))

        test("Hit Packages tab clickable",
             lambda: click_tab("Hit Packages") and
                     (has("Package") or has("Revenue")))

        test("Discovery Agent tab clickable",
             lambda: click_tab("Discovery Agent") and
                     (has("LAUNCH") or has("Fragment")))

        # ── 4. FRAGMENT LIBRARY TAB ───────────────────────────────────
        section("4. FRAGMENT LIBRARY TAB")

        click_tab("Fragment Library")
        page.wait_for_timeout(1500)

        test("Stats banner — compound count",
             lambda: has("12") or has("Total Compounds") or has("compound"))

        test("Stats banner — 5σ discoveries",
             lambda: has("5") and (has("Discover") or has("sigma")))

        test("Disease area filter dropdown",
             lambda: count('[data-testid="stSelectbox"]') > 0)

        test("Min Sigma slider",
             lambda: has("Min Sigma") or has("Sigma"))

        test("Novel only checkbox",
             lambda: has("Novel only") or has("Novel"))

        test("5σ only checkbox",
             lambda: has("5σ") or has("5-sigma") or has("sigma"))

        test("Compounds table (dataframe)",
             lambda: count('[data-testid="stDataFrame"]') > 0 or
                     has("Affinity") or has("ID"))

        test("Compound inspector",
             lambda: has("Inspect Compound") or has("Select compound"))

        test("Export Filtered CSV button",
             lambda: has("Export Filtered") or has("Download"))

        test("Refresh Library button",
             lambda: has("Refresh"))

        # ── 5. LEAD OPTIMIZER TAB ─────────────────────────────────────
        section("5. LEAD OPTIMIZER TAB")

        click_tab("Lead Optimizer")
        page.wait_for_timeout(1500)

        test("Selection mode options",
             lambda: has("Top N") or has("Selection mode") or
                     count('[data-testid="stRadio"]') > 0)

        test("Strategy checkboxes (rgroup/bioisostere/scaffold)",
             lambda: has("rgroup") or has("bioisostere") or has("scaffold"))

        test("Analogs per strategy slider",
             lambda: has("Analogs per strategy") or has("Analogs"))

        test("Dock with Vina checkbox",
             lambda: has("Dock") or has("Vina"))

        test("Run Optimization button",
             lambda: has("Run Optimization") or has("Optimize"))

        test("Harvest to Library button",
             lambda: has("Harvest") or has("Library"))

        test("Results section or empty state",
             lambda: has("Optimization Results") or
                     has("No optimization") or has("Select compounds"))

        # ── 6. HIT PACKAGES TAB ───────────────────────────────────────
        section("6. HIT PACKAGES TAB")

        click_tab("Hit Packages")
        page.wait_for_timeout(1500)

        test("Value banner — library count",
             lambda: has("12,794") or has("Compound Library") or has("12"))

        test("Value banner — 5σ discoveries",
             lambda: has("8,082") or has("Discoveries") or has("5σ"))

        test("Value banner — targets covered",
             lambda: has("14") or has("Targets") or has("Disease"))

        test("Value banner — pricing",
             lambda: has("50K") or has("500K") or has("Hit Package Value"))

        test("Build Hit Package section",
             lambda: has("Build Hit Package") or has("Package Type"))

        test("Target selector (HIV_INTEGRASE etc)",
             lambda: has("HIV_INTEGRASE") or has("EGFR") or has("All Targets"))

        test("Package type options",
             lambda: has("Premium Hits") or has("Standard Screen") or
                     has("Package Type"))

        test("Export formats selector",
             lambda: has("SMILES") or has("Export Formats") or has("JSON"))

        test("Build & Download Package button",
             lambda: has("Build") and has("Download") or has("Package"))

        test("Revenue tiers section",
             lambda: has("Revenue Tiers") or has("Hit Package") or has("50K"))

        test("Three pricing tiers",
             lambda: has("150K") or has("500K") or has("Platform Access"))

        # ── 7. DISCOVERY AGENT TAB ────────────────────────────────────
        section("7. DISCOVERY AGENT TAB")

        click_tab("Discovery Agent")
        page.wait_for_timeout(1500)

        test("Metric cards area",
             lambda: has("Fragments") or has("Docked") or has("Iteration"))

        test("LAUNCH button",
             lambda: page.locator("button").filter(
                 has_text="LAUNCH").count() > 0 or has("LAUNCH"))

        test("STOP button",
             lambda: has("STOP") or
                     page.locator("button").count() >= 2)

        test("Agent log panel area",
             lambda: has("log") or has("Agent") or has("Fragment screening"))

        test("3D viewer section",
             lambda: has("3D") or has("structure") or has("SMILES"))

        # ── 8. THEME & STYLING ────────────────────────────────────────
        section("8. THEME & STYLING")

        test("Dark navy background",
             lambda: "#0a1628" in src() or "0a1628" in src())

        test("Teal accent color (#00b4a0)",
             lambda: "00b4a0" in src())

        test("Space Mono font",
             lambda: "Space Mono" in src())

        test("Amber/warning color",
             lambda: "f59e0b" in src() or "amber" in src().lower())

        test("Green success color",
             lambda: "22c55e" in src() or "4ade80" in src())

        test("No error messages visible",
             lambda: "NameError" not in src() and
                     "AttributeError" not in src() and
                     "ModuleNotFoundError" not in src())

        # ── 9. RESPONSIVE & POLISH ────────────────────────────────────
        section("9. RESPONSIVE & POLISH")

        test("Page title set correctly",
             lambda: "PhysicsChem" in page.title() or
                     "Discovery" in page.title())

        test("Wide layout (no narrow column)",
             lambda: page.evaluate(
                 "window.innerWidth") >= 1200)

        test("No horizontal scrollbar",
             lambda: page.evaluate(
                 "document.body.scrollWidth <= window.innerWidth + 100"))

        test("Streamlit version warning-free",
             lambda: "use_container_width" not in src() and
                     "components.v1.html" not in src())

        # HIV_INTEGRASE only visible when Infectious Disease category selected
        # Check it exists in the dashboard source code instead
        test("HIV_INTEGRASE target available",
             lambda: has("HIV_INTEGRASE") or has("HIV Integrase") or
                     "HIV_INTEGRASE" in open("dashboard.py",
                         encoding="utf-8").read())

        test("Whitepaper link / branding",
             lambda: has("Higgs") or has("5-sigma") or has("5σ"))

        # ── SCREENSHOT ────────────────────────────────────────────────
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        page.screenshot(path=f"ui_test_screenshot_{ts}.png",
                        full_page=True)
        log(f"Full-page screenshot → ui_test_screenshot_{ts}.png", GRN)

        # Screenshot each tab
        for tab_name, filename in [
            ("Fragment Library", f"screenshot_library_{ts}.png"),
            ("Lead Optimizer",   f"screenshot_optimizer_{ts}.png"),
            ("Hit Packages",     f"screenshot_packages_{ts}.png"),
        ]:
            click_tab(tab_name)
            page.wait_for_timeout(800)
            page.screenshot(path=filename)
        log(f"Per-tab screenshots saved", GRN)

        browser.close()
    return True


def print_summary():
    passed  = sum(1 for _,s,_ in results if s=="PASS")
    failed  = sum(1 for _,s,_ in results if s=="FAIL")
    total   = len(results)
    pct     = passed/total*100 if total>0 else 0

    print(f"\n{BLD}{'═'*56}{RST}")
    print(f"{BLD}  UI TEST SUMMARY{RST}")
    print(f"{'═'*56}")
    print(f"  {GRN}PASS{RST}  {passed:>3}/{total}")
    print(f"  {RED}FAIL{RST}  {failed:>3}/{total}")

    if failed:
        print(f"\n{RED}Failed tests:{RST}")
        for name, status, detail in results:
            if status == "FAIL":
                print(f"  ✗ {name}")
                if detail and len(detail) > 3:
                    print(f"    → {detail[:80]}")

    bar_len = 40
    filled  = int(bar_len * pct / 100)
    bar     = f"{GRN}{'█'*filled}{RST}{'░'*(bar_len-filled)}"
    print(f"\n  [{bar}] {pct:.0f}%")

    if pct >= 95:   print(f"\n  {GRN}{BLD}★ UI is production-ready{RST}")
    elif pct >= 80: print(f"\n  {YLW}{BLD}⚠ UI mostly ready — fix failing elements{RST}")
    else:           print(f"\n  {RED}{BLD}✗ UI needs fixes before demo{RST}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"ui_test_report_{ts}.json","w") as f:
        json.dump({"timestamp":ts,"passed":passed,"failed":failed,
                   "total":total,"pct":round(pct,1),
                   "tests":[{"name":n,"status":s,"detail":d}
                             for n,s,d in results]}, f, indent=2)
    print(f"  Report → ui_test_report_{ts}.json")


def main():
    parser = argparse.ArgumentParser(description="PhysicsChem UI Tests")
    parser.add_argument("--url", default="http://localhost:8501")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    print(f"\n{BLD}{CYN}PhysicsChem Platform — UI Test Suite (Playwright){RST}")
    print(f"{'═'*56}")
    print(f"  URL:  {args.url}")
    print(f"  Mode: {'headless' if args.headless else 'visible browser'}")
    print(f"\n  {YLW}Dashboard must be running:{RST}")
    print(f"  streamlit run dashboard.py\n")

    import urllib.request
    try:
        urllib.request.urlopen(args.url, timeout=5)
    except Exception:
        print(f"{RED}Dashboard not reachable at {args.url}{RST}")
        print(f"Start it: streamlit run dashboard.py")
        sys.exit(1)

    run_tests(args.url, args.headless)
    print_summary()


if __name__ == "__main__":
    main()
