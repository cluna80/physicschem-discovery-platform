# BioNav Architecture Documentation

## System Overview

BioNav is an autonomous fragment-based drug discovery (FBDD) platform that combines multi-agent AI orchestration with molecular docking, cheminformatics, and ADMET profiling to discover novel drug candidates.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BioNav Platform                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐              ┌──────────────────┐           │
│  │   Streamlit      │◄────────────►│  Autonomous      │           │
│  │   Dashboard      │   Subprocess │  Drug Agent v2   │           │
│  │  (dashboard.py)  │   + Logs     │  (2,015 lines)   │           │
│  └──────────────────┘              └──────────────────┘           │
│         │                                    │                     │
│         │ Real-time                          │ Orchestrates        │
│         │ Monitoring                         │ 5-Stage Pipeline    │
│         │                                    │                     │
│         ▼                                    ▼                     │
│  ┌──────────────────┐              ┌──────────────────┐           │
│  │  3D Molecular    │              │   Multi-Agent    │           │
│  │  Visualization   │              │   Coordination   │           │
│  │  (py3Dmol)       │              │   System         │           │
│  └──────────────────┘              └──────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Pipeline: 5-Stage Drug Discovery

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OrchestratorAgent                                │
│  (Coordinates 5-stage drug discovery pipeline)                      │
└─────────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Fragment    │    │   Docking    │    │   Growing    │
│  Selector    │───▶│    Agent     │───▶│    Agent     │
│              │    │              │    │              │
│ • 120 frags  │    │ • AutoDock   │    │ • R-group    │
│ • PAINS      │    │   Vina       │    │   enum       │
│   filter     │    │ • Meeko      │    │ • Redocking  │
└──────────────┘    └──────────────┘    └──────────────┘
                                                │
                        ┌───────────────────────┘
                        │
                        ▼
                ┌──────────────┐    ┌──────────────┐
                │    ADMET     │───▶│  Validator   │
                │    Agent     │    │    Agent     │
                │              │    │              │
                │ • ADMET-AI   │    │ • Higgs 5σ   │
                │ • 104 props  │    │ • Confidence │
                │ • Toxicity   │    │ • Selectivity│
                └──────────────┘    └──────────────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │   Results    │
                                    │   • CSV      │
                                    │   • JSON     │
                                    │   • Cert     │
                                    └──────────────┘
