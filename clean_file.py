import re

# Read the file as binary to avoid encoding issues
with open('complete_quantum_drug_discovery.py', 'rb') as f:
    content = f.read().decode('utf-8', errors='ignore')

# Define the correct section
correct_section = '''
@app.route('/api/get_original', methods=['GET'])
def get_original():
    return jsonify(ORIGINAL_DISCOVERY)

@app.route('/api/get_library', methods=['GET'])
def get_library():
    """Get all saved drug candidates"""
    return jsonify({'library': ALL_DISCOVERIES, 'count': len(ALL_DISCOVERIES)})

@app.route('/api/get_targets', methods=['GET'])
def get_targets():
    return jsonify(DISEASE_TARGETS)

@app.route('/api/delete_candidate', methods=['POST'])
def delete_candidate():
    data = request.json or {}
    drug_id = data.get('id')
    global ALL_DISCOVERIES
    ALL_DISCOVERIES = [d for d in ALL_DISCOVERIES if d['id'] != drug_id]
    save_library()
    return jsonify({'status': 'deleted'})

@app.route('/api/clear_library', methods=['POST'])
def clear_library():
    global ALL_DISCOVERIES
    ALL_DISCOVERIES = []
    save_library()
    return jsonify({'status': 'cleared'})
'''

# Find and replace the problematic section
pattern = r'@app\.route\(\'/api/get_original\'.*?def clear_library\(\):.*?return jsonify'
match = re.search(pattern, content, re.DOTALL)
if match:
    new_content = content[:match.start()] + correct_section + content[match.end():]
    with open('complete_quantum_drug_discovery.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✅ File fixed successfully!")
else:
    print("Pattern not found. Let's try a different approach.")
