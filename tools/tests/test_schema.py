import json

import numpy as np
import pytest

from housescan.schema import SchemaError, parse_scan


def test_fixture_loads(sample):
    assert [r.name for r in sample.rooms] == ["Kitchen", "Living Room"]
    assert len(sample.all_walls()) == 8
    kitchen, living = sample.rooms
    assert kitchen.floor_polygon is not None
    assert living.floor_polygon is None
    assert len(kitchen.doors) == 1 and kitchen.doors[0].is_open is True
    assert len(living.windows) == 1


def test_transform_is_column_major(sample):
    # Kitchen east wall: center (4, 1.2, 1.5), local X along +Z.
    east = sample.rooms[0].walls[1]
    np.testing.assert_allclose(east.center, [4.0, 1.2, 1.5])
    np.testing.assert_allclose(east.x_axis, [0.0, 0.0, 1.0], atol=1e-9)
    assert east.width == pytest.approx(3.0)


def test_low_confidence_preserved(sample):
    assert sample.rooms[0].walls[3].confidence == "low"


@pytest.mark.parametrize(
    "mutate, msg",
    [
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: d.update(units="ft"), "units"),
        (lambda d: d["rooms"][0]["walls"][0].update(transform=[0] * 15), "16 floats"),
        (lambda d: d["rooms"][0]["walls"][0].update(confidence="meh"), "confidence"),
        (lambda d: d["rooms"][0]["doors"][0].update(parent_wall_id="nope"), "parent_wall_id"),
        (lambda d: d["rooms"][1]["walls"][0].update(id=d["rooms"][0]["walls"][0]["id"]), "duplicate"),
    ],
)
def test_invalid_rejected(sample_path, mutate, msg):
    data = json.loads(sample_path.read_text())
    mutate(data)
    with pytest.raises(SchemaError, match=msg):
        parse_scan(data)
