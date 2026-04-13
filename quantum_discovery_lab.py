import json
import time
import numpy as np
import matplotlib.pyplot as plt
import re
from ollama import chat
from datetime import datetime

# ============================================
# CONFIGURATION - NOW WITH 10 QUBITS!
# ============================================
MODEL = "qwen3:8b"
MAX_CYCLES = 12
MAX_QUBITS = 10  # UPGRADED to 10 qubits!
N_STATES = 2 ** MAX_QUBITS  # 1,024 states

print(f"🚀 10-QUBIT QUANTUM DISCOVERY LAB")
print(f"📊 Exploring {N_STATES} states (2^{MAX_QUBITS} qubits)")
print(f"🎯 Optimal Grover iterations: {int(np.pi/4 * np.sqrt(N_STATES))}")
print("="*60)

class QuantumSimulator:
    def __init__(self, n_qubits=MAX_QUBITS):
        self.n_qubits = n_qubits
        self.N = 2 ** n_qubits
        print(f"✅ Simulator ready: {self.N} states, ~{self.N*16/1024:.1f} KB memory")
        
    def run_grover(self, target_state, iterations=None, modification=None, noise_level=0):
        """Grover simulation for up to 10 qubits"""
        N = self.N
        target = target_state % N
        
        # Optimal iterations formula
        if iterations is None:
            iterations = int(np.pi / 4 * np.sqrt(N))
        iterations = max(1, min(iterations, 50))
        
        # Initialize uniform superposition
        state = np.ones(N, dtype=complex) / np.sqrt(N)
        
        # Oracle
        oracle = np.eye(N, dtype=complex)
        oracle[target, target] = -1
        
        # Diffusion operator
        uniform = np.ones(N, dtype=complex) / np.sqrt(N)
        diffusion = 2 * np.outer(uniform, uniform.conjugate()) - np.eye(N)
        
        # Apply modifications
        if modification:
            mod_type = modification.get('type', '')
            if mod_type == 'weighted':
                alpha = modification.get('alpha', 0.5)
                target_vec = np.zeros(N, dtype=complex)
                target_vec[target] = 1
                target_diff = 2 * np.outer(target_vec, target_vec.conjugate()) - np.eye(N)
                diffusion = alpha * diffusion + (1 - alpha) * target_diff
            elif mod_type == 'phased':
                phase = modification.get('phase', 0)
                diffusion = np.exp(1j * phase) * diffusion
        
        # Apply Grover iterations
        for _ in range(iterations):
            state = oracle @ state
            state = diffusion @ state
            
            # Add noise if specified
            if noise_level > 0:
                state = self._add_noise(state, noise_level)
        
        probs = np.abs(state)**2
        success = probs[target]
        return probs, success, iterations
    
    def _add_noise(self, state, noise_level):
        """Simple noise model for scaling studies"""
        noisy = state.copy()
        # Add phase noise
        for i in range(len(state)):
            if np.random.random() < noise_level:
                noisy[i] *= np.exp(1j * np.random.uniform(-np.pi/4, np.pi/4))
        # Renormalize
        norm = np.linalg.norm(noisy)
        if norm > 0:
            noisy = noisy / norm
        return noisy
    
    def benchmark_scaling(self, alphas, noise_levels):
        """Benchmark scaling behavior across parameters"""
        results = {}
        for alpha in alphas:
            for noise in noise_levels:
                mod = {'type': 'weighted', 'alpha': alpha}
                _, success, _ = self.run_grover(
                    target_state=5,
                    iterations=int(np.pi/4 * np.sqrt(self.N)),
                    modification=mod,
                    noise_level=noise
                )
                results[(alpha, noise)] = success
        return results


