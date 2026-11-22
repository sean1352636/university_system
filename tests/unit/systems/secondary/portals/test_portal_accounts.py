"""Parent and linked portal logins (domain.portal_accounts) on temporary databases."""

from __future__ import annotations

import re

import pytest

from education_system.systems.secondary import SYSTEM_KEY
from education_system.systems.secondary.modules.portals.domain import portal as PT
from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
from education_system.systems.secondary.modules.pupils.domain import pupil_accounts as PAC
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="pt_teach", role="teacher")


@pytest.fixture
def env(tmp_path):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    ua = UserAuth(db_path=str(tmp_path / "auth.db"))
    for user, pw, name, mail, sysrole in (
            ("pt_teach", "Teach!ng-Pass-123", "Ms Maths", "maths@school.org", (SYSTEM_KEY, "teacher")),
            ("student2", "student1234", "School Student", "student@school.local",
             (SYSTEM_KEY, "student")),
            ("parent2", "parent1234", "School Parent", "parent@school.local",
             (SYSTEM_KEY, "parent")),
            ("elsewhere", "Elsewhere-Pass-1", "Other Parent", "dad@home.org", ("primary", "parent"))):
        ua.provision_user(user, pw, display_name=name, email=mail, systems=[sysrole])
    pupils = [P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Portal", "date_of_birth": "2013-01-15",
        "gender": "Female", "year_group": 9, "admission_date": "2023-09-01"}, actor=ADMIN)
        for n in ("Ava", "Ben")]
    yield {"ava": pupils[0], "ben": pupils[1], "path": tmp_path}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _mum(pupil, email="mum@home.org", **kw):
    return C.add_contact(pupil.pupil_id, {"full_name": "Mum Portal", "relationship": "Mother",
                                          "email": email, **kw}, actor=ADMIN)


def _sees(username, role="parent"):
    return sorted(p.display_name for p in PT.pupils(Principal(username, role)))


def test_contact_makes_parent_login_and_second_child_joins_it(env):
    _mum(env["ava"])
    login = accounts.find_login_by_email("mum@home.org")
    assert login["username"] == "mum.portal" and login["role"] == accounts.PARENT_ROLE
    assert PA.undelivered(), "a welcome e-mail is queued"
    _mum(env["ben"], email="MUM@home.org")  # same parent, case differs
    assert _sees("mum.portal") == ["Ava Portal", "Ben Portal"]
    rows = PA.parent_logins()
    assert [r["username"] for r in rows] == ["mum.portal"]
    assert len(rows[0]["children"]) == 2


def test_no_login_without_parental_responsibility_or_email(env):
    C.add_contact(env["ben"].pupil_id, {"full_name": "Gran", "relationship": "Grandparent",
                                        "email": "gran@home.org",
                                        "parental_responsibility": False}, actor=ADMIN)
    C.add_contact(env["ben"].pupil_id, {"full_name": "Uncle", "relationship": "Other",
                                        "phone": "01234 567890"}, actor=ADMIN)
    assert accounts.find_login_by_email("gran@home.org") is None
    assert PA.parent_logins() == []


def test_login_from_another_system_is_reused_then_role_removed(env):
    c = C.add_contact(env["ben"].pupil_id, {"full_name": "Dad Portal", "relationship": "Father",
                                            "email": "dad@home.org"}, actor=ADMIN)
    assert accounts.find_login("elsewhere")["role"] == accounts.PARENT_ROLE
    assert _sees("elsewhere") == ["Ben Portal"]
    C.delete_contact(c.contact_id, actor=ADMIN)
    assert accounts.find_login("elsewhere")["role"] is None
    assert _sees("elsewhere") == []


def test_email_change_moves_link_and_responsibility_off_removes_it(env):
    c1 = _mum(env["ava"])
    c2 = _mum(env["ben"])
    C.update_contact(c1.contact_id, {"email": "mum.new@home.org"}, actor=ADMIN)
    new = accounts.find_login_by_email("mum.new@home.org")["username"]
    assert new != "mum.portal"
    assert _sees(new) == ["Ava Portal"] and _sees("mum.portal") == ["Ben Portal"]
    C.update_contact(c2.contact_id, {"parental_responsibility": False}, actor=ADMIN)
    assert _sees("mum.portal") == []
    assert accounts.find_login("mum.portal")["role"] is None


def test_parent_cannot_see_other_children(env):
    _mum(env["ava"])
    with pytest.raises(PA.PermissionDenied):
        PT.home(Principal("mum.portal", "parent"), env["ben"].pupil_id)


def test_manual_link_rules(env):
    ava, ben = env["ava"], env["ben"]
    PAC.create_for_pupil(ava.pupil_id, actor=ADMIN, send_welcome=False)
    with pytest.raises(PA.ValidationError):  # Ava already has a pupil login
        PA.link_login("student2", ava.pupil_id, "pupil", actor=ADMIN)
    PA.link_login("student2", ben.pupil_id, "pupil", actor=ADMIN)
    assert _sees("student2", "student") == ["Ben Portal"]
    link = PA.link_login("parent2", ben.pupil_id, "parent", actor=ADMIN)
    with pytest.raises(PA.ValidationError):  # already linked
        PA.link_login("parent2", ben.pupil_id, "parent", actor=ADMIN)
    with pytest.raises(PA.ValidationError):  # staff only as parents
        PA.link_login("pt_teach", ben.pupil_id, "pupil", actor=ADMIN)
    PA.link_login("pt_teach", ben.pupil_id, "parent", actor=ADMIN)
    assert PA.has_children(TEACHER)
    assert accounts.find_login("pt_teach")["role"] == "teacher"  # staff role kept
    with pytest.raises(PA.PermissionDenied):
        PA.link_login("parent2", ava.pupil_id, "parent", actor=TEACHER)
    with pytest.raises((PA.ValidationError, PA.NotFound)):
        PA.link_login("nobody", ben.pupil_id, "parent", actor=ADMIN)
    assert PA.unlink(link.link_id, actor=ADMIN).status == "removed"
    assert _sees("parent2") == []
    assert accounts.find_login("parent2")["role"] == "parent"  # not granted here, so kept


def test_contact_link_cannot_be_removed_by_hand(env):
    _mum(env["ava"])
    link = next(x for x in PA.list_links() if x.source == "contact")
    with pytest.raises(PA.ValidationError):
        PA.unlink(link.link_id, actor=ADMIN)


def test_sync_all_is_admin_only_and_idempotent(env):
    _mum(env["ava"])
    with pytest.raises(PA.PermissionDenied):
        PA.sync_all(actor=TEACHER)
    PA.sync_all(actor=ADMIN)
    assert [r["username"] for r in PA.parent_logins()] == ["mum.portal"]
    assert len(PA.links_for_pupil(env["ava"].pupil_id)) == 1


def test_usernames_are_not_emails_and_log_has_no_emails(env):
    _mum(env["ava"])
    assert "@" not in accounts.find_login_by_email("mum@home.org")["username"]
    log = (env["path"] / "activity.log").read_text()
    assert not re.search(r"[\w.]+@[\w.]+", log)
