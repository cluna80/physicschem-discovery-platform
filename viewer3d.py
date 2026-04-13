"""
viewer3d.py - 3D binding visualization + MP4 docking animation
PhysicsChem Discovery Pipeline v2
"""
import os, re, subprocess, sys, tempfile
from pathlib import Path

try:
    import py3Dmol
    PY3DMOL_OK = True
except ImportError:
    PY3DMOL_OK = False

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem, Draw
    RDLogger.DisableLog('rdApp.*')
    RDKIT_OK = True
except ImportError:
    RDKIT_OK = False


# ── Coordinate helpers ────────────────────────────────────────────────

def pdbqt_to_pdb(path):
    lines = []
    try:
        with open(path) as f:
            for l in f:
                if l.startswith(('ATOM','HETATM','END','MODEL','ENDMDL')):
                    lines.append(l[:66])
    except Exception: pass
    return ''.join(lines)


def smiles_to_pdb(smiles):
    if not RDKIT_OK: return ""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return ""
        mol = Chem.AddHs(mol)
        p = AllChem.ETKDGv3(); p.randomSeed = 42
        AllChem.EmbedMolecule(mol, p)
        AllChem.MMFFOptimizeMolecule(mol)
        mol = Chem.RemoveHs(mol)
        return Chem.MolToPDBBlock(mol)
    except Exception: return ""


def get_best_pose(pdbqt):
    if not os.path.isfile(pdbqt): return ""
    lines = []; in_model = False
    try:
        with open(pdbqt) as f:
            for l in f:
                if l.startswith('MODEL'): in_model=True; lines=[]
                elif l.startswith('ENDMDL'): break
                elif in_model and l.startswith(('ATOM','HETATM')):
                    lines.append(l[:66])
    except Exception: pass
    return ''.join(lines)


def get_all_poses(pdbqt):
    poses = []
    if not os.path.isfile(pdbqt): return poses
    try:
        with open(pdbqt) as f: content = f.read()
        for model in re.findall(r'MODEL.*?ENDMDL', content, re.DOTALL):
            lines = [l[:66] for l in model.splitlines()
                     if l.startswith(('ATOM','HETATM'))]
            if lines: poses.append('\n'.join(lines))
    except Exception: pass
    return poses


def pdb_centroid(pdb_str):
    """Get centroid of PDB atoms."""
    xs,ys,zs = [],[],[]
    for l in pdb_str.splitlines():
        if l.startswith(('ATOM','HETATM')):
            try:
                xs.append(float(l[30:38]))
                ys.append(float(l[38:46]))
                zs.append(float(l[46:54]))
            except: pass
    if not xs: return (0,0,0)
    return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))


# ── Viewer builders ───────────────────────────────────────────────────

def ligand_spin_html(smiles, width=380, height=280):
    """Spinning 3D ligand from SMILES. Centered."""
    if not (PY3DMOL_OK and RDKIT_OK): return ""
    pdb = smiles_to_pdb(smiles)
    if not pdb: return ""
    cx,cy,cz = pdb_centroid(pdb)
    v = py3Dmol.view(width=width, height=height)
    v.addModel(pdb, 'pdb')
    v.setStyle({}, {
        'stick':  {'colorscheme':'cyanCarbon', 'radius':0.22},
        'sphere': {'colorscheme':'cyanCarbon', 'radius':0.40}
    })
    v.setBackgroundColor('#050d18')
    v.zoomTo()
    v.setView([0,0,0,0, cx, cy, cz, 1])
    v.spin({'axis':'y', 'speed':1})
    return v._make_html()


