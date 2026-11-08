"""Run the n256 beam-steering sweep and archive the 2.185 GHz patterns.

The 0 deg frame reuses the existing broadside run; all other angles get their
own FDTD run.  After each run the 2.185 GHz gain pattern is stored as a small
``.npz`` in ``docs/sweep`` and the multi-hundred-MB work directory is deleted.

Usage::

    python run_sweep.py                 # full sweep, 2 runs in parallel
    python run_sweep.py --workers 3
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import array_model as am
from make_sweep import project_path, write_project

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "sweep"
LOGS = HERE / "sweep_logs"
F0 = 2.185e9
BROADSIDE_WORK = "work_array_4x4_broadside_2p2ghz"


def _work(theta_deg: float) -> Path:
    if abs(theta_deg) < 1e-6:
        return HERE / BROADSIDE_WORK
    return HERE / f"work_scan_{am.sweep_tag(theta_deg)}"


def extract(theta_deg: float, work: Path) -> Path:
    nf = json.loads((work / "nf2ff" / "nf2ff.json").read_text(encoding="utf-8"))
    freqs = np.asarray(nf["frequencies"], dtype=float)
    k = int(np.argmin(np.abs(freqs - F0)))
    gain = np.asarray(nf["gain_dBi"], dtype=float)[k].astype(np.float32)
    theta = np.asarray(nf["theta_deg"], dtype=float).astype(np.float32)
    phi = np.asarray(nf["phi_deg"], dtype=float).astype(np.float32)
    ti, pi = np.unravel_index(int(np.argmax(gain)), gain.shape)

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"scan_{am.sweep_tag(theta_deg)}.npz"
    np.savez_compressed(
        out, gain77=gain, theta=theta, phi=phi,
        steer_deg=np.float32(theta_deg),
        peak_theta_deg=np.float32(theta[ti]),
        peak_phi_deg=np.float32(phi[pi]),
        peak_gain_dbi=np.float32(gain[ti, pi]),
        dmax_dbi=np.float32(nf["Dmax_dBi"][k]),
    )
    return out


def run_one(theta_deg: float) -> str:
    tag = am.sweep_tag(theta_deg)
    npz = OUT / f"scan_{tag}.npz"
    if npz.is_file():
        return f"{tag}: cached"

    work = _work(theta_deg)
    if not work.is_dir() or not (work / "nf2ff" / "nf2ff.json").is_file():
        proj = project_path(theta_deg)
        if not proj.is_file():
            write_project(theta_deg)
        LOGS.mkdir(parents=True, exist_ok=True)
        log = LOGS / f"scan_{tag}.log"
        t0 = time.time()
        with log.open("w", encoding="utf-8", errors="replace") as fh:
            rc = subprocess.call(
                [sys.executable, str(HERE / "run_headless.py"), proj.name,
                 "--work", f"work_scan_{tag}"],
                cwd=str(HERE), stdout=fh, stderr=subprocess.STDOUT)
        if rc != 0:
            raise RuntimeError(f"{tag}: run_headless failed (rc={rc})")
        work = HERE / f"work_scan_{tag}"
        dt = time.time() - t0
    else:
        dt = 0.0

    out = extract(theta_deg, work)
    if abs(theta_deg) > 1e-6:
        shutil.rmtree(work, ignore_errors=True)
    return f"{tag}: {dt/60:.1f} min -> {out.name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--angles", type=float, nargs="*",
                    default=list(am.SWEEP_ANGLES_DEG))
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()

    angles = sorted(args.angles)
    print(f"sweep: {len(angles)} angles, {args.workers} parallel", flush=True)
    t0 = time.time()
    ok = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, a): a for a in angles}
        for fut in as_completed(futures):
            a = futures[fut]
            try:
                msg = fut.result()
                ok += 1
            except Exception as exc:          # noqa: BLE001
                msg = f"{a:+.0f} deg: FAILED - {exc}"
            print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)
    print(f"done: {ok}/{len(angles)} in {(time.time()-t0)/60:.1f} min",
          flush=True)
    return 0 if ok == len(angles) else 1


if __name__ == "__main__":
    raise SystemExit(main())
