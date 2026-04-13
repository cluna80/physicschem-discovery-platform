# -*- coding: utf-8 -*-
import subprocess

# Load binding site
with open("hiv_binding_site.txt", 'r') as f:
    coords = f.read().strip().split(',')
    binding_site = (float(coords[0]), float(coords[1]), float(coords[2]))

print(f"Binding site: ({binding_site[0]:.1f}, {binding_site[1]:.1f}, {binding_site[2]:.1f})")

# Test with CURE_4G_003 (known working)
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
    "--out", "test_working.pdbqt",
    "--num_modes", "9",
    "--exhaustiveness", "16",
    "--cpu", "4"
]

print("Testing CURE_4G_003...")
result = subprocess.run(cmd, capture_output=True, text=True)

print("\nOutput:")
for line in result.stdout.split('\n'):
    if 'mode' in line.lower() or (line.strip() and line.strip()[0].isdigit()):
        print(line)

# Parse affinity
for line in result.stdout.split('\n'):
    if line.strip() and line.strip()[0].isdigit():
        parts = line.strip().split()
        if len(parts) >= 2:
            print(f"\nAffinity: {parts[1]} kcal/mol")
            break
