"""Shared pytest fixture factories for all education subsystems.

Each subsystem's ``conftest.py`` can use these to build its template-DB
and per-test-copy fixtures without duplicating the boilerplate.

Usage (in a subsystem's conftest.py)::

    from education_system.platform.testing.conftest_helpers import (
        make_template_db_fixture,
        make_template_auth_db_fixture,
        make_db_path_fixture,
        make_auth_db_path_fixture,
        make_auth_fixture,
    )
    from education_system.foo_system.infrastructure.database.schema import init_db, seed_data
    from education_system.foo_system.infrastructure.database.db import set_db_path

    _template_db = make_template_db_fixture(init_db, seed_data)
    db_path = make_db_path_fixture(set_db_path, "test_foo.db")
"""

import shutil

import pytest

from education_system.platform.identity.auth.schema import (
    initialise_auth_db,
    seed_default_users as seed_auth_users,
)


def make_template_db_fixture(*init_funcs):
    """Create a session-scoped fixture that builds a template DB.

    Parameters
    ----------
    *init_funcs:
        Callables that accept a ``db_path`` string and initialise /
        seed the database (e.g. ``init_db``, ``seed_default_data``).
    """
    @pytest.fixture(scope="session")
    def _template_db(tmp_path_factory):
        path = str(tmp_path_factory.mktemp("template") / "template.db")
        for fn in init_funcs:
            fn(path)
        return path

    return _template_db


def make_template_auth_db_fixture():
    """Create a session-scoped fixture that builds a template auth DB."""
    @pytest.fixture(scope="session")
    def _template_auth_db(tmp_path_factory):
        path = str(tmp_path_factory.mktemp("template_auth") / "template_auth.db")
        initialise_auth_db(path)
        seed_auth_users(path)
        return path

    return _template_auth_db


def make_db_path_fixture(set_db_path_func, db_filename="test.db"):
    """Create a per-test fixture that copies the template DB.

    Parameters
    ----------
    set_db_path_func:
        The subsystem's ``set_db_path`` function used to point the
        connection layer at the test DB.
    db_filename:
        Name for the per-test copy.
    """
    @pytest.fixture
    def db_path(tmp_path, _template_db):
        path = str(tmp_path / db_filename)
        shutil.copy2(_template_db, path)
        set_db_path_func(path)
        yield path
        set_db_path_func(None)

    return db_path


def make_auth_db_path_fixture():
    """Create a per-test fixture that copies the template auth DB."""
    @pytest.fixture
    def auth_db_path(tmp_path, _template_auth_db):
        path = str(tmp_path / "test_auth.db")
        shutil.copy2(_template_auth_db, path)
        return path

    return auth_db_path


def make_auth_fixture(auth_class):
    """Create a fixture that instantiates an auth class with the test auth DB.

    Parameters
    ----------
    auth_class:
        Typically ``UserAuth`` from the subsystem's auth module.
    """
    @pytest.fixture
    def auth(auth_db_path):
        return auth_class(auth_db_path)

    return auth
