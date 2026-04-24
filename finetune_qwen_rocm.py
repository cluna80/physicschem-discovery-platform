"""
Qwen2.5-7B LoRA Fine-Tuning on AMD MI300X (ROCm)
==================================================
Fine-tunes Qwen2.5-7B on the FBDD drug discovery dataset
using LoRA/QLoRA via HuggingFace + PEFT on ROCm.

Usage on AMD MI300X:
    pip install -r requirements_rocm.txt
    python finetune_qwen_rocm.py

Estimated cost: ~$4-8 at $1.99/hr (2-4 hrs total)
Expected result: ~15-25% improvement on FBDD tasks vs base Qwen
"""

import os
import sys
import json
import torch
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

# ── Silence noisy warnings ──
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_HIP_ALLREDUCE_BYPASS"] = "1"  # ROCm stability

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
log = logging.getLogger(__name__)

# ── Check ROCm / CUDA ──
if torch.cuda.is_available():
    device_name = torch.cuda.get_device_name(0)
    log.info(f"GPU detected: {device_name}")
    log.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    IS_ROCM = "AMD" in device_name or "Radeon" in device_name or "gfx" in device_name.lower()
    log.info(f"ROCm mode: {IS_ROCM}")
else:
    log.error("No GPU found! This script requires an AMD MI300X GPU.")
    sys.exit(1)

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
)
from peft import (
    LoraConfig,
    get_peft_model,
    TaskType,
    prepare_model_for_kbit_training,
)
from datasets import load_dataset, DatasetDict
from huggingface_hub import login, HfApi

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FBDDTrainingConfig:
    # Model
    base_model: str = "Qwen/Qwen2.5-7B-Instruct"
    dataset_id: str = "cluna80/fbdd-qwen-dataset"
    output_dir: str = "./qwen-fbdd-finetuned"
    hub_model_id: str = "cluna80/qwen-fbdd-7b"

    # LoRA — tuned for MI300X 192GB VRAM
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])

    # Training
    num_epochs: int = 3
    batch_size: int = 4
    grad_accumulation: int = 4          # effective batch = 16
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    max_seq_length: int = 1024
    weight_decay: float = 0.01
    lr_scheduler: str = "cosine"

    # Checkpointing
    save_steps: int = 50
    eval_steps: int = 50
    logging_steps: int = 10
    load_best_at_end: bool = True

    # Push to HF when done
    push_to_hub: bool = True
    hf_token: Optional[str] = None      # set via HF_TOKEN env var


CFG = FBDDTrainingConfig()

# ─────────────────────────────────────────────────────────────────────────────
# HF LOGIN
# ─────────────────────────────────────────────────────────────────────────────

hf_token = CFG.hf_token or os.environ.get("HF_TOKEN")
if not hf_token:
    log.error("No HF token found. Set HF_TOKEN env var:")
    log.error("  export HF_TOKEN=hf_your_token_here")
    sys.exit(1)

login(token=hf_token)
log.info("HuggingFace login successful")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────

log.info(f"Loading tokenizer: {CFG.base_model}")
tokenizer = AutoTokenizer.from_pretrained(
    CFG.base_model,
    trust_remote_code=True,
    padding_side="right",
)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.pad_token_id = tokenizer.eos_token_id

log.info(f"Vocab size: {len(tokenizer)}")

# ─────────────────────────────────────────────────────────────────────────────
# LOAD MODEL
# ─────────────────────────────────────────────────────────────────────────────

log.info(f"Loading model: {CFG.base_model}")
log.info("Using bfloat16 (optimal for MI300X)")

model = AutoModelForCausalLM.from_pretrained(
    CFG.base_model,
    torch_dtype=torch.bfloat16,    # MI300X handles bf16 natively
    device_map="auto",              # auto-maps across GPUs if multiple
    trust_remote_code=True,
)

model.config.use_cache = False
model.config.pretraining_tp = 1

