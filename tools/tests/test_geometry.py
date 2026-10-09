"""Spec tests for geometry.py (Phase 3).

Marked xfail(strict=True) while geometry.py is stubbed: CI stays green, and the
moment an implementation makes a test pass it XPASSes -> fails, reminding us to
remove the marker.
"""

import math

import pytest

from housescan import geometry
from housescan.geometry import Segment

pytestmark = pytest.mark.xfail(raises=NotImplementedError, strict=True,
                               reason="geometry.py not implemented (Phase 3)")

KITCHEN_EAST = "0A1B2C3D-0000-4000-8000-000000000002"
LIVING_WEST = "0A1B2C3D-0000-4000-8000-100000000004"


def _endpoints(seg):
    return sorted([tuple(round(c, 3) for c in seg.start), tuple(round(c, 3) for c in seg.end)])


def _angle_deg(seg):
    return math.degrees(math.atan2(seg.end[1] - seg.start[1], seg.end[0] - seg.start[0])) % 180


def test_wall_segment_endpoints(sample):
    south = sample.rooms[0].walls[0]
    seg = geometry.wall_segment(south)
    assert _endpoints(seg) == [(0.0, 0.0), (4.0, 0.0)]
    assert seg.source_ids == (south.id,)
    assert seg.height == pytest.approx(2.4)


def test_project_walls_one_per_wall(sample):
    segs = geometry.project_walls(sample)
    assert len(segs) == 8
    assert {s.source_ids[0] for s in segs} == {w.id for w in sample.all_walls()}


def test_snap_straightens_small_drift(sample):
    segs = geometry.snap_to_axes(geometry.project_walls(sample), tolerance_deg=2.0)
    west = next(s for s in segs if s.source_ids == (LIVING_WEST,))
    assert west.start[0] == pytest.approx(west.end[0], abs=1e-6)  # now vertical
    assert west.start[0] == pytest.approx(4.01, abs=1e-3)          # rotated about its midpoint


def test_snap_leaves_large_angles_alone():
    seg = Segment(start=(0.0, 0.0), end=(math.cos(math.radians(5)), math.sin(math.radians(5))),
                  source_ids=("x",))
    (out,) = geometry.snap_to_axes([seg], tolerance_deg=2.0)
    assert _angle_deg(out) == pytest.approx(5.0, abs=1e-6)


def test_merge_shared_wall(sample):
    segs = geometry.snap_to_axes(geometry.project_walls(sample))
    merged = geometry.merge_collinear(segs, offset_tol=0.05)
    shared = [s for s in merged if KITCHEN_EAST in s.source_ids]
    assert len(shared) == 1
    shared = shared[0]
    assert LIVING_WEST in shared.source_ids
    xs = (shared.start[0], shared.end[0])
    assert all(4.0 - 1e-6 <= x <= 4.01 + 1e-6 for x in xs)
    zs = sorted((shared.start[1], shared.end[1]))
    assert zs == pytest.approx([0.0, 3.0], abs=0.03)
    # Every original wall is accounted for exactly once.
    all_ids = [i for s in merged for i in s.source_ids]
    assert sorted(all_ids) == sorted(w.id for w in sample.all_walls())


def test_merge_does_not_join_parallel_walls_far_apart(sample):
    segs = geometry.project_walls(sample)
    merged = geometry.merge_collinear(segs, offset_tol=0.05)
    north_k = next(s for s in merged if "0A1B2C3D-0000-4000-8000-000000000003" in s.source_ids)
    assert "0A1B2C3D-0000-4000-8000-000000000001" not in north_k.source_ids


def test_room_polygon_from_floor(sample):
    poly = geometry.room_polygon(sample.rooms[0])
    assert poly.is_valid
    assert poly.area == pytest.approx(12.0, abs=1e-6)


def test_room_polygon_from_wall_loop(sample):
    living = sample.rooms[1]
    assert living.floor_polygon is None
    poly = geometry.room_polygon(living)
    assert poly.is_valid
    assert poly.area == pytest.approx((9.0 - 4.01) * 3.0, abs=0.1)
