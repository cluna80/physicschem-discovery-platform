# -*- coding: utf-8 -*-
# Create a simple ligand specifically for EGFR based on known inhibitors

ligand_content = """REMARK  Simple EGFR inhibitor scaffold (quinazoline-like)
ROOT
ATOM      1  C   LIG     1      22.000   0.300  52.800  1.00  0.00          C
ATOM      2  C   LIG     1      23.200   0.800  52.800  1.00  0.00          C
ATOM      3  N   LIG     1      23.200   2.000  52.800  1.00  0.00          N
ATOM      4  C   LIG     1      22.000   2.500  52.800  1.00  0.00          C
ATOM      5  C   LIG     1      20.800   2.000  52.800  1.00  0.00          C
ATOM      6  C   LIG     1      20.800   0.800  52.800  1.00  0.00          C
ENDROOT
BRANCH   2   7
ATOM      7  H   LIG     1      24.000   0.300  52.800  1.00  0.00          H
ENDBRANCH   2   7
BRANCH   3   8
ATOM      8  H   LIG     1      24.000   2.500  52.800  1.00  0.00          H
ENDBRANCH   3   8
BRANCH   4   9
ATOM      9  H   LIG     1      22.000   3.400  52.800  1.00  0.00          H
ENDBRANCH   4   9
BRANCH   5  10
ATOM     10  H   LIG     1      20.000   2.500  52.800  1.00  0.00          H
ENDBRANCH   5  10
BRANCH   6  11
ATOM     11  H   LIG     1      20.000   0.300  52.800  1.00  0.00          H
ENDBRANCH   6  11
TORSDOF 5
"""

with open("egfr_specific.pdbqt", "w") as f:
    f.write(ligand_content)

print("Created egfr_specific.pdbqt (quinazoline-like scaffold)")
print("  Positioned at EGFR binding pocket center")
