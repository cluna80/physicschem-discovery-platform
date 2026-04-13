"""Run this once in your project folder to fix dashboard.py"""
with open('dashboard.py','r',encoding='utf-8') as f: c=f.read()

# Fix 1: rename stream_agent -> run_agent
c = c.replace('def stream_agent(target, frags, iters, exh):',
              'def run_agent(target, frags, iters, exh):')

# Fix 2: fix the call site too (in case it still says stream_agent)
c = c.replace('target=stream_agent,', 'target=run_agent,')

# Fix 3: fix st.iframe -> components.v1.html
import re
c = re.sub(r'st\.iframe\(([^)]+),\s*scrolling=\w+\)',
           lambda m: f'st.components.v1.html({m.group(1)})', c)
c = re.sub(r'st\.iframe\(([^)]+)\)',
           lambda m: f'st.components.v1.html({m.group(1)})', c)

with open('dashboard.py','w',encoding='utf-8') as f: f.write(c)

import ast
try:
    ast.parse(c)
    print('dashboard.py fixed OK')
    print(f'  run_agent defined: {"def run_agent(" in c}')
    print(f'  stream_agent remaining: {"stream_agent" in c}')
    print(f'  st.iframe remaining: {c.count("st.iframe")}')
except SyntaxError as e:
    print(f'Syntax error {e.lineno}: {e}')
