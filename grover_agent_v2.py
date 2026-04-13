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
    N = 2 ** n_qubits
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


def run_modified_grover(n_qubits=3, target_state=7, iterations=None, modification=None):
    N = 2 ** n_qubits
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
            options={"temperature": 0.9}  # Increased for more variety
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


print(f"🚀 Autonomous Quantum Lab Agent - Using {MODEL}\n")

for cycle in range(1, MAX_ITERATIONS + 1):
    print(f"\n{'='*60}")
    print(f"Cycle {cycle}/{MAX_ITERATIONS}")
    print(f"{'='*60}")
    
    # Build detailed history with results
    history_text = ""
    for i, h in enumerate(history[-5:], 1):
        mod = h.get('modification', {})
        mod_type = mod.get('type', 'unknown')
        params = mod.get('parameters', {})
        success = h.get('success_probability', 0)
        history_text += f"  Experiment {i}: {mod_type} {params} → {success*100:.1f}%\n"
    
    if not history_text:
        history_text = "  No previous experiments yet.\n"
    
    # Suggest unexplored parameters
    tried_alphas = []
    for h in history:
        mod = h.get('modification', {})
        if mod.get('type') == 'weighted_diffusion':
            alpha = mod.get('parameters', {}).get('alpha')
            if alpha:
                tried_alphas.append(alpha)
    
    alpha_suggestion = ""
    if tried_alphas:
        tried_alphas_str = ", ".join([f"{a:.1f}" for a in sorted(tried_alphas)])
        alpha_suggestion = f"\nAlready tried α values: {tried_alphas_str}. Try a DIFFERENT α like 0.5, 0.6, 0.8, or 0.95."
    
    force_target = (3 + cycle) % 8
    force_iters = 2  # Use optimal iterations for fair comparison
    
    prompt = f"""You are exploring modifications to Grover's algorithm.

PREVIOUS EXPERIMENTS AND RESULTS:
{history_text}

YOUR GOAL: Try something NEW. Do NOT repeat previous experiments.

Available modification types:
1. weighted_diffusion - D = α(2|ψ⟩⟨ψ| - I) + (1-α)(2|target⟩⟨target| - I)
2. phased_diffusion - D = e^(iφ)(2|ψ⟩⟨ψ| - I)  
3. adaptive_oracle - Oracle with phase rotation instead of -1

{alpha_suggestion}

Choose a modification with DIFFERENT parameters than what's been tried.

Respond with ONLY JSON:
{{
  "research_question": "What happens when we try [YOUR NEW PARAMETER]?",
  "modification": {{
    "type": "weighted_diffusion",
    "parameters": {{"alpha": 0.6}}
  }},
  "experiment_params": {{"n_qubits": 3, "target": {force_target}, "iterations": {force_iters}}}
}}

YOUR NEW EXPERIMENT:"""

    try:
        response_text = agent_think(prompt)
        plan = extract_json(response_text)
        
        # Fallback with systematic parameter sweep
        if not plan or 'modification' not in plan:
            # Try different alpha values systematically
            alphas_to_try = [0.5, 0.6, 0.7, 0.8, 0.85, 0.95]
            # Find the first alpha not tried yet
            next_alpha = None
            for a in alphas_to_try:
                if a not in tried_alphas:
                    next_alpha = a
                    break
            if next_alpha is None:
                next_alpha = 0.95  # default
            
            plan = {
                "research_question": f"Testing weighted diffusion with α={next_alpha}",
                "modification": {"type": "weighted_diffusion", "parameters": {"alpha": next_alpha}},
                "experiment_params": {"n_qubits": 3, "target": force_target, "iterations": force_iters}
            }
            print(f"⚠️  Using systematic fallback: α={next_alpha}")
        
        idea = plan.get("research_question", "Unnamed")
        mod = plan.get("modification", {})
        mod_type = mod.get("type", "standard")
        params = mod.get("parameters", {})
        
        print(f"💡 {idea}")
        print(f"🔧 {mod_type} | Params: {params}")
        
        # Extract params
        p = plan.get("experiment_params", {})
        n = 3
        target = int(p.get("target", force_target)) % 8
        iters = int(p.get("iterations", force_iters))
        iters = max(1, min(iters, 10))
        
        # Run simulation
        probs, success, used_iters = run_modified_grover(n, target, iters, mod)
        
        print(f"📊 Result: {success:.4f} ({success*100:.2f}%)")
        
        # Store
        history.append({
            "research_question": idea,
            "modification": mod,
            "success_probability": success,
            "target": target,
            "iterations": used_iters
        })
        
        # Create plots
        plt.figure(figsize=(14, 5))
        
        # Left plot
        plt.subplot(1, 2, 1)
        colors = ['red' if i == target else 'steelblue' for i in range(8)]
        plt.bar(range(8), probs, color=colors, edgecolor='black', alpha=0.8)
        plt.axhline(y=0.125, color='orange', linestyle='--', label='Random (1/8)')
        plt.title(f"Target |{target}⟩, {used_iters} iterations\nSuccess: {success*100:.1f}%", fontsize=11)
        plt.xlabel("Basis State")
        plt.ylabel("Probability")
        plt.xticks(range(8))
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Right plot
        plt.subplot(1, 2, 2)
        iters_range = list(range(0, 9))
        
        standard_vals = []
        modified_vals = []
        for i in iters_range:
            _, s_std, _ = run_standard_grover(n, target, i)
            _, s_mod, _ = run_modified_grover(n, target, i, mod)
            standard_vals.append(s_std)
            modified_vals.append(s_mod)
        
        plt.plot(iters_range, standard_vals, 'o-', color='blue', linewidth=2, markersize=6, label='Standard Grover')
        plt.plot(iters_range, modified_vals, 's-', color='red', linewidth=2, markersize=6, label=f'Modified ({mod_type})')
        plt.axvline(x=used_iters, color='green', linestyle='--', label=f'Used {used_iters} iters')
        plt.title(f"Comparison at target |{target}⟩", fontsize=11)
        plt.xlabel("Iterations")
        plt.ylabel("Success Probability")
        plt.ylim(0, 1.05)
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(f"grover_cycle_{cycle}.png", dpi=150)
        plt.close()
        
        print(f"📊 Saved: grover_cycle_{cycle}.png")
        
        # Show what we learned
        standard_at_iters = standard_vals[used_iters]
        print(f"📈 Improvement vs standard: {success - standard_at_iters:+.2%}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    time.sleep(1)

print(f"\n{'='*60}")
print("🎉 Complete!")
print("\n📊 Experiment Summary:")
print("-"*50)
for i, exp in enumerate(history, 1):
    mod = exp.get('modification', {})
    params = mod.get('parameters', {})
    success = exp.get('success_probability', 0)
    print(f"Cycle {i}: α={params.get('alpha', 'N/A')} → {success*100:.1f}%")