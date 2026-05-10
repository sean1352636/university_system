"""CLI for self-serve enrolment verification / status letters."""

from __future__ import annotations

from education_system.university_system.modules.domain.student_affairs.student_app.documentation.services.documentation_service import (
    DocumentationService,
    LETTER_TYPES,
)


def _is_staff(auth) -> bool:
    if not auth or not getattr(auth, "current_user", None):
        return False
    user = auth.current_user
    role = (user.get("role") or "").lower() if isinstance(user, dict) else ""
    return role in {"admin", "staff", "registrar", "manager"}


def _username(auth) -> str:
    if auth and getattr(auth, "current_user", None) and isinstance(auth.current_user, dict):
        return auth.current_user.get("username") or "unknown"
    return "unknown"


def display_documentation_menu(auth) -> None:
    service = DocumentationService()
    student_id = _username(auth)
    staff = _is_staff(auth)

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("ENROLMENT VERIFICATION & STATUS LETTERS".center(70))
        print("=" * 70)
        print("\n  1. Request a new letter")
        print("  2. View my requests")
        print("  3. View my issued letters")
        print("  4. Verify a letter (third-party)")
        if staff:
            print("\n  -- Registry Staff --")
            print("  5. Review pending requests")
            print("  6. Revoke an issued letter")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            _request_letter(service, student_id)
        elif choice == "2":
            _list_my_requests(service, student_id)
        elif choice == "3":
            _list_my_letters(service, student_id)
        elif choice == "4":
            _verify_letter(service)
        elif choice == "5" and staff:
            _review_pending(service, _username(auth))
        elif choice == "6" and staff:
            _revoke_letter(service)
        else:
            print("Invalid option.")
        input("\nPress Enter to continue...")


def _request_letter(service: DocumentationService, student_id: str) -> None:
    print("\nLetter types:")
    keys = list(LETTER_TYPES.keys())
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {LETTER_TYPES[key]}")
    sel = input("\nChoose type number: ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(keys)):
        print("Invalid selection.")
        return
    letter_type = keys[int(sel) - 1]
    purpose = input("Purpose / brief reason (optional): ").strip() or None
    recipient_name = input("Recipient name (e.g. council, lender) [optional]: ").strip() or None
    recipient_address = input("Recipient address [optional]: ").strip() or None
    request_id = service.submit_request(
        student_id=student_id,
        letter_type=letter_type,
        purpose=purpose,
        recipient_name=recipient_name,
        recipient_address=recipient_address,
    )
    print(f"\nRequest #{request_id} submitted. Registry will review and issue.")


def _list_my_requests(service: DocumentationService, student_id: str) -> None:
    rows = service.list_requests(student_id=student_id)
    if not rows:
        print("\nNo requests yet.")
        return
    print(f"\n{'ID':<5} {'Type':<14} {'Status':<10} {'Requested':<20} Letter")
    print("-" * 70)
    for r in rows:
        print(
            f"{r['id']:<5} {r['letter_type']:<14} {r['status']:<10} "
            f"{(r['requested_at'] or '')[:19]:<20} "
            f"{r['letter_id'] or ''}"
        )


def _list_my_letters(service: DocumentationService, student_id: str) -> None:
    rows = service.list_letters(student_id)
    if not rows:
        print("\nNo issued letters.")
        return
    for r in rows:
        flag = " (REVOKED)" if r["revoked"] else ""
        print(
            f"  {r['id']}: {r['reference_code']} — {r['letter_type']} "
            f"issued {r['issued_at'][:10]}, valid until {r['valid_until']}{flag}"
        )
    sel = input("\nView letter ID (Enter to skip): ").strip()
    if sel.isdigit():
        letter = service.get_letter(int(sel))
        if letter:
            print("\n" + "=" * 70)
            print(letter["content"])
            print("=" * 70)
            print(f"\nVerification token: {letter['verification_token']}")
        else:
            print("Letter not found.")


def _verify_letter(service: DocumentationService) -> None:
    token = input("\nReference code or verification token: ").strip()
    if not token:
        return
    result = service.verify_letter(token)
    if not result:
        print("\nNot recognised. This letter cannot be verified.")
        return
    print("\n--- Verification Result ---")
    for key in (
        "reference_code",
        "letter_type",
        "student_id",
        "issued_at",
        "valid_until",
        "is_valid",
        "revoked",
        "revoked_reason",
    ):
        if result.get(key) not in (None, ""):
            print(f"  {key}: {result[key]}")


def _review_pending(service: DocumentationService, approver: str) -> None:
    rows = service.list_requests(status="pending")
    if not rows:
        print("\nNo pending requests.")
        return
    for r in rows:
        print(
            f"\n  #{r['id']} student={r['student_id']} type={r['letter_type']} "
            f"requested={(r['requested_at'] or '')[:19]}"
        )
        print(f"    purpose: {r.get('purpose') or '-'}")
        print(f"    recipient: {r.get('recipient_name') or '-'}")
    sel = input("\nRequest ID to action (Enter to skip): ").strip()
    if not sel.isdigit():
        return
    action = input("(a)pprove, (r)eject, (s)kip: ").strip().lower()
    if action == "a":
        try:
            letter = service.approve_request(int(sel), approver)
            print(f"\nIssued {letter['reference_code']} (letter #{letter['id']}).")
        except ValueError as exc:
            print(f"\nError: {exc}")
    elif action == "r":
        reason = input("Rejection reason: ").strip() or "Not specified"
        if service.reject_request(int(sel), approver, reason):
            print("Request rejected.")
        else:
            print("No pending request with that ID.")


def _revoke_letter(service: DocumentationService) -> None:
    sel = input("\nLetter ID to revoke: ").strip()
    if not sel.isdigit():
        return
    reason = input("Reason: ").strip() or "Revoked by registry"
    if service.revoke_letter(int(sel), reason):
        print("Letter revoked.")
    else:
        print("Letter not found.")
