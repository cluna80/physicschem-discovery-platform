# -*- coding: utf-8 -*-
"""
Search ChEMBL for similar compounds to your HIV candidates
Find known active compounds and their binding affinities
"""

from chembl_webresource_client.new_client import new_client
import json

# Your best compound from the CURE_15G series (with N-methyl P1' filling)
YOUR_SMILES = "c1ccc2cc(C(=O)N[C@@H](Cc3cccc(F)c3)[C@@H](O)CN(C)C(=O)[C@@H]4CO[C@@H]5OCCO[C@@H]45)ccc2c1"

print("="*80)
print("ChEMBL SEARCH - Finding similar HIV compounds")
print("="*80)
print(f"\nSearching for compounds similar to:\n{YOUR_SMILES[:100]}...\n")

# Search by similarity
similarity = new_client.similarity
results = similarity.filter(smiles=YOUR_SMILES, similarity=85).only(
    ['molecule_chembl_id', 'similarity', 'pref_name', 'max_phase', 
     'molecule_properties', 'pchembl_values', 'activities']
)

print("SIMALARITY SEARCH RESULTS:")
print("-"*80)
found = 0
for r in results[:10]:
    found += 1
    print(f"\nCompound: {r.get('molecule_chembl_id', 'N/A')}")
    print(f"  Similarity: {r.get('similarity', 0):.1f}%")
    print(f"  Name: {r.get('pref_name', 'Not named')}")
    print(f"  Max Phase: {r.get('max_phase', 'N/A')}")
    
    # Get properties
    props = r.get('molecule_properties', {})
    if props:
        print(f"  MW: {props.get('full_mwt', 'N/A')}")
        print(f"  LogP: {props.get('alogp', 'N/A')}")
        print(f"  HBA: {props.get('hba', 'N/A')}")
        print(f"  HBD: {props.get('hbd', 'N/A')}")

if found == 0:
    print("No similar compounds found with 85% similarity.")
    print("Trying with lower similarity threshold...")
    
    results = similarity.filter(smiles=YOUR_SMILES, similarity=70).only(
        ['molecule_chembl_id', 'similarity', 'pref_name', 'max_phase']
    )
    
    for r in results[:5]:
        found += 1
        print(f"\nCompound: {r.get('molecule_chembl_id', 'N/A')}")
        print(f"  Similarity: {r.get('similarity', 0):.1f}%")
        print(f"  Name: {r.get('pref_name', 'Not named')}")
        print(f"  Max Phase: {r.get('max_phase', 'N/A')}")

print("\n" + "="*80)
print("SEARCHING FOR HIV PROTEASE INHIBITORS")
print("="*80)

# Search for known HIV protease inhibitors
activity = new_client.activity
hits = activity.filter(target_chembl_id='CHEMBL256', standard_type='IC50').only(
    ['molecule_chembl_id', 'standard_value', 'standard_units', 'standard_type']
)

print("\nKnown HIV Protease Inhibitors (IC50 values):")
print("-"*80)
count = 0
for act in hits[:20]:
    if act.get('standard_value'):
        count += 1
        print(f"  {act.get('molecule_chembl_id', 'N/A')}: IC50 = {act.get('standard_value', 'N/A')} {act.get('standard_units', 'nM')}")

print(f"\nFound {count} known HIV protease inhibitors in ChEMBL")
print("="*80)
