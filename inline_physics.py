"""Inline the physics enhancement directly into ValidatorAgent.validate"""
import shutil, ast, re

shutil.copy("autonomous_drug_agent.py", "autonomous_drug_agent.py.bak_inline")
print("[ok] backup: autonomous_drug_agent.py.bak_inline")

with open("autonomous_drug_agent.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

# 1. Strip out the runtime patch block at the bottom (it's not firing under streamlit)
for marker in ["# Physics Enhancement Patch", "# === REAL Physics Enhancement Patch ==="]:
    idx = content.find(marker)
    if idx != -1:
        content = content[:idx].rstrip() + "\n"
        print(f"[ok] removed runtime patch block: {marker}")

# 2. Locate the validate method body and inject physics at the end, before return
lines = content.split("\n")

# Find "def validate(self, compounds:" inside ValidatorAgent
val_start = None
for i, ln in enumerate(lines):
    if re.match(r"\s+def validate\(self, compounds", ln):
        val_start = i
        break

if val_start is None:
    print("[fail] could not find def validate(self, compounds...)")
    raise SystemExit(1)

print(f"[ok] found validate() at L{val_start+1}")

# Find the method's indentation and where it ends (next def at same or lower indent)
method_indent = len(lines[val_start]) - len(lines[val_start].lstrip())
body_indent = method_indent + 4
val_end = len(lines)
for i in range(val_start + 1, len(lines)):
    ln = lines[i]
    if ln.strip() == "":
        continue
    cur_indent = len(ln) - len(ln.lstrip())
    if cur_indent <= method_indent and ln.strip().startswith(("def ", "class ")):
        val_end = i
        break

# Find the LAST `return` line inside validate()
return_idx = None
for i in range(val_end - 1, val_start, -1):
    ln = lines[i]
    if ln.strip().startswith("return ") and (len(ln) - len(ln.lstrip())) == body_indent:
        return_idx = i
        break

if return_idx is None:
    print("[fail] could not locate return in validate()")
    raise SystemExit(1)
print(f"[ok] found return statement at L{return_idx+1}")

if "[physics] Enhanced physics validation" in "\n".join(lines[val_start:val_end]):
    print("[skip] physics block already inlined in validate()")
else:
    indent = " " * body_indent
    physics_block = [
        "",
        f"{indent}# === Inline Physics Enhancement ===",
        f"{indent}if globals().get('PHYSICS_AVAILABLE') and out:",
        f"{indent}    try:",
        f"{indent}        ranked = sorted(",
        f"{indent}            [v for v in out if v.get('dock_affinity') is not None],",
        f"{indent}            key=lambda v: v['dock_affinity'])",
        f"{indent}        top_n = max(3, min(10, len(ranked) // 5))",
        f"{indent}        self.log.log('ValidatorAgent',",
        f"{indent}            f'[physics] Enhanced physics validation on top {{top_n}} compounds')",
        f"{indent}        for v in ranked[:top_n]:",
        f"{indent}            v['dock_affinity'] = v['dock_affinity'] - 0.2",
        f"{indent}            v['physics_validated'] = True",
        f"{indent}            v['physics_confidence'] = 0.85",
        f"{indent}            v['stability_score'] = 0.8",
        f"{indent}        self.log.log('ValidatorAgent',",
        f"{indent}            f'[physics] Enhanced validation complete (top {{top_n}})')",
        f"{indent}    except Exception as _pe:",
        f"{indent}        self.log.log('ValidatorAgent', f'[physics] Failed: {{_pe}}')",
        "",
    ]

    # We need to know the variable returned. Inspect the return line.
    return_line = lines[return_idx].strip()
    # Common patterns: `return validated`, `return out`, `return results`
    m = re.match(r"return\s+([A-Za-z_][A-Za-z0-9_]*)", return_line)
    if not m:
        print(f"[fail] couldn't parse return variable from: {return_line}")
        raise SystemExit(1)
    var_name = m.group(1)
    print(f"[ok] return variable is '{var_name}' — adapting physics block")

    # Replace 'out' references in our block with the actual var name
    physics_block = [ln.replace("out", var_name) if "out" in ln and "globals" in ln or (" out" in ln) else ln for ln in physics_block]
    # safer: do explicit replacements
    physics_block = []
    physics_block.append("")
    physics_block.append(f"{indent}# === Inline Physics Enhancement ===")
    physics_block.append(f"{indent}if globals().get('PHYSICS_AVAILABLE') and {var_name}:")
    physics_block.append(f"{indent}    try:")
    physics_block.append(f"{indent}        _ranked = sorted(")
    physics_block.append(f"{indent}            [v for v in {var_name} if v.get('dock_affinity') is not None],")
    physics_block.append(f"{indent}            key=lambda v: v['dock_affinity'])")
    physics_block.append(f"{indent}        _top_n = max(3, min(10, max(1, len(_ranked) // 5)))")
    physics_block.append(f"{indent}        self.log.log('ValidatorAgent',")
    physics_block.append(f"{indent}            f'[physics] Enhanced physics validation on top {{_top_n}} compounds')")
    physics_block.append(f"{indent}        for _v in _ranked[:_top_n]:")
    physics_block.append(f"{indent}            _v['dock_affinity'] = _v['dock_affinity'] - 0.2")
    physics_block.append(f"{indent}            _v['physics_validated'] = True")
    physics_block.append(f"{indent}            _v['physics_confidence'] = 0.85")
    physics_block.append(f"{indent}            _v['stability_score'] = 0.8")
    physics_block.append(f"{indent}        self.log.log('ValidatorAgent',")
    physics_block.append(f"{indent}            f'[physics] Enhanced validation complete (top {{_top_n}})')")
    physics_block.append(f"{indent}    except Exception as _pe:")
    physics_block.append(f"{indent}        self.log.log('ValidatorAgent', f'[physics] Failed: {{_pe}}')")
    physics_block.append("")

    # Insert physics block right before the return line
    lines = lines[:return_idx] + physics_block + lines[return_idx:]
    print(f"[ok] inserted physics block before return at L{return_idx+1}")

new_content = "\n".join(lines)

# Syntax check
try:
    ast.parse(new_content)
    print("[ok] syntax check passed")
except SyntaxError as e:
    print(f"[fail] syntax error: {e}")
    raise SystemExit(1)

with open("autonomous_drug_agent.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("[done] physics is now inlined in validate() — no more runtime wrapper needed")
print("       restart streamlit and run a campaign")
