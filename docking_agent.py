# -*- coding: utf-8 -*-
"""
Docking Agent for Autonomous AI Quantum Lab
Use this module to evaluate molecular binding
"""

import os
import subprocess
from docking_module import VinaDocker

class DockingAgent:
    """AI Agent for molecular docking"""
    
    def __init__(self, vina_path="./bin/vina.exe"):
        self.docker = VinaDocker(vina_path)
        self.results_history = []
    
    def evaluate_compound(self, ligand_file, receptor_file, binding_site, 
                          exhaustiveness=16, num_modes=9):
        """
        Evaluate a compound's binding affinity
        
        Parameters:
        - ligand_file: path to ligand PDBQT file
        - receptor_file: path to receptor PDBQT file  
        - binding_site: dict with 'center' (x,y,z) and 'size' (int or tuple)
        - exhaustiveness: thoroughness of search (8-32)
        - num_modes: number of binding modes to generate
        
        Returns:
        - dict with binding results
        """
        
        print(f"\nEvaluating: {ligand_file}")
        print(f"   Receptor: {receptor_file}")
        print(f"   Binding site: center={binding_site['center']}, size={binding_site['size']}")
        
        try:
            affinities = self.docker.dock(
                receptor=receptor_file,
                ligand=ligand_file,
                center=binding_site['center'],
                size=binding_site['size'],
                exhaustiveness=exhaustiveness,
                num_modes=num_modes
            )
            
            if affinities:
                best = affinities[0]
                result = {
                    'success': True,
                    'ligand': ligand_file,
                    'receptor': receptor_file,
                    'best_affinity': best['affinity'],
                    'best_mode': best['mode'],
                    'all_modes': affinities,
                    'binding_strength': self._classify_binding(best['affinity'])
                }
                self.results_history.append(result)
                return result
            else:
                return {'success': False, 'error': 'No binding modes found'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _classify_binding(self, affinity):
        """Classify binding strength based on affinity"""
        if affinity < -9:
            return "Very Strong (High Affinity)"
        elif affinity < -7:
            return "Strong (Good Candidate)"
        elif affinity < -5:
            return "Moderate"
        elif affinity < -3:
            return "Weak"
        else:
            return "Very Weak (Needs Optimization)"
    
    def batch_evaluate(self, ligand_list, receptor_file, binding_site):
        """Evaluate multiple compounds"""
        results = []
        for ligand in ligand_list:
            result = self.evaluate_compound(ligand, receptor_file, binding_site)
            results.append(result)
            if result['success']:
                print(f"   -> Affinity: {result['best_affinity']:.3f} kcal/mol ({result['binding_strength']})")
            else:
                print(f"   -> Failed: {result.get('error', 'Unknown error')}")
        return results
    
    def get_best_candidates(self, threshold=-7):
        """Get compounds with binding better than threshold"""
        return [r for r in self.results_history 
                if r['success'] and r['best_affinity'] < threshold]

def convert_pdb_to_pdbqt(pdb_file, output_file, is_receptor=True):
    """Convert PDB to PDBQT using OpenBabel"""
    cmd = ["obabel", pdb_file, "-O", output_file]
    if is_receptor:
        cmd.extend(["-xr", "-p"])
    else:
        cmd.append("-xh")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

# Example usage
if __name__ == "__main__":
    print("="*60)
    print("AI Docking Agent - Test Run")
    print("="*60)
    
    # Create agent
    agent = DockingAgent()
    
    # Define binding site
    binding_site = {
        'center': (15.0, 53.0, 17.0),
        'size': 20
    }
    
    # Test with our example files
    result = agent.evaluate_compound(
        ligand_file="final_ligand.pdbqt",
        receptor_file="final_receptor.pdbqt",
        binding_site=binding_site
    )
    
    if result['success']:
        print(f"\nEvaluation Complete")
        print(f"   Best Affinity: {result['best_affinity']:.3f} kcal/mol")
        print(f"   Binding Strength: {result['binding_strength']}")
        print(f"   Best Mode: {result['best_mode']}")
        print(f"\nTop 5 Binding Modes:")
        for mode in result['all_modes'][:5]:
            print(f"     Mode {mode['mode']}: {mode['affinity']:.3f} kcal/mol (RMSD: {mode['rmsd_lb']:.2f} A)")
    else:
        print(f"\nEvaluation Failed: {result.get('error')}")
    
    print("\n" + "="*60)
    print("AI Docking Agent Ready!")
    print("="*60)
