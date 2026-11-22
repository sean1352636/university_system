"""Tests for the primary section of ``education_system.paths``."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def paths_mod():
    from education_system import paths
    return paths


def test_package_root_is_primary_package(paths_mod):
    assert paths_mod.PRIMARY_PACKAGE_ROOT.name == "primary"
    assert paths_mod.PRIMARY_PACKAGE_ROOT.is_dir()


def test_data_dir_default_under_var(paths_mod):
    # Runtime state lives under <repo>/var (ADR 0018), not inside the package.
    assert paths_mod.PRIMARY_DATA_DIR == (
        paths_mod.VAR_DIR / "data" / "primary"
    ).resolve()


def test_pupils_db_lives_in_data_dir(paths_mod):
    assert paths_mod.PRIMARY_PUPILS_DB == paths_mod.PRIMARY_DATA_DIR / "primary.db"


def test_all_domain_dbs_share_the_pupils_file(paths_mod):
    """Every per-domain ``*_DB`` constant aliases to ``PUPILS_DB``."""
    pupils = paths_mod.PRIMARY_PUPILS_DB
    aliases = [
        name
        for name in dir(paths_mod)
        if name.startswith("PRIMARY_") and name.endswith("_DB")
        and name != "PRIMARY_PUPILS_DB"
    ]
    assert aliases, "expected per-domain *_DB aliases to exist"
    for name in aliases:
        assert getattr(paths_mod, name) == pupils, name


def test_known_aliases_present(paths_mod):
    sentinels = [
        "PRIMARY_ADMISSIONS_DB", "PRIMARY_ENROLMENT_DB", "PRIMARY_ONBOARDING_DB", "PRIMARY_ACADEMIC_YEAR_DB",
        "PRIMARY_STAFF_DB", "PRIMARY_STAFF_HR_DB", "PRIMARY_FEES_DB", "PRIMARY_GDPR_DB", "PRIMARY_SETTINGS_DB",
        "PRIMARY_GOVERNANCE_DB", "PRIMARY_POLICIES_DB", "PRIMARY_TODO_DB",
    ]
    for name in sentinels:
        assert hasattr(paths_mod, name), name
        assert isinstance(getattr(paths_mod, name), Path), name


def test_ensure_directories_creates_data_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "data"
    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(target))
    from education_system import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.PRIMARY_DATA_DIR == target.resolve()
        assert not target.exists()
        reloaded.ensure_primary_directories()
        assert target.exists() and target.is_dir()
        # Calling again is a no-op.
        reloaded.ensure_primary_directories()
        assert target.exists()
    finally:
        monkeypatch.delenv("EDU_PRIMARY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)


def test_env_override_overrides_default(tmp_path, monkeypatch):
    override = tmp_path / "alt_data"
    monkeypatch.setenv("EDU_PRIMARY_DATA_DIR", str(override))
    from education_system import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.PRIMARY_DATA_DIR == override.resolve()
        assert reloaded.PRIMARY_PUPILS_DB == override.resolve() / "primary.db"
    finally:
        monkeypatch.delenv("EDU_PRIMARY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
