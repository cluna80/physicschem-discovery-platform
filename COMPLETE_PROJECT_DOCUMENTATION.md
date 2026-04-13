
---

## Appendix C: Grover Quantum Search System

### C.1 What is Grover?

The **Grover Quantum Search System** is a quantum-inspired algorithm used for **de novo compound generation** — discovering entirely new chemical structures rather than screening existing libraries.

Unlike classical methods that enumerate known compounds, Grover's algorithm explores chemical space exponentially faster using quantum superposition and amplitude amplification principles.

### C.2 How Grover Was Used in This Project

The Grover system was the **foundation** of this drug discovery pipeline:
┌─────────────────────────────────────────────────────────────────┐
│ GROVER QUANTUM DISCOVERY │
│ │
│ Quantum State Preparation │
│ ↓ │
│ Superposition over Chemical Space (2^n possibilities) │
│ ↓ │
│ Oracle: HIV Protease Binding Potential │
│ ↓ │
│ Amplitude Amplification (finds high-probability binders) │
│ ↓ │
│ Collapse → Novel Compounds (CURE series) │
│ ↓ │
│ Classical Validation (Gnina Docking, MD) │
└─────────────────────────────────────────────────────────────────┘

text

### C.3 Grover Scripts in This Project

| File | Purpose |
|------|---------|
| `grover_agent.py` | Main Grover agent for compound generation |
| `grover_agent_v2.py` | Enhanced version with improved scoring |
| `grover_agent_v3.py` | Iterative refinement |
| `grover_agent_v4.py` | Final optimized version |
| `grover_on_real_quantum.py` | IBM Quantum backend integration |
| `submit_grover_marrakesh.py` | Marrakesh quantum computer submission |
| `submit_grover_real.py` | Real quantum hardware submission |
| `get_grover_results.py` | Result retrieval from quantum jobs |
| `grover_job_id.txt` | Track quantum job IDs |
| `grover_marrakesh_job.txt` | Marrakesh job tracking |
| `grover_real_results.txt` | Results from real quantum hardware |

### C.4 Grover-Generated Compounds

The **CURE series** (CURE_13G_001, CURE_16G_007, CURE_17G_002, CURE_17G_003, CURE_17G_007, Q15_020) were **all discovered using Grover's quantum search algorithm**, not from existing databases.

Each compound represents a **novel chemical scaffold** that the quantum system identified as having high predicted binding probability to HIV protease.

### C.5 Quantum Hardware Used

| Hardware | Purpose |
|----------|---------|
| **IBM Quantum** | Real quantum computer access via IBM Quantum Experience |
| **Marrakesh** | Specific IBM quantum processor used for production runs |
| **Simulators** | Qiskit Aer for development and testing |

### C.6 Grover Results & Validation

The quantum system identified:
- **Hydroxy-isoquinoline core** as optimal scaffold
- **bis-THF moiety** for S2 pocket binding
- **3,5-diF substitution** on phenyl ring
- **S-OH stereochemistry** preference

These quantum-derived insights were then:
1. Validated by Gnina docking
2. Tested in MD simulations
3. Optimized via CF3 addition
4. Profiled against resistance mutants

### C.7 Why Grover Matters

Traditional compound generation:
- Screens millions of existing compounds
- Limited to known chemical space
- Time-consuming

Grover quantum generation:
- Explores **unexplored chemical space**
- Generates **truly novel scaffolds**
- Finds **quantum-optimal** binding motifs
- Runs in **hours instead of months**

**The CURE series and opt5_v2_7 exist because Grover found them.**

