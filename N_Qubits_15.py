import numpy as np
import matplotlib.pyplot as plt
import json
import os
import time

# ================== CONFIG ==================
N_QUBITS = 15
TRIALS = 10                 # Fewer trials per setting for speed; increase if needed
NOISE_LEVELS = [0.0, 0.01, 0.02, 0.03, 0.05]  # Phase noise standard deviation
ALPHA_VALUES = np.linspace(0.0, 0.01, 11)    # Adaptive coefficient sweep
WORK_DIR = "./results_sweep"
os.makedirs(WORK_DIR, exist_ok=True)
# ============================================

# ---------------- Core Grover Simulation ----------------
def run_quantum_simulation(n_qubits, target_state, iterations, noise=0.0):
    N = 2 ** n_qubits
    state = np.ones(N, dtype=np.complex128) / np.sqrt(N)
    for _ in range(iterations):
        # Oracle
        state[target_state] *= -1
        # Diffusion
        mean = np.mean(state)
        state = 2 * mean - state
        # Phase noise
        if noise > 0:
            state *= np.exp(1j * noise * np.random.randn(N))
            state /= np.linalg.norm(state)
    return np.abs(state[target_state])**2

# ---------------- Iteration Formulas ----------------
def standard_iterations(N):
    return int(np.pi / 4 * np.sqrt(N))

def adaptive_iterations(N, alpha):
    """Adaptive formula: over-rotation factor alpha"""
    return int((np.pi / 4 * np.sqrt(N)) * (1 + alpha * np.log2(N)))

# ---------------- Sweep Experiment ----------------
def run_sweep(n_qubits, alpha_values, noise_levels, trials):
    N = 2 ** n_qubits
    heatmap = np.zeros((len(alpha_values), len(noise_levels)))

    for i, alpha in enumerate(alpha_values):
        for j, noise in enumerate(noise_levels):
            successes = []
            for t in range(trials):
                target = np.random.randint(0, N)
                iters = adaptive_iterations(N, alpha)
                success = run_quantum_simulation(n_qubits, target, iters, noise)
                successes.append(success)
            heatmap[i, j] = np.mean(successes)
            print(f"Alpha {alpha:.4f}, Noise {noise:.3f} | Avg Success: {heatmap[i,j]:.4f}")
    return heatmap

# ---------------- Plot Heatmap ----------------
def plot_heatmap(alpha_values, noise_levels, heatmap):
    plt.figure(figsize=(10, 6))
    im = plt.imshow(heatmap, origin='lower', aspect='auto', 
                    extent=[min(noise_levels), max(noise_levels), min(alpha_values), max(alpha_values)],
                    cmap="viridis")
    plt.colorbar(im, label="Average Success Probability")
    plt.xlabel("Noise Level (σ)")
    plt.ylabel("Adaptive Coefficient α")
    plt.title(f"Adaptive Grover Success Heatmap ({N_QUBITS} qubits)")
    path = os.path.join(WORK_DIR, "adaptive_grover_heatmap.png")
    plt.savefig(path)
    plt.close()
    print(f"Heatmap saved to: {path}")

# ---------------- Main ----------------
def main():
    print("🚀 Running Adaptive Grover Sweep Study...")
    start = time.time()
    heatmap = run_sweep(N_QUBITS, ALPHA_VALUES, NOISE_LEVELS, TRIALS)
    plot_heatmap(ALPHA_VALUES, NOISE_LEVELS, heatmap)
    # Save results to JSON
    results_path = os.path.join(WORK_DIR, "adaptive_grover_results.json")
    json.dump({
        "N_QUBITS": N_QUBITS,
        "TRIALS": TRIALS,
        "ALPHA_VALUES": ALPHA_VALUES.tolist(),
        "NOISE_LEVELS": NOISE_LEVELS,
        "HEATMAP": heatmap.tolist()
    }, open(results_path, "w"), indent=2)
    print(f"Results JSON saved to: {results_path}")
    print(f"Total runtime: {time.time() - start:.2f} sec")

if __name__ == "__main__":
    main()