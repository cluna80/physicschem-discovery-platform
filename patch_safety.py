with open('autonomous_drug_agent.py','r',encoding='utf-8') as f: c=f.read()

# Fix 1: Strengthen ADMET thresholds - fail hERG > 0.50 and DILI > 0.50
old_pass = '''                c["admet_pass"] = (
                            c["hERG"]    < 0.50 and
                            c["DILI"]    < 0.50 and
                            c["AMES"]    < 0.50 and
                            c["ClinTox"] < 0.50
                        )'''
new_pass = '''                c["admet_pass"] = (
                            c["hERG"]    < 0.50 and
                            c["DILI"]    < 0.50 and
                            c["AMES"]    < 0.50 and
                            c["ClinTox"] < 0.50 and
                            c.get("Bioavailability", 0) > 0.50
                        )'''
c=c.replace(old_pass, new_pass, 1)

# Fix 2: Add hERG/DILI penalty to confidence scoring
old_conf = '''            if c.get("admet_pass"):
                score += 25; reasons.append("ADMET pass")
            if c.get("hERG", 1) < 0.30:
                score += 10; reasons.append("hERG safe")
            if c.get("DILI", 1) < 0.30:
                score += 10; reasons.append("DILI safe")'''
new_conf = '''            if c.get("admet_pass"):
                score += 25; reasons.append("ADMET pass")
            # hERG graded scoring
            herg = c.get("hERG", 0.5)
            if herg < 0.30:
                score += 15; reasons.append("hERG safe")
            elif herg < 0.50:
                score += 8;  reasons.append("hERG low")
            elif herg > 0.80:
                score -= 15; reasons.append("hERG RISK")
            elif herg > 0.50:
                score -= 5;  reasons.append("hERG mod")
            # DILI graded scoring
            dili = c.get("DILI", 0.5)
            if dili < 0.30:
                score += 15; reasons.append("DILI safe")
            elif dili < 0.50:
                score += 8;  reasons.append("DILI low")
            elif dili > 0.80:
                score -= 15; reasons.append("DILI RISK")
            elif dili > 0.50:
                score -= 5;  reasons.append("DILI mod")'''
c=c.replace(old_conf, new_conf, 1)

# Fix 3: Bias fragment selection toward safe scaffolds
# Promote piperidine/decalin fragments (F036, F058, F076) over flat aromatics
old_bias = '''        # Bias toward target-specific scaffolds
        if bias:
            priority = [f for f in valid if bias.lower() in f["name"].lower()]
            rest     = [f for f in valid if f not in priority]
            valid    = priority + rest'''
new_bias = '''        # Bias toward target-specific scaffolds + safe chemotypes
        safe_scaffolds = ["piperidine","decalin","pyrrolidine","tetrahydro",
                          "piperazine","isobutyl","cyclohex"]
        if bias:
            priority = [f for f in valid if bias.lower() in f["name"].lower()]
            safe     = [f for f in valid if any(s in f["name"].lower()
                        for s in safe_scaffolds) and f not in priority]
            rest     = [f for f in valid if f not in priority and f not in safe]
            valid    = priority + safe + rest'''
c=c.replace(old_bias, new_bias, 1)

with open('autonomous_drug_agent.py','w',encoding='utf-8') as f: f.write(c)
import ast
try:
    ast.parse(c)
    print('Patched OK - hERG/DILI penalties active, safe scaffolds prioritised')
except SyntaxError as e:
    print(f'Error: {e}')
