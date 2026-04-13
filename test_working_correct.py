# -*- coding: utf-8 -*-
import subprocess

with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print("="*80)
print("TESTING CURE_4G_003 WITH CORRECT BINDING SITE")
print("="*80)
print(f"Binding site: ({binding_site[0]:.3f}, {binding_site[1]:.3f}, {binding_site[2]:.3f})")
print("-"*80)

cmd = [
    "./bin/vina.exe",
    "--receptor", "hiv_protease.pdbqt",
    "--ligand", "CURE_4G_003.pdbqt",
    "--center_x", str(binding_site[0]),
    "--center_y", str(binding_site[1]),
    "--center_z", str(binding_site[2]),
    "--size_x", "25",
    "--size_y", "25",
    "--size_z", "25",
    "--out", "test_correct_site.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "16",
    "--cpu", "4"
]

print("\nRunning docking...")
result = subprocess.run(cmd, capture_output=True, text=True)

print("\nBinding Affinities:")
for line in result.stdout.split('\n'):
    if line.strip() and line.strip()[0].isdigit():
        parts = line.strip().split()
        if len(parts) >= 2:
            print(f"  Mode {parts[0]}: {parts[1]} kcal/mol")

print("\n" + "="*80)
