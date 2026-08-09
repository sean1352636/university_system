"""Regression tests for the extracted authentication schema mixin."""

import threading

from education_system.systems.university.infrastructure.auth.facade_components.bootstrap.schema import (
    AuthBootstrapSchemaMixin,
)


def test_init_db_resolves_runtime_facade_class_without_global_userauth():
    class AuthFacade(AuthBootstrapSchemaMixin):
        _init_lock = threading.Lock()
        _db_initialized = False

        def __init__(self):
            self.calls = 0

        def _do_init_db(self):
            self.calls += 1

    auth = AuthFacade()
    auth._init_db()
    auth._init_db()

    assert auth.calls == 1
    assert AuthFacade._db_initialized is True
