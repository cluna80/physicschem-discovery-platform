# CURE HIV Drug Discovery Campaign — Run Log

*Last updated: 2026-03-26 20:22*


## Progress Summary

| Metric | Value |
|--------|-------|
| Generations completed | 15 |
| Starting affinity (Gen 4) | -5.365 kcal/mol |
| **Current best** | **-7.812 kcal/mol (CURE_19G_002)** |
| Total improvement | -2.447 kcal/mol |
| Gap to Darunavir (~-10.2) | 2.388 kcal/mol |
| Gap to target (-9.0) | 1.188 kcal/mol |
| ChEMBL matches (85%) | 0 — potentially novel scaffold |

## Generation-by-Generation Results

| Gen | Best Compound | Affinity | Key Discovery |
|-----|--------------|----------|---------------|
| 4 | CURE_4G_003 | -5.365 | Initial amide + trifluorophenyl scaffold |
| 5 | CURE_5G_002 | -6.122 | Single THF ring added to right arm |
| 6 | CURE_6G_002 | -6.772 | Naphthalene left arm — pi-stacking in S2 |
| 7 | CURE_7G_007 | -5.183 | Regression — THP ring worse than THF |
| 8 | CURE_8G_001 | -5.335 | Regression — naphthalene substituents hurt |
| 9 | CURE_9G_008 | -6.207 | Chiral THF stereo exploration |
| 10 | CURE_10G_007 | -6.861 | P1 benzyl group added — first major P1 improvement |
| 11 | CURE_11G_007 | -7.265 | meta-Fluorobenzyl P1 — breakthrough +0.4 kcal/mol |
| 12 | CURE_12G_001 | -7.290 | Chiral R-OH on linker stereochemistry |
| 13 | CURE_13G_001 | -7.333 | R-OH + bis-THF optimised — best naphthalene result |
| 15 | Q15_020 | -7.398 | S-OH stereochemistry better than R-OH on isoquinoline |
| 16 | CURE_16G_007 | -7.487 | Hydroxy-isoquinoline left arm — OH on ring reaches Asp30 |
| 17 | CURE_17G_002 | -7.753 | Hydroxy-isoquinoline + 3,5-difluorobenzyl + S-OH + bis-THF |
| 18 | CURE_18G_010 | -7.660 | Regression — scaffold plateau reached, new scaffold needed |
| 19 | CURE_19G_002 * | -7.812 | Indole + 3,5-diF + S-OH + bis-THF |

## Key Learnings

- **Left arm**: Isoquinoline > Naphthalene; OH on isoquinoline adds H-bond to Asp30
- **P1 group**: meta-Fluorobenzyl optimal; 3,5-difluoro also strong
- **OH stereo**: S-OH optimal on isoquinoline scaffold (R-OH better on naphthalene)
- **Right arm**: bis-THF bicyclic > single THF > THP; hydroxy-bis-THF underperforms
- **Linker**: NH-CO core locked in; N-methyl blocks key H-bond
- **Quantum search**: S-OH + isoquinoline combination found via 10-qubit Grover search

## Lead Compound

**CURE_19G_002** — Indole + 3,5-diF + S-OH + bis-THF

Binding affinity: -7.812 kcal/mol (AutoDock Vina, HIV-1 Protease 1HVR)

SMILES: `Oc1ccc2ccc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@H](O)CNC(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)nc2c1`

## Next Generation (CURE_17G)

Strategy: Maximise hydroxy-isoquinoline scaffold
- Combine hydroxy-isoquinoline with 3,5-difluorobenzyl
- Test alternate OH position on isoquinoline ring
- Methoxy vs hydroxy comparison
- Diol linker variant
- High exhaustiveness reconfirm at 32

## Novelty Status

- ChEMBL (85% similarity): **0 matches** for all top compounds
- PubChem (85% similarity): Fragment-level matches only (different full molecules)
- Patent search: **Pending** (Google Patents / Espacenet)
- Assessment: Potentially novel full molecular architecture
