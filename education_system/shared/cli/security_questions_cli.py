"""Shared CLI menu for managing security questions.

Works with any education subsystem's auth object. The user can view,
set, or update their security questions used for password recovery.
"""

import getpass
import logging

from education_system.shared.auth.forgot_password import ForgotPasswordService
from education_system.shared.auth.schema import SECURITY_QUESTIONS
from education_system.shared.cli.cli_helpers import print_header, print_menu, get_choice

logger = logging.getLogger(__name__)


def _get_user_id(auth) -> int | None:
    """Extract the user_id from various auth object shapes."""
    cu = getattr(auth, "current_user", None) or {}
    if isinstance(cu, dict):
        return cu.get("user_id") or cu.get("id")
    return None


def _get_username(auth) -> str | None:
    """Extract the username from various auth object shapes."""
    cu = getattr(auth, "current_user", None) or {}
    if isinstance(cu, dict):
        return cu.get("username")
    return None


def _get_auth_db_path(auth) -> str | None:
    """Extract the auth DB path from various auth object shapes."""
    # Shared auth stores it as _db_path
    return getattr(auth, "_db_path", None) or getattr(auth, "_auth_db_path", None)


def security_questions_menu(auth):
    """Interactive CLI menu for viewing and updating security questions."""
    user_id = _get_user_id(auth)
    username = _get_username(auth)
    db_path = _get_auth_db_path(auth)

    if not user_id or not username:
        print("\n  Unable to determine current user. Please log in first.")
        return

    svc = ForgotPasswordService(db_path)

    while True:
        print_header("Security Questions")

        # Show current status
        has_questions = svc.has_security_questions(username)
        if has_questions:
            try:
                questions = svc.get_questions_for_user(username)
                print("\n  Current security questions:")
                for i, q in enumerate(questions, 1):
                    print(f"    {i}. {q['question']}")
                print()
            except Exception:
                print("\n  Status: Configured\n")
        else:
            print("\n  Status: Not configured")
            print("  You need to set up security questions to use the Forgot Password feature.\n")

        options = [
            ("1", "Set / Update Security Questions"),
            ("2", "View Available Questions"),
        ]
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _set_questions(svc, user_id)
        elif choice == "2":
            _view_available_questions()
        elif choice == "0":
            return
        else:
            print("\n  Invalid option.")


def _view_available_questions():
    """Display the list of available security questions."""
    print_header("Available Security Questions")
    for i, q in enumerate(SECURITY_QUESTIONS, 1):
        print(f"  {i}. {q}")
    print()
    input("  Press Enter to continue...")


def _set_questions(svc: ForgotPasswordService, user_id: int):
    """Guide the user through setting 3 security questions."""
    print_header("Set Security Questions")
    print("\n  Choose 3 different questions and provide answers.")
    print("  Answers are case-insensitive.\n")

    print("  Available questions:")
    for i, q in enumerate(SECURITY_QUESTIONS, 1):
        print(f"    {i}. {q}")
    print()

    chosen: list[tuple[str, str]] = []
    used_indices: set[int] = set()

    for qnum in range(1, 4):
        while True:
            try:
                idx_str = input(f"  Question {qnum} — enter number (1-{len(SECURITY_QUESTIONS)}): ").strip()
                idx = int(idx_str)
                if idx < 1 or idx > len(SECURITY_QUESTIONS):
                    print(f"    Please enter a number between 1 and {len(SECURITY_QUESTIONS)}.")
                    continue
                if idx in used_indices:
                    print("    You've already chosen that question. Pick a different one.")
                    continue
                break
            except ValueError:
                print("    Please enter a valid number.")

        question = SECURITY_QUESTIONS[idx - 1]
        answer = input(f"  Answer for \"{question}\": ").strip()
        if not answer:
            print("    Answer cannot be empty. Please try again.")
            # Let them retry this question
            continue

        used_indices.add(idx)
        chosen.append((question, answer))

    if len(chosen) < 3:
        print("\n  Could not complete setup — 3 questions are required.")
        return

    # Confirm
    print("\n  Your chosen questions:")
    for i, (q, _) in enumerate(chosen, 1):
        print(f"    {i}. {q}")

    confirm = input("\n  Save these questions? (y/n): ").strip().lower()
    if confirm != "y":
        print("\n  Cancelled.")
        return

    try:
        svc.set_security_questions(user_id, chosen)
        print("\n  Security questions updated successfully.")
    except Exception as e:
        print(f"\n  Error: {e}")
