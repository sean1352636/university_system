"""Wellbeing Casework — CLI twin of the GUI window: counselling, Support to
Study, trusted contacts and evacuation plans (PEEPs). Each area decides what
the signed-in person may do."""

from __future__ import annotations


def _counselling(auth):
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing import (
        counselling_cli,
    )
    counselling_cli.run_menu(auth)


def _sts(auth):
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.casework import (
        support_to_study_cli,
    )
    support_to_study_cli.run_menu(auth)


def _trusted(auth):
    from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.casework import (
        trusted_contacts_cli,
    )
    trusted_contacts_cli.run_menu(auth)


def _peeps(auth):
    from education_system.systems.university.domains.student_support.interfaces.cli.disability import (
        peeps_cli,
    )
    peeps_cli.run(auth)


OPTIONS = (("1", "Counselling", _counselling), ("2", "Support to Study", _sts),
           ("3", "Trusted contacts", _trusted), ("4", "Evacuation plans (PEEPs)", _peeps))


def run_casework_menu(auth=None) -> None:
    if auth is None:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
    while True:
        print("\n" + "=" * 50 + "\n  WELLBEING CASEWORK\n" + "=" * 50)
        for key, label, _fn in OPTIONS:
            print(f"{key}. {label}")
        print("0. Return")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        for key, _label, fn in OPTIONS:
            if choice == key:
                try:
                    fn(auth)
                except KeyboardInterrupt:
                    print()
                except ImportError as exc:
                    print(f"\n❌ That area is not available: {exc}")
                break
        else:
            print("❌ Invalid choice.")
