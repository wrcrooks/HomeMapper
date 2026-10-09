"""Load and validate the simplified ``scan.json`` contract (CLAUDE.md §5).

Units are meters, world frame is RoomPlan/ARKit (Y up). Transforms are 4x4
column-major, so translation is elements 12..14 and the local X axis is 0..2.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_VERSION = 1
CONFIDENCE_LEVELS = ("high", "medium", "low")


class SchemaError(ValueError):
    """Raised when scan.json does not match the contract."""


@dataclass(frozen=True)
class Surface:
    """A RoomPlan surface: wall, door, window or opening."""

    id: str
    transform: np.ndarray  # (4, 4), row-major in memory (converted from column-major JSON)
    dimensions: tuple[float, float, float]  # width, height, depth
    confidence: str
    parent_wall_id: str | None = None
    is_open: bool | None = None

    @property
    def center(self) -> np.ndarray:
        return self.transform[:3, 3]

    @property
    def x_axis(self) -> np.ndarray:
        return self.transform[:3, 0]

    @property
    def width(self) -> float:
        return self.dimensions[0]

    @property
    def height(self) -> float:
        return self.dimensions[1]


@dataclass
class Room:
    id: str
    name: str
    section_label: str | None
    story: int
    floor_polygon: list[tuple[float, float]] | None
    walls: list[Surface] = field(default_factory=list)
    doors: list[Surface] = field(default_factory=list)
    windows: list[Surface] = field(default_factory=list)
    openings: list[Surface] = field(default_factory=list)


@dataclass
class Scan:
    schema_version: int
    units: str
    up_axis: str
    rooms: list[Room]

    def all_walls(self) -> list[Surface]:
        return [w for r in self.rooms for w in r.walls]


def _require(obj: dict, key: str, ctx: str) -> Any:
    if key not in obj:
        raise SchemaError(f"{ctx}: missing required key '{key}'")
    return obj[key]


def _parse_surface(raw: dict, ctx: str, kind: str) -> Surface:
    sid = _require(raw, "id", ctx)
    ctx = f"{ctx}[{sid}]"
    t = _require(raw, "transform", ctx)
    if not isinstance(t, list) or len(t) != 16:
        raise SchemaError(f"{ctx}: transform must be 16 floats, got {t!r:.60}")
    d = _require(raw, "dimensions", ctx)
    if not isinstance(d, list) or len(d) != 3:
        raise SchemaError(f"{ctx}: dimensions must be 3 floats")
    conf = _require(raw, "confidence", ctx)
    if conf not in CONFIDENCE_LEVELS:
        raise SchemaError(f"{ctx}: confidence must be one of {CONFIDENCE_LEVELS}, got {conf!r}")
    matrix = np.asarray(t, dtype=float).reshape(4, 4).T  # column-major -> row-major
    return Surface(
        id=sid,
        transform=matrix,
        dimensions=(float(d[0]), float(d[1]), float(d[2])),
        confidence=conf,
        parent_wall_id=raw.get("parent_wall_id") if kind != "walls" else None,
        is_open=raw.get("is_open") if kind == "doors" else None,
    )


def parse_scan(data: dict) -> Scan:
    version = _require(data, "schema_version", "scan")
    if version != SCHEMA_VERSION:
        raise SchemaError(f"unsupported schema_version {version!r} (expected {SCHEMA_VERSION})")
    units = _require(data, "units", "scan")
    if units != "m":
        raise SchemaError(f"units must be 'm', got {units!r}")
    up = _require(data, "up_axis", "scan")
    if up != "Y":
        raise SchemaError(f"up_axis must be 'Y', got {up!r}")

    rooms: list[Room] = []
    seen_ids: set[str] = set()
    for i, raw_room in enumerate(_require(data, "rooms", "scan")):
        ctx = f"rooms[{i}]"
        poly = raw_room.get("floor_polygon")
        if poly is not None:
            if len(poly) < 3 or any(len(p) != 2 for p in poly):
                raise SchemaError(f"{ctx}: floor_polygon must be >=3 [x, z] pairs or null")
            poly = [(float(x), float(z)) for x, z in poly]
        room = Room(
            id=_require(raw_room, "id", ctx),
            name=_require(raw_room, "name", ctx),
            section_label=raw_room.get("section_label"),
            story=int(raw_room.get("story", 0)),
            floor_polygon=poly,
        )
        for kind in ("walls", "doors", "windows", "openings"):
            surfaces = [_parse_surface(s, f"{ctx}.{kind}", kind) for s in raw_room.get(kind, [])]
            for s in surfaces:
                if s.id in seen_ids:
                    raise SchemaError(f"{ctx}.{kind}: duplicate surface id {s.id}")
                seen_ids.add(s.id)
            setattr(room, kind, surfaces)
        rooms.append(room)

    wall_ids = {w.id for r in rooms for w in r.walls}
    for r in rooms:
        for s in (*r.doors, *r.windows, *r.openings):
            if s.parent_wall_id is not None and s.parent_wall_id not in wall_ids:
                raise SchemaError(f"{s.id}: parent_wall_id {s.parent_wall_id} not found")

    return Scan(schema_version=version, units=units, up_axis=up, rooms=rooms)


def load_scan(path: str | Path) -> Scan:
    with open(path, encoding="utf-8") as f:
        return parse_scan(json.load(f))
