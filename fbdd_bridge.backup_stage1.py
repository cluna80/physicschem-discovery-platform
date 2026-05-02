"""
fbdd_bridge.py v2.0 — Hardened Digital Twin <-> PhysicsChem FBDD Bridge

Changes from v1.0:
    - Postgres-backed job queue; concurrent runs supported (up to MAX_CONCURRENT_JOBS)
    - Every job has a UUID; results isolated per-job (no more shared LIVE_LOG / DONE_FLAG)
    - Per-job log file and results CSV under ./jobs/{uuid}/
    - Proper subprocess tree termination via psutil (kills Vina children too)
    - Race-free result loading: results written BEFORE status flips to 'done'
    - PPI scan auto-launches as a TRACKED child job (parent_job_id linkage)
    - SSE stream with 30-min idle timeout, per-job file positioning
    - Diagnosis->target returns 400 on unknown (no dangerous defaults)
    - Disclaimer field on every response; explicit disclaimer_accepted required
    - CORS restricted to localhost dev origins only
    - Normalized CSV loading (absorbs agent's inconsistent column naming)

Localhost-only. No auth. Do not expose to public internet.

Install:
    pip install fastapi "uvicorn[standard]" "psycopg[binary,pool]" psutil pydantic

Postgres setup (one time):
    createdb fbdd_bridge
    psql fbdd_bridge < schema.sql
    export FBDD_DB_URL="postgresql://USER:PASS@localhost:5432/fbdd_bridge"

Run:
    cd /path/to/autonomous-drug-agent   (folder with autonomous_drug_agentV2.py)
    python fbdd_bridge.py

Patient data handling:
    Currently passed to the agent via environment variables. This is acceptable
    ONLY because you confirmed the patient/lab data is mocked. For real PHI,
    Stage 2 migrates to a per-job tempfile with mode 0600 and agent-side JSON
    ingestion. DO NOT use this bridge with identifiable patient data until
    that migration lands.
"""

from __future__ import annotations

import os
import sys
import csv
import json
import time
import uuid
import threading
import subprocess
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any
from contextlib import contextmanager

import psutil
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from fastapi import FastAPI, HTTPException, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field


# =====================================================================
# Configuration
# =====================================================================

