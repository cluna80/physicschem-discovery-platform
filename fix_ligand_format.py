# -*- coding: utf-8 -*-
import os

def fix_pdbqt_format(input_file, output_file):
    """Fix PDBQT formatting issues"""
    
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    atom_counter = 1
    
    for line in lines:
        if line.startswith("ATOM") or line.startswith("HETATM"):
            # Extract data
            name = line[12:16].strip()
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            element = name[0] if name else "C"
            
            # Create properly formatted PDBQT line
            new_line = f"ATOM  {atom_counter:5d} {name:<4s}LIG     1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:2s}\n"
            fixed_lines.append(new_line)
            atom_counter += 1
        else:
            fixed_lines.append(line)
    
    with open(output_file, 'w') as f:
        f.writelines(fixed_lines)
    
    print(f"Converted {input_file} -> {output_file}")
    print(f"  Processed {atom_counter-1} atoms")
    return output_file

# Fix the erlotinib-based ligand
if os.path.exists("egfr_ligand.pdbqt"):
    fix_pdbqt_format("egfr_ligand.pdbqt", "egfr_ligand_fixed.pdbqt")
else:
    print("egfr_ligand.pdbqt not found")

# Fix simple_test if it exists
if os.path.exists("simple_test.pdbqt"):
    fix_pdbqt_format("simple_test.pdbqt", "simple_test_fixed.pdbqt")
    
# Fix any other ligands
for ligand in ["final_ligand.pdbqt", "inhibitor.pdbqt"]:
    if os.path.exists(ligand):
        output = ligand.replace('.pdbqt', '_fixed.pdbqt')
        fix_pdbqt_format(ligand, output)
        
print("\nAll ligands fixed!")
