# -*- coding: utf-8 -*-
import subprocess

# List of potential EGFR inhibitor SMILES strings
inhibitors = {
    "gefitinib_like": "COC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC(=C(C=C3)Cl)Cl)OCCOC",
    "erlotinib_like": "COCCOC1=CC2=NC=NC(=C2C=C1OCCOC)NC3=CC=CC=C3",
    "simple_quinazoline": "C1=CC=C2C(=C1)C(=NC=N2)NC3=CC=C(C=C3)Cl"
}

for name, smiles in inhibitors.items():
    output = f"{name}.smi"
    with open(output, 'w') as f:
        f.write(f"{smiles}\t{name}\n")
    print(f"Created {output}")

print("\nTo convert to PDBQT, run:")
print("obabel gefitinib_like.smi -O gefitinib_like.pdbqt -xh")
print("obabel erlotinib_like.smi -O erlotinib_like.pdbqt -xh")
print("obabel simple_quinazoline.smi -O simple_quinazoline.pdbqt -xh")