DB_URL = os.environ.get(
    "FBDD_DB_URL",
    "postgresql://postgres:postgres@localhost:5432/fbdd_bridge",
)
JOBS_DIR = Path(os.environ.get("FBDD_JOBS_DIR", "./jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

SSE_IDLE_TIMEOUT_SEC = 30 * 60        # kill an SSE stream after 30 min of no log activity
SSE_POLL_INTERVAL_SEC = 0.5
MAX_CONCURRENT_JOBS = 4               # soft cap for single-box localhost

DISCLAIMER = (
    "Research use only. This system generates computational lead candidates "
    "based on in silico docking and predicted ADMET properties. Outputs have "
    "not been synthesized, validated in vitro or in vivo, or approved by any "
    "regulatory agency. No output should influence patient care decisions."
)


# =====================================================================
# Diagnosis -> target map (audit before adding entries)
# =====================================================================

DIAGNOSIS_TO_TARGET: dict[str, str] = {
    "hiv-1 chronic":        "HIV_INTEGRASE",
    "hiv-1 acute":          "HIV_INTEGRASE",
    "hiv":                  "HIV_INTEGRASE",
    "nsclc":                "EGFR",
    "lung cancer":          "EGFR",
    "type 2 diabetes":      "DPP4",
    "t2dm":                 "DPP4",
    "covid-19":             "COVID_MPRO",
    "sars-cov-2":           "COVID_MPRO",
    "alzheimer's":          "BACE1",
    "alzheimers":           "BACE1",
    "parkinson's":          "MAO_B",
    "inflammation":         "COX2",
    "rheumatoid arthritis": "JAK1",
    "thrombosis":           "THROMBIN",
    "atrial fibrillation":  "FACTOR_XA",
    # Removed from v1 because they were medically wrong:
    #   "Hypertension"    -> THROMBIN    (hypertension is not a thrombin disease)
    #   "None (Baseline)" -> HIV_INTEGRASE  (silent fallback to HIV discovery)
    # Unknown diagnoses now return HTTP 400 at the endpoint.
}

REFERENCE: dict[str, tuple[str, float]] = {
    "HIV_INTEGRASE": ("Dolutegravir",  -9.43),
    "HIV":           ("Darunavir",     -10.4),
    "EGFR":          ("Erlotinib",     -8.0),
    "T790M":         ("Osimertinib",   -7.5),
    "DPP4":          ("Sitagliptin",   -9.4),
    "COX2":          ("Celecoxib",     -9.1),
    "THROMBIN":      ("Dabigatran",    -9.8),
    "FACTOR_XA":     ("Rivaroxaban",   -9.5),
    "COVID_MPRO":    ("Nirmatrelvir",  -8.8),
    "BACE1":         ("Verubecestat",  -9.1),
    "JAK1":          ("Tofacitinib",   -8.7),
    "MAO_B":         ("Selegiline",    -8.3),
}


# =====================================================================
# Database (psycopg 3 + connection pool)
# =====================================================================

_pool: Optional[ConnectionPool] = None


def init_db_pool() -> None:
    global _pool
    _pool = ConnectionPool(
        conninfo=DB_URL,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )
    with _pool.connection() as conn:
        conn.execute("SELECT 1")


@contextmanager
def db():
    assert _pool is not None, "DB pool not initialized"
    with _pool.connection() as conn:
        yield conn


def create_job(
    *,
    job_type: str,
    parent_job_id: Optional[str],
    target: Optional[str],
    diagnosis: Optional[str],
    generation: int,
    params: dict,
    patient: Optional[dict],
    reference_drug: Optional[str],
    reference_affinity: Optional[float],
) -> str:
    jid = str(uuid.uuid4())
    job_dir = JOBS_DIR / jid
    job_dir.mkdir(parents=True, exist_ok=True)
    log_file = str(job_dir / "run.log")
    results_file = str(job_dir / "results.csv")
    with db() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, parent_job_id, job_type, status,
                target, diagnosis, generation, params, patient,
                reference_drug, reference_affinity,
                log_file, results_file, created_at
            )
            VALUES (
                %s, %s, %s, 'queued',
                %s, %s, %s, %s::jsonb, %s::jsonb,
                %s, %s,
                %s, %s, NOW()
            )
            """,
            (
                jid, parent_job_id, job_type,
                target, diagnosis, generation,
                json.dumps(params),
                json.dumps(patient) if patient is not None else None,
                reference_drug, reference_affinity,
                log_file, results_file,
            ),
        )
    return jid


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    cols: list[str] = []
    vals: list[Any] = []
    jsonb_keys = {"params", "patient", "best_candidate", "leaderboard"}
    for k, v in fields.items():
        if k in jsonb_keys:
            cols.append(f"{k} = %s::jsonb")
            vals.append(json.dumps(v) if v is not None else None)
        else:
            cols.append(f"{k} = %s")
            vals.append(v)
    vals.append(job_id)
    with db() as conn:
        conn.execute(
            f"UPDATE jobs SET {', '.join(cols)} WHERE id = %s",
            vals,
        )


def get_job(job_id: str) -> Optional[dict]:
    with db() as conn:
        cur = conn.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        return cur.fetchone()


def get_child_jobs(parent_job_id: str) -> list[dict]:
    with db() as conn:
        cur = conn.execute(
            "SELECT * FROM jobs WHERE parent_job_id = %s ORDER BY created_at",
            (parent_job_id,),
        )
        return cur.fetchall()


def list_recent_jobs(limit: int = 50) -> list[dict]:
    with db() as conn:
        cur = conn.execute(
            """
            SELECT id, job_type, status, target, diagnosis, generation,
                   created_at, started_at, completed_at
            FROM jobs
            WHERE parent_job_id IS NULL
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def count_running_jobs() -> int:
    with db() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs "
            "WHERE status IN ('queued', 'running') AND parent_job_id IS NULL"
        )
        return cur.fetchone()["c"]


# =====================================================================
# Process registry (for stop operations)
# =====================================================================

_proc_registry: dict[str, subprocess.Popen] = {}
_registry_lock = threading.Lock()


def register_proc(job_id: str, proc: subprocess.Popen) -> None:
    with _registry_lock:
        _proc_registry[job_id] = proc


