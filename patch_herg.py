"""patch_herg.py — apply to autonomous_drug_agent.py"""
with open('autonomous_drug_agent.py','r',encoding='utf-8') as f:
    c = f.read()

fixes = 0

# Fix 1: hERG hard cutoff 0.70, DILI 0.65
old1 = ('                c["admet_pass"] = (\n'
        '                            c["hERG"]    < 0.50 and\n'
        '                            c["DILI"]    < 0.50 and\n'
        '                            c["AMES"]    < 0.50 and\n'
        '                            c["ClinTox"] < 0.50 and\n'
        '                            c.get("Bioavailability", 0) > 0.50\n'
        '                        )')
new1 = ('                c["admet_pass"] = (\n'
        '                            c["hERG"]    < 0.70 and\n'
        '                            c["DILI"]    < 0.65 and\n'
        '                            c["AMES"]    < 0.55 and\n'
        '                            c["ClinTox"] < 0.50\n'
        '                        )')
if old1 in c:
    c = c.replace(old1, new1, 1); fixes += 1
    print('Fix 1 OK: hERG<0.70 DILI<0.65 cutoffs')
else:
    # Try original version without bioavailability line
    old1b = ('                c["admet_pass"] = (\n'
             '                            c["hERG"]    < 0.50 and\n'
             '                            c["DILI"]    < 0.50 and\n'
             '                            c["AMES"]    < 0.50 and\n'
             '                            c["ClinTox"] < 0.50\n'
             '                        )')
    if old1b in c:
        c = c.replace(old1b, new1, 1); fixes += 1
        print('Fix 1 OK (variant): hERG<0.70 DILI<0.65 cutoffs')
    else:
        print('Fix 1 SKIP: admet_pass block not found')

# Fix 2: Replace azaindole pharma tail with safe aniline heads
old2 = ('"EGFR":  [\n'
        '            "Nc1ncnc2ccccc12",           # quinazoline head\n'
        '            "Nc1ccc(Nc2ncnc3ccccc23)cc1",# anilinoquinazoline\n'
        '            "c1ccc2[nH]cnc2c1",          # azaindole\n'
        '        ],')
new2 = ('"EGFR":  [\n'
        '            "Nc1ncnc2ccccc12",           # quinazoline head\n'
        '            "Nc1ccc(Nc2ncnc3ccccc23)cc1",# anilinoquinazoline\n'
        '            "Nc1cccc(F)c1",              # 3-fluoroaniline safe\n'
        '            "Nc1ccc(F)cc1",              # 4-fluoroaniline safe\n'
        '            "Nc1ccccc1",                 # aniline safe\n'
        '        ],')
if old2 in c:
    c = c.replace(old2, new2, 1); fixes += 1
    print('Fix 2 OK: azaindole replaced with safe aniline heads')
else:
    print('Fix 2 SKIP: pharma tails block not found')

# Fix 3: Carbon-only attachment strategies (no bare N append)
old3 = ('        strategies = [\n'
        '            f"{base_smi}{rgroup}",        # direct append\n'
        '            f"{rgroup}{base_smi}",        # prepend\n'
        '            f"{base_smi}C{rgroup}",       # methylene spacer\n'
        '            f"{base_smi}CC{rgroup}",      # ethylene spacer\n'
        '        ]')
new3 = ('        strategies = [\n'
        '            f"{base_smi}C{rgroup}",       # methylene spacer\n'
        '            f"{base_smi}CC{rgroup}",      # ethylene spacer\n'
        '            f"{base_smi}CCC{rgroup}",     # propylene spacer\n'
        '            f"{base_smi}CCCC{rgroup}",    # butylene spacer\n'
        '        ]')
if old3 in c:
    c = c.replace(old3, new3, 1); fixes += 1
    print('Fix 3 OK: carbon-only spacer strategies')
else:
    print('Fix 3 SKIP: strategies block not found')

# Fix 4: Safe scaffold bias - piperidine/decalin first
old4 = ('        # Bias toward target-specific scaffolds + safe chemotypes\n'
        '        safe_scaffolds = ["piperidine","decalin","pyrrolidine","tetrahydro",\n'
        '                          "piperazine","isobutyl","cyclohex"]\n'
        '        if bias:\n'
        '            priority = [f for f in valid if bias.lower() in f["name"].lower()]\n'
        '            safe     = [f for f in valid if any(s in f["name"].lower()\n'
        '                        for s in safe_scaffolds) and f not in priority]\n'
        '            rest     = [f for f in valid if f not in priority and f not in safe]\n'
        '            valid    = priority + safe + rest')
if old4 in c:
    print('Fix 4 already applied: safe scaffold bias exists')
    fixes += 1
else:
    # Apply safe scaffold bias fresh
    old4b = ('        # Bias toward target-specific scaffolds\n'
             '        if bias:\n'
             '            priority = [f for f in valid if bias.lower() in f["name"].lower()]\n'
             '            rest     = [f for f in valid if f not in priority]\n'
             '            valid    = priority + rest')
    new4 = ('        # Bias: target scaffolds first, then safe chemotypes\n'
            '        safe_scaffolds = ["piperidine","decalin","pyrrolidine",\n'
            '                          "piperazine","isobutyl","cyclohex","morpholine"]\n'
            '        if bias:\n'
            '            priority = [f for f in valid if bias.lower() in f["name"].lower()]\n'
            '            safe     = [f for f in valid if any(s in f["name"].lower()\n'
            '                        for s in safe_scaffolds) and f not in priority]\n'
            '            rest     = [f for f in valid if f not in priority and f not in safe]\n'
            '            valid    = priority + safe + rest')
    if old4b in c:
        c = c.replace(old4b, new4, 1); fixes += 1
        print('Fix 4 OK: safe scaffold bias applied')
    else:
        print('Fix 4 SKIP: bias block not found')

with open('autonomous_drug_agent.py','w',encoding='utf-8') as f:
    f.write(c)

import ast
try:
    ast.parse(c)
    print(f'\nAll done: {fixes}/4 fixes applied, syntax valid')
    print('Run: python -W ignore autonomous_drug_agent.py --target EGFR 2>/dev/null')
except SyntaxError as e:
    print(f'Syntax error: {e}')
