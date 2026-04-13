import numpy as np
import matplotlib.pyplot as plt
import os

def plot_xvg(filename, title, ylabel, output=None):
    """Plot XVG file from GROMACS"""
    if not os.path.exists(filename):
        print(f"File {filename} not found")
        return
    
    data = np.loadtxt(filename, comments=['@', '#'])
    plt.figure(figsize=(10, 6))
    plt.plot(data[:, 0], data[:, 1], 'b-', linewidth=1.5)
    plt.xlabel('Time (ns)')
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    if output:
        plt.savefig(output, dpi=150)
        print(f"Saved {output}")
    plt.close()

# Plot results
print("Generating plots...")
plot_xvg('rmsd.xvg', 'Protein RMSD', 'RMSD (nm)', 'rmsd_plot.png')
plot_xvg('rmsf.xvg', 'Residue Fluctuations', 'RMSF (nm)', 'rmsf_plot.png')
plot_xvg('gyrate.xvg', 'Radius of Gyration', 'Rg (nm)', 'gyrate_plot.png')

# Generate summary report
if os.path.exists('rmsd.xvg'):
    rmsd = np.loadtxt('rmsd.xvg', comments=['@', '#'])
    rmsd_avg = np.mean(rmsd[:, 1])
    rmsd_std = np.std(rmsd[:, 1])
    rmsd_final = rmsd[-1, 1]
    
    report = f"""
    ========================================
    MD Simulation Summary
    ========================================
    
    System: HIV Protease with Ligand
    
    RMSD Analysis:
      - Average RMSD: {rmsd_avg:.3f} ± {rmsd_std:.3f} nm
      - Final RMSD: {rmsd_final:.3f} nm
    
    Stability Assessment:
      - System is {'stable' if rmsd_avg < 0.3 else 'partially stable' if rmsd_avg < 0.5 else 'unstable'}
    
    ========================================
    """
    
    with open('md_summary.txt', 'w') as f:
        f.write(report)
    
    print(report)

print("Analysis complete!")
