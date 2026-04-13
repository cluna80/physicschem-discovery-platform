"""
prep_integrase.py
=================
Downloads HIV-1 Integrase PDB 3L2T and prepares hiv_integrase.pdbqt
for docking with AutoDock Vina.

USAGE:
    python prep_integrase.py
"""

import os, sys, subprocess, urllib.request, warnings
warnings.filterwarnings('ignore')

GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    print(f"  {color}{msg}{RST}")

def download_pdb(pdb_id: str, out_path: str) -> bool:
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    log(f"Downloading {pdb_id} from RCSB...")
    try:
        urllib.request.urlretrieve(url, out_path)
        log(f"Saved → {out_path}", GRN)
        return True
    except Exception as e:
        log(f"Download failed: {e}", RED)
        return False

def clean_pdb(in_path: str, out_path: str) -> bool:
    """Strip HETATM, waters, keep only protein ATOM records."""
    log("Cleaning PDB — removing waters, ligands, HETATM...")
    kept = []
    with open(in_path) as f:
        for line in f:
            rec = line[:6].strip()
            if rec == 'ATOM':
                kept.append(line)
            elif rec == 'TER':
                kept.append(line)
    if not kept:
        log("No ATOM records found!", RED)
        return False
    with open(out_path, 'w') as f:
        f.writelines(kept)
        f.write("END\n")
    log(f"Cleaned → {out_path}  ({len(kept)} ATOM lines)", GRN)
    return True

def pdb_to_pdbqt_obabel(in_path: str, out_path: str) -> bool:
    """Convert with Open Babel."""
    log("Converting to PDBQT with Open Babel...")
    for exe in ['obabel', 'obabel.exe']:
        try:
            result = subprocess.run(
                [exe, in_path, '-O', out_path,
                 '-xr',          # receptor mode
                 '--partialcharge', 'gasteiger'],
                capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.isfile(out_path):
                log(f"Open Babel succeeded → {out_path}", GRN)
                return True
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"obabel error: {e}", YLW)
    return False

