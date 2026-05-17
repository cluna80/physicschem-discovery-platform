# 🧬 Mutant FBDD Agent - ML-Based Drug Discovery

## Overview

The **MutantFBDDAgent** is a parallel ML-based drug discovery pipeline that runs alongside the traditional Discovery Agent. Instead of physical docking simulations, it uses Large Language Models (LLMs) via Ollama to predict binding affinities directly from SMILES strings.

## Key Features

- **ML-Based Predictions**: Uses Ollama LLM to predict binding affinities without physical docking
- **Parallel Execution**: Runs independently from Discovery Agent - no interference
- **Fast**: Generates 50 predictions in minutes vs hours for physical docking
- **Comparison Ready**: Results saved in same CSV format for easy comparison
- **Separate Logging**: Independent log files for each pipeline

## Architecture

```
Discovery Agent (Physical)          Mutant FBDD Agent (ML)
├── Fragment Selection              ├── Fragment Selection (same library)
├── AutoDock Vina Docking          ├── LLM Affinity Prediction
├── Growing/Optimization           ├── Ranking by Predicted Affinity
├── ADMET Profiling                ├── Minimal ADMET (ML-predicted)
└── Results CSV                    └── Results CSV (MUTANT_FBDD_*)
```

## Setup

### 1. Install Ollama

**Windows:**
```powershell
winget install Ollama.Ollama
```

**Linux/Mac:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Pull a Model

```bash
ollama pull llama3.2
# or
ollama pull mistral
# or
ollama pull qwen2.5:7b
```

### 3. Start Ollama Server

```bash
ollama serve
```

## Usage

### Enable Mutant FBDD Agent

Set the environment variable:

**PowerShell:**
```powershell
$env:MUTANT_FBDD_ENABLED="1"
$env:OLLAMA_MODEL="llama3.2"
```

**Bash:**
```bash
export MUTANT_FBDD_ENABLED=1
export OLLAMA_MODEL=llama3.2
```

### Run Discovery Pipeline

```bash
python autonomous_drug_agentV2.py --target EGFR
```

**Output:**
- Discovery Agent runs normally → `agent_results_EGFR_*.csv`
- Mutant FBDD Agent runs in parallel → `agent_results_MUTANT_FBDD_EGFR_*.csv`
- Comparison printed at end showing top 10 from each pipeline

### Test Mutant FBDD Only

```bash
python test_mutant_fbdd.py
```

## How It Works

### 1. Fragment Selection
Uses the same 120-fragment library as Discovery Agent

### 2. LLM Affinity Prediction
For each fragment SMILES, queries Ollama:
```
"Given SMILES: {smiles}, predict the binding affinity in kcal/mol 
against {target} kinase. Respond with ONLY a number between -12 and 0."
```

### 3. Ranking
Sorts predictions by affinity (most negative = best binding)

### 4. Results
Saves to CSV with canonical schema:
- `id`: MUTANT_{fragment_id}
- `dock_affinity`: ML-predicted value
- `sigma_label`: "ML" (not Higgs-tested)
- `confidence`: 50% (ML predictions)
- `llm_insight`: Model name used

## Output Files

### CSV Results
```
agent_results_MUTANT_FBDD_EGFR_20260517_142530.csv
```

Columns match Discovery Agent schema for easy comparison:
- `id`, `smiles`, `name`, `parent`
- `dock_affinity` (ML-predicted)
- `sigma_label` = "ML"
- `confidence` = 50
- `target`, `timestamp`, `run_id`

### Log Files
```
agent_run_MUTANT_FBDD_EGFR_20260517_142530.log
```

All predictions logged under `[MutantFBDDAgent]` label.

## Comparison with Discovery Agent

| Feature | Discovery Agent | Mutant FBDD Agent |
|---------|----------------|-------------------|
| Method | Physical docking (Vina) | ML prediction (LLM) |
| Speed | ~3-5 min/compound | ~1-2 sec/compound |
| Accuracy | High (validated) | Experimental |
| ADMET | Full 41-endpoint profiling | Minimal |
| Sigma Testing | Yes (Higgs 5σ) | No (ML label) |
| Confidence | 0-100% (validated) | 50% (ML) |
| Use Case | Production | Rapid screening |

## Dashboard Integration

The dashboard automatically detects both result files:

1. **Discovery Tab**: Shows physical docking results
2. **Library Tab**: Can load either CSV for comparison
3. **Research Chat**: Can discuss both result sets

To compare in dashboard:
```bash
streamlit run dashboard.py
```

Navigate to Library tab and select:
- `agent_results_EGFR_*.csv` (Discovery)
- `agent_results_MUTANT_FBDD_EGFR_*.csv` (Mutant FBDD)

## Example Output

```
========================================================================
  📊 PIPELINE COMPARISON
========================================================================

  Discovery Agent (Physical Docking):
  ----------------------------------------------------------------------
      1. F002_G001           -9.43 kcal/mol
      2. F015_G003           -9.21 kcal/mol
      3. F007_G002           -8.95 kcal/mol
      ...

  Mutant FBDD Agent (ML Predictions):
  ----------------------------------------------------------------------
      1. MUTANT_F002         -9.12 kcal/mol
      2. MUTANT_F015         -8.87 kcal/mol
      3. MUTANT_F007         -8.65 kcal/mol
      ...

========================================================================
  ✅ Both pipelines complete
  📁 Compare results:
     - Discovery: agent_results_EGFR_20260517_142530.csv
     - Mutant FBDD: agent_results_MUTANT_FBDD_EGFR_20260517_142530.csv
========================================================================
```

## Troubleshooting

### "requests library not available"
```bash
pip install requests
```

### "Ollama not available" / Connection errors
1. Check Ollama is running: `ollama serve`
2. Verify model is pulled: `ollama list`
3. Test manually: `ollama run llama3.2 "test"`

### "Mutant FBDD Agent not enabled"
Ensure environment variable is set:
```bash
echo $MUTANT_FBDD_ENABLED  # Should print "1"
```

### Poor predictions
- Try different models: `qwen2.5:7b`, `mistral`, `llama3.1`
- Fine-tune model on drug discovery data
- Use specialized chemistry models if available

## Advanced Configuration

### Custom Model
```bash
export OLLAMA_MODEL="hf.co/username/custom-drug-model"
ollama pull hf.co/username/custom-drug-model
```

### Adjust Number of Predictions
Edit `MutantFBDDAgent.run()` in `autonomous_drug_agentV2.py`:
```python
selected_fragments = random.sample(FRAGMENT_LIBRARY, min(100, len(FRAGMENT_LIBRARY)))
```

### Change Prediction Prompt
Edit `MutantFBDDAgent.predict_affinity()`:
```python
prompt = f"Your custom prompt for {smiles} against {self.target_key}"
```

## Future Enhancements

- [ ] Fine-tuned Qwen model on ChEMBL docking data
- [ ] Ensemble predictions (multiple models)
- [ ] Uncertainty quantification
- [ ] Active learning loop
- [ ] Integration with AlphaFold structures

## Citation

If you use Mutant FBDD Agent in research:

```bibtex
@software{mutant_fbdd_2026,
  title={Mutant FBDD Agent: ML-Based Drug Discovery Pipeline},
  author={PhysicsChem Discovery Platform},
  year={2026},
  url={https://github.com/yourusername/physicschem}
}
```

## License

Same as main project (see LICENSE file).

## Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Email: support@physicschem.ai