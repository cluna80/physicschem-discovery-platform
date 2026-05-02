"""
resistance_test.py v2 — HIV integrase resistance modeling with true multi-mutant support
======================================================================================
Tests a lead compound against individual mutations AND true multi-mutant combinations
(e.g., Q148R+G140S applied together on one structure).

WORKFLOW
--------
  Lead compound → for each mutation/combination:
                    1. Mutate hiv_integrase PDB (Biopython, ALL mutations at once)
                    2. Convert mutant PDB → PDBQT
                    3. Dock lead compound against mutant
                    4. Compute ΔΔG (resistance penalty) vs. WT
                  → Resistance robustness composite score

USAGE
-----
  Individual mutations:
    python resistance_test.py \\
      --lead-id HNA_G031_insert \\
      --smiles "O=C(O)/C=C/c1ccc(O)cc1CCc1ccccc1" \\
      --wt-affinity -7.68 \\
      --mutations T66I E92Q G140S Q148R N155H

  True double mutant (Q148R and G140S on same structure):
    python resistance_test.py \\
      --lead-id HNA_G031_insert \\
      --smiles "O=C(O)/C=C/c1ccc(O)cc1CCc1ccccc1" \\
      --wt-affinity -7.68 \\
      --mutations-individual T66I E92Q \\
      --mutations-combined Q148R,G140S

  Or simpler — just test combined:
    python resistance_test.py \\
      --lead-id HNA_double \\
      --smiles "..." \\
      --wt-affinity -7.68 \\
      --mutations-combined Q148R,G140S

"""
import argparse, json, logging, os, sys, time, shutil, tempfile, subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("RESIST")

# HIV integrase docking box
HIV_INTEGRASE_CENTER = (-38.5, 30.5, -20.8)
HIV_INTEGRASE_SIZE   = (25, 25, 25)

# Amino acid maps
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
               output_pdb: str, chain_id: str = "A", verbose: bool = True) -> bool:
    """
    Apply MULTIPLE point mutations to a PDB file using Biopython.
    All mutations are applied to the same structure (true multi-mutant).
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

    BACKBONE = {"N", "CA", "C", "O", "CB"}
    mutated_residues = []

    for wt_aa, pos, mut_aa in mutations:
        target_res = None
        for model in structure:
            for chain in model:
                if chain.id != chain_id:
                    continue
                for res in chain:
                    if res.id[1] == pos:
                        target_res = res
                        break
        
        if not target_res:
            if verbose:
                log.warning(f"  residue {pos} not found in chain {chain_id}, skipping {wt_aa}{pos}{mut_aa}")
            continue

        original = AA_3TO1.get(target_res.resname, "?")
        if original != wt_aa and verbose:
            log.warning(f"  WARNING: residue {pos} is {original}, not {wt_aa}")

        # Strip side-chain atoms
        atoms_to_remove = [atom.name for atom in target_res if atom.name not in BACKBONE]
        for aname in atoms_to_remove:
            target_res.detach_child(aname)

        # Rename residue
        target_res.resname = AA_1TO3[mut_aa]
        mutated_residues.append((wt_aa, pos, mut_aa))
        if verbose:
            log.info(f"  mutated {wt_aa}{pos}{mut_aa} (chain {chain_id})")

    if not mutated_residues:
        log.error("[fail] no mutations applied")
        return False

    io = PDBIO()
    io.set_structure(structure)
    io.save(output_pdb)
    if verbose:
        log.info(f"  wrote: {output_pdb}")
    return True


# ── PDB → PDBQT conversion ───────────────────────────────────────────────────

def pdbqt_from_template(wt_pdbqt: str, mutations: List[Tuple[str, int, str]],
                         output_pdbqt: str, chain_id: str = "A") -> bool:
    """
    Copy WT PDBQT, then strip side-chain atoms of all mutated residues.
    Preserves receptor preparation (charges, polar hydrogens, atom typing).
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
                if atom_name in BACKBONE:
                    new_resname = AA_1TO3[mut_positions[key]]
                    new_line = line[:17] + f"{new_resname:>3}" + line[20:]
                    out_lines.append(new_line)
                    modified += 1
                else:
                    continue  # Strip side-chain
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)

    try:
        with open(output_pdbqt, "w") as f:
            f.writelines(out_lines)
        log.info(f"  wrote: {output_pdbqt} ({modified} backbone atoms, side-chains stripped)")
        return True
    except IOError as e:
        log.error(f"[fail] could not write {output_pdbqt}: {e}")
        return False


