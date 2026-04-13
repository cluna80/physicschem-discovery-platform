import json
import time
import numpy as np
import matplotlib.pyplot as plt
import re
from ollama import chat

MODEL = "qwen3:8b"
MAX_ITERATIONS = 8  # More cycles for 4-qubit exploration
N_QUBITS = 4  # NEW: 4 qubits!
N_STATES = 2 ** N_QUBITS  # 16 states

history = []

def run_standard_grover(n_qubits=N_QUBITS, target_state=None, iterations=None):
    """Standard Grover's algorithm for 4 qubits"""
    N = 2 ** n_qubits
    
    if target_state is None:
        target_state = np.random.randint(0, N)
    target_state = max(0, min(target_state, N-1))
    
    if iterations is None or iterations < 1:
        iterations = int(np.pi / 4 * np.sqrt(N))
    iterations = max(1, min(iterations, 20))
    
    # Initialize uniform superposition
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    
    # Oracle
    oracle = np.eye(N, dtype=complex)
    oracle[target_state, target_state] = -1
    
    # Diffusion (inversion about mean)
    uniform = np.ones(N, dtype=complex) / np.sqrt(N)
    diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
    
    # Apply iterations
    for _ in range(iterations):
        state = oracle @ state
        state = diffusion @ state
    
    probs = np.abs(state)**2
    success = probs[target_state]
    return probs, success, iterations