def unregister_proc(job_id: str) -> None:
    with _registry_lock:
        _proc_registry.pop(job_id, None)


def get_proc(job_id: str) -> Optional[subprocess.Popen]:
    with _registry_lock:
        return _proc_registry.get(job_id)


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Terminate a process and every child it has spawned (Vina workers, etc.)."""
    try:
        parent = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return
    try:
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=5)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.terminate()
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            parent.kill()
        except psutil.NoSuchProcess:
            pass
    except Exception as e:
        print(f"[Bridge] kill_process_tree error: {e}")


# =====================================================================
# Python interpreter resolution
# =====================================================================

def get_python() -> str:
    win_venv = Path(".venv") / "Scripts" / "python.exe"
    nix_venv = Path(".venv") / "bin" / "python"
    if win_venv.is_file():
        return str(win_venv)
    if nix_venv.is_file():
        return str(nix_venv)
    return sys.executable


# =====================================================================
# CSV loading (normalizes agent's inconsistent columns)
# =====================================================================

def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def load_results_csv(csv_path: str) -> list[dict]:
    """
    Load the agent's canonical CSV schema (see CANONICAL_CSV_COLUMNS in
    autonomous_drug_agentV2.py). Does NOT probe for alternate column
    names — the agent is responsible for writing the schema correctly.
    If the file is missing or malformed, returns [].

    Back-compat shim: if we see a row that clearly came from the
    pre-Stage-2 agent (uppercase "MW", no sigma_label column), we
    read those legacy keys so old CSVs still load during migration.
    """
    if not csv_path or not os.path.isfile(csv_path):
        return []
    rows: list[dict] = []
    try:
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = dict(raw)

                # Canonical numeric fields — simple reads.
                # Back-compat fallbacks marked explicitly.
                row["dock_affinity"] = _safe_float(row.get("dock_affinity"))
                row["confidence"]    = _safe_int(row.get("confidence"))

                row["mw"]   = _safe_float(row.get("mw") or row.get("MW"))
                row["logp"] = _safe_float(row.get("logp") or row.get("LogP"))
                row["le"]   = _safe_float(row.get("le") or row.get("LE"))
                row["hac"]  = _safe_int(row.get("hac") or row.get("HAC"))

                row["hERG"] = _safe_float(row.get("hERG"), default=-1.0)
                row["DILI"] = _safe_float(row.get("DILI"), default=-1.0)
                row["AMES"] = _safe_float(row.get("AMES"), default=-1.0)

                # CYP surface
                row["cyp3a4_inh"]  = _safe_float(row.get("cyp3a4_inh"),  default=-1.0)
                row["cyp2d6_inh"]  = _safe_float(row.get("cyp2d6_inh"),  default=-1.0)
                row["cyp2c9_inh"]  = _safe_float(row.get("cyp2c9_inh"),  default=-1.0)
                row["cyp2c19_inh"] = _safe_float(row.get("cyp2c19_inh"), default=-1.0)
                row["cyp1a2_inh"]  = _safe_float(row.get("cyp1a2_inh"),  default=-1.0)
                row["cyp_safe"]    = _truthy(row.get("cyp_safe"))
                row["cyp_warning"] = str(row.get("cyp_warning", "") or "")

                # PK
                row["half_life"]     = _safe_float(row.get("half_life"))
                row["clearance_hep"] = _safe_float(row.get("clearance_hep"))

                # Higgs significance — canonical column is sigma_label.
                row["sigma_label"]  = str(
                    row.get("sigma_label") or "-"
                ).strip() or "-"
                row["z_score"]      = _safe_float(row.get("z_score"))
                row["is_discovery"] = _truthy(row.get("is_discovery"))
                row["is_evidence"]  = _truthy(row.get("is_evidence"))

                # Reasons: pipe-separated in the CSV
                reasons_raw = row.get("reasons", "") or ""
                row["reasons_list"] = [
                    r for r in str(reasons_raw).split("|") if r
                ]

                rows.append(row)
        rows.sort(key=lambda r: r["dock_affinity"])  # most negative first
    except Exception as e:
        print(f"[Bridge] CSV load error {csv_path}: {e}")
    return rows


def _find_legacy_csv(target: str) -> Optional[str]:
    """Fallback if the agent didn't write to AGENT_RESULTS_FILE."""
    cands = sorted(
        Path(".").glob(f"agent_results_{target}_*.csv"),
        key=os.path.getmtime,
    )
    return str(cands[-1]) if cands else None


