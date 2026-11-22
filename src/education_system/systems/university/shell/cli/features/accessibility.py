"""Component extracted from the legacy menu router.

Disability & Accessibility (2026-10-19): the Accessibility Services portal
and Medical Accommodations as one menu. It used to be a placeholder that
listed tables and said "access via SQL".
"""
from __future__ import annotations
from ..bootstrap.integrations import ValidationError


def display_accessibility_tools_menu(auth):
    """Display the Disability & Accessibility CLI menu.

    A student goes straight to their own menu (requests, documents,
    messages, accommodations, renewals). Disability services and the health
    team choose between the request queue and the full Medical
    Accommodations tool."""
    from education_system.systems.university.domains.student_support.domain.disability import access
    from education_system.systems.university.domains.student_support.interfaces.cli.disability.accessibility_cli import (
        AccessibilityCLI,
    )
    try:
        staff = access.scope(auth) is None
    except PermissionError as exc:
        print(f"\n❌ {exc}")
        return
    cli = AccessibilityCLI(auth)
    if not staff:
        _student_menu(auth, cli)
        return

    while True:
        print("\n" + "="*50)
        print("  DISABILITY & ACCESSIBILITY SERVICES")
        print("="*50)
        print("1. Requests and renewals (student requests queue)")
        print("2. Accommodation management (Medical Accommodations)")
        print("3. DSA cases and exam access arrangements")
        print("4. Evacuation plans (PEEPs)")
        print("0. Return to Main Menu")
        print("="*50)
        try:
            choice = input("\nEnter your choice: ").strip()
            if choice == '1':
                cli.run_staff()
            elif choice == '2':
                try:
                    from ..services.medical_accommodation_cli import launch_medical_accommodation_cli
                except ImportError as exc:
                    print(f"\n❌ Medical Accommodations is not available: {exc}")
                    continue
                launch_medical_accommodation_cli(auth)
            elif choice == '3':
                from education_system.systems.university.domains.student_support.interfaces.cli.disability import (
                    dsa_cli,
                )
                dsa_cli.run(auth)
            elif choice == '4':
                from education_system.systems.university.domains.student_support.interfaces.cli.disability import (
                    peeps_cli,
                )
                peeps_cli.run(auth)
            elif choice == '0':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"❌ Error: {e}")


def _student_menu(auth, cli):
    """A student's choice: their requests and adjustments (the menu they
    always had), their DSA case, or their evacuation plan."""
    from education_system.systems.university.domains.student_support.interfaces.cli.disability import (
        dsa_cli,
        peeps_cli,
    )
    while True:
        print("\n" + "="*50)
        print("  DISABILITY & ACCESSIBILITY SERVICES")
        print("="*50)
        print("1. My requests and adjustments")
        print("2. My DSA (Disabled Students' Allowances)")
        print("3. My evacuation plan (PEEP)")
        print("0. Return to Main Menu")
        try:
            choice = input("\nEnter your choice: ").strip()
        except KeyboardInterrupt:
            return
        if choice == '1':
            cli.run()
        elif choice == '2':
            dsa_cli.run(auth)
        elif choice == '3':
            peeps_cli.run(auth)
        elif choice == '0':
            return
        else:
            print("❌ Invalid choice.")
