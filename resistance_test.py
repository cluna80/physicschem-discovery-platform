"""
resistance_test.py — Module 3: Resistance Modeling Engine
============================================================
Tests a lead compound against a panel of HIV-1 integrase resistance
mutations to assess "resistance robustness" — the gold standard for
modern INSTI development.

WORKFLOW
--------
  Lead compound → for each mutation:
                    1. Mutate hiv_integrase PDB (Biopython)
                    2. Convert mutant PDB → PDBQT (meeko/openbabel)
                    3. Dock lead compound against mutant
                    4. Compute ΔΔG (resistance penalty) vs. WT
                  → Resistance robustness composite score

USAGE
-----
  python resistance_test.py \\
      --lead-id HNA_G031_insert \\
      --smiles "O=C(O)/C=C/c1ccc(O)cc1CCc1ccccc1" \\
      --wt-affinity -7.68 \\
      --target HIV_DIP \\
      --pdb 3L2T_clean.pdb \\
      --mutations T66I E92Q G140S Q148R N155H

The mutations panel default is the 5 clinical INSTI resistance mutations.

INTERPRETATION
--------------
  ΔΔG > +2.0 kcal/mol  → significant resistance (compound vulnerable)
  ΔΔG +0.5 to +2.0     → moderate resistance penalty
  ΔΔG -0.5 to +0.5     → ROBUST (binding maintained)
  ΔΔG < -0.5           → mutation actually helps binding (rare; suspicious)

Compounds that maintain binding through Q148R + G140S double mutant
are publication-quality INSTI candidates.
"""
import argparse, json, logging, os, sys, time, shutil, tempfile, subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("RESIST")

# HIV integrase docking box (matches admet_profiler.py and sar_optimize.py)
HIV_INTEGRASE_CENTER = (-38.5, 30.5, -20.8)
HIV_INTEGRASE_SIZE   = (25, 25, 25)

# Standard 3-letter to 1-letter amino acid map
AA_3TO1 = {
    'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E',
    'GLY':'G','HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F',
    'PRO':'P','SER':'S','THR':'T','TRP':'W','TYR':'Y','VAL':'V'
}
AA_1TO3 = {v: k for k, v in AA_3TO1.items()}


# ── Biopython mutagenesis ────────────────────────────────────────────────────

def parse_mutation(mut_str: str) -> Tuple[str, int, str]:
    """Parse 'T66I' style mutation string → ('T', 66, 'I')."""
    mut_str = mut_str.strip().upper()
    if len(mut_str) < 3:
        raise ValueError(f"invalid mutation: {mut_str}")
    wt_aa = mut_str[0]
    mut_aa = mut_str[-1]
    try:
        pos = int(mut_str[1:-1])
    except ValueError:
        raise ValueError(f"invalid position in mutation: {mut_str}")
    if wt_aa not in AA_1TO3 or mut_aa not in AA_1TO3:
        raise ValueError(f"unknown amino acid in mutation: {mut_str}")
    return wt_aa, pos, mut_aa


def mutate_pdb(input_pdb: str, mutations: List[Tuple[str, int, str]],
               output_pdb: str, chain_id: str = "A") -> bool:
    """
    Apply point mutations to a PDB file using Biopython.
    Approach: keep backbone atoms, rename residue, strip side-chain atoms
              that aren't in the new residue type.
    
    This is "mutagenesis with default rotamer" — fast and good enough for
    a first-pass resistance screen. For publication-quality results,
    swap in real crystal structures.
    """
    try:
        from Bio.PDB import PDBParser, PDBIO, Select
    except ImportError:
        log.error("[fail] biopython not available")
        return False

    parser = PDBParser(QUIET=True)
    try:
        structure = parser.get_structure("integrase", input_pdb)
    except Exception as e:
        log.error(f"[fail] could not parse PDB: {e}")
        return False

    # Backbone atoms always kept
    BACKBONE = {"N", "CA", "C", "O", "CB"}

    mutated_residues = []
    for wt_aa, pos, mut_aa in mutations:
        target_chain = None
        target_res = None
        for model in structure:
            for chain in model:
                if chain.id != chain_id:
                    continue
                for res in chain:
                    if res.id[1] == pos:
                        target_chain = chain
                        target_res = res
                        break
        if not target_res:
            log.warning(f"  residue {pos} not found in chain {chain_id}, skipping {wt_aa}{pos}{mut_aa}")
            continue

        # Verify the original amino acid matches what we expect
        original = AA_3TO1.get(target_res.resname, "?")
        if original != wt_aa:
            log.warning(f"  WARNING: residue {pos} is {original}, not {wt_aa} (expected for {wt_aa}{pos}{mut_aa})")
            log.warning(f"           proceeding anyway — this may indicate non-standard numbering")

        # Strip side-chain atoms (not in BACKBONE)
        atoms_to_remove = []
        for atom in target_res:
            if atom.name not in BACKBONE:
                atoms_to_remove.append(atom.name)
        for aname in atoms_to_remove:
            target_res.detach_child(aname)

        # Rename residue to new amino acid (3-letter)
        target_res.resname = AA_1TO3[mut_aa]
        mutated_residues.append((wt_aa, pos, mut_aa))
        log.info(f"  mutated {wt_aa}{pos}{mut_aa} (chain {chain_id})")

    if not mutated_residues:
        log.error("[fail] no mutations applied")
        return False

    # Write mutant PDB
    io = PDBIO()
    io.set_structure(structure)
    io.save(output_pdb)
    log.info(f"  wrote: {output_pdb}")
    return True


