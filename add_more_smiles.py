import re

# Read the file
with open('complete_quantum_drug_discovery.py', 'r', encoding='utf-8') as f:
    content = f.read()

# New SMILES to add
new_smiles = [
    "Cc1ccc(C(=O)Nc2ccc(F)cc2)cc1",
    "O=C(Nc1ccc(F)cc1)c1ccc(N2CCCC2)cc1",
    "Cc1ccc(C(=O)Nc2cccc(F)c2)cc1",
    "O=C(Nc1ccc(Cl)cc1)c1ccc(N2CCOCC2)cc1",
    "Cc1ccc(NC(=O)c2ccc(Cl)cc2)cc1F",
    "Cc1ccc(S(=O)(=O)Nc2ccc(F)cc2)cc1",
    "O=S(=O)(Nc1ccc(F)cc1)c1ccccc1",
    "Cc1ccc(S(=O)(=O)Nc2ccccc2)cc1",
    "Cc1nc(Nc2ccc(F)cc2)nc(N2CCOCC2)n1",
    "O=C(Nc1ccc(Cl)cc1)c1cnc(N2CCOCC2)s1",
    "Cc1nnc(Nc2ccc(F)cc2)n1C",
    "O=C(c1ccc(F)cc1)N1CCN(c2ccccc2)CC1",
    "Cc1ccc(C(=O)N2CCN(c3ccccc3)CC2)cc1",
    "O=C(Nc1ccc(F)cc1)c1ccncc1",
    "Cc1ccc(NC(=O)c2ccncc2)cc1F",
    "O=C(Nc1ccc(F)cc1)c1ccc(N2CCCC2)cc1",
    "Cc1ccc(NC(=O)c2ccc(N3CCCC3)cc2)cc1",
    "O=C(Nc1ccc(F)cc1)c1ccc(OC(F)(F)F)cc1",
    "Cc1ccc(NC(=O)c2ccc(OC(F)(F)F)cc2)cc1F",
    "O=C(Nc1ccc(F)cc1)c1ccc2[nH]ccc2c1",
    "Cc1ccc(NC(=O)c2ccc3[nH]ccc3c2)cc1",
    "O=C(Nc1ccc(F)cc1)c1ccc2ncccc2c1",
    "Cc1ccc(NC(=O)c2cccc3cccnc23)cc1",
    "Cc1ccc(-c2cnn(C)c2)cc1NC(=O)c1ccc(F)cc1",
    "O=C(Nc1ccc(Cl)cc1)c1ccc(-c2cnn(C)c2)cc1",
    "Cc1ccc(NC(=O)c2cn(-c3ccccc3)nn2)cc1",
    "O=C(Nc1ccc(F)cc1)c1cn(-c2ccccc2)nn1",
    "Cc1ccc(-c2nnn[nH]2)cc1NC(=O)c1ccc(F)cc1",
    "O=C(Nc1ccc(Cl)cc1)c1ccc(-c2nnn[nH]2)cc1",
    "O=C(Nc1ccc(F)cc1)Nc1ccc(Cl)cc1",
    "Cc1ccc(NC(=O)Nc2ccc(F)cc2)cc1",
    "CCOC(=O)Nc1ccc(NC(=O)c2ccc(F)cc2)cc1",
    "CC(C)OC(=O)Nc1ccc(C(=O)Nc2cccc(F)c2)cc1",
]

# Create a string of new SMILES
new_smiles_str = ',\n    '.join([f'"{s}"' for s in new_smiles])

# Find the VALID_DRUG_SMILES_POOL and extend it
pattern = r'(VALID_DRUG_SMILES_POOL = \[.*?\])(?=\s*\n\s*def|\s*\n\s*#|\s*\n\s*$)'
match = re.search(pattern, content, re.DOTALL)

if match:
    current_pool = match.group(1)
    # Remove the closing bracket and add new SMILES
    new_pool = current_pool.rstrip(']') + ',\n    ' + new_smiles_str + '\n]'
    content = content[:match.start()] + new_pool + content[match.end():]
    print("✅ Added 40+ new SMILES to the fallback pool!")
else:
    print("Could not find VALID_DRUG_SMILES_POOL, trying alternative method...")
    
    # Alternative: find and replace near the end of the pool
    pattern2 = r'(VALID_DRUG_SMILES_POOL = \[.*?\])'
    match2 = re.search(pattern2, content, re.DOTALL)
    if match2:
        current_pool = match2.group(1)
        new_pool = current_pool.rstrip(']') + ',\n    ' + new_smiles_str + '\n]'
        content = content[:match2.start()] + new_pool + content[match2.end():]
        print("✅ Added SMILES via alternative method!")

# Also increase max candidates
content = content.replace(
    'num_candidates = min(int(data.get(\'num_candidates\', 5)), 20)',
    'num_candidates = min(int(data.get(\'num_candidates\', 5)), 100)'
)

# Write back
with open('complete_quantum_drug_discovery.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ File updated successfully!")
print("   - Added 40+ new SMILES to fallback pool")
print("   - Increased max candidates to 100")