def pdb_to_pdbqt_prepare4(in_path: str, out_path: str) -> bool:
    """Convert with AutoDock's prepare_receptor4.py."""
    log("Trying prepare_receptor4.py...")
    for script in ['prepare_receptor4.py', 'prepare_receptor.py']:
        try:
            result = subprocess.run(
                [sys.executable, script,
                 '-r', in_path, '-o', out_path,
                 '-A', 'hydrogens', '-U', 'nphs_lps_waters_nonstdres'],
                capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.isfile(out_path):
                log(f"prepare_receptor4 succeeded → {out_path}", GRN)
                return True
        except FileNotFoundError:
            pass
        except Exception as e:
            log(f"prepare_receptor4 error: {e}", YLW)
    return False

def make_minimal_pdbqt(in_path: str, out_path: str) -> bool:
    """
    Minimal PDB→PDBQT conversion — adds AD4 atom types.
    Works without obabel or AutoDock Tools.
    Based on AutoDock 4 atom type assignment rules.
    """
    log("Building minimal PDBQT (no external tools)...")

    # AutoDock4 atom type mapping
    ad4_types = {
        'C':  'C',  'CA': 'A',  'CB': 'C',  'CG': 'C',  'CD': 'C',
        'CE': 'C',  'CZ': 'A',  'N':  'N',  'ND': 'NA', 'NE': 'N',
        'NH': 'N',  'NZ': 'N',  'O':  'OA', 'OD': 'OA', 'OE': 'OA',
        'OG': 'OA', 'OH': 'OA', 'OXT':'OA', 'S':  'S',  'SD': 'SA',
        'SG': 'SA', 'SE': 'S',  'FE': 'Fe', 'ZN': 'Zn', 'CA2':'Ca',
        'MG': 'Mg', 'MN': 'Mn', 'CU': 'Cu', 'NA': 'Na', 'P':  'P',
    }

    lines_out = []
    try:
        with open(in_path) as f:
            for line in f:
                if not line.startswith('ATOM'):
                    if line.startswith('TER') or line.startswith('END'):
                        lines_out.append(line.rstrip() + '\n')
                    continue

                # Parse PDB ATOM record
                atom_name = line[12:16].strip()
                element   = line[76:78].strip() if len(line) > 76 else ''

                # Determine AD4 type
                ad4 = 'C'  # default
                if element in ('C','N','O','S','P','F','Cl','Br','I','H'):
                    type_map = {'C':'C','N':'N','O':'OA','S':'SA',
                                'P':'P','F':'F','Cl':'Cl','Br':'Br',
                                'I':'I','H':'HD'}
                    ad4 = type_map.get(element, 'C')
                else:
                    # Try atom name prefix
                    for k,v in ad4_types.items():
                        if atom_name.startswith(k):
                            ad4 = v
                            break

                # Build PDBQT line — columns 1-66 same as PDB, cols 71-76 charge, 77-78 AD4 type
                pdb_part = line[:66].rstrip()
                pdb_part = pdb_part.ljust(66)
                charge_str = "  0.000"
                out_line = f"{pdb_part}{charge_str}  {ad4:<2}\n"
                lines_out.append(out_line)

        with open(out_path, 'w') as f:
            f.writelines(lines_out)
            f.write("END\n")

        line_count = len([l for l in lines_out if l.startswith('ATOM')])
        log(f"Minimal PDBQT → {out_path}  ({line_count} atoms)", GRN)
        return True
    except Exception as e:
        log(f"Minimal conversion failed: {e}", RED)
        return False

def verify_pdbqt(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    with open(path) as f:
        content = f.read()
    atom_count = content.count('\nATOM')
    log(f"Verified {path}: {atom_count} ATOM records", GRN)
    return atom_count > 100

def main():
    print(f"\n{BLD}{CYN}HIV-1 Integrase Receptor Preparation{RST}")
    print(f"{CYN}PDB: 3L2T (Raltegravir-bound, 2.2Å){RST}")
    print("="*52)

    pdb_id   = "3L2T"
    raw_pdb  = "3L2T.pdb"
    clean    = "3L2T_clean.pdb"
    out_pdbqt = "hiv_integrase.pdbqt"

    # Skip if already done
    if os.path.isfile(out_pdbqt) and verify_pdbqt(out_pdbqt):
        log(f"\nhiv_integrase.pdbqt already exists and is valid.", GRN)
        print_docking_box()
        return

    # Step 1 — Download
    if not os.path.isfile(raw_pdb):
        if not download_pdb(pdb_id, raw_pdb):
            log("Cannot download PDB — check internet connection", RED)
            sys.exit(1)
    else:
        log(f"Using existing {raw_pdb}", YLW)

    # Step 2 — Clean
    if not clean_pdb(raw_pdb, clean):
        log("PDB cleaning failed", RED)
        sys.exit(1)

    # Step 3 — Convert (try multiple methods)
    success = (pdb_to_pdbqt_obabel(clean, out_pdbqt) or
               pdb_to_pdbqt_prepare4(clean, out_pdbqt) or
               make_minimal_pdbqt(clean, out_pdbqt))

    if not success:
        log("All conversion methods failed", RED)
        sys.exit(1)

    if not verify_pdbqt(out_pdbqt):
        log("PDBQT verification failed — file may be corrupt", RED)
        sys.exit(1)

    print(f"\n{BLD}{GRN}✓ hiv_integrase.pdbqt ready{RST}")
    print_docking_box()

def print_docking_box():
    print(f"""
  {BLD}Docking box (Raltegravir binding site):{RST}
    Center: x=-38.5  y=30.5  z=-20.8
    Size:   25 × 25 × 25 Å
    Mg2+ chelation residues: D64, D116, E152

  {BLD}Now validate your top leads:{RST}
    python validate_leads.py --target HIV_INTEGRASE --top 5
    python validate_leads.py --id OPT2_naph_metaCF3_HOP_007_HOP_026
""")

if __name__ == "__main__":
    main()
