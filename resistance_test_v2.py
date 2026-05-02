"""
resistance_test.py v2 — HIV integrase resistance modeling with true multi-mutant support
"""
import argparse, json, logging, os, sys, time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("RESIST")

HIV_INTEGRASE_CENTER = (-38.5, 30.5, -20.8)
HIV_INTEGRASE_SIZE   = (25, 25, 25)

AA_3TO1 = {'ALA':'A','ARG':'R','ASN':'N','ASP':'D','CYS':'C','GLN':'Q','GLU':'E',
    'GLY':'G','HIS':'H','ILE':'I','LEU':'L','LYS':'K','MET':'M','PHE':'F',
    'PRO':'P','SER':'S','THR':'T','TRP':'W','TYR':'Y','VAL':'V'}
AA_1TO3 = {v: k for k, v in AA_3TO1.items()}

def parse_mutation(mut_str: str) -> Tuple[str, int, str]:
    mut_str = mut_str.strip().upper()
    if len(mut_str) < 3:
        raise ValueError(f"invalid mutation: {mut_str}")
    wt_aa, mut_aa = mut_str[0], mut_str[-1]
    try:
        pos = int(mut_str[1:-1])
    except ValueError:
        raise ValueError(f"invalid position in mutation: {mut_str}")
    if wt_aa not in AA_1TO3 or mut_aa not in AA_1TO3:
        raise ValueError(f"unknown amino acid in mutation: {mut_str}")
    return wt_aa, pos, mut_aa

def pdbqt_from_template(wt_pdbqt: str, mutations: List[Tuple[str, int, str]],
                         output_pdbqt: str, chain_id: str = "A") -> bool:
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
                    continue
            else:
                out_lines.append(line)
        else:
            out_lines.append(line)

    try:
        with open(output_pdbqt, "w") as f:
            f.writelines(out_lines)
        log.info(f"  wrote: {output_pdbqt} ({modified} backbone atoms)")
        return True
    except IOError as e:
        log.error(f"[fail] could not write {output_pdbqt}: {e}")
        return False

def dock_against_mutant(smiles: str, lead_id: str, mutant_pdbqt: str,
                         exhaustiveness: int = 8, ada=None) -> Optional[Dict]:
    if not Path(mutant_pdbqt).exists():
        log.error(f"[fail] mutant pdbqt missing: {mutant_pdbqt}")
        return None
    class CLILog:
        def log(self, agent, msg):
            pass
    DockingAgent = ada.DockingAgent
    docker = DockingAgent(logger=CLILog(), receptor=mutant_pdbqt,
        center=HIV_INTEGRASE_CENTER, size=HIV_INTEGRASE_SIZE,
        exhaustiveness=exhaustiveness)
    result = docker.dock(smiles, lead_id)
    if "affinity" in result:
        return {"affinity": result["affinity"], "n_poses": result.get("n_poses", 0)}
    log.warning(f"  dock failed: {result.get('error', 'unknown')}")
    return None

def classify_resistance(ddg: float) -> str:
    if ddg > 2.0: return "VULNERABLE"
    elif ddg > 0.5: return "PENALIZED"
    elif ddg >= -0.5: return "ROBUST"
    else: return "ENHANCED"

