"""Geometry, mesh and project factory for the n256 (2.185 GHz) 4x4 array.

Single source of truth for the full-wave follow-up of the sizing study:
the same board carries a single element (reference), an embedded element
(port P6 driven) and a fully driven 4x4 broadside array.

Drawing unit: mm (as in the VisualopenEMS projects).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# frequency plan
# ---------------------------------------------------------------------------

F0_HZ = 2.185e9              # n256 receive band centre (2170..2200 MHz)
F_START_HZ = 2.00e9          # mesh band; fc = 200 MHz keeps the pulse short
F_STOP_HZ = 2.40e9
FC_HZ = 0.5 * (F_STOP_HZ - F_START_HZ)

NF2FF_FREQS_HZ = [2.170e9, 2.180e9, 2.185e9, 2.195e9, 2.200e9]
NF2FF_THETA_STEPS = 91       # 0..180 deg in 2 deg steps
NF2FF_PHI_STEPS = 181        # 0..360 deg in 2 deg steps
END_CRITERIA = 1e-4
MAX_TIMESTEPS = 40000

C0 = 299792458.0
LAMBDA0_MM = C0 / F0_HZ * 1e3

# ---------------------------------------------------------------------------
# substrate (Rogers RO4003C, 60 mil)
# ---------------------------------------------------------------------------

SUBSTRATE_NAME = "ro4003c"
SUBSTRATE_EPS_R = 3.55
SUBSTRATE_TAND = 0.0027
SUBSTRATE_H_MM = 1.524

# ---------------------------------------------------------------------------
# element and array
# ---------------------------------------------------------------------------

PATCH_W_MM = 45.5            # radiating edge (y)
PATCH_L_MM = 33.0            # resonant length (x), final tuning
PATCH_L_HAMMERSTAD_MM = 36.0
FEED_INSET_MM = 0.30 * PATCH_L_MM    # 9.9 mm for 50 ohm

N_X = 4
N_Y = 4
PITCH_MM = LAMBDA0_MM / 2.0          # 68.6 mm
BOARD_MM = 340.0                     # aperture 274 mm + 0.2 lambda margin

PORT_R_OHM = 50.0
COPPER_UM = 35.0

VARIANTS = ("element", "embedded", "broadside", "scan")

#: beam steering angles (deg, E plane) for the full-wave sweep animation
SWEEP_ANGLES_DEG = [-45.0, -30.0, -15.0, 0.0, 15.0, 30.0, 45.0]


def sweep_tag(theta_deg: float) -> str:
    a = int(round(theta_deg))
    if a < 0:
        return f"m{abs(a):02d}"
    if a > 0:
        return f"p{a:02d}"
    return "000"


def scan_phases_deg(theta_deg: float, phi_deg: float = 0.0) -> dict[int, float]:
    """Progressive element phases for a beam at (theta, phi).

    openEMS uses exp(+j*omega*t); a wave travelling in +x carries exp(-j*k*x),
    so the element at x_n must lead by -k0*x_n*sin(theta).  Verified by
    simulation in the 77 GHz study.
    """
    th = math.radians(theta_deg)
    ph = math.radians(phi_deg)
    phases: dict[int, float] = {}
    for j in range(N_Y):
        for i in range(N_X):
            x, y = element_xy(i, j)
            phase = (-360.0 / LAMBDA0_MM
                     * (x * math.sin(th) * math.cos(ph)
                        + y * math.sin(th) * math.sin(ph)))
            phases[port_number(i, j)] = phase
    return phases

# ---------------------------------------------------------------------------
# mesh, boundary, NF2FF, dumps
# ---------------------------------------------------------------------------

AIR_MARGIN_MM = [45.0, 45.0, 45.0, 45.0, 25.0, 120.0]

NF2FF_START_MM = [-190.0, -190.0, -20.0]
NF2FF_STOP_MM = [190.0, 190.0, 110.0]
NF2FF_CENTER_MM = [0.0, 0.0, SUBSTRATE_H_MM / 2.0]

DUMPS = [
    {"name": "E_xz", "quantity": "E",
     "start": [-200.0, 0.0, -30.0], "stop": [200.0, 0.0, 120.0]},
    {"name": "E_near", "quantity": "E",
     "start": [-200.0, -200.0, 20.0], "stop": [200.0, 200.0, 20.0]},
]


def substrate_kappa() -> float:
    """Conductivity equivalent to the dielectric loss tangent at f0."""
    eps0 = 8.8541878128e-12
    return 2.0 * math.pi * F0_HZ * eps0 * SUBSTRATE_EPS_R * SUBSTRATE_TAND


def patch_eps_eff(w_mm: float = PATCH_W_MM) -> float:
    h = SUBSTRATE_H_MM
    er = SUBSTRATE_EPS_R
    return (er + 1.0) / 2.0 + (er - 1.0) / 2.0 * (1.0 + 12.0 * h / w_mm) ** -0.5


def patch_length(eps_eff: float | None = None) -> float:
    """Hammerstad resonant length for the stored patch width."""
    h = SUBSTRATE_H_MM
    w = PATCH_W_MM
    er = SUBSTRATE_EPS_R
    ee = eps_eff if eps_eff is not None else patch_eps_eff(w)
    dl = (0.412 * h * (ee + 0.3) * (w / h + 0.264)
          / ((ee - 0.258) * (w / h + 0.8)))
    return C0 / (2.0 * F0_HZ * math.sqrt(ee)) * 1e3 - 2.0 * dl


# ---------------------------------------------------------------------------
# element placement
# ---------------------------------------------------------------------------

def element_xy(i: int, j: int) -> tuple[float, float]:
    return ((i - (N_X - 1) / 2.0) * PITCH_MM,
            (j - (N_Y - 1) / 2.0) * PITCH_MM)


def port_number(i: int, j: int) -> int:
    return j * N_X + i + 1


def port_xy(n: int) -> tuple[float, float]:
    i = (n - 1) % N_X
    j = (n - 1) // N_X
    x, y = element_xy(i, j)
    return x - PATCH_L_MM / 2.0 + FEED_INSET_MM, y


def patch_rect(i: int, j: int) -> tuple[float, float, float, float]:
    xc, yc = element_xy(i, j)
    return (xc - PATCH_L_MM / 2.0, yc - PATCH_W_MM / 2.0,
            xc + PATCH_L_MM / 2.0, yc + PATCH_W_MM / 2.0)


# ---------------------------------------------------------------------------
# project dictionary
# ---------------------------------------------------------------------------

def _mesh_dict() -> dict[str, Any]:
    """Mesh for 2.12..2.25 GHz on a 340 mm board.

    max 8 mm keeps air below lambda/17; 2.5 mm at metal edges resolves the
    36 mm patch with ~14 cells; 0.35 mm in z gives four cells through the
    1.524 mm laminate.
    """
    return {
        "preset": "high",
        "drawing_unit": "mm",
        "start_frequency": F_START_HZ,
        "stop_frequency": F_STOP_HZ,
        "target_frequency": F0_HZ,
        "refined_cellsize": 2.5,
        "min_cellsize": 1.5,
        "max_cellsize": 8.0,
        "min_cellsize_z": 0.40,
        "cells_per_wavelength": 20.0,
        "max_grading_ratio": 1.6,
        "smooth_metal_edge": "one_third_two_thirds",
        "use_circle_detection": False,
        "use_arc_detection": False,
        "handle_closely_placed_edges": True,
        "num_lines": 5,
        "dirs": "xyz",
        "align_coordinates": True,
        "diagnose_cell_sources": True,
        "manual_mesh_lines": None,
        "manual_mesh_lines_removed": None,
        "mesh_repairs": None,
        "enforce_min_cellsize": False,
        "accepted_cells": None,
        "add_graded_mesh_lines_at_material_transitions": True,
        "coord_system": "cartesian",
        "excitation": "gauss",
        "excitation_file": "",
    }


def _port_dict(n: int, x: float, y: float, excite: bool,
               phase_deg: float = 0.0) -> dict[str, Any]:
    return {
        "name": f"P{n}",
        "type": "lumped",
        "start": [round(x, 6), round(y, 6), 0.0],
        "stop": [round(x, 6), round(y, 6), SUBSTRATE_H_MM],
        "resistance": PORT_R_OHM,
        "inductance": 0.0,
        "capacitance": 0.0,
        "direction": "z",
        "excite_port": bool(excite),
        "excite_phase_deg": float(phase_deg),
        "active": True,
        "prop_direction": "",
        "exc_direction": "",
        "mesh_dirs": "xy",
        "metal_edge_res": None,
        "lumped_width": "line",
        "metal": "",
        "wg_a": 0.0,
        "wg_b": 0.0,
        "wg_mode": "TE10",
        "reverse": False,
    }


def _dump_dict(d: dict[str, str]) -> dict[str, Any]:
    return {
        "name": d["name"],
        "quantity": d["quantity"],
        "start": list(d["start"]),
        "stop": list(d["stop"]),
        "frequency_domain": True,
        "frequency": F0_HZ,
        "sub_sampling": [1, 1, 1],
        "enabled": True,
        "file_type": 1,
        "dump_mode": 1,
        "frequencies": None,
    }


def _primitives(variant: str) -> list[dict[str, Any]]:
    half = BOARD_MM / 2.0
    prims = [
        {"kind": "box", "name": "substrate", "material": SUBSTRATE_NAME,
         "priority": 10, "start": [-half, -half, 0.0],
         "stop": [half, half, SUBSTRATE_H_MM], "edges2grid": ""},
        {"kind": "box", "name": "ground", "material": "copper",
         "priority": 100, "start": [-half, -half, 0.0],
         "stop": [half, half, 0.0], "edges2grid": "xy"},
    ]
    if variant == "element":
        patches = [(1, 1)]          # inner element, board centre
    else:
        patches = [(i, j) for j in range(N_Y) for i in range(N_X)]
    for i, j in patches:
        if variant == "element":
            x0, y0 = -PATCH_L_MM / 2.0, -PATCH_W_MM / 2.0
            x1, y1 = PATCH_L_MM / 2.0, PATCH_W_MM / 2.0
            tag = "patch"
        else:
            x0, y0, x1, y1 = patch_rect(i, j)
            tag = f"patch_{j * N_X + i + 1:02d}"
        prims.append({"kind": "box", "name": tag, "material": "copper",
                      "priority": 100,
                      "start": [round(x0, 6), round(y0, 6), SUBSTRATE_H_MM],
                      "stop": [round(x1, 6), round(y1, 6), SUBSTRATE_H_MM],
                      "edges2grid": "xy"})
    return prims


def _ports(variant: str, theta_deg: float | None = None) -> list[dict[str, Any]]:
    if variant == "element":
        return [_port_dict(1, -PATCH_L_MM / 2.0 + FEED_INSET_MM, 0.0, True)]
    if variant == "scan":
        if theta_deg is None:
            raise ValueError("variant 'scan' needs theta_deg")
        phases = scan_phases_deg(theta_deg)
    else:
        phases = {}
    ports = []
    for j in range(N_Y):
        for i in range(N_X):
            n = port_number(i, j)
            x, y = port_xy(n)
            if variant in ("broadside", "scan"):
                excite, phase = True, phases.get(n, 0.0)
            else:
                excite = variant == "embedded" and n == 6
                phase = 0.0
            ports.append(_port_dict(n, x, y, excite, phase))
    return ports


def _notes(variant: str, theta_deg: float | None = None) -> str:
    common = (
        f"4x4 patch array, 3GPP n256 (2170-2200 MHz), RO4003C "
        f"(h={SUBSTRATE_H_MM} mm, eps_r={SUBSTRATE_EPS_R}, "
        f"tan_d={SUBSTRATE_TAND}); patch {PATCH_L_MM:.2f} x {PATCH_W_MM:.2f} mm "
        f"(L along x), pitch {PITCH_MM:.2f} mm = lambda0/2, board "
        f"{BOARD_MM:g} x {BOARD_MM:g} mm, probe feed {FEED_INSET_MM:.2f} mm "
        f"inset, 50 ohm lumped ports."
    )
    extra = {
        "element": " Single patch at the board centre (isolated reference).",
        "embedded": (" 16 patches, only P6 excited - embedded element pattern "
                     "and coupling column S*n6."),
        "broadside": (" 16 ports excited in phase - 4x4 broadside pattern "
                      "including mutual coupling."),
        "scan": (" 16 ports with progressive phase for a beam steered to "
                 f"theta={theta_deg:g} deg (E plane)."),
    }[variant]
    return common + extra


def _gerber_block(half: float) -> dict[str, Any]:
    return {"enabled": False, "edge_mm": half, "margin_mm": 2.0,
            "layers": [], "filename": ""}


def _kicad_block(half: float) -> dict[str, Any]:
    return {"enabled": False, "board_width_mm": 2 * half,
            "board_height_mm": 2 * half, "thickness_mm": SUBSTRATE_H_MM,
            "filename": ""}


def project_dict(name: str, variant: str,
                 theta_deg: float | None = None) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}")
    if variant == "scan" and theta_deg is None:
        raise ValueError("variant 'scan' needs theta_deg")
    return {
        "name": name,
        "version": 1,
        "geometry_files": [],
        "materials": [
            {"name": "copper", "kind": "pec", "epsilon": 1.0,
             "permeability": 1.0, "kappa": 0.0, "tand": 0.0,
             "color": [0.85, 0.55, 0.2, 1.0]},
            {"name": SUBSTRATE_NAME, "kind": "dielectric",
             "epsilon": SUBSTRATE_EPS_R, "permeability": 1.0,
             "kappa": round(substrate_kappa(), 12),
             "tand": SUBSTRATE_TAND, "color": [0.2, 0.5, 0.85, 0.6]},
        ],
        "assignments": [],
        "ports": _ports(variant, theta_deg),
        "dumps": [_dump_dict(d) for d in DUMPS],
        "nf2ff": {
            "enabled": True, "box_mode": "manual",
            "start": list(NF2FF_START_MM), "stop": list(NF2FF_STOP_MM),
            "center": list(NF2FF_CENTER_MM), "radius": 1.0,
            "frequencies": list(NF2FF_FREQS_HZ), "freq_mode": "list",
            "freq_count": len(NF2FF_FREQS_HZ),
            "theta_steps": NF2FF_THETA_STEPS, "phi_steps": NF2FF_PHI_STEPS,
        },
        "mesh": _mesh_dict(),
        "boundary": {
            "xmin": "PML", "xmax": "PML", "ymin": "PML", "ymax": "PML",
            "zmin": "PML", "zmax": "PML", "pml_size": 8,
            "air_margin": list(AIR_MARGIN_MM),
        },
        "sim": {
            "end_criteria": END_CRITERIA, "max_timesteps": MAX_TIMESTEPS,
            "max_time": None, "nf2ff_enabled": True,
            "field_dumps_enabled": True, "num_threads": 0, "output_dir": "",
            "antenna_mode": False, "antenna_pml_lambda": 0.5,
            "antenna_nf2ff_lambda": 0.5, "antenna_cells_per_wavelength": 15.0,
            "verbose": 2, "engine": "", "setup_only": False, "cleanup": True,
            "disable_dumps": False, "dump_statistics": False,
            "debug_material": False, "debug_pec": False, "debug_boxes": False,
            "debug_operator": False, "debug_csx": False,
            "show_probe_discretization": False, "legacy_hdf5_dumps": False,
            "over_sampling": None, "time_step_factor": None,
            "time_step_method": None, "cell_constant_material": False,
        },
        "mesh2freecad": {"export_step": False, "fcstd_object_type": "mesh",
                         "voxel_grid": True, "voxel_grid_mode": "all",
                         "include_sheets": True, "export_ports": True,
                         "keep_temp": False},
        "gerber": _gerber_block(BOARD_MM / 2.0),
        "kicad": _kicad_block(BOARD_MM / 2.0),
        "cst": {"source": "", "enabled": False},
        "notes": _notes(variant, theta_deg),
        "primitives": _primitives(variant),
    }


def summary() -> str:
    return (
        "n256 4x4 patch array, 2.185 GHz (3GPP n256 receive band)\n"
        f"  substrate : RO4003C h={SUBSTRATE_H_MM} mm, eps_r={SUBSTRATE_EPS_R}, "
        f"tan_d={SUBSTRATE_TAND}\n"
        f"  lambda0   : {LAMBDA0_MM:.1f} mm -> pitch {PITCH_MM:.2f} mm\n"
        f"  patch     : L={PATCH_L_MM:.2f} mm, W={PATCH_W_MM:.2f} mm, "
        f"eps_eff={patch_eps_eff():.3f}\n"
        f"  feed      : probe, inset {FEED_INSET_MM:.2f} mm\n"
        f"  array     : 4x4, aperture {4 * PITCH_MM:.1f} mm, board "
        f"{BOARD_MM:g} mm\n"
    )
