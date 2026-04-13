"""
validate_leads.py
=================
Fast Vina docking validator for OPT compounds.
Docks specific SMILES directly — no fragment screening, no growing.

USAGE:
  python validate_leads.py --top 10              # top 10 from library by affinity
  python validate_leads.py --target HIV_INTEGRASE --top 5
  python validate_leads.py --id OPT2_naph_metaCF3_HOP_007_HOP_026
  python validate_leads.py --smiles "O=C(NCC..." --name "MyCompound"
"""

import os, sys, json, csv, sqlite3, subprocess, tempfile, argparse, warnings
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem, Descriptors
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False

GRN="\033[92m"; YLW="\033[93m"; CYN="\033[96m"
RED="\033[91m"; MAG="\033[95m"; RST="\033[0m"; BLD="\033[1m"

def log(msg, color=CYN):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {color}{BLD}Validator{RST}  {msg}")

# ── Target receptor configs ───────────────────────────────────────────
RECEPTOR_CONFIGS = {
    "HIV_INTEGRASE": {
        "receptor": "hiv_integrase.pdbqt",
        "center": [-38.5, 30.5, -20.8],
        "box":    [25.0, 25.0, 25.0],
        "ref":    "Dolutegravir",
        "ref_aff": -9.43,
    },
    "HIV": {
        "receptor": "hiv_protease.pdbqt",
        "center": [2.5, 4.5, -18.0],
        "box":    [25.0, 25.0, 25.0],
        "ref":    "Darunavir",
        "ref_aff": -10.4,
    },
    "EGFR": {
        "receptor": "egfr.pdbqt",
        "center": [-3.0, 52.0, 13.0],
        "box":    [25.0, 25.0, 25.0],
        "ref":    "Erlotinib",
        "ref_aff": -8.0,
    },
    "COVID_MPRO": {
        "receptor": "covid_mpro.pdbqt",
        "center": [-11.3, 13.5, 59.0],
        "box":    [25.0, 25.0, 25.0],
        "ref":    "Nirmatrelvir",
        "ref_aff": -7.8,
    },
    "BACE1": {
        "receptor": "bace1.pdbqt",
        "center": [5.0, 17.0, 25.0],
        "box":    [25.0, 25.0, 25.0],
        "ref":    "Verubecestat",
        "ref_aff": -8.5,
    },
}

