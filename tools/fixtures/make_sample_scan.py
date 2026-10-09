"""Regenerate sample_scan.json (hand-made 2-room fixture).

Layout (plan view, X right, Z down), meters, Y up, floor at y=0, ceiling 2.4:

    Kitchen       x 0.00..4.00, z 0..3   floor_polygon given
    Living Room   x 4.01..9.00, z 0..3   floor_polygon null (forces wall-loop fallback)

The shared wall appears twice: Kitchen's east wall at x=4.00 and Living Room's
west wall at x≈4.01, rotated 0.8° (inside the 2° snap tolerance) to mimic drift.
One door sits in the shared wall (owned by Kitchen); one window in the Living
Room's north wall.

Run: python tools/fixtures/make_sample_scan.py
"""

import json
import math
from pathlib import Path

H = 2.4


def pose(center, direction):
    """Column-major 4x4: local X along `direction` (XZ), Y up, Z = X × Y."""
    dx, dz = direction
    n = math.hypot(dx, dz)
    dx, dz = dx / n, dz / n
    x = (dx, 0.0, dz)
    y = (0.0, 1.0, 0.0)
    z = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    cols = [(*x, 0.0), (*y, 0.0), (*z, 0.0), (*center, 1.0)]
    return [round(v, 6) + 0.0 for col in cols for v in col]


def wall(wid, a, b, confidence="high"):
    (x1, z1), (x2, z2) = a, b
    width = math.hypot(x2 - x1, z2 - z1)
    return {
        "id": wid,
        "transform": pose(((x1 + x2) / 2, H / 2, (z1 + z2) / 2), (x2 - x1, z2 - z1)),
        "dimensions": [round(width, 6), H, 0.0],
        "confidence": confidence,
    }


def rotated(a, b, deg):
    """Rotate segment a-b about its midpoint by `deg` in the XZ plane."""
    mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))

    def r(p):
        px, pz = p[0] - mx, p[1] - mz
        return (mx + c * px - s * pz, mz + s * px + c * pz)

    return r(a), r(b)


K = "0A1B2C3D-0000-4000-8000-0000000000"  # kitchen UUID prefix
L = "0A1B2C3D-0000-4000-8000-1000000000"  # living room UUID prefix

kitchen_walls = [
    wall(K + "01", (0, 0), (4, 0)),            # south
    wall(K + "02", (4, 0), (4, 3)),            # east (shared)
    wall(K + "03", (4, 3), (0, 3)),            # north
    wall(K + "04", (0, 3), (0, 0), "low"),     # west, low confidence
]

lw_a, lw_b = rotated((4.01, 3), (4.01, 0), 0.8)
living_walls = [
    wall(L + "01", (4.01, 0), (9, 0)),         # south
    wall(L + "02", (9, 0), (9, 3)),            # east
    wall(L + "03", (9, 3), (4.01, 3)),         # north
    wall(L + "04", lw_a, lw_b, "medium"),      # west (shared, drifted 0.8°)
]

door = {
    "id": K + "D1",
    "parent_wall_id": K + "02",
    "transform": pose((4.0, 1.0, 1.5), (0, 1)),
    "dimensions": [0.9, 2.0, 0.0],
    "is_open": True,
    "confidence": "high",
}

window = {
    "id": L + "W1",
    "parent_wall_id": L + "03",
    "transform": pose((6.5, 1.5, 3.0), (-1, 0)),
    "dimensions": [1.2, 1.0, 0.0],
    "confidence": "high",
}

scan = {
    "schema_version": 1,
    "units": "m",
    "up_axis": "Y",
    "rooms": [
        {
            "id": "room-1",
            "name": "Kitchen",
            "section_label": "kitchen",
            "story": 0,
            "floor_polygon": [[0, 0], [4, 0], [4, 3], [0, 3]],
            "walls": kitchen_walls,
            "doors": [door],
            "windows": [],
            "openings": [],
        },
        {
            "id": "room-2",
            "name": "Living Room",
            "section_label": "livingRoom",
            "story": 0,
            "floor_polygon": None,
            "walls": living_walls,
            "doors": [],
            "windows": [window],
            "openings": [],
        },
    ],
}

out = Path(__file__).with_name("sample_scan.json")
out.write_text(json.dumps(scan, indent=2) + "\n")
print(f"wrote {out}")
