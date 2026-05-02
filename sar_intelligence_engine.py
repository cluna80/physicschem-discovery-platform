"""
sar_intelligence_engine.py
=========================
Module 2: SAR Intelligence Engine for Autonomous Pharmaceutical Lab v3

Automated lead optimization through systematic structure-activity relationship analysis:
- AnalogGeneratorAgent: Generate 1000s of structural analogs from lead hits
- ScaffoldHopAgent: Bioisostere replacement and scaffold morphing  
- FragmentLinkerAgent: Optimize spacers and connecting atoms
- SARAnalysisAgent: Map activity cliffs and identify key pharmacophores

Integrates with enhanced_physics_engine.py and existing DIP scoring.
"""

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, Crippen, rdMolDescriptors
from rdkit.Chem import BRICS, Recap, rdRGroupDecomposition
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.Chem.FilterCatalog import FilterCatalog, FilterCatalogParams
import itertools
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import subprocess
import tempfile

@dataclass
class SARPoint:
    """Single structure-activity relationship data point"""
    compound_id: str
    smiles: str
    activity: float  # binding energy kcal/mol
    properties: Dict[str, float]  # MW, LogP, TPSA, etc.
    scaffold: str    # Murcko scaffold
    r_groups: Dict[str, str]  # R-group decomposition
    confidence: float
    dip_advantage: Optional[float] = None  # DIP competitive advantage
    
@dataclass
class AnalogSeries:
    """Series of analogs with common scaffold"""
    scaffold: str
    compounds: List[SARPoint]
    activity_range: Tuple[float, float]
    r_group_sar: Dict[str, List[Tuple[str, float]]]  # R-group → [(SMILES, activity)]
    lead_compound: str
    optimization_suggestions: List[str]