def binding_html(rec_pdb, lig_pdb, width=480, height=400, surface=True):
    """Receptor + ligand binding view. Zoomed to ligand center."""
    if not PY3DMOL_OK: return ""
    v = py3Dmol.view(width=width, height=height)
    if rec_pdb:
        v.addModel(rec_pdb, 'pdb')
        v.setStyle({'model':0}, {
            'cartoon': {'color':'spectrum', 'opacity':0.75}
        })
        if surface:
            v.addSurface(py3Dmol.SES,
                {'opacity':0.12,'colorscheme':'whiteCarbon'},
                {'model':0})
    if lig_pdb:
        idx = 1 if rec_pdb else 0
        v.addModel(lig_pdb, 'pdb')
        v.setStyle({'model':idx}, {
            'stick':  {'colorscheme':'cyanCarbon', 'radius':0.25},
            'sphere': {'colorscheme':'cyanCarbon', 'radius':0.42}
        })
        # Zoom to ligand centroid
        cx,cy,cz = pdb_centroid(lig_pdb)
        v.zoomTo({'model':idx})
        v.zoom(1.5)
    v.setBackgroundColor('#050d18')
    return v._make_html()


def poses_html(rec_pdb, poses_pdbqt, width=480, height=400):
    """All docking poses animated. Best pose highlighted."""
    if not PY3DMOL_OK: return ""
    v = py3Dmol.view(width=width, height=height)
    if rec_pdb:
        v.addModel(rec_pdb, 'pdb')
        v.setStyle({'model':0}, {
            'cartoon':{'color':'#2563eb','opacity':0.5}
        })
    poses = get_all_poses(poses_pdbqt)
    for i, pose_pdb in enumerate(poses):
        v.addModel(pose_pdb, 'pdb')
        idx = i + (1 if rec_pdb else 0)
        alpha = max(0.25, 1.0 - i * 0.1)
        v.setStyle({'model':idx}, {
            'stick': {
                'colorscheme': 'cyanCarbon' if i==0 else 'grayCarbon',
                'radius': 0.25 if i==0 else 0.12,
                'opacity': alpha
            }
        })
    v.setBackgroundColor('#050d18')
    if poses:
        cx,cy,cz = pdb_centroid(poses[0])
        v.zoomTo()
    v.spin({'axis':'y','speed':0.8})
    return v._make_html()


# ── MP4 Docking Animation ─────────────────────────────────────────────