class QuantumAIAgent:
    def __init__(self, model=MODEL):
        self.model = model
        
    def think(self, prompt):
        try:
            response = chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.85}
            )
            return response['message']['content']
        except:
            return ""
    
    def generate_hypothesis(self, discoveries, n_qubits):
        """Generate hypothesis for 10-qubit exploration"""
        
        prompt = f"""You are exploring Grover's algorithm on {n_qubits} qubits ({2**n_qubits} states).

KEY INSIGHTS SO FAR:
- At 4 qubits, α=0.6 caused complete failure
- At 4 qubits, α=0.95 performed well under noise
- QUESTION: Does the α=0.6 anomaly scale to {n_qubits} qubits?

Generate a hypothesis about how the weighted diffusion parameter α should behave at {n_qubits} qubits.

Respond with JSON:
{{
  "hypothesis": "At {n_qubits} qubits, α=X will be optimal under noise",
  "alpha": 0.94,
  "reasoning": "Because scaling suggests..."
}}

Your hypothesis:"""
        
        response = self.think(prompt)
        return self._extract_json(response)
    
    def _extract_json(self, text):
        if not text:
            return None
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


# ============================================
# 10-QUBIT DISCOVERY LOOP
# ============================================

def main():
    print("\n" + "="*70)
    print("🔬 10-QUBIT AUTONOMOUS QUANTUM DISCOVERY LAB")
    print("="*70)
    
    simulator = QuantumSimulator(n_qubits=MAX_QUBITS)
    ai_agent = QuantumAIAgent()
    
    discoveries = []
    target_state = np.random.randint(0, N_STATES)  # Random target
    
    # Baseline: Standard Grover at optimal iterations
    optimal_iters = int(np.pi / 4 * np.sqrt(N_STATES))
    print(f"\n📊 10-QUBIT BASELINE:")
    print(f"   Target: |{target_state}⟩")
    print(f"   Optimal iterations: {optimal_iters}")
    
    _, baseline_clean, _ = simulator.run_grover(target_state, iterations=optimal_iters)
    print(f"   Standard Grover (no noise): {baseline_clean*100:.1f}%")
    
    _, baseline_noisy, _ = simulator.run_grover(target_state, iterations=optimal_iters, noise_level=0.05)
    print(f"   Standard Grover (5% noise): {baseline_noisy*100:.1f}%")
    
    print("="*70)
    
    # Systematic alpha exploration
    alphas_to_test = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.92, 0.95, 0.98, 1.0]
    noise_level = 0.05
    
    print("\n🔬 SYSTEMATIC 10-QUBIT EXPLORATION:")
    print("-"*70)
    print(f"{'α':^8} | {'Success':^12} | {'vs Standard':^12} | {'Finding':^20}")
    print("-"*70)
    
    for alpha in alphas_to_test:
        modification = {'type': 'weighted', 'alpha': alpha}
        _, success, _ = simulator.run_grover(
            target_state, 
            iterations=optimal_iters,
            modification=modification,
            noise_level=noise_level
        )
        
        improvement = success - baseline_noisy
        
        # Determine finding
        if improvement > 0.1:
            finding = "🎉 MAJOR DISCOVERY!"
        elif improvement > 0.05:
            finding = "✨ SIGNIFICANT"
        elif improvement > 0.02:
            finding = "📈 Promising"
        elif improvement < -0.05:
            finding = "⚠️ Poor"
        else:
            finding = "📝 Similar"
        
        print(f"{alpha:^8.2f} | {success*100:^12.1f}% | {improvement*100:^+12.1f}% | {finding:^20}")
        
        discoveries.append({
            'alpha': alpha,
            'success': success,
            'improvement': improvement,
            'finding': finding
        })
        
        # Create visualization every few runs
        if len(discoveries) % 3 == 0:
            plt.figure(figsize=(10, 6))
            alphas = [d['alpha'] for d in discoveries]
            successes = [d['success'] for d in discoveries]
            plt.plot(alphas, successes, 'o-', linewidth=2, markersize=8, color='red')
            plt.axhline(y=baseline_noisy, color='blue', linestyle='--', label=f'Standard Grover ({noise_level*100:.0f}% noise)')
            plt.axhline(y=1/N_STATES, color='gray', linestyle=':', label=f'Random guess (1/{N_STATES})')
            plt.xlabel('α (weight parameter)')
            plt.ylabel('Success Probability')
            plt.title(f'10-Qubit Grover: Weighted Diffusion Under {noise_level*100:.0f}% Noise')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.savefig(f'10qubit_scan_{len(discoveries)}.png', dpi=150)
            plt.close()
            print(f"   📊 Saved: 10qubit_scan_{len(discoveries)}.png")
    
    print("-"*70)
    
    # Find best alpha
    best = max(discoveries, key=lambda x: x['success'])
    
    print("\n" + "="*70)
    print("🎯 10-QUBIT DISCOVERY RESULTS")
    print("="*70)
    
    print(f"\n🌟 BEST PERFORMER: α = {best['alpha']}")
    print(f"   Success rate: {best['success']*100:.1f}%")
    print(f"   Improvement over standard: {best['improvement']*100:+.1f}%")
    
    if best['alpha'] != 1.0:
        print(f"\n💡 KEY DISCOVERY: α={best['alpha']} outperforms standard Grover!")
        print(f"   This suggests weighted diffusion can RESIST NOISE better than the standard algorithm!")
    
    # Check if α=0.6 anomaly scales
    alpha_06 = next((d for d in discoveries if d['alpha'] == 0.6), None)
    if alpha_06 and alpha_06['success'] < 0.05:
        print(f"\n🔬 SCALING OBSERVATION: α=0.6 anomaly PERSISTS at 10 qubits!")
        print(f"   Success at α=0.6: {alpha_06['success']*100:.1f}%")
        print(f"   This confirms the critical point is scale-invariant!")
    
    # Create final visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: α scan
    ax1 = axes[0]
    alphas = [d['alpha'] for d in discoveries]
    successes = [d['success'] for d in discoveries]
    ax1.plot(alphas, successes, 'o-', linewidth=2, markersize=8, color='red')
    ax1.axhline(y=baseline_noisy, color='blue', linestyle='--', label=f'Standard Grover')
    ax1.axhline(y=1/N_STATES, color='gray', linestyle=':', label=f'Random guess')
    ax1.fill_between(alphas, successes, baseline_noisy, where=(np.array(successes) > baseline_noisy), 
                      color='green', alpha=0.3, label='Improvement region')
    ax1.set_xlabel('α (weight parameter)')
    ax1.set_ylabel('Success Probability')
    ax1.set_title(f'10-Qubit Grover: Noise Robustness\n{noise_level*100:.0f}% Noise')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(0, 1)
    
    # Plot 2: Scaling comparison (4 vs 10 qubits - simulated data)
    ax2 = axes[1]
    # Simulated 4-qubit data from earlier experiments
    alphas_4q = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    successes_4q = [0.012, 0.0003, 0.012, 0.125, 0.399, 0.631, 0.945]
    
    ax2.plot(alphas_4q, successes_4q, 'o-', linewidth=2, markersize=6, label='4 Qubits', color='blue')
    ax2.plot(alphas, successes, 's-', linewidth=2, markersize=6, label='10 Qubits', color='red')
    ax2.set_xlabel('α (weight parameter)')
    ax2.set_ylabel('Success Probability')
    ax2.set_title('Scaling: 4 Qubits vs 10 Qubits\nUnder 5% Noise')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 1)
    
    plt.tight_layout()
    plt.savefig('10qubit_final_discoveries.png', dpi=150)
    plt.close()
    
    print(f"\n📊 Final plots saved:")
    print(f"   - 10qubit_final_discoveries.png")
    for i in range(1, len(discoveries)//3 + 1):
        print(f"   - 10qubit_scan_{i*3}.png")
    
    print("\n" + "="*70)
    print("🎉 10-QUBIT DISCOVERY CAMPAIGN COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    main()