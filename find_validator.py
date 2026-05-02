"""Find where ValidatorAgent runs"""

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

lines = content.split("\n")

print("="*70)
print("SCANNING FOR VALIDATOR AGENT STRUCTURE")
print("="*70)

# 1. Find ValidatorAgent class
print("\n[1] ValidatorAgent class location:")
class_start = None
for i, line in enumerate(lines):
    if "class ValidatorAgent" in line:
        print(f"  L{i+1}: {line}")
        class_start = i
        break

# 2. Find all methods in ValidatorAgent
print("\n[2] Methods inside ValidatorAgent:")
if class_start:
    for i in range(class_start, min(class_start + 400, len(lines))):
        line = lines[i]
        if line.strip().startswith("def ") and (line.startswith("    def ") or line.startswith("\tdef ")):
            print(f"  L{i+1}: {line.strip()}")
        if i > class_start and line.startswith("class "):
            break

# 3. Find ValidatorAgent instantiation
print("\n[3] ValidatorAgent instantiation:")
for i, line in enumerate(lines):
    if "ValidatorAgent(" in line and "class ValidatorAgent" not in line:
        print(f"  L{i+1}: {line.strip()}")

# 4. Find validate references
print("\n[4] 'validate' call sites:")
for i, line in enumerate(lines):
    lower = line.lower()
    if "validat" in lower and "class" not in lower:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            print(f"  L{i+1}: {stripped[:100]}")

# 5. Find compound scoring loops
print("\n[5] Compound scoring patterns:")
for i, line in enumerate(lines):
    if any(p in line for p in ["for compound", "for idx, row", "for _, row", "iterrows()"]):
        if not line.strip().startswith("#"):
            print(f"  L{i+1}: {line.strip()[:100]}")

# 6. Find affinity scoring
print("\n[6] Affinity scoring lines:")
for i, line in enumerate(lines):
    if "affinity" in line.lower() and ("confidence" in line.lower() or "score" in line.lower()):
        if not line.strip().startswith("#"):
            print(f"  L{i+1}: {line.strip()[:100]}")

print("\n" + "="*70)
print("Paste this output back")
print("="*70)
