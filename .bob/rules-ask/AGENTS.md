# Ask Mode Documentation Rules (Non-Obvious Only)

## Project Structure Context

### Counterintuitive Organization
- Receptor files NOT in `receptors/` - stored in target-specific dirs like `cancer_egfr_agent/`
- Fragment library is hardcoded in [`autonomous_drug_agent.py`](../../autonomous_drug_agent.py:103), not external DB
- Training logs auto-named with timestamp, not configurable: `training_YYYYMMDD_HHMMSS.log`

### Hidden Dependencies
- Meeko is the ONLY supported PDBQT generator - obabel causes "Mode 1 +10.000" errors
- [`_SilenceRDKit`](../../autonomous_drug_agent.py:53) context manager required for C-level stderr suppression
- Physics engine is optional - code checks `PHYSICS_AVAILABLE` flag before use

### Dataset Architecture
- [`TARGET_INFO`](../../build_fbdd_dataset.py:36) dict contains affinity thresholds per target
- 8 supported targets: EGFR, HIV, HIV_INTEGRASE, HIV_DIP, BACE1, COVID_MPRO, THROMBIN, OPT
- Dataset builder harvests from docking results, not pre-existing data

### Testing Framework
- Custom test suite in [`stress_test.py`](../../stress_test.py:1) - NOT pytest/unittest
- 10 component tests: imports, files, library, syntax, rdkit, optimizer, validator, expander, whitepaper, dashboard
- Use `--quick` to skip slow docking tests, `--component <name>` for specific tests

### ADMET Profiling
- 23 critical properties in [`ADMET_PANEL`](../../admet_profiler.py:26) (subset of 104 total)
- SA Score has fallback calculation if RDKit contrib unavailable
- Model instantiated once at module level for performance

### ROCm Training
- **MUST set** `PYTORCH_HIP_ALLREDUCE_BYPASS=1` for stability
- `TOKENIZERS_PARALLELISM=false` prevents deadlocks
- Training cost: ~$4-8 for 2-4 hours on AMD Dev Cloud at $1.99/hr

### File Naming Patterns
- Agent results: `agent_results_<TARGET>_<TIMESTAMP>.csv`
- Agent leaderboards: `agent_leaderboard_<TARGET>_<TIMESTAMP>.json`
- Agent logs: `agent_run_<TARGET>_<TIMESTAMP>.log`
- ADMET reports: `admet_report_<COMPOUND_ID>_<TIMESTAMP>.json`