import sys, os

def extract_pocket(pdb_file="hiv_protease.pdb"):
    x, y, z = [], [], []
    skip = {"HOH", "WAT"}
    with open(pdb_file) as f:
        for line in f:
            if not line.startswith("HETATM"): continue
            if line[17:20].strip() in skip: continue
            try:
                x.append(float(line[30:38]))
                y.append(float(line[38:46]))
                z.append(float(line[46:54]))
            except: pass
    if not x:
        print("No ligand atoms found"); return
    c = (round(sum(x)/len(x),1), round(sum(y)/len(y),1), round(sum(z)/len(z),1))
    print(f"Binding pocket center: {c}")
    print(f"Atoms used: {len(x)}")
    open("hiv_binding_site.txt","w").write(f"{c[0]},{c[1]},{c[2]}")
    print("Saved to hiv_binding_site.txt")

extract_pocket()
