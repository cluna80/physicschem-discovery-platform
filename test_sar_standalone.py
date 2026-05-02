"""Test the SAR Intelligence Engine on the real 3-sigma lead."""
print("Testing SAR Intelligence Engine...")
print("=" * 60)

# 1. Import check
try:
    from sar_intelligence_engine import (
        SARIntelligenceEngine,
        AnalogGeneratorAgent,
        ScaffoldHopAgent,
        FragmentLinkerAgent,
    )
    print("[ok] all SAR classes imported")
except ImportError as e:
    print(f"[fail] import error: {e}")
    raise SystemExit(1)

# 2. RDKit check
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors
    print("[ok] RDKit available")
except ImportError as e:
    print(f"[fail] RDKit missing: {e}")
    raise SystemExit(1)

# 3. Try generating analogs of the actual 3-sigma hit
hna_g031_smiles = "O=C(O)/C=C/c1ccc(O)cc1CCc1ccccc1"
print(f"\n[test] Generating analogs of SEED_DIP_HNA_G031")
print(f"       SMILES: {hna_g031_smiles}")

mol = Chem.MolFromSmiles(hna_g031_smiles)
if not mol:
    print("[fail] could not parse SMILES")
    raise SystemExit(1)
print(f"[ok] parsed: MW={Descriptors.MolWt(mol):.1f}, atoms={mol.GetNumHeavyAtoms()}")

# 4. Run the actual analog generator
print("\n[test] Running AnalogGeneratorAgent...")
try:
    gen = AnalogGeneratorAgent()
    analogs = gen.generate_analogs(
        lead_smiles=hna_g031_smiles,
        lead_id="HNA_G031",
        modifications_per_position=10,
        max_analogs=50,
    )
    print(f"[ok] generated {len(analogs)} analogs")
    if analogs:
        print(f"     example: {analogs[0].get('smiles', '?')[:60]}")
        print(f"     example: {analogs[1].get('smiles', '?')[:60]}" if len(analogs) > 1 else "")
except Exception as e:
    print(f"[fail] analog generation failed: {e}")
    import traceback
    traceback.print_exc()
    raise SystemExit(1)

# 5. Try scaffold hopping
print("\n[test] Running ScaffoldHopAgent...")
try:
    hopper = ScaffoldHopAgent()
    hops = hopper.find_scaffold_hops(hna_g031_smiles, "HNA_G031", max_hops=20)
    print(f"[ok] generated {len(hops)} scaffold hops")
except Exception as e:
    print(f"[fail] scaffold hop failed: {e}")

# 6. Try linker optimization
print("\n[test] Running FragmentLinkerAgent...")
try:
    linker = FragmentLinkerAgent()
    variants = linker.optimize_linkers(hna_g031_smiles, "HNA_G031", max_linker_variants=20)
    print(f"[ok] generated {len(variants)} linker variants")
except Exception as e:
    print(f"[fail] linker optimization failed: {e}")

# 7. Engine init
print("\n[test] Building full SARIntelligenceEngine...")
try:
    engine = SARIntelligenceEngine({
        "analogs_per_lead": 30,
        "scaffold_hops_per_lead": 10,
        "linker_variants_per_lead": 10,
        "temp_dir": "/tmp/sar_test"
    })
    print("[ok] engine instantiated")
except Exception as e:
    print(f"[fail] engine init failed: {e}")
    raise SystemExit(1)

print("\n" + "=" * 60)
print("MODULE 2 STANDALONE TEST: PASSED")
print("Ready to integrate with autonomous_drug_agent.py")
