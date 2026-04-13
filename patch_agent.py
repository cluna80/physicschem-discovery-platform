with open('autonomous_drug_agent.py','r',encoding='utf-8') as f:
    c=f.read()

c=c.replace("open(logfile, 'w') as","open(logfile, 'w', encoding='utf-8') as")
c=c.replace("open(self.logfile, 'a') as","open(self.logfile, 'a', encoding='utf-8') as")

# Replace every non-ASCII character
out=[]
for ch in c:
    if ord(ch)<128:
        out.append(ch)
    else:
        subs={
            '\u2550':'=','\u2500':'-','\u2551':'|',
            '\u2554':'+','\u2557':'+','\u255a':'+','\u255d':'+',
            '\u2560':'+','\u2563':'+','\u256c':'+',
            '\u2605':'*','\u2606':'*',
            '\u2713':'OK','\u2717':'XX','\u26a0':'!!',
            '\u2192':'->','\u2014':'-','\u2019':"'",
        }
        out.append(subs.get(ch,'?'))

c=''.join(out)
with open('autonomous_drug_agent.py','w',encoding='utf-8') as f:
    f.write(c)
print('Patched OK')
