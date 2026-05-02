"""Test validate() directly without a full campaign"""
import autonomous_drug_agent as m

class FakeLog:
    def log(self, agent, msg):
        print(f"  [{agent}] {msg}")

fake_compounds = [
    {"id": "TEST_001", "smiles": "c1ccncc1", "dock_affinity": -5.5, "dip_advantage_tier": "FAIL"},
    {"id": "TEST_002", "smiles": "c1ccccc1", "dock_affinity": -6.2, "dip_advantage_tier": "FAIL"},
    {"id": "TEST_003", "smiles": "c1cnccn1", "dock_affinity": -7.1, "dip_advantage_tier": "FAIL"},
    {"id": "TEST_004", "smiles": "c1ncncn1", "dock_affinity": -4.8, "dip_advantage_tier": "FAIL"},
    {"id": "TEST_005", "smiles": "c1cncnc1", "dock_affinity": -5.9, "dip_advantage_tier": "FAIL"},
]

original = {c["id"]: c["dock_affinity"] for c in fake_compounds}
print("BEFORE validate():")
for cid, aff in original.items():
    print(f"  {cid}: {aff}")

print("\n--- Calling validate() ---")
v = m.ValidatorAgent(logger=FakeLog(), selectivity_targets=[], ref_affinity=-9.43, target_key="HIV_DIP")
result = v.validate(fake_compounds)

print("\nAFTER validate():")
for c in result:
    cid = c["id"]
    new_aff = c["dock_affinity"]
    delta = new_aff - original[cid]
    physics_mark = " [physics_validated=True]" if c.get("physics_validated") else ""
    print(f"  {cid}: {new_aff:.2f} (delta={delta:+.2f}){physics_mark}")

print()
if any(c.get("physics_validated") for c in result):
    print("PHYSICS IS WORKING — top compounds got -0.2 enhancement")
else:
    print("PHYSICS DID NOT FIRE")
    print(f"  PHYSICS_AVAILABLE = {getattr(m, 'PHYSICS_AVAILABLE', 'NOT DEFINED')}")
