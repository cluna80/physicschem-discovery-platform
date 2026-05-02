"""
show_me.py - pure diagnostic, no patching.
Dumps the exact lines around HIV_DIP tails, PHARMA_TAILS, and HISTORICAL_NULL
so we can see what the file actually looks like and write a one-shot fix.
"""
from pathlib import Path

FILE = "autonomous_drug_agent.py"
lines = Path(FILE).read_text(encoding="utf-8").splitlines()
print(f"[scan] File: {len(lines)} lines\n")

def show_context(label, predicate, context_before=2, context_after=8):
    """Print lines matching predicate plus surrounding context."""
    print(f"=" * 70)
    print(f"  {label}")
    print(f"=" * 70)
    hits = [i for i, ln in enumerate(lines) if predicate(ln)]
    if not hits:
        print("  (no matches)\n")
        return
    # group consecutive hits to avoid duplicate context blocks
    shown = set()
    for hit in hits:
        start = max(0, hit - context_before)
        end = min(len(lines), hit + context_after + 1)
        if any(s in shown for s in range(start, end)):
            continue
        for i in range(start, end):
            marker = " >>>" if i == hit else "    "
            print(f"  L{i+1:4d}{marker} {lines[i]}")
            shown.add(i)
        print()

# 1. Every line containing HIV_DIP
show_context(
    "ALL LINES CONTAINING 'HIV_DIP'",
    lambda ln: "HIV_DIP" in ln,
    context_before=1, context_after=3
)

# 2. PHARMA_TAILS dict
show_context(
    "PHARMA_TAILS DICT (looking for HIV_DIP key inside)",
    lambda ln: "PHARMA_TAILS" in ln,
    context_before=0, context_after=2
)

# 3. HISTORICAL_NULL (any case, also "historical_null")
show_context(
    "HISTORICAL_NULL / historical_null",
    lambda ln: "HISTORICAL_NULL" in ln or "historical_null" in ln,
    context_before=2, context_after=10
)

# 4. Higgs null distribution
show_context(
    "HIGGS NULL / fragment_null / historical_targets",
    lambda ln: any(s in ln for s in ["HIGGS_NULL", "fragment_null", "historical_targets", "HISTORICAL"]),
    context_before=2, context_after=6
)

print("=" * 70)
print("  DONE. Paste the full output above back into the chat.")
print("=" * 70)
