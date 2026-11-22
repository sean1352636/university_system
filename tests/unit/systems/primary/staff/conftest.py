"""Every staff test runs in the primary sandbox (see ../conftest.py)."""

import pytest


@pytest.fixture(autouse=True)
def _sandbox(primary_sandbox):
    yield primary_sandbox