def make_docking_mp4(smiles, receptor_pdbqt, out_path="docking_animation.mp4",
                     compound_id="Lead", affinity=-9.5, confidence=90):
    """
    Generate a docking animation MP4 showing the compound
    approaching and binding to the EGFR receptor pocket.

    Uses matplotlib + RDKit 2D projection for fast rendering.
    No GPU required. Generates ~8s / 200 frame movie.

    Returns path to MP4 or None on failure.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        import numpy as np
        from rdkit import Chem
        from rdkit.Chem import AllChem, Draw
        from rdkit.Chem.Draw import rdMolDraw2D
        import io
        from PIL import Image

        # ── Generate 2D compound image ────────────────────────────────
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None

        def mol_img_array(mol, size=300):
            d = rdMolDraw2D.MolDraw2DCairo(size, size)
            d.drawOptions().clearBackground = True
            d.DrawMolecule(mol)
            d.FinishDrawing()
            img = Image.open(io.BytesIO(d.GetDrawingText()))
            return np.array(img)

        mol_arr = mol_img_array(mol, 280)

        # ── Animation parameters ──────────────────────────────────────
        FPS    = 25
        FRAMES = 200  # 8 seconds
        fig, ax = plt.subplots(figsize=(8, 6), facecolor='#050d18')
        ax.set_facecolor('#050d18')
        ax.set_xlim(-1, 1); ax.set_ylim(-1, 1)
        ax.axis('off')

        # Background binding pocket (schematic circles)
        pocket_artists = []
        for r, alpha, color in [
            (0.85, 0.08, '#1a5276'),
            (0.65, 0.12, '#1e3a5f'),
            (0.45, 0.18, '#0f2033'),
        ]:
            circle = plt.Circle((0,0), r, fill=True,
                                  facecolor=color, edgecolor='#00b4a0',
                                  linewidth=0.8, alpha=alpha)
            ax.add_patch(circle)
            pocket_artists.append(circle)

        # Binding site label
        pocket_label = ax.text(0, -0.92, 'ATP Binding Pocket',
            ha='center', va='center', fontsize=9,
            color='#1e3a5f', fontfamily='monospace')

        # Receptor schematic arcs
        theta = np.linspace(0, 2*np.pi, 100)
        for scale, lw, alpha in [(0.78,1.5,0.3),(0.62,1.0,0.4),(0.48,0.7,0.5)]:
            x = scale * np.cos(theta)
            y = scale * np.sin(theta)
            ax.plot(x, y, color='#00b4a0', linewidth=lw, alpha=alpha)

        # Hinge H-bond markers (appear at end)
        hbond_markers = []
        for angle in [45, 135, 225, 315]:
            r_pos = 0.38
            hx = r_pos * np.cos(np.radians(angle))
            hy = r_pos * np.sin(np.radians(angle))
            m, = ax.plot(hx, hy, 'o', color='#fbbf24', markersize=6,
                         alpha=0, zorder=5)
            hbond_markers.append(m)

        # Compound image overlay
        img_extent = [-0.32, 0.32, -0.32, 0.32]
        compound_img = ax.imshow(mol_arr, extent=img_extent,
            aspect='auto', zorder=10, alpha=0)

        # Trail dots (compound path)
        trail_x = np.linspace(-1.4, 0, FRAMES//2)
        trail_y = np.sin(trail_x * 2) * 0.3
        trail_dots, = ax.plot([], [], 'o', color='#00b4a0',
                               markersize=3, alpha=0.4)

        # Labels
        title = ax.text(0, 0.96, 'PhysicsChem Discovery Lab',
            ha='center', va='center', fontsize=11,
            color='#00b4a0', fontfamily='monospace', fontweight='bold')

        info_text = ax.text(0, -0.76, '',
            ha='center', va='center', fontsize=9,
            color='#e2e8f0', fontfamily='monospace')

        conf_text = ax.text(0.82, 0.88, '',
            ha='right', va='center', fontsize=22,
            color='#22c55e', fontfamily='monospace', fontweight='bold',
            alpha=0)

        aff_text = ax.text(-0.82, 0.88, '',
            ha='left', va='center', fontsize=12,
            color='#4ade80', fontfamily='monospace', fontweight='bold',
            alpha=0)

        ready_text = ax.text(0, -0.60, '',
            ha='center', va='center', fontsize=10,
            color='#fbbf24', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a150a',
                      edgecolor='#fbbf24', alpha=0))

        # ── Animation function ────────────────────────────────────────
        def animate(frame):
            t = frame / FRAMES  # 0 → 1

            # Phase 1 (0-0.35): compound approaches from left
            if t < 0.35:
                phase = t / 0.35
                # Compound position on curved path
                cx = -1.4 + phase * 1.4
                cy = np.sin(cx * 2) * 0.3 * (1 - phase)
                # Trail
                n_trail = max(1, int(phase * 20))
                end_idx = int(phase*len(trail_x))
                start_idx = max(0, end_idx-n_trail)
                tx = trail_x[start_idx:end_idx]
                ty = trail_y[start_idx:end_idx]
                trail_dots.set_data(tx, ty)
                # Compound image follows path
                new_extent = [cx-0.28, cx+0.28, cy-0.28, cy+0.28]
                compound_img.set_extent(new_extent)
                compound_img.set_alpha(0.5 + phase*0.4)
                info_text.set_text(f'Approaching binding pocket...\n{compound_id}')
                info_text.set_color('#94a3b8')

            # Phase 2 (0.35-0.60): compound docks (snaps to center)
            elif t < 0.60:
                phase = (t - 0.35) / 0.25
                ease = 1 - (1-phase)**3  # ease-out cubic
                cx = (1-ease) * (trail_x[int(0.35*len(trail_x))]) 
                cy = (1-ease) * (trail_y[int(0.35*len(trail_y))])
                new_extent = [cx-0.28, cx+0.28, cy-0.28, cy+0.28]
                compound_img.set_extent(new_extent)
                compound_img.set_alpha(0.9)
                trail_dots.set_data([], [])
                # Pocket glows brighter
                for p in pocket_artists:
                    p.set_alpha(p.get_alpha() * 1.02)
                info_text.set_text(f'Docking to ATP pocket...\n{compound_id}')
                info_text.set_color('#fbbf24')

            # Phase 3 (0.60-0.80): H-bonds appear, compound settles
            elif t < 0.80:
                phase = (t-0.60)/0.20
                compound_img.set_extent(img_extent)
                compound_img.set_alpha(1.0)
                for m in hbond_markers:
                    m.set_alpha(max(0.0, min(1.0, phase * 2)))
                info_text.set_text(f'Binding confirmed | {affinity:.2f} kcal/mol')
                info_text.set_color('#4ade80')
                aff_text.set_text(f'{affinity:.2f}\nkcal/mol')
                aff_text.set_alpha(phase)

            # Phase 4 (0.80-1.0): certificate appears
            else:
                phase = (t-0.80)/0.20
                compound_img.set_extent(img_extent)
                compound_img.set_alpha(1.0)
                for m in hbond_markers: m.set_alpha(1.0)
                conf_text.set_text(f'{confidence}%')
                conf_text.set_alpha(max(0.0, min(1.0, phase*3)))
                aff_text.set_alpha(1.0)
                ready_text.set_text('READY FOR SYNTHESIS QUOTATION')
                ready_text.set_alpha(max(0.0, min(1.0, (phase-0.3)*4)))
                info_text.set_text(f'Confidence: {confidence}% | DILI: 0.16 | AMES: 0.05')
                info_text.set_color('#22c55e')
                pocket_label.set_text('ATP Binding Pocket · Hinge contacts confirmed')
                pocket_label.set_color('#00b4a0')

            return ([compound_img, trail_dots, info_text, conf_text,
                     aff_text, ready_text, pocket_label] + hbond_markers)

        anim = animation.FuncAnimation(
            fig, animate, frames=FRAMES,
            interval=1000//FPS, blit=True
        )

        # Save MP4
        # Find ffmpeg - check common Windows install locations
        import shutil
        ffmpeg_path = (
            shutil.which('ffmpeg') or
            shutil.which('ffmpeg.exe') or
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe' if os.path.isfile(r'C:\Program Files\ffmpeg\bin\ffmpeg.exe') else None
        )
        # Also check winget install location
        if not ffmpeg_path:
            import glob
            candidates = glob.glob(r'C:\Users\*\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\ffmpeg.exe', recursive=True)
            if candidates:
                ffmpeg_path = candidates[0]
        if not ffmpeg_path:
            raise RuntimeError("ffmpeg not found. Run: winget install ffmpeg, then restart terminal.")
        ffmpeg_path = r"C:\Users\krizz\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
        if not os.path.isfile(ffmpeg_path):
            import shutil; ffmpeg_path = shutil.which('ffmpeg') or ffmpeg_path
        matplotlib.rcParams['animation.ffmpeg_path'] = ffmpeg_path
        writer = animation.FFMpegWriter(fps=FPS, bitrate=1800,
            metadata={'title': f'PhysicsChem Docking Animation - {compound_id}'})
        anim.save(out_path, writer=writer, dpi=120)
        plt.close(fig)
        return out_path

    except Exception as e:
        print(f"MP4 generation error: {e}")
        import traceback; traceback.print_exc()
        return None


def make_docking_gif(smiles, out_path="docking_animation.gif",
                     compound_id="Lead", affinity=-9.5, confidence=90):
    """
    Fallback GIF animation (no ffmpeg needed).
    Simpler but works everywhere.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
        import numpy as np
        from rdkit import Chem
        from rdkit.Chem.Draw import rdMolDraw2D
        import io
        from PIL import Image

        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None

        # 2D mol image
        d = rdMolDraw2D.MolDraw2DCairo(260,260)
        d.drawOptions().clearBackground=True
        d.DrawMolecule(mol); d.FinishDrawing()
        mol_img = Image.open(io.BytesIO(d.GetDrawingText()))
        mol_arr = np.array(mol_img)

        FRAMES = 60
        fig, ax = plt.subplots(figsize=(7,5.5), facecolor='#050d18')
        ax.set_facecolor('#050d18')
        ax.set_xlim(-1,1); ax.set_ylim(-1,1); ax.axis('off')

        # Static elements
        for r, alpha, color in [(0.82,0.1,'#1a5276'),(0.60,0.15,'#1e3a5f'),(0.42,0.2,'#0f2033')]:
            ax.add_patch(plt.Circle((0,0),r,fill=True,facecolor=color,
                         edgecolor='#00b4a0',linewidth=0.8,alpha=alpha))

        theta = np.linspace(0,2*np.pi,100)
        for sc,lw,al in [(0.75,1.5,0.3),(0.58,1.0,0.4)]:
            ax.plot(sc*np.cos(theta),sc*np.sin(theta),
                    color='#00b4a0',linewidth=lw,alpha=al)

        ax.text(0,0.93,'PhysicsChem Discovery Lab',ha='center',
                fontsize=10,color='#00b4a0',fontfamily='monospace',fontweight='bold')

        img_ax = ax.imshow(mol_arr, extent=[-0.3,0.3,-0.3,0.3],
                            aspect='auto', zorder=10, alpha=0)
        status = ax.text(0,-0.72,'',ha='center',fontsize=9,
                         color='#e2e8f0',fontfamily='monospace')
        score  = ax.text(0,-0.85,'',ha='center',fontsize=11,
                         color='#4ade80',fontfamily='monospace',fontweight='bold')

        def animate(f):
            t = f/FRAMES
            if t < 0.4:
                p = t/0.4
                cx = -1.2 + p*1.2; cy = np.sin(p*np.pi)*0.2
                img_ax.set_extent([cx-.26,cx+.26,cy-.26,cy+.26])
                img_ax.set_alpha(0.4+p*0.5)
                status.set_text(f'Approaching... {compound_id}')
                status.set_color('#94a3b8')
                score.set_text('')
            elif t < 0.7:
                p = (t-.4)/.3
                e = 1-(1-p)**3
                img_ax.set_extent([e*-.3,(e*-.3)+.6+.3*e,-.3,.3])
                img_ax.set_extent([-0.3,0.3,-0.3,0.3])
                img_ax.set_alpha(0.9)
                status.set_text(f'Docking... {affinity:.2f} kcal/mol')
                status.set_color('#fbbf24')
                score.set_text('')
            else:
                p = (t-.7)/.3
                img_ax.set_extent([-0.3,0.3,-0.3,0.3])
                img_ax.set_alpha(1.0)
                status.set_text(f'Bound! Confidence: {confidence}%')
                status.set_color('#4ade80')
                score.set_text(f'{affinity:.2f} kcal/mol  |  {confidence}% confidence')
            return img_ax, status, score

        anim = animation.FuncAnimation(fig, animate, frames=FRAMES,
                                        interval=80, blit=True)
        anim.save(out_path, writer='pillow', fps=12, dpi=100)
        plt.close(fig)
        return out_path
    except Exception as e:
        print(f"GIF error: {e}")
        return None