```

## Stage-by-Stage Flow

### Stage 1: Fragment Selection
```
FragmentSelectorAgent
├── Input: Target disease (e.g., EGFR, HIV, COVID-19)
├── Process:
│   ├── Load 120 drug-like fragments from built-in library
│   ├── Apply PAINS filter (remove toxic substructures)
│   └── Select top N fragments (default: 20)
└── Output: List of validated fragments with SMILES, MW, LogP
```

**Key Files:**
- `autonomous_drug_agentV2.py:216-364` - FRAGMENT_LIBRARY (120 fragments)
- `autonomous_drug_agentV2.py:897-945` - FragmentSelectorAgent.load()

**Critical Pattern:**
- Fragments are **hardcoded**, not loaded from database
- IDs follow semantic grouping: F001-F015 (hinge binders), F016-F030 (anilines), etc.

---

### Stage 2: Molecular Docking
```
DockingAgent
├── Input: Fragment SMILES + Receptor PDBQT
├── Process:
│   ├── Convert SMILES → 3D structure (RDKit)
│   ├── Generate PDBQT with Meeko (NOT obabel!)
│   ├── Run AutoDock Vina docking
│   └── Parse binding affinity + poses
└── Output: Docked fragments with affinity scores (kcal/mol)
```

**Key Files:**
- `vina_wrapper.py:6-287` - VinaDocker class
- `meeko_utils.py:11-156` - smiles_to_pdbqt_meeko()
- `autonomous_drug_agentV2.py:948-1071` - DockingAgent

**Critical Pattern:**
- **MUST use Meeko** for PDBQT generation (obabel causes "Mode 1 +10.000" errors)
- Vina binary location: `./bin/vina.exe` (resolved relative to script)
- Receptor paths are target-specific: `cancer_egfr_agent/egfr_receptor.pdbqt`

---

### Stage 3: Fragment Growing
```
GrowingAgent
├── Input: Top-scoring fragments from docking
├── Process:
│   ├── Enumerate R-group additions (RDKit)
│   ├── Generate 20-50 variants per fragment
│   ├── Redock all variants
│   └── Filter by affinity improvement
└── Output: Grown compounds with enhanced binding
```

**Key Files:**
- `autonomous_drug_agentV2.py:1074-1192` - GrowingAgent
- R-group library: Methyl, ethyl, propyl, hydroxyl, amino, etc.

**Critical Pattern:**
- Growing uses **RDKit ReplaceSubstructs** (not SMARTS-based)
- Each fragment generates 20-50 variants
- Only variants with improved affinity are kept

---

### Stage 4: ADMET Profiling
```
ADMETAgent
├── Input: Grown compounds
├── Process:
│   ├── Predict 104 ADMET properties (ADMET-AI)
│   ├── Focus on 23 critical properties:
│   │   ├── hERG (cardiotoxicity)
│   │   ├── DILI (liver toxicity)
│   │   ├── BBB (brain penetration)
│   │   ├── Solubility, CYP metabolism, etc.
│   └── Filter compounds failing critical thresholds
└── Output: ADMET-validated compounds
```

**Key Files:**
- `admet_profiler.py:1-441` - ADMET profiling system
- `admet_profiler.py:26` - ADMET_PANEL (23 critical properties)

**Critical Pattern:**
- ADMET-AI model instantiated **once at module level** (not per-call)
- SA Score has fallback calculation if RDKit contrib missing
- 23 critical properties out of 104 total

---

### Stage 5: Validation & Significance Testing
```
ValidatorAgent
├── Input: ADMET-validated compounds
├── Process:
│   ├── Higgs 5-sigma significance testing
│   │   ├── Fit null distribution from fragments
│   │   ├── Calculate Z-scores for each compound
│   │   └── Classify: 5σ (discovery), 3σ (evidence), <3σ (candidate)
│   ├── Multi-target selectivity check
│   └── Confidence scoring (0-100%)
└── Output: Ranked lead compounds with confidence scores
```

**Key Files:**
- `autonomous_drug_agentV2.py:381-505` - HiggsSignificanceTester
- `autonomous_drug_agentV2.py:1195-1398` - ValidatorAgent

**Critical Pattern:**
- Higgs testing runs **BEFORE** confidence validation (not after)
- Z-score contributes to confidence bonus (was broken in v1)
- 5-sigma = discovery, 3-sigma = evidence, <3-sigma = candidate

---

## Data Flow Diagram

```
┌─────────────┐
│   Target    │ (e.g., EGFR)
│  Selection  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  Fragment   │────▶│   Docking    │
│  Library    │     │   (Vina)     │
│  (120)      │     │              │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Growing    │
                    │  (R-groups)  │
                    │              │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │    ADMET     │
                    │  Profiling   │
                    │  (104 props) │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Validation  │
                    │  (Higgs 5σ)  │
                    │              │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Results    │
                    │   • CSV      │
                    │   • JSON     │
                    │   • Cert     │
                    └──────────────┘