def _find_ppi_json() -> Optional[str]:
    cands = sorted(Path(".").glob("ppi_results_*.json"), key=os.path.getmtime)
    return str(cands[-1]) if cands else None


def _admet_score(r: dict) -> int:
    score = 75
    if r["hERG"] >= 0:
        if r["hERG"] > 0.82:
            score -= 25
        elif r["hERG"] > 0.50:
            score -= 10
    if r["DILI"] >= 0:
        if r["DILI"] > 0.65:
            score -= 20
        elif r["DILI"] > 0.35:
            score -= 8
    return max(0, min(100, score))


def _reasoning(
    r: dict, target: str,
    ref_drug: Optional[str], ref_aff: Optional[float],
) -> str:
    aff = r["dock_affinity"]
    sigma = r["sigma_label"]
    delta = ""
    if ref_aff is not None and aff < ref_aff:
        delta = f", beats {ref_drug} by {abs(aff - ref_aff):.2f} kcal/mol"
    tag = " [5-sigma hit]" if r["is_discovery"] else ""
    return (
        f"{target} binder predicted at {aff:.2f} kcal/mol, significance {sigma}"
        f"{delta}{tag}. Computational lead candidate; requires synthesis and "
        f"experimental validation before any therapeutic use."
    )


# =====================================================================
# Pydantic request models
# =====================================================================

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
    diagnosis: str = Field(..., min_length=1)
    target: Optional[str] = None
    patient: Optional[PatientProfile] = None
    labData: Optional[LabData] = None
    frags: int = Field(20, ge=5, le=100)
    iters: int = Field(1, ge=1, le=5)
    exhaustiveness: int = Field(4, ge=1, le=32)
    generation: int = 1
    disclaimer_accepted: bool = False


# =====================================================================
# Target resolution & param adjustment
# =====================================================================

def resolve_target(diagnosis: str, override: Optional[str]) -> Optional[str]:
    if override:
        return override.upper().strip()
    dx = diagnosis.lower().strip()
    # longest-match first so "hiv-1 chronic" beats "hiv"
    for key in sorted(DIAGNOSIS_TO_TARGET.keys(), key=len, reverse=True):
        if key in dx:
            return DIAGNOSIS_TO_TARGET[key]
    return None


def adjust_params_for_severity(
    frags: int, exh: int, lab: Optional[LabData],
) -> tuple[int, int]:
    if lab is None:
        return frags, exh
    viral_load = 10 ** lab.viralLoadLog10
    if lab.cd4 < 200:
        frags, exh = 50, 16
    elif lab.cd4 < 350:
        frags, exh = 40, 12
    elif lab.cd4 < 500:
        frags, exh = 30, 10
    if viral_load > 100000:
        frags = min(frags + 10, 60)
    return frags, exh


