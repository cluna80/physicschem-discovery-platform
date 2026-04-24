# QwenFBDD — AI Drug Discovery on AMD MI300X

> Fine-tuned Qwen2.5-7B on real fragment-based drug discovery docking data using ROCm on AMD Instinct MI300X.
> Built for the [AMD Developer Hackathon](https://lablab.ai/ai-hackathons/amd-developer-hackathon) — May 2026.

## Hackathon Tracks

- **Track 2: Fine-Tuning on AMD GPUs** — Fine-tuned Qwen2.5-7B on EGFR & HIV-1 docking data
- **Build in Public** — Open-source code, public dataset, social posts

## Model & Dataset

| Resource | Link |
|---|---|
| Fine-tuned model | [Cluna80/qwen-fbdd-7b](https://huggingface.co/Cluna80/qwen-fbdd-7b) |
| Training dataset | [cluna80/fbdd-qwen-dataset](https://huggingface.co/datasets/cluna80/fbdd-qwen-dataset) |

## Training Results

| Metric | Value |
|---|---|
| Base model | Qwen/Qwen2.5-7B-Instruct |
| Hardware | AMD Instinct MI300X (192GB VRAM) |
| Stack | ROCm 7.2 + PyTorch 2.5.1+rocm6.2 + TRL 1.2.0 |
| Training time | ~16 minutes |
| Starting loss | 2.99 |
| Final loss | 0.24 |
| Final train loss | 0.9669 |
| Token accuracy | ~92% at epoch 3 |

## Dataset

2,334 instruction pairs from real AutoDock Vina docking campaigns:

| Target | Records | Disease |
|---|---|---|
| EGFR Kinase | 132 | Non-small cell lung cancer |
| HIV-1 Protease | 168 | HIV/AIDS |
| HIV Integrase | 300 | HIV/AIDS |
| BACE1 | 19 | Alzheimer's |
| COVID Mpro | 17 | COVID-19 |
| Thrombin | 17 | Thrombosis |
| Fragment Library | 12,663 | Multi-target |

Top docking hits used as training signal:
- EGFR: -10.08 kcal/mol (beats Erlotinib, Gefitinib, Osimertinib)
- HIV Integrase: -9.708 kcal/mol (beats Dolutegravir)

## Task Types

- Binding affinity classification (excellent / good / moderate / weak)
- Docking score regression (predicted kcal/mol)
- ADMET drug-likeness assessment
- Fragment growing strategy suggestions
- Target identification from SMILES

## Quick Start

```bash
pip install transformers peft accelerate datasets huggingface_hub trl einops sentencepiece
export HF_TOKEN=your_token
python finetune_qwen_rocm.py
```

## Inference

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch

base = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-7B-Instruct",
    torch_dtype=torch.bfloat16,
    device_map="auto"
)
model = PeftModel.from_pretrained(base, "Cluna80/qwen-fbdd-7b")
tokenizer = AutoTokenizer.from_pretrained("Cluna80/qwen-fbdd-7b")

messages = [
    {"role": "system", "content": "You are an expert computational medicinal chemist specializing in FBDD."},
    {"role": "user", "content": "Predict binding affinity for SMILES: CCOc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCC\nTarget: EGFR\nCategories: excellent, good, moderate, weak"}
]

text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=100, temperature=0.1)
print(tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True))
```

## AMD Stack

- ROCm 7.2 — AMD open GPU compute platform
- PyTorch 2.5.1+rocm6.2
- AMD Instinct MI300X — 192GB HBM3, 750W
- AMD Developer Cloud — $1.99/hr

## Files

| File | Description |
|---|---|
| `build_fbdd_dataset.py` | Harvests docking results → instruction JSONL |
| `finetune_qwen_rocm.py` | LoRA fine-tuning on AMD MI300X |
| `requirements_rocm.txt` | Python dependencies |
| `MAY4_RUNBOOK.md` | AMD Dev Cloud step-by-step runbook |

## License

Apache 2.0

## Author

Chris Luna — [@cluna80](https://github.com/cluna80)
