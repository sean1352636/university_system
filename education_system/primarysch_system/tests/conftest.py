"""Shared fixtures for Primary School tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def fresh_data_dir(tmp_path, monkeypatch):
    """Redirect the primary data dir at a brand-new directory.

    Reloads ``core.paths`` so ``DATA_DIR`` / ``PUPILS_DB`` re-read the env
    override, and restores the default module state afterwards so downstream
    tests see the real package paths again.
    """
    import importlib

    target = tmp_path / "data"
    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(target))
    from education_system.primarysch_system.core import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        yield reloaded
    finally:
        monkeypatch.delenv("EDU_PRIMARY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
