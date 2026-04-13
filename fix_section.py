with open('complete_quantum_drug_discovery.py', 'r') as f:
    lines = f.readlines()

# Find and replace the problematic section
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Check if we're at the get_original section
    if '@app.route(\'/api/get_original\'' in line:
        new_lines.append(line)  # Add the route
        i += 1
        # Skip the next line if it's the duplicate def
        if i < len(lines) and 'def get_original' in lines[i]:
            new_lines.append('def get_original():\n')
            i += 1
        # Add the return statement
        new_lines.append('    return jsonify(ORIGINAL_DISCOVERY)\n')
        # Skip any existing return statements
        while i < len(lines) and ('return' in lines[i] or 'def get_library' in lines[i] or '@app.route' in lines[i]):
            if 'def get_library' in lines[i]:
                break
            i += 1
        continue
    new_lines.append(line)
    i += 1

with open('complete_quantum_drug_discovery.py', 'w') as f:
    f.writelines(new_lines)

print("✅ File fixed!")
