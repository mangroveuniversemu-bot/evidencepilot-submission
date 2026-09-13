"""Shared fixtures. Tests import the packages straight from the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def maya_inputs() -> Path:
    return ROOT / "examples" / "maya_case" / "inputs"


@pytest.fixture(scope="session")
def adversarial() -> Path:
    return ROOT / "examples" / "adversarial"


@pytest.fixture(scope="session")
def maya_run(maya_inputs):
    from agent.researchops_agent import verify_package

    return verify_package(maya_inputs)