# ── PDB → PDBQT conversion ───────────────────────────────────────────────────

def pdb_to_pdbqt(input_pdb: str, output_pdbqt: str) -> bool:
    """
    Convert mutant PDB to PDBQT for AutoDock Vina.
    Uses a simple ATOM-line transformation since we're not adding hydrogens
    or computing charges — Vina will handle most of that with its receptor.
    
    For the receptor, the cleaner approach is to use the existing WT pdbqt
    as a template and only modify the lines that correspond to mutated residues.
    But for v1, a simple ATOM→PDBQT conversion is sufficient.
    """
    # Read PDB
    try:
        with open(input_pdb, "r") as f:
            pdb_lines = f.readlines()
    except IOError as e:
        log.error(f"[fail] could not read {input_pdb}: {e}")
        return False

    # Convert ATOM/HETATM lines → PDBQT format
    # PDBQT format adds: charge field, atom type field
    pdbqt_lines = []
    for line in pdb_lines:
        if line.startswith(("ATOM", "HETATM")):
            # PDB format: cols 31-38 (x), 39-46 (y), 47-54 (z)
            # PDBQT adds: cols 67-76 charge + atom_type
            stripped = line.rstrip()
            if len(stripped) < 78:
                stripped = stripped.ljust(78)
            # Crude charge=0.0 + atom type from element column
            element = stripped[76:78].strip() if len(stripped) >= 78 else "C"
            if not element:
                # Try column 12-16 (atom name)
                atom_name = stripped[12:16].strip()
                element = atom_name[0] if atom_name else "C"
            pdbqt_line = f"{stripped[:66]}{0.0:>6.3f} {element:<2}\n"
            pdbqt_lines.append(pdbqt_line)
        elif line.startswith(("TER", "END", "HEADER", "TITLE", "REMARK")):
            pdbqt_lines.append(line)

    try:
        with open(output_pdbqt, "w") as f:
            f.writelines(pdbqt_lines)
        log.info(f"  wrote: {output_pdbqt}")
        return True
    except IOError as e:
        log.error(f"[fail] could not write {output_pdbqt}: {e}")
        return False


def pdbqt_from_template(wt_pdbqt: str, mutations: List[Tuple[str, int, str]],
                         output_pdbqt: str, chain_id: str = "A") -> bool:
    """
    BETTER approach: copy WT PDBQT, then strip side-chain atoms of mutated
    residues and rename. Preserves all the receptor preparation (charges,
    polar hydrogens, atom typing) that the WT pdbqt already has.
    """
    try:
        with open(wt_pdbqt, "r") as f:
            lines = f.readlines()
    except IOError as e:
        log.error(f"[fail] could not read {wt_pdbqt}: {e}")
        return False

    BACKBONE = {"N", "CA", "C", "O", "CB"}
    mut_positions = {(chain_id, pos): mut_aa for _, pos, mut_aa in mutations}
    out_lines = []
    modified = 0

    for line in lines:
        if line.startswith(("ATOM", "HETATM")):
            try:
                atom_name = line[12:16].strip()
                resname = line[17:20].strip()
                line_chain = line[21:22].strip() or "A"
                resnum = int(line[22:26].strip())
            except (ValueError, IndexError):
                out_lines.append(line)
                continue

            key = (line_chain, resnum)
            if key in mut_positions:
                # This residue is being mutated
                if atom_name in BACKBONE:
                    # Keep backbone atom but rename residue
                    new_resname = AA_1TO3[mut_positions[key]]
                    new_line = line[:17] + f"{new_resname:>3}" + line[20:]
                    out_lines.append(new_line)
                    modified += 1
                else:
                    # Strip side-chain atom (default rotamer of new aa is missing)
                    continue
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)

    if modified == 0:
        log.warning(f"[warn] no atoms modified — check chain ID and residue numbers")

    try:
        with open(output_pdbqt, "w") as f:
            f.writelines(out_lines)
        log.info(f"  wrote: {output_pdbqt} ({modified} backbone atoms preserved, side-chains stripped)")
        return True
    except IOError as e:
        log.error(f"[fail] could not write {output_pdbqt}: {e}")
        return False


