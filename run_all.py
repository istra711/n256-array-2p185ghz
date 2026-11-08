"""Run the n256 study end to end (projects, validation, FDTD, report)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable

PROJECTS = [
    ("patch_element_2p2ghz.fcsim.json", "work_patch_element_2p2ghz"),
    ("array_4x4_2p2ghz.fcsim.json", "work_array_4x4_2p2ghz"),
    ("array_4x4_broadside_2p2ghz.fcsim.json", "work_array_4x4_broadside_2p2ghz"),
]


def run(step: str, *args: str) -> None:
    print(f"\n=== {step} ===", flush=True)
    subprocess.run([PY, *args], cwd=str(HERE), check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-sim", action="store_true")
    args = ap.parse_args()

    if args.force or not (HERE / "patch_element_2p2ghz.fcsim.json").is_file():
        run("projects", "make_project.py")
    if args.force or not (HERE / "work_validate_patch_element_2p2ghz").is_dir():
        run("validation", "validate_project.py")

    if not args.no_sim:
        for proj, work in PROJECTS:
            if args.force or not (HERE / work / "nf2ff" / "nf2ff.json").is_file():
                run(f"FDTD {proj}", "run_headless.py", proj)

    if args.force or not (HERE / "docs" / "results.json").is_file():
        run("figures", "plot_results.py")
    run("report", "build_docs.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
