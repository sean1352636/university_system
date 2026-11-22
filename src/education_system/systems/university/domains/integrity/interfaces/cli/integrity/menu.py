"""Entry point: shows each person the parts of academic integrity their
role allows."""

from __future__ import annotations

from education_system.systems.university.application.integrity import access
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.common import (  # noqa: E501
    ask, session,
)
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.officer import (  # noqa: E501
    officer_menu,
)
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.staff import (
    staff_menu,
)
from education_system.systems.university.domains.integrity.interfaces.cli.integrity.student import (  # noqa: E501
    student_menu,
)


def _who(auth):
    try:
        with session(auth) as (conn, who, _outbox):
            return who, access.is_officer(conn, who)
    except PermissionError as exc:
        print(f"\n{exc}")
        return None, False


def integrity_menu(auth) -> None:
    who, officer = _who(auth)
    if who is None:
        return
    if who.is_student:
        student_menu(auth)
        return
    if not who.is_staff:
        print("\nAcademic integrity is for students and staff.")
        return
    while True:
        print("\nAcademic integrity")
        print("1. Similarity checks and reviews")
        if officer:
            print("2. Cases, appeals and administration")
        print("0. Back")
        choice = ask("Choose")
        if choice == "1":
            staff_menu(auth)
        elif choice == "2" and officer:
            officer_menu(auth)
        elif choice in ("0", ""):
            return


def cases_menu(auth) -> None:
    """Straight to cases (integrity officers)."""
    who, officer = _who(auth)
    if who is None:
        return
    if not officer:
        print("\nIntegrity cases are run by integrity officers.")
        return
    officer_menu(auth)
