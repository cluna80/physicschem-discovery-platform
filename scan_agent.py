import sys, os

# Accept path as argument or default
path = sys.argv[1] if len(sys.argv) > 1 else "autonomous_drug_agent.py"

if not os.path.isfile(path):
    print(f"File not found: {path}")
    sys.exit(1)

with open(path, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print()

# Find all def/class definitions
print("=== All def/class definitions ===")
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
        print(f"  L{i:>4}: {s[:80]}")

print()

# Search for canonicalize anywhere
print("=== Lines containing 'canonicalize' ===")
for i, line in enumerate(lines, 1):
    if "canonicalize" in line.lower():
        print(f"  L{i:>4}: {line.rstrip()}")

print()

# Search for CANONICAL_CSV_COLUMNS
print("=== Lines containing 'CANONICAL_CSV_COLUMNS' ===")
for i, line in enumerate(lines, 1):
    if "CANONICAL_CSV_COLUMNS" in line:
        print(f"  L{i:>4}: {line.rstrip()}")

print()

# Show lines around 'confidence' assignment in what looks like a row-building function
print("=== Lines containing row[\"confidence\"] or row['confidence'] ===")
for i, line in enumerate(lines, 1):
    if 'row["confidence"]' in line or "row['confidence']" in line:
        # Show context
        start = max(0, i-5)
        end   = min(len(lines), i+3)
        print(f"  --- context around L{i} ---")
        for j in range(start, end):
            marker = ">>>" if j == i-1 else "   "
            print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()}")
        print()

# Search for dip_ already present
print("=== Lines containing 'dip_' ===")
dip_lines = [(i+1, l.rstrip()) for i, l in enumerate(lines) if "dip_" in l]
print(f"  Found {len(dip_lines)} lines")
for ln, content in dip_lines[:20]:
    print(f"  L{ln:>4}: {content[:100]}")
