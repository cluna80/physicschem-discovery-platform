# Code Mode Rules (Non-Obvious Only)

## PDBQT Generation - Critical
- **NEVER use `obabel`** for SMILES→PDBQT - causes "Mode 1 +10.000" docking errors
- **ALWAYS use [`meeko_utils.smiles_to_pdbqt_meeko()`](../../meeko_utils.py:11)** instead
- This is a hard requirement discovered through debugging - obabel creates malformed coordinates

## Path Resolution
- [`VinaDocker`](../../vina_wrapper.py:6) resolves `./bin/vina.exe` relative to **script location**, not CWD
- Use `os.path.dirname(os.path.abspath(__file__))` pattern when adding new tools
- Receptor paths are target-specific: `cancer_egfr_agent/egfr_receptor.pdbqt`, not flat structure

## RDKit Stderr Suppression
- [`_SilenceRDKit`](../../autonomous_drug_agent.py:53) context manager redirects FD 2 (not just RDLogger)
- Required because C-level kekulization warnings bypass Python logging
- Use this pattern: `with _SilenceRDKit(): mol = Chem.MolFromSmiles(smiles)`

## Fragment Library
- 120 fragments hardcoded in [`autonomous_drug_agent.py`](../../autonomous_drug_agent.py:103) as tuples: `(id, smiles, name)`
- NOT loaded from database - modify source to add fragments
- IDs follow pattern: F001-F120 with semantic grouping (F001-F015 hinge binders, etc.)

## Physics Engine Integration
- [`enhanced_physics_engine.py`](../../autonomous_drug_agent.py:4) is optional - check `PHYSICS_AVAILABLE` flag
- Import with try/except at module level, not function level
- Graceful degradation pattern used throughout codebase

## ADMET Profiling
- [`ADMET_PANEL`](../../admet_profiler.py:26) dict defines 23 critical properties (not all 104)
- SA Score has fallback calculation from molecular complexity if RDKit contrib missing
- ADMET-AI model instantiated once at module level: `_ADMET_MODEL = ADMETModel()`

## Testing Pattern
- Custom test framework in [`stress_test.py`](../../stress_test.py:36) - NOT pytest
- Tests use `test(name, fn, skip_if=condition)` wrapper
- Colored output via ANSI codes: `GRN`, `RED`, `CYN`, `BLD`, `RST`