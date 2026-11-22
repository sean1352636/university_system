"""The canonical system list drives API role scoping, so every system must be in it."""
import pytest

from education_system.platform.identity.auth.role_manager import RoleManager
from education_system.platform.identity.auth.schema import initialise_auth_db
from education_system.platform.kernel.core.system_keys import (
    CANONICAL_SYSTEMS,
    canonical_system_key,
    is_known_system,
)
from education_system.systems import registry


def test_canonical_list_matches_the_system_registry():
    assert set(CANONICAL_SYSTEMS) == {manifest.key for manifest in registry.all_manifests()}


@pytest.mark.parametrize("alias, key", [
    ("fecollege", "fe_college"),
    ("fe-college", "fe_college"),
    ("apprentice", "apprenticeships"),
    ("apprenticeship", "apprenticeships"),
    ("sixthform", "sixth_form"),
    ("school", "secondary"),
])
def test_aliases(alias, key):
    assert canonical_system_key(alias) == key
    assert is_known_system(alias)


def test_removed_systems_stay_unknown():
    assert not is_known_system("playgroup")
    assert not is_known_system("higherapprenticeship")


class TestRoleLookupWithLegacyRows:
    @pytest.fixture
    def manager(self, tmp_path):
        path = str(tmp_path / "auth.db")
        initialise_auth_db(path)
        manager = RoleManager(path)
        conn = manager._conn()
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES ('legacy', 'x'), ('both', 'x')"
        )
        conn.execute(
            "INSERT INTO user_systems (user_id, system_key, role) "
            "SELECT id, 'fecollege', 'staff' FROM users WHERE username IN ('legacy', 'both')"
        )
        conn.execute(
            "INSERT INTO user_systems (user_id, system_key, role) "
            "SELECT id, 'fe_college', 'admin' FROM users WHERE username = 'both'"
        )
        conn.commit()
        self.ids = dict(conn.execute("SELECT username, id FROM users").fetchall())
        conn.close()
        return manager

    def test_legacy_row_is_found_by_either_key(self, manager):
        uid = self.ids["legacy"]
        assert manager.get_user_role_for_system(uid, "fecollege") == "staff"
        assert manager.get_user_role_for_system(uid, "fe_college") == "staff"

    def test_canonical_row_wins(self, manager):
        assert manager.get_user_role_for_system(self.ids["both"], "fecollege") == "admin"

    def test_no_row_for_another_system(self, manager):
        assert manager.get_user_role_for_system(self.ids["legacy"], "university") is None
