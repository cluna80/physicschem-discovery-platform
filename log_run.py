# -*- coding: utf-8 -*-
"""
CURE Campaign Documentation Logger
Run after every generation to update the master record.

Usage:
    python log_run.py  --gen 16 --best CURE_16G_007 --affinity -7.487 \
                       --note "Hydroxy-isoquinoline + meta-F + S-OH + bis-THF"

Outputs:
    cure_campaign_log.json   — full history
    cure_campaign_log.md     — human-readable report
"""

import json, argparse, os
from datetime import datetime

LOG_FILE = "cure_campaign_log.json"

# ── Complete verified history ────────────────────────────────
HISTORY = [
    {"gen":  4, "best": "CURE_4G_003",  "affinity": -5.365, "key_discovery": "Initial amide + trifluorophenyl scaffold"},
    {"gen":  5, "best": "CURE_5G_002",  "affinity": -6.122, "key_discovery": "Single THF ring added to right arm"},
    {"gen":  6, "best": "CURE_6G_002",  "affinity": -6.772, "key_discovery": "Naphthalene left arm — pi-stacking in S2"},
    {"gen":  7, "best": "CURE_7G_007",  "affinity": -5.183, "key_discovery": "Regression — THP ring worse than THF"},
    {"gen":  8, "best": "CURE_8G_001",  "affinity": -5.335, "key_discovery": "Regression — naphthalene substituents hurt"},
    {"gen":  9, "best": "CURE_9G_008",  "affinity": -6.207, "key_discovery": "Chiral THF stereo exploration"},
    {"gen": 10, "best": "CURE_10G_007", "affinity": -6.861, "key_discovery": "P1 benzyl group added — first major P1 improvement"},
    {"gen": 11, "best": "CURE_11G_007", "affinity": -7.265, "key_discovery": "meta-Fluorobenzyl P1 — breakthrough +0.4 kcal/mol"},
    {"gen": 12, "best": "CURE_12G_001", "affinity": -7.290, "key_discovery": "Chiral R-OH on linker stereochemistry"},
    {"gen": 13, "best": "CURE_13G_001", "affinity": -7.333, "key_discovery": "R-OH + bis-THF optimised — best naphthalene result"},
    {"gen": 15, "best": "Q15_020",      "affinity": -7.398, "key_discovery": "S-OH stereochemistry better than R-OH on isoquinoline"},
    {"gen": 16, "best": "CURE_16G_007", "affinity": -7.487, "key_discovery": "Hydroxy-isoquinoline left arm — OH on ring reaches Asp30"},
]


def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return {"history": HISTORY, "created": datetime.now().isoformat()}


def save_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def add_run(log, gen, best, affinity, note, smiles=""):
    entry = {
        "gen": gen,
        "best": best,
        "affinity": affinity,
        "key_discovery": note,
        "smiles": smiles,
        "timestamp": datetime.now().isoformat(),
    }
    # Replace if gen already exists
    log["history"] = [h for h in log["history"] if h["gen"] != gen]
    log["history"].append(entry)
    log["history"].sort(key=lambda x: x["gen"])
    return log


