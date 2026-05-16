# BioNav — AI-Powered Drug Discovery with IBM Bob

**Hackathon Submission: IBM Bob AI Assistant Challenge**

![BioNav Dashboard](docs/screenshot_placeholder.png)

## 🧬 Problem Statement

Computational biology codebases are notoriously complex:
- **Multi-domain expertise required**: Molecular docking, quantum chemistry, ADMET profiling, statistical significance testing
- **Fragmented workflows**: Separate tools for fragment screening, growing, validation, and visualization
- **Integration challenges**: Connecting AutoDock Vina, RDKit, Meeko, and custom physics engines
- **Steep learning curve**: New researchers spend weeks understanding the pipeline before contributing

Traditional documentation falls short because it can't capture the **non-obvious patterns** that experienced developers discover through trial and error.

## 💡 Solution Overview

**BioNav** is an autonomous fragment-based drug discovery (FBDD) platform that combines:
1. **Multi-agent AI pipeline** (`autonomous_drug_agentV2.py`) - Orchestrates fragment selection, docking, growing, ADMET profiling, and validation
2. **Interactive Streamlit dashboard** (`dashboard.py`) - Real-time monitoring, 3D visualization, and results export
3. **IBM Bob integration** - Intelligent codebase analysis, architecture documentation, and automated testing

The platform discovers drug candidates for 18+ disease targets (EGFR, HIV, COVID-19, Alzheimer's) using:
- **AutoDock Vina** for molecular docking
- **RDKit** for cheminformatics
- **Higgs 5-sigma testing** for statistical significance (borrowed from particle physics)
- **ADMET-AI** for toxicity/pharmacokinetics prediction

## 🤖 How IBM Bob Was Used

### 1. **Codebase Architecture Analysis**
Bob analyzed 2000+ lines of Python code across multiple modules to create:
- **AGENTS.md**: Non-obvious patterns like "MUST use Meeko for PDBQT generation (NOT obabel)"
- **ARCHITECTURE.md**: Visual flow diagrams of the 5-stage FBDD pipeline
- **Mode-specific rules**: Separate guidance for coding, planning, and documentation tasks

**Key Discovery**: Bob identified that the dashboard and agent were designed for different architectures (synchronous vs async), preventing real-time log streaming.

### 2. **Integration Fix**
Bob diagnosed and fixed the broken dashboard ↔ agent integration:
- **Problem**: Dashboard expected `dashboard_live.log`, agent wrote to timestamped files
- **Solution**: Added `DASHBOARD_MODE` environment variable to switch log destinations
- **Impact**: Enabled real-time progress monitoring for hackathon demos

**Code Changes** (3 surgical edits):
```python
# autonomous_drug_agentV2.py - Dynamic log file selection
if os.environ.get("DASHBOARD_MODE"):
    logfile = "dashboard_live.log"
else:
    logfile = f"agent_run_{self.run_id}.log"

# dashboard.py - Set environment variable
env["DASHBOARD_MODE"] = "1"
```

### 3. **Test Generation**
Bob created `test_fbdd_pipeline.py` with:
- **Component tests**: Fragment loading, PAINS filtering, SMILES validation
- **Integration tests**: End-to-end docking workflow
- **Edge case coverage**: Invalid SMILES, missing receptors, empty results

### 4. **Documentation Automation**
Bob generated comprehensive documentation:
- **Non-obvious patterns**: "RDKit stderr suppression requires FD 2 redirection, not just RDLogger"
- **Critical gotchas**: "Receptor paths are target-specific (e.g., `cancer_egfr_agent/egfr_receptor.pdbqt`)"
- **Testing commands**: `python stress_test.py --component rdkit`

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements_rocm.txt
```

### Launch Dashboard
```bash
streamlit run dashboard.py
```

### Run Agent (CLI)
```bash
python autonomous_drug_agentV2.py --target EGFR --frags 20 --iterations 3
```

### Run Tests
```bash
python stress_test.py --quick  # Skip slow docking tests
python test_fbdd_pipeline.py   # Bob-generated integration tests
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Molecular Docking** | AutoDock Vina 1.2.5 |
| **Cheminformatics** | RDKit 2023.9.1 |
| **PDBQT Generation** | Meeko (NOT obabel - critical!) |
| **ADMET Profiling** | ADMET-AI (104 properties) |
| **Statistical Testing** | Custom Higgs 5-sigma implementation |
| **Dashboard** | Streamlit 1.28+ |
| **3D Visualization** | py3Dmol, RDKit MolDraw2D |
| **AI Assistant** | IBM Bob (codebase analysis, integration, testing) |
| **Language** | Python 3.10+ |

## 📊 Results

- **18 disease targets** supported (EGFR, HIV, COVID-19, BACE1, Thrombin, etc.)
- **120-fragment library** with drug-like properties
- **5-sigma significance testing** for discovery validation
- **Real-time dashboard** with live log streaming (thanks to Bob!)
- **Canonical CSV export** for downstream analysis

## 🎯 IBM Bob Impact

**Before Bob:**
- ❌ Dashboard couldn't stream agent logs in real-time
- ❌ No automated tests for integration points
- ❌ Critical patterns buried in 2000+ lines of code
- ❌ New contributors needed weeks to understand the pipeline

**After Bob:**
- ✅ Real-time log streaming for demos
- ✅ Comprehensive test suite with edge case coverage
- ✅ AGENTS.md captures non-obvious patterns (e.g., Meeko requirement)
- ✅ New contributors productive in hours, not weeks

## 📁 Project Structure

```
.
├── autonomous_drug_agentV2.py  # Core multi-agent pipeline
├── dashboard.py                # Streamlit UI with live monitoring
├── vina_wrapper.py             # AutoDock Vina integration
├── meeko_utils.py              # PDBQT generation (Meeko-based)
├── admet_profiler.py           # ADMET-AI toxicity prediction
├── test_fbdd_pipeline.py       # Bob-generated integration tests
├── stress_test.py              # Component test suite
├── AGENTS.md                   # Bob-generated codebase guide
├── ARCHITECTURE.md             # Bob-generated architecture docs
├── .bob/                       # Bob mode-specific rules
│   ├── rules-code/
│   ├── rules-advanced/
│   ├── rules-ask/
│   └── rules-plan/
└── bob_sessions/               # Bob interaction logs
```

## 🏆 Hackathon Highlights

1. **AI-Assisted Debugging**: Bob diagnosed the dashboard integration issue in minutes (would have taken hours manually)
2. **Automated Documentation**: AGENTS.md captures patterns that would be lost in Slack threads
3. **Test Generation**: Bob created integration tests covering edge cases we hadn't considered
4. **Knowledge Transfer**: New team members can use AGENTS.md to avoid common pitfalls

## 📸 Screenshots

![Dashboard Overview](docs/screenshot_placeholder.png)
*Real-time monitoring of drug discovery pipeline with live log streaming*

![3D Visualization](docs/screenshot_placeholder.png)
*Interactive 3D molecular viewer with docking pose analysis*

![Results Export](docs/screenshot_placeholder.png)
*Canonical CSV export with ADMET profiling and significance testing*

## 🔗 Links

- **GitHub Repository**: [Link to repo]
- **Demo Video**: [Link to video]
- **IBM Bob Documentation**: https://ibm.com/bob

## 👥 Team

Built with ❤️ using IBM Bob for the IBM Bob AI Assistant Hackathon

---

**Note**: This project demonstrates how AI assistants like IBM Bob can accelerate development in complex scientific codebases by capturing non-obvious patterns, automating integration fixes, and generating comprehensive tests.
