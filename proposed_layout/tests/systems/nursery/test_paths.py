"""Tests for ``education_system.systems.nursery.infrastructure.paths``."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def paths_mod():
    from education_system.systems.nursery.infrastructure import paths
    return paths


def test_package_root_is_nursery_package(paths_mod):
    assert paths_mod.PACKAGE_ROOT.name == "nursery_system"
    assert paths_mod.PACKAGE_ROOT.is_dir()


def test_data_dir_default_under_package(paths_mod):
    assert paths_mod.DATA_DIR == (paths_mod.PACKAGE_ROOT / "data").resolve()


def test_nursery_db_lives_in_data_dir(paths_mod):
    assert paths_mod.NURSERY_DB == paths_mod.DATA_DIR / "nursery.db"


def test_pupils_and_staff_alias_the_nursery_db(paths_mod):
    assert paths_mod.PUPILS_DB == paths_mod.NURSERY_DB
    assert paths_mod.STAFF_DB == paths_mod.NURSERY_DB


def test_all_domain_dbs_share_the_nursery_file(paths_mod):
    """Every per-domain ``*_DB`` constant aliases to ``NURSERY_DB``."""
    nursery = paths_mod.NURSERY_DB
    aliases = [
        name
        for name in dir(paths_mod)
        if name.endswith("_DB") and name != "NURSERY_DB"
    ]
    assert aliases, "expected per-domain *_DB aliases to exist"
    for name in aliases:
        assert getattr(paths_mod, name) == nursery, name


def test_known_aliases_present(paths_mod):
    sentinels = [
        "POLICIES_DB", "GDPR_DB", "RECRUITMENT_DB", "COMPLAINTS_DB",
        "FEEDBACK_DB", "EXPENSE_CLAIMS_DB", "AUDIT_REPORTS_DB",
        "VISITORS_DB", "DBS_CHECKS_DB", "APPRAISALS_DB", "SETTINGS_DB",
    ]
    for name in sentinels:
        assert hasattr(paths_mod, name), name
        assert isinstance(getattr(paths_mod, name), Path), name


def test_ensure_directories_creates_data_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "data"
    monkeypatch.setenv("EDU_NURSERY_DATA_DIR", str(target))
    from education_system.systems.nursery.infrastructure import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.DATA_DIR == target.resolve()
        assert not target.exists()
        reloaded.ensure_directories()
        assert target.exists() and target.is_dir()
        # Calling again is a no-op.
        reloaded.ensure_directories()
        assert target.exists()
    finally:
        monkeypatch.delenv("EDU_NURSERY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)


def test_env_override_overrides_default(tmp_path, monkeypatch):
    override = tmp_path / "alt_data"
    monkeypatch.setenv("EDU_NURSERY_DATA_DIR", str(override))
    from education_system.systems.nursery.infrastructure import paths as paths_mod
    reloaded = importlib.reload(paths_mod)
    try:
        assert reloaded.DATA_DIR == override.resolve()
        assert reloaded.NURSERY_DB == override.resolve() / "nursery.db"
    finally:
        monkeypatch.delenv("EDU_NURSERY_DATA_DIR", raising=False)
        importlib.reload(paths_mod)
