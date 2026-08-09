"""What the interface layer depends on, and the services written for it.

Two kinds of test here. The first is structural: every entry in the CLI
menu tree and the GUI navigation tree names a module and a callable, and
a typo in either is invisible until somebody clicks it. The second
covers the services the account and settings screens were built on —
preferences, the CSV export, and the read side of the account adapter.

Nothing here opens a Tk window. The windows are checked for importability
and for exposing ``render``; drawing them needs a display and belongs to
the ``gui`` marker, not to a headless run.
"""

from __future__ import annotations

import importlib

import pytest

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.services import preferences, reporting_service
from education_system.systems.apprenticeships.services.access import Actor, PermissionDenied

_COMMANDS = "education_system.systems.apprenticeships.interfaces.cli.commands"
_WINDOWS = "education_system.systems.apprenticeships.interfaces.gui.windows"


def _cli_targets() -> list[str]:
    from education_system.systems.apprenticeships.interfaces.cli import menus

    targets = {
        target
        for tree in menus.MENUS.values()
        for _, items in tree
        for _, target in items
    }
    targets |= {t for _, t in [*menus.SYSTEM_CATEGORY, *menus.SYSTEM_CATEGORY_ADMIN]}
    return sorted(targets)


def _gui_windows() -> list[str]:
    from education_system.systems.apprenticeships.interfaces.gui import gui_main

    modules = {
        module
        for tree in gui_main.NAV_BY_ROLE.values()
        for _, items in tree
        for _, module in items
    }
    modules |= {
        m for _, m in [*gui_main.SYSTEM_CATEGORY, *gui_main.SYSTEM_CATEGORY_ADMIN]
    }
    return sorted(modules)


# ═════════════════════════════════════════════════════════════════════
# The menu trees resolve
# ═════════════════════════════════════════════════════════════════════

class TestWiring:
    @pytest.mark.parametrize("target", _cli_targets())
    def test_every_cli_menu_entry_resolves(self, target):
        """``module:function`` in the menu tree has to exist.

        The shell reports a failed lookup as "this command is
        unavailable", which is the right thing at runtime and useless as
        a warning — nothing surfaces the typo until a user picks it.
        """
        module_name, _, function_name = target.partition(":")
        module = importlib.import_module(f"{_COMMANDS}.{module_name}")
        assert callable(getattr(module, function_name, None)), target

    @pytest.mark.parametrize("module_name", _gui_windows())
    def test_every_gui_window_exposes_render(self, module_name):
        module = importlib.import_module(f"{_WINDOWS}.{module_name}")
        assert callable(getattr(module, "render", None)), module_name

    def test_no_screen_is_a_placeholder(self):
        """The helpers that stood in for unbuilt screens are gone.

        Guards the regression rather than the removal: re-adding either
        would let a screen go back to announcing itself as unfinished
        instead of failing review.
        """
        from education_system.systems.apprenticeships.interfaces.cli import prompts
        from education_system.systems.apprenticeships.interfaces.gui import widgets

        assert not hasattr(prompts, "placeholder_menu")
        assert not hasattr(widgets, "placeholder")


# ═════════════════════════════════════════════════════════════════════
# Preferences
# ═════════════════════════════════════════════════════════════════════

