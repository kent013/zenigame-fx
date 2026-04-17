from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def oanda_fixture() -> callable:
    def _load(name: str) -> Any:
        path = FIXTURE_DIR / "oanda" / name
        return json.loads(path.read_text())

    return _load