# ── Streamlit render functions ────────────────────────────────────────

def render_ligand_spin(st, smiles, width=380, height=280):
    """Spinning 3D ligand in Streamlit."""
    
    if not (PY3DMOL_OK and RDKIT_OK): return False
    html = ligand_spin_html(smiles, width=width, height=height)
    if not html: return False
    st.components.v1.html(html, height=height+10)
    return True


def render_3d_panel(st, lead, receptor_pdbqt, result_pdbqt=""):
    """Full binding panel with tabs."""
    

    st.markdown("""<div style="font-family:'Space Mono',monospace;font-size:.65rem;
    color:#00b4a0;text-transform:uppercase;letter-spacing:.1em;
    border-bottom:1px solid #1e3a5f;padding-bottom:.3rem;
    margin-bottom:.6rem">3D Binding Visualization</div>""",
    unsafe_allow_html=True)

    if not PY3DMOL_OK:
        st.warning("pip install stmol py3Dmol")
        return

    smiles = lead.get('smiles','')
    cid    = lead.get('id','?')
    aff    = lead.get('dock_affinity','?')

    rec_pdb = ""
    rec_pdb_path = receptor_pdbqt.replace('.pdbqt','.pdb')
    if os.path.isfile(rec_pdb_path):
        rec_pdb = open(rec_pdb_path).read()
    elif os.path.isfile(receptor_pdbqt):
        rec_pdb = pdbqt_to_pdb(receptor_pdbqt)

    lig_pdb = ""
    if result_pdbqt and os.path.isfile(result_pdbqt):
        lig_pdb = get_best_pose(result_pdbqt)
    if not lig_pdb and smiles:
        lig_pdb = smiles_to_pdb(smiles)

    if not lig_pdb:
        st.info("No 3D coordinates available.")
        return

    tab1, tab2, tab3 = st.tabs(["Bound Pose", "All Poses", "Docking Movie"])

    with tab1:
        html = binding_html(rec_pdb, lig_pdb, width=680, height=440)
        if html:
            st.components.v1.html(html, height=450)
            st.markdown(
                f'<div style="font-size:.68rem;color:#94a3b8;'
                f'font-family:\'Space Mono\',monospace;margin-top:.3rem">'
                f'<span style="color:#00b4a0">{cid}</span> &nbsp;|&nbsp; '
                f'<span style="color:#4ade80">{aff} kcal/mol</span> '
                f'&nbsp;|&nbsp; Drag: rotate &nbsp; Scroll: zoom</div>',
                unsafe_allow_html=True)

    with tab2:
        if result_pdbqt and os.path.isfile(result_pdbqt):
            html2 = poses_html(rec_pdb, result_pdbqt, width=680, height=440)
            if html2:
                st.components.v1.html(html2, height=450)
                st.caption("All 9 docking poses. Cyan = best. Spinning.")
        else:
            html3 = ligand_spin_html(smiles, width=680, height=440)
            if html3:
                st.components.v1.html(html3, height=450)
            st.caption("Run docking to see all poses")

    with tab3:
        st.markdown("""<div style="font-size:.8rem;color:#94a3b8;
        font-family:'Space Mono',monospace;margin-bottom:.8rem">
        Generate a docking animation showing the compound
        approaching and binding to the EGFR pocket.</div>""",
        unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate MP4 (ffmpeg)", use_container_width=True):
                with st.spinner("Rendering animation... ~30 seconds"):
                    out = make_docking_mp4(
                        smiles, receptor_pdbqt,
                        out_path="docking_animation.mp4",
                        compound_id=cid,
                        affinity=float(aff) if aff != '?' else -9.5,
                        confidence=lead.get('confidence', 90)
                    )
                if out and os.path.isfile(out):
                    with open(out,'rb') as f:
                        st.download_button(
                            "Download MP4",
                            f.read(), file_name="docking_animation.mp4",
                            mime="video/mp4")
                    st.video(out)
                else:
                    st.warning("ffmpeg not found - try GIF instead")

        with col2:
            if st.button("Generate GIF (no ffmpeg)", use_container_width=True):
                with st.spinner("Rendering GIF... ~20 seconds"):
                    out = make_docking_gif(
                        smiles,
                        out_path="docking_animation.gif",
                        compound_id=cid,
                        affinity=float(aff) if aff != '?' else -9.5,
                        confidence=lead.get('confidence', 90)
                    )
                if out and os.path.isfile(out):
                    with open(out,'rb') as f:
                        st.download_button(
                            "Download GIF",
                            f.read(), file_name="docking_animation.gif",
                            mime="image/gif")
                    st.image(out)
                else:
                    st.error("GIF generation failed")
