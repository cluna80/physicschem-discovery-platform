import os, csv, subprocess, shutil, time
from pathlib import Path

class DockingAgent:
    def __init__(self, vina_path="./bin/vina.exe"):
        self.vina_path = vina_path
        if not os.path.exists(vina_path) and shutil.which("vina"):
            self.vina_path = "vina"
        print(f"[INFO] Vina: {self.vina_path}")

    def dock(self, receptor, ligand, center, size, out_file, exhaustiveness=8):
        cmd = [self.vina_path,"--receptor",receptor,"--ligand",ligand,
               "--center_x",str(center[0]),"--center_y",str(center[1]),
               "--center_z",str(center[2]),"--size_x",str(size),
               "--size_y",str(size),"--size_z",str(size),
               "--out",out_file,"--exhaustiveness",str(exhaustiveness)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in r.stdout.splitlines():
                if line.strip().startswith("1 "):
                    parts = line.split()
                    if len(parts) >= 2:
                        return float(parts[1])
        except Exception as e:
            print(f"    [!] Dock error: {e}")
        return None

    def prepare_ligand(self, smiles, name, out_dir):
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        pdbqt = Path(out_dir) / f"{name}.pdbqt"
        if pdbqt.exists(): return str(pdbqt)
        try:
            from meeko import MoleculePreparation, PDBQTWriterLegacy
            from rdkit import Chem
            from rdkit.Chem import AllChem
            mol = Chem.MolFromSmiles(smiles)
            if mol is None: return None
            mol = Chem.AddHs(mol)
            if AllChem.EmbedMolecule(mol, AllChem.ETKDGv3()) != 0: return None
            AllChem.MMFFOptimizeMolecule(mol)
            prep = MoleculePreparation()
            setups = prep.prepare(mol)
            pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
            pdbqt.write_text(pdbqt_str)
            return str(pdbqt)
        except Exception as e:
            print(f"    [!] Prep failed: {e}")
            return None

class HIVDockingAgent(DockingAgent):
    def __init__(self, receptor_file="hiv_protease.pdbqt",
                 vina_path="./bin/vina.exe",
                 library_smi="hiv_drug_library.smi",
                 library_csv="hiv_drug_library.csv"):
        super().__init__(vina_path)
        self.receptor_file = receptor_file
        self.library_smi = library_smi
        self.library_csv = library_csv
        self.binding_site = {"center": (-11.4, 19.8, 28.0), "size": 20}
        if os.path.exists("hiv_binding_site.txt"):
            try:
                coords = open("hiv_binding_site.txt").read().strip().split(",")
                self.binding_site["center"] = (float(coords[0]),float(coords[1]),float(coords[2]))
                print(f"Using extracted binding site: {self.binding_site['center']}")
            except: pass
        print(f"HIV Protease Docking Agent Ready!")
        print(f"Binding site: {self.binding_site['center']}")
        print(f"Receptor: {self.receptor_file}")

    def load_library(self):
        drugs = []
        meta = {}
        if os.path.exists(self.library_csv):
            with open(self.library_csv, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    meta[row["name"]] = row
        with open(self.library_smi, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split("\t")
                if len(parts) < 2: continue
                name = parts[1]
                drugs.append({"smiles": parts[0], "name": name,
                    "class": parts[2] if len(parts)>2 else "Unknown",
                    "mol_weight": meta.get(name,{}).get("mol_weight","N/A"),
                    "lipinski_ro5": meta.get(name,{}).get("lipinski_ro5","N/A")})
        print(f"[INFO] Loaded {len(drugs)} compounds")
        return drugs

    def screen_library(self, exhaustiveness=8, output_csv="hiv_screening_results.csv"):
        drugs = self.load_library()
        if not drugs: return []
        if not os.path.exists(self.receptor_file):
            print(f"[ERROR] Receptor not found: {self.receptor_file}"); return []
        Path("ligand_pdbqt").mkdir(exist_ok=True)
        Path("docking_results").mkdir(exist_ok=True)
        results = []
        print(f"\n{'='*55}")
        print(f"  SCREENING {len(drugs)} DRUGS vs HIV-1 PROTEASE")
        print(f"{'='*55}\n")
        for i, drug in enumerate(drugs, 1):
            name = drug["name"]
            safe = name.replace(" ","_")
            print(f"[{i:02d}/{len(drugs)}] {name} ({drug['class']})")
            pdbqt = self.prepare_ligand(drug["smiles"], safe, "ligand_pdbqt")
            if not pdbqt:
                print(f"         [-] Prep failed"); results.append({**drug,"affinity":"FAILED","status":"failed"}); continue
            out_pose = f"docking_results/{safe}_out.pdbqt"
            aff = self.dock(self.receptor_file, pdbqt,
                            self.binding_site["center"], self.binding_site["size"],
                            out_pose, exhaustiveness)
            if aff is not None:
                print(f"         Affinity: {aff:.2f} kcal/mol")
                results.append({**drug,"affinity":aff,"pose_file":out_pose,"status":"success"})
            else:
                print(f"         [-] Docking failed")
                results.append({**drug,"affinity":"FAILED","status":"failed"})
        success = sorted([r for r in results if r["status"]=="success"], key=lambda x: x["affinity"])
        failed  = [r for r in results if r["status"]!="success"]
        ranked  = success + failed
        with open(output_csv,"w",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name","class","affinity","mol_weight","lipinski_ro5","smiles","status"], extrasaction="ignore")
            w.writeheader(); w.writerows(ranked)
        print(f"\n{'='*55}")
        print(f"  COMPLETE — {len(success)} docked, {len(failed)} failed")
        print(f"  Results: {output_csv}")
        print(f"\n  TOP 10 HITS:")
        print(f"  {'Rank':<5} {'Name':<28} {'Affinity':>12}")
        print(f"  {'-'*48}")
        for i,r in enumerate(success[:10],1):
            print(f"  {i:<5} {r['name']:<28} {r['affinity']:>8.2f} kcal/mol")
        print("="*55)
        return ranked

if __name__ == "__main__":
    agent = HIVDockingAgent()
    agent.screen_library(exhaustiveness=8)
