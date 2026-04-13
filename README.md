# ⚗ PhysicsChem Discovery Platform v3.0

> **The world's first drug discovery platform applying particle physics discovery standards (Higgs 5σ) to Fragment-Based Drug Design.**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-red)](https://streamlit.io)
[![AutoDock Vina](https://img.shields.io/badge/Docking-AutoDock%20Vina-green)](https://vina.scripps.edu)
[![RDKit](https://img.shields.io/badge/Cheminformatics-RDKit-orange)](https://rdkit.org)

---

## 🏆 Key Results

| Compound | Target | Vina Affinity | vs Reference Drug | Status |
|---|---|---|---|---|
| SEED_INT_RAL_G004 | HIV Integrase | **-9.708 kcal/mol** | Beats Dolutegravir (-9.43) ✓ | 5.87σ |
| SEED_INT_RAL_G003 | HIV Integrase | -9.221 kcal/mol | Beats Dolutegravir ✓ | 5.08σ |
| F007_G013 | EGFR Kinase | -10.530 kcal/mol | Beats Erlotinib, Gefitinib, Osimertinib ✓ | 7.86σ |
| COVID SEED_R1C1_G010 | COVID-19 Mpro | -7.595 kcal/mol | 5σ Discovery | 8.82σ |

---

## 📊 Library Statistics

- **12,794+ compounds** across 14 disease targets
- **8,082 five-sigma discoveries** (p < 2.87×10⁻⁷)
- **97 novel scaffolds** (Tanimoto < 0.40 vs known drugs)
- **6 disease areas**: Oncology, Infectious Disease, Neurological, Cardiovascular, Metabolic, Inflammation

---

## 🔬 Scientific Framework

### Higgs 5σ Significance Testing
Standard borrowed from particle physics — the same bar that confirmed the Higgs boson:
H₀: Null distribution from fragment docking scores (n=20-50)
Z(c) = (μ₀ − affinity_c) / σ₀
5σ → p < 2.87×10⁻⁷ → DISCOVERY
3σ → p < 0.0027    → EVIDENCE

No competitor platform applies this statistical rigor to FBDD.

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install streamlit rdkit-pypi meeko admet-ai plotly pandas numpy

# Launch dashboard
streamlit run dashboard.py

# Run a discovery campaign (terminal)
python -W ignore autonomous_drug_agentV2.py --target HIV_INTEGRASE --fast

# Stress test everything
python stress_test.py
```

---

## 📁 Platform Architecture
autonomous_drug_agentV2.py   — FBDD Agent (18 targets, Higgs 5σ, ADMET-AI)
dashboard.py                 — 4-tab Streamlit UI (Discovery/Library/Optimizer/Export)
library_builder.py           — SQLite compound library manager
lead_optimizer.py            — R-group / Bioisostere / Scaffold hop optimizer
validate_leads.py            — Direct Vina docking validator
library_expander.py          — Mass expansion (ChEMBL, BRICS, Combinatorial)
harvest_all.py               — Universal campaign harvester
prep_integrase.py            — HIV Integrase receptor prep (PDB 3L2T)
higgs_whitepaper.py          — Auto-generates investor HTML report
stress_test.py               — Full end-to-end platform stress test

---

## 🎯 18 Disease Targets

| Category | Targets |
|---|---|
| Oncology | EGFR, T790M, VEGFR2, KRAS_G12C, BRAF_V600E, CDK4, PARP1 |
| Infectious Disease | HIV (Protease), HIV_INTEGRASE, COVID_MPRO, TB_INHA |
| Neurological | BACE1, ACHE, MAO_B |
| Cardiovascular | THROMBIN, FACTOR_XA |
| Metabolic | DPP4 |
| Inflammation | COX2, JAK1 |

---

## 💼 Commercial Applications

- **Hit Package Sales**: $50K–150K per target
- **Target Library License**: $150K–500K
- **Platform-as-a-Service**: $350K–1M/year
- **Drug Discovery Services**: Custom campaigns for pharma

---

## 📋 Workflow

Select Target (18 targets, FDA-validated receptors)
↓
Run FBDD Campaign (fragment screen → Higgs 5σ → grow → ADMET)
↓
Browse Fragment Library (12,794+ compounds, filter/inspect/3D view)
↓
Optimize Leads (R-group / bioisostere / scaffold hop)
↓
Validate with Vina (real docking scores, no ML estimation)
↓
Export Hit Package (SMILES + SDF + HTML report → ZIP)


---

## ⚗ Author

**PhysicsChem Discovery Lab**
Autonomous AI Drug Discovery Platform
GitHub: [@cluna80](https://github.com/cluna80)

---

*All results are computational predictions requiring experimental validation.*
*Provisional patent recommended before publication.*