log.info(f"Model loaded. Parameters: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

# ─────────────────────────────────────────────────────────────────────────────
# LORA CONFIG
# ─────────────────────────────────────────────────────────────────────────────

log.info("Applying LoRA...")
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=CFG.lora_r,
    lora_alpha=CFG.lora_alpha,
    lora_dropout=CFG.lora_dropout,
    target_modules=CFG.target_modules,
    bias="none",
    inference_mode=False,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable/1e6:.1f}M / {total/1e6:.0f}M params ({100*trainable/total:.2f}%)")

# ─────────────────────────────────────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────────────────────────────────────

log.info(f"Loading dataset: {CFG.dataset_id}")
dataset = load_dataset(CFG.dataset_id, token=hf_token)
log.info(f"Train: {len(dataset['train'])} | Val: {len(dataset['validation'])}")

def format_messages_to_text(example):
    """Convert chat messages to Qwen chat template format."""
    messages = example["messages"]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}

def tokenize(example):
    """Tokenize with labels for causal LM training."""
    result = tokenizer(
        example["text"],
        truncation=True,
        max_length=CFG.max_seq_length,
        padding=False,
        return_tensors=None,
    )
    result["labels"] = result["input_ids"].copy()
    return result

log.info("Formatting and tokenizing dataset...")
dataset = dataset.map(format_messages_to_text, remove_columns=dataset["train"].column_names)
tokenized = dataset.map(tokenize, batched=False, remove_columns=["text"])

log.info(f"Tokenized train: {len(tokenized['train'])} | val: {len(tokenized['validation'])}")

# Quick sanity check
sample = tokenized["train"][0]
log.info(f"Sample input_ids length: {len(sample['input_ids'])}")
log.info(f"Sample decoded (first 200 chars): {tokenizer.decode(sample['input_ids'][:50])}")

# ─────────────────────────────────────────────────────────────────────────────
# TRAINING ARGS — ROCm optimized
# ─────────────────────────────────────────────────────────────────────────────

training_args = TrainingArguments(
    output_dir=CFG.output_dir,
    num_train_epochs=CFG.num_epochs,
    per_device_train_batch_size=CFG.batch_size,
    per_device_eval_batch_size=CFG.batch_size,
    gradient_accumulation_steps=CFG.grad_accumulation,
    learning_rate=CFG.learning_rate,
    weight_decay=CFG.weight_decay,
    warmup_ratio=CFG.warmup_ratio,
    lr_scheduler_type=CFG.lr_scheduler,

    # Mixed precision — bf16 for MI300X
    bf16=True,
    fp16=False,

    # ROCm-specific: disable CUDA-specific optimizations
    tf32=False,

    # Logging
    logging_dir=f"{CFG.output_dir}/logs",
    logging_steps=CFG.logging_steps,
    report_to="none",               # disable wandb/tensorboard by default

    # Evaluation
    eval_strategy="steps",
    eval_steps=CFG.eval_steps,
    save_strategy="steps",
    save_steps=CFG.save_steps,
    save_total_limit=3,
    load_best_model_at_end=CFG.load_best_at_end,
    metric_for_best_model="eval_loss",
    greater_is_better=False,

    # Memory optimization
    gradient_checkpointing=True,
    dataloader_num_workers=4,
    dataloader_pin_memory=False,    # False for ROCm stability
    group_by_length=True,           # pack similar-length sequences

    # Hub
    push_to_hub=False,              # we push manually at the end
)

# ─────────────────────────────────────────────────────────────────────────────
# TRAINER
# ─────────────────────────────────────────────────────────────────────────────

data_collator = DataCollatorForSeq2Seq(
    tokenizer=tokenizer,
    model=model,
    padding=True,
    pad_to_multiple_of=8,
    return_tensors="pt",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized["train"],
    eval_dataset=tokenized["validation"],
    tokenizer=tokenizer,
    data_collator=data_collator,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
)