# ── Docking against mutant ───────────────────────────────────────────────────

def dock_against_mutant(smiles: str, lead_id: str, mutant_pdbqt: str,
                         exhaustiveness: int = 8, ada=None) -> Optional[Dict]:
    """Dock lead compound against a mutant receptor."""
    if not Path(mutant_pdbqt).exists():
        log.error(f"[fail] mutant pdbqt missing: {mutant_pdbqt}")
        return None

    class CLILog:
        def log(self, agent, msg):
            log.info(f"  [{agent}] {msg}")

    DockingAgent = ada.DockingAgent
    docker = DockingAgent(
        logger=CLILog(),
        receptor=mutant_pdbqt,
        center=HIV_INTEGRASE_CENTER,
        size=HIV_INTEGRASE_SIZE,
        exhaustiveness=exhaustiveness,
    )
    result = docker.dock(smiles, lead_id)
    if "affinity" in result:
        return {
            "affinity": result["affinity"],
            "n_poses": result.get("n_poses", 0),
        }
    log.warning(f"  dock failed: {result.get('error', 'unknown')}")
    return None


# ── Robustness scoring ───────────────────────────────────────────────────────

def classify_resistance(ddg: float) -> str:
    """Categorize a single mutation's ΔΔG into a resistance tier."""
    if ddg > 2.0:
        return "VULNERABLE"
    elif ddg > 0.5:
        return "PENALIZED"
    elif ddg >= -0.5:
        return "ROBUST"
    else:
        return "ENHANCED"


def compute_robustness(results: List[Dict]) -> Dict:
    """Compute composite resistance robustness score from per-mutation ΔΔG."""
    n = len(results)
    if n == 0:
        return {"robustness_score": 0, "tier": "FAIL", "summary": "no data"}

    valid = [r for r in results if r.get("ddg") is not None]
    if not valid:
        return {"robustness_score": 0, "tier": "FAIL", "summary": "no valid dockings"}

    avg_ddg = sum(r["ddg"] for r in valid) / len(valid)
    max_ddg = max(r["ddg"] for r in valid)
    n_robust = sum(1 for r in valid if r["tier"] == "ROBUST")
    n_vulnerable = sum(1 for r in valid if r["tier"] == "VULNERABLE")

    # Robustness score: 0-100, higher is better
    # Heavy penalty for any VULNERABLE mutation (would make compound clinically poor)
    # Reward ROBUST tier hits
    score = 100
    score -= max(0, avg_ddg) * 15        # average penalty
    score -= max(0, max_ddg - 2.0) * 25  # extra penalty if any mutation is vulnerable
    score += n_robust * 5                 # reward for each robust mutation
    score = max(0, min(100, score))

    if n_vulnerable >= 2:
        tier = "POOR"
    elif n_vulnerable == 1:
        tier = "MODERATE"
    elif avg_ddg < 1.0 and n_robust >= len(valid) // 2:
        tier = "STRONG"
    else:
        tier = "ACCEPTABLE"

    return {
        "robustness_score": round(score, 1),
        "tier": tier,
        "avg_ddg": round(avg_ddg, 2),
        "max_ddg": round(max_ddg, 2),
        "n_robust": n_robust,
        "n_vulnerable": n_vulnerable,
        "n_total": len(valid),
    }


