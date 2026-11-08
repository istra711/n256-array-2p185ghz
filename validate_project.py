"""Validate a VisualopenEMS ``.fcsim.json`` project without running FDTD.

Loads the project through the real VisualopenEMS data model, builds the CSX
geometry and the easyMesh grid, prints a compact feasibility report and stores
the resulting grid lines in ``work_validate_<name>/grid_lines.json`` (used by
``plot_results.py`` for the mesh figure).

Usage::

    python validate_project.py                       # all four projects
    python validate_project.py patch_element_77ghz.fcsim.json

Requires the VisualopenEMS source tree (default
``C:\\path\\to\\FreeCAD_OpenEMS_GUI``, override with
``VISUALOPENEMS_ROOT``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_APP_ROOT = Path(r"C:\path\to\FreeCAD_OpenEMS_GUI")

INTERESTING = (
    "Cells ",
    "Cell size",
    "Courant limit",
    "Resolution",
    "Domain crossing",
    "Runtime penalty",
    "Critical cells",
    "Findings:",
    "WARNING",
    "ERROR",
    "[INFO]",
)

ALL_PROJECTS = [
    "patch_element_2p2ghz.fcsim.json",
    "array_4x4_2p2ghz.fcsim.json",
    "array_4x4_broadside_2p2ghz.fcsim.json",
]


def _app_root() -> Path:
    return Path(os.environ.get("VISUALOPENEMS_ROOT", DEFAULT_APP_ROOT))


def _import_app():
    root = _app_root()
    if not (root / "app" / "models" / "project.py").is_file():
        raise SystemExit(
            f"VisualopenEMS source not found at {root}\n"
            "Set VISUALOPENEMS_ROOT to the FreeCAD_OpenEMS_GUI folder."
        )
    sys.path.insert(0, str(root))
    from app.meshing.build_task import build_mesh_and_validate
    from app.models.project import Project

    return Project, build_mesh_and_validate


def _project_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".fcsim.json"):
        return name[: -len(".fcsim.json")]
    return path.stem


def validate(path: Path) -> bool:
    Project, build_mesh_and_validate = _import_app()
    print("=" * 78)
    print(f"Project: {path}")
    if not path.is_file():
        print("  MISSING")
        return False

    project = Project.load(path)
    print(f"  name        : {project.name}")
    print(f"  materials   : {', '.join(m.name for m in project.materials)}")
    excited = [p for p in project.ports if p.excite_port]
    print(
        f"  ports       : {len(project.ports)} total, "
        f"{len(excited)} excited"
        + (f" ({', '.join(p.name for p in excited)})"
           if len(excited) <= 4 else "")
    )
    print(f"  primitives  : {len(project.primitives or [])}")
    m = project.mesh
    print(
        f"  band        : {m.start_frequency/1e9:.3f} .. "
        f"{m.stop_frequency/1e9:.3f} GHz (f0={m.target_frequency/1e9:.3f} GHz)"
    )
    print(
        f"  mesh        : preset={m.preset}, min={m.min_cellsize} mm, "
        f"max={m.max_cellsize} mm, refined={m.refined_cellsize} mm, "
        f"min_z={m.min_cellsize_z} mm"
    )
    print(
        f"  nf2ff       : {len(project.nf2ff.frequencies)} freq(s), "
        f"{project.nf2ff.theta_steps} x {project.nf2ff.phi_steps} steps"
    )

    work = HERE / f"work_validate_{_project_stem(path)}"
    t0 = time.time()
    try:
        res = build_mesh_and_validate(project, project.primitives or [], work)
    except Exception as exc:  # noqa: BLE001
        print(f"  MESH BUILD FAILED: {type(exc).__name__}: {exc}")
        return False
    print(f"  mesh build  : OK in {time.time() - t0:.1f} s")

    grid = res.csx.GetGrid()
    nx = len(grid.GetLines("x")) - 1
    ny = len(grid.GetLines("y")) - 1
    nz = len(grid.GetLines("z")) - 1
    print(f"  grid        : {nx} x {ny} x {nz} = {nx * ny * nz:,} cells")
    lines_out = {}
    for axis in "xyz":
        lines = [float(v) for v in grid.GetLines(axis)]
        lines_out[axis] = lines
        print(
            f"    {axis}: {lines[0]:8.3f} .. {lines[-1]:8.3f} mm  "
            f"({len(lines)} lines, min cell "
            f"{min(b - a for a, b in zip(lines, lines[1:]))*1000:.1f} um)"
        )
    (work / "grid_lines.json").write_text(
        json.dumps(lines_out), encoding="utf-8")
    print(f"  grid lines  : {work / 'grid_lines.json'}")

    print("  report:")
    for line in res.lines:
        if any(key in line for key in INTERESTING):
            print("    " + line.strip())
    print("  RESULT: PASS")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("projects", nargs="*", help="project file(s)")
    args = ap.parse_args()
    paths = [Path(p) for p in args.projects] if args.projects else [
        HERE / n for n in ALL_PROJECTS
    ]
    ok = True
    for p in paths:
        ok = validate(p if p.is_absolute() else HERE / p) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
