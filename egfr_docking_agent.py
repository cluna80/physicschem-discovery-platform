# -*- coding: utf-8 -*-
"""
EGFR Docking Agent for Autonomous AI Quantum Lab
Specialized for docking compounds against EGFR
"""

import subprocess
import os
from docking_agent import DockingAgent

class EGFRDockingAgent(DockingAgent):
    """Specialized docking agent for EGFR"""
    
    def __init__(self, pocket_file="egfr_pocket.pdbqt", vina_path="./bin/vina.exe"):
        super().__init__(vina_path)
        self.pocket_file = pocket_file
        self.binding_site = {
            'center': (22.0, 0.3, 52.8),
            'size': 20
        }
        
        if not os.path.exists(pocket_file):
            print(f"Warning: {pocket_file} not found.")
    
    def evaluate_egfr_compound(self, ligand_file, exhaustiveness=16):
        """Evaluate a compound against EGFR"""
        if not os.path.exists(ligand_file):
            return {'success': False, 'error': f'Ligand file {ligand_file} not found'}
        
        return self.evaluate_compound(
            ligand_file=ligand_file,
            receptor_file=self.pocket_file,
            binding_site=self.binding_site,
            exhaustiveness=exhaustiveness
        )
    
    def screen_compounds(self, ligand_list):
        """Screen multiple compounds against EGFR"""
        results = []
        for ligand in ligand_list:
            if os.path.exists(ligand):
                print(f"\nScreening {ligand}...")
                result = self.evaluate_egfr_compound(ligand)
                if result['success']:
                    results.append({
                        'ligand': ligand,
                        'affinity': result['best_affinity'],
                        'strength': result['binding_strength']
                    })
                    print(f"  -> Affinity: {result['best_affinity']:.2f} kcal/mol")
                else:
                    print(f"  -> Failed: {result.get('error', 'Unknown')}")
        
        results.sort(key=lambda x: x['affinity'])
        return results

if __name__ == "__main__":
    print("="*70)
    print("EGFR Docking Agent for AI Quantum Lab")
    print("="*70)
    
    agent = EGFRDockingAgent()
    
    if os.path.exists("egfr_pocket.pdbqt"):
        print(f"\nReceptor: egfr_pocket.pdbqt")
        print(f"Binding site: center={agent.binding_site['center']}, size={agent.binding_site['size']}")
        
        # Test with working ligand
        result = agent.evaluate_egfr_compound("final_ligand.pdbqt")
        
        if result['success']:
            print(f"\nSUCCESS!")
            print(f"  Ligand: final_ligand.pdbqt")
            print(f"  Binding affinity: {result['best_affinity']:.3f} kcal/mol")
            print(f"  Binding strength: {result['binding_strength']}")
    else:
        print("\nEGFR pocket file not found.")
