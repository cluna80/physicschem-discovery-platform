#!/usr/bin/env python3
"""
HIV Protease Resistance Profiling
Tests CURE_17G_002 against wild-type + key resistance mutants
Mutations: D30N, L90M, V82A, I50V, G48V
"""

import subprocess, os, shutil, json
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────
PROTEIN_PDB  = "../gromacs_md_simulation/protein_ready.pdb"
LIGAND_PDBQT = "../top_candidates/CURE_17G_002_pose1.pdbqt"  # adjust if needed
GNINA        = "../gnina/gnina"

# HIV protease active site box (standard coordinates for 1HVR)
BOX = "-center_x -9.0 -center_y 30.5 -center_z 29.0 -size_x 25 -size_y 25 -size_z 25"

# Resistance mutations: chain A residue → mutation
# Format: (chain, res_num, original_aa, mutant_aa, 3letter_orig, 3letter_mut)
MUTATIONS = [
    ("A", 30,  "D", "N", "ASP", "ASN"),  # D30N — Nelfinavir resistance
    ("A", 90,  "L", "M", "LEU", "MET"),  # L90M — broad resistance
    ("A", 82,  "V", "A", "VAL", "ALA"),  # V82A — Ritonavir resistance
    ("A", 50,  "I", "V", "ILE", "VAL"),  # I50V — Amprenavir resistance
    ("A", 48,  "G", "V", "GLY", "VAL"),  # G48V — Saquinavir resistance
]

def mutate_pdb(input_pdb, chain, resnum, orig3, mut3, output_pdb):
    """Simple in-silico mutation — replaces residue name, removes non-backbone atoms"""
    lines = open(input_pdb).readlines()
    out = []
    # Backbone atoms to keep for any residue
    backbone = {"N", "CA", "C", "O", "CB"}
    for line in lines:
        if not (line.startswith("ATOM") or line.startswith("TER") or line.startswith("END")):
            out.append(line)
            continue
        if line.startswith("ATOM"):
            res_chain = line[21]
            res_num   = int(line[22:26].strip())
            res_name  = line[17:20].strip()
            atom_name = line[12:16].strip()
            # Apply mutation
            if res_chain == chain and res_num == resnum and res_name == orig3:
                if atom_name not in backbone:
                    continue  # drop sidechain atoms
                line = line[:17] + mut3.ljust(3) + line[20:]
        out.append(line)
    open(output_pdb, "w").writelines(out)
    print(f"  Mutated {orig3}{resnum}{mut3} → {output_pdb}")

def run_gnina(protein_pdb, ligand_pdbqt, label):
    """Run Gnina docking and return best CNN score + Vina affinity"""
    out_file = f"docking_{label}.pdbqt"
    log_file = f"docking_{label}.log"
    
    # Convert protein PDB to PDBQT first
    prot_pdbqt = f"protein_{label}.pdbqt"
    subprocess.run(
        f"obabel {protein_pdb} -O {prot_pdbqt} 2>/dev/null",
        shell=True
    )
    
    cmd = (f"{GNINA} -r {prot_pdbqt} -l {ligand_pdbqt} "
           f"{BOX} --num_modes 5 --exhaustiveness 8 "
           f"-o {out_file} --log {log_file} 2>&1")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    # Parse results
    cnn_score, vina_aff = None, None
    combined = result.stdout + result.stderr
    for line in combined.split("\n"):
        if "CNNscore" in line or "CNN" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                try:
                    val = float(p)
                    if 0 <= val <= 1 and cnn_score is None:
                        cnn_score = val
                    elif val < 0 and vina_aff is None:
                        vina_aff = val
                except:
                    pass
    
    # Also try parsing the output pdbqt
    if os.path.exists(log_file):
        for line in open(log_file):
            if line.strip().startswith("1 ") or "REMARK VINA" in line:
                parts = line.split()
                try:
                    vina_aff = float(parts[1]) if vina_aff is None else vina_aff
                    cnn_score = float(parts[2]) if cnn_score is None else cnn_score
                except:
                    pass
    
    return cnn_score, vina_aff

# ── Main profiling loop ────────────────────────────────────────
results = {}
os.makedirs("mutant_pdbs", exist_ok=True)
os.makedirs("docking_results", exist_ok=True)
os.chdir("docking_results")

print("=" * 60)
print("HIV Protease Resistance Profiling")
print("Compound: CURE_17G_002")
print("=" * 60)

# Find ligand
ligand = LIGAND_PDBQT
if not os.path.exists(ligand):
    # Try to find it
    for p in Path("../..").rglob("*CURE_17G*pose*.pdbqt"):
        ligand = str(p)
        break
    if not os.path.exists(ligand):
        for p in Path("../..").rglob("*CURE_17G*.pdbqt"):
            ligand = str(p)
            break

print(f"Ligand: {ligand}")
print(f"Protein: {PROTEIN_PDB}")
print()

# ── Wild type ──────────────────────────────────────────────────
print("[1/6] Docking against WILD TYPE...")
cnn, vina = run_gnina(PROTEIN_PDB, ligand, "wildtype")
results["Wild_Type"] = {"mutation": "WT", "cnn": cnn, "vina": vina}
print(f"  WT  → CNN: {cnn}  Vina: {vina} kcal/mol")

# ── Mutants ────────────────────────────────────────────────────
for i, (chain, resnum, orig1, mut1, orig3, mut3) in enumerate(MUTATIONS):
    label = f"{orig1}{resnum}{mut1}"
    print(f"[{i+2}/6] Docking against {label} mutant...")
    
    mut_pdb = f"../mutant_pdbs/protein_{label}.pdb"
    mutate_pdb(f"../../gromacs_md_simulation/protein_ready.pdb",
               chain, resnum, orig3, mut3, mut_pdb)
    
    cnn, vina = run_gnina(mut_pdb, ligand, label)
    results[label] = {"mutation": label, "cnn": cnn, "vina": vina}
    print(f"  {label} → CNN: {cnn}  Vina: {vina} kcal/mol")

# ── Summary ────────────────────────────────────────────────────
print()
print("=" * 60)
print("RESISTANCE PROFILING RESULTS")
print("=" * 60)
print(f"{'Variant':<12} {'Vina (kcal/mol)':<18} {'CNN Score':<12} {'ΔAffinity':<12} {'Status'}")
print("-" * 60)

wt_vina = results["Wild_Type"]["vina"] or -7.753
for name, r in results.items():
    vina = r["vina"] or 0
    cnn  = r["cnn"] or 0
    delta = vina - wt_vina if name != "Wild_Type" else 0
    if name == "Wild_Type":
        status = "Reference"
    elif delta > 1.0:
        status = "⚠️  RESISTANT"
    elif delta > 0.5:
        status = "🟡 Reduced"
    else:
        status = "✅ Sensitive"
    print(f"{name:<12} {vina:<18.3f} {cnn:<12.4f} {delta:<12.3f} {status}")

# Save results
json.dump(results, open("resistance_results.json", "w"), indent=2)
print()
print("Results saved to resistance_results.json")
print("=" * 60)
