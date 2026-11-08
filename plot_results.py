"""Result figures and results.json for the n256 (2.185 GHz) array study.

Reads the finished runs and writes ``docs/figures/fig01..06.png`` plus
``docs/results.json`` (the number source for ``build_docs.py``).

Runs consumed
-------------
``work_patch_element_2p2ghz``  single element, isolated reference
``work_array_4x4_2p2ghz``      4x4, only P6 driven (embedded element, coupling)
``work_array_4x4_broadside_2p2ghz``  4x4, all 16 ports in phase

Usage::

    python plot_results.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

import array_model as am
from analyze_zin import load_signal

HERE = Path(__file__).resolve().parent
FIG = HERE / "docs" / "figures"
F0 = 2.185e9
DB_FLOOR = -30.0

RUNS = {
    "element": "work_patch_element_2p2ghz",
    "embedded": "work_array_4x4_2p2ghz",
    "broadside": "work_array_4x4_broadside_2p2ghz",
}


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------

def load_s(work: str, key: str = "S11") -> tuple[np.ndarray, np.ndarray]:
    d = json.loads((HERE / work / "sparams" / "sparams.json")
                   .read_text(encoding="utf-8"))
    f = np.array(d["freq"])
    s = np.array(d[key]["real"]) + 1j * np.array(d[key]["imag"])
    return f, s


def load_nf(work: str) -> dict:
    d = json.loads((HERE / work / "nf2ff" / "nf2ff.json")
                   .read_text(encoding="utf-8"))
    return {
        "freq": np.array(d["frequencies"]),
        "theta": np.array(d["theta_deg"]),
        "phi": np.array(d["phi_deg"]),
        "D": np.array(d["D_dBi"]),
        "gain": np.array(d["gain_dBi"]),
        "Dmax": np.array(d["Dmax_dBi"]),
        "eff": np.array(d["efficiency"]),
        "Prad": np.array(d["Prad"]),
    }


def s11_db(s: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.clip(np.abs(s), 1e-12, None))


def z_of(s: np.ndarray) -> np.ndarray:
    return 50.0 * (1.0 + s) / (1.0 - s)


def f0_index(f: np.ndarray) -> int:
    return int(np.argmin(np.abs(f - F0)))


def bw_10db(f: np.ndarray, s: np.ndarray) -> tuple[float, float, float]:
    db = s11_db(s)
    k = f0_index(f)
    if db[k] > -10.0:
        return float("nan"), float("nan"), float("nan")
    lo = k
    while lo > 0 and db[lo - 1] <= -10.0:
        lo -= 1
    hi = k
    while hi < len(f) - 1 and db[hi + 1] <= -10.0:
        hi += 1
    return float(f[lo]), float(f[hi]), float(f[hi] - f[lo])


def dft_pulse(x: np.ndarray, t: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    dt = float(np.mean(np.diff(t)))
    ph = np.exp(-1j * 2.0 * np.pi * freqs[None, :] * t[:, None])
    return 2.0 * (x[:, None] * ph).sum(axis=0) * dt


def accepted_power(work: str, freqs: np.ndarray) -> np.ndarray:
    """Sum of 0.5*Re(U I*) over all driven ports (same time axis)."""
    sim = HERE / work / "simulation"
    total = np.zeros(len(freqs), dtype=float)
    n = 0
    for p in range(1, 17):
        ut_p, it_p = sim / f"port_ut_{p}", sim / f"port_it_{p}"
        if not (ut_p.is_file() and it_p.is_file()):
            continue
        tu, ut = load_signal(ut_p)
        _, it = load_signal(it_p)
        u = dft_pulse(ut, tu, freqs)
        i = dft_pulse(it, tu, freqs)
        total += 0.5 * np.real(u * np.conj(i))
        n += 1
    if n == 0:
        raise RuntimeError(f"no port signals in {work}")
    return total


def array_factor(theta_deg: np.ndarray, phi_deg: np.ndarray,
                 pos: np.ndarray, phases_deg: np.ndarray) -> np.ndarray:
    th = np.radians(theta_deg)
    ph = np.radians(phi_deg)
    proj = (pos[:, 0][:, None] * (np.sin(th) * np.cos(ph))[None, :]
            + pos[:, 1][:, None] * (np.sin(th) * np.sin(ph))[None, :])
    total = 2.0 * np.pi / am.LAMBDA0_MM * proj + np.radians(phases_deg)[:, None]
    af = np.exp(1j * total).sum(axis=0) / len(pos)
    return np.abs(af) ** 2


def element_positions() -> np.ndarray:
    return np.array([am.element_xy(i, j)
                     for j in range(am.N_Y) for i in range(am.N_X)])


def _cut(nf: dict, fi: int, phi_deg: float):
    j = int(round(phi_deg / 180.0 * (len(nf["phi"]) - 1) / 2.0 * 2.0))
    j = int(np.argmin(np.abs(nf["phi"] - phi_deg)))
    return nf["theta"], nf["D"][fi][:, j], nf["gain"][fi][:, j]


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

def fig_element_match() -> dict:
    f, s = load_s(RUNS["element"])
    z = z_of(s)
    k = f0_index(f)
    lo, hi, bw = bw_10db(f, s)

    fig, ax = plt.subplots(1, 2, figsize=(11.2, 4.3), dpi=140)
    ax[0].plot(f / 1e9, z.real, color="#1f5fa8", lw=1.8, label="Re Zin")
    ax[0].plot(f / 1e9, z.imag, color="#c0392b", lw=1.8, ls="--",
               label="Im Zin")
    ax[0].axhline(50, color="gray", lw=0.9, ls=":")
    ax[0].axhline(0, color="k", lw=0.7)
    ax[0].axvline(F0 / 1e9, color="#7f8c8d", lw=0.9, ls=":")
    ax[0].plot([F0 / 1e9], [z[k].real], "o", color="#1f5fa8", ms=5)
    ax[0].plot([F0 / 1e9], [z[k].imag], "o", color="#c0392b", ms=5)
    ax[0].set_xlabel("frequency (GHz)")
    ax[0].set_ylabel("Zin (ohm)")
    ax[0].set_title(f"Input impedance - Zin = {z[k].real:.1f} "
                    f"{z[k].imag:+.1f}j ohm")
    ax[0].grid(True, alpha=0.4)
    ax[0].legend(fontsize=9)

    ax[1].plot(f / 1e9, s11_db(s), color="#1f5fa8", lw=2.0)
    ax[1].axhline(-10, color="#c0392b", lw=1.0, ls=":")
    ax[1].axvline(F0 / 1e9, color="#7f8c8d", lw=0.9, ls=":")
    ax[1].set_xlabel("frequency (GHz)")
    ax[1].set_ylabel("|S11| (dB)")
    ax[1].set_title(f"Reflection - |S11| = {s11_db(s)[k]:.1f} dB")
    ax[1].grid(True, alpha=0.4)

    fig.tight_layout()
    out = FIG / "fig01_element_match.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")
    return {
        "zin_real": float(z[k].real), "zin_imag": float(z[k].imag),
        "s11_db": float(s11_db(s)[k]),
        "best_s11_db": float(np.min(s11_db(s))),
        "best_ghz": float(f[np.argmin(s11_db(s))] / 1e9),
        "bw10_low_ghz": lo / 1e9, "bw10_high_ghz": hi / 1e9,
        "bw10_ghz": bw / 1e9,
        "vswr": float((1 + abs(s[k])) / (1 - abs(s[k]))),
    }


def _pattern_3d(ax, nf: dict, fi: int, title: str) -> float:
    th = np.radians(nf["theta"])
    ph = np.radians(nf["phi"])
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    G = nf["gain"][fi]
    peak = float(np.max(G))
    Gc = np.clip(G, peak + DB_FLOOR, None)
    amp = 10 ** ((Gc - peak) / 20.0)
    X = amp * np.sin(TH) * np.cos(PH)
    Y = amp * np.sin(TH) * np.sin(PH)
    Z = amp * np.cos(TH)
    cmap = plt.get_cmap("jet")
    ax.plot_surface(X, Y, Z, facecolors=cmap(
        Normalize(peak + DB_FLOOR, peak)(Gc)),
        rstride=2, cstride=2, linewidth=0, antialiased=False, shade=False)
    ax.set_title(title, fontsize=10)
    ax.set_box_aspect((1, 1, 0.85))
    lim = 1.05
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-lim, lim)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.view_init(elev=24, azim=-132)
    return peak


def fig_element_pattern() -> dict:
    nf = load_nf(RUNS["element"])
    fi = f0_index(nf["freq"])
    fig = plt.figure(figsize=(6.4, 5.4), dpi=140)
    ax = fig.add_subplot(111, projection="3d")
    peak = _pattern_3d(ax, nf, fi,
                       f"Isolated element, gain at 2.185 GHz "
                       f"(peak {nf['gain'][fi].max():.2f} dBi)")
    m = plt.cm.ScalarMappable(
        cmap="jet", norm=Normalize(nf["gain"][fi].max() + DB_FLOOR,
                                   nf["gain"][fi].max()))
    m.set_array([])
    fig.colorbar(m, ax=ax, shrink=0.6, pad=0.02, label="gain (dBi)")
    fig.tight_layout()
    out = FIG / "fig02_element_pattern.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")
    return {"dmax": float(nf["Dmax"][fi]), "eff": float(nf["eff"][fi]),
            "gain": float(np.max(nf["gain"][fi])), "peak": peak}


def fig_element_vs_embedded() -> dict:
    iso = load_nf(RUNS["element"])
    emb = load_nf(RUNS["embedded"])
    fi = f0_index(iso["freq"])
    fig, ax = plt.subplots(1, 2, figsize=(11.0, 4.3), dpi=140,
                           subplot_kw={"projection": "polar"})
    for a, (phi, name) in zip(ax, ((0.0, "E-plane (xz, phi = 0)"),
                                   (90.0, "H-plane (yz, phi = 90)"))):
        th, _, g_i = _cut(iso, fi, phi)
        _, _, g_e = _cut(emb, fi, phi)
        a.plot(np.radians(th), g_i, color="#1f5fa8", lw=1.8,
               label="isolated element")
        a.plot(np.radians(th), g_e, color="#c0392b", lw=1.8, ls="--",
               label="embedded (P6)")
        a.set_theta_zero_location("N")
        a.set_theta_direction(-1)
        a.set_thetagrids(range(0, 360, 45))
        lo = min(g_i.min(), g_e.min())
        a.set_rlim(lo - 2, max(g_i.max(), g_e.max()) + 2)
        a.set_title(name, fontsize=10, pad=12)
        a.grid(True, alpha=0.4)
        a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.22),
                 fontsize=8, ncol=2)
    fig.tight_layout()
    out = FIG / "fig03_element_vs_embedded.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")
    fe = f0_index(emb["freq"])
    return {"embedded_dmax": float(emb["Dmax"][fe]),
            "embedded_eff": float(emb["eff"][fe])}


def fig_coupling() -> dict:
    f, _ = load_s(RUNS["embedded"], "S_P6")
    s66 = load_s(RUNS["embedded"], "S_P6")[1]
    k = f0_index(f)
    entries = []
    for n in range(1, 17):
        _, s = load_s(RUNS["embedded"], f"S_P{n}")
        xk, yk = am.port_xy(n)
        x6, y6 = am.port_xy(6)
        entries.append((n, math.hypot(xk - x6, yk - y6),
                        float(s11_db(np.array([s[k]]))[0])))
    entries.sort(key=lambda e: e[1])

    fig, ax = plt.subplots(1, 2, figsize=(11.0, 4.3), dpi=140)
    dists = [e[1] for e in entries if e[0] != 6]
    cpls = [e[2] for e in entries if e[0] != 6]
    ax[0].scatter(dists, cpls, s=42, color="#1f5fa8", zorder=3)
    for idx, (n, d, c) in enumerate(entries):
        if n != 6:
            ax[0].annotate(f"P{n}", (d, c), fontsize=7,
                           xytext=(4, 4 if idx % 2 else -10),
                           textcoords="offset points")
    ax[0].axhline(s11_db(np.array([s66[k]]))[0], color="#c0392b", ls="--",
                  label=f"|S66| = {s11_db(np.array([s66[k]]))[0]:.1f} dB")
    ax[0].set_xlabel("distance from P6 (mm)")
    ax[0].set_ylabel("|S_i6| (dB)")
    ax[0].set_title("Coupling column at 2.185 GHz")
    ax[0].grid(True, alpha=0.4)
    ax[0].legend(fontsize=8)

    for n, style in ((5, "-"), (2, "--"), (1, "-."), (10, ":")):
        _, s = load_s(RUNS["embedded"], f"S_P{n}")
        ax[1].plot(f / 1e9, s11_db(s), ls=style, lw=1.5,
                   label=f"|S{n}6| @ {math.dist(am.port_xy(n), am.port_xy(6)):.1f} mm")
    ax[1].plot(f / 1e9, s11_db(s66), color="#c0392b", lw=1.8,
               label="|S66|")
    ax[1].set_xlabel("frequency (GHz)")
    ax[1].set_ylabel("|S| (dB)")
    ax[1].set_title("Coupling vs frequency")
    ax[1].grid(True, alpha=0.4)
    ax[1].legend(fontsize=8)
    fig.tight_layout()
    out = FIG / "fig04_coupling.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")
    near = [c for n, d, c in entries if n != 6 and d < 2.0 * am.PITCH_MM]
    return {"s66_db": float(s11_db(np.array([s66[k]]))[0]),
            "coupling_max": float(max(cpls)),
            "coupling_nearest": float(max(near)) if near else None}


def fig_array() -> dict:
    nf = load_nf(RUNS["broadside"])
    fi = f0_index(nf["freq"])
    pos = element_positions()
    ph = np.zeros(len(pos))

    iso = load_nf(RUNS["element"])
    th_e, _, g_e = _cut(iso, fi, 0.0)
    th_h, _, g_h = _cut(iso, fi, 90.0)

    fig = plt.figure(figsize=(12.8, 4.8), dpi=140)
    ax3 = fig.add_subplot(1, 3, 1, projection="3d")
    _pattern_3d(ax3, nf, fi,
                f"Broadside, 2.185 GHz\npeak {nf['gain'][fi].max():.2f} dBi")
    m = plt.cm.ScalarMappable(
        cmap="jet", norm=Normalize(nf["gain"][fi].max() + DB_FLOOR,
                                   nf["gain"][fi].max()))
    m.set_array([])
    fig.colorbar(m, ax=ax3, shrink=0.55, pad=0.02, label="gain (dBi)")

    ax2 = fig.add_subplot(1, 3, 2)
    g_fw = _cut(nf, fi, 0.0)[2]
    floor = float(np.max(g_fw)) - 40.0
    ax2.plot(th_e, g_fw, color="#1f5fa8", lw=1.9, label="4x4 full wave")
    ax2.plot(th_e, g_e, color="#c0392b", lw=1.2, ls="--",
             label="isolated element")
    ax2.set_ylim(floor, float(np.max(g_fw)) + 6)
    ax2.set_xlabel("theta (deg), phi = 0")
    ax2.set_ylabel("gain (dBi)")
    ax2.set_title("E-plane cut", fontsize=10)
    ax2.grid(True, alpha=0.4)
    ax2.legend(fontsize=8, loc="lower left")

    ax3b = fig.add_subplot(1, 3, 3)
    g_fwh = _cut(nf, fi, 90.0)[2]
    ax3b.plot(th_h, g_fwh, color="#1f5fa8", lw=1.9, label="4x4 full wave")
    ax3b.plot(th_h, g_h, color="#c0392b", lw=1.2, ls="--",
              label="isolated element")
    ax3b.set_ylim(floor, float(np.max(g_fw)) + 6)
    ax3b.set_xlabel("theta (deg), phi = 90")
    ax3b.set_title("H-plane cut", fontsize=10)
    ax3b.grid(True, alpha=0.4)
    ax3b.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    out = FIG / "fig05_broadside.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")

    G = nf["gain"][fi]
    ti, pi = np.unravel_index(int(np.argmax(G)), G.shape)
    return {"dmax": float(nf["Dmax"][fi]),
            "gain": float(G[ti, pi]), "eff_raw": float(nf["eff"][fi]),
            "theta_peak": float(nf["theta"][ti]),
            "phi_peak": float(nf["phi"][pi])}


def array_power_numbers(work: str, nf: dict) -> dict:
    p = accepted_power(work, nf["freq"])
    fi = f0_index(nf["freq"])
    eta = nf["Prad"] / p
    gain = nf["D"] + 10 * np.log10(np.clip(eta, 1e-9, None))[:, None, None]
    return {"eta": eta, "gain": gain, "p_acc": p, "fi": fi}


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    res: dict = {"design": {
        "f0_ghz": F0 / 1e9, "band_ghz": [am.F_START_HZ / 1e9,
                                         am.F_STOP_HZ / 1e9],
        "patch_l_mm": am.PATCH_L_MM, "patch_w_mm": am.PATCH_W_MM,
        "inset_mm": am.FEED_INSET_MM, "pitch_mm": am.PITCH_MM,
        "board_mm": am.BOARD_MM, "n_x": am.N_X, "n_y": am.N_Y,
        "substrate": am.SUBSTRATE_NAME, "eps_r": am.SUBSTRATE_EPS_R,
        "tand": am.SUBSTRATE_TAND, "h_mm": am.SUBSTRATE_H_MM,
        "lambda0_mm": am.LAMBDA0_MM,
    }}

    res["element"] = fig_element_match()
    res["element"].update(fig_element_pattern())
    res["element"].update(fig_element_vs_embedded())
    res["coupling"] = fig_coupling()
    res["array"] = fig_array()

    nf = load_nf(RUNS["broadside"])
    corr = array_power_numbers(RUNS["broadside"], nf)
    fi = corr["fi"]
    res["array"]["eff_corr"] = float(corr["eta"][fi])
    res["array"]["gain_corr"] = float(corr["gain"][fi][
        int(np.argmin(np.abs(nf["theta"] - res["array"]["theta_peak"]))),
        int(np.argmin(np.abs(nf["phi"] - res["array"]["phi_peak"])))])
    print(f"array: eta raw {res['array']['eff_raw']:.2f} -> "
          f"corrected {res['array']['eff_corr']:.3f}")

    out = HERE / "docs" / "results.json"
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