# ── Docking ──────────────────────────────────────────────────────────────────

def dock_against_mutant(smiles: str, lead_id: str, mutant_pdbqt: str,
                         exhaustiveness: int = 8, ada=None) -> Optional[Dict]:
    """Dock lead compound against a mutant receptor."""
    if not Path(mutant_pdbqt).exists():
        log.error(f"[fail] mutant pdbqt missing: {mutant_pdbqt}")
        return None

    class CLILog:
        def log(self, agent, msg):
            pass  # Suppress verbose docking logs

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
    """Categorize ΔΔG into resistance tier."""
    if ddg > 2.0:
        return "VULNERABLE"
    elif ddg > 0.5:
        return "PENALIZED"
    elif ddg >= -0.5:
        return "ROBUST"
    else:
        return "ENHANCED"


def compute_robustness(results: List[Dict]) -> Dict:
    """Compute composite resistance robustness score."""
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

    score = 100
    score -= max(0, avg_ddg) * 15
    score -= max(0, max_ddg - 2.0) * 25
    score += n_robust * 5
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


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="HIV integrase resistance modeling (with true multi-mutant support)")
    ap.add_argument("--lead-id", required=True)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--wt-affinity", type=float, required=True)
    ap.add_argument("--target", default="HIV_DIP")
    ap.add_argument("--wt-pdbqt", default="hiv_integrase.pdbqt")
    ap.add_argument("--pdb", default="3L2T_clean.pdb")
    ap.add_argument("--mutations", nargs="*", default=[], help="Individual mutations (T66I, E92Q, ...)")
    ap.add_argument("--mutations-individual", nargs="*", default=[], help="Individual mutations to test separately")
    ap.add_argument("--mutations-combined", nargs="*", default=[], help="Mutation combinations (Q148R,G140S) to test together")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--exhaustiveness", type=int, default=8)
    ap.add_argument("--out-dir", default="resistance_results")
    ap.add_argument("--use-pdbqt-template", action="store_true", default=True)
    args = ap.parse_args()

    # Handle backwards compatibility: --mutations becomes --mutations-individual
    if args.mutations and not args.mutations_individual:
        args.mutations_individual = args.mutations
        args.mutations = []

    # Verify inputs
    if not Path(args.wt_pdbqt).exists():
        log.error(f"[fail] WT receptor missing: {args.wt_pdbqt}"); sys.exit(1)

    # Import
    try:
        import autonomous_drug_agent as ada
    except ImportError as e:
        log.error(f"[fail] cannot import autonomous_drug_agent: {e}"); sys.exit(1)

    log.info("=" * 70)
    log.info("HIV INTEGRASE RESISTANCE MODELING — Module 3 (v2)")
    log.info("=" * 70)
    log.info(f"Lead:       {args.lead_id}")
    log.info(f"SMILES:     {args.smiles}")
    log.info(f"WT affinity: {args.wt_affinity:.3f} kcal/mol")
    if args.mutations_individual:
        log.info(f"Individual:  {', '.join(args.mutations_individual)}")
    if args.mutations_combined:
        log.info(f"Combined:    {', '.join(args.mutations_combined)}")
    log.info("=" * 70)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / f"{args.lead_id}_mutants"
    work_dir.mkdir(parents=True, exist_ok=True)

    results = []

    # ── Individual mutations ──
    for mut_str in args.mutations_individual:
        log.info(f"\n>>> Individual Mutation: {mut_str}")
        try:
            mutation = parse_mutation(mut_str)
        except ValueError as e:
            log.error(f"  [fail] {e}"); continue

        mut_pdbqt = work_dir / f"integrase_{mut_str}.pdbqt"
        ok = pdbqt_from_template(args.wt_pdbqt, [mutation], str(mut_pdbqt), args.chain)

        if not ok:
            log.error(f"  [fail] preparation failed")
            results.append({"mutation": mut_str, "error": "preparation failed"})
            continue

        log.info(f"  docking...")
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
            results.append({"mutation": mut_str, "error": "docking failed"})
            continue

        mut_aff = dock_result["affinity"]
        ddg = mut_aff - args.wt_affinity
        tier = classify_resistance(ddg)

        log.info(f"  WT:     {args.wt_affinity:.3f}")
        log.info(f"  Mutant: {mut_aff:.3f}")
        log.info(f"  ΔΔG:    {ddg:+.3f}  →  {tier}  ({dt:.0f}s)")

        results.append({
            "mutation": mut_str,
            "type": "individual",
            "wt_affinity": args.wt_affinity,
            "mutant_affinity": mut_aff,
            "ddg": ddg,
            "tier": tier,
        })

    # ── Combined mutations ──
    for combo_str in args.mutations_combined:
        mut_list = combo_str.split(",")
        log.info(f"\n>>> Combined Mutation: {' + '.join(mut_list)}")
        
        try:
            mutations = [parse_mutation(m.strip()) for m in mut_list]
        except ValueError as e:
            log.error(f"  [fail] {e}"); continue

        combo_name = "_".join(m.upper() for m in mut_list)
        mut_pdbqt = work_dir / f"integrase_{combo_name}.pdbqt"
        ok = pdbqt_from_template(args.wt_pdbqt, mutations, str(mut_pdbqt), args.chain)

        if not ok:
            log.error(f"  [fail] preparation failed")
            results.append({"mutation": combo_str, "error": "preparation failed"})
            continue

        log.info(f"  docking against combined mutant...")
        t0 = time.time()
        dock_result = dock_against_mutant(
            smiles=args.smiles,
            lead_id=f"{args.lead_id}_vs_{combo_name}",
            mutant_pdbqt=str(mut_pdbqt),
            exhaustiveness=args.exhaustiveness,
            ada=ada,
        )
        dt = time.time() - t0

        if dock_result is None:
            results.append({"mutation": combo_str, "error": "docking failed"})
            continue

        mut_aff = dock_result["affinity"]
        ddg = mut_aff - args.wt_affinity
        tier = classify_resistance(ddg)

        log.info(f"  WT:     {args.wt_affinity:.3f}")
        log.info(f"  Mutant: {mut_aff:.3f}")
        log.info(f"  ΔΔG:    {ddg:+.3f}  →  {tier}  ({dt:.0f}s)")

        results.append({
            "mutation": combo_str,
            "type": "combined",
            "wt_affinity": args.wt_affinity,
            "mutant_affinity": mut_aff,
            "ddg": ddg,
            "tier": tier,
        })

    # ── Report ──
    robustness = compute_robustness(results)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report = {
        "lead_id": args.lead_id,
        "smiles": args.smiles,
        "wt_affinity": args.wt_affinity,
        "per_mutation_results": results,
        "robustness": robustness,
        "timestamp": timestamp,
    }
    report_file = out_dir / f"resistance_report_{args.lead_id}_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    log.info("\n" + "=" * 70)
    log.info(f"RESISTANCE PROFILE — {args.lead_id}")
    log.info("=" * 70)
    log.info(f"  WT:                     {args.wt_affinity:.3f} kcal/mol")
    log.info(f"  Mutations tested:       {len(results)}")
    log.info("")
    log.info(f"  {'Mutation':<20} {'Type':<12} {'Mutant':>10} {'ΔΔG':>10} {'Tier':>14}")
    log.info(f"  {'-'*70}")
    for r in results:
        if "error" in r:
            log.info(f"  {r['mutation']:<20} {'─':<12} {'─':>10} {'─':>10} {'ERROR':>14}")
        else:
            mtype = r.get("type", "individual").upper()
            log.info(f"  {r['mutation']:<20} {mtype:<12} "
                    f"{r['mutant_affinity']:>10.2f} {r['ddg']:>+10.2f} {r['tier']:>14}")
    log.info("")
    log.info(f"  ROBUSTNESS SCORE:     {robustness['robustness_score']}/100")
    log.info(f"  TIER:                 {robustness['tier']}")
    log.info(f"  Average ΔΔG:          {robustness.get('avg_ddg', 'N/A')}")
    log.info(f"  Worst-case ΔΔG:       {robustness.get('max_ddg', 'N/A')}")
    log.info(f"  Robust mutations:     {robustness.get('n_robust', 0)}/{robustness.get('n_total', 0)}")
    log.info(f"  Vulnerable:           {robustness.get('n_vulnerable', 0)}")
    log.info("")
    log.info(f"  Report: {report_file.name}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()