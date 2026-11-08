"""Build the 3D beam-steering animation of the n256 array study.

Reads the archived 2.185 GHz patterns in ``docs/sweep/scan_*.npz`` and renders
one frame per steering angle (3D lobe + polar E-plane cut), then assembles
GIF, animated WebP and MP4.

Usage::

    python make_animation.py
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from PIL import Image

HERE = Path(__file__).resolve().parent
SWEEP = HERE / "docs" / "sweep"
FIG = HERE / "docs" / "figures"
DB_FLOOR = 30.0


def load_frames() -> list[dict]:
    frames = []
    for p in sorted(SWEEP.glob("scan_*.npz")):
        d = np.load(p)
        frames.append({
            "steer": float(d["steer_deg"]),
            "theta": d["theta"].astype(float),
            "phi": d["phi"].astype(float),
            "gain": d["gain77"].astype(float),
            "peak_theta": float(d["peak_theta_deg"]),
            "peak_phi": float(d["peak_phi_deg"]),
            "peak_gain": float(d["peak_gain_dbi"]),
        })
    frames.sort(key=lambda f: f["steer"])
    return frames


def plane_cut(frame: dict) -> tuple[np.ndarray, np.ndarray, float]:
    if frame["steer"] < 0:
        j = int(np.argmin(np.abs(frame["phi"] - 180.0)))
        return -frame["theta"], frame["gain"][:, j], -frame["peak_theta"]
    j = int(np.argmin(np.abs(frame["phi"] - 0.0)))
    return frame["theta"], frame["gain"][:, j], frame["peak_theta"]


def render(frame: dict, gmax: float, vmin: float, path: Path,
           size: float) -> None:
    th = np.radians(frame["theta"])
    ph = np.radians(frame["phi"])
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    G = np.clip(frame["gain"], vmin, gmax)
    amp = 10.0 ** ((G - gmax) / 20.0)
    X = amp * np.sin(TH) * np.cos(PH)
    Y = amp * np.sin(TH) * np.sin(PH)
    Z = amp * np.cos(TH)

    norm = Normalize(vmin, gmax)
    cmap = plt.get_cmap("jet")
    col = plt.get_cmap("coolwarm")(0.5 + 0.5 * frame["steer"] / 45.0)

    fig = plt.figure(figsize=(size * 1.5, size * 0.80), dpi=110)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.22, 1.0])

    ax = fig.add_subplot(gs[0, 0], projection="3d")
    ax.plot_surface(X, Y, Z, facecolors=cmap(norm(G)), rstride=2, cstride=2,
                    linewidth=0, antialiased=False, shade=False)
    ax.set_box_aspect((1, 1, 0.9))
    lim = 1.06
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_zlim(-lim, lim)
    ax.set_xlabel("x", labelpad=-4)
    ax.set_ylabel("y", labelpad=-4)
    ax.set_zlabel("z", labelpad=-6)
    ax.tick_params(labelsize=7, pad=-2)
    ax.view_init(elev=22, azim=-132)
    m = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    m.set_array([])
    fig.colorbar(m, ax=ax, shrink=0.60, pad=0.02, label="gain (dBi)")

    x, g, xpk = plane_cut(frame)
    axp = fig.add_subplot(gs[0, 1], projection="polar")
    axp.plot(np.radians(x), g, color=col, lw=2.0)
    axp.plot([np.radians(xpk)], [frame["peak_gain"]], "o", color=col, ms=6)
    axp.axvline(np.radians(frame["steer"]), color=col, lw=0.8, ls=":")
    axp.set_thetamin(-90)
    axp.set_thetamax(90)
    axp.set_theta_zero_location("N")
    axp.set_theta_direction(-1)
    axp.set_rlim(max(vmin, gmax - DB_FLOOR), gmax + 3.0)
    axp.set_yticklabels([])
    axp.tick_params(labelsize=8)
    axp.set_title("E plane", fontsize=9, pad=6)
    axp.grid(True, alpha=0.4)

    fig.suptitle(
        f"n256 4×4 array, full wave, 2.185 GHz     "
        f"$\\theta_0$ = {frame['steer']:+.0f}$^\\circ$     "
        f"peak $\\theta$ = {frame['peak_theta']:.0f}$^\\circ$, "
        f"$\\varphi$ = {frame['peak_phi']:.0f}$^\\circ$  "
        f"({frame['peak_gain']:.2f} dBi)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.92), pad=0.3)
    fig.savefig(path)
    plt.close(fig)


def write_movie(tmp: Path, fps: int, mp4: Path) -> bool:
    try:
        import imageio_ffmpeg
    except Exception:                       # noqa: BLE001
        return False
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-y", "-loglevel", "error", "-framerate", str(fps),
           "-i", str(tmp / "frame_%02d.png"),
           "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20", str(mp4)]
    return subprocess.call(cmd) == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=int, default=320)
    ap.add_argument("--size", type=float, default=6.4)
    args = ap.parse_args()

    frames = load_frames()
    if len(frames) < 2:
        raise SystemExit(f"need at least two sweep runs, found {len(frames)}")

    gmax = max(f["gain"].max() for f in frames)
    vmin = gmax - DB_FLOOR
    print(f"{len(frames)} frames, {vmin:.1f}..{gmax:.1f} dBi, "
          f"{frames[0]['steer']:+.0f}..{frames[-1]['steer']:+.0f} deg")

    FIG.mkdir(parents=True, exist_ok=True)
    tmp = HERE / "sweep_frames"
    tmp.mkdir(exist_ok=True)
    for old in tmp.glob("frame_*.png"):
        old.unlink()
    paths = []
    for i, fr in enumerate(frames):
        p = tmp / f"frame_{i:02d}.png"
        render(fr, gmax, vmin, p, args.size)
        paths.append(p)
        print(f"  frame {i+1:2d}/{len(frames)} theta0={fr['steer']:+.0f} "
              f"peak {fr['peak_theta']:.0f} deg @ {fr['peak_gain']:.2f} dBi")

    pick = min(range(len(frames)), key=lambda i: abs(frames[i]["steer"] - 30))
    fb = FIG / "anim_beam_steer_frame.png"
    Image.open(paths[pick]).save(fb)
    print(f"wrote {fb}")

    imgs = [Image.open(p).convert("RGB") for p in paths]
    quants = [im.quantize(colors=256, method=Image.MEDIANCUT) for im in imgs]
    gif = FIG / "anim_beam_steer.gif"
    quants[0].save(gif, save_all=True, append_images=quants[1:],
                   duration=args.duration, loop=0, optimize=True, disposal=2)
    print(f"wrote {gif}  ({gif.stat().st_size/1e6:.2f} MB)")

    webp = FIG / "anim_beam_steer.webp"
    imgs[0].save(webp, format="WEBP", save_all=True, append_images=imgs[1:],
                 duration=args.duration, loop=0, quality=82, method=6)
    print(f"wrote {webp}  ({webp.stat().st_size/1e6:.2f} MB)")

    mp4 = FIG / "anim_beam_steer.mp4"
    fps = max(1, int(round(1000.0 / args.duration)))
    if write_movie(tmp, fps, mp4):
        print(f"wrote {mp4}  ({mp4.stat().st_size/1e6:.2f} MB)")

    # static companion: signed E-plane cuts of all runs
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=150)
    cmap = plt.get_cmap("coolwarm")
    snorm = Normalize(frames[0]["steer"], frames[-1]["steer"])
    for fr in frames:
        x, g, xpk = plane_cut(fr)
        c = cmap(snorm(fr["steer"]))
        ax.plot(x, g, color=c, lw=1.6)
        ax.plot([xpk], [fr["peak_gain"]], "o", ms=3.5, color=c)
    ax.set_xlabel("signed theta (deg)  -  E plane")
    ax.set_ylabel("gain (dBi), 2.185 GHz")
    ax.set_title("Full-wave beam steering - E-plane cuts")
    ax.set_xlim(-90, 90)
    ax.set_ylim(gmax - 30, gmax + 3)
    ax.grid(True, alpha=0.4)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=snorm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="steering angle $\\theta_0$ (deg)")
    fig.tight_layout()
    sweep_fig = FIG / "fig06_beam_sweep.png"
    fig.savefig(sweep_fig)
    plt.close(fig)
    print(f"wrote {sweep_fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
