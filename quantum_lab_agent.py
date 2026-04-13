import json
import time
import numpy as np
import matplotlib.pyplot as plt
from ollama import chat

# ================== CONFIG ==================
MODEL = "qwen2:7b"             # Your actual pulled model
MAX_ITERATIONS = 3             # Start small, increase when ready
WORK_DIR = "."                 # Folder to save plots and reports
# ===========================================

def run_quantum_simulation(n_qubits=3, target_state=7, iterations=None):
    """Pure NumPy Grover's algorithm simulation"""
    N = 2 ** n_qubits
    if iterations is None:
        iterations = int(np.pi / 4 * np.sqrt(N))
    
    # Initial uniform superposition
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    
    # Oracle: mark the target state
    oracle = np.eye(N, dtype=complex)
    oracle[target_state, target_state] = -1
    
    # Diffusion operator
    diffusion = 2 * np.outer(np.ones(N)/N, np.ones(N)) - np.eye(N)
    
    # Grover iterations
    for _ in range(iterations):
        state = oracle @ state
        state = diffusion @ state
    
    probs = np.abs(state)**2
    success_prob = probs[target_state]
    return probs, success_prob, iterations


def agent_think(prompt):
    """Call Ollama"""
    response = chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
    return response['message']['content']


# ================== MAIN AGENT LOOP ==================
print("🚀 Starting Autonomous Quantum Lab Agent (Grover's Algorithm Researcher)")
print(f"Model: {MODEL} | Max cycles: {MAX_ITERATIONS}\n")

for cycle in range(1, MAX_ITERATIONS + 1):
    print(f"\n=== Cycle {cycle}/{MAX_ITERATIONS} ===")
    
    # 1. Agent plans the research
    research_prompt = f"""
You are an autonomous quantum computing researcher.
Task: Suggest a small, testable variation or improvement idea for Grover's algorithm on very small scales (2-4 qubits).

Reply with **ONLY** valid JSON (no extra text, no markdown):
{{
  "research_question": "short clear question",
  "novel_formula": "brief description of your small modification or formula (use simple LaTeX if possible)",
  "experiment_params": {{"n_qubits": integer, "target": integer between 0 and 2^n-1, "iterations": integer or null}},
  "expected_outcome": "short expected result"
}}
"""
    plan_text = agent_think(research_prompt)
    print("Raw agent output:", plan_text[:300] + "..." if len(plan_text) > 300 else plan_text)
    
    # Robust JSON extraction
    try:
        # Remove possible markdown code blocks
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0]
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0]
        
        plan_json = json.loads(plan_text.strip())
    except Exception as e:
        print(f"⚠️ JSON parse failed: {e}. Using default experiment.")
        plan_json = {
            "research_question": "Default Grover test",
            "novel_formula": "Standard Grover",
            "experiment_params": {"n_qubits": 3, "target": 7, "iterations": None}
        }
    
    # 2. Run simulation
    params = plan_json.get("experiment_params", {})
    n = int(params.get("n_qubits", 3))
    target = int(params.get("target", 7))
    iters = params.get("iterations")
    
    probs, success, used_iters = run_quantum_simulation(n, target, iters)
    print(f"Simulation done → Success probability: {success:.4f} on {n} qubits")
    
    # 3. Create and save plot
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    plt.bar(range(2**n), probs, color='skyblue')
    plt.axvline(target, color='red', linestyle='--', linewidth=2, label=f'Target (state {target})')
    plt.title(f"Grover Search - {n} Qubits")
    plt.xlabel("Basis State")
    plt.ylabel("Probability")
    plt.legend()
    
    plt.subplot(1, 2, 2)
    iters_range = list(range(1, min(12, 2**n + 1)))
    successes = [run_quantum_simulation(n, target, i)[1] for i in iters_range]
    plt.plot(iters_range, successes, 'o-', color='darkblue')
    plt.title("Success Probability vs Iterations")
    plt.xlabel("Grover Iterations")
    plt.ylabel("Success Probability")
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = f"{WORK_DIR}/grover_cycle_{cycle}.png"
    plt.savefig(plot_path)
    plt.close()
    print(f"📊 Plot saved → {plot_path}")
    
    # 4. Agent writes conclusion
    analysis_prompt = f"""
Simulation results for your idea "{plan_json.get('novel_formula')}":
- {n} qubits, target state {target}
- Achieved success probability: {success:.4f} after {used_iters} iterations

Write a short scientific conclusion (3-5 sentences):
- Interpret the result
- Does it support your proposed idea?
- Suggest one concrete next small experiment
"""
    conclusion = agent_think(analysis_prompt)
    
    print("\n🔬 Agent Conclusion:")
    print(conclusion)
    
    # Save markdown report
    with open(f"{WORK_DIR}/research_cycle_{cycle}.md", "w", encoding="utf-8") as f:
        f.write(f"# Quantum Lab Cycle {cycle} — Grover Research\n\n")
        f.write(f"**Question:** {plan_json.get('research_question', 'N/A')}\n\n")
        f.write(f"**Proposed Idea:** {plan_json.get('novel_formula', 'None')}\n\n")
        f.write(f"**Result:** Success probability = **{success:.4f}** after {used_iters} iterations\n\n")
        f.write("### Conclusion\n\n")
        f.write(conclusion)
    
    print(f"📝 Report saved → research_cycle_{cycle}.md")
    time.sleep(1.5)

print("\n🎉 All cycles finished! Check the generated .png plots and .md files in your folder.")