```

## Dashboard Integration

### Communication Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      Dashboard Process                       │
│                     (dashboard.py)                           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ subprocess.Popen()
                         │ env["DASHBOARD_MODE"] = "1"
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    Agent Subprocess                          │
│              (autonomous_drug_agentV2.py)                    │
├──────────────────────────────────────────────────────────────┤
│  if os.environ.get("DASHBOARD_MODE"):                       │
│      logfile = "dashboard_live.log"  # Fixed for dashboard  │
│  else:                                                       │
│      logfile = f"agent_run_{run_id}.log"  # Timestamped     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         │ Writes to dashboard_live.log
                         │ (line-by-line, flushed)
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   Dashboard Monitoring                       │
│  • Reads dashboard_live.log in real-time                    │
│  • Displays progress in UI                                  │
│  • Checks for dashboard_done.flag                           │
└──────────────────────────────────────────────────────────────┘
```

**Key Integration Points:**
1. **Environment Variable:** `DASHBOARD_MODE=1` signals dashboard mode
2. **Log File:** `dashboard_live.log` (fixed) vs `agent_run_*.log` (timestamped)
3. **Done Flag:** `dashboard_done.flag` written on completion
4. **Subprocess:** `PYTHONUNBUFFERED=1` ensures immediate output

---

## File Structure

```
autonomous AI quantum lab agent/
├── autonomous_drug_agentV2.py    # Core multi-agent pipeline (2,015 lines)
├── dashboard.py                  # Streamlit UI (2,416 lines)
├── vina_wrapper.py               # AutoDock Vina integration (287 lines)
├── meeko_utils.py                # PDBQT generation (156 lines)
├── admet_profiler.py             # ADMET-AI profiling (441 lines)
├── stress_test.py                # Component test suite (custom framework)
├── test_fbdd_pipeline.py         # Integration tests (Bob-generated)
├── AGENTS.md                     # Non-obvious patterns (Bob-generated)
├── ARCHITECTURE.md               # This file (Bob-generated)
├── README.md                     # Hackathon submission
├── DEMO_SCRIPT.md                # 12-minute demo walkthrough
├── RESULTS_SUMMARY.md            # Discovery explanation (plain English)
├── .bob/                         # Bob mode-specific rules
│   ├── rules-code/AGENTS.md
│   ├── rules-advanced/AGENTS.md
│   ├── rules-ask/AGENTS.md
│   └── rules-plan/AGENTS.md
├── bob_sessions/                 # Bob interaction logs
├── cancer_egfr_agent/
│   └── egfr_receptor.pdbqt       # EGFR target structure
├── receptors/                    # Additional target receptors
├── docking_results/              # Docking output files
└── ... (400+ additional files)
```

---

## Technology Stack

### Core Technologies
- **Python 3.10+** - Primary language
- **AutoDock Vina 1.2.5** - Molecular docking engine
- **RDKit 2023.9.1** - Cheminformatics library
- **Meeko** - PDBQT generation (critical!)
- **ADMET-AI** - Toxicity/pharmacokinetics prediction
- **NumPy/Pandas** - Data processing
- **Streamlit 1.28+** - Dashboard UI

### Visualization
- **py3Dmol** - 3D molecular viewer
- **RDKit MolDraw2D** - 2D structure rendering
- **Matplotlib** - Plotting

### AI/ML
- **Custom Higgs 5-sigma testing** - Statistical significance
- **ADMET-AI neural networks** - Property prediction
- **IBM Bob** - Codebase analysis and documentation

---

## Critical Design Patterns

### 1. PDBQT Generation (MUST USE MEEKO)
```python
# ❌ WRONG - causes "Mode 1 +10.000" errors
subprocess.run(["obabel", "-ismi", "input.smi", "-opdbqt", "-O", "output.pdbqt"])

# ✅ CORRECT - proper format
from meeko_utils import smiles_to_pdbqt_meeko
pdbqt_string = smiles_to_pdbqt_meeko(smiles)
```

### 2. RDKit Stderr Suppression
```python
# Required because C-level warnings bypass Python logging
with _SilenceRDKit():
    mol = Chem.MolFromSmiles(smiles)
```

### 3. Dashboard Mode Detection
```python
# Agent checks environment variable
if os.environ.get("DASHBOARD_MODE"):
    logfile = "dashboard_live.log"
    write_done_flag = True
else:
    logfile = f"agent_run_{run_id}.log"
    write_done_flag = False
```

