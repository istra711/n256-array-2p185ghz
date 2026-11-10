"""Build the English and German ODT reports of the n256 (2.185 GHz) study.

Usage::

    python build_docs.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tools"))
sys.path.insert(0, str(HERE))

from odt_builder import Report          # noqa: E402
import array_model as am                # noqa: E402

DOCS = HERE / "docs"
FIG = DOCS / "figures"
RES = json.loads((DOCS / "results.json").read_text(encoding="utf-8"))


def export_pdf(odt: Path) -> Path | None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if exe is None:
        for cand in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                     r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
            if Path(cand).is_file():
                exe = cand
                break
    if exe is None:
        return None
    subprocess.run([exe, "--headless", "--convert-to", "pdf",
                    "--outdir", str(odt.parent), str(odt)],
                   check=False, capture_output=True)
    pdf = odt.with_suffix(".pdf")
    return pdf if pdf.is_file() else None


def build(lang: str) -> Path:
    de = lang == "de"

    def T(a: str, b: str) -> str:
        return b if de else a

    def N(v: float, d: int = 2) -> str:
        s = f"{v:.{d}f}"
        return s.replace(".", ",") if de else s

    el = RES["element"]
    cp = RES["coupling"]
    arr = RES["array"]
    des = RES["design"]

    r = Report(
        title="n256 4×4 Patch Array at 2.185 GHz",
        author="VisualopenEMS · openEMS workflow",
        subject=T("Full-wave design of a 3GPP n256 user-terminal array",
                  "Vollwellenentwurf eines 3GPP-n256-Nutzerterminal-Arrays"),
        header=T("n256 4×4 array study · 2.185 GHz · RO4003C",
                 "n256-4×4-Array-Studie · 2,185 GHz · RO4003C"),
        toc_title=T("Contents", "Inhalt"),
    )
    r.figure_word = T("Figure", "Bild")
    r.table_word = T("Table", "Tabelle")

    # ------------------------------------------------------------- cover
    r.p("n256 4×4 Patch Array at 2.185 GHz", style="Title")
    r.p(T("Full-wave follow-up of the sizing study: element tuning, embedded "
          "element and broadside array",
          "Vollwellen-Fortsetzung der Sizing-Studie: Elementabstimmung, "
          "eingebettetes Element und Broadside-Array"), style="Subtitle")
    r.p("", style="Rule")
    r.p(T("openEMS FDTD · RO4003C · 3GPP n256 receive band (2170–2200 MHz)",
          "openEMS-FDTD · RO4003C · 3GPP-n256-Empfangsband (2170–2200 MHz)"),
        style="CoverMeta")
    r.p(T(f"Patch {N(des['patch_l_mm'])} × {N(des['patch_w_mm'])} mm · "
          f"lattice {N(des['pitch_mm'])} mm · board {N(des['board_mm'], 0)} mm",
          f"Patch {N(des['patch_l_mm'])} × {N(des['patch_w_mm'])} mm · "
          f"Raster {N(des['pitch_mm'])} mm · Platine {N(des['board_mm'], 0)} mm"),
        style="CoverMeta")
    r.p(date.today().isoformat(), style="CoverMeta")
    r.p("© 2026 Michael T. — all rights reserved; reuse requires written permission",
        style="CoverMeta")

    r.start_main()
    r.toc()
    r.page_break()

    # ------------------------------------------------------------- 1
    r.h1("1", T("Executive summary", "Zusammenfassung"))
    r.p(T(
        "The sizing study showed that a 4×4 array at n256 (2170–2200 MHz) fits "
        "on a car roof with a 33 cm module.  This report takes the next step "
        "and simulates the structure in openEMS: first the element, then the "
        "embedded element and finally the fully driven broadside array, all "
        "on the same 340 mm board.",
        "Die Sizing-Studie zeigte, dass ein 4×4-Array bei n256 (2170–2200 MHz) "
        "mit einem 33-cm-Modul auf ein Pkw-Dach passt.  Dieser Bericht geht "
        "den nächsten Schritt und simuliert die Struktur in openEMS: erst das "
        "Element, dann das eingebettete Element und schließlich das voll "
        "gespeiste Broadside-Array, jeweils auf derselben 340-mm-Platine."))
    r.bullets([
        T(f"The Hammerstad length of {N(am.PATCH_L_HAMMERSTAD_MM)} mm is only "
          f"a starting point: once the inset is present the input resistance "
          f"follows R_in = R_edge·cos²(πs/L) while the resonant product f·L "
          f"stays constant.  Full-wave tuning gives L = {N(des['patch_l_mm'])} "
          f"mm with an inset of {N(des['inset_mm'])} mm.",
          f"Die Hammerstad-Länge von {N(am.PATCH_L_HAMMERSTAD_MM)} mm ist nur "
          f"ein Startwert: Mit Inset folgt der Eingangswiderstand "
          f"R_in = R_edge·cos²(πs/L), während das Produkt f·L konstant bleibt. "
          f"Die Vollwellenabstimmung ergibt L = {N(des['patch_l_mm'])} mm bei "
          f"einem Inset von {N(des['inset_mm'])} mm."),
        T(f"Final element: Zin = {N(el['zin_real'], 1)} "
          f"{N(el['zin_imag'], 1)}j Ω, |S11| = {N(el['s11_db'], 1)} dB, "
          f"VSWR {N(el['vswr'], 2)}, directivity {N(el['dmax'], 2)} dBi.",
          f"Finales Element: Zin = {N(el['zin_real'], 1)} "
          f"{N(el['zin_imag'], 1)}j Ω, |S11| = {N(el['s11_db'], 1)} dB, "
          f"VSWR {N(el['vswr'], 2)}, Richtfaktor {N(el['dmax'], 2)} dBi."),
        T(f"Embedded element (P6): {N(el['embedded_dmax'], 2)} dBi at "
          f"η = {N(el['embedded_eff'], 3)}; strongest coupling "
          f"{N(cp['coupling_max'], 1)} dB to the nearest neighbour, self "
          f"reflection {N(cp['s66_db'], 1)} dB.",
          f"Eingebettetes Element (P6): {N(el['embedded_dmax'], 2)} dBi bei "
          f"η = {N(el['embedded_eff'], 3)}; stärkste Kopplung "
          f"{N(cp['coupling_max'], 1)} dB zum nächsten Nachbarn, "
          f"Eigenreflexion {N(cp['s66_db'], 1)} dB."),
        T(f"Broadside array: {N(arr['dmax'], 2)} dBi directivity, "
          f"{N(arr['gain_corr'], 2)} dBi realised gain at "
          f"η = {N(arr['eff_corr'], 3)} – the 4×4 gain predicted by the "
          f"sizing study.",
          f"Broadside-Array: {N(arr['dmax'], 2)} dBi Richtfaktor, "
          f"{N(arr['gain_corr'], 2)} dBi realisierter Gewinn bei "
          f"η = {N(arr['eff_corr'], 3)} – der in der Sizing-Studie "
          f"vorhergesagte 4×4-Gewinn."),
    ])

    # ------------------------------------------------------------- 2
    r.h1("2", T("Model and method", "Modell und Methode"))
    r.p(T(
        "The project reuses the workflow of the 77 GHz radar study: one Python "
        "module defines geometry, mesh and project files; the runs use the "
        "VisualopenEMS headless runner; the evaluation reads S-parameters and "
        "NF2FF patterns from the run directory.",
        "Das Projekt nutzt den Workflow der 77-GHz-Radarstudie: ein "
        "Python-Modul definiert Geometrie, Mesh und Projektdateien; die Läufe "
        "verwenden den VisualopenEMS-Headless-Runner; die Auswertung liest "
        "S-Parameter und NF2FF-Diagramme aus dem Laufverzeichnis."))
    r.table(
        T("Simulation parameters.", "Simulationsparameter."),
        [T("Item", "Größe"), T("Value", "Wert")],
        [
            [T("Centre frequency", "Mittenfrequenz"),
             f"{N(des['f0_ghz'], 3)} GHz"],
            [T("Excitation band", "Anregungsband"),
             f"{N(des['band_ghz'][0], 2)}–{N(des['band_ghz'][1], 2)} GHz "
             f"(fc = {N(am.FC_HZ/1e6, 0)} MHz)"],
            [T("Substrate", "Substrat"),
             f"RO4003C, εr {N(des['eps_r'], 2)}, tan δ {N(des['tand'], 4)}, "
             f"h {N(des['h_mm'], 3)} mm"],
            [T("Patch L × W", "Patch L × W"),
             f"{N(des['patch_l_mm'])} × {N(des['patch_w_mm'])} mm"],
            [T("Lattice / board", "Raster / Platine"),
             f"{N(des['pitch_mm'])} / {N(des['board_mm'], 0)} mm"],
            [T("Mesh", "Mesh"),
             "max 8 mm, refined 2.5 mm, min 1.5 mm, min z 0.40 mm"],
            [T("NF2FF", "NF2FF"),
             f"5 frequencies, {am.NF2FF_THETA_STEPS} × "
             f"{am.NF2FF_PHI_STEPS} angles"],
        ],
        widths=[4.6, 8.0])

    # ------------------------------------------------------------- 3
    r.h1("3", T("Element design and tuning", "Elemententwurf und Abstimmung"))
    r.p(T(
        f"The Hammerstad length of {N(am.PATCH_L_HAMMERSTAD_MM)} mm "
        f"({N(am.patch_eps_eff())} effective permittivity) is the starting "
        f"point.  A first run with a 5 % inset showed almost no coupling "
        f"(Zin ≈ 1.6 Ω): with the probe so close to the radiating edge the "
        f"patch is far from its 50 Ω point and the port sees a strongly "
        f"reactive load.  The same run also revealed that the product "
        f"f_res·L stays constant at about 72 GHz·mm once the inset is "
        f"present, i.e. the inset changes the input resistance but not the "
        f"resonant length.",
        f"Die Hammerstad-Länge von {N(am.PATCH_L_HAMMERSTAD_MM)} mm "
        f"({N(am.patch_eps_eff())} effektive Permittivität) ist der "
        f"Ausgangspunkt.  Ein erster Lauf mit 5 % Inset zeigte praktisch keine "
        f"Ankopplung (Zin ≈ 1,6 Ω): So nahe an der strahlenden Kante ist das "
        f"Patch weit von seinem 50-Ω-Punkt entfernt und der Port sieht eine "
        f"stark reaktive Last.  Derselbe Lauf zeigte außerdem, dass das "
        f"Produkt f_res·L mit Inset konstant bei etwa 72 GHz·mm liegt – der "
        f"Inset ändert den Eingangswiderstand, nicht die Resonanzlänge."))
    r.p(T(
        "With the inset law R_in = R_edge·cos²(π·s/L) and the measured edge "
        "resistance of about 150 Ω, 50 Ω requires s ≈ 0.30 L.  Scaling the "
        "length to the target frequency then gives L = 33.0 mm with s = "
        "9.9 mm; a verification run confirms the design.",
        "Mit dem Inset-Gesetz R_in = R_edge·cos²(π·s/L) und dem gemessenen "
        "Kantenwiderstand von etwa 150 Ω folgt für 50 Ω ein s ≈ 0,30 L.  Die "
        "Skalierung der Länge auf die Zielfrequenz ergibt dann L = 33,0 mm "
        "bei s = 9,9 mm; ein Verifikationslauf bestätigt den Entwurf."))
    r.p(T(
        f"One mesh detail was changed after the first run: the excitation "
        f"band was widened to 2.00–2.40 GHz (f_c = {N(am.FC_HZ/1e6, 0)} MHz) "
        f"and the minimum z cell relaxed to 0.40 mm.  The shorter pulse cut "
        f"the run from 40 000 non-converged steps (60 min) to about 24 000 "
        f"steps that converge to −40 dB in 19 min.",
        f"Ein Mesh-Detail wurde nach dem ersten Lauf geändert: Das "
        f"Anregungsband wurde auf 2,00–2,40 GHz verbreitert (f_c = "
        f"{N(am.FC_HZ/1e6, 0)} MHz) und die minimale z-Zelle auf 0,40 mm "
        f"entspannt.  Der kürzere Puls reduzierte den Lauf von 40 000 nicht "
        f"konvergierten Schritten (60 min) auf rund 24 000 Schritte, die in "
        f"19 min bis −40 dB konvergieren."))
    r.p(T(
        f"The final element has Zin = {N(el['zin_real'], 1)} "
        f"{N(el['zin_imag'], 1)}j Ω and |S11| = {N(el['s11_db'], 1)} dB at "
        f"2.185 GHz; the best match is {N(el['best_s11_db'], 1)} dB at "
        f"{N(el['best_ghz'], 3)} GHz.  The −10 dB bandwidth spans "
        f"{N(el['bw10_low_ghz'], 3)}–{N(el['bw10_high_ghz'], 3)} GHz.",
        f"Das finale Element hat Zin = {N(el['zin_real'], 1)} "
        f"{N(el['zin_imag'], 1)}j Ω und |S11| = {N(el['s11_db'], 1)} dB bei "
        f"2,185 GHz; die beste Anpassung ist {N(el['best_s11_db'], 1)} dB bei "
        f"{N(el['best_ghz'], 3)} GHz.  Die −10-dB-Bandbreite reicht von "
        f"{N(el['bw10_low_ghz'], 3)} bis {N(el['bw10_high_ghz'], 3)} GHz."))
    r.figure(str(FIG / "fig01_element_match.png"),
             T("Input impedance and reflection of the tuned element.",
               "Eingangsimpedanz und Reflexion des abgestimmten Elements."),
             16.0)
    r.p(T(
        f"The isolated element reaches {N(el['dmax'], 2)} dBi directivity at "
        f"η = {N(el['eff'], 3)}, but its beam is **not** broadside-symmetric: "
        f"the deep inset probe ({N(des['inset_mm'])} mm from the edge) and "
        f"the finite 340 mm ground plane tilt the maximum to about 26° in the "
        f"E plane.  This is a single-element effect: in the fully driven "
        f"array the symmetric excitation produces a clean broadside beam "
        f"(Section 5).  A product design would use a symmetric dual-probe or "
        f"a corporate feed to avoid the tilt.",
        f"Das isolierte Element erreicht {N(el['dmax'], 2)} dBi Richtfaktor "
        f"bei η = {N(el['eff'], 3)}, aber seine Keule ist **nicht** "
        f"broadside-symmetrisch: Die tiefe Sonden-Speisung "
        f"({N(des['inset_mm'])} mm von der Kante) und die endliche "
        f"340-mm-Groundplane kippen das Maximum im E-Schnitt auf etwa 26°.  "
        f"Das ist ein Einzelelement-Effekt: Im voll gespeisten Array erzeugt "
        f"die symmetrische Anregung eine saubere Broadside-Keule "
        f"(Abschnitt 5).  Ein Produktentwurf würde eine symmetrische "
        f"Doppelsonde oder eine Corporate-Speisung nutzen, um die Kippung zu "
        f"vermeiden."))
    r.figure(str(FIG / "fig02_element_pattern.png"),
             T(f"Element pattern at 2.185 GHz ({N(el['gain'], 2)} dBi peak).",
               f"Elementdiagramm bei 2,185 GHz ({N(el['gain'], 2)} dBi "
               f"Maximum)."), 11.4)

    # ------------------------------------------------------------- 4
    r.h1("4", T("Embedded element and coupling",
                "Eingebettetes Element und Kopplung"))
    r.p(T(
        f"In the embedded run only port P6 is driven; the other fifteen ports "
        f"are terminated in 50 Ω.  The self reflection rises to "
        f"{N(cp['s66_db'], 1)} dB – not because of ohmic loss but because the "
        f"mutual coupling shifts the element resonance from 2.192 GHz "
        f"(isolated) to about 2.205 GHz, i.e. by more than half of the "
        f"28 MHz matching bandwidth.  This is the key result of the embedded "
        f"run: with a 1.5 mm substrate the element is too narrowband for the "
        f"coupled array environment.  The neighbour coupling itself is "
        f"{N(cp['coupling_max'], 1)} dB at λ/2 spacing.",
        f"Im eingebetteten Lauf wird nur Port P6 angeregt; die übrigen "
        f"fünfzehn Ports sind mit 50 Ω abgeschlossen.  Die Eigenreflexion "
        f"steigt auf {N(cp['s66_db'], 1)} dB – nicht wegen ohmscher Verluste, "
        f"sondern weil die Kopplung die Elementresonanz von 2,192 GHz "
        f"(isoliert) auf etwa 2,205 GHz verschiebt, also um mehr als die "
        f"halbe 28-MHz-Anpassbandbreite.  Das ist das zentrale Ergebnis des "
        f"eingebetteten Laufs: Mit 1,5 mm Substrat ist das Element für die "
        f"gekoppelte Arrayumgebung zu schmalbandig.  Die Nachbarkooplung "
        f"selbst beträgt {N(cp['coupling_max'], 1)} dB bei λ/2-Raster."))
    r.figure(str(FIG / "fig04_coupling.png"),
             T("Coupling column S_i6 of the embedded run.",
               "Kopplungsspalte S_i6 des eingebetteten Laufs."), 16.0)
    r.p(T(
        "The embedded element pattern is slightly wider than the isolated one "
        "because the neighbours scatter part of the radiated field.",
        "Das eingebettete Elementdiagramm ist etwas breiter als das isolierte, "
        "weil die Nachbarn einen Teil des abgestrahlten Feldes streuen."))
    r.figure(str(FIG / "fig03_element_vs_embedded.png"),
             T("E and H plane: isolated versus embedded element at 2.185 GHz.",
               "E- und H-Ebene: isoliertes versus eingebettetes Element bei "
               "2,185 GHz."), 16.0)

    # ------------------------------------------------------------- 5
    r.h1("5", T("Broadside 4×4 array", "Broadside-4×4-Array"))
    r.p(T(
        f"With all sixteen ports driven in phase the array reaches "
        f"{N(arr['dmax'], 2)} dBi directivity.  The sizing study predicted "
        f"about 17 dBi for a 4×4 on a λ/2 lattice; the difference is the "
        f"element pattern and the mutual coupling, which the aperture estimate "
        f"ignores.",
        f"Mit allen sechzehn Ports in Phase erreicht das Array "
        f"{N(arr['dmax'], 2)} dBi Richtfaktor.  Die Sizing-Studie sagte für "
        f"ein 4×4 auf λ/2-Raster etwa 17 dBi voraus; die Differenz stammt aus "
        f"Elementdiagramm und Kopplung, die die Aperturschätzung ignoriert."))
    r.p(T(
        f"The raw efficiency from the bundled post-processing is "
        f"{N(arr['eff_raw'], 2)} because it uses the accepted power of a "
        f"single port for a sixteen-port excitation.  After summing the "
        f"accepted power of all ports the array efficiency is "
        f"{N(arr['eff_corr'], 3)} and the realised gain "
        f"{N(arr['gain_corr'], 2)} dBi.",
        f"Der rohe Wirkungsgrad der mitgelieferten Nachverarbeitung ist "
        f"{N(arr['eff_raw'], 2)}, weil sie bei sechzehn angeregten Ports nur "
        f"die Leistung eines Ports verwendet.  Nach Summation der "
        f"aufgenommenen Leistung aller Ports ergibt sich ein Wirkungsgrad von "
        f"{N(arr['eff_corr'], 3)} und ein realisierter Gewinn von "
        f"{N(arr['gain_corr'], 2)} dBi."))
    r.figure(str(FIG / "fig05_broadside.png"),
             T("Broadside array at 2.185 GHz: 3D pattern, E and H plane with "
               "the isolated element for reference.",
               "Broadside-Array bei 2,185 GHz: 3D-Diagramm, E- und H-Ebene mit "
               "dem isolierten Element als Referenz."), 16.4)
    r.p(T(
        "The array beam is clean and broadside, in contrast to the tilted "
        "isolated-element pattern.  The first sidelobes are about 12 dB below "
        "the main lobe; a full element-×-array-factor comparison is not "
        "meaningful here because the isolated element is tilted, so the cuts "
        "are shown against the isolated element as a reference only.",
        "Die Array-Keule ist sauber und broadside – im Gegensatz zum "
        "gekippten Einzelelement-Diagramm.  Die ersten Nebenkeulen liegen "
        "etwa 12 dB unter der Hauptkeule; ein vollständiger "
        "Element-×-Arrayfaktor-Vergleich ist hier nicht sinnvoll, weil das "
        "isolierte Element gekippt ist.  Die Schnitte zeigen es daher nur als "
        "Referenz."))

    # ------------------------------------------------------------- 6
    sweep = []
    for p in sorted((DOCS / "sweep").glob("scan_*.npz")):
        d = np.load(p)
        sweep.append((float(d["steer_deg"]), float(d["peak_theta_deg"]),
                      float(d["peak_phi_deg"]), float(d["peak_gain_dbi"])))
    sweep.sort()
    if sweep:
        r.h1("6", T("Beam steering", "Strahlschwenkung"))
        r.p(T(
            f"Six additional FDTD runs steer the beam with a progressive port "
            f"phase (90° per element gives 30°); the 0° frame is "
            f"the existing broadside run.  Figure 6 shows the E-plane cuts of "
            f"all angles; the animation (`anim_beam_steer.gif`, also `.webp` "
            f"and `.mp4`) is included in the repository.",
            f"Sechs zusätzliche FDTD-Läufe schwenken die Keule über eine "
            f"progressive Portphase (90° pro Element ergeben 30°); das "
            f"0°-Bild ist der vorhandene Broadside-Lauf.  Bild 6 zeigt die "
            f"E-Ebenen aller Winkel; die Animation (`anim_beam_steer.gif`, "
            f"auch `.webp` und `.mp4`) liegt im Repository."))
        r.table(
            T("Peak direction versus nominal steering angle at 2.185 GHz.",
              "Maximum-Richtung über dem Sollwinkel bei 2,185 GHz."),
            [T("nominal θ₀", "Soll θ₀"), T("peak θ", "Maximum θ"),
             T("peak φ", "Maximum φ"), T("gain", "Gewinn")],
            [[f"{s:+.0f}°", f"{t:.0f}°", f"{p:.0f}°", f"{g:.2f} dBi"]
             for s, t, p, g in sweep],
            widths=[3.4, 3.4, 3.4, 4.0],
            source=T("Signed peak: negative angles appear at φ = 180°.",
                     "Vorzeichenbehaftetes Maximum: negative Winkel liegen bei "
                     "φ = 180°."))
        r.figure(str(FIG / "fig06_beam_sweep.png"),
                 T("Full-wave beam steering: signed E-plane cuts of all runs.",
                   "Vollwellen-Strahlschwenkung: vorzeichenbehaftete "
                   "E-Ebenen-Schnitte aller Läufe."), 16.0)
        r.figure(str(FIG / "anim_beam_steer_frame.png"),
                 T("Single frame of the animation (θ₀ = +30°).",
                   "Einzelbild der Animation (θ₀ = +30°)."), 14.0)

    # ------------------------------------------------------------- 7
    r.h1("7", T("Discussion and next steps", "Diskussion und nächste Schritte"))
    r.bullets([
        T("The probe feed is a modelling abstraction for independent element "
          "excitation.  A product would use a corporate microstrip feed; its "
          "loss (about 1–1.5 dB) and the feed-network coupling must then be "
          "simulated as part of the structure.",
          "Die Sonden-Speisung ist eine Modellabstraktion für die unabhängige "
          "Anregung der Elemente.  Ein Produkt würde eine Corporate-"
          "Mikrostreifen-Speisung nutzen; deren Verlust (ca. 1–1,5 dB) und "
          "die Speisenetz-Kopplung müssen dann mit simuliert werden."),
        T(f"The coupling of {N(cp['coupling_max'], 1)} dB at λ/2 spacing is "
          f"the dominant deviation from the ideal array factor and should be "
          f"addressed by a thicker substrate, a slot or a defected ground "
          f"structure.",
          f"Die Kopplung von {N(cp['coupling_max'], 1)} dB bei λ/2-Raster ist "
          f"die dominante Abweichung vom idealen Arrayfaktor und sollte durch "
          f"ein dickeres Substrat, Schlitze oder eine strukturierte "
          f"Grundfläche adressiert werden."),
        T("Circular polarisation and the scan sweep (±60°) are the next "
          "simulation steps; the workflow of the 77 GHz study can be reused "
          "unchanged.",
          "Zirkulare Polarisation und der Scan-Sweep (±60°) sind die nächsten "
          "Simulationsschritte; der Workflow der 77-GHz-Studie kann "
          "unverändert übernommen werden."),
        T("A finite-roof model (1.4 × 1.2 m ground plane) would quantify the "
          "vehicle-body effect on the pattern and the back lobe.",
          "Ein endliches-Dach-Modell (1,4 × 1,2 m Groundplane) würde den "
          "Karosserieeinfluss auf Diagramm und Rückkeule quantifizieren."),
    ])

    # ------------------------------------------------------------- 8
    r.h1("8", T("Reproduction", "Reproduktion"))
    r.code(
        "python make_project.py                      # three .fcsim.json\n"
        "python validate_project.py                  # mesh checks\n"
        "python run_headless.py patch_element_2p2ghz.fcsim.json\n"
        "python run_headless.py array_4x4_2p2ghz.fcsim.json\n"
        "python run_headless.py array_4x4_broadside_2p2ghz.fcsim.json\n"
        "python make_sweep.py                        # steering projects\n"
        "python run_sweep.py                         # steering runs\n"
        "python plot_results.py                      # figures + results.json\n"
        "python make_animation.py                    # GIF / WebP / MP4\n"
        "python build_docs.py                        # this report (EN + DE)")
    r.p(T(
        "The element runs take about 15 min each (19k timesteps, 1.0 M cells); "
        "the array runs use the same mesh and take roughly twice as long.",
        "Die Elementläufe dauern rund 15 min (19k Zeitschritte, 1,0 Mio. "
        "Zellen); die Array-Läufe nutzen dasselbe Mesh und brauchen etwa "
        "doppelt so lange."))

    out = DOCS / f"n256_array_2p185ghz_{lang}.odt"
    r.save(str(out))
    print(f"wrote {out}")
    pdf = export_pdf(out)
    if pdf:
        print(f"wrote {pdf}")
    return out


def main() -> int:
    build("en")
    build("de")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
