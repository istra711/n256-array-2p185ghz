"""Quick Zin(f) analysis of a finished run (debug tool).

DFTs the raw port time signals ``simulation/port_ut_N`` / ``port_it_N`` and
plots Re/Im/Zin over a wide band, so a resonance outside the simulated
S-parameter band can be located.

Usage::

    python analyze_zin.py work_element --port 1 --fmin 50e9 --fmax 110e9
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_signal(path: Path) -> tuple[np.ndarray, np.ndarray]:
    t, v = [], []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("%"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                t.append(float(parts[0]))
                v.append(float(parts[1]))
    return np.asarray(t), np.asarray(v)


def dft(t: np.ndarray, y: np.ndarray, freqs: np.ndarray) -> np.ndarray:
    """Rectangular-window DFT (openEMS uses the same integral)."""
    return np.array([
        np.trapz(y * np.exp(-1j * 2 * np.pi * f * t), t) for f in freqs
    ])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("work", help="work directory (contains simulation/)")
    ap.add_argument("--port", type=int, default=1)
    ap.add_argument("--fmin", type=float, default=50e9)
    ap.add_argument("--fmax", type=float, default=110e9)
    ap.add_argument("--steps", type=int, default=601)
    ap.add_argument("--out", default="")
    ap.add_argument("--print", action="store_true",
                    help="print Z(f) and S11-from-Z table")
    args = ap.parse_args()

    sim = Path(args.work) / "simulation"
    tu, ut = load_signal(sim / f"port_ut_{args.port}")
    ti, it = load_signal(sim / f"port_it_{args.port}")
    print(f"port_ut: {len(tu)} samples, t = {tu[0]:.3e} .. {tu[-1]:.3e} s")
    print(f"port_it: {len(ti)} samples, t = {ti[0]:.3e} .. {ti[-1]:.3e} s")

    freqs = np.linspace(args.fmin, args.fmax, args.steps)
    u = dft(tu, ut, freqs)
    i = dft(ti, it, freqs)
    z = u / i

    k = np.argmin(np.abs(z.imag))
    mag = np.abs(z)
    print(f"\n  f(Im Z ~ 0)      : {freqs[k]/1e9:.3f} GHz")
    print(f"  Z at that freq   : {z[k].real:.2f} {z[k].imag:+.2f}j ohm")
    kmax = np.argmax(mag)
    print(f"  |Z| max          : {mag[kmax]:.1f} ohm @ {freqs[kmax]/1e9:.2f} GHz")
    for f in (74e9, 77e9, 80e9):
        j = int(np.argmin(np.abs(freqs - f)))
        print(f"  Z({f/1e9:.0f} GHz)        : {z[j].real:8.2f} {z[j].imag:+8.2f}j ohm"
              f"   |Z|={mag[j]:.1f}")

    if args.print:
        print("\n   f [GHz]    Re Z     Im Z    |S11| [dB]")
        for f in np.arange(np.ceil(args.fmin / 1e9), args.fmax / 1e9 + 1e-9, 0.5):
            j = int(np.argmin(np.abs(freqs - f * 1e9)))
            gam = (z[j] - 50.0) / (z[j] + 50.0)
            print(f"   {freqs[j]/1e9:7.2f}  {z[j].real:8.2f} {z[j].imag:+8.2f}"
                  f"   {20*np.log10(abs(gam)):8.2f}")

    fig, ax = plt.subplots(1, 2, figsize=(11.4, 4.4), dpi=140)
    ax[0].plot(freqs / 1e9, z.real, label="Re{Zin}")
    ax[0].plot(freqs / 1e9, z.imag, label="Im{Zin}")
    ax[0].axhline(0, color="k", lw=0.7)
    ax[0].axhline(50, color="gray", lw=0.7, ls="--")
    ax[0].set_xlabel("Frequency (GHz)")
    ax[0].set_ylabel("Zin (Ohm)")
    ax[0].grid(True)
    ax[0].legend()
    ax[0].set_title(f"Input impedance, port {args.port}")

    ax[1].plot(freqs / 1e9, 20 * np.log10(np.abs(
        (z - 50) / (z + 50))))
    ax[1].set_xlabel("Frequency (GHz)")
    ax[1].set_ylabel("|S11| from Zin (dB)")
    ax[1].grid(True)
    ax[1].set_title("Reflection from Zin (50 ohm reference)")

    fig.tight_layout()
    out = Path(args.out) if args.out else Path(args.work) / "zin_analysis.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