### 4. Canonical CSV Schema
```python
# Stage 2 change: One set of column names, no aliasing
CANONICAL_CSV_COLUMNS = [
    "id", "smiles", "name", "parent", "dock_affinity", "dock_poses",
    "MW", "LogP", "HBD", "HBA", "TPSA", "RotBonds", "AromaticRings",
    "hERG", "DILI", "BBB", "Solubility", "CYP3A4", "SA_Score",
    "z_score", "sigma_label", "sigma_status", "is_discovery", "is_evidence",
    "confidence", "reasons", "target", "reference_drug", "reference_affinity",
    "run_id", "timestamp"
]
```

---

## Performance Characteristics

### Typical Run Times (EGFR, 20 fragments, 3 iterations)
- **Fragment loading:** 1-2 seconds
- **PAINS filtering:** 1-2 seconds
- **Fragment docking:** 30-60 seconds (20 fragments × 2-3 sec each)
- **Growing:** 60-120 seconds (100 variants × 1-2 sec each)
- **ADMET profiling:** 10-20 seconds (batch prediction)
- **Validation:** 5-10 seconds (Higgs testing + confidence)
- **Total:** 3-5 minutes per iteration

### Scaling
- **Fragments:** Linear scaling (2-3 sec per fragment)
- **Iterations:** Linear scaling (3-5 min per iteration)
- **Exhaustiveness:** Exponential scaling (8 = 2x slower than 4)

---

## Error Handling

### Common Issues

1. **Receptor not found**
   - Triggers simulation mode (fake affinities)
   - Logs warning, continues execution

2. **Invalid SMILES**
   - Caught by RDKit validation
   - Compound skipped, logged

3. **Docking failure**
   - Retries with different random seed
   - Falls back to simulation if persistent

4. **ADMET prediction failure**
   - Uses default values
   - Logs warning, continues

---

## Testing Strategy

### Component Tests (`stress_test.py`)
```bash
python stress_test.py                    # Full suite
python stress_test.py --quick            # Skip slow tests
python stress_test.py --component rdkit  # Test specific component
```

### Integration Tests (`test_fbdd_pipeline.py`)
```bash
python test_fbdd_pipeline.py  # Bob-generated tests
```

### Test Coverage
- Fragment loading and PAINS filtering
- SMILES validation and canonicalization
- Docking workflow (end-to-end)
- ADMET profiling
- Higgs significance testing
- CSV export with canonical schema

---

## Deployment

### Local Development
```bash
# Install dependencies
pip install -r requirements_rocm.txt

# Run agent (CLI)
python autonomous_drug_agentV2.py --target EGFR

# Run dashboard
streamlit run dashboard.py
```

### Production Considerations
- **Receptor files:** Pre-generate PDBQT files for all targets
- **Vina binary:** Ensure `./bin/vina.exe` is accessible
- **ADMET-AI model:** ~500MB download on first run
- **Disk space:** ~1GB for results per 100 runs

---

## Future Enhancements

### Planned Features
1. **Multi-target optimization** - Simultaneous optimization for multiple targets
2. **Quantum chemistry integration** - DFT calculations for top candidates
3. **Active learning** - Iterative refinement based on experimental feedback
4. **Cloud deployment** - AWS/Azure batch processing
5. **Database integration** - PostgreSQL for results storage

### Research Directions
1. **Generative models** - VAE/GAN for novel fragment generation
2. **Reinforcement learning** - RL-guided fragment growing
3. **Physics-based scoring** - MM-GBSA rescoring
4. **Protein flexibility** - Ensemble docking with multiple conformations

---

**Document Version:** 1.0  
**Last Updated:** May 16, 2026  
**Generated by:** IBM Bob AI Assistant  
**Maintained by:** BioNav Team