def run_modified_grover(n_qubits=N_QUBITS, target_state=None, iterations=None, modification=None):
    """Run Grover's algorithm with modifications on 4 qubits"""
    N = 2 ** n_qubits
    
    if target_state is None:
        target_state = np.random.randint(0, N)
    target_state = max(0, min(target_state, N-1))
    
    if iterations is None or iterations < 1:
        iterations = int(np.pi / 4 * np.sqrt(N))
    iterations = max(1, min(iterations, 20))
    
    # Initialize uniform superposition
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    
    # Create oracle
    oracle = np.eye(N, dtype=complex)
    
    if modification and modification.get('type') == 'adaptive_oracle':
        phase_angle = modification.get('parameters', {}).get('phase_angle', np.pi)
        oracle[target_state, target_state] = np.exp(1j * phase_angle)
    else:
        oracle[target_state, target_state] = -1
    
    # Create diffusion operator
    if modification and modification.get('type') == 'weighted_diffusion':
        alpha = modification.get('parameters', {}).get('alpha', 0.5)
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        standard_diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        
        target_vector = np.zeros(N, dtype=complex)
        target_vector[target_state] = 1
        target_diffusion = 2 * np.outer(target_vector, target_vector.conjugate()) - np.eye(N)
        
        diffusion = alpha * standard_diffusion + (1 - alpha) * target_diffusion
        
    elif modification and modification.get('type') == 'phased_diffusion':
        phase = modification.get('parameters', {}).get('phase', 0)
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        standard_diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        diffusion = np.exp(1j * phase) * standard_diffusion
        
    elif modification and modification.get('type') == 'multi_target':
        # Search for multiple targets simultaneously
        targets = modification.get('parameters', {}).get('targets', [target_state])
        oracle = np.eye(N, dtype=complex)
        for t in targets:
            t = t % N
            oracle[t, t] = -1
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        
    elif modification and modification.get('type') == 'partial_diffusion':
        # Only diffuse over a subset of states
        subset_size = modification.get('parameters', {}).get('subset_size', N//2)
        uniform_subset = np.zeros(N, dtype=complex)
        uniform_subset[:subset_size] = 1 / np.sqrt(subset_size)
        diffusion = 2 * np.outer(uniform_subset, uniform_subset.conjugate()) - np.eye(N)
        
    else:
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
    
    # Apply iterations
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


print(f"🚀 4-Qubit Autonomous Quantum Lab Agent - Using {MODEL}")
print(f"📊 Exploring {N_STATES} states (2^{N_QUBITS} qubits)")
print(f"🎯 Optimal iterations: {int(np.pi / 4 * np.sqrt(N_STATES))}")
print("="*60)

# Test 4-qubit simulation
print("\n🔬 Testing 4-qubit Grover:")
_, s, _ = run_standard_grover(4, target_state=5, iterations=3)
print(f"   Target |5⟩, 3 iterations: {s:.4f} (expected ~0.95-1.00)")
print("="*60)

for cycle in range(1, MAX_ITERATIONS + 1):
    print(f"\n{'='*60}")
    print(f"Cycle {cycle}/{MAX_ITERATIONS} (4 qubits)")
    print(f"{'='*60}")
    
    # Build detailed history
    history_text = ""
    for i, h in enumerate(history[-5:], 1):
        mod = h.get('modification', {})
        mod_type = mod.get('type', 'unknown')
        params = mod.get('parameters', {})
        success = h.get('success_probability', 0)
        history_text += f"  Exp{i}: {mod_type} {params} → {success*100:.1f}%\n"
    
    if not history_text:
        history_text = "  No previous experiments yet.\n"
    
    # Random target for variety
    target_state = np.random.randint(0, N_STATES)
    
    # 4-qubit specific prompt
    prompt = f"""You are exploring Grover's algorithm on 4 QUBITS (16 states).

PREVIOUS EXPERIMENTS:
{history_text}

4-QUBIT SPECIFICS:
- N=16 states, optimal iterations ≈ 3
- The space is larger - try variations that exploit this!

MODIFICATION TYPES:
1. weighted_diffusion - D = α(2|ψ⟩⟨ψ| - I) + (1-α)(2|target⟩⟨target| - I)
2. phased_diffusion - Add global phase e^(iφ) to diffusion
3. multi_target - Search for multiple targets simultaneously
4. partial_diffusion - Only diffuse over subset of states

Try a NOVEL modification. Be creative with parameters!

Respond with JSON:
{{
  "research_question": "Your research question for 4-qubit Grover",
  "modification": {{
    "type": "weighted_diffusion",
    "parameters": {{"alpha": 0.7}}
  }},
  "experiment_params": {{
    "n_qubits": 4,
    "target": {target_state},
    "iterations": 3
  }}
}}

YOUR 4-QUBIT EXPERIMENT:"""

    try:
        response_text = agent_think(prompt)
        plan = extract_json(response_text)
        
        # Intelligent fallback for 4-qubit exploration
        if not plan or 'modification' not in plan:
            # Explore different modification types
            mod_types = ['weighted_diffusion', 'phased_diffusion', 'multi_target', 'partial_diffusion']
            mod_type = mod_types[(cycle - 1) % len(mod_types)]
            
            if mod_type == 'weighted_diffusion':
                alphas = [0.3, 0.5, 0.7, 0.9, 0.95]
                alpha = alphas[(cycle - 1) % len(alphas)]
                plan = {
                    "research_question": f"4-qubit weighted diffusion with α={alpha}",
                    "modification": {"type": "weighted_diffusion", "parameters": {"alpha": alpha}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            elif mod_type == 'phased_diffusion':
                phases = [np.pi/4, np.pi/3, np.pi/2, 2*np.pi/3]
                phase = phases[(cycle - 1) % len(phases)]
                plan = {
                    "research_question": f"4-qubit phased diffusion with φ={phase:.2f}",
                    "modification": {"type": "phased_diffusion", "parameters": {"phase": phase}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            elif mod_type == 'multi_target':
                num_targets = 2 + (cycle % 3)
                targets = [target_state, (target_state + 4) % N_STATES][:num_targets]
                plan = {
                    "research_question": f"Search for {num_targets} targets simultaneously",
                    "modification": {"type": "multi_target", "parameters": {"targets": targets}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            else:  # partial_diffusion
                subset_size = 4 + (cycle % 4) * 2
                plan = {
                    "research_question": f"Partial diffusion over {subset_size} states",
                    "modification": {"type": "partial_diffusion", "parameters": {"subset_size": subset_size}},
                    "experiment_params": {"n_qubits": 4, "target": target_state, "iterations": 3}
                }
            print(f"⚠️  Using fallback: {mod_type}")
        
        idea = plan.get("research_question", "Unnamed")
        mod = plan.get("modification", {})
        mod_type = mod.get("type", "standard")
        params = mod.get("parameters", {})
        
        print(f"💡 {idea}")
        print(f"🔧 {mod_type} | Params: {params}")
        
        # Extract experiment params
        p = plan.get("experiment_params", {})
        n = 4  # Fixed to 4 qubits
        target = int(p.get("target", target_state)) % N_STATES
        iters = int(p.get("iterations", 3))
        iters = max(1, min(iters, 15))
        
        # Run simulation
        probs, success, used_iters = run_modified_grover(n, target, iters, mod)
        
        print(f"📊 Result: {success:.4f} ({success*100:.2f}%)")
        
        # Store
        history.append({
            "research_question": idea,
            "modification": mod,
            "success_probability": success,
            "target": target,
            "iterations": used_iters,
            "cycle": cycle
        })
        
        # Create 4-qubit visualization
        fig, axes = plt.subplots(1, 2, figsize=(16, 5))
        
        # Left plot: Probability distribution (16 states)
        ax1 = axes[0]
        colors = ['red' if i == target else 'steelblue' for i in range(N_STATES)]
        ax1.bar(range(N_STATES), probs, color=colors, edgecolor='black', alpha=0.8)
        ax1.axhline(y=1/N_STATES, color='orange', linestyle='--', label=f'Random (1/{N_STATES})')
        ax1.set_title(f"4-Qubit Grover - Cycle {cycle}\nTarget |{target}⟩, {used_iters} iterations\nSuccess: {success*100:.1f}%", fontsize=12)
        ax1.set_xlabel("Basis State (0-15)")
        ax1.set_ylabel("Probability")
        ax1.set_xticks(range(0, N_STATES, 2))
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Right plot: Comparison
        ax2 = axes[1]
        iters_range = list(range(0, 11))
        
        standard_vals = []
        modified_vals = []
        for i in iters_range:
            _, s_std, _ = run_standard_grover(n, target, i)
            _, s_mod, _ = run_modified_grover(n, target, i, mod)
            standard_vals.append(s_std)
            modified_vals.append(s_mod)
        
        ax2.plot(iters_range, standard_vals, 'o-', color='blue', linewidth=2, markersize=8, label='Standard Grover', alpha=0.7)
        ax2.plot(iters_range, modified_vals, 's-', color='red', linewidth=2, markersize=8, label=f'Modified ({mod_type})', alpha=0.7)
        ax2.axvline(x=used_iters, color='green', linestyle='--', linewidth=2, label=f'Used {used_iters} iters')
        
        # Mark optimal for 4 qubits
        optimal_iters = int(np.pi / 4 * np.sqrt(N_STATES))
        ax2.axvline(x=optimal_iters, color='purple', linestyle=':', linewidth=2, alpha=0.7, label=f'Optimal ({optimal_iters})')
        
        ax2.set_title(f"4-Qubit Success Probability Comparison", fontsize=12)
        ax2.set_xlabel("Iterations")
        ax2.set_ylabel("Success Probability")
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(f"grover_4q_cycle_{cycle}.png", dpi=150)
        plt.close()
        
        print(f"📊 Saved: grover_4q_cycle_{cycle}.png")
        
        # Calculate improvement
        standard_at_iters = standard_vals[used_iters]
        improvement = success - standard_at_iters
        print(f"📈 vs Standard at {used_iters} iters: {standard_at_iters:.4f} → {success:.4f} ({improvement:+.2%})")
        
        # 4-qubit specific insights
        if success > 0.9:
            print("🎉 EXCELLENT! Near-perfect success on 4 qubits!")
        elif success > 0.7:
            print("✅ Good performance on 4 qubits!")
        elif success < 0.1 and used_iters == optimal_iters:
            print("⚠️  Interesting: Poor performance at optimal iterations - modification breaks 4-qubit Grover!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    time.sleep(1)

print("\n" + "="*60)
print("🎉 4-Qubit Exploration Complete!")
print(f"📁 Generated {MAX_ITERATIONS} plots")
print("\n📊 4-Qubit Experiment Summary:")
print("-"*60)
for i, exp in enumerate(history, 1):
    mod = exp.get('modification', {})
    mod_type = mod.get('type', 'unknown')
    params = mod.get('parameters', {})
    success = exp.get('success_probability', 0)
    print(f"Cycle {i}: {mod_type:20s} {str(params):30s} → {success*100:5.1f}%")