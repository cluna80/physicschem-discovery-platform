# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project: QwenFBDD - AI Drug Discovery on AMD MI300X

Fragment-based drug discovery (FBDD) platform with Qwen2.5-7B fine-tuning on AMD GPUs using ROCm.

## Critical Non-Obvious Patterns

### PDBQT Generation - MUST Use Meeko
- **NEVER use Open Babel (`obabel`)** for SMILES→PDBQT conversion - causes "Mode 1 +10.000" errors
- **ALWAYS use [`meeko_utils.smiles_to_pdbqt_meeko()`](meeko_utils.py:11)** - proper format, no coordinate issues
- Meeko is the ONLY supported PDBQT generator in this codebase

### AutoDock Vina Paths
- Vina binary location: `./bin/vina.exe` (Windows) - hardcoded in [`vina_wrapper.py`](vina_wrapper.py:7)
- [`VinaDocker`](vina_wrapper.py:6) class resolves paths relative to script location, not CWD
- Receptor files stored in target-specific directories (e.g., `cancer_egfr_agent/egfr_receptor.pdbqt`)

### ROCm-Specific Environment Variables
- **MUST set** `PYTORCH_HIP_ALLREDUCE_BYPASS=1` for ROCm stability ([`finetune_qwen_rocm.py`](finetune_qwen_rocm.py:26))
- `TOKENIZERS_PARALLELISM=false` required to prevent deadlocks ([`finetune_qwen_rocm.py`](finetune_qwen_rocm.py:25))
- Training logs auto-created with timestamp: `training_YYYYMMDD_HHMMSS.log`

### Fragment Library Architecture
- Built-in 120-fragment library in [`autonomous_drug_agent.py`](autonomous_drug_agent.py:103) (F001-F120)
- Fragments categorized: hinge binders, anilines, linkers, piperidines, fluorinated, etc.
- **NOT** loaded from external database - hardcoded in source

### ADMET Profiling
- Uses ADMET-AI (104 properties) via [`admet_profiler.py`](admet_profiler.py:1)
- Key panel: 23 critical properties in [`ADMET_PANEL`](admet_profiler.py:26) dict
- SA Score fallback: estimates from molecular complexity if RDKit contrib unavailable

### Testing
- Main test suite: `python stress_test.py` (10 component tests)
- Use `--quick` flag to skip slow docking tests
- Use `--component <name>` to test specific modules
- No pytest/unittest - custom test framework with colored output

### Dataset Building
- [`build_fbdd_dataset.py`](build_fbdd_dataset.py:1) harvests docking results → instruction JSONL
- Target metadata in [`TARGET_INFO`](build_fbdd_dataset.py:36) dict with affinity thresholds
- Supports 8 targets: EGFR, HIV, HIV_INTEGRASE, HIV_DIP, BACE1, COVID_MPRO, THROMBIN, OPT

### Physics Engine Integration
- Optional [`enhanced_physics_engine.py`](autonomous_drug_agent.py:4) module
- Gracefully degrades if not available - check `PHYSICS_AVAILABLE` flag
- Imported at module level with try/except pattern

### RDKit Stderr Suppression
- Custom [`_SilenceRDKit`](autonomous_drug_agent.py:53) context manager redirects file descriptor 2
- Required because RDLogger alone doesn't suppress C-level kekulization warnings
- Use for production runs to avoid log pollution

## Commands

### Training on AMD MI300X
```bash
# Set HF token first
export HF_TOKEN=your_token_here

# Run training (2-4 hours, ~$4-8 on AMD Dev Cloud)
python finetune_qwen_rocm.py
```

### Drug Discovery
```bash
# Run autonomous agent
python autonomous_drug_agent.py --target EGFR
python autonomous_drug_agent.py --target HIV --receptor hiv_protease.pdbqt

# ADMET profiling
python admet_profiler.py --id COMPOUND_ID
python admet_profiler.py --smiles "CCOc1cc2ncnc..."
```

### Testing
```bash
python stress_test.py                    # Full test suite
python stress_test.py --quick            # Skip slow tests
python stress_test.py --component rdkit  # Test specific component
```

### Receptor Setup
```bash
python setup_receptors.py  # Downloads PDB files, converts to PDBQT
```

## Dependencies

Install via: `pip install -r requirements_rocm.txt`

Critical: RDKit, Meeko (NOT obabel), ADMET-AI, transformers, peft, accelerate