# ── Main runner ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="HIV integrase resistance modeling")
    ap.add_argument("--lead-id", required=True)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--wt-affinity", type=float, required=True,
                    help="Wild-type binding affinity from previous campaign (kcal/mol)")
    ap.add_argument("--target", default="HIV_DIP")
    ap.add_argument("--wt-pdbqt", default="hiv_integrase.pdbqt")
    ap.add_argument("--pdb", default="3L2T_clean.pdb")
    ap.add_argument("--mutations", nargs="+",
                    default=["T66I", "E92Q", "G140S", "Q148R", "N155H"])
    ap.add_argument("--chain", default="A")
    ap.add_argument("--exhaustiveness", type=int, default=8)
    ap.add_argument("--out-dir", default="resistance_results")
    ap.add_argument("--use-pdbqt-template", action="store_true", default=True,
                    help="Use WT pdbqt as template (recommended)")
    args = ap.parse_args()

    log.info("=" * 60)
    log.info("HIV INTEGRASE RESISTANCE MODELING (Module 3)")
    log.info("=" * 60)
    log.info(f"Lead:       {args.lead_id}")
    log.info(f"SMILES:     {args.smiles}")
    log.info(f"WT affinity: {args.wt_affinity:.3f} kcal/mol")
    log.info(f"Mutations:  {', '.join(args.mutations)}")
    log.info("=" * 60)

    # Verify inputs
    if not Path(args.wt_pdbqt).exists():
        log.error(f"[fail] WT receptor missing: {args.wt_pdbqt}"); sys.exit(1)

    # Import autonomous_drug_agent
    try:
        import autonomous_drug_agent as ada
    except ImportError as e:
        log.error(f"[fail] cannot import autonomous_drug_agent: {e}"); sys.exit(1)

    # Working directory
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / f"{args.lead_id}_mutants"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Process each mutation
    results = []
    for mut_str in args.mutations:
        log.info(f"\n>>> Mutation: {mut_str}")
        try:
            mutation = parse_mutation(mut_str)
        except ValueError as e:
            log.error(f"  [fail] {e}"); continue

        # Build mutant pdbqt
        mut_pdbqt = work_dir / f"integrase_{mut_str}.pdbqt"

        if args.use_pdbqt_template:
            ok = pdbqt_from_template(args.wt_pdbqt, [mutation], str(mut_pdbqt), args.chain)
        else:
            mut_pdb = work_dir / f"integrase_{mut_str}.pdb"
            ok = mutate_pdb(args.pdb, [mutation], str(mut_pdb), args.chain)
            if ok:
                ok = pdb_to_pdbqt(str(mut_pdb), str(mut_pdbqt))

        if not ok:
            log.error(f"  [fail] could not prepare mutant {mut_str}")
            results.append({"mutation": mut_str, "error": "preparation failed"})
            continue

        # Dock lead against mutant
        log.info(f"  docking lead against {mut_str} mutant...")
        t0 = time.time()
        dock_result = dock_against_mutant(
            smiles=args.smiles,
            lead_id=f"{args.lead_id}_vs_{mut_str}",
            mutant_pdbqt=str(mut_pdbqt),
            exhaustiveness=args.exhaustiveness,
            ada=ada,
        )
        dt = time.time() - t0

        if dock_result is None:
            log.warning(f"  [skip] docking failed for {mut_str}")
            results.append({"mutation": mut_str, "error": "docking failed"})
            continue

        mut_aff = dock_result["affinity"]
        ddg = mut_aff - args.wt_affinity  # Positive = resistance, negative = enhancement
        tier = classify_resistance(ddg)

        log.info(f"  WT:     {args.wt_affinity:.3f} kcal/mol")
        log.info(f"  Mutant: {mut_aff:.3f} kcal/mol")
        log.info(f"  ΔΔG:    {ddg:+.3f} kcal/mol  →  {tier}  (docking: {dt:.0f}s)")

        results.append({
            "mutation": mut_str,
            "wt_affinity": args.wt_affinity,
            "mutant_affinity": mut_aff,
            "ddg": ddg,
            "tier": tier,
            "n_poses": dock_result.get("n_poses", 0),
        })

    # Compute robustness
    robustness = compute_robustness(results)

    # Save full report
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report = {
        "lead_id": args.lead_id,
        "smiles": args.smiles,
        "wt_affinity": args.wt_affinity,
        "mutations_tested": args.mutations,
        "per_mutation_results": results,
        "robustness": robustness,
        "timestamp": timestamp,
    }
    report_file = out_dir / f"resistance_report_{args.lead_id}_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # Print summary
    log.info("\n" + "=" * 60)
    log.info(f"RESISTANCE PROFILE — {args.lead_id}")
    log.info("=" * 60)
    log.info(f"  WT:                     {args.wt_affinity:.3f} kcal/mol")
    log.info(f"  Mutations tested:       {len(args.mutations)}")
    log.info("")
    log.info(f"  {'Mutation':<10} {'Mutant':>10} {'ΔΔG':>10} {'Tier':>14}")
    log.info(f"  {'─'*46}")
    for r in results:
        if "error" in r:
            log.info(f"  {r['mutation']:<10} {'─':>10} {'─':>10} {'ERROR':>14}")
        else:
            log.info(f"  {r['mutation']:<10} "
                    f"{r['mutant_affinity']:>10.2f} "
                    f"{r['ddg']:>+10.2f} "
                    f"{r['tier']:>14}")
    log.info("")
    log.info(f"  ROBUSTNESS SCORE: {robustness['robustness_score']}/100")
    log.info(f"  TIER:             {robustness['tier']}")
    log.info(f"  Average ΔΔG:      {robustness.get('avg_ddg', 'N/A')}")
    log.info(f"  Worst-case ΔΔG:   {robustness.get('max_ddg', 'N/A')}")
    log.info(f"  Robust mutations: {robustness.get('n_robust', 0)}/{robustness.get('n_total', 0)}")
    log.info(f"  Vulnerable:       {robustness.get('n_vulnerable', 0)}")
    log.info("")
    log.info(f"  Report: {report_file.name}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
