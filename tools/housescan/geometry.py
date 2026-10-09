"""2D plan geometry: project walls to XZ, snap to dominant axes, merge shared walls,
build room polygons. Phase 3 — not implemented yet (tests are xfail-strict).
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon

from .schema import Room, Scan, Surface

Point = tuple[float, float]  # (x, z) in meters


@dataclass(frozen=True)
class Segment:
    """A wall in plan view. ``source_ids`` lists every RoomPlan wall merged into it."""

    start: Point
    end: Point
    source_ids: tuple[str, ...]
    height: float = 0.0


def wall_segment(wall: Surface) -> Segment:
    """Endpoints = center ± (width/2 · local X axis), projected onto XZ."""
    raise NotImplementedError


def project_walls(scan: Scan) -> list[Segment]:
    """One Segment per wall across all rooms."""
    raise NotImplementedError


def snap_to_axes(segments: list[Segment], tolerance_deg: float = 2.0) -> list[Segment]:
    """Rotate each segment about its midpoint onto the nearest dominant axis if within tolerance."""
    raise NotImplementedError


def merge_collinear(segments: list[Segment], offset_tol: float = 0.05,
                    angle_tol_deg: float = 2.0) -> list[Segment]:
    """Merge collinear, overlapping segments (e.g. the two faces of a shared wall)."""
    raise NotImplementedError


def room_polygon(room: Room) -> Polygon:
    """Room outline from ``floor_polygon``, else reconstructed from its wall loop."""
    raise NotImplementedError