def smiles_to_pdbqt(smiles: str, out_path: str) -> bool:
    """
    Convert SMILES to PDBQT using the same pipeline as autonomous_drug_agentV2.
    Priority: meeko API → mk_prepare_ligand CLI → obabel CLI
    """
    if not RDKIT_OK:
        log("RDKit not available", RED)
        return False
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            log(f"Invalid SMILES: {smiles[:50]}", RED)
            return False

        # 3D conformer generation
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 42
        if AllChem.EmbedMolecule(mol, params) != 0:
            AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        try:
            AllChem.MMFFOptimizeMolecule(mol, maxIters=2000)
        except Exception:
            AllChem.UFFOptimizeMolecule(mol)

        sdf_path = out_path.replace('.pdbqt', '.sdf')
        with Chem.SDWriter(sdf_path) as w:
            w.write(mol)

        # ── Method 1: meeko Python API (same as agent) ─────────────
        try:
            from meeko import MoleculePreparation, PDBQTWriterLegacy
            preparator = MoleculePreparation()
            mol_setups = preparator.prepare(mol)
            pdbqt_str, is_ok, err = PDBQTWriterLegacy.write_string(mol_setups[0])
            if is_ok and pdbqt_str:
                with open(out_path, 'w') as f:
                    f.write(pdbqt_str)
                log(f"  Prepared via meeko API", GRN)
                return True
        except Exception as e:
            pass

        # ── Method 2: mk_prepare_ligand CLI ───────────────────────
        for script in ['mk_prepare_ligand.py', 'mk_prepare_ligand']:
            try:
                r = subprocess.run(
                    [sys.executable, script, '-i', sdf_path, '-o', out_path],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and os.path.isfile(out_path):
                    log(f"  Prepared via {script}", GRN)
                    return True
            except FileNotFoundError:
                pass
            except Exception:
                pass

        # ── Method 3: obabel ──────────────────────────────────────
        for exe in ['obabel', 'obabel.exe']:
            try:
                r = subprocess.run(
                    [exe, sdf_path, '-O', out_path,
                     '--partialcharge', 'gasteiger'],
                    capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and os.path.isfile(out_path):
                    log(f"  Prepared via obabel", GRN)
                    return True
            except FileNotFoundError:
                pass
            except Exception:
                pass

        # ── Method 4: robust manual PDBQT (Vina-compatible) ─────
        try:
            conf = mol.GetConformer()
            ad4_map = {
                'C': 'C', 'N': 'N', 'O': 'OA', 'S': 'SA',
                'P': 'P', 'F': 'F', 'Cl': 'Cl', 'Br': 'Br', 'I': 'I',
            }
            lines = ['ROOT\n']
            atom_idx = 1
            for atom in mol.GetAtoms():
                if atom.GetAtomicNum() == 1:
                    continue  # skip H
                pos  = conf.GetAtomPosition(atom.GetIdx())
                sym  = atom.GetSymbol()
                arom = atom.GetIsAromatic()
                if sym == 'C' and arom:
                    ad4 = 'A'
                elif sym == 'O':
                    ad4 = 'OA'
                elif sym == 'S':
                    ad4 = 'SA'
                elif sym == 'N':
                    ad4 = 'NA' if atom.GetTotalNumHs() > 0 else 'N'
                else:
                    ad4 = ad4_map.get(sym, 'C')
                name = f"{sym}{atom_idx}"[:4].ljust(4)
                line = (f"ATOM  {atom_idx:5d} {name} LIG A   1    "
                        f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}"
                        f"  1.00  0.00     0.000 {ad4}\n")
                lines.append(line)
                atom_idx += 1
            lines.append('ENDROOT\n')
            lines.append('TORSDOF 0\n')
            with open(out_path, 'w') as f:
                f.writelines(lines)
            log(f"  Prepared via manual PDBQT ({atom_idx-1} heavy atoms)", YLW)
            return True
        except Exception as e:
            log(f"  manual fallback: {e}", RED)

        log("All PDBQT prep methods failed", RED)
        return False

    except Exception as e:
        log(f"Prep error: {e}", RED)
        return False

def run_vina(receptor: str, ligand_pdbqt: str,
             center: list, box: list,
             exhaustiveness: int = 8) -> float:
    """Run AutoDock Vina and return best affinity."""
    out_path = ligand_pdbqt.replace('.pdbqt', '_result.pdbqt')

    vina_exe = None
    import shutil
    candidates = [
        './bin/vina.exe', './bin/vina',      # project bin/ folder
        'vina.exe', 'vina',                  # current directory
        './vina.exe', './vina',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'vina.exe'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', 'vina'),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            vina_exe = candidate
            break
    if not vina_exe:
        vina_exe = shutil.which('vina') or shutil.which('vina.exe')
    if not vina_exe:
        log("Vina not found — checked ./bin/vina.exe, ./vina.exe, PATH", RED)
        return None
    log(f"Using Vina: {vina_exe}", CYN)

    cmd = [
        vina_exe,
        '--receptor', receptor,
        '--ligand', ligand_pdbqt,
        '--out', out_path,
        '--center_x', str(center[0]),
        '--center_y', str(center[1]),
        '--center_z', str(center[2]),
        '--size_x', str(box[0]),
        '--size_y', str(box[1]),
        '--size_z', str(box[2]),
        '--exhaustiveness', str(exhaustiveness),
        '--num_modes', '5',
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300)

        # Parse affinity from Vina output
        # Vina output table looks like:   "   1        -8.5      0.000      0.000"
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped: continue
            parts = stripped.split()
            if len(parts) >= 2 and parts[0] == '1':
                try:
                    val = float(parts[1])
                    # Vina returns +10.000 on error (bad ligand/box)
                    if val < 0:
                        return val
                    else:
                        log(f"Vina returned positive value ({val}) — "
                            f"ligand may be outside box or malformed", YLW)
                        return None
                except ValueError:
                    pass

        # Try parsing from output file
        if os.path.isfile(out_path):
            with open(out_path) as f:
                for line in f:
                    if 'REMARK VINA RESULT' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            try:
                                return float(parts[3])
                            except ValueError:
                                pass

        log(f"Could not parse Vina output", YLW)
        return None
    except subprocess.TimeoutExpired:
        log(f"Vina timed out", YLW)
        return None
    except Exception as e:
        log(f"Vina error: {e}", RED)
        return None

def load_compounds(db_path: str, compound_ids=None,
                   target=None, top_n=10) -> list:
    """Load compounds from library for validation."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if compound_ids:
        placeholders = ','.join('?' * len(compound_ids))
        rows = conn.execute(
            f"SELECT * FROM compounds WHERE id IN ({placeholders})",
            compound_ids).fetchall()
    elif target:
        rows = conn.execute(
            "SELECT * FROM compounds WHERE target=? "
            "ORDER BY dock_affinity ASC LIMIT ?",
            (target, top_n)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM compounds ORDER BY dock_affinity ASC LIMIT ?",
            (top_n,)).fetchall()

    conn.close()
    return [dict(r) for r in rows]

def validate_compound(compound: dict, config: dict,
                      exhaustiveness: int = 8,
                      work_dir: str = '.') -> dict:
    """Validate a single compound via Vina docking."""
    smiles = compound.get('smiles', '')
    cid    = compound.get('id', 'UNK')
    est_aff = float(compound.get('dock_affinity', 0) or 0)

    if not smiles:
        return {**compound, 'vina_affinity': None, 'validated': False}

    receptor = config['receptor']
    if not os.path.isfile(receptor):
        log(f"Receptor not found: {receptor}", RED)
        return {**compound, 'vina_affinity': None, 'validated': False}

    log(f"Validating {cid}  (estimated: {est_aff:.3f} kcal/mol)", CYN)

    # Prepare ligand
    pdbqt_path = os.path.join(work_dir, f"val_{cid[:20]}.pdbqt")
    prepared = smiles_to_pdbqt(smiles, pdbqt_path)

    if not prepared:
        log(f"  Prep failed for {cid}", YLW)
        return {**compound, 'vina_affinity': None, 'validated': False}

    # Dock
    aff = run_vina(receptor, pdbqt_path,
                   config['center'], config['box'], exhaustiveness)

    # Cleanup
    for f in [pdbqt_path,
              pdbqt_path.replace('.pdbqt', '.sdf'),
              pdbqt_path.replace('.pdbqt', '_result.pdbqt')]:
        try: os.remove(f)
        except: pass

    result = {**compound, 'vina_affinity': aff, 'validated': aff is not None}
    if aff is not None:
        delta = aff - est_aff
        flag = GRN+"✓ CONFIRMED" if aff <= est_aff*0.8 else \
               GRN+"✓ STRONG" if aff <= -9.0 else \
               YLW+"~ MODERATE" if aff <= -7.0 else RED+"✗ WEAK"
        log(f"  {flag}{RST}  Vina={aff:.3f}  Estimated={est_aff:.3f}  Δ={delta:+.3f}", GRN)
    return result

def main():
    parser = argparse.ArgumentParser(
        description="PhysicsChem Lead Validator — Direct Vina Docking")
    parser.add_argument("--id", nargs="+", help="Compound IDs to validate")
    parser.add_argument("--smiles", help="Validate a specific SMILES string")
    parser.add_argument("--name",   default="CUSTOM", help="Name for --smiles")
    parser.add_argument("--target", default=None,
        help="Target to validate (HIV_INTEGRASE, EGFR, HIV, ...)")
    parser.add_argument("--top",    type=int, default=5,
        help="Top N compounds by estimated affinity (default: 5)")
    parser.add_argument("--exhaustiveness", type=int, default=8)
    parser.add_argument("--db",     default="fragment_library.db")
    args = parser.parse_args()

    print(f"\n{BLD}{CYN}PhysicsChem Lead Validator v3.0{RST}")
    print(f"{CYN}Direct Vina Docking — No Fragment Screening{RST}")
    print("="*60)

    # Build compound list
    compounds = []
    if args.smiles:
        compounds = [{'id': args.name, 'smiles': args.smiles,
                      'target': args.target or 'HIV_INTEGRASE',
                      'dock_affinity': 0}]
    elif args.id:
        compounds = load_compounds(args.db, compound_ids=args.id)
        if not compounds:
            # Try from OPT CSV files
            for csv_path in sorted(Path('.').glob('agent_results_OPT_*.csv'),
                                   key=os.path.getmtime, reverse=True):
                with open(csv_path) as f:
                    for row in csv.DictReader(f):
                        if row.get('id') in args.id:
                            compounds.append({
                                'id': row['id'],
                                'smiles': row.get('smiles',''),
                                'target': row.get('target','HIV_INTEGRASE'),
                                'dock_affinity': float(row.get('dock_affinity',0) or 0)
                            })
    else:
        compounds = load_compounds(args.db, target=args.target, top_n=args.top)

    if not compounds:
        print(f"{RED}No compounds found to validate{RST}")
        sys.exit(1)

    log(f"Validating {len(compounds)} compound(s)", BLD+CYN)

    # Determine receptor config
    results = []
    for c in compounds:
        tgt    = (args.target or c.get('target','HIV_INTEGRASE')).upper()
        # Map OPT_ targets back to their actual target
        if tgt.startswith('OPT_'):
            tgt = 'HIV_INTEGRASE'

        config = RECEPTOR_CONFIGS.get(tgt)
        if not config:
            # Try partial match
            for k in RECEPTOR_CONFIGS:
                if k in tgt:
                    config = RECEPTOR_CONFIGS[k]
                    break
        if not config:
            config = RECEPTOR_CONFIGS['HIV_INTEGRASE']
            log(f"Unknown target {tgt}, defaulting to HIV_INTEGRASE", YLW)

        result = validate_compound(c, config, args.exhaustiveness)
        results.append(result)

    # Summary
    validated = [r for r in results if r.get('validated')]
    print(f"\n{BLD}{'='*60}{RST}")
    print(f"{BLD}VALIDATION SUMMARY{RST}")
    print(f"{'='*60}")
    print(f"  Compounds attempted: {len(results)}")
    print(f"  Successfully docked: {len(validated)}")
    print()

    if validated:
        validated.sort(key=lambda x: x.get('vina_affinity', 0))
        ref_aff = RECEPTOR_CONFIGS.get(
            (args.target or 'HIV_INTEGRASE').upper(), {}
        ).get('ref_aff', -9.0)

        print(f"  {'ID':<35} {'Vina':>8} {'Est':>8} {'vs Ref':>8}")
        print(f"  {'-'*60}")
        for r in validated:
            va  = r.get('vina_affinity', 0)
            est = float(r.get('dock_affinity', 0) or 0)
            vs  = va - ref_aff
            flag = f"{GRN}★{RST}" if va <= ref_aff else " "
            print(f"  {flag}{r['id']:<34} {va:>8.3f} {est:>8.3f} {vs:>+8.3f}")

        best = validated[0]
        best_aff = best.get('vina_affinity', 0)
        print(f"\n{BLD}  Best validated: {best['id']}{RST}")
        print(f"  Vina affinity:  {best_aff:.3f} kcal/mol")

        if best_aff <= -12.0:
            print(f"\n  {GRN}{BLD}★★★ EXCEPTIONAL — beats all approved drugs computationally{RST}")
        elif best_aff <= -10.0:
            print(f"\n  {GRN}{BLD}★★  EXCELLENT — competitive with approved drugs{RST}")
        elif best_aff <= -8.0:
            print(f"\n  {YLW}{BLD}★   GOOD — clinical development range{RST}")

        # Save results
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"validation_results_{ts}.csv"
        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f,
                fieldnames=['id','smiles','target','dock_affinity',
                            'vina_affinity','validated'],
                extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        print(f"\n  Results saved → {out_path}")

if __name__ == "__main__":
    main()
