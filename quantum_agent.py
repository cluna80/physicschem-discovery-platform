import ollama
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

MODEL = 'qwen2:7b'

def ask_ai(prompt: str, history=None, temperature=0.7):
    if history is None:
        history = []
    
    history.append({'role': 'user', 'content': prompt})
    
    response = ollama.chat(
        model=MODEL,
        messages=history,
        options={'temperature': temperature}
    )
    
    answer = response['message']['content']
    history.append({'role': 'assistant', 'content': answer})
    
    return answer, history

def plot_double_slit():
    """Simple double-slit interference pattern plot"""
    x = np.linspace(-10, 10, 1000)
    # Simple interference pattern: two slits
    intensity = (np.cos(2 * np.pi * x / 2)**2 + 0.5) * np.exp(-x**2 / 20)
    
    plt.figure(figsize=(10, 6))
    plt.plot(x, intensity, 'b-', linewidth=2)
    plt.title('Double-Slit Interference Pattern (Simplified)')
    plt.xlabel('Position on Screen')
    plt.ylabel('Intensity')
    plt.grid(True, alpha=0.3)
    plt.axvline(x=-2, color='r', linestyle='--', alpha=0.6, label='Slit 1')
    plt.axvline(x=2, color='r', linestyle='--', alpha=0.6, label='Slit 2')
    plt.legend()
    plt.show()

print("🔬 Autonomous AI Quantum Lab Agent v2")
print(f"Model: {MODEL}")
print("Commands:")
print("   • Just ask any quantum question")
print("   • Type 'plot double slit' → show interference pattern")
print("   • Type 'exit' or 'quit' to stop\n")

history = []

while True:
    try:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("👋 Goodbye! Keep exploring quantum mechanics!")
            break
            
        if not user_input:
            continue
            
        # Special command for plotting
        if user_input.lower() in ['plot double slit', 'double slit plot', 'show double slit']:
            print("Plotting double-slit interference pattern...")
            plot_double_slit()
            continue
            
        print("Thinking...", end=" ")
        answer, history = ask_ai(user_input, history, temperature=0.65)
        print("\r" + " " * 12, end="\r")   # clear Thinking...
        
        print(f"Agent:\n{answer}\n")
        
    except KeyboardInterrupt:
        print("\n\n👋 Agent stopped by user.")
        break
    except Exception as e:
        print(f"\nError: {e}")

print("Session ended at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))