class AnalogGeneratorAgent:
    """Generate systematic analogs from lead compounds"""
    
    def __init__(self, fragment_db_path: str = None):
        self.logger = logging.getLogger(__name__)
        
        # Load fragment databases for R-group enumeration
        self.r_group_db = self._load_r_group_database(fragment_db_path)
        
        # Setup PAINS/ADMET filters
        params = FilterCatalogParams()
        params.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
        self.pains_filter = FilterCatalog(params)
        
    def generate_analogs(self, lead_smiles: str, lead_id: str, 
                        modifications_per_position: int = 20,
                        max_analogs: int = 1000) -> List[Dict]:
        """Generate systematic analogs of a lead compound"""
        
        mol = Chem.MolFromSmiles(lead_smiles)
        if not mol:
            self.logger.error(f"Invalid SMILES: {lead_smiles}")
            return []
            
        analogs = []
        
        # Strategy 1: R-group enumeration
        analogs.extend(self._r_group_enumeration(mol, lead_id, modifications_per_position))
        
        # Strategy 2: Ring replacement (bioisosteres)
        analogs.extend(self._ring_replacements(mol, lead_id))
        
        # Strategy 3: Functional group morphing
        analogs.extend(self._functional_group_morphing(mol, lead_id))
        
        # Strategy 4: Linker optimization (if multiple fragments)
        analogs.extend(self._linker_optimization(mol, lead_id))
        
        # Filter and rank
        analogs = self._filter_analogs(analogs, max_analogs)
        
        self.logger.info(f"Generated {len(analogs)} analogs for {lead_id}")
        return analogs
        
    def _r_group_enumeration(self, mol: Chem.Mol, lead_id: str, 
                           modifications_per_position: int) -> List[Dict]:
        """Systematic R-group substitution"""
        
        analogs = []
        
        # Find substitutable positions using BRICS decomposition
        brics_bonds = list(BRICS.FindBRICSBonds(mol))
        
        for bond_idx, (atom1_idx, atom2_idx) in enumerate(brics_bonds[:5]):  # Limit to 5 positions
            
            # Break bond and enumerate R-groups
            for r_group_smiles in self.r_group_db[:modifications_per_position]:
                
                try:
                    # Create analog by replacing R-group
                    analog_mol = self._substitute_r_group(mol, atom1_idx, atom2_idx, r_group_smiles)
                    
                    if analog_mol:
                        analog_smiles = Chem.MolToSmiles(analog_mol)
                        
                        analogs.append({
                            "compound_id": f"{lead_id}_R{bond_idx}_{len(analogs)}",
                            "smiles": analog_smiles,
                            "parent": lead_id,
                            "modification_type": "R_group_substitution",
                            "modification_site": f"bond_{atom1_idx}_{atom2_idx}",
                            "r_group": r_group_smiles,
                            "predicted_activity": None  # To be calculated by docking
                        })
                        
                except Exception as e:
                    self.logger.debug(f"R-group substitution failed: {e}")
                    continue
                    
        return analogs
        
    def _ring_replacements(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Replace rings with bioisosteric equivalents"""
        
        analogs = []
        
        # Common bioisosteric ring replacements
        ring_replacements = {
            # Original → Replacements
            "c1ccccc1": ["c1ccncc1", "c1cncnc1", "c1cnccn1"],  # benzene → pyridines
            "c1ccncc1": ["c1ccccc1", "c1cncnc1", "c1cnscn1"],  # pyridine variants
            "c1cncnc1": ["c1ccncc1", "c1cnccn1", "c1nnccn1"],  # pyrimidine variants
        }
        
        mol_smiles = Chem.MolToSmiles(mol)
        
        for original_ring, replacements in ring_replacements.items():
            if original_ring in mol_smiles:
                
                for replacement_ring in replacements:
                    try:
                        # Perform ring replacement
                        analog_smiles = mol_smiles.replace(original_ring, replacement_ring, 1)
                        analog_mol = Chem.MolFromSmiles(analog_smiles)
                        
                        if analog_mol and Chem.SanitizeMol(analog_mol, catchErrors=True) == 0:
                            analogs.append({
                                "compound_id": f"{lead_id}_ring_{len(analogs)}",
                                "smiles": analog_smiles,
                                "parent": lead_id,
                                "modification_type": "ring_replacement",
                                "original_ring": original_ring,
                                "replacement_ring": replacement_ring,
                                "predicted_activity": None
                            })
                            
                    except Exception as e:
                        self.logger.debug(f"Ring replacement failed: {e}")
                        continue
                        
        return analogs
        
    def _functional_group_morphing(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Morph functional groups to bioisosteric equivalents"""
        
        analogs = []
        
        # Functional group replacements (SMARTS patterns)
        fg_replacements = {
            # Carboxyl acid variants
            "[CX3](=O)[OX2H1]": ["[CX3](=O)[OX2H0][CX4H3]", "[CX3](=O)[NX3H2]", "S(=O)(=O)[OX2H1]"],
            # Amide variants  
            "[CX3](=[OX1])[NX3]": ["[CX3](=[OX1])[OX2]", "[CX3](=[SX1])[NX3]", "[SX2][CX3](=[OX1])"],
            # Alcohol variants
            "[CX4][OX2H1]": ["[CX4][SX2H1]", "[CX4][NX3H2]", "[CX4F1]"],
        }
        
        for fg_smarts, replacements in fg_replacements.items():
            matches = mol.GetSubstructMatches(Chem.MolFromSmarts(fg_smarts))
            
            for match_idx, match in enumerate(matches[:2]):  # Limit to 2 matches per FG
                for repl_idx, replacement_smarts in enumerate(replacements):
                    
                    try:
                        # Perform functional group replacement using reaction SMARTS
                        rxn_smarts = f"[{fg_smarts}]>>[{replacement_smarts}]"
                        rxn = AllChem.ReactionFromSmarts(rxn_smarts)
                        
                        products = rxn.RunReactants((mol,))
                        
                        if products:
                            analog_mol = products[0][0]
                            Chem.SanitizeMol(analog_mol)
                            analog_smiles = Chem.MolToSmiles(analog_mol)
                            
                            analogs.append({
                                "compound_id": f"{lead_id}_fg_{match_idx}_{repl_idx}",
                                "smiles": analog_smiles,
                                "parent": lead_id,
                                "modification_type": "functional_group_morph",
                                "original_fg": fg_smarts,
                                "replacement_fg": replacement_smarts,
                                "predicted_activity": None
                            })
                            
                    except Exception as e:
                        self.logger.debug(f"Functional group morphing failed: {e}")
                        continue
                        
        return analogs
        
    def _linker_optimization(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Optimize linkers between fragments"""
        
        analogs = []
        
        # Common linker modifications
        linker_patterns = {
            # Single bonds → various linkers
            "[*]-[*]": ["[*]C[*]", "[*]CC[*]", "[*]CCC[*]", "[*]O[*]", "[*]N[*]", "[*]S[*]"],
            # Two-atom linkers → variants
            "[*]C[*]": ["[*]CC[*]", "[*]N[*]", "[*]O[*]", "[*]S[*]"],
            "[*]CC[*]": ["[*]C[*]", "[*]CCC[*]", "[*]COC[*]", "[*]CNC[*]"],
        }
        
        mol_smiles = Chem.MolToSmiles(mol)
        
        for pattern_smarts, replacements in linker_patterns.items():
            pattern = Chem.MolFromSmarts(pattern_smarts)
            matches = mol.GetSubstructMatches(pattern)
            
            for match in matches[:3]:  # Limit to 3 linker positions
                for repl_smarts in replacements:
                    
                    try:
                        # Create reaction for linker replacement
                        rxn_smarts = f"{pattern_smarts}>>{repl_smarts}"
                        rxn = AllChem.ReactionFromSmarts(rxn_smarts)
                        
                        products = rxn.RunReactants((mol,))
                        
                        if products:
                            analog_mol = products[0][0]
                            analog_smiles = Chem.MolToSmiles(analog_mol)
                            
                            analogs.append({
                                "compound_id": f"{lead_id}_linker_{len(analogs)}",
                                "smiles": analog_smiles,
                                "parent": lead_id,
                                "modification_type": "linker_optimization",
                                "original_linker": pattern_smarts,
                                "new_linker": repl_smarts,
                                "predicted_activity": None
                            })
                            
                    except Exception as e:
                        self.logger.debug(f"Linker optimization failed: {e}")
                        continue
                        
        return analogs
        
    def _substitute_r_group(self, mol: Chem.Mol, atom1_idx: int, 
                          atom2_idx: int, r_group_smiles: str) -> Optional[Chem.Mol]:
        """Substitute R-group at specific bond position"""
        
        try:
            # Break the bond
            emol = Chem.EditableMol(mol)
            emol.RemoveBond(atom1_idx, atom2_idx)
            
            # Add R-group
            r_group_mol = Chem.MolFromSmiles(r_group_smiles)
            if not r_group_mol:
                return None
                
            # Connect R-group (simplified - real implementation more complex)
            combined = Chem.CombineMols(emol.GetMol(), r_group_mol)
            
            # Would need proper bond formation logic here
            # This is a simplified placeholder
            
            return combined
            
        except Exception:
            return None
            
    def _filter_analogs(self, analogs: List[Dict], max_analogs: int) -> List[Dict]:
        """Filter analogs by drug-likeness and PAINS"""
        
        filtered = []
        
        for analog in analogs:
            mol = Chem.MolFromSmiles(analog["smiles"])
            if not mol:
                continue
                
            # Drug-likeness filters
            mw = Descriptors.MolWt(mol)
            logp = Crippen.MolLogP(mol)
            hbd = rdMolDescriptors.CalcNumHBD(mol)
            hba = rdMolDescriptors.CalcNumHBA(mol)
            tpsa = rdMolDescriptors.CalcTPSA(mol)
            
            # Lipinski's Rule of 5
            if mw > 500 or logp > 5 or hbd > 5 or hba > 10:
                continue
                
            # TPSA filter
            if tpsa > 140:
                continue
                
            # PAINS filter
            if self.pains_filter.HasMatch(mol):
                continue
                
            # Calculate drug-likeness score
            drug_score = self._calculate_drug_score(mw, logp, hbd, hba, tpsa)
            analog["drug_score"] = drug_score
            
            filtered.append(analog)
            
        # Sort by drug-likeness and truncate
        filtered.sort(key=lambda x: x["drug_score"], reverse=True)
        return filtered[:max_analogs]
        
    def _calculate_drug_score(self, mw: float, logp: float, hbd: int, 
                            hba: int, tpsa: float) -> float:
        """Calculate composite drug-likeness score"""
        
        # Ideal ranges and penalties
        score = 1.0
        
        # MW penalty (optimal ~300-400 Da)
        if mw < 200:
            score -= (200 - mw) / 200 * 0.3
        elif mw > 400:
            score -= (mw - 400) / 100 * 0.3
            
        # LogP penalty (optimal ~2-3)
        if logp < 0:
            score -= abs(logp) * 0.2
        elif logp > 4:
            score -= (logp - 4) * 0.2
            
        # TPSA penalty (optimal 60-90)
        if tpsa < 40:
            score -= (40 - tpsa) / 40 * 0.2
        elif tpsa > 120:
            score -= (tpsa - 120) / 20 * 0.2
            
        return max(0.0, score)
        
    def _load_r_group_database(self, db_path: str = None) -> List[str]:
        """Load R-group fragments for enumeration"""
        
        # Default R-group library if no database provided
        default_r_groups = [
            # Alkyl chains
            "C", "CC", "CCC", "CCCC", "CCC(C)C", "CC(C)C",
            # Aromatic
            "c1ccccc1", "c1ccncc1", "c1cncnc1", "c1ccoc1", "c1ccsc1",
            # Halogenated
            "CF", "CCF", "CF3", "Cl", "Br", "F",
            # Heteroatoms
            "O", "N", "S", "OC", "NC", "SC",
            # Functional groups
            "C(=O)O", "C(=O)N", "C(=O)C", "S(=O)(=O)N", "C#N",
            # Heterocycles
            "c1ccncc1", "c1cncnc1", "c1nnccn1", "C1CCNCC1", "C1CCOCC1",
        ]
        
        if db_path and Path(db_path).exists():
            try:
                with open(db_path) as f:
                    custom_groups = [line.strip() for line in f if line.strip()]
                return custom_groups + default_r_groups
            except Exception as e:
                self.logger.warning(f"Could not load R-group database: {e}")
                
        return default_r_groups


class ScaffoldHopAgent:
    """Identify and perform scaffold hopping for lead optimization"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common scaffold hops for drug discovery
        self.scaffold_hops = self._load_scaffold_hop_database()
        
    def find_scaffold_hops(self, lead_smiles: str, lead_id: str, 
                          max_hops: int = 50) -> List[Dict]:
        """Find scaffold hopping opportunities"""
        
        mol = Chem.MolFromSmiles(lead_smiles)
        if not mol:
            return []
            
        # Extract Murcko scaffold
        scaffold = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smiles = Chem.MolToSmiles(scaffold)
        
        hops = []
        
        # Strategy 1: Database lookup of known scaffold hops
        hops.extend(self._database_scaffold_hops(scaffold_smiles, lead_id))
        
        # Strategy 2: Systematic ring morphing
        hops.extend(self._systematic_ring_morphing(mol, lead_id))
        
        # Strategy 3: Privileged scaffold insertion
        hops.extend(self._privileged_scaffold_insertion(mol, lead_id))
        
        return hops[:max_hops]
        
    def _database_scaffold_hops(self, scaffold_smiles: str, lead_id: str) -> List[Dict]:
        """Look up known scaffold hops from database"""
        
        hops = []
        
        for original, hop_targets in self.scaffold_hops.items():
            if original in scaffold_smiles:
                for target_scaffold in hop_targets:
                    
                    hopped_smiles = scaffold_smiles.replace(original, target_scaffold, 1)
                    
                    hops.append({
                        "compound_id": f"{lead_id}_hop_{len(hops)}",
                        "smiles": hopped_smiles,
                        "parent": lead_id,
                        "modification_type": "scaffold_hop",
                        "original_scaffold": original,
                        "target_scaffold": target_scaffold,
                        "hop_type": "database_known",
                        "predicted_activity": None
                    })
                    
        return hops
        
    def _systematic_ring_morphing(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Systematically morph ring systems"""
        
        hops = []
        
        # Ring size changes
        ring_morphs = {
            # 6-membered → 5-membered
            "c1ccccc1": ["c1cccc1", "c1ccco1", "c1cccs1"],
            # 5-membered → 6-membered  
            "c1ccco1": ["c1ccccc1", "c1ccncc1"],
            # Nitrogen insertion/deletion
            "c1ccccc1": ["c1ccncc1", "c1cncnc1"],
            "c1ccncc1": ["c1ccccc1", "c1cncnc1"],
        }
        
        mol_smiles = Chem.MolToSmiles(mol)
        
        for original, morphs in ring_morphs.items():
            if original in mol_smiles:
                for morph in morphs:
                    
                    hopped_smiles = mol_smiles.replace(original, morph, 1)
                    
                    try:
                        hopped_mol = Chem.MolFromSmiles(hopped_smiles)
                        if hopped_mol and Chem.SanitizeMol(hopped_mol, catchErrors=True) == 0:
                            
                            hops.append({
                                "compound_id": f"{lead_id}_morph_{len(hops)}",
                                "smiles": hopped_smiles,
                                "parent": lead_id,
                                "modification_type": "ring_morph",
                                "original_ring": original,
                                "morphed_ring": morph,
                                "predicted_activity": None
                            })
                            
                    except Exception:
                        continue
                        
        return hops
        
    def _privileged_scaffold_insertion(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Insert privileged scaffolds known for activity"""
        
        hops = []
        
        # Privileged scaffolds in drug discovery
        privileged_scaffolds = [
            "c1cnc2ccccc2c1",  # quinoline  
            "c1ccc2ncccc2c1",  # isoquinoline
            "c1ccc2c(c1)nccc2N",  # aminoquinoline
            "c1cnc2nc(ccc2c1)N",  # quinazoline
            "n1cnc2ccccc2c1",  # quinoxaline
            "c1cc2ccccc2cc1",  # naphthalene
        ]
        
        # Try inserting privileged scaffolds
        for scaffold in privileged_scaffolds:
            
            # Simple insertion strategy (real implementation would be more sophisticated)
            try:
                # Combine with existing molecule fragments
                scaffold_mol = Chem.MolFromSmiles(scaffold)
                combined = Chem.CombineMols(mol, scaffold_mol)
                combined_smiles = Chem.MolToSmiles(combined)
                
                hops.append({
                    "compound_id": f"{lead_id}_priv_{len(hops)}",
                    "smiles": combined_smiles,
                    "parent": lead_id,
                    "modification_type": "privileged_insertion",
                    "inserted_scaffold": scaffold,
                    "predicted_activity": None
                })
                
            except Exception:
                continue
                
        return hops
        
    def _load_scaffold_hop_database(self) -> Dict[str, List[str]]:
        """Load database of known successful scaffold hops"""
        
        return {
            # Benzene replacements
            "c1ccccc1": ["c1ccncc1", "c1cncnc1", "c1cnccn1", "c1nnccn1"],
            
            # Pyridine variants
            "c1ccncc1": ["c1cncnc1", "c1cnccn1", "c1ccccc1"],
            
            # Five-membered heterocycles
            "c1ccoc1": ["c1ccsc1", "c1cc[nH]c1", "c1cccn1"],
            
            # Saturated rings
            "C1CCCCC1": ["C1CCNCC1", "C1CCOCC1", "C1CCSCC1"],
            
            # Fused systems
            "c1ccc2ccccc2c1": ["c1ccc2ncccc2c1", "c1cnc2ccccc2c1"],
        }


class FragmentLinkerAgent:
    """Optimize linkers between molecular fragments"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.linker_library = self._build_linker_library()
        
    def optimize_linkers(self, lead_smiles: str, lead_id: str,
                        max_linker_variants: int = 100) -> List[Dict]:
        """Optimize linkers in lead compound"""
        
        mol = Chem.MolFromSmiles(lead_smiles)
        if not mol:
            return []
            
        linker_variants = []
        
        # Strategy 1: Identify existing linkers and replace
        linker_variants.extend(self._replace_existing_linkers(mol, lead_id))
        
        # Strategy 2: Insert new linkers at cut points
        linker_variants.extend(self._insert_linkers_at_cuts(mol, lead_id))
        
        # Strategy 3: Conformationally restricted linkers
        linker_variants.extend(self._conformationally_restricted_linkers(mol, lead_id))
        
        return linker_variants[:max_linker_variants]
        
    def _replace_existing_linkers(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Replace existing linkers with alternatives"""
        
        variants = []
        mol_smiles = Chem.MolToSmiles(mol)
        
        # Common linker patterns to replace
        existing_linkers = {
            "C": ["CC", "CCC", "O", "N", "S", "C(=O)", "C(=O)N", "C(=O)O"],
            "CC": ["C", "CCC", "COC", "CNC", "CSC", "C=C"],
            "CCC": ["CC", "CCCC", "COCOC", "CNCNC", "C=CC"],
            "O": ["C", "N", "S", "C(=O)", "S(=O)"],
            "N": ["C", "O", "S", "C(=O)N", "S(=O)(=O)N"],
            "S": ["C", "O", "N", "S(=O)", "S(=O)(=O)"],
        }
        
        for current_linker, replacements in existing_linkers.items():
            # Look for linker pattern in molecule
            if current_linker in mol_smiles:
                
                for replacement in replacements:
                    try:
                        # Simple string replacement (real implementation would use SMARTS)
                        variant_smiles = mol_smiles.replace(current_linker, replacement, 1)
                        variant_mol = Chem.MolFromSmiles(variant_smiles)
                        
                        if variant_mol and Chem.SanitizeMol(variant_mol, catchErrors=True) == 0:
                            
                            # Calculate linker properties
                            linker_props = self._calculate_linker_properties(replacement)
                            
                            variants.append({
                                "compound_id": f"{lead_id}_link_{len(variants)}",
                                "smiles": variant_smiles,
                                "parent": lead_id,
                                "modification_type": "linker_replacement",
                                "original_linker": current_linker,
                                "new_linker": replacement,
                                "linker_length": linker_props["length"],
                                "linker_flexibility": linker_props["flexibility"],
                                "predicted_activity": None
                            })
                            
                    except Exception:
                        continue
                        
        return variants
        
    def _insert_linkers_at_cuts(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Insert linkers at potential cutting points"""
        
        variants = []
        
        # Use BRICS to find reasonable cutting points
        brics_bonds = list(BRICS.FindBRICSBonds(mol))
        
        for bond_idx, (atom1_idx, atom2_idx) in enumerate(brics_bonds[:5]):
            
            # Try inserting different linkers at this position
            for linker_smiles in self.linker_library[:10]:  # Top 10 linkers
                
                try:
                    # Insert linker between atoms (simplified)
                    # Real implementation would properly break bond and insert
                    
                    # For now, just conceptual representation
                    variant_data = {
                        "compound_id": f"{lead_id}_insert_{bond_idx}_{len(variants)}",
                        "smiles": Chem.MolToSmiles(mol),  # Placeholder
                        "parent": lead_id,
                        "modification_type": "linker_insertion",
                        "insertion_point": f"bond_{atom1_idx}_{atom2_idx}",
                        "inserted_linker": linker_smiles,
                        "predicted_activity": None
                    }
                    
                    variants.append(variant_data)
                    
                except Exception:
                    continue
                    
        return variants
        
    def _conformationally_restricted_linkers(self, mol: Chem.Mol, lead_id: str) -> List[Dict]:
        """Add conformationally restricted linkers for improved selectivity"""
        
        variants = []
        
        # Rigid linkers for conformational control
        rigid_linkers = [
            "C#C",          # alkyne
            "c1ccccc1",     # benzene
            "C=C",          # alkene
            "c1ccncc1",     # pyridine
            "C1CC1",        # cyclopropane
            "C1CCC1",       # cyclobutane
            "C1CCCC1",      # cyclopentane
        ]
        
        mol_smiles = Chem.MolToSmiles(mol)
        
        # Look for flexible linkers to replace with rigid ones
        flexible_patterns = ["CC", "CCC", "CCCC", "COC", "CNC"]
        
        for flexible in flexible_patterns:
            if flexible in mol_smiles:
                
                for rigid in rigid_linkers:
                    try:
                        variant_smiles = mol_smiles.replace(flexible, rigid, 1)
                        variant_mol = Chem.MolFromSmiles(variant_smiles)
                        
                        if variant_mol and Chem.SanitizeMol(variant_mol, catchErrors=True) == 0:
                            
                            variants.append({
                                "compound_id": f"{lead_id}_rigid_{len(variants)}",
                                "smiles": variant_smiles,
                                "parent": lead_id,
                                "modification_type": "rigidification",
                                "original_linker": flexible,
                                "rigid_linker": rigid,
                                "conformational_restriction": True,
                                "predicted_activity": None
                            })
                            
                    except Exception:
                        continue
                        
        return variants
        
    def _calculate_linker_properties(self, linker_smiles: str) -> Dict[str, float]:
        """Calculate properties of linker"""
        
        linker_mol = Chem.MolFromSmiles(linker_smiles)
        if not linker_mol:
            return {"length": 0, "flexibility": 0}
            
        # Estimate linker length (number of non-hydrogen atoms)
        length = linker_mol.GetNumAtoms()
        
        # Estimate flexibility (number of rotatable bonds)
        flexibility = rdMolDescriptors.CalcNumRotatableBonds(linker_mol)
        
        return {"length": length, "flexibility": flexibility}
        
    def _build_linker_library(self) -> List[str]:
        """Build library of common linkers"""
        
        return [
            # Basic linkers
            "C", "CC", "CCC", "CCCC",
            
            # Heteroatom linkers
            "O", "N", "S", "C(=O)", "C(=O)N", "C(=O)O",
            
            # Extended linkers
            "COC", "CNC", "CSC", "C(=O)NC", "C(=O)OC",
            
            # Aromatic linkers
            "c1ccccc1", "c1ccncc1", "c1cncnc1",
            
            # Rigid linkers
            "C#C", "C=C", "C1CC1", "C1CCC1",
            
            # PEG-like linkers
            "COCOC", "COCOCOC", "NCNC", "SCSC",
            
            # Amide linkers
            "C(=O)NCCNC(=O)", "C(=O)NCNC(=O)",
            
            # Urea/carbamate linkers
            "NC(=O)N", "OC(=O)N", "NC(=O)O",
        ]


class SARAnalysisAgent:
    """Analyze structure-activity relationships and identify key pharmacophores"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def analyze_sar_series(self, sar_points: List[SARPoint]) -> AnalogSeries:
        """Analyze SAR for a series of analogs"""
        
        if not sar_points:
            return None
            
        # Group by scaffold
        scaffold_groups = {}
        for point in sar_points:
            if point.scaffold not in scaffold_groups:
                scaffold_groups[point.scaffold] = []
            scaffold_groups[point.scaffold].append(point)
            
        # Analyze the largest scaffold group
        largest_group = max(scaffold_groups.values(), key=len)
        main_scaffold = largest_group[0].scaffold
        
        # Calculate activity range
        activities = [point.activity for point in largest_group]
        activity_range = (min(activities), max(activities))
        
        # Perform R-group SAR analysis
        r_group_sar = self._analyze_r_group_sar(largest_group)
        
        # Find lead compound (best activity + confidence)
        lead_compound = max(largest_group, 
                           key=lambda p: p.activity * p.confidence).compound_id
        
        # Generate optimization suggestions
        suggestions = self._generate_optimization_suggestions(largest_group, r_group_sar)
        
        return AnalogSeries(
            scaffold=main_scaffold,
            compounds=largest_group,
            activity_range=activity_range,
            r_group_sar=r_group_sar,
            lead_compound=lead_compound,
            optimization_suggestions=suggestions
        )
        
    def _analyze_r_group_sar(self, compounds: List[SARPoint]) -> Dict[str, List[Tuple[str, float]]]:
        """Analyze R-group contributions to activity"""
        
        r_group_sar = {}
        
        # Group compounds by R-group positions
        for compound in compounds:
            for position, r_group in compound.r_groups.items():
                if position not in r_group_sar:
                    r_group_sar[position] = []
                    
                r_group_sar[position].append((r_group, compound.activity))
                
        # Sort each position by activity
        for position in r_group_sar:
            r_group_sar[position].sort(key=lambda x: x[1], reverse=True)  # Best activity first
            
        return r_group_sar
        
    def _generate_optimization_suggestions(self, compounds: List[SARPoint], 
                                         r_group_sar: Dict[str, List[Tuple[str, float]]]) -> List[str]:
        """Generate specific optimization suggestions"""
        
        suggestions = []
        
        # Find best R-groups for each position
        for position, r_groups in r_group_sar.items():
            if len(r_groups) >= 2:
                best_r_group, best_activity = r_groups[0]
                worst_r_group, worst_activity = r_groups[-1]
                
                activity_diff = best_activity - worst_activity
                
                if activity_diff > 0.5:  # Significant difference
                    suggestions.append(
                        f"Position {position}: {best_r_group} gives {activity_diff:.1f} kcal/mol "
                        f"advantage over {worst_r_group}"
                    )
                    
        # Identify property-activity correlations
        mw_activities = [(p.properties.get('MW', 0), p.activity) for p in compounds]
        logp_activities = [(p.properties.get('LogP', 0), p.activity) for p in compounds]
        
        # MW correlation
        if len(mw_activities) >= 3:
            mw_corr = np.corrcoef([x[0] for x in mw_activities], 
                                 [x[1] for x in mw_activities])[0, 1]
            
            if abs(mw_corr) > 0.5:
                direction = "Increase" if mw_corr > 0 else "Decrease"
                suggestions.append(f"{direction} molecular weight (correlation: {mw_corr:.2f})")
                
        # LogP correlation  
        if len(logp_activities) >= 3:
            logp_corr = np.corrcoef([x[0] for x in logp_activities],
                                   [x[1] for x in logp_activities])[0, 1]
            
            if abs(logp_corr) > 0.5:
                direction = "Increase" if logp_corr > 0 else "Decrease"
                suggestions.append(f"{direction} lipophilicity (correlation: {logp_corr:.2f})")
                
        # DIP advantage suggestions (if available)
        dip_compounds = [p for p in compounds if p.dip_advantage is not None]
        if len(dip_compounds) >= 2:
            best_dip = max(dip_compounds, key=lambda p: p.dip_advantage)
            suggestions.append(
                f"Best DIP advantage: {best_dip.dip_advantage:.2f} kcal/mol "
                f"from compound {best_dip.compound_id}"
            )
            
        return suggestions
        
    def identify_activity_cliffs(self, compounds: List[SARPoint], 
                               similarity_threshold: float = 0.8,
                               activity_threshold: float = 1.0) -> List[Dict]:
        """Identify activity cliffs (similar structures, different activities)"""
        
        cliffs = []
        
        for i, compound1 in enumerate(compounds):
            for j, compound2 in enumerate(compounds[i+1:], i+1):
                
                # Calculate structural similarity
                mol1 = Chem.MolFromSmiles(compound1.smiles)
                mol2 = Chem.MolFromSmiles(compound2.smiles)
                
                if mol1 and mol2:
                    fp1 = AllChem.GetMorganFingerprintAsBitVect(mol1, 2)
                    fp2 = AllChem.GetMorganFingerprintAsBitVect(mol2, 2)
                    
                    similarity = DataStructs.TanimotoSimilarity(fp1, fp2)
                    activity_diff = abs(compound1.activity - compound2.activity)
                    
                    # Activity cliff criteria
                    if similarity >= similarity_threshold and activity_diff >= activity_threshold:
                        cliffs.append({
                            "compound1": compound1.compound_id,
                            "compound2": compound2.compound_id,
                            "similarity": similarity,
                            "activity_difference": activity_diff,
                            "smiles1": compound1.smiles,
                            "smiles2": compound2.smiles,
                            "activity1": compound1.activity,
                            "activity2": compound2.activity
                        })
                        
        # Sort by activity difference
        cliffs.sort(key=lambda x: x["activity_difference"], reverse=True)
        
        return cliffs


class SARIntelligenceEngine:
    """Main orchestrator for SAR-driven lead optimization"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {
            "analogs_per_lead": 500,
            "scaffold_hops_per_lead": 50,
            "linker_variants_per_lead": 100,
            "parallel_generation": True,
            "temp_dir": "/tmp/sar_engine"
        }
        
        self.analog_generator = AnalogGeneratorAgent()
        self.scaffold_hopper = ScaffoldHopAgent()
        self.linker_optimizer = FragmentLinkerAgent()
        self.sar_analyzer = SARAnalysisAgent()
        
        Path(self.config["temp_dir"]).mkdir(parents=True, exist_ok=True)
        
    def optimize_leads(self, lead_compounds: List[Dict], 
                      target_activity: float = -9.43) -> Dict:
        """Comprehensive lead optimization workflow"""
        
        all_analogs = []
        optimization_report = {
            "input_leads": len(lead_compounds),
            "target_activity": target_activity,
            "generated_analogs": 0,
            "sar_series": [],
            "activity_cliffs": [],
            "optimization_suggestions": [],
            "top_candidates": []
        }
        
        # Generate analogs for each lead
        for lead in lead_compounds:
            lead_id = lead["compound_id"]
            lead_smiles = lead["smiles"]
            
            self.logger.info(f"Optimizing lead: {lead_id}")
            
            # Generate all types of analogs
            analogs = []
            
            # Strategy 1: Systematic analogs
            analogs.extend(self.analog_generator.generate_analogs(
                lead_smiles, lead_id, max_analogs=self.config["analogs_per_lead"]
            ))
            
            # Strategy 2: Scaffold hops
            analogs.extend(self.scaffold_hopper.find_scaffold_hops(
                lead_smiles, lead_id, max_hops=self.config["scaffold_hops_per_lead"]
            ))
            
            # Strategy 3: Linker optimization
            analogs.extend(self.linker_optimizer.optimize_linkers(
                lead_smiles, lead_id, max_linker_variants=self.config["linker_variants_per_lead"]
            ))
            
            all_analogs.extend(analogs)
            
        optimization_report["generated_analogs"] = len(all_analogs)
        
        # TODO: Dock all analogs (would integrate with existing docking pipeline)
        # For now, assign placeholder predicted activities
        for analog in all_analogs:
            analog["predicted_activity"] = np.random.uniform(-8.0, -4.0)  # Placeholder
            
        # Convert to SARPoint objects for analysis
        sar_points = self._convert_to_sar_points(all_analogs)
        
        # Perform SAR analysis
        if sar_points:
            sar_series = self.sar_analyzer.analyze_sar_series(sar_points)
            if sar_series:
                optimization_report["sar_series"].append(sar_series.__dict__)
                optimization_report["optimization_suggestions"] = sar_series.optimization_suggestions
                
            # Find activity cliffs
            cliffs = self.sar_analyzer.identify_activity_cliffs(sar_points)
            optimization_report["activity_cliffs"] = cliffs
            
        # Identify top candidates
        top_candidates = sorted(all_analogs, 
                               key=lambda x: x.get("predicted_activity", 0), 
                               reverse=True)[:20]
        optimization_report["top_candidates"] = top_candidates
        
        # Save optimization report
        report_file = Path(self.config["temp_dir"]) / "sar_optimization_report.json"
        with open(report_file, "w") as f:
            json.dump(optimization_report, f, indent=2, default=str)
            
        self.logger.info(f"SAR optimization complete. Report: {report_file}")
        
        return optimization_report
        
    def _convert_to_sar_points(self, analogs: List[Dict]) -> List[SARPoint]:
        """Convert analog dictionaries to SARPoint objects"""
        
        sar_points = []
        
        for analog in analogs:
            if not analog.get("smiles"):
                continue
                
            mol = Chem.MolFromSmiles(analog["smiles"])
            if not mol:
                continue
                
            # Calculate properties
            properties = {
                "MW": Descriptors.MolWt(mol),
                "LogP": Crippen.MolLogP(mol),
                "TPSA": rdMolDescriptors.CalcTPSA(mol),
                "HBD": rdMolDescriptors.CalcNumHBD(mol),
                "HBA": rdMolDescriptors.CalcNumHBA(mol),
                "RotBonds": rdMolDescriptors.CalcNumRotatableBonds(mol)
            }
            
            # Get scaffold
            scaffold = MurckoScaffold.GetScaffoldForMol(mol)
            scaffold_smiles = Chem.MolToSmiles(scaffold) if scaffold else ""
            
            # Placeholder R-group decomposition
            r_groups = {"R1": "placeholder", "R2": "placeholder"}
            
            sar_point = SARPoint(
                compound_id=analog["compound_id"],
                smiles=analog["smiles"],
                activity=analog.get("predicted_activity", 0.0),
                properties=properties,
                scaffold=scaffold_smiles,
                r_groups=r_groups,
                confidence=0.7,  # Placeholder confidence
                dip_advantage=analog.get("dip_advantage")
            )
            
            sar_points.append(sar_point)
            
        return sar_points


def integrate_sar_with_pipeline():
    """Integration function for autonomous_drug_agent.py"""
    
    def sar_optimization_workflow(compounds_csv: str, target_key: str,
                                 optimization_cycles: int = 2) -> str:
        """
        SAR optimization workflow to enhance lead discovery
        
        Args:
            compounds_csv: Path to CSV with lead compounds
            target_key: Target identifier (e.g., "HIV_DIP")  
            optimization_cycles: Number of SAR optimization cycles
            
        Returns:
            Path to optimized compounds CSV
        """
        import pandas as pd
        
        # Load lead compounds
        df = pd.read_csv(compounds_csv)
        
        # Convert to lead format expected by SAR engine
        leads = []
        for _, row in df.iterrows():
            leads.append({
                "compound_id": row["compound_id"],
                "smiles": row.get("smiles", ""),  # Would need SMILES generation
                "affinity": row.get("affinity", row.get("binding_energy", 0.0)),
                "confidence": row.get("confidence", 0.6)
            })
            
        # Setup SAR engine
        sar_config = {
            "analogs_per_lead": 100,  # Manageable for docking
            "scaffold_hops_per_lead": 25,
            "linker_variants_per_lead": 25,
            "temp_dir": f"/tmp/sar_{target_key}"
        }
        
        sar_engine = SARIntelligenceEngine(sar_config)
        
        # Run optimization cycles
        all_optimized = []
        current_leads = leads
        
        for cycle in range(optimization_cycles):
            print(f"SAR optimization cycle {cycle + 1}/{optimization_cycles}")
            
            # Generate optimized analogs
            optimization_report = sar_engine.optimize_leads(current_leads)
            
            # TODO: Dock top candidates (integrate with existing docking pipeline)
            # For now, use predicted activities
            
            # Select best candidates for next cycle
            top_candidates = optimization_report["top_candidates"][:10]
            current_leads = top_candidates
            all_optimized.extend(top_candidates)
            
        # Convert optimized compounds back to DataFrame format
        optimized_df = pd.DataFrame(all_optimized)
        
        # Save results
        optimized_csv = compounds_csv.replace('.csv', '_sar_optimized.csv')
        optimized_df.to_csv(optimized_csv, index=False)
        
        return optimized_csv
        
    return sar_optimization_workflow


if __name__ == "__main__":
    # Test the SAR Intelligence Engine
    print("Testing SAR Intelligence Engine...")
    
    # Mock lead compound from HIV_DIP results
    test_leads = [{
        "compound_id": "SEED_DIP_HYP_G006",
        "smiles": "O=c1nccc(OC2CCCNC2)[nH]1",  # From actual results
        "affinity": -5.458,
        "confidence": 0.7
    }]
    
    sar_engine = SARIntelligenceEngine({
        "analogs_per_lead": 50,  # Small for testing
        "scaffold_hops_per_lead": 10,
        "linker_variants_per_lead": 10,
    })
    
    optimization_report = sar_engine.optimize_leads(test_leads, target_activity=-9.43)
    
    print(f"Generated {optimization_report['generated_analogs']} analogs")
    print(f"Top 3 optimization suggestions:")
    for i, suggestion in enumerate(optimization_report['optimization_suggestions'][:3]):
        print(f"  {i+1}. {suggestion}")
        
    print("\nSAR Intelligence Engine loaded successfully!")
    print("Integration function available: sar_optimization_workflow()")
    print("\nNext: Integrate with docking pipeline for activity prediction")
