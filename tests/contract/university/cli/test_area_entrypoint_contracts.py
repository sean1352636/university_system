"""Cross-area behavioral contracts for university CLI entry points."""

from types import SimpleNamespace


def input_sequence(*values):
    responses = iter(values)
    return lambda _prompt="": next(responses)


def test_admissions_invalid_input_recovers_and_exits(monkeypatch, capsys):
    from education_system.systems.university.domains.admissions.interfaces.cli import (
        admissions_crm_cli,
    )

    monkeypatch.setattr("builtins.input", input_sequence("invalid", "8"))
    result = admissions_crm_cli.run_admissions_crm_menu(SimpleNamespace())

    output = capsys.readouterr().out
    assert result is None
    assert "ADMISSIONS & RECRUITMENT CRM" in output
    assert "Invalid choice" in output


def test_admissions_keyboard_interrupt_returns_cleanly(monkeypatch, capsys):
    from education_system.systems.university.domains.admissions.interfaces.cli import (
        admissions_crm_cli,
    )

    def interrupt(_prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    assert admissions_crm_cli.run_admissions_crm_menu(SimpleNamespace()) is None
    assert "ADMISSIONS & RECRUITMENT CRM" in capsys.readouterr().out


def test_learner_cli_handles_malformed_choice_then_exits(monkeypatch, capsys):
    from education_system.systems.university.domains.learners.interfaces.cli.student_id import (
        student_id_cli,
    )

    monkeypatch.setattr(student_id_cli.student_id_service, "init_db", lambda: None)
    monkeypatch.setattr("builtins.input", input_sequence("?", "0"))
    assert student_id_cli.main() is None
    output = capsys.readouterr().out
    assert "Invalid option" in output
    assert "Returning to main menu" in output


def test_operations_cli_starts_with_empty_database_and_exits(monkeypatch, capsys):
    from education_system.systems.university.domains.operations.interfaces.cli.campus.equipment import (
        equipment_cli,
    )

    initialized = []
    monkeypatch.setattr(equipment_cli, "init_equipment_db", lambda: initialized.append(True))
    monkeypatch.setattr("builtins.input", input_sequence("0"))
    assert equipment_cli.display_menu() is None
    assert initialized == [True]
    assert "EQUIPMENT RENTAL MANAGEMENT SYSTEM" in capsys.readouterr().out


def test_finance_menu_output_and_clean_exit(monkeypatch, capsys):
    from education_system.systems.university.domains.finance.interfaces.cli.ledger import ledger_cli

    monkeypatch.setattr("builtins.input", input_sequence("4"))
    assert ledger_cli.run_ledger_menu(SimpleNamespace()) is None
    output = capsys.readouterr().out
    assert "GENERAL LEDGER" in output
    assert "Returning to main menu" in output


def test_staff_cli_denies_unauthenticated_user(monkeypatch, capsys):
    from education_system.systems.university.domains.staff.interfaces.cli.staff_hr import staff_hr_cli

    monkeypatch.setattr(staff_hr_cli, "auth", None)
    monkeypatch.setattr(staff_hr_cli, "get_auth", lambda: None)
    monkeypatch.setattr("builtins.input", input_sequence(""))
    assert staff_hr_cli.display_staff_hr_menu() is None
    assert "logged in" in capsys.readouterr().out.lower()


def test_shell_initialization_failure_returns_without_menu(monkeypatch, capsys):
    from education_system.systems.university.shell.cli import cli_main

    monkeypatch.setattr(cli_main, "silent_integrity_check", lambda: None)
    monkeypatch.setattr(cli_main, "fix_parent_portal_database", lambda: None)
    monkeypatch.setattr(cli_main, "init_i18n", lambda: None)
    monkeypatch.setattr(cli_main, "initialize_system", lambda: False)

    assert cli_main.main() is None
    assert "System initialization failed" in capsys.readouterr().out


def test_assessment_menu_has_stable_empty_exit(monkeypatch, capsys):
    from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.services import (
        mitigating_circumstances_service as service_module,
    )
    from education_system.systems.university.domains.assessment.interfaces.cli.mitigating_circumstances import (
        mitigating_circumstances_cli,
    )

    monkeypatch.setattr(service_module, "MitigatingCircumstancesService", lambda: object())
    monkeypatch.setattr("builtins.input", input_sequence("0"))
    assert mitigating_circumstances_cli.display_mitigating_circumstances_menu(None) is None
    assert "MITIGATING CIRCUMSTANCES" in capsys.readouterr().out


def test_governance_menu_returns_cleanly(monkeypatch, capsys):
    from education_system.systems.university.domains.governance.interfaces.cli.health_safety import (
        health_safety_cli,
    )

    monkeypatch.setattr("builtins.input", input_sequence("4"))
    assert health_safety_cli.run_health_safety_menu(SimpleNamespace()) is None
    assert "HEALTH & SAFETY PORTAL" in capsys.readouterr().out


def test_pastoral_menu_handles_empty_notification_database(monkeypatch, capsys):
    from education_system.systems.university.domains.student_life.domain.student_app.services import (
        student_app_service,
    )
    from education_system.systems.university.domains.student_life.interfaces.cli.student_app import (
        student_app_cli,
    )

    empty_service = SimpleNamespace(get_unread_count=lambda _student: 0)
    monkeypatch.setattr(student_app_service, "StudentAppService", lambda: empty_service)
    monkeypatch.setattr("builtins.input", input_sequence("0", ""))
    auth = SimpleNamespace(current_user={"username": "student"})
    assert student_app_cli.display_student_app_menu(auth) is None
    assert "0 unread" in capsys.readouterr().out


def test_progression_menu_clean_exit(monkeypatch, capsys):
    from education_system.systems.university.domains.progression.interfaces.cli.apprenticeships import (
        apprenticeships_cli,
    )

    service = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(apprenticeships_cli, "ApprenticeshipService", lambda: service)
    monkeypatch.setattr("builtins.input", input_sequence("5"))
    assert apprenticeships_cli.run_apprenticeships_menu(SimpleNamespace()) is None
    assert "UNIVERSITY APPRENTICESHIP MANAGEMENT" in capsys.readouterr().out


def test_safeguarding_menu_initializes_empty_store_and_exits(monkeypatch, capsys):
    from education_system.systems.university.domains.safeguarding.interfaces.cli import (
        safeguarding_cli,
    )

    initialized = []
    monkeypatch.setattr(safeguarding_cli, "init_db", lambda: initialized.append(True))
    monkeypatch.setattr("builtins.input", input_sequence("8"))
    assert safeguarding_cli.run_safeguarding_menu(SimpleNamespace()) is None
    assert initialized == [True]
    assert "SAFEGUARDING" in capsys.readouterr().out