def compute_robustness(results: List[Dict]) -> Dict:
    n = len(results)
    if n == 0: return {"robustness_score": 0, "tier": "FAIL", "summary": "no data"}
    valid = [r for r in results if r.get("ddg") is not None]
    if not valid: return {"robustness_score": 0, "tier": "FAIL"}
    avg_ddg = sum(r["ddg"] for r in valid) / len(valid)
    max_ddg = max(r["ddg"] for r in valid)
    n_robust = sum(1 for r in valid if r["tier"] == "ROBUST")
    n_vulnerable = sum(1 for r in valid if r["tier"] == "VULNERABLE")
    score = 100 - max(0, avg_ddg) * 15 - max(0, max_ddg - 2.0) * 25 + n_robust * 5
    score = max(0, min(100, score))
    if n_vulnerable >= 2: tier = "POOR"
    elif n_vulnerable == 1: tier = "MODERATE"
    elif avg_ddg < 1.0 and n_robust >= len(valid) // 2: tier = "STRONG"
    else: tier = "ACCEPTABLE"
    return {"robustness_score": round(score, 1), "tier": tier, "avg_ddg": round(avg_ddg, 2),
            "max_ddg": round(max_ddg, 2), "n_robust": n_robust, "n_vulnerable": n_vulnerable, "n_total": len(valid)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-id", required=True)
    ap.add_argument("--smiles", required=True)
    ap.add_argument("--wt-affinity", type=float, required=True)
    ap.add_argument("--target", default="HIV_DIP")
    ap.add_argument("--wt-pdbqt", default="hiv_integrase.pdbqt")
    ap.add_argument("--pdb", default="3L2T_clean.pdb")
    ap.add_argument("--mutations-combined", nargs="*", default=[])
    ap.add_argument("--chain", default="A")
    ap.add_argument("--exhaustiveness", type=int, default=8)
    ap.add_argument("--out-dir", default="resistance_results")
    args = ap.parse_args()

    if not Path(args.wt_pdbqt).exists():
        log.error(f"[fail] WT receptor missing: {args.wt_pdbqt}"); sys.exit(1)

    try:
        import autonomous_drug_agent as ada
    except ImportError as e:
        log.error(f"[fail] cannot import ada: {e}"); sys.exit(1)

    log.info("=" * 70)
    log.info("HIV INTEGRASE RESISTANCE MODELING — True Double Mutant")
    log.info("=" * 70)
    log.info(f"Lead:       {args.lead_id}")
    log.info(f"WT affinity: {args.wt_affinity:.3f} kcal/mol")
    if args.mutations_combined:
        log.info(f"Combined:    {', '.join(args.mutations_combined)}")
    log.info("=" * 70)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / f"{args.lead_id}_mutants"
    work_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for combo_str in args.mutations_combined:
        mut_list = combo_str.split(",")
        log.info(f"\n>>> Combined: {' + '.join(mut_list)}")
        try:
            mutations = [parse_mutation(m.strip()) for m in mut_list]
        except ValueError as e:
            log.error(f"  [fail] {e}"); continue

        combo_name = "_".join(m.upper() for m in mut_list)
        mut_pdbqt = work_dir / f"integrase_{combo_name}.pdbqt"
        ok = pdbqt_from_template(args.wt_pdbqt, mutations, str(mut_pdbqt), args.chain)

        if not ok:
            results.append({"mutation": combo_str, "error": "preparation failed"})
            continue

        log.info(f"  docking...")
        t0 = time.time()
        dock_result = dock_against_mutant(args.smiles, f"{args.lead_id}_vs_{combo_name}",
            str(mut_pdbqt), args.exhaustiveness, ada)
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

    robustness = compute_robustness(results)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report = {"lead_id": args.lead_id, "smiles": args.smiles, "wt_affinity": args.wt_affinity,
              "results": results, "robustness": robustness, "timestamp": timestamp}
    report_file = out_dir / f"resistance_report_{args.lead_id}_{timestamp}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    log.info("\n" + "=" * 70)
    log.info(f"RESISTANCE PROFILE — {args.lead_id}")
    log.info("=" * 70)
    log.info(f"  WT:                 {args.wt_affinity:.3f} kcal/mol")
    log.info(f"  Results:            {len(results)}")
    log.info("")
    log.info(f"  {'Mutation':<20} {'Mutant':>10} {'ΔΔG':>10} {'Tier':>14}")
    log.info(f"  {'-'*60}")
    for r in results:
        if "error" in r:
            log.info(f"  {r['mutation']:<20} {'ERROR':>10}")
        else:
            log.info(f"  {r['mutation']:<20} {r['mutant_affinity']:>10.2f} {r['ddg']:>+10.2f} {r['tier']:>14}")
    log.info("")
    log.info(f"  ROBUSTNESS SCORE:   {robustness['robustness_score']}/100")
    log.info(f"  TIER:               {robustness['tier']}")
    log.info(f"  Report:             {report_file.name}")
    log.info("=" * 70)

if __name__ == "__main__":
    main()
