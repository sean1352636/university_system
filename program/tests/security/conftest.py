"""Fixtures for the independent security test suite.

These tests assert the fail-closed behaviour of security controls, so several
of them need to flip APP_ENV to a production value. The root conftest sets
APP_ENV=testing for the rest of the suite; here we provide a helper to run a
block as if in production without leaking that state to other tests.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest


@contextmanager
def _env(**overrides):
    saved = {k: os.environ.get(k) for k in overrides}
    try:
        for k, v in overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture
def as_production():
    """Run code inside the block with APP_ENV=production and no dev secrets."""
    def _factory(**extra):
        return _env(APP_ENV="production", **extra)

    return _factory


@pytest.fixture
def as_development():
    def _factory(**extra):
        return _env(APP_ENV="development", **extra)

    return _factory
