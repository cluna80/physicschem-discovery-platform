# May 4 Hackathon Runbook — FBDD Qwen Fine-Tuning on AMD MI300X
# ================================================================
# Budget: $100 | Rate: $1.99/hr | Max safe hours: ~50
# Estimated training time: 2-4 hrs = ~$4-8
# SET A PHONE ALARM — SHUT DOWN INSTANCE WHEN DONE

# ── STEP 1: Spin up MI300X (single GPU, NOT x8) ──────────────────
# Go to amd.digitalocean.com → GPU Droplets → MI300X (1 GPU, 192GB)
# Select your fbdd-hackathon SSH key
# Note the IP address shown after creation

# ── STEP 2: SSH in ───────────────────────────────────────────────
ssh root@<YOUR_INSTANCE_IP>

# ── STEP 3: Verify ROCm + GPU ────────────────────────────────────
rocm-smi
python3 -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"

# ── STEP 4: Install dependencies ─────────────────────────────────
pip install transformers peft accelerate datasets huggingface_hub trl einops sentencepiece

# ── STEP 5: Upload your training script ──────────────────────────
# From your LOCAL machine (Git Bash):
scp finetune_qwen_rocm.py root@<YOUR_INSTANCE_IP>:/root/
scp requirements_rocm.txt root@<YOUR_INSTANCE_IP>:/root/

# ── STEP 6: Set your HF token ────────────────────────────────────
export HF_TOKEN=hf_your_write_token_here

# ── STEP 7: Run training ─────────────────────────────────────────
# Run in tmux so SSH disconnect doesn't kill it
tmux new -s training
python3 finetune_qwen_rocm.py
# Ctrl+B then D to detach, tmux attach -t training to reattach

# ── STEP 8: Monitor training ─────────────────────────────────────
# Watch GPU usage
watch -n 5 rocm-smi

# Watch training log
tail -f training_*.log

# ── STEP 9: After training completes ─────────────────────────────
# Script auto-pushes LoRA adapter to cluna80/qwen-fbdd-7b on HF
# Verify it's there: https://huggingface.co/cluna80/qwen-fbdd-7b

# ── STEP 10: SHUT DOWN INSTANCE ──────────────────────────────────
# Go to amd.digitalocean.com → GPU Droplets → Destroy
# !! DO THIS IMMEDIATELY AFTER TRAINING !!

# ── TROUBLESHOOTING ──────────────────────────────────────────────

# If torch not found:
pip3 install torch --extra-index-url https://download.pytorch.org/whl/rocm6.0

# If OOM (unlikely on 192GB for 7B):
# Reduce batch_size to 2 in finetune_qwen_rocm.py

# If bitsandbytes fails:
pip uninstall bitsandbytes -y
# Script will still work — we use bf16 not 4bit

# If model download is slow:
# Qwen2.5-7B is ~15GB — takes 5-10 min on first run
# Cached after first download

# ── SUBMISSION CHECKLIST ─────────────────────────────────────────
# [ ] Fine-tuned model on HF: cluna80/qwen-fbdd-7b
# [ ] Dataset on HF: cluna80/fbdd-qwen-dataset  
# [ ] HF Space with demo (create after training)
# [ ] 2x social posts tagging @AIatAMD and @lablab
# [ ] GitHub repo with code open-sourced
# [ ] Submit on lablab.ai before deadline