class TestPreferences:
    @pytest.fixture(autouse=True)
    def _isolate(self, db):
        """Every test starts from the defaults, and leaves them there.

        The active preferences are a module global — the cell formatters
        are called thousands of times a screen and have no actor to hand
        — so a test that set them and walked away would leak into the
        next one.
        """
        preferences.reset_active()
        yield
        preferences.reset_active()

    def test_defaults_apply_to_an_unknown_user(self, db):
        assert preferences.get(Actor(username="nobody", role="staff")) == preferences.DEFAULTS

    def test_a_saved_preference_comes_back(self, db, admin):
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 50})
        assert preferences.get(admin)[preferences.ROWS_PER_PAGE] == 50

    def test_preferences_are_per_login(self, db, admin):
        other = Actor(username="tutor1", role="staff")
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 50})
        assert preferences.get(other)[preferences.ROWS_PER_PAGE] == preferences.DEFAULTS[
            preferences.ROWS_PER_PAGE
        ]

    def test_a_dropdown_label_is_accepted_as_well_as_the_pattern(self, db, admin):
        preferences.set_preferences(admin, {preferences.DATE_FORMAT: "UK — 09/03/2026"})
        assert preferences.get(admin)[preferences.DATE_FORMAT] == "%d/%m/%Y"

    @pytest.mark.parametrize("payload", [
        {"rows_per_page": 999},
        {"date_format": "%c"},
        {"idle_timeout_minutes": 7},
    ])
    def test_a_value_outside_the_offered_set_is_refused(self, db, admin, payload):
        with pytest.raises(ValidationError):
            preferences.set_preferences(admin, payload)

    def test_reset_goes_back_to_the_defaults(self, db, admin):
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 50})
        assert preferences.reset(admin) == preferences.DEFAULTS
        assert preferences.get(admin) == preferences.DEFAULTS

    def test_activate_makes_them_the_ones_the_formatters_read(self, db, admin):
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 50})
        preferences.activate(admin.username)
        assert preferences.rows_per_page() == 50

    def test_saving_updates_the_active_session_in_place(self, db, admin):
        preferences.activate(admin.username)
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 15})
        assert preferences.rows_per_page() == 15

    def test_activating_a_stranger_falls_back_to_the_defaults(self, db, admin):
        preferences.set_preferences(admin, {preferences.ROWS_PER_PAGE: 50})
        preferences.activate(admin.username)
        preferences.activate("someone-else")
        assert preferences.rows_per_page() == preferences.DEFAULTS[preferences.ROWS_PER_PAGE]

    def test_an_unusable_stored_value_is_discarded_not_raised(self, db, admin):
        """A dropped format must not lock anybody out.

        ``activate`` runs during login, so a stored value that no longer
        validates has to degrade to the default rather than raise.
        """
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            preference_repository,
        )

        preference_repository.save(admin.username, {preferences.DATE_FORMAT: "%c"})
        assert preferences.get(admin)[preferences.DATE_FORMAT] == preferences.DEFAULTS[
            preferences.DATE_FORMAT
        ]


class TestDateFormatting:
    """``format_date`` is called on every cell, dates and everything else."""

    @pytest.fixture(autouse=True)
    def _uk_format(self, db, admin):
        preferences.reset_active()
        preferences.set_preferences(admin, {preferences.DATE_FORMAT: "%d/%m/%Y"})
        preferences.activate(admin.username)
        yield
        preferences.reset_active()

    def test_an_iso_date_is_reformatted(self):
        assert preferences.format_date("2026-03-09") == "09/03/2026"

    @pytest.mark.parametrize("value", [
        "2026-03-09 10:00:00",   # a timestamp is not a date
        "ST0119",                # a standard reference
        "K3, S1, B2",            # KSB codes
        "2026-13-45",            # shaped like a date, is not one
        "",
        None,
        7,
        3.5,
        True,
    ])
    def test_anything_that_is_not_an_iso_date_is_untouched(self, value):
        assert preferences.format_date(value) == value

    def test_the_cli_cell_formatter_applies_it(self):
        from education_system.systems.apprenticeships.interfaces.cli import prompts

        assert prompts.cell("2026-03-09") == "09/03/2026"
        assert prompts.cell("ST0119") == "ST0119"
        assert prompts.cell(None) == config.EMPTY_CELL


# ═════════════════════════════════════════════════════════════════════
# Reports and exports
# ═════════════════════════════════════════════════════════════════════

