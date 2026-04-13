with open('autonomous_drug_agent.py','r',encoding='utf-8') as f: c=f.read()

# Replace unsafe N-N/N-O linkers with safe carbon/ether linkers
old_linkers = '"linkers":  ["CC","CCC","CCCC","CCO","CCN","CCNC"],'
new_linkers = '"linkers":  ["CC","CCC","CCCC","CCO","CCCC","CCC"],'
c=c.replace(old_linkers, new_linkers, 1)

# Replace unsafe merge linkers - remove empty string and N/O direct bonds
old_merge = 'linkers = ["","C","CC","CCC","N","NC","O","OC"]'
new_merge = 'linkers = ["C","CC","CCC","CCCC","CCO","COC","CNC"]'
c=c.replace(old_merge, new_merge, 1)

with open('autonomous_drug_agent.py','w',encoding='utf-8') as f: f.write(c)
print('Linkers patched - removed N-N, N-O, direct bonds')
