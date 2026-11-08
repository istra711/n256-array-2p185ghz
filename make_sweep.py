"""Write one project per beam-steering angle (n256 sweep).

Usage::

    python make_sweep.py
"""

from __future__ import annotations

import json
from pathlib import Path

import array_model as am

HERE = Path(__file__).resolve().parent


def project_path(theta_deg: float) -> Path:
    return HERE / f"scan_{am.sweep_tag(theta_deg)}_2p2ghz.fcsim.json"


def write_project(theta_deg: float) -> Path:
    tag = am.sweep_tag(theta_deg)
    data = am.project_dict(f"scan_{tag}_2p2ghz", "scan",
                           theta_deg=float(theta_deg))
    path = project_path(theta_deg)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def main() -> int:
    for a in am.SWEEP_ANGLES_DEG:
        p = write_project(a)
        ph = am.scan_phases_deg(a)
        print(f"  theta {a:+6.1f} deg -> phase step {ph[2]-ph[1]:+7.2f} deg/px "
              f"({p.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