def build_patient_env(
    target: str,
    diagnosis: str,
    patient: Optional[PatientProfile],
    lab: Optional[LabData],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Returns (env_vars_for_subprocess, adjustments_for_audit)."""
    env: dict[str, str] = {}
    adjustments: dict[str, Any] = {}

    if patient:
        env["PATIENT_NAME"]       = patient.name
        env["PATIENT_WEIGHT_KG"]  = str(patient.weight)
        env["PATIENT_HEIGHT_CM"]  = str(patient.height)
        env["PATIENT_BLOOD_TYPE"] = patient.bloodType
        env["PATIENT_BSA"]        = str(patient.bsa)
        env["PATIENT_EBV"]        = str(patient.ebv)

    if lab:
        viral_load = 10 ** lab.viralLoadLog10
        env["PATIENT_CD4"]        = str(lab.cd4)
        env["PATIENT_VIRAL_LOAD"] = f"{viral_load:.0f}"
        env["PATIENT_DIAGNOSIS"]  = diagnosis

        # Liver: elevated ALT/AST tightens DILI
        if lab.alt > 80 or lab.ast > 80:
            dili_t = max(0.15, 0.50 - (max(lab.alt, lab.ast) - 40) / 400)
        else:
            dili_t = 0.50
        env["PATIENT_DILI_THRESHOLD"] = f"{dili_t:.2f}"
        adjustments["dili_threshold"] = dili_t

        # Renal: elevated creatinine tightens hERG proxy
        if lab.creatinine > 1.5:
            herg_t = max(0.20, 0.50 - (lab.creatinine - 1.5) / 10)
        else:
            herg_t = 0.50
        env["PATIENT_HERG_THRESHOLD"] = f"{herg_t:.2f}"
        adjustments["herg_threshold"] = herg_t

        # CYP450 DDI: tighter if on an HIV regimen (INSTI / PI)
        if "hiv" in diagnosis.lower():
            env["PATIENT_CYP3A4_THRESH"] = "0.60"
            env["PATIENT_CYP2D6_THRESH"] = "0.65"
            adjustments["cyp_profile"] = "hiv_regimen_aware"
        else:
            env["PATIENT_CYP3A4_THRESH"] = "0.70"
            env["PATIENT_CYP2D6_THRESH"] = "0.70"
            adjustments["cyp_profile"] = "standard"
        env["PATIENT_CYP2C9_THRESH"]  = "0.70"
        env["PATIENT_CYP2C19_THRESH"] = "0.70"
        env["PATIENT_CYP1A2_THRESH"]  = "0.75"

    return env, adjustments


# =====================================================================
# Job execution (each runs in its own thread)
# =====================================================================

def run_fbdd_job(
    job_id: str,
    target: str,
    frags: int,
    iters: int,
    exh: int,
    patient_env: dict[str, str],
) -> None:
    """Main FBDD agent runner."""
    try:
        update_job(
            job_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        job = get_job(job_id)
        if job is None:
            return

        log_file = job["log_file"]
        results_file = job["results_file"]

        py = get_python()
        cmd = [
            py, "-u", "-W", "ignore",
            "autonomous_drug_agentV2.py",
            "--target", target,
            "--frags", str(frags),
            "--iterations", str(iters),
            "--exhaustiveness", str(exh),
        ]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # Stage 2: agent now honors these env vars and writes directly
        # to per-job paths. Legacy filename fallback still works if the
        # agent is an older version.
        env["AGENT_RESULTS_FILE"]     = results_file
        env["AGENT_LEADERBOARD_FILE"] = str(Path(results_file).with_name("leaderboard.json"))
        env.update(patient_env)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        register_proc(job_id, proc)
        update_job(job_id, pid=proc.pid)

        with open(log_file, "w", encoding="utf-8") as lf:
            for line in iter(proc.stdout.readline, ""):
                lf.write(line)
                lf.flush()

        proc.wait()

        effective_csv = (
            results_file if os.path.isfile(results_file)
            else (_find_legacy_csv(target) or "")
        )
        results = load_results_csv(effective_csv)
        ref_drug, ref_aff = REFERENCE.get(target, (None, None))

        best: Optional[dict] = None
        leaderboard: list[dict] = []
        if results:
            b = results[0]
            best = {
                # Identity + chemistry
                "id":               b.get("id", "?"),
                "smiles":           b.get("smiles", ""),
                "bindingAffinity":  b["dock_affinity"],
                "molecularWeight":  b["mw"],
                "ligandEfficiency": b["le"],
                "confidence":       b["confidence"],
                # Higgs
                "sigmaLabel":       b["sigma_label"],
                "zScore":           b["z_score"],
                "isDiscovery":      b["is_discovery"],
                "isEvidence":       b["is_evidence"],
                # ADMET core
                "admetScore":       _admet_score(b),
                "hERG":             b["hERG"] if b["hERG"] >= 0 else None,
                "DILI":             b["DILI"] if b["DILI"] >= 0 else None,
                "AMES":             b["AMES"] if b["AMES"] >= 0 else None,
                # CYP450 profile (Stage 2: now populated)
                "cyp3a4":           b["cyp3a4_inh"]  if b["cyp3a4_inh"]  >= 0 else None,
                "cyp2d6":           b["cyp2d6_inh"]  if b["cyp2d6_inh"]  >= 0 else None,
                "cyp2c9":           b["cyp2c9_inh"]  if b["cyp2c9_inh"]  >= 0 else None,
                "cyp2c19":          b["cyp2c19_inh"] if b["cyp2c19_inh"] >= 0 else None,
                "cyp1a2":           b["cyp1a2_inh"]  if b["cyp1a2_inh"]  >= 0 else None,
                "cypSafe":          b["cyp_safe"],
                "cypWarning":       b["cyp_warning"] or None,
                # PK
                "halfLife":         b["half_life"]     or None,
                "clearanceHep":     b["clearance_hep"] or None,
                # Provenance
                "reasons":          b.get("reasons_list", []),
                "reasoning":        _reasoning(b, target, ref_drug, ref_aff),
            }
            leaderboard = [
                {
                    "id":              r.get("id", "?"),
                    "smiles":          r.get("smiles", ""),
                    "bindingAffinity": r["dock_affinity"],
                    "confidence":      r["confidence"],
                    "sigmaLabel":      r["sigma_label"],
                    "isDiscovery":     r["is_discovery"],
                }
                for r in results[:10]
            ]

        # CRITICAL ORDER: results first, THEN status flip.
        # Frontend polling /results right when /status flips to 'done'
        # must always see the results populated.
        update_job(
            job_id,
            best_candidate=best,
            leaderboard=leaderboard,
        )
        update_job(
            job_id,
            status="done" if proc.returncode == 0 else "error",
            completed_at=datetime.now(timezone.utc),
            error_message=(
                None if proc.returncode == 0
                else f"Agent exited with code {proc.returncode}"
            ),
        )

        # Tracked PPI child job for HIV runs that completed successfully
        if (
            proc.returncode == 0
            and "HIV" in target.upper()
            and patient_env.get("PATIENT_CD4")
            and os.path.isfile("hiv_ppi_network.py")
        ):
            spawn_ppi_child_job(job_id, target, patient_env)

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Bridge] run_fbdd_job {job_id} fatal: {e}\n{tb}")
        update_job(
            job_id,
            status="error",
            completed_at=datetime.now(timezone.utc),
            error_message=f"{e}",
        )
    finally:
        unregister_proc(job_id)


def spawn_ppi_child_job(
    parent_job_id: str, target: str, patient_env: dict[str, str],
) -> str:
    child_id = create_job(
        job_type="ppi",
        parent_job_id=parent_job_id,
        target=target,
        diagnosis=patient_env.get("PATIENT_DIAGNOSIS", ""),
        generation=1,
        params={"driver": "hiv_ppi_network.py"},
        patient=None,
        reference_drug=None,
        reference_affinity=None,
    )
    t = threading.Thread(
        target=run_ppi_job,
        args=(child_id, patient_env),
        daemon=True,
        name=f"ppi-{child_id[:8]}",
    )
    t.start()
    return child_id


def run_ppi_job(job_id: str, patient_env: dict[str, str]) -> None:
    try:
        update_job(
            job_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        job = get_job(job_id)
        if job is None:
            return

        log_file = job["log_file"]
        results_file = job["results_file"]

        py = get_python()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PPI_RESULTS_FILE"] = results_file
        env.update(patient_env)

        proc = subprocess.Popen(
            [py, "-u", "hiv_ppi_network.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        register_proc(job_id, proc)
        update_job(job_id, pid=proc.pid)

        with open(log_file, "w", encoding="utf-8") as lf:
            for line in iter(proc.stdout.readline, ""):
                lf.write(line)
                lf.flush()

        proc.wait()

        leaderboard: list[dict] = []
        ppi_json = _find_ppi_json()
        if ppi_json and os.path.isfile(ppi_json):
            try:
                with open(ppi_json, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    leaderboard = data[:10]
            except Exception as e:
                print(f"[Bridge] PPI json parse error: {e}")

        update_job(job_id, leaderboard=leaderboard)
        update_job(
            job_id,
            status="done" if proc.returncode == 0 else "error",
            completed_at=datetime.now(timezone.utc),
            error_message=(
                None if proc.returncode == 0
                else f"PPI exited with code {proc.returncode}"
            ),
        )
    except Exception as e:
        print(f"[Bridge] run_ppi_job {job_id} fatal: {e}")
        update_job(
            job_id,
            status="error",
            completed_at=datetime.now(timezone.utc),
            error_message=f"{e}",
        )
    finally:
        unregister_proc(job_id)


# =====================================================================
# Helpers used by routes
# =====================================================================

def _read_log_tail(path: str, n: int) -> list[str]:
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [line.rstrip() for line in lines[-n:] if line.strip()]
    except Exception:
        return []


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# =====================================================================
# FastAPI
# =====================================================================

app = FastAPI(title="FBDD Bridge", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db_pool()
    masked = DB_URL.split("@")[-1] if "@" in DB_URL else DB_URL
    print(f"[Bridge v2.1] Ready. DB={masked}  Jobs={JOBS_DIR.resolve()}")


@app.on_event("shutdown")
def _shutdown() -> None:
    if _pool is not None:
        _pool.close()


@app.get("/health")
def health():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        return {
            "status": "ok",
            "bridge": "FBDD Bridge v2.1",
            "running_jobs": count_running_jobs(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "error": str(e)},
        )


@app.post("/jobs")
def create_fbdd_job(req: RunRequest):
    if not req.disclaimer_accepted:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "disclaimer_not_accepted",
                "message": DISCLAIMER,
                "hint": "Set disclaimer_accepted=true to proceed.",
            },
        )

    target = resolve_target(req.diagnosis, req.target)
    if target is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_diagnosis",
                "message": (
                    f"Diagnosis '{req.diagnosis}' does not map to a known "
                    "target. Provide an explicit 'target' override or a "
                    "recognized diagnosis."
                ),
                "supported_targets": sorted(set(DIAGNOSIS_TO_TARGET.values())),
            },
        )

    if count_running_jobs() >= MAX_CONCURRENT_JOBS:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "too_many_running_jobs",
                "max_concurrent": MAX_CONCURRENT_JOBS,
                "retry_after_seconds": 60,
            },
        )

    frags, exh = adjust_params_for_severity(
        req.frags, req.exhaustiveness, req.labData
    )
    patient_env, adjustments = build_patient_env(
        target, req.diagnosis, req.patient, req.labData
    )
    ref_drug, ref_aff = REFERENCE.get(target, (None, None))

    patient_audit: Optional[dict] = None
    if req.patient is not None or req.labData is not None:
        patient_audit = {
            "patient": req.patient.model_dump() if req.patient else None,
            "lab":     req.labData.model_dump() if req.labData else None,
            "adjustments": adjustments,
        }

    job_id = create_job(
        job_type="fbdd",
        parent_job_id=None,
        target=target,
        diagnosis=req.diagnosis,
        generation=req.generation,
        params={"frags": frags, "iters": req.iters, "exhaustiveness": exh},
        patient=patient_audit,
        reference_drug=ref_drug,
        reference_affinity=ref_aff,
    )

    threading.Thread(
        target=run_fbdd_job,
        args=(job_id, target, frags, req.iters, exh, patient_env),
        daemon=True,
        name=f"fbdd-{job_id[:8]}",
    ).start()

    return {
        "job_id": job_id,
        "status": "queued",
        "target": target,
        "diagnosis": req.diagnosis,
        "generation": req.generation,
        "params": {"frags": frags, "iters": req.iters, "exhaustiveness": exh},
        "reference_drug": ref_drug,
        "reference_affinity": ref_aff,
        "disclaimer": DISCLAIMER,
        "_links": {
            "status":  f"/jobs/{job_id}",
            "results": f"/jobs/{job_id}/results",
            "stream":  f"/jobs/{job_id}/stream",
            "stop":    f"/jobs/{job_id}",  # DELETE
        },
    }


@app.get("/jobs")
def list_jobs(limit: int = 50):
    n = min(max(limit, 1), 200)
    rows = list_recent_jobs(n)
    return {
        "jobs": [
            {
                "id":           r["id"],
                "job_type":     r["job_type"],
                "status":       r["status"],
                "target":       r["target"],
                "diagnosis":    r["diagnosis"],
                "generation":   r["generation"],
                "created_at":   _iso(r["created_at"]),
                "started_at":   _iso(r["started_at"]),
                "completed_at": _iso(r["completed_at"]),
            }
            for r in rows
        ],
        "disclaimer": DISCLAIMER,
    }


@app.get("/jobs/{job_id}")
def job_status(job_id: str = FPath(...)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    log_tail = _read_log_tail(job["log_file"], 20)
    children = [
        {
            "id":         c["id"],
            "job_type":   c["job_type"],
            "status":     c["status"],
            "started_at": _iso(c["started_at"]),
        }
        for c in get_child_jobs(job_id)
    ]
    return {
        "job_id":             job["id"],
        "parent_job_id":      job["parent_job_id"],
        "job_type":           job["job_type"],
        "status":             job["status"],
        "target":             job["target"],
        "diagnosis":          job["diagnosis"],
        "generation":         job["generation"],
        "params":             job["params"],
        "reference_drug":     job["reference_drug"],
        "reference_affinity": job["reference_affinity"],
        "error":              job["error_message"],
        "log_tail":           log_tail,
        "children":           children,
        "created_at":         _iso(job["created_at"]),
        "started_at":         _iso(job["started_at"]),
        "completed_at":       _iso(job["completed_at"]),
        "disclaimer":         DISCLAIMER,
    }


@app.get("/jobs/{job_id}/results")
def job_results(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("done", "error"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "job_not_complete",
                "status": job["status"],
                "hint": f"Poll /jobs/{job_id} until status is 'done'.",
            },
        )
    children = get_child_jobs(job_id)
    child_payload = [
        {
            "id":          c["id"],
            "job_type":    c["job_type"],
            "status":      c["status"],
            "leaderboard": c["leaderboard"] or [],
        }
        for c in children
    ]
    return {
        "job_id":             job["id"],
        "status":             job["status"],
        "generation":         job["generation"],
        "target":             job["target"],
        "reference_drug":     job["reference_drug"],
        "reference_affinity": job["reference_affinity"],
        "best":               job["best_candidate"],
        "leaderboard":        job["leaderboard"] or [],
        "children":           child_payload,
        "error":              job["error_message"],
        "disclaimer":         DISCLAIMER,
    }


@app.delete("/jobs/{job_id}")
def stop_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("queued", "running"):
        return {
            "job_id": job_id,
            "status": job["status"],
            "action": "noop",
        }
    proc = get_proc(job_id)
    if proc is not None:
        kill_process_tree(proc)
    for c in get_child_jobs(job_id):
        if c["status"] in ("queued", "running"):
            cproc = get_proc(c["id"])
            if cproc is not None:
                kill_process_tree(cproc)
            update_job(
                c["id"],
                status="stopped",
                completed_at=datetime.now(timezone.utc),
            )
    update_job(
        job_id,
        status="stopped",
        completed_at=datetime.now(timezone.utc),
    )
    return {"job_id": job_id, "status": "stopped"}


@app.get("/jobs/{job_id}/stream")
def job_stream(job_id: str):
    """SSE stream of log lines for a specific job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    log_file = job["log_file"]

    def generate():
        last_pos = 0
        last_activity = time.time()
        yield _sse({"type": "hello", "job_id": job_id, "status": job["status"]})

        while True:
            current = get_job(job_id)
            if current is None:
                yield _sse({"type": "error", "message": "job_vanished"})
                return

            if os.path.isfile(log_file):
                try:
                    with open(log_file, encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        chunk = f.read()
                        last_pos = f.tell()
                    if chunk:
                        last_activity = time.time()
                        for line in chunk.splitlines():
                            if line.strip():
                                yield _sse({"type": "log", "line": line})
                except Exception:
                    pass

            if current["status"] in ("done", "error", "stopped"):
                yield _sse({
                    "type":   "done",
                    "status": current["status"],
                    "job_id": job_id,
                    "error":  current["error_message"],
                })
                return

            if time.time() - last_activity > SSE_IDLE_TIMEOUT_SEC:
                yield _sse({
                    "type":        "timeout",
                    "idle_seconds": SSE_IDLE_TIMEOUT_SEC,
                })
                return

            time.sleep(SSE_POLL_INTERVAL_SEC)

    return StreamingResponse(generate(), media_type="text/event-stream")


# =====================================================================
# Entry point
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  FBDD Bridge Server v2.1  -  Digital Twin Integration")
    print(f"  Jobs dir: {JOBS_DIR.resolve()}")
    masked = DB_URL.split("@")[-1] if "@" in DB_URL else DB_URL
    print(f"  DB:       {masked}")
    print("  Listening on http://127.0.0.1:8765")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")