def write_markdown(log):
    history = log["history"]
    best_ever = min(history, key=lambda x: x["affinity"])
    start = history[0]["affinity"]
    improvement = best_ever["affinity"] - start

    md = []
    md.append("# CURE HIV Drug Discovery Campaign — Run Log\n")
    md.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    md.append("\n## Progress Summary\n")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Generations completed | {len(history)} |")
    md.append(f"| Starting affinity (Gen 4) | {start:.3f} kcal/mol |")
    md.append(f"| **Current best** | **{best_ever['affinity']:.3f} kcal/mol ({best_ever['best']})** |")
    md.append(f"| Total improvement | {improvement:.3f} kcal/mol |")
    md.append(f"| Gap to Darunavir (~-10.2) | {best_ever['affinity'] - (-10.2):.3f} kcal/mol |")
    md.append(f"| Gap to target (-9.0) | {best_ever['affinity'] - (-9.0):.3f} kcal/mol |")
    md.append(f"| ChEMBL matches (85%) | 0 — potentially novel scaffold |")

    md.append("\n## Generation-by-Generation Results\n")
    md.append("| Gen | Best Compound | Affinity | Key Discovery |")
    md.append("|-----|--------------|----------|---------------|")
    for h in history:
        star = " *" if h["best"] == best_ever["best"] else ""
        md.append(f"| {h['gen']} | {h['best']}{star} | {h['affinity']:.3f} | {h['key_discovery']} |")

    md.append("\n## Key Learnings\n")
    md.append("- **Left arm**: Isoquinoline > Naphthalene; OH on isoquinoline adds H-bond to Asp30")
    md.append("- **P1 group**: meta-Fluorobenzyl optimal; 3,5-difluoro also strong")
    md.append("- **OH stereo**: S-OH optimal on isoquinoline scaffold (R-OH better on naphthalene)")
    md.append("- **Right arm**: bis-THF bicyclic > single THF > THP; hydroxy-bis-THF underperforms")
    md.append("- **Linker**: NH-CO core locked in; N-methyl blocks key H-bond")
    md.append("- **Quantum search**: S-OH + isoquinoline combination found via 10-qubit Grover search")

    md.append("\n## Lead Compound\n")
    md.append(f"**{best_ever['best']}** — {best_ever['key_discovery']}")
    md.append(f"\nBinding affinity: {best_ever['affinity']:.3f} kcal/mol (AutoDock Vina, HIV-1 Protease 1HVR)")
    md.append("\nSMILES: `Oc1ccc2ccc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)nc2c1`")

    md.append("\n## Next Generation (CURE_17G)\n")
    md.append("Strategy: Maximise hydroxy-isoquinoline scaffold")
    md.append("- Combine hydroxy-isoquinoline with 3,5-difluorobenzyl")
    md.append("- Test alternate OH position on isoquinoline ring")
    md.append("- Methoxy vs hydroxy comparison")
    md.append("- Diol linker variant")
    md.append("- High exhaustiveness reconfirm at 32")

    md.append("\n## Novelty Status\n")
    md.append("- ChEMBL (85% similarity): **0 matches** for all top compounds")
    md.append("- PubChem (85% similarity): Fragment-level matches only (different full molecules)")
    md.append("- Patent search: **Pending** (Google Patents / Espacenet)")
    md.append("- Assessment: Potentially novel full molecular architecture\n")

    with open("cure_campaign_log.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen",      type=int,   help="Generation number")
    parser.add_argument("--best",     type=str,   help="Best compound name")
    parser.add_argument("--affinity", type=float, help="Best affinity kcal/mol")
    parser.add_argument("--note",     type=str,   help="Key discovery note")
    parser.add_argument("--smiles",   type=str,   default="", help="SMILES of best compound")
    args = parser.parse_args()

    log = load_log()

    if args.gen:
        log = add_run(log, args.gen, args.best, args.affinity, args.note, args.smiles)
        print(f"  Added Gen {args.gen}: {args.best} at {args.affinity:.3f}")

    write_markdown(log)
    save_log(log)

    # Print current leaderboard
    history = log["history"]
    best_ever = min(history, key=lambda x: x["affinity"])
    print("\n" + "=" * 62)
    print("  CURE CAMPAIGN — CURRENT LEADERBOARD")
    print("=" * 62)
    print(f"  {'Gen':<5} {'Compound':<18} {'Affinity':>10}  Key Discovery")
    print("  " + "-" * 58)
    for h in sorted(history, key=lambda x: x["affinity"]):
        star = " *" if h["best"] == best_ever["best"] else ""
        print(f"  {h['gen']:<5} {h['best']+star:<18} {h['affinity']:>10.3f}  {h['key_discovery'][:35]}")
    print(f"\n  Best ever : {best_ever['best']}  {best_ever['affinity']:.3f} kcal/mol")
    print(f"  Gap -9.0  : {best_ever['affinity']-(-9.0):.3f} kcal/mol")
    print(f"  Gap -10.2 : {best_ever['affinity']-(-10.2):.3f} kcal/mol (Darunavir)")
    print("=" * 62)
    print(f"\n  Saved: {LOG_FILE}")
    print(f"  Saved: cure_campaign_log.md")


if __name__ == "__main__":
    main()