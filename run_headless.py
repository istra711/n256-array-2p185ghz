"""Generate and run the headless openEMS deck for a VisualopenEMS project.

The VisualopenEMS GUI itself writes ``<work>/project_run.py`` when a simulation
is started.  This wrapper does the same from the command line, so the array
study runs without opening the GUI.

Usage::

    python run_headless.py patch_element_77ghz.fcsim.json --mesh-only
    python run_headless.py patch_element_77ghz.fcsim.json
    python run_headless.py patch_array_4x4_broadside.fcsim.json --work work_array_broadside

``--mesh-only`` performs the CSX + easyMesh + FDTD setup and stops before the
time stepping.  Without it, the full FDTD run and the S-parameter / field /
NF2FF post-processing of the generated script are executed.

Requires the VisualopenEMS source tree (default
``C:\\path\\to\\FreeCAD_OpenEMS_GUI``, override with
``VISUALOPENEMS_ROOT``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_APP_ROOT = Path(r"C:\path\to\FreeCAD_OpenEMS_GUI")

#: default work directory per project (kept short - openEMS writes into it)
WORK_DIRS = {
    "patch_element_77ghz": "work_element",
    "patch_array_4x4_77ghz": "work_array_embedded",
    "patch_array_4x4_broadside": "work_array_broadside",
    "patch_array_4x4_scan30": "work_array_scan30",
}


def _app_root() -> Path:
    return Path(os.environ.get("VISUALOPENEMS_ROOT", DEFAULT_APP_ROOT))


def _project_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".fcsim.json"):
        return name[: -len(".fcsim.json")]
    return path.stem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "project",
        nargs="?",
        default="patch_array_4x4_77ghz.fcsim.json",
        help="project file (default: the embedded-element array)",
    )
    ap.add_argument("--work", default="", help="work directory (default: work_<variant>)")
    ap.add_argument("--mesh-only", action="store_true", help="setup only, no FDTD")
    ap.add_argument(
        "--max-timesteps",
        type=int,
        default=0,
        help="override the project's max_timesteps (smoke tests)",
    )
    ap.add_argument("--keep", action="store_true", help="keep an existing work directory")
    args = ap.parse_args()

    root = _app_root()
    if not (root / "app" / "models" / "project.py").is_file():
        raise SystemExit(
            f"VisualopenEMS source not found at {root}\n"
            "Set VISUALOPENEMS_ROOT to the FreeCAD_OpenEMS_GUI folder."
        )
    sys.path.insert(0, str(root))
    from app.models.project import Project
    from app.simulation.script_gen import generate_run_script

    project_path = Path(args.project)
    if not project_path.is_absolute():
        project_path = HERE / project_path
    if not project_path.is_file():
        raise SystemExit(f"project not found: {project_path}")

    stem = _project_stem(project_path)
    project = Project.load(project_path)
    if args.mesh_only:
        project.sim.setup_only = True
    if args.max_timesteps > 0:
        project.sim.max_timesteps = int(args.max_timesteps)

    work = Path(args.work) if args.work else HERE / WORK_DIRS.get(stem, f"work_{stem}")
    if work.exists() and not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    script = generate_run_script(project, project_path, work, project.primitives)
    print(f"generated: {script}")
    print(f"running  : {sys.executable} {script.name}  (cwd={work})")
    result = subprocess.run([sys.executable, str(script)], cwd=str(work))
    print(f"exit code: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
