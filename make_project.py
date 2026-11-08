"""Write the VisualopenEMS projects of the n256 4x4 study.

Usage::

    python make_project.py
"""

from __future__ import annotations

import json
from pathlib import Path

import array_model as am

HERE = Path(__file__).resolve().parent

PROJECTS = {
    "element": "patch_element_2p2ghz",
    "embedded": "array_4x4_2p2ghz",
    "broadside": "array_4x4_broadside_2p2ghz",
}


def main() -> int:
    print(am.summary())
    for variant, stem in PROJECTS.items():
        data = am.project_dict(stem, variant)
        path = HERE / f"{stem}.fcsim.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  wrote {path.name}  ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