# ─────────────────────────────────────────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────────────────────────────────────────

log.info("=" * 60)
log.info("Starting training...")
log.info(f"Model: {CFG.base_model}")
log.info(f"Dataset: {CFG.dataset_id}")
log.info(f"Epochs: {CFG.num_epochs}")
log.info(f"Effective batch size: {CFG.batch_size * CFG.grad_accumulation}")
log.info(f"LoRA r={CFG.lora_r}, alpha={CFG.lora_alpha}")
log.info("=" * 60)

train_result = trainer.train()

log.info("Training complete!")
log.info(f"Training loss: {train_result.training_loss:.4f}")
log.info(f"Total steps: {train_result.global_step}")
log.info(f"Runtime: {train_result.metrics['train_runtime']/3600:.2f} hours")

# Save metrics
with open(f"{CFG.output_dir}/train_metrics.json", "w") as f:
    json.dump(train_result.metrics, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# SAVE MODEL
# ─────────────────────────────────────────────────────────────────────────────

log.info(f"Saving model to {CFG.output_dir}")
trainer.save_model(CFG.output_dir)
tokenizer.save_pretrained(CFG.output_dir)

# Save LoRA adapter separately (much smaller — ~100MB vs 14GB)
lora_dir = f"{CFG.output_dir}/lora_adapter"
model.save_pretrained(lora_dir)
tokenizer.save_pretrained(lora_dir)
log.info(f"LoRA adapter saved to {lora_dir}")

# ─────────────────────────────────────────────────────────────────────────────
# PUSH TO HUB
# ─────────────────────────────────────────────────────────────────────────────

if CFG.push_to_hub:
    log.info(f"Pushing LoRA adapter to HuggingFace Hub: {CFG.hub_model_id}")
    try:
        api = HfApi()
        api.create_repo(
            CFG.hub_model_id,
            repo_type="model",
            private=True,
            exist_ok=True,
            token=hf_token,
        )
        api.upload_folder(
            folder_path=lora_dir,
            repo_id=CFG.hub_model_id,
            repo_type="model",
            token=hf_token,
        )
        log.info(f"Model pushed to: https://huggingface.co/{CFG.hub_model_id}")
    except Exception as e:
        log.error(f"Push failed: {e}")
        log.info(f"Model saved locally at: {lora_dir}")

# ─────────────────────────────────────────────────────────────────────────────
# QUICK INFERENCE TEST
# ─────────────────────────────────────────────────────────────────────────────

log.info("\nRunning quick inference test...")

test_prompt = [
    {
        "role": "system",
        "content": "You are an expert computational medicinal chemist specializing in fragment-based drug design."
    },
    {
        "role": "user",
        "content": (
            "Predict the binding affinity category for this molecule against "
            "Epidermal Growth Factor Receptor (EGFR), a key target in Non-small cell lung cancer.\n\n"
            "Molecule SMILES: c1ccc2c(c1)cc(cc2Nc3nccc(n3)c4cccnc4)C(=O)O\n"
            "Target binding pocket: ATP-binding kinase domain\n\n"
            "Categories: excellent, good, moderate, weak\n\n"
            "Predicted affinity category:"
        )
    }
]

model.eval()
with torch.no_grad():
    inputs = tokenizer.apply_chat_template(
        test_prompt,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
    ).to(model.device)

    outputs = model.generate(
        inputs,
        max_new_tokens=100,
        temperature=0.1,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id,
    )

    response = tokenizer.decode(
        outputs[0][inputs.shape[1]:],
        skip_special_tokens=True
    )

log.info(f"Test inference response: {response}")
log.info("\n" + "=" * 60)
log.info("ALL DONE — SHUT DOWN YOUR INSTANCE NOW")
log.info(f"LoRA adapter: {lora_dir}")
log.info(f"HF model: https://huggingface.co/{CFG.hub_model_id}")
log.info("=" * 60)
