"""Certificates & Transcripts in the terminal — the CLI twin of
:mod:`certificates_gui`.

Staff and admins get the GUI's four tabs as menu options: Certificates (list
all, search by student, export one as HTML, revoke one), Transcripts
(search learners across every system, show the full or summary transcript,
save it to a file), Generate and Verify. A signed-in student sees only their
own certificates (with HTML export) and their own transcript, as in the GUI.

Same services as the GUI: :class:`CertificateService` for certificates and
the cross-system :class:`transcript.transcript_service.TranscriptService`
for transcripts. Entry point: ``run(db_path=None, auth=None)``, like the
other platform CLIs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

CERT_TYPES = ["completion", "achievement", "attendance", "merit", "distinction"]


# ── Prompts ──────────────────────────────────────────────────────────

def _ask(msg: str, default: str = "") -> str:
    try:
        raw = input(f"  {msg}{f' [{default}]' if default else ''}: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    return raw or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _header(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


# ── Who is signed in (same rule as the GUI) ──────────────────────────

def _current_user(auth: Any) -> dict | None:
    if not auth:
        return None
    user = getattr(auth, "current_user", None)
    if user is None and hasattr(auth, "get_current_user"):
        try:
            user = auth.get_current_user()
        except Exception:
            user = None
    return user or None


def _is_student(auth: Any) -> bool:
    """True iff the signed-in user has only the 'student' role; staff, admins
    and callers with no session get the full menu."""
    user = _current_user(auth)
    if not user:
        return False
    role = (user.get("role") or "").lower()
    if role:
        return role == "student"
    roles = {(s.get("role") or "").lower() for s in (user.get("systems") or [])}
    roles.discard("")
    return bool(roles) and roles.issubset({"student"})


def _student_identity(auth: Any) -> tuple[str, str]:
    user = _current_user(auth) or {}
    sid = (user.get("student_id") or user.get("user_id") or user.get("id")
           or user.get("username") or "")
    name = (user.get("display_name") or user.get("name")
            or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            or str(sid))
    return str(sid), name


# ── Certificates ─────────────────────────────────────────────────────

def _cert_service(db_path):
    from education_system.platform.features.certificates.certificate_service import (
        CertificateService,
    )
    return CertificateService(db_path)


def _print_certs(certs: list[dict], *, with_student: bool = True) -> None:
    if not certs:
        print("\n  No certificates found.")
        return
    print()
    head = f"  {'ID':>4}  " + (f"{'Student':<12} " if with_student else "") + \
        f"{'Certificate No.':<22} {'Type':<12} {'Course':<26} {'Awarded':<10} " \
        f"{'Grade':<6} {'Status':<8} Issued by"
    print(head)
    print("  " + "-" * (len(head) - 2))
    for c in certs:
        print(f"  {c.get('id', ''):>4}  "
              + (f"{str(c.get('student_id', ''))[:12]:<12} " if with_student else "")
              + f"{str(c.get('certificate_number', ''))[:22]:<22} "
              f"{str(c.get('certificate_type', ''))[:12]:<12} "
              f"{str(c.get('course_name', ''))[:26]:<26} {str(c.get('award_date', '')):<10} "
              f"{str(c.get('grade') or ''):<6} {str(c.get('status', '')):<8} "
              f"{c.get('issued_by') or ''}")
    print(f"\n  {len(certs)} certificate(s).")


def _list_all(svc) -> None:
    _print_certs(svc.list_certificates())


def _search(svc) -> None:
    sid = _ask("Student ID")
    if not sid:
        print("  Enter a Student ID to search.")
        return
    _print_certs(svc.list_certificates(student_id=sid))


def _export_html(svc, *, own_student_id: str | None = None) -> None:
    raw = _ask("Certificate ID to export")
    if not raw.isdigit():
        print("  Enter the certificate's ID (the first column).")
        return
    cert_id = int(raw)
    if own_student_id is not None:
        mine = {c.get("id") for c in svc.list_certificates(student_id=own_student_id)}
        if cert_id not in mine:
            print("  That isn't one of your certificates.")
            return
    html = svc.export_certificate_html(cert_id)
    path = Path(_ask("Save as", f"certificate_{cert_id}.html")).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print(f"  Certificate saved to: {path.resolve()}")


def _revoke(svc) -> None:
    raw = _ask("Certificate ID to revoke")
    if not raw.isdigit():
        print("  Enter the certificate's ID (the first column).")
        return
    reason = _ask("Reason for revocation")
    if not reason:
        print("  A reason is required; nothing changed.")
        return
    svc.revoke_certificate(int(raw), reason)
    print("  Certificate has been revoked.")


def _generate(svc, auth) -> None:
    _header("Generate New Certificate")
    sid = _ask("Student ID")
    course = _ask("Course name")
    award_date = _ask("Award date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
    if not sid or not course or not award_date:
        print("  Student ID, Course Name, and Award Date are required.")
        return
    print("  Types: " + ", ".join(f"{i}) {t}" for i, t in enumerate(CERT_TYPES, 1)))
    raw = _ask("Certificate type", "1")
    cert_type = (CERT_TYPES[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(CERT_TYPES)
                 else raw.lower())
    issuer_default = (_current_user(auth) or {}).get("username", "")
    cert = svc.generate_certificate(
        student_id=sid, certificate_type=cert_type, course_name=course,
        award_date=award_date, grade=_ask("Grade (optional)") or None,
        additional_info=_ask("Additional info (optional)") or None,
        issued_by=_ask("Issued by", issuer_default) or None)
    print(f"\n  Certificate generated successfully!\n"
          f"  Certificate No: {cert.get('certificate_number', 'N/A')}")


def _verify(svc) -> None:
    number = _ask("Certificate number")
    if not number:
        print("  Enter a certificate number to verify.")
        return
    r = svc.verify_certificate(number)
    print(f"\n  {'[VALID]' if r.get('valid') else '[INVALID]'}\n")
    print(f"  Status:  {r.get('status', 'N/A')}")
    print(f"  Message: {r.get('message', '')}")
    if r.get("certificate_number"):
        for label, key in (("Certificate No", "certificate_number"),
                           ("Type", "certificate_type"), ("Student", "student_name"),
                           ("Course", "course_name"), ("Award Date", "award_date"),
                           ("Grade", "grade"), ("Issued By", "issued_by"),
                           ("Issued At", "issued_at")):
            if key == "grade" and not r.get(key):
                continue
            print(f"  {label + ':':<16} {r.get(key, 'N/A')}")


# ── Transcripts (cross-system, as the GUI's Transcripts tab) ─────────

def _transcript_service():
    from education_system.platform.features.transcript.transcript_service import (
        TranscriptService,
    )
    return TranscriptService()


def _show_transcript(tsvc, student_name: str) -> None:
    transcript = tsvc.generate_transcript(student_name)
    text = tsvc.format_transcript(transcript)
    print("\n" + text)
    while True:
        choice = _ask("S) Summary view · F) Save to file · Enter to go back").lower()
        if not choice:
            return
        if choice == "s":
            print("\n" + tsvc.get_transcript_summary(transcript.get("student_name", student_name)))
        elif choice == "f":
            path = Path(_ask("Save as", "transcript.txt")).expanduser()
            tsvc.save_transcript(text, str(path))
            print(f"  Transcript saved to: {path.resolve()}")


def _transcripts() -> None:
    from education_system.platform.features.transcript.transcript_service import SYSTEM_LABELS
    tsvc = _transcript_service()
    query = _ask("Student name to search (all systems)")
    if not query:
        print("  Please enter a student name.")
        return
    results = tsvc.search_students(query)
    if not results:
        print("  No students found.")
        return
    print()
    for i, r in enumerate(results, 1):
        print(f"  {i:>3}) {SYSTEM_LABELS.get(r['system'], r['system']):<20} "
              f"{str(r.get('student_id', '')):<12} {r.get('name', ''):<28} "
              f"{str(r.get('year_group', '')):<8} {r.get('status', '')}")
    raw = _ask("Number to show (Enter to go back)")
    if raw.isdigit() and 1 <= int(raw) <= len(results):
        name = results[int(raw) - 1].get("name", "")
        if name:
            _show_transcript(tsvc, name)


# ── Menus ────────────────────────────────────────────────────────────

def _run_student(db_path, auth) -> None:
    sid, name = _student_identity(auth)
    svc = _cert_service(db_path)
    while True:
        _header(f"My Certificates & Transcript — {name or sid}")
        print("  1) My certificates\n  2) Export one as HTML\n  3) My transcript\n  0) Back")
        choice = _ask("Select")
        if choice in ("0", ""):
            return
        try:
            if choice == "1":
                _print_certs(svc.list_certificates(student_id=sid), with_student=False)
            elif choice == "2":
                _export_html(svc, own_student_id=sid)
            elif choice == "3":
                _show_transcript(_transcript_service(), name or sid)
            else:
                print("  Invalid selection.")
                continue
        except Exception as e:  # noqa: BLE001 - keep the menu alive, as the GUI does
            print(f"  Error: {e}")
        _pause()


def run(db_path=None, auth=None) -> None:
    """Open the Certificates & Transcripts menu for the signed-in user."""
    if _is_student(auth):
        _run_student(db_path, auth)
        return
    svc = _cert_service(db_path)
    while True:
        _header("Certificates & Transcripts")
        print("  Certificates\n"
              "    1) Show all\n    2) Search by student\n"
              "    3) Export certificate as HTML\n    4) Revoke certificate\n"
              "  Transcripts\n    5) Find a learner's transcript (all systems)\n"
              "  Generate / Verify\n    6) Generate certificate\n    7) Verify certificate\n"
              "    0) Back")
        choice = _ask("Select")
        if choice in ("0", ""):
            return
        try:
            if choice == "1":
                _list_all(svc)
            elif choice == "2":
                _search(svc)
            elif choice == "3":
                _export_html(svc)
            elif choice == "4":
                _revoke(svc)
            elif choice == "5":
                _transcripts()
            elif choice == "6":
                _generate(svc, auth)
            elif choice == "7":
                _verify(svc)
            else:
                print("  Invalid selection.")
                continue
        except Exception as e:  # noqa: BLE001 - keep the menu alive, as the GUI does
            print(f"  Error: {e}")
        _pause()


__all__ = ["run"]
