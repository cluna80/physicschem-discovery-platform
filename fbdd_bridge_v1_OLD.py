"""
fbdd_bridge.py — Digital Twin ↔ PhysicsChem FBDD Bridge Server
Run from your drug discovery directory (same folder as autonomous_drug_agentV2.py):

    cd C:/Users/krizz/OneDrive/Desktop/PhysicsChemDiscovery   (your FBDD folder)
    python fbdd_bridge.py

Listens on http://localhost:8765
"""

import os
import sys
import csv
import json
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="FBDD Bridge", version="1.0")

# Allow Digital Twin (localhost:3000) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://10.0.0.246:3000", "http://127.0.0.1:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Constants (same as dashboard.py) ─────────────────────────────────
LIVE_LOG  = "dashboard_live.log"
DONE_FLAG = "dashboard_done.flag"

# ── Diagnosis → FBDD Target mapping ──────────────────────────────────
DIAGNOSIS_TO_TARGET = {
    "HIV-1 Chronic":        "HIV_INTEGRASE",
    "HIV":                  "HIV_INTEGRASE",
    "None (Baseline)":      "HIV_INTEGRASE",    # fallback
    "Metabolic Syndrome":   "DPP4",
    "Type 2 Diabetes":      "DPP4",
    "Chronic Kidney Disease":"COX2",
    "Hypertension":         "THROMBIN",
    "NSCLC":                "EGFR",
    "Cancer":               "EGFR",
    "COVID":                "COVID_MPRO",
    "Alzheimer":            "BACE1",
}

# Reference affinities to beat (kcal/mol) — same as dashboard DISEASE_DB
REFERENCE_AFFINITY = {
    "HIV_INTEGRASE": -9.43,  # Dolutegravir
    "HIV":           -10.4,  # Darunavir
    "EGFR":          -8.0,   # Erlotinib
    "DPP4":          -9.4,   # Sitagliptin
    "COX2":          -9.1,   # Celecoxib
    "THROMBIN":      -9.8,   # Dabigatran
    "COVID_MPRO":    -8.8,   # Nirmatrelvir
    "BACE1":         -9.1,   # Verubecestat
}

# ── Request models ────────────────────────────────────────────────────
class LabData(BaseModel):
    wbc: float = 6.5
    cd4: float = 320
    creatinine: float = 1.4
    alt: float = 45
    ast: float = 40
    viralLoadLog10: float = 5.2
    immuneHealth: float = 320
    renalClearance: float = 1.4

class PatientProfile(BaseModel):
    name: str = ""
    height: float = 0
    weight: float = 0
    bloodType: str = ""
    bsa: float = 0
    ebv: float = 0

class RunRequest(BaseModel):
    diagnosis: str = "HIV-1 Chronic"
    target: Optional[str] = None
    patient: Optional[PatientProfile] = None
    labData: Optional[LabData] = None
    frags: int = 20
    iters: int = 1
    exhaustiveness: int = 4
    generation: int = 1

class StatusResponse(BaseModel):
    running: bool
    done: bool
    generation: int
    log_tail: list[str] = []

# ── Global run state ──────────────────────────────────────────────────
_state = {
    "running": False,
    "done": False,
    "proc": None,
    "generation": 0,
    "log_lines": [],
    "last_results": [],
}

# ── Helpers ───────────────────────────────────────────────────────────
def resolve_target(diagnosis: str, override: Optional[str]) -> str:
    if override:
        return override.upper()
    for key, tgt in DIAGNOSIS_TO_TARGET.items():
        if key.lower() in diagnosis.lower():
            return tgt
    return "HIV_INTEGRASE"

