import json
import time
import numpy as np
import matplotlib.pyplot as plt
import re
from ollama import chat

MODEL = "qwen3:8b"
MAX_ITERATIONS = 6

history = []

def run_standard_grover(n_qubits=3, target_state=7, iterations=None):
    """Standard Grover's algorithm"""
    N = 2 ** n_qubits
    target_state = max(0, min(target_state, N-1))
    
    if iterations is None or iterations < 1:
        iterations = int(np.pi / 4 * np.sqrt(N))
    iterations = max(1, min(iterations, 20))
    
    # Initialize uniform superposition
    state = np.ones(N, dtype=complex) / np.sqrt(N)
    
    # Oracle: flips sign of target state
    oracle = np.eye(N, dtype=complex)
    oracle[target_state, target_state] = -1
    
    # Diffusion: inversion about mean
    uniform = np.ones(N, dtype=complex) / np.sqrt(N)
    diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
    
    # Apply iterations
    for _ in range(iterations):
        state = oracle @ state
        state = diffusion @ state
    
    probs = np.abs(state)**2
    success = probs[target_state]
    return probs, success, iterations


def run_modified_grover(n_qubits=3, target_state=7, iterations=None, modification=None):
    """Run Grover's algorithm with modifications"""
    N = 2 ** n_qubits
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
        
    else:
        # Standard diffusion
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
            options={"temperature": 0.85}
        )
        content = response['message']['content']
        return content
    except Exception as e:
        print(f"[ERROR] Agent think failed: {e}")
        return ""


def extract_json(text):
    text = re.sub(r'```json?\s*|\s*```', '', text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except:
        pass
    
    match = re.search(r'(\{[\s\S]*?\})', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    return None


print(f"🚀 Autonomous Quantum Lab Agent - Using {MODEL}\n")

for cycle in range(1, MAX_ITERATIONS + 1):
    print(f"\n{'='*60}")
    print(f"Cycle {cycle}/{MAX_ITERATIONS}")
    print(f"{'='*60}")
    
    # Build memory
    previous_ideas = [h.get("research_question", "") for h in history[-3:] if h.get("research_question")]
    memory = " | ".join(previous_ideas) if previous_ideas else "None yet"
    
    force_target = (3 + cycle) % 8
    
    prompt = f"""You are a quantum algorithms researcher. Propose a modification to Grover's algorithm.

PREVIOUS IDEAS: {memory}

Choose from:
1. weighted_diffusion - D = α(2|ψ⟩⟨ψ| - I) + (1-α)(2|target⟩⟨target| - I)
2. phased_diffusion - Add global phase e^(iφ) to diffusion
3. adaptive_oracle - Oracle with phase rotation

Respond with JSON:
{{
  "research_question": "Your research question",
  "modification": {{
    "type": "weighted_diffusion",
    "parameters": {{"alpha": 0.9}}
  }},
  "experiment_params": {{"n_qubits": 3, "target": {force_target}, "iterations": 2}}
}}

YOUR MODIFICATION:"""

    try:
        response_text = agent_think(prompt)
        plan = extract_json(response_text)
        
        if not plan or 'modification' not in plan:
            # Fallback with different alpha each time
            alphas = [0.9, 0.95, 0.8, 0.85]
            plan = {
                "research_question": f"Testing weighted diffusion with α={alphas[(cycle-1)%len(alphas)]}",
                "modification": {"type": "weighted_diffusion", "parameters": {"alpha": alphas[(cycle-1)%len(alphas)]}},
                "experiment_params": {"n_qubits": 3, "target": force_target, "iterations": 2}
            }
        
        idea = plan.get("research_question", "Unnamed")
        mod = plan.get("modification", {})
        mod_type = mod.get("type", "standard")
        params = mod.get("parameters", {})
        
        print(f"💡 {idea}")
        print(f"🔧 {mod_type} | Params: {params}")
        
        # Extract experiment params
        p = plan.get("experiment_params", {})
        n = 3
        target = int(p.get("target", force_target)) % 8
        iters = int(p.get("iterations", 2))
        iters = max(1, min(iters, 10))
        
        # Run simulation
        probs, success, used_iters = run_modified_grover(n, target, iters, mod)
        
        print(f"📊 Result: {success:.4f} ({success*100:.2f}%)")
        
        # Store history
        history.append({
            "research_question": idea,
            "modification": mod,
            "success_probability": success,
            "target": target,
            "iterations": used_iters
        })
        
        # Create plots
        plt.figure(figsize=(14, 5))
        
        # Left plot: Probability distribution
        plt.subplot(1, 2, 1)
        colors = ['red' if i == target else 'steelblue' for i in range(8)]
        plt.bar(range(8), probs, color=colors, edgecolor='black', alpha=0.8)
        plt.axhline(y=0.125, color='orange', linestyle='--', label='Random (1/8)')
        plt.title(f"Probability Distribution\nTarget |{target}⟩, {used_iters} iterations", fontsize=12)
        plt.xlabel("Basis State")
        plt.ylabel("Probability")
        plt.xticks(range(8))
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Right plot: Compare standard vs modified
        plt.subplot(1, 2, 2)
        iters_range = list(range(0, 9))
        
        standard_vals = []
        modified_vals = []
        
        for i in iters_range:
            _, s_std, _ = run_standard_grover(n, target, i)
            _, s_mod, _ = run_modified_grover(n, target, i, mod)
            standard_vals.append(s_std)
            modified_vals.append(s_mod)
        
        # Verify data is correct
        print(f"   Standard at 2 iters: {standard_vals[2]:.4f} (expected ~0.945)")
        print(f"   Modified at {used_iters} iters: {modified_vals[used_iters]:.4f}")
        
        plt.plot(iters_range, standard_vals, 'o-', color='blue', linewidth=2, markersize=6, label='Standard Grover')
        plt.plot(iters_range, modified_vals, 's-', color='red', linewidth=2, markersize=6, label=f'Modified ({mod_type})')
        plt.axvline(x=used_iters, color='green', linestyle='--', linewidth=2, label=f'Used {used_iters} iters')
        plt.title(f"Success Probability Comparison", fontsize=12)
        plt.xlabel("Iterations")
        plt.ylabel("Success Probability")
        plt.ylim(0, 1.05)
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(f"grover_cycle_{cycle}.png", dpi=150)
        plt.close()
        
        print(f"📊 Saved: grover_cycle_{cycle}.png")
        
        # Discovery detection
        if mod_type == 'weighted_diffusion':
            alpha = params.get('alpha', 0)
            if alpha > 0.95:
                print("✨ Near-standard Grover performance!")
            elif alpha < 0.8:
                print(f"⚠️  α={alpha} too low - algorithm fails")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    time.sleep(1)

print(f"\n{'='*60}")
print("🎉 Complete!")