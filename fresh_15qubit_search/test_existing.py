#!/usr/bin/env python3
import subprocess
import os

print("="*80)
print("🔬 TESTING EXISTING PDBQT FILES")
print("="*80)

# Known working PDBQT files
working_files = [
    "docking_results/naphthalene_35diF.pdbqt",
    "docking_results/indole_metaCF3.pdbqt",
    "docking_results/isoquinoline_35diF.pdbqt",
]

RECEPTOR = "../resistance_profiling/docking_out/prot_WT.pdbqt"
REF_LIGAND = "../resistance_profiling/ligand_split_1.pdbqt"

for pdbqt_file in working_files:
    if not os.path.exists(pdbqt_file):
        print(f"❌ {pdbqt_file} not found")
        continue
    
    print(f"\nTesting {pdbqt_file}...")
    output_file = f"test_{os.path.basename(pdbqt_file).replace('.pdbqt', '_out.pdbqt')}"
    
    cmd = f"../gnina_cu11 --no_gpu -r {RECEPTOR} -l {pdbqt_file} --autobox_ligand {REF_LIGAND} --autobox_add 6 --num_modes 3 --exhaustiveness 6 --cpu 6 -o {output_file} 2>/dev/null"
    
    subprocess.run(cmd, shell=True, timeout=180)
    
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            for line in f:
                if "REMARK Vina score:" in line:
                    print(f"   ✅ Score: {line.strip()}")
                    break
    else:
        print("   ❌ Failed")

print("\n" + "="*80)
