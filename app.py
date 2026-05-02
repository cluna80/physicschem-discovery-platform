import gradio as gr
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

print("Loading model...")
pipe = pipeline(
    "text-generation",
    model=MODEL,
    torch_dtype=torch.float32,
    device_map="cpu",
    trust_remote_code=True,
)
print("Ready!")

TARGET_INFO = {
    "EGFR (Lung Cancer)":  {"full": "Epidermal Growth Factor Receptor", "key": "EGFR", "pocket": "ATP-binding kinase domain", "drugs": "Erlotinib, Gefitinib, Osimertinib", "excellent": -10.0, "good": -9.0},
    "HIV-1 Protease":      {"full": "HIV-1 Protease", "key": "HIV", "pocket": "Catalytic aspartate dyad", "drugs": "Darunavir, Lopinavir", "excellent": -8.5, "good": -7.0},
    "HIV Integrase":       {"full": "HIV-1 Integrase", "key": "HIV_INTEGRASE", "pocket": "Catalytic core domain Mg2+", "drugs": "Raltegravir, Dolutegravir", "excellent": -9.0, "good": -7.5},
    "BACE1 (Alzheimer's)": {"full": "Beta-secretase 1", "key": "BACE1", "pocket": "Aspartyl protease active site", "drugs": "Verubecestat", "excellent": -9.5, "good": -8.0},
    "COVID Mpro":          {"full": "SARS-CoV-2 Main Protease", "key": "COVID_MPRO", "pocket": "Cys145/His41 catalytic dyad", "drugs": "Nirmatrelvir", "excellent": -9.0, "good": -7.5},
}

TASKS = {
    "Affinity Prediction": lambda s, t: f"Predict the binding affinity category for SMILES: {s} against {t['full']}.\nCategories: excellent (≤{t['excellent']} kcal/mol), good (≤{t['good']}), moderate (≤-6.0), weak (>-6.0)\nAnswer:",
    "ADMET Assessment":    lambda s, t: f"Assess drug-likeness of SMILES: {s} for {t['full']}.\nProvide: Ro5 compliance, bioavailability, liabilities, verdict.",
    "Fragment Growing":    lambda s, t: f"Suggest 3 fragment growing strategies for SMILES: {s} against {t['full']} pocket: {t['pocket']}.\nFor each give direction and rationale.",
    "Target ID":           lambda s, t: f"Identify the likely therapeutic target for SMILES: {s}.\nGive primary target and rationale.",
}

def predict(smiles, target_name, task, max_tokens, temperature):
    if not smiles.strip():
        return "Please enter a SMILES string."
    t = TARGET_INFO[target_name]
    messages = [
        {"role": "system", "content": "You are an expert computational medicinal chemist specializing in fragment-based drug design (FBDD)."},
        {"role": "user", "content": TASKS[task](smiles.strip(), t)},
    ]
    result = pipe(messages, max_new_tokens=int(max_tokens), temperature=float(temperature) if temperature > 0.05 else 1.0, do_sample=temperature > 0.05)
    return result[0]["generated_text"][-1]["content"].strip()

with gr.Blocks(title="QwenFBDD") as demo:
    gr.HTML("""
    <h1 style='text-align:center'>🧬 QwenFBDD — Drug Discovery AI</h1>
    <p style='text-align:center'>
        Fine-tuned on real EGFR & HIV-1 docking data · AMD Developer Hackathon 2026<br>
        <a href='https://huggingface.co/Cluna80/qwen-fbdd-7b' target='_blank'>Fine-tuned 7B Model</a> · 
        <a href='https://huggingface.co/datasets/cluna80/fbdd-qwen-dataset' target='_blank'>Dataset</a> · 
        <a href='https://github.com/cluna80/AMD-Hackathon' target='_blank'>GitHub</a>
    </p>
    <p style='text-align:center;font-size:12px;color:#888'>
        Demo runs Qwen2.5-1.5B on CPU. Full fine-tuned 7B model trained on AMD Instinct MI300X with ROCm.
    </p>
    """)
    with gr.Row():
        with gr.Column():
            smi = gr.Textbox(label="SMILES String", placeholder="CCOc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCC", lines=2)
            with gr.Row():
                tgt = gr.Dropdown(choices=list(TARGET_INFO.keys()), value="EGFR (Lung Cancer)", label="Target")
                tsk = gr.Dropdown(choices=list(TASKS.keys()), value="Affinity Prediction", label="Task")
            with gr.Row():
                tok = gr.Slider(50, 300, value=150, step=50, label="Max tokens")
                tmp = gr.Slider(0.0, 1.0, value=0.1, step=0.05, label="Temperature")
            btn = gr.Button("🔬 Analyze", variant="primary")
        out = gr.Textbox(label="Output", lines=10, show_copy_button=True)
    gr.Examples(
        examples=[
            ["CCOc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCC", "EGFR (Lung Cancer)", "Affinity Prediction", 150, 0.1],
            ["CC(C)CN1CC(O)C(Nc2ccc3c(c2)OCCO3)C1=O", "HIV-1 Protease", "ADMET Assessment", 150, 0.1],
            ["c1ccc(NC(=O)c2ccncc2)cc1", "EGFR (Lung Cancer)", "Fragment Growing", 200, 0.2],
        ],
        inputs=[smi, tgt, tsk, tok, tmp],
    )
    btn.click(predict, inputs=[smi, tgt, tsk, tok, tmp], outputs=out)

demo.launch()
