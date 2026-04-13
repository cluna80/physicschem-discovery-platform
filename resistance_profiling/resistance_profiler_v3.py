#!/usr/bin/env python3
import subprocess, os, json

PROTEIN     = "../gromacs_md_simulation/protein_ready.pdb"
LIGAND      = "../docking_results/CURE_17G_002_out.pdbqt"
GNINA       = "../gnina_cu11"
BOX         = "-center_x -9.0 -center_y 30.5 -center_z 29.0 -size_x 25 -size_y 25 -size_z 25"

MUTATIONS = [
    ("A", 30, "ASP", "ASN", "D30N"),
    ("A", 90, "LEU", "MET", "L90M"),
    ("A", 82, "VAL", "ALA", "V82A"),
    ("A", 50, "ILE", "VAL", "I50V"),
    ("A", 48, "GLY", "VAL", "G48V"),
]

def mutate_pdb(src, chain, resnum, orig3, mut3, dst):
    backbone = {"N", "CA", "C", "O", "CB"}
    out = []
    for line in open(src):
        if line.startswith("ATOM"):
            if (line[21]==chain and int(line[22:26])==resnum and line[17:20].strip()==orig3):
                if line[12:16].strip() not in backbone:
                    continue
                line = line[:17] + mut3.ljust(3) + line[20:]
        out.append(line)
    open(dst,"w").writelines(out)

def parse_scores(pdbqt):
    """Use strings to read binary pdbqt, grab first VINA RESULT line"""
    r = subprocess.run(f"strings {pdbqt} | grep 'VINA RESULT' | head -1",
                       shell=True, capture_output=True, text=True)
    vina, cnn = None, None
    if r.stdout.strip():
        parts = r.stdout.strip().split()
        try: vina = float(parts[3])
        except: pass
    # CNN score from gnina stdout saved to log
    log = pdbqt.replace(".pdbqt", ".log")
    if os.path.exists(log):
        for line in open(log):
            if "CNNscore" in line or "cnn_score" in line.lower():
                try: cnn = float(line.split()[-1])
                except: pass
    return vina, cnn

def run_docking(prot_pdb, label):
    os.makedirs("docking_out", exist_ok=True)
    out   = f"docking_out/out_{label}.pdbqt"
    log   = f"docking_out/out_{label}.log"
    prot_pdbqt = f"docking_out/prot_{label}.pdbqt"

    # Convert protein
    subprocess.run(f"obabel {prot_pdb} -O {prot_pdbqt} -h 2>/dev/null",
                   shell=True, capture_output=True)

    cmd = (f"{GNINA} -r {prot_pdbqt} -l {LIGAND} {BOX} "
           f"--num_modes 3 --exhaustiveness 8 --no_gpu "
           f"-o {out} 2>&1 | tee {log}")
    subprocess.run(cmd, shell=True, capture_output=False)

    vina, cnn = parse_scores(out)

    # Also scrape log for CNN
    if os.path.exists(log) and cnn is None:
        for line in open(log):
            if "CNNscore" in line:
                try: cnn = float(line.split()[-1])
                except: pass
    return vina, cnn

# ── Main ───────────────────────────────────────────────────────
os.makedirs("mutant_pdbs", exist_ok=True)
print("=" * 62)
print("  HIV Protease Resistance Profiling — CURE_17G_002")
print("=" * 62)

results = {}

# Wild type
print("\n[1/6] Wild type...")
vina, cnn = run_docking(PROTEIN, "WT")
results["Wild_Type"] = {"vina": vina, "cnn": cnn}
wt_vina = vina or -7.753
print(f"  WT  Vina={vina}  CNN={cnn}")

# Mutants
for i, (chain, resnum, orig3, mut3, label) in enumerate(MUTATIONS):
    print(f"\n[{i+2}/6] {label}...")
    mut_pdb = f"mutant_pdbs/protein_{label}.pdb"
    mutate_pdb(PROTEIN, chain, resnum, orig3, mut3, mut_pdb)
    vina, cnn = run_docking(mut_pdb, label)
    results[label] = {"vina": vina, "cnn": cnn}
    print(f"  {label}  Vina={vina}  CNN={cnn}")

# Table
print("\n" + "=" * 65)
print(f"{'Variant':<10} {'Vina':>8} {'CNN':>8} {'ΔVina':>8}  Status")
print("-" * 65)
for name, r in results.items():
    v = r["vina"] or 0
    c = r["cnn"] or 0
    d = v - wt_vina if name != "Wild_Type" else 0
    if name == "Wild_Type":   status = "◆ Reference"
    elif d > 1.5:             status = "🔴 RESISTANT"
    elif d > 0.5:             status = "🟡 Reduced"
    else:                     status = "✅ Active"
    print(f"{name:<10} {v:>8.3f} {c:>8.4f} {d:>8.3f}  {status}")

json.dump(results, open("resistance_results.json","w"), indent=2)
print("\nSaved → resistance_results.json")
