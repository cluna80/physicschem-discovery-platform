import json
import time
import numpy as np
import matplotlib.pyplot as plt
import re
from ollama import chat

MODEL = "qwen3:8b"
MAX_ITERATIONS = 8
N_QUBITS = 4
N_STATES = 2 ** N_QUBITS

history = []
discoveries = []


def run_standard_grover(n_qubits=N_QUBITS, target_state=None, iterations=None):
    N = 2 ** n_qubits
    
    if target_state is None:
        target_state = np.random.randint(0, N)
    # Handle both int and list inputs
    if isinstance(target_state, list):
        target_state = target_state[0]  # Take first target if list
    target_state = max(0, min(target_state, N-1))
    
    if iterations is None or iterations < 1:
        iterations = int(np.pi / 4 * np.sqrt(N))
    iterations = max(1, min(iterations, 20))
    
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    oracle = np.eye(N, dtype=complex)
    oracle[target_state, target_state] = -1
    uniform = np.ones(N, dtype=complex) / np.sqrt(N)
    diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
    
    for _ in range(iterations):
        state = oracle @ state
        state = diffusion @ state
    
    probs = np.abs(state)**2
    success = probs[target_state]
    return probs, success, iterations


def run_modified_grover(n_qubits=N_QUBITS, target_state=None, iterations=None, modification=None):
    N = 2 ** n_qubits
    
    if target_state is None:
        target_state = np.random.randint(0, N)
    # Handle both int and list inputs
    if isinstance(target_state, list):
        target_state = target_state[0]
    target_state = max(0, min(target_state, N-1))
    
    if iterations is None or iterations < 1:
        iterations = int(np.pi / 4 * np.sqrt(N))
    iterations = max(1, min(iterations, 20))
    
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    
    # Create oracle
    oracle = np.eye(N, dtype=complex)
    if modification and modification.get('type') == 'adaptive_oracle':
        phase_angle = modification.get('parameters', {}).get('phase_angle', np.pi)
        oracle[target_state, target_state] = np.exp(1j * phase_angle)
    else:
        oracle[target_state, target_state] = -1
    
    # Handle hybrid modifications
    mod_type = modification.get('type', 'standard') if modification else 'standard'
    params = modification.get('parameters', {}) if modification else {}
    
    # Check for hybrid (can be string or dict)
    if mod_type == 'hybrid' or (isinstance(mod_type, dict) and 'weighted' in str(mod_type)):
        # Hybrid: combine weighted and phased
        alpha = params.get('alpha', 0.9)
        phase = params.get('phase', 0)
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        standard_diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        
        target_vector = np.zeros(N, dtype=complex)
        target_vector[target_state] = 1
        target_diffusion = 2 * np.outer(target_vector, target_vector.conjugate()) - np.eye(N)
        
        weighted = alpha * standard_diffusion + (1 - alpha) * target_diffusion
        diffusion = np.exp(1j * phase) * weighted
        
    elif mod_type == 'weighted_diffusion':
        alpha = params.get('alpha', 0.5)
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        standard_diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        
        target_vector = np.zeros(N, dtype=complex)
        target_vector[target_state] = 1
        target_diffusion = 2 * np.outer(target_vector, target_vector.conjugate()) - np.eye(N)
        
        diffusion = alpha * standard_diffusion + (1 - alpha) * target_diffusion
        
    elif mod_type == 'phased_diffusion':
        phase = params.get('phase', 0)
        # Handle string phase like 'π/4'
        if isinstance(phase, str):
            if 'π' in phase:
                phase = eval(phase.replace('π', 'np.pi'))
            else:
                phase = float(phase)
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        standard_diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        diffusion = np.exp(1j * phase) * standard_diffusion
        
    elif mod_type == 'partial_diffusion':
        subset = params.get('subset', list(range(N//2)))
        uniform_subset = np.zeros(N, dtype=complex)
        for idx in subset:
            if idx < N:
                uniform_subset[idx] = 1 / np.sqrt(len(subset))
        diffusion = 2 * np.outer(uniform_subset, uniform_subset.conjugate()) - np.eye(N)
        
    else:
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
    
    for _ in range(iterations):
        state = oracle @ state
        state = diffusion @ state
    
    probs = np.abs(state)**2
    success = probs[target_state]
    return probs, success, iterations


def agent_think(prompt):
    try:
        response = chat(
            model=MODEL, 
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.9}
        )
        return response['message']['content']
    except Exception as e:
        print(f"[ERROR] {e}")
        return ""


def extract_json(text):
    text = re.sub(r'```json?\s*|\s*```', '', text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except:
        match = re.search(r'(\{[\s\S]*?\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    return None


print("="*70)
print("🚀 4-Qubit Autonomous Quantum Lab Agent - Hybrid Mode")
print("="*70)
print(f"📊 {N_STATES} states | Optimal iterations: {int(np.pi/4 * np.sqrt(N_STATES))}")
print("="*70)

# Test
_, s, _ = run_standard_grover(4, target_state=5, iterations=3)
print(f"✅ Standard Grover test: {s*100:.1f}% success\n")

for cycle in range(1, MAX_ITERATIONS + 1):
    print(f"\n{'='*70}")
    print(f"Cycle {cycle}/{MAX_ITERATIONS}")
    print(f"{'='*70}")
    
    # Build history
    history_text = ""
    for h in history[-5:]:
        mod = h.get('modification', {})
        mod_type = mod.get('type', 'unknown')
        success = h.get('success', 0)
        history_text += f"  - {mod_type}: {success*100:.1f}%\n"
    
    target_state = np.random.randint(0, N_STATES)
    
    prompt = f"""You are exploring Grover's algorithm on 4 qubits.

PREVIOUS EXPERIMENTS:
{history_text if history_text else "None yet"}

SUCCESSFUL PATTERNS FOUND:
- Weighted diffusion with α<0.8: FAILS (0-6%)
- Phased diffusion: WORKS PERFECTLY (96%)
- Partial diffusion: WORKS POORLY (6%)

Try a NEW idea. Be creative! Consider:
- HYBRID: weighted + phased combined
- Different α values near 0.9-0.95
- Multi-target search
- Custom diffusion subsets

Respond with JSON:
{{
  "research_question": "Your creative question",
  "modification": {{
    "type": "hybrid",
    "parameters": {{"alpha": 0.92, "phase": 0.5}}
  }},
  "experiment_params": {{
    "n_qubits": 4,
    "target": {target_state},
    "iterations": 3
  }}
}}

YOUR CREATIVE IDEA:"""

    try:
        response_text = agent_think(prompt)
        plan = extract_json(response_text)
        
        if not plan:
            # Smart fallback - try unexplored parameters
            tried_alphas = []
            for h in history:
                mod = h.get('modification', {})
                if mod.get('type') == 'weighted_diffusion':
                    tried_alphas.append(mod.get('parameters', {}).get('alpha', 0))
            
            # Try hybrid or new alpha
            if cycle % 2 == 0:
                plan = {
                    "research_question": f"Testing hybrid: weighted + phased",
                    "modification": {"type": "hybrid", "parameters": {"alpha": 0.92, "phase": np.pi/4}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            else:
                new_alpha = 0.85 + (cycle % 3) * 0.05
                plan = {
                    "research_question": f"Testing weighted diffusion with α={new_alpha}",
                    "modification": {"type": "weighted_diffusion", "parameters": {"alpha": new_alpha}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            print(f"⚠️  Smart fallback: {plan['modification']['type']}")
        
        idea = plan.get("research_question", "Unnamed")
        mod = plan.get("modification", {})
        mod_type = mod.get("type", "standard")
        params = mod.get("parameters", {})
        exp_params = plan.get("experiment_params", {})
        
        print(f"💡 {idea}")
        print(f"🔧 {mod_type} | Params: {params}")
        
        # Safe parameter extraction
        target = exp_params.get("target", target_state)
        if isinstance(target, list):
            target = target[0]
        target = int(target) % N_STATES
        
        iters = int(exp_params.get("iterations", 3))
        iters = max(1, min(iters, 10))
        
        # Run simulation
        probs, success, used_iters = run_modified_grover(4, target, iters, mod)
        
        # Get standard for comparison
        _, standard_success, _ = run_standard_grover(4, target, iters)
        
        improvement = success - standard_success
        
        print(f"\n📊 Result: {success*100:.2f}%")
        print(f"   Standard: {standard_success*100:.2f}%")
        print(f"   Improvement: {improvement*100:+.2f}%")
        
        # Store
        history.append({
            'idea': idea,
            'modification': mod,
            'success': success,
            'standard': standard_success,
            'improvement': improvement
        })
        
        # Create visualization
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # Left: Probability distribution
        ax1 = axes[0]
        colors = ['red' if i == target else 'steelblue' for i in range(N_STATES)]
        ax1.bar(range(N_STATES), probs, color=colors, edgecolor='black', alpha=0.8)
        ax1.axhline(y=1/N_STATES, color='orange', linestyle='--', label=f'Random (1/{N_STATES})')
        ax1.set_title(f"4-Qubit Grover - Cycle {cycle}\nTarget |{target}⟩, {iters} iterations\nSuccess: {success*100:.1f}%", fontsize=11)
        ax1.set_xlabel("Basis State")
        ax1.set_ylabel("Probability")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Right: Comparison
        ax2 = axes[1]
        iters_range = list(range(0, 9))
        std_vals = []
        mod_vals = []
        for i in iters_range:
            _, s_std, _ = run_standard_grover(4, target, i)
            _, s_mod, _ = run_modified_grover(4, target, i, mod)
            std_vals.append(s_std)
            mod_vals.append(s_mod)
        
        ax2.plot(iters_range, std_vals, 'o-', color='blue', linewidth=2, markersize=6, label='Standard Grover')
        ax2.plot(iters_range, mod_vals, 's-', color='red', linewidth=2, markersize=6, label=f'Modified ({mod_type})')
        ax2.axvline(x=iters, color='green', linestyle='--', label=f'Used {iters} iters')
        ax2.set_title(f"Performance Comparison\nImprovement: {improvement*100:+.1f}%", fontsize=11)
        ax2.set_xlabel("Iterations")
        ax2.set_ylabel("Success Probability")
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(f"grover_4q_cycle_{cycle}.png", dpi=150)
        plt.close()
        
        print(f"📊 Saved: grover_4q_cycle_{cycle}.png")
        
        # Discovery detection
        if mod_type == 'hybrid':
            print("🔬 TESTING HYBRID: Weighted + Phased Diffusion")
            if improvement > 0:
                print("🎉 DISCOVERY: Hybrid modification outperforms standard Grover!")
                discoveries.append({'cycle': cycle, 'mod': 'hybrid', 'improvement': improvement})
            else:
                print("📝 Hybrid doesn't improve over standard (phase doesn't help weighted failures)")
        
        elif mod_type == 'weighted_diffusion':
            alpha = params.get('alpha', 0)
            if alpha > 0.9 and success > 0.5:
                print(f"✨ α={alpha} gives {success*100:.1f}% - approaching standard!")
            elif alpha < 0.8:
                print(f"⚠️  α={alpha} too low - algorithm fails")
        
        elif mod_type == 'phased_diffusion':
            print("✅ Phase invariance confirmed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    time.sleep(1)

print("\n" + "="*70)
print("🎉 COMPLETE!")
print("="*70)

print("\n📊 FINAL SUMMARY:")
print("-"*50)
for i, h in enumerate(history, 1):
    mod = h.get('modification', {})
    mod_type = mod.get('type', 'unknown')
    success = h.get('success', 0)
    print(f"Cycle {i}: {mod_type:20s} → {success*100:5.1f}%")

if discoveries:
    print("\n🌟 DISCOVERIES MADE:")
    for d in discoveries:
        print(f"   Cycle {d['cycle']}: {d['mod']} - {d['improvement']*100:+.1f}% improvement")