def load_latest_results() -> list[dict]:
    """Load top compounds from most recent agent_results_*.csv"""
    target_filter = _state.get("target", "")
    pattern = f"agent_results_{target_filter}_*.csv" if target_filter else "agent_results_*.csv"
    csvs = sorted(Path(".").glob(pattern), key=os.path.getmtime)
    if not csvs:
        return []
    rows = []
    try:
        with open(csvs[-1], encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                # dock_affinity
                try:
                    row["dock_affinity"] = float(row.get("dock_affinity", "0") or 0)
                except:
                    row["dock_affinity"] = 0
                # confidence
                try:
                    row["confidence"] = int(float(row.get("confidence", "0") or 0))
                except:
                    row["confidence"] = 0
                # mw — try multiple column names
                for mw_col in ["mw", "molecular_weight", "mol_weight", "MW"]:
                    val = row.get(mw_col)
                    if val:
                        try:
                            row["mw"] = float(val)
                            break
                        except:
                            pass
                else:
                    row["mw"] = 0.0
                # sigma — try multiple column names
                for sig_col in ["sigma_label", "sigma_value", "sigma"]:
                    val = row.get(sig_col)
                    if val and str(val).strip():
                        row["sigma_label"] = str(val).strip()
                        break
                else:
                    row["sigma_label"] = "-"
                # is_discovery — derive from sigma_value if not present
                if "is_discovery" not in row or not row["is_discovery"]:
                    try:
                        sigma = float(row.get("sigma_value", 0) or 0)
                        row["is_discovery"] = "True" if sigma >= 5.0 else "False"
                    except:
                        row["is_discovery"] = "False"
                # is_novel
                row["is_novel"] = row.get("is_novel", "False")
                rows.append(row)
        rows.sort(key=lambda x: x["dock_affinity"])   # most negative = best
    except Exception as e:
        print(f"[Bridge] CSV load error: {e}")
    return rows

def get_python():
    """Use .venv if available, same as dashboard.py"""
    venv = r".venv\Scripts\python.exe"
    if os.path.isfile(venv):
        return venv
    return sys.executable

def run_agent_thread(target: str, frags: int, iters: int, exh: int, generation: int, patient_env: dict = {}):
    """Run autonomous_drug_agentV2.py — mirrors dashboard.py run_agent()"""
    _state["running"] = True
    _state["done"] = False
    _state["target"] = target
    _state["log_lines"] = []
    _state["generation"] = generation

    # Clean up previous run files
    for f in [LIVE_LOG, DONE_FLAG]:
        try:
            os.remove(f)
        except:
            pass

    _py = get_python()
    cmd = [
        _py, "-u", "-W", "ignore",
        "autonomous_drug_agentV2.py",
        "--target", target,
        "--frags",  str(frags),
        "--iterations", str(iters),
        "--exhaustiveness", str(exh),
    ]

    print(f"[Bridge] Gen {generation} — launching: {' '.join(cmd)}")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(patient_env)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        _state["proc"] = proc

        with open(LIVE_LOG, "w", encoding="utf-8") as lf:
            for line in iter(proc.stdout.readline, ""):
                lf.write(line)
                lf.flush()
                _state["log_lines"].append(line.rstrip())

        proc.wait()

    except Exception as e:
        print(f"[Bridge] Agent error: {e}")
        _state["log_lines"].append(f"[ERROR] {e}")
    finally:
        with open(DONE_FLAG, "w") as f:
            f.write("done")
        _state["running"] = False
        _state["done"] = True
        _state["last_results"] = load_latest_results()
        # Launch PPI network screen on top candidates
        cd4 = float(patient_env.get("PATIENT_CD4", "0"))
        vl  = float(patient_env.get("PATIENT_VIRAL_LOAD", "0"))
        if cd4 > 0 and "HIV" in target.upper():
            try:
                py = get_python()
                env2 = os.environ.copy()
                env2.update(patient_env)
                subprocess.Popen(
                    [py, "-u", "hiv_ppi_network.py"],
                    env=env2, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
                )
                print(f"[Bridge] PPI network screen launched for {target}")
            except Exception as e:
                print(f"[Bridge] PPI screen skipped: {e}")
        print(f"[Bridge] Gen {generation} done — {len(_state['last_results'])} candidates found")


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/ppi-results")
def get_ppi_results():
    """Return latest PPI network screen results."""
    import glob
    csvs = sorted(glob.glob("ppi_results_*.json"), key=os.path.getmtime)
    if not csvs:
        return {"results": [], "status": "no_ppi_data"}
    with open(csvs[-1], encoding="utf-8") as f:
        data = json.load(f)
    return {"results": data[:5], "status": "ok", "file": csvs[-1]}

@app.get("/health")
def health():
    return {"status": "ok", "bridge": "FBDD Bridge v1.0"}

@app.post("/run-fbdd")
def run_fbdd(req: RunRequest):
    """
    Launch one generation of drug discovery for the given patient/target.
    Returns immediately — poll /status or /results for output.
    """
    if _state["running"]:
        return JSONResponse(
            status_code=409,
            content={"error": "Agent already running — wait for completion"}
        )

    target = resolve_target(req.diagnosis, req.target)

    # Adjust parameters based on lab data severity
    frags = req.frags
    exh   = req.exhaustiveness
    patient_env = {}

    if req.labData:
        lab = req.labData
    if req.patient:
        p = req.patient
        print(f"[Bridge] Patient: {p.name} | {p.weight}kg {p.height}cm | Blood: {p.bloodType} | BSA: {p.bsa:.2f}m²")
        # Pass full patient profile to agent
        patient_env["PATIENT_NAME"]       = p.name
        patient_env["PATIENT_WEIGHT_KG"]  = str(p.weight)
        patient_env["PATIENT_HEIGHT_CM"]  = str(p.height)
        patient_env["PATIENT_BLOOD_TYPE"] = p.bloodType
        patient_env["PATIENT_BSA"]        = str(p.bsa)
        patient_env["PATIENT_EBV"]        = str(p.ebv)

    if req.labData:
        lab = req.labData
        print(f"[Bridge] Clinical data received: CD4={lab.cd4}, ALT={lab.alt}, AST={lab.ast}, Creatinine={lab.creatinine}, ViralLoad={lab.viralLoadLog10}")
        
        # Patient-specific screening intensity based on HIV disease stage
        viral_load = 10 ** lab.viralLoadLog10  # actual copies/mL
        
        if lab.cd4 < 200:
            # AIDS-defining: maximum intensity
            frags = 50; exh = 16
            print(f"[Bridge] AIDS stage (CD4<200) — maximum screening intensity")
        elif lab.cd4 < 350:
            # Advanced HIV: high intensity  
            frags = 40; exh = 12
            print(f"[Bridge] Advanced HIV (CD4<350) — high intensity screening")
        elif lab.cd4 < 500:
            # Moderate: standard+
            frags = 30; exh = 10
            print(f"[Bridge] Moderate HIV (CD4<500) — enhanced screening")
        else:
            frags = 25; exh = 8
            
        if viral_load > 100000:
            frags = min(frags + 10, 60)
            print(f"[Bridge] High viral load ({viral_load:.0f} copies/mL) — adding fragments")
            
        # Liver safety: ALT/AST drives DILI threshold
        if lab.alt > 80 or lab.ast > 80:
            dili_thresh = max(0.15, 0.50 - (max(lab.alt, lab.ast) - 40) / 400)
            patient_env["PATIENT_DILI_THRESHOLD"] = str(round(dili_thresh, 2))
            print(f"[Bridge] Elevated liver enzymes — DILI threshold tightened to {dili_thresh:.2f}")
        else:
            patient_env["PATIENT_DILI_THRESHOLD"] = "0.50"
            
        # Renal safety
        if lab.creatinine > 1.5:
            herg_thresh = max(0.20, 0.50 - (lab.creatinine - 1.5) / 10)
            patient_env["PATIENT_HERG_THRESHOLD"] = str(round(herg_thresh, 2))
            print(f"[Bridge] Elevated creatinine {lab.creatinine} — hERG threshold tightened to {herg_thresh:.2f}")
        else:
            patient_env["PATIENT_HERG_THRESHOLD"] = "0.50"
            
        # Pass patient context as env vars for agent logging
        patient_env["PATIENT_CD4"] = str(lab.cd4)
        patient_env["PATIENT_VIRAL_LOAD"] = str(viral_load)
        patient_env["PATIENT_DIAGNOSIS"] = req.diagnosis
        
        # CYP450 drug-drug interaction thresholds
        # HIV patients on INSTIs (dolutegravir/bictegravir) — CYP3A4 substrate
        # Protease inhibitors (ritonavir) — strong CYP3A4 inhibitor (boosting)
        # New compound must NOT strongly inhibit CYP3A4/2D6 to avoid DDI
        if "HIV" in req.diagnosis.upper():
            # Tight CYP3A4 threshold — patient likely on INSTI or PI-based regimen
            patient_env["PATIENT_CYP3A4_THRESH"] = "0.60"
            patient_env["PATIENT_CYP2D6_THRESH"] = "0.65"
            patient_env["PATIENT_CYP2C9_THRESH"]  = "0.70"
            patient_env["PATIENT_CYP2C19_THRESH"] = "0.70"
            patient_env["PATIENT_CYP1A2_THRESH"]  = "0.75"
            print(f"[Bridge] HIV patient: CYP3A4 DDI threshold set to 0.60 (INSTI co-medication protection)")
        else:
            patient_env["PATIENT_CYP3A4_THRESH"] = "0.70"
            patient_env["PATIENT_CYP2D6_THRESH"] = "0.70"
            patient_env["PATIENT_CYP2C9_THRESH"]  = "0.70"
            patient_env["PATIENT_CYP2C19_THRESH"] = "0.70"
            patient_env["PATIENT_CYP1A2_THRESH"]  = "0.75"
        # If renal clearance is poor, note it (future: pass as constraint to agent)
        if lab.creatinine > 1.5:
            print(f"[Bridge] Note: elevated creatinine {lab.creatinine} — prioritize renal-safe compounds")

    print(f"[Bridge] Starting Gen {req.generation}: target={target}, frags={frags}, iters={req.iters}, exh={exh}")
    dili = patient_env.get("PATIENT_DILI_THRESHOLD", "0.50 (default)")
    herg = patient_env.get("PATIENT_HERG_THRESHOLD", "0.50 (default)")
    print(f"[Bridge] Safety thresholds — DILI:{dili}  hERG:{herg}")

    thread = threading.Thread(
        target=run_agent_thread,
        args=(target, frags, req.iters, exh, req.generation, patient_env),
        daemon=True
    )
    thread.start()

    return {
        "status": "started",
        "target": target,
        "generation": req.generation,
        "frags": frags,
        "iters": req.iters,
        "exhaustiveness": exh,
        "reference_affinity": REFERENCE_AFFINITY.get(target, -9.0),
    }

@app.get("/status")
def get_status():
    """Poll this to check if agent has finished."""
    log_tail = _state["log_lines"][-20:] if _state["log_lines"] else []
    return {
        "running": _state["running"],
        "done": _state["done"],
        "generation": _state["generation"],
        "log_tail": log_tail,
    }

@app.get("/results")
def get_results():
    """Get top compound from last completed run."""
    results = _state["last_results"]

    if not results:
        # Try loading from disk in case server restarted
        results = load_latest_results()

    if not results:
        return JSONResponse(status_code=404, content={"error": "No results yet"})

    best = results[0]  # sorted by affinity — best is first

    return {
        "generation": _state["generation"],
        "total_candidates": len(results),
        "best": {
            "id":              best.get("id", "?"),
            "smiles":          best.get("smiles", ""),
            "bindingAffinity": best.get("dock_affinity", 0),
            "molecularWeight": best.get("mw") or best.get("molecular_weight") or best.get("MW") or 0,
            "confidence":      best.get("confidence", 0),
            "admetScore":      _admet_to_score(best),
            "sigmaLabel":      best.get("sigma_label") or best.get("sigma_value") or "-",
            "isDiscovery":     best.get("is_discovery", "False"),
            "hERG":            best.get("hERG") or best.get("herg") or None,
            "DILI":            best.get("DILI") or best.get("dili") or None,
            "ligandEfficiency":best.get("LE") or best.get("le") or best.get("ligand_efficiency") or None,
            "reasoning":       _make_reasoning(best),
        },
        "leaderboard": [
            {
                "id":              r.get("id", "?"),
                "smiles":          r.get("smiles", ""),
                "bindingAffinity": r.get("dock_affinity", 0),
                "confidence":      r.get("confidence", 0),
                "sigmaLabel":      r.get("sigma_label", "-"),
            }
            for r in results[:10]
        ]
    }

@app.post("/stop")
def stop_agent():
    """Stop a running agent."""
    proc = _state.get("proc")
    if proc and _state["running"]:
        try:
            proc.terminate()
        except:
            pass
        _state["running"] = False
        _state["done"] = True
        with open(DONE_FLAG, "w") as f:
            f.write("done")
        return {"status": "stopped"}
    return {"status": "not_running"}

@app.get("/log-stream")
def log_stream():
    """Server-sent events stream of live log output."""
    def generate():
        last_pos = 0
        while _state["running"] or not _state["done"]:
            if os.path.isfile(LIVE_LOG):
                try:
                    with open(LIVE_LOG, encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_text = f.read()
                        last_pos = f.tell()
                    if new_text:
                        for line in new_text.splitlines():
                            if line.strip():
                                yield f"data: {json.dumps({'line': line})}\n\n"
                except:
                    pass
            time.sleep(0.5)
        yield f"data: {json.dumps({'done': True, 'generation': _state['generation']})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Helpers ───────────────────────────────────────────────────────────
def _admet_to_score(row: dict) -> int:
    """Convert hERG + DILI into 0-100 ADMET score for Digital Twin display."""
    score = 75  # baseline
    try:
        herg = float(row.get("hERG") or 0)
        dili = float(row.get("DILI") or 0)
        if herg > 0.82: score -= 25
        elif herg > 0.50: score -= 10
        if dili > 0.65: score -= 20
        elif dili > 0.35: score -= 8
    except:
        pass
    return max(0, min(100, score))

def _make_reasoning(row: dict) -> str:
    """Generate a one-line reasoning string from result row."""
    aff   = row.get("dock_affinity", 0)
    sigma = row.get("sigma_label", "-")
    tgt   = row.get("target", "?")
    novel = "novel scaffold" if str(row.get("is_novel","")).lower() in ("true","1") else "known scaffold"
    disc  = "★ 5σ DISCOVERY" if str(row.get("is_discovery","")).lower() in ("true","1") else ""
    return f"{tgt} binder at {aff:.2f} kcal/mol ({sigma}) — {novel} {disc}".strip()


# ── Entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  FBDD Bridge Server — Digital Twin Integration")
    print("  Run this from your PhysicsChem drug discovery folder")
    print("  Listening on http://localhost:8765")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
