"""Shared test fixtures for cross-system integration tests."""

import os
import shutil
import sys
from pathlib import Path

import pytest

# conftest.py -> platform -> tests -> <repo root>
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(scope="session")
def _template_auth_db(tmp_path_factory):
    """Create a seeded template auth DB once per session."""
    from education_system.platform.identity.auth.schema import initialise_auth_db, seed_default_users
    path = str(tmp_path_factory.mktemp("template") / "template_auth.db")
    initialise_auth_db(path)
    seed_default_users(path)
    return path


@pytest.fixture
def shared_auth_db(tmp_path, _template_auth_db):
    """Copy the template auth DB for each test (fast file copy)."""
    db_path = str(tmp_path / "test_auth.db")
    shutil.copy2(_template_auth_db, db_path)
    return db_path
