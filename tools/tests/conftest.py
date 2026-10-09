from pathlib import Path

import pytest

from housescan.schema import load_scan

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def sample_path() -> Path:
    return FIXTURES / "sample_scan.json"


@pytest.fixture
def sample(sample_path):
    return load_scan(sample_path)