class TestExport:
    @pytest.fixture(autouse=True)
    def _exports_dir(self, tmp_path, monkeypatch):
        """Write the CSVs somewhere disposable.

        ``export_csv`` reads the path off the module at call time, so
        repointing the attribute is enough — and necessary, because the
        real one is under ``<repo>/var`` and a test run must not leave
        files there.
        """
        from education_system import paths

        target = tmp_path / "exports"
        target.mkdir()
        monkeypatch.setattr(paths, "APPRENTICESHIPS_EXPORTS_DIR", target)
        return target

    def test_every_named_export_writes_a_file_with_a_header(
        self, cohort, admin, _exports_dir
    ):
        for kind in reporting_service.EXPORTS:
            target = reporting_service.export_csv(admin, kind)
            assert target.exists(), kind
            assert target.parent == _exports_dir
            assert target.read_text(encoding="utf-8").splitlines()[0], kind

    def test_the_filename_carries_the_run_date(self, cohort, admin):
        target = reporting_service.export_csv(admin, "cohort", as_of="2026-01-31")
        assert target.name == "cohort-2026-01-31.csv"

    def test_the_cohort_export_holds_a_row_per_apprentice(self, cohort, admin):
        target = reporting_service.export_csv(admin, "cohort", as_of="2026-01-31")
        lines = target.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2  # header plus the one apprentice in the fixture
        assert "Bell" in lines[1]

    def test_an_unknown_export_is_refused(self, db, admin):
        with pytest.raises(ValidationError, match="Export must be one of"):
            reporting_service.export_csv(admin, "everything")

    def test_an_employer_may_not_export_at_all(self, cohort):
        """``report.view`` is not an employer capability, and the export needs it."""
        with pytest.raises(PermissionDenied):
            reporting_service.export_csv(cohort["employer_actor"], "cohort")

    def test_the_export_is_scoped_the_way_the_screens_are(self, cohort):
        """It reads through the services, so the scope is not re-derived.

        A tutor with nobody on their caseload must get a header and no
        rows. The failure mode guarded against is an export that reaches
        past the scope the screens apply and hands over the whole cohort.
        """
        stranger = Actor(username="other-tutor", role="staff", staff_id=9999)
        target = reporting_service.export_csv(stranger, "cohort", as_of="2026-01-31")
        lines = target.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0].startswith("Apprentice")
        assert len(lines) == 1


# ═════════════════════════════════════════════════════════════════════
# Accounts
# ═════════════════════════════════════════════════════════════════════

class TestAccounts:
    """The adapter over the platform's shared login database.

    Only the parts that do not need an ``auth.db`` to exist: the
    permission boundary, the link rules, and the validation. The
    password and MFA paths belong to the platform's own tests.
    """

    def test_only_an_administrator_may_read_the_account_list(self, cohort):
        from education_system.systems.apprenticeships.services import account_service

        with pytest.raises(PermissionDenied):
            account_service.list_accounts(cohort["tutor"])

    def test_only_an_administrator_may_grant_a_role(self, cohort):
        from education_system.systems.apprenticeships.services import account_service

        with pytest.raises(PermissionDenied):
            account_service.grant_role(cohort["tutor"], "someone", "staff")

    def test_a_role_outside_this_system_is_refused(self, db, admin):
        from education_system.systems.apprenticeships.services import account_service

        with pytest.raises(ValidationError, match="Role must be one of"):
            account_service.grant_role(admin, "someone", "headteacher")

    def test_an_administrator_cannot_revoke_their_own_access(self, db, admin):
        """Otherwise the system can be left with nobody who can grant it back."""
        from education_system.systems.apprenticeships.services import account_service

        with pytest.raises(ValidationError, match="your own access"):
            account_service.revoke_access(admin, admin.username)

    def test_a_role_with_no_record_behind_it_cannot_be_linked(self, db, admin):
        from education_system.systems.apprenticeships.services import account_service

        with pytest.raises(ValidationError, match="not scoped to a single record"):
            account_service.link_to_record(admin, "someone", config.ADMIN, 1)

    def test_linking_an_apprentice_login_sets_the_username_on_the_record(
        self, cohort, admin
    ):
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            apprentice_repository,
        )
        from education_system.systems.apprenticeships.services import account_service

        message = account_service.link_to_record(
            admin, "new-login", config.APPRENTICE, cohort["apprentice_id"]
        )
        assert "new-login" in message
        record = apprentice_repository.get(cohort["apprentice_id"])
        assert record.username == "new-login"

    def test_link_candidates_report_the_login_already_on_the_record(self, cohort, admin):
        from education_system.systems.apprenticeships.services import account_service

        candidates = account_service.link_candidates(admin, config.APPRENTICE)
        assert [c["username"] for c in candidates] == ["apprentice1"]

    def test_whoami_reports_an_unresolvable_session_rather_than_raising(self, db):
        """A screen has to be able to say why the account actions are off."""
        from education_system.systems.apprenticeships.services import account_service

        account = account_service.whoami(Actor(username="", role="staff"))
        assert account["user_id"] is None
        assert account["linked"] is False

    @pytest.mark.parametrize("role,linked", [
        (config.ADMIN, True),               # nothing to link an admin to
        (config.END_POINT_ASSESSOR, True),  # nor an external assessor
        (config.APPRENTICE, False),
        (config.EMPLOYER, False),
        (config.STAFF, False),
    ])
    def test_is_linked_follows_the_role(self, db, role, linked):
        from education_system.systems.apprenticeships.services import account_service

        assert account_service.is_linked(Actor(username="x", role=role)) is linked
