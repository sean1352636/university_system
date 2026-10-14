"""CLI flows for Sixth Form Admissions."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import date as _date
from datetime import timedelta as _timedelta
from typing import Any, Callable
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    DECISION_REASONS,
    DEFAULT_OFFER_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DOCUMENT_TYPES,
    OFFER_TYPES,
    RECOMMENDATIONS,
    REFERENCE_STATUSES,
    SOURCES,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _input_validated(prompt: str, validator: Callable[[Any], Any], *,
                     default: str = "") -> str:
    """Prompt, re-prompting until the domain validator accepts (item 19)."""
    while True:
        val = _input(prompt, default=default)
        try:
            validator(val)
            return val
        except ValidationError as e:
            print(f"    ✗ {e} — try again (or 'cancel').")


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_subject(label: str, default: str | None = None) -> str | None:
    """Pick from the live subjects catalogue. Empty = skip."""
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        names = [s.name for s in _subjects.list_subjects()]
    except Exception:
        names = []
    if not names:
        return _input(label, default=default or "") or None
    return _pick_from(label, names, default=default)


def _pick_applicant() -> Applicant:
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or applicant id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            continue
        match = next((a for a in rows
                       if a.applicant_id.lower() == raw.lower()), None)
        if match:
            return match
        print("    No matching applicant.")


def _yes(prompt: str, *, default: str = "no") -> bool:
    return _input(f"{prompt} (y/n)", default=default).lower() in (
        "y", "yes")


def _pick_many_applicants() -> list[Applicant]:
    """Pick several applicants by comma-separated indices and/or ids."""
    rows = data.list_applicants()
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"[{a.status}]")
    raw = _input("  Pick numbers/ids (comma-separated)", allow_empty=False)
    picked: dict[str, Applicant] = {}
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        if tok.isdigit() and 1 <= int(tok) <= len(rows):
            a = rows[int(tok) - 1]
            picked[a.applicant_id] = a
        else:
            m = next((a for a in rows
                       if a.applicant_id.lower() == tok.lower()), None)
            if m:
                picked[m.applicant_id] = m
    if not picked:
        print("    Nothing matched.")
        raise _UserAbort
    return list(picked.values())


def _pick_grade(label: str) -> str:
    grades = ["A*", "A", "B", "C", "D", "E",
              "9", "8", "7", "6", "5", "4"]
    return _pick_from(label, grades)


def _age(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        d = _date.fromisoformat(dob[:10])
    except ValueError:
        return None
    t = _date.today()
    years = t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    return years if 0 <= years < 130 else None


def _days_in_stage(a: Applicant) -> int | None:
    try:
        d = _date.fromisoformat((a.updated_at or "")[:10])
    except ValueError:
        return None
    return max(0, (_date.today() - d).days)


# ── Print helpers ──────────────────────────────────────────────────

def _print_applicants(rows: list[Applicant], *, sort_by: str = "") -> None:
    if not rows:
        print("\n  (no applicants)")
        return
    rows = _sort_rows(rows, sort_by) if sort_by else rows
    print()
    print(f"  {'ID':<10}  {'Name':<22}  {'Age':>3}  {'Submitted':<10}  "
          f"{'Days':>4}  {'Status':<20}  Subjects")
    print("  " + "-" * 108)
    for a in rows:
        subj = ", ".join(a.subjects)[:28]
        age = _age(a.dob)
        days = _days_in_stage(a)
        flag = "!" if (a.is_open and days is not None and days >= 14) else " "
        print(f"  {a.applicant_id:<10}  {a.full_name[:22]:<22}  "
              f"{(str(age) if age is not None else '—'):>3}  "
              f"{a.submitted_at:<10}  "
              f"{(str(days) if days is not None else '—'):>3}{flag}  "
              f"{a.status:<20}  {subj}")
    # Status-count footer (item 10).
    counts: dict[str, int] = {}
    for a in rows:
        counts[a.status] = counts.get(a.status, 0) + 1
    tally = " · ".join(f"{counts[s]} {s}" for s in STATUSES if s in counts)
    print(f"\n  {len(rows)} shown  —  {tally}")


_SORT_KEYS: dict[str, Callable[[Applicant], Any]] = {
    "id": lambda a: a.applicant_id,
    "name": lambda a: a.full_name.lower(),
    "age": lambda a: _age(a.dob) if _age(a.dob) is not None else -1,
    "submitted": lambda a: a.submitted_at or "",
    "days": lambda a: _days_in_stage(a) if _days_in_stage(a)
    is not None else -1,
    "status": lambda a: a.status,
}


def _sort_rows(rows: list[Applicant], key: str) -> list[Applicant]:
    reverse = key.startswith("-")
    name = key.lstrip("-")
    fn = _SORT_KEYS.get(name)
    if fn is None:
        return rows
    return sorted(rows, key=fn, reverse=reverse)


# ── Sidecar JSON + shared helpers ──────────────────────────────────
# Small bits of GUI/CLI-only state (interview rooms, slot caps, saved
# views) live next to the admissions DB rather than in the schema.

ROOMS_FILE = "admissions_interview_rooms.json"
CONFIG_FILE = "admissions_config.json"
VIEWS_FILE = "admissions_saved_views.json"
DEFAULT_SLOT_CAP = 8
REQUIRED_DOCS = ("Personal Statement", "Reference Letter", "Transcript")

# Rough probability an applicant in a given open stage eventually enrols.
_ENROL_PROB = {
    "Submitted": 0.15, "Under Review": 0.25, "Interview Scheduled": 0.40,
    "Interviewed": 0.55, "Offer Made": 0.70, "Waitlisted": 0.20,
    "Offer Accepted": 0.95,
}


def _sidecar_path(name: str):
    from pathlib import Path
    return Path(data.DB_PATH).parent / name


def _load_json(name: str, default):
    p = _sidecar_path(name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a corrupt sidecar shouldn't break the CLI
        return default


def _store_json(name: str, obj) -> None:
    _sidecar_path(name).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _forecast_enrolment(applicants: list[Applicant]) -> dict:
    """Projected enrolments = already enrolled + expected from the pipeline."""
    enrolled = sum(1 for a in applicants if a.status == "Enrolled")
    expected = 0.0
    contributing = 0
    for a in applicants:
        p = _ENROL_PROB.get(a.status)
        if p:
            expected += p
            contributing += 1
    return {"enrolled": enrolled, "expected_additional": round(expected, 1),
            "projected_total": round(enrolled + expected),
            "in_pipeline": contributing}


def _merge_ics(applicant_ids: list[str]) -> tuple[str, int]:
    """Combine each applicant's single-event calendar into one VCALENDAR."""
    events: list[str] = []
    for aid in applicant_ids:
        try:
            cal = data.interview_to_ics(aid)
        except Exception:  # noqa: BLE001 — skip applicants without an interview
            continue
        start = cal.find("BEGIN:VEVENT")
        end = cal.find("END:VEVENT")
        if start != -1 and end != -1:
            events.append(cal[start:end + len("END:VEVENT")])
    body = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0",
                        "PRODID:-//SixthForm//Admissions//EN",
                        *events, "END:VCALENDAR"])
    return body + "\r\n", len(events)


def _send_to_printer(text: str) -> None:
    """Send plain text to the default printer (lpr / Windows print)."""
    if os.name == "nt":
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.startfile(path, "print")  # type: ignore[attr-defined]
        return
    proc = subprocess.run(["lpr"], input=text.encode("utf-8"),
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()
                           or f"lpr exited with status {proc.returncode}")


def _open_path(path: str) -> None:
    """Open a file with the OS default handler."""
    import sys
    if sys.platform.startswith("darwin"):
        subprocess.run(["open", path], check=False)
    elif os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", path], check=False)


def _write_applicants_pdf(path: str, rows: list[Applicant]) -> None:
    """Landscape-A4 table of applicants (mirrors the GUI export)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from education_system.platform import branding
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=8,
                          leading=9)

    def P(text: str):
        safe = (text or "—").replace("&", "&amp;").replace(
            "<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, cell)

    header = ["ID", "Name", "Age", "Status", "Offer", "Source", "Subjects"]
    table_rows: list[list] = [header]
    for a in rows:
        age = _age(a.dob)
        table_rows.append([
            a.applicant_id, P(a.full_name),
            str(age) if age is not None else "—", P(a.status),
            a.offer_type or "—", P(a.application_source),
            P(", ".join(a.subjects))])
    widths = [2, 4.2, 1.2, 3.2, 2.6, 3, 8]
    tbl = Table(table_rows, repeatRows=1, colWidths=[w * cm for w in widths])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=1 * cm,
                            rightMargin=1 * cm, topMargin=1 * cm,
                            bottomMargin=1 * cm)
    doc.build([
        Paragraph(f"{branding.SYSTEM_NAME} — Admissions", styles["Title"]),
        Paragraph(f"{len(rows)} applicant(s) · generated "
                  f"{_date.today().isoformat()}", styles["Normal"]),
        Spacer(1, 8), tbl])


def _write_summary_pdf(path: str) -> None:
    """Management summary PDF: headline + funnel + source effectiveness."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )
    from education_system.platform import branding
    styles = getSampleStyleSheet()
    summ = data.summary()
    elems = [Paragraph(f"{branding.SYSTEM_NAME} — Admissions summary",
                       styles["Title"]),
             Paragraph(f"Generated {_date.today().isoformat()}",
                       styles["Normal"]), Spacer(1, 10),
             Paragraph("Headline", styles["Heading2"])]
    head = [["Total", summ.total], ["Open", summ.open_count],
            ["Awaiting decision", summ.awaiting_decision],
            ["Pending offers", summ.pending_offers],
            ["Converted", summ.converted], ["Rejected", summ.rejected]]
    t1 = Table(head, colWidths=[6 * cm, 3 * cm])
    t1.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems += [t1, Spacer(1, 10),
              Paragraph("Conversion funnel", styles["Heading2"])]
    funnel_rows = [["Stage", "Count"]] + [[s, n] for s, n in data.funnel()]
    t2 = Table(funnel_rows, colWidths=[7 * cm, 3 * cm], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems += [t2, Spacer(1, 10),
              Paragraph("Source effectiveness", styles["Heading2"])]
    src_rows = [["Source", "Total", "Offers", "Enrolled", "Conv%"]]
    for d in data.source_effectiveness():
        src_rows.append([d["source"], d["total"], d["offers"],
                         d["enrolled"], f"{d['conversion']}%"])
    t3 = Table(src_rows, repeatRows=1,
               colWidths=[5 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2 * cm])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    elems.append(t3)
    SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm).build(elems)


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Applicants ═══")
    _print_applicants(data.list_applicants())
    _pause()


def list_open() -> None:
    print("\n═══ Open Applicants ═══")
    _print_applicants(data.list_applicants(open_only=True))
    _pause()


def filter_applicants() -> None:
    print("\n═══ Filter Applicants ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        source = _input(f"Source ({'/'.join(SOURCES)})") or None
        subject = _input("Subject contains") or None
        search = _input("Search (id/name/email)") or None
        date_from = _input("Submitted from (YYYY-MM-DD)") or None
        date_to = _input("Submitted to (YYYY-MM-DD)") or None
        open_raw = _input("Open only? (y/n)", default="n")
        offer_raw = _input("Has offer? (y/n)", default="n")
        enrolled_raw = _input("Enrolled only? (y/n)", default="n")
        sort_by = _input("Sort by (id/name/age/submitted/days/status; "
                          "prefix '-' for desc)") or ""
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_applicants(
            status=status, source=source, search=search,
            date_from=date_from, date_to=date_to,
            open_only=open_raw.lower() in ("y", "yes"),
            has_offer=offer_raw.lower() in ("y", "yes"),
            enrolled_only=enrolled_raw.lower() in ("y", "yes"),
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    if subject:
        rows = [a for a in rows
                if any(subject.lower() in s.lower() for s in a.subjects)]
    _print_applicants(rows, sort_by=sort_by)
    _pause()


def view_applicant() -> None:
    print("\n═══ View Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    ID                : {a.applicant_id}")
    print(f"    Name              : {a.full_name}")
    print(f"    DOB               : {a.dob or '—'}")
    print(f"    Email             : {a.email or '—'}")
    print(f"    Phone             : {a.phone or '—'}")
    print(f"    Address           : {a.address or '—'}")
    print(f"    Previous school   : {a.previous_school or '—'}")
    print(f"    Predicted GCSEs   : {a.predicted_gcses or '—'}")
    print(f"    Subjects          : "
          f"{', '.join(a.subjects) if a.subjects else '—'}")
    age = _age(a.dob)
    if age is not None:
        print(f"    Age               : {age}")
    print(f"    Reference         : {a.reference_name or '—'}  "
          f"({a.reference_contact or '—'})  [{a.reference_status}]")
    print(f"    Source            : {a.application_source}")
    print(f"    Submitted on      : {a.submitted_at}")
    print(f"    Status            : {a.status}"
          + (f"   (waitlist rank {a.waitlist_rank})"
             if a.waitlist_rank else ""))
    days = _days_in_stage(a)
    if days is not None:
        print(f"    Days in stage     : {days}")
    if a.follow_up:
        print("    Follow-up         : FLAGGED")
    if a.offer_type:
        print(f"    Offer             : {a.offer_type}"
              + (f"   expires {a.offer_expiry}" if a.offer_expiry else ""))
        if a.offer_conditions:
            print(f"      Conditions      : {a.offer_conditions}")
    if a.interview_date or a.interviewer or a.interview_notes:
        print(f"    Interview         : "
              f"{a.interview_date or '—'}  with "
              f"{a.interviewer or '—'}")
        if a.interview_notes:
            print(f"      Notes           : {a.interview_notes}")
    score = data.get_interview_score(a.applicant_id)
    if score:
        print(f"    Scorecard         : motivation {score.motivation or '—'}"
              f" · subject-fit {score.subject_fit or '—'}"
              f" · attainment {score.attainment or '—'}"
              f"  → avg {score.average if score.average is not None else '—'}"
              f"  (rec: {score.recommendation or '—'})")
    if a.decision_by or a.decision_date or a.decision_notes \
            or a.decision_reason:
        print(f"    Decision          : {a.decision_date or '—'} "
              f"by {a.decision_by or '—'}")
        if a.decision_reason:
            print(f"      Reason          : {a.decision_reason}")
        if a.decision_notes:
            print(f"      Notes           : {a.decision_notes}")
    if a.converted_student_id:
        print(f"    Enrolled student  : {a.converted_student_id}")
    concern = data.gcse_concern(a.predicted_gcses, a.offer_conditions)
    if concern:
        print(f"\n    ⚠ GCSE check      : {concern}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    _pause()


def _input_required_validated(prompt: str, validator: Callable[[Any], Any], *,
                              default: str = "") -> str:
    """Prompt until a non-blank value also passes the domain validator."""
    while True:
        val = _input(prompt, default=default, allow_empty=False)
        try:
            validator(val)
            return val
        except ValidationError as e:
            print(f"    ✗ {e} — try again (or 'cancel').")


def _reprompt_field(key: str, label: str,
                    existing: Applicant | None) -> Any:
    """Re-ask for a single required field, guaranteeing a valid, non-blank
    value. Dispatches by field type (if/elif)."""
    default = (getattr(existing, key, None) or "") if existing else ""
    if key in ("subject_1", "subject_2", "subject_3"):
        while True:
            val = _pick_subject(label, default=default or None)
            if val:
                return val
            print("    This subject is required.")
    elif key == "application_source":
        return _pick_from("Application source", list(SOURCES),
                           default=default or DEFAULT_SOURCE)
    elif key == "email":
        return _input_required_validated(label, data._validate_email,
                                          default=default)
    elif key == "phone":
        return _input_required_validated(label, data._validate_phone,
                                          default=default)
    elif key in ("dob", "submitted_at"):
        return _input_required_validated(
            f"{label} (YYYY-MM-DD)",
            lambda v: data._validate_date(v, label), default=default)
    else:
        return _input(label, default=default, allow_empty=False)


def _ensure_complete(payload: dict[str, Any],
                     existing: Applicant | None) -> None:
    """Block until every required field is filled, listing all that remain."""
    while True:
        missing = data.missing_required(payload)
        if not missing:
            return
        print(f"\n  ⚠ Required field(s) still missing: "
              f"{', '.join(missing)}")
        for key, label in data.REQUIRED_FIELDS:
            if label in missing:
                payload[key] = _reprompt_field(key, label, existing)


def _collect_form(existing: Applicant | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        print(f"\n  Editing applicant {existing.applicant_id}")
    payload["first_name"] = _input(
        "First name",
        default=(existing.first_name if is_edit else ""),
        allow_empty=False)
    payload["last_name"] = _input(
        "Last name",
        default=(existing.last_name if is_edit else ""),
        allow_empty=False)
    payload["dob"] = _input_validated(
        "Date of birth (YYYY-MM-DD)",
        lambda v: data._validate_date(v, "Date of birth"),
        default=(existing.dob or "") if is_edit else "")
    payload["email"] = _input_validated(
        "Email", data._validate_email,
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input_validated(
        "Phone", data._validate_phone,
        default=(existing.phone or "") if is_edit else "")
    payload["address"] = _input(
        "Address",
        default=(existing.address or "") if is_edit else "")
    payload["previous_school"] = _input(
        "Previous school",
        default=(existing.previous_school or "") if is_edit else "")
    payload["predicted_gcses"] = _input(
        "Predicted GCSEs",
        default=(existing.predicted_gcses or "") if is_edit else "")
    payload["subject_1"] = _pick_subject(
        "Subject 1",
        default=(existing.subject_1 if is_edit else None))
    payload["subject_2"] = _pick_subject(
        "Subject 2",
        default=(existing.subject_2 if is_edit else None))
    payload["subject_3"] = _pick_subject(
        "Subject 3",
        default=(existing.subject_3 if is_edit else None))
    payload["reference_name"] = _input(
        "Reference name",
        default=(existing.reference_name or "") if is_edit else "")
    payload["reference_contact"] = _input(
        "Reference contact",
        default=(existing.reference_contact or "") if is_edit else "")
    payload["application_source"] = _pick_from(
        "Application source", list(SOURCES),
        default=(existing.application_source if is_edit
                  else DEFAULT_SOURCE))
    payload["submitted_at"] = _input(
        "Submitted on (YYYY-MM-DD)",
        default=(existing.submitted_at if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    # Block submission until every required field is present (lists all).
    _ensure_complete(payload, existing)
    return payload


def new_applicant() -> None:
    print("\n═══ New Applicant ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Duplicate detection (item 15).
    dups = data.find_duplicates(
        email=payload.get("email") or None,
        first_name=payload.get("first_name"),
        last_name=payload.get("last_name"),
        dob=payload.get("dob") or None)
    if dups:
        print(f"\n  ⚠ {len(dups)} possible duplicate(s):")
        for d in dups:
            print(f"      {d.applicant_id} — {d.full_name} "
                  f"({d.email or 'no email'})")
        if not _yes("  Create anyway?"):
            print("\n  Cancelled.")
            return
    try:
        a = data.create_applicant(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created applicant {a.applicant_id} "
          f"({a.full_name}, {a.status})")
    _pause()


def edit_applicant() -> None:
    print("\n═══ Edit Applicant ═══")
    try:
        a = _pick_applicant()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_applicant(a.applicant_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {a.applicant_id}")
    _pause()


def schedule_interview_flow() -> None:
    print("\n═══ Schedule Interview ═══")
    try:
        a = _pick_applicant()
        date_str = _input("Interview date (YYYY-MM-DD)",
                            default=a.interview_date or "",
                            allow_empty=False)
        interviewer = _input("Interviewer",
                              default=a.interviewer or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule_interview(a.applicant_id,
                                  interview_date=date_str,
                                  interviewer=interviewer or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview scheduled for {a.applicant_id} on {date_str}")
    _pause()


def record_interview_flow() -> None:
    print("\n═══ Record Interview Notes ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview recorded for {a.applicant_id}")
    _pause()


def _build_conditions(a: Applicant) -> str:
    """Structured per-subject grade builder (item 29)."""
    parts: list[str] = []
    subjects = a.subjects or []
    for i in range(max(3, len(subjects))):
        default = subjects[i] if i < len(subjects) else ""
        subj = _input(f"Condition subject {i + 1} (blank to stop)",
                       default=default)
        if not subj:
            break
        grade = _pick_grade(f"Minimum grade for {subj}")
        parts.append(f"{subj} grade {grade} or above")
    return "; ".join(parts)


def make_offer_flow() -> None:
    print("\n═══ Make Offer ═══")
    try:
        a = _pick_applicant()
        offer_type = _pick_from(
            "Offer type", list(OFFER_TYPES), default=DEFAULT_OFFER_TYPE)
        if _yes("Build conditions from subjects + grades?"):
            conditions = _build_conditions(a)
            print(f"    Conditions: {conditions or '(none)'}")
        else:
            conditions = _input("Conditions",
                                  default=a.offer_conditions or "")
        decided_by = _input("Decided by", default=a.decision_by or "")
        expiry = _input("Offer expiry (YYYY-MM-DD, blank to skip)",
                         default=a.offer_expiry
                         or (_date.today()
                             + _timedelta(days=28)).isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.make_offer(a.applicant_id, offer_type=offer_type,
                          conditions=conditions or None,
                          decided_by=decided_by or None)
        if expiry:
            data.set_offer_expiry(a.applicant_id, expiry)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Offer ({offer_type}) made to {a.applicant_id}"
          + (f", expires {expiry}" if expiry else ""))
    _pause()


def accept_offer_flow() -> None:
    print("\n═══ Accept Offer ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.accept_offer(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} accepted offer")
    _pause()


def decline_offer_flow() -> None:
    print("\n═══ Decline Offer ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.decline_offer(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} declined offer")
    _pause()


def reject_flow() -> None:
    print("\n═══ Reject Applicant ═══")
    try:
        a = _pick_applicant()
        reason = _pick_from("Reason code", list(DECISION_REASONS))
        decided_by = _input("Decided by")
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_decision(a.applicant_id, "Rejected", reason=reason,
                              decided_by=decided_by or None,
                              notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} rejected ({reason})")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw Applicant ═══")
    try:
        a = _pick_applicant()
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(a.applicant_id, notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} withdrawn")
    _pause()


def convert_flow() -> None:
    print("\n═══ Convert to Student ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Pre-conversion checklist (items 37, 40).
    issues = data.pre_conversion_check(a.applicant_id)
    print("\n  Pre-conversion checklist:")
    if issues:
        for iss in issues:
            print(f"    ✗ {iss}")
        print("\n  Not ready to enrol.")
        _pause()
        return
    print("    ✓ Status is 'Offer Accepted'")
    print("    ✓ Three subjects selected")
    print("    ✓ Email on file")
    print("    ✓ Offer not expired")
    if _input(f"\n  Create a `students` row from {a.applicant_id} "
              f"({a.full_name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        updated, sid = data.convert_to_student(a.applicant_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Applicant {a.applicant_id} enrolled as student {sid}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_applicant()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.applicant_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ {a.applicant_id} → {new_status}")
    _pause()


def delete_applicant_flow() -> None:
    print("\n═══ Delete Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete applicant {a.applicant_id} ({a.full_name})? "
              f"Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_applicant(a.applicant_id):
        print(f"\n  ✓ Deleted {a.applicant_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Admissions Summary ═══")
    try:
        win = int(_input("Upcoming interview window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total applicants     : {summ.total}")
    print(f"  Open                 : {summ.open_count}")
    print(f"  Awaiting decision    : {summ.awaiting_decision}")
    print(f"  Pending offers       : {summ.pending_offers}")
    print(f"  Converted to student : {summ.converted}")
    print(f"  Rejected             : {summ.rejected}")
    print(f"  Upcoming interviews  : {summ.upcoming_interviews}  "
          f"(next {win} days)")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    print("\n  By source:")
    for s in SOURCES:
        n = summ.by_source.get(s, 0)
        if n:
            print(f"    {s:<22} : {n}")
    _pause()


# ── Presets & reports (items 3, 4, 9) ─────────────────────────────

def preset_awaiting() -> None:
    print("\n═══ Awaiting Decision ═══")
    rows = [a for a in data.list_applicants()
            if a.status in ("Under Review", "Interviewed")]
    _print_applicants(rows, sort_by="days")
    _pause()


def preset_offers_outstanding() -> None:
    print("\n═══ Offers Outstanding ═══")
    _print_applicants(data.list_applicants(status="Offer Made"),
                       sort_by="submitted")
    _pause()


def preset_interviews_this_week() -> None:
    print("\n═══ Interviews This Week ═══")
    today = _date.today()
    end = (today + _timedelta(days=7)).isoformat()
    rows = [a for a in data.list_applicants()
            if a.interview_date
            and today.isoformat() <= a.interview_date[:10] <= end]
    _print_applicants(rows, sort_by="submitted")
    _pause()


def stale_report() -> None:
    print("\n═══ Overdue / Stale Applicants (open ≥14 days in stage) ═══")
    rows = [a for a in data.list_applicants(open_only=True)
            if (_days_in_stage(a) or 0) >= 14]
    _print_applicants(rows, sort_by="-days")
    _pause()


# ── Bulk actions (items 2, 39) ────────────────────────────────────

def bulk_status_flow() -> None:
    print("\n═══ Bulk Change Status ═══")
    try:
        picks = _pick_many_applicants()
        new_status = _pick_from("New status for all", list(STATUSES))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.set_status(a.applicant_id, new_status)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ {ok} updated → {new_status}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_enrol_flow() -> None:
    print("\n═══ Bulk Enrol Accepted Offers ═══")
    accepted = data.list_applicants(status="Offer Accepted")
    if not accepted:
        print("\n  No applicants in 'Offer Accepted'.")
        _pause()
        return
    if not _yes(f"Attempt to enrol {len(accepted)} accepted applicant(s)?"):
        print("\n  Cancelled.")
        return
    done, skipped = [], []
    for a in accepted:
        issues = data.pre_conversion_check(a.applicant_id)
        if issues:
            skipped.append(f"{a.applicant_id}: {issues[0]}")
            continue
        try:
            _, sid = data.convert_to_student(a.applicant_id)
            done.append(f"{a.applicant_id} → {sid}")
        except Exception as e:  # noqa: BLE001
            skipped.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Enrolled {len(done)}:")
    for d in done:
        print(f"      {d}")
    if skipped:
        print("  Skipped:")
        for s in skipped:
            print(f"      {s}")
    _pause()


# ── Per-applicant operations (items 12–20, 38, 49, 50) ────────────

def timeline_flow(a: Applicant) -> None:
    print(f"\n═══ Timeline — {a.applicant_id} ═══")
    events = data.list_events(a.applicant_id)
    if not events:
        print("  (no events)")
    for e in events:
        print(f"    {e.at}  [{e.kind}]  {e.detail}")
    _pause()


def notes_flow(a: Applicant) -> None:
    print(f"\n═══ Notes — {a.applicant_id} ═══")
    for n in data.list_notes(a.applicant_id):
        print(f"    {n.at}  —  {n.author or 'unknown'}")
        print(f"      {n.body}")
    if _yes("\n  Add a note?"):
        author = _input("Author")
        body = _input("Note", allow_empty=False)
        data.add_note(a.applicant_id, body, author=author or None)
        print("  ✓ Note added.")
    _pause()


def documents_flow(a: Applicant) -> None:
    while True:
        print(f"\n═══ Documents — {a.applicant_id} ═══")
        docs = data.list_documents(a.applicant_id)
        for d in docs:
            print(f"    {d.id:>4})  [{d.doc_type}]  {d.label or '—'}")
            print(f"           {d.path}")
        if not docs:
            print("  (no documents)")
        choice = _input("\n  (a)dd, (r)emove, or Enter to go back",
                         default="")
        if choice.lower() == "a":
            try:
                path = _input("File path", allow_empty=False)
                doc_type = _pick_from("Type", list(DOCUMENT_TYPES))
                label = _input("Label (optional)")
                data.add_document(a.applicant_id, path, doc_type=doc_type,
                                  label=label or None)
                print("  ✓ Document attached.")
            except (ValidationError, _UserAbort) as e:
                print(f"  ✗ {e}")
        elif choice.lower() == "r":
            did = _input("Document id to remove", allow_empty=False)
            if did.isdigit() and data.remove_document(int(did)):
                print("  ✓ Removed.")
            else:
                print("  ✗ Not found.")
        else:
            return


def reference_flow(a: Applicant) -> None:
    print(f"\n═══ Reference — {a.applicant_id} ═══")
    print(f"    Referee : {a.reference_name or '—'} "
          f"({a.reference_contact or '—'})")
    print(f"    Status  : {a.reference_status}")
    print("\n    1) Set status   2) Chase referee   Enter) back")
    choice = _input("  Select", default="")
    if choice == "1":
        new = _pick_from("Reference status", list(REFERENCE_STATUSES),
                          default=a.reference_status)
        data.set_reference_status(a.applicant_id, new)
        print(f"  ✓ Reference status → {new}")
    elif choice == "2":
        if not a.reference_contact:
            print("  ✗ No referee contact on file.")
        else:
            data.set_reference_status(a.applicant_id, "Requested")
            print(f"\n  Reminder to {a.reference_name or 'referee'} "
                  f"({a.reference_contact}):")
            print(f"    We are still awaiting your reference for "
                  f"{a.full_name}. Status set to 'Requested'.")
    _pause()


def _capture_scorecard(a: Applicant) -> dict[str, Any]:
    existing = data.get_interview_score(a.applicant_id)

    def grade(attr: str) -> str:
        cur = getattr(existing, attr) if existing else None
        return _input(f"{attr.replace('_', ' ').title()} (1-5, blank=skip)",
                       default=str(cur) if cur else "")
    rec = _pick_from("Recommendation", ["(skip)"] + list(RECOMMENDATIONS))
    return {
        "motivation": grade("motivation") or None,
        "subject_fit": grade("subject_fit") or None,
        "attainment": grade("attainment") or None,
        "recommendation": None if rec == "(skip)" else rec,
        "scored_by": _input("Scored by") or None,
        "comments": _input("Comments") or None,
    }


def scorecard_flow(a: Applicant) -> None:
    print(f"\n═══ Interview Scorecard — {a.applicant_id} ═══")
    score = data.get_interview_score(a.applicant_id)
    if score:
        print(f"    Current avg: {score.average}  "
              f"(rec: {score.recommendation or '—'})")
    try:
        vals = _capture_scorecard(a)
        data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Scorecard saved.")
    _pause()


def gcse_check_flow(a: Applicant) -> None:
    print(f"\n═══ GCSE Check — {a.applicant_id} ═══")
    print(f"    Predicted  : {a.predicted_gcses or '—'}")
    print(f"    Conditions : {a.offer_conditions or '—'}")
    concern = data.gcse_concern(a.predicted_gcses, a.offer_conditions)
    print(f"\n    {'⚠ ' + concern if concern else '✓ No obvious concern.'}")
    _pause()


def offer_letter_flow(a: Applicant) -> None:
    print(f"\n═══ Offer Letter — {a.applicant_id} ═══")
    if not a.offer_type:
        print("  ✗ No offer has been made yet.")
        _pause()
        return
    letter = data.render_offer_letter(a.applicant_id)
    print("\n" + "\n".join("    " + ln for ln in letter.splitlines()))
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"offer_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(letter)
        print(f"  ✓ Saved to {path}")
    _pause()


def email_flow(a: Applicant) -> None:
    print(f"\n═══ Email — {a.applicant_id} ═══")
    subject, body = data.render_status_email(a.applicant_id)
    print(f"\n    Subject: {subject}\n")
    for ln in body.splitlines():
        print(f"    {ln}")
    if _yes("\n  Save to file?"):
        path = _input("Path", default=f"email_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"Subject: {subject}\n\n{body}")
        print(f"  ✓ Saved to {path}")
    _pause()


def open_student_flow(a: Applicant) -> None:
    print(f"\n═══ Linked Student — {a.applicant_id} ═══")
    if not a.converted_student_id:
        print("  ✗ This applicant has not been enrolled.")
        _pause()
        return
    from education_system.systems.sixth_form.domain.learners.students import (  # noqa: E501
        students as _students,
    )
    st = _students.get_student(a.converted_student_id)
    if st is None:
        print(f"  ✗ Student {a.converted_student_id} not found.")
    else:
        print(f"    Student ID : {st.student_id}")
        print(f"    Name       : {st.first_name} {st.last_name}")
        print(f"    Email      : {getattr(st, 'email', '—')}")
        print(f"    Subjects   : {getattr(st, 'subject_1', '—')}, "
              f"{getattr(st, 'subject_2', '—')}, "
              f"{getattr(st, 'subject_3', '—')}")
    _pause()


def find_duplicates_flow(a: Applicant) -> None:
    print(f"\n═══ Possible Duplicates — {a.applicant_id} ═══")
    dups = data.find_duplicates(email=a.email, first_name=a.first_name,
                                 last_name=a.last_name, dob=a.dob,
                                 exclude_id=a.applicant_id)
    if not dups:
        print("  ✓ None found.")
    for d in dups:
        print(f"    {d.applicant_id} — {d.full_name} "
              f"({d.email or 'no email'})")
    _pause()


def follow_up_flow(a: Applicant) -> None:
    new = not a.follow_up
    data.set_follow_up(a.applicant_id, new)
    print(f"\n  ✓ Follow-up flag {'set' if new else 'cleared'} for "
          f"{a.applicant_id}")
    _pause()


def manage_subjects_flow(a: Applicant) -> None:
    print(f"\n═══ Subjects — {a.applicant_id} ═══")
    subs = list(a.subjects)
    print(f"    Current: {', '.join(subs) if subs else '—'}")
    new = [
        _pick_subject("Subject 1", default=a.subject_1),
        _pick_subject("Subject 2", default=a.subject_2),
        _pick_subject("Subject 3", default=a.subject_3),
    ]
    try:
        data.update_applicant(a.applicant_id, {
            "subject_1": new[0], "subject_2": new[1], "subject_3": new[2]})
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print("  ✓ Subjects updated.")
    _pause()


def gdpr_export_flow(a: Applicant) -> None:
    print(f"\n═══ GDPR Export — {a.applicant_id} ═══")
    payload = json.dumps(data.gdpr_export(a.applicant_id), indent=2,
                          default=str)
    path = _input("Save JSON to path",
                   default=f"gdpr_{a.applicant_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    print(f"  ✓ Exported to {path}")
    _pause()


def gdpr_erase_flow(a: Applicant) -> None:
    print(f"\n═══ GDPR Erase — {a.applicant_id} ═══")
    print("  This permanently deletes the applicant and ALL related "
          "records/files.")
    if _input("  Type 'ERASE' to confirm", default="") != "ERASE":
        print("  Cancelled.")
        return
    data.erase_applicant(a.applicant_id)
    print(f"  ✓ All data for {a.applicant_id} erased.")
    _pause()


# ── Per-applicant action menu (item 7 — context-menu analogue) ────

def applicant_actions_flow() -> None:
    print("\n═══ Applicant Actions ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    actions: list[tuple[str, Callable[[], None]]] = [
        ("View record",        lambda: _view_inline(_fresh(a))),
        ("Timeline",           lambda: timeline_flow(_fresh(a))),
        ("Notes",              lambda: notes_flow(_fresh(a))),
        ("Documents / photo",  lambda: documents_flow(_fresh(a))),
        ("Reference status",   lambda: reference_flow(_fresh(a))),
        ("Interview scorecard", lambda: scorecard_flow(_fresh(a))),
        ("GCSE check",         lambda: gcse_check_flow(_fresh(a))),
        ("Manage subjects",    lambda: manage_subjects_flow(_fresh(a))),
        ("Toggle follow-up",   lambda: follow_up_flow(_fresh(a))),
        ("Missing documents",  lambda: missing_docs_flow(_fresh(a))),
        ("Preview / open document", lambda: document_preview_flow(_fresh(a))),
        ("Add several documents", lambda: bulk_upload_docs_flow(_fresh(a))),
        ("Communications log", lambda: communication_log_flow(_fresh(a))),
        ("Score vs cohort",    lambda: score_comparison_flow(_fresh(a))),
        ("─" * 6,              lambda: None),
        ("Quick standard offer", lambda: quick_offer_flow(_fresh(a))),
        ("Offer status / expiry", lambda: offer_expiry_flow(_fresh(a))),
        ("Offer letter",       lambda: offer_letter_flow(_fresh(a))),
        ("Print offer letter", lambda: print_offer_letter_flow(_fresh(a))),
        ("Email applicant",    lambda: email_flow(_fresh(a))),
        ("Custom email",       lambda: custom_email_flow(_fresh(a))),
        ("Open student record", lambda: open_student_flow(_fresh(a))),
        ("Find duplicates",    lambda: find_duplicates_flow(_fresh(a))),
        ("GDPR export",        lambda: gdpr_export_flow(_fresh(a))),
        ("GDPR erase",         lambda: gdpr_erase_flow(_fresh(a))),
    ]
    _run_submenu(f"Actions — {a.applicant_id} {a.full_name}", actions)


def _fresh(a: Applicant) -> Applicant:
    """Re-read the applicant so each action sees the latest state."""
    return data.get_applicant(a.applicant_id) or a


def _view_inline(a: Applicant) -> None:
    print()
    print(f"    {a.applicant_id}  {a.full_name}  [{a.status}]")
    print(f"    Email {a.email or '—'} · Phone {a.phone or '—'} · "
          f"Age {_age(a.dob) if _age(a.dob) is not None else '—'}")
    print(f"    Subjects: {', '.join(a.subjects) or '—'}")
    print(f"    Reference: {a.reference_status} · Follow-up: "
          f"{'yes' if a.follow_up else 'no'}")
    if a.offer_type:
        print(f"    Offer: {a.offer_type} "
              f"(expires {a.offer_expiry or '—'}) — {a.offer_conditions or '—'}")
    _pause()


# ── Interviews (items 21–28) ──────────────────────────────────────

def interviews_agenda_flow() -> None:
    print("\n═══ Interview Agenda ═══")
    rows = [a for a in data.list_applicants() if a.interview_date]
    rows.sort(key=lambda a: (a.interview_date or "",
                              a.interviewer or "", a.full_name))
    if not rows:
        print("  (no scheduled interviews)")
        _pause()
        return
    # Clash detection (item 23): same interviewer + same day.
    from collections import Counter
    slots = Counter((a.interview_date, a.interviewer)
                    for a in rows if a.interviewer)
    clashes = {k for k, n in slots.items() if n > 1}
    current = None
    for a in rows:
        if a.interview_date != current:
            current = a.interview_date
            print(f"\n  ── {a.interview_date} ──")
        flag = "  ⚠CLASH" if (a.interview_date, a.interviewer) in clashes \
            else ""
        print(f"      {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"{a.interviewer or '—':<16}  [{a.status}]{flag}")
    # Interviewer workload (item 22).
    print("\n  Interviewer load:")
    load = Counter(a.interviewer or "(unassigned)" for a in rows)
    for who, n in sorted(load.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"      {who:<20} {n}")
    _pause()


def record_outcome_flow() -> None:
    print("\n═══ Record Interview Outcome ═══")
    try:
        a = _pick_applicant()
        notes = _input("Interview notes", default=a.interview_notes or "")
        do_score = _yes("Add a scorecard?", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_interview(a.applicant_id, interview_notes=notes or None)
        if do_score:
            vals = _capture_scorecard(a)
            data.save_interview_score(a.applicant_id, **vals)
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Outcome recorded for {a.applicant_id}")
    _pause()


def reschedule_flow() -> None:
    print("\n═══ Reschedule Interview ═══")
    try:
        a = _pick_applicant()
        new_date = _input("New date (YYYY-MM-DD)",
                           default=a.interview_date or "", allow_empty=False)
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    # Clash warning (item 23).
    clash = [x for x in data.list_applicants()
             if x.interviewer and x.interviewer == a.interviewer
             and x.interview_date == new_date
             and x.applicant_id != a.applicant_id]
    if clash and not _yes(
            f"  {a.interviewer} already has "
            f"{', '.join(x.full_name for x in clash)} on {new_date}. "
            f"Proceed?"):
        print("\n  Cancelled.")
        return
    try:
        data.reschedule_interview(a.applicant_id, new_date=new_date,
                                   reason=reason or None,
                                   interviewer=a.interviewer)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Rescheduled {a.applicant_id} to {new_date}")
    _pause()


def cancel_interview_flow() -> None:
    print("\n═══ Cancel Interview ═══")
    try:
        a = _pick_applicant()
        reason = _input("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    data.cancel_interview(a.applicant_id, reason=reason or None)
    print(f"\n  ✓ Interview cancelled for {a.applicant_id} "
          f"(returned to Under Review)")
    _pause()


def no_show_flow() -> None:
    print("\n═══ Record No-Show ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    data.mark_no_show(a.applicant_id, follow_up=True)
    print(f"\n  ✓ {a.applicant_id} marked no-show (flagged for follow-up)")
    _pause()


def export_ics_flow() -> None:
    print("\n═══ Export Interview (.ics) ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ics = data.interview_to_ics(a.applicant_id)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    path = _input("Save to path", default=f"interview_{a.applicant_id}.ics")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ics)
    print(f"  ✓ Saved to {path}")
    _pause()


# ── Waitlist & decision day (items 34, 35) ────────────────────────

def waitlist_flow() -> None:
    while True:
        print("\n═══ Waitlist ═══")
        wl = data.get_waitlist()
        if not wl:
            print("  (waitlist empty)")
        for i, a in enumerate(wl, 1):
            print(f"    {i:>2}) rank {a.waitlist_rank or '—':<3}  "
                  f"{a.applicant_id}  {a.full_name[:24]:<24}  "
                  f"{', '.join(a.subjects)[:30]}")
        print("\n    (u)p / (d)own <n>, (o)ffer <n>, (r)emove <n>, "
              "Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if cmd in ("u", "d") and idx is not None and 0 <= idx < len(wl):
            data.move_waitlist(wl[idx].applicant_id,
                                -1 if cmd == "u" else 1)
        elif cmd == "o" and idx is not None and 0 <= idx < len(wl):
            make_offer_for(wl[idx])
        elif cmd == "r" and idx is not None and 0 <= idx < len(wl):
            data.set_waitlist_rank(wl[idx].applicant_id, None)
        else:
            print("  ✗ Unrecognised action.")


def make_offer_for(a: Applicant) -> None:
    try:
        offer_type = _pick_from("Offer type", list(OFFER_TYPES),
                                 default=DEFAULT_OFFER_TYPE)
        conditions = _input("Conditions", default=a.offer_conditions or "")
        data.make_offer(a.applicant_id, offer_type=offer_type,
                          conditions=conditions or None)
        print(f"  ✓ Offer made to {a.applicant_id}")
    except (ValidationError, _UserAbort) as e:
        print(f"  ✗ {e}")


def decision_day_flow() -> None:
    print("\n═══ Decision Day (Interviewed queue) ═══")
    queue = data.list_applicants(status="Interviewed")
    if not queue:
        print("  No applicants awaiting a decision.")
        _pause()
        return
    for n, a in enumerate(queue, 1):
        a = data.get_applicant(a.applicant_id)
        if a is None:
            continue
        score = data.get_interview_score(a.applicant_id)
        print(f"\n  [{n}/{len(queue)}] {a.applicant_id} — {a.full_name}")
        print(f"      Subjects: {', '.join(a.subjects) or '—'}")
        print(f"      Predicted: {a.predicted_gcses or '—'}")
        if score:
            print(f"      Scorecard avg {score.average}  "
                  f"(rec: {score.recommendation or '—'})")
        print("      1) Make offer  2) Waitlist  3) Reject  "
              "4) Skip  0) Finish")
        choice = _input("  Decision", default="4")
        decided_by = ""
        try:
            if choice == "0":
                break
            if choice == "1":
                cond = _input("Conditions")
                decided_by = _input("Decided by")
                data.make_offer(a.applicant_id, conditions=cond or None,
                                 decided_by=decided_by or None)
                print("      ✓ Offer made.")
            elif choice == "2":
                data.set_status(a.applicant_id, "Waitlisted")
                data.set_waitlist_rank(a.applicant_id,
                                        len(data.get_waitlist()))
                print("      ✓ Waitlisted.")
            elif choice == "3":
                reason = _pick_from("Reason", list(DECISION_REASONS))
                data.record_decision(a.applicant_id, "Rejected",
                                      reason=reason)
                print("      ✓ Rejected.")
        except (ValidationError, _UserAbort) as e:
            print(f"      ✗ {e}")
    print("\n  Decision day complete.")
    _pause()


def expiring_offers_flow() -> None:
    print("\n═══ Expiring Offers ═══")
    try:
        days = int(_input("Within how many days?", default="7"))
    except (ValueError, _UserAbort):
        return
    rows = data.list_expiring_offers(within_days=days)
    if not rows:
        print(f"  No offers expiring within {days} days.")
    for a in rows:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24}  "
              f"expires {a.offer_expiry}")
    _pause()


# ── Analytics (items 41–46) ───────────────────────────────────────

def analytics_flow() -> None:
    print("\n═══ Admissions Analytics ═══")
    fn = data.funnel()
    top = fn[0][1] if fn else 0
    print("\n  Conversion funnel:")
    for stage, n in fn:
        bar = "█" * (round(30 * n / top) if top else 0)
        pct = f"{round(100 * n / top)}%" if top else "—"
        print(f"    {stage:<20} {n:>4} {pct:>4}  {bar}")

    print("\n  Source effectiveness:")
    print(f"    {'Source':<18}{'Total':>6}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for d in data.source_effectiveness():
        print(f"    {d['source']:<18}{d['total']:>6}{d['offers']:>8}"
              f"{d['enrolled']:>10}{d['conversion']:>7}%")

    ttd = data.time_to_decision_stats()
    print("\n  Time to decision (days):")
    if ttd["count"]:
        print(f"    n={ttd['count']}  avg={ttd['avg']}  "
              f"median={ttd['median']}  min={ttd['min']}  max={ttd['max']}")
    else:
        print("    (no decisions yet)")

    print("\n  Applications by week:")
    weeks = data.applications_by_week()[-10:]
    wmax = max((n for _, n in weeks), default=0)
    for wk, n in weeks:
        print(f"    {wk:<10} {n:>4} {'█' * (round(20 * n / wmax) if wmax else 0)}")
    if not weeks:
        print("    (none)")

    print("\n  Subject demand:")
    for subj, n in data.subject_demand()[:15]:
        print(f"    {subj:<28} {n:>4}")

    # Drill-down (item 46).
    if _yes("\n  Drill down into a status?"):
        status = _pick_from("Status", list(STATUSES))
        _print_applicants(data.list_applicants(status=status))
    _pause()


# ── CSV import / export (items 47, 48) ────────────────────────────

def export_csv_flow() -> None:
    print("\n═══ Export Applicants to CSV ═══")
    path = _input("Save to path", default="applicants.csv")
    try:
        n = data.export_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {n} applicant(s) to {path}")
    _pause()


def import_csv_flow() -> None:
    print("\n═══ Import Applicants from CSV ═══")
    path = _input("CSV path", allow_empty=False)
    try:
        created, errors = data.import_csv(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Imported {created} applicant(s).")
    for err in errors[:12]:
        print(f"    ✗ {err}")
    if len(errors) > 12:
        print(f"    … and {len(errors) - 12} more.")
    _pause()


# ══ Bulk & selection flows (GUI items 1–15) ═══════════════════════
# Item 1 (bulk change status) is already covered by bulk_status_flow.

def bulk_reject_flow() -> None:
    """Item 2 — reject several applicants with one shared reason."""
    print("\n═══ Bulk Reject ═══")
    try:
        picks = _pick_many_applicants()
        reason = _pick_from("Shared rejection reason", list(DECISION_REASONS))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.record_decision(a.applicant_id, "Rejected", reason=reason)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ {ok} rejected — {reason}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_add_note_flow() -> None:
    """Item 3 — append the same note to several applicants."""
    print("\n═══ Bulk Add Note ═══")
    try:
        picks = _pick_many_applicants()
        body = _input("Note to append to each", allow_empty=False)
        author = _input("Author", default="admissions-cli")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.add_note(a.applicant_id, body, author=author or None)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Note added to {ok} applicant(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_set_source_flow() -> None:
    """Item 4 — correct the application source across a selection."""
    print("\n═══ Bulk Set Source ═══")
    try:
        picks = _pick_many_applicants()
        source = _pick_from("New application source", list(SOURCES))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.update_applicant(a.applicant_id,
                                  {"application_source": source})
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Source set to {source} for {ok} applicant(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def bulk_assign_interviewer_flow() -> None:
    """Item 5 — assign one interviewer to several applicants."""
    print("\n═══ Bulk Assign Interviewer ═══")
    try:
        picks = _pick_many_applicants()
        who = _input("Interviewer name (blank clears)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.update_applicant(a.applicant_id,
                                  {"interviewer": who or None})
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Interviewer '{who or '(cleared)'}' set for {ok}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def _do_merge(primary: Applicant, other: Applicant) -> None:
    fields = ("dob", "email", "phone", "address", "previous_school",
              "predicted_gcses", "subject_1", "subject_2", "subject_3",
              "reference_name", "reference_contact")
    fill = {f: getattr(other, f) for f in fields
            if not getattr(primary, f) and getattr(other, f)}
    if fill:
        data.update_applicant(primary.applicant_id, fill)
    for note in reversed(data.list_notes(other.applicant_id)):
        data.add_note(primary.applicant_id,
                      f"[merged from {other.applicant_id}] {note.body}",
                      author=note.author)
    data.add_note(primary.applicant_id,
                  f"Merged duplicate {other.applicant_id} "
                  f"({other.full_name}).", author="admissions-cli")
    data.delete_applicant(other.applicant_id)
    print(f"\n  ✓ Merged {other.applicant_id} into {primary.applicant_id} "
          f"({len(fill)} field(s) filled).")


def merge_duplicates_flow() -> None:
    """Item 6 — merge a duplicate record into a kept applicant."""
    print("\n═══ Merge Duplicates ═══")
    try:
        primary = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    dupes = data.find_duplicates(
        email=primary.email, first_name=primary.first_name,
        last_name=primary.last_name, dob=primary.dob,
        exclude_id=primary.applicant_id)
    if not dupes:
        print(f"  No potential duplicates for {primary.applicant_id}.")
        _pause()
        return
    print(f"\n  Potential duplicates of {primary.applicant_id} "
          f"({primary.full_name}):")
    for i, d in enumerate(dupes, 1):
        print(f"    {i:>2}) {d.applicant_id}  {d.full_name[:24]:<24}  "
              f"{d.email or 'no email'}")
    try:
        raw = _input(f"  Merge which #1..{len(dupes)} into "
                     f"{primary.applicant_id}?", allow_empty=False)
        if not raw.isdigit() or not (1 <= int(raw) <= len(dupes)):
            print("  ✗ Invalid choice.")
            _pause()
            return
        other = dupes[int(raw) - 1]
        if not _yes(f"Merge {other.applicant_id} into "
                    f"{primary.applicant_id} and delete it?"):
            print("\n  Cancelled.")
            return
        _do_merge(primary, other)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _pause()


def duplicate_report_flow() -> None:
    """Item 7 — list applicants sharing an email or phone."""
    print("\n═══ Duplicate Report ═══")
    from collections import defaultdict
    by_key: dict[tuple[str, str], list[Applicant]] = defaultdict(list)
    for a in data.list_applicants():
        if a.email and a.email.strip():
            by_key[("email", a.email.strip().lower())].append(a)
        if a.phone and a.phone.strip():
            by_key[("phone", a.phone.strip())].append(a)
    groups = [(k, v) for k, v in by_key.items() if len(v) > 1]
    if not groups:
        print("  No shared email/phone found.")
        _pause()
        return
    for (kind, val), members in groups:
        print(f"\n  Shared {kind}: {val}")
        for a in members:
            print(f"      {a.applicant_id}  {a.full_name[:24]:<24}  "
                  f"[{a.status}]")
    _pause()


def saved_views_flow() -> None:
    """Item 8 — save/apply/delete named filter presets."""
    while True:
        views = _load_json(VIEWS_FILE, {})
        print("\n═══ Saved Views ═══")
        names = sorted(views)
        for i, name in enumerate(names, 1):
            v = views[name]
            print(f"    {i:>2}) {name}  "
                  f"(status={v.get('status') or 'any'}, "
                  f"source={v.get('source') or 'any'}, "
                  f"sort={v.get('sort') or '—'})")
        if not names:
            print("    (no saved views)")
        print("\n    (a)pply <n>, (s)ave new, (d)elete <n>, Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if cmd == "s":
            try:
                name = _input("View name", allow_empty=False)
                status = _pick_from("Status", ["(any)"] + list(STATUSES))
                source = _pick_from("Source", ["(any)"] + list(SOURCES))
                sort = _pick_from("Sort by",
                                  ["(none)", "name", "age", "submitted",
                                   "days", "status"])
            except _UserAbort:
                continue
            views[name] = {
                "status": "" if status == "(any)" else status,
                "source": "" if source == "(any)" else source,
                "sort": "" if sort == "(none)" else sort}
            _store_json(VIEWS_FILE, views)
        elif cmd == "a" and idx is not None and 0 <= idx < len(names):
            v = views[names[idx]]
            rows = data.list_applicants(status=v.get("status") or None,
                                        source=v.get("source") or None)
            _print_applicants(rows, sort_by=v.get("sort") or "")
            _pause()
        elif cmd == "d" and idx is not None and 0 <= idx < len(names):
            views.pop(names[idx], None)
            _store_json(VIEWS_FILE, views)
        else:
            print("  ✗ Unrecognised action.")


def column_chooser_flow() -> None:
    """Item 9 — choose which columns to show, then list applicants."""
    print("\n═══ Choose Columns ═══")
    all_cols = [("id", "ID"), ("name", "Name"), ("age", "Age"),
                ("submitted", "Submitted"), ("days", "Days"),
                ("status", "Status"), ("offer", "Offer"),
                ("source", "Source"), ("subjects", "Subjects")]
    for i, (_, label) in enumerate(all_cols, 1):
        print(f"    {i:>2}) {label}")
    raw = _input("  Columns to show (comma-separated numbers, blank=all)",
                 default="")
    if raw.strip():
        picks = [all_cols[int(t) - 1][0] for t in raw.replace(" ", "").split(",")
                 if t.isdigit() and 1 <= int(t) <= len(all_cols)]
    else:
        picks = [c for c, _ in all_cols]
    if not picks:
        print("  ✗ No valid columns.")
        _pause()
        return
    rows = data.list_applicants()

    def cell(a: Applicant, col: str) -> str:
        age = _age(a.dob)
        days = _days_in_stage(a)
        return {
            "id": a.applicant_id, "name": a.full_name[:22],
            "age": str(age) if age is not None else "—",
            "submitted": a.submitted_at or "—",
            "days": str(days) if days is not None else "—",
            "status": a.status, "offer": a.offer_type or "—",
            "source": a.application_source,
            "subjects": ", ".join(a.subjects)[:28]}.get(col, "")

    header = {"id": "ID", "name": "Name", "age": "Age",
              "submitted": "Submitted", "days": "Days", "status": "Status",
              "offer": "Offer", "source": "Source", "subjects": "Subjects"}
    print()
    print("  " + "  ".join(f"{header[c]:<14}" for c in picks))
    print("  " + "-" * (16 * len(picks)))
    for a in rows:
        print("  " + "  ".join(f"{cell(a, c):<14}" for c in picks))
    print(f"\n  {len(rows)} shown.")
    _pause()


def quick_search_flow() -> None:
    """Item 10 — search applicants by id / name / email."""
    print("\n═══ Quick Search ═══")
    try:
        q = _input("Search (id / name / email)", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = [a for a in data.list_applicants()
            if q in a.applicant_id.lower() or q in a.full_name.lower()
            or (a.email and q in a.email.lower())]
    _print_applicants(rows)
    _pause()


def email_list_flow() -> None:
    """Item 11 — collect a selection's email addresses."""
    print("\n═══ Email List ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    emails = [a.email for a in picks if a.email and a.email.strip()]
    if not emails:
        print("  None of the selected applicants have an email address.")
        _pause()
        return
    joined = "; ".join(emails)
    print(f"\n  {len(emails)} address(es):\n\n  {joined}")
    if _yes("\n  Save to a file?"):
        path = _input("Save to path", default="emails.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(joined + "\n")
        print(f"  ✓ Saved to {path}")
    _pause()


def export_pdf_flow() -> None:
    """Item 12 — export a selection to a formatted PDF."""
    print("\n═══ Export Selection to PDF ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    path = _input("Save PDF to path", default="applicants.pdf")
    try:
        _write_applicants_pdf(path, picks)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {len(picks)} applicant(s) to {path}")
    _pause()


def print_list_flow() -> None:
    """Item 13 — send the applicant list to the default printer."""
    print("\n═══ Print Applicant List ═══")
    rows = data.list_applicants()
    if not rows:
        print("  (nothing to print)")
        _pause()
        return
    lines = [f"Admissions — {len(rows)} applicants — "
             f"{_date.today().isoformat()}", "",
             f"{'ID':<8} {'Name':<22} {'Age':>3} {'Status':<18} Subjects"]
    for a in rows:
        age = _age(a.dob)
        lines.append(f"{a.applicant_id:<8} {a.full_name[:22]:<22} "
                     f"{(str(age) if age is not None else '—'):>3} "
                     f"{a.status:<18} {', '.join(a.subjects)}")
    try:
        _send_to_printer("\n".join(lines) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Could not print: {e}")
        _pause()
        return
    print(f"  ✓ Sent {len(rows)} applicant(s) to the default printer.")
    _pause()


def bulk_follow_up_flow() -> None:
    """Item 14 — set/clear the follow-up flag on a selection."""
    print("\n═══ Bulk Follow-up ═══")
    try:
        picks = _pick_many_applicants()
        flag = _yes("Turn follow-up ON? (n = clear)", default="y")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for a in picks:
        try:
            data.set_follow_up(a.applicant_id, flag)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Follow-up {'set' if flag else 'cleared'} on {ok}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def age_filter_flow() -> None:
    """Item 15 — filter applicants by an age range."""
    print("\n═══ Filter by Age ═══")
    try:
        lo_s = _input("Min age (blank = none)")
        hi_s = _input("Max age (blank = none)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    lo = int(lo_s) if lo_s.isdigit() else None
    hi = int(hi_s) if hi_s.isdigit() else None
    rows = []
    for a in data.list_applicants():
        age = _age(a.dob)
        if age is None:
            continue
        if lo is not None and age < lo:
            continue
        if hi is not None and age > hi:
            continue
        rows.append(a)
    _print_applicants(rows, sort_by="age")
    _pause()


# ══ Interview flows (GUI items 16–25) ═════════════════════════════

def _scheduled() -> list[Applicant]:
    rows = [a for a in data.list_applicants() if a.interview_date]
    rows.sort(key=lambda a: (a.interview_date or "", a.interviewer or "",
                             a.full_name))
    return rows


def calendar_view_flow() -> None:
    """Item 16 — month calendar of interview counts."""
    import calendar
    from collections import Counter
    print("\n═══ Interview Calendar ═══")
    ym = _input("Month (YYYY-MM)", default=_date.today().strftime("%Y-%m"))
    try:
        year, month = (int(x) for x in ym.split("-")[:2])
    except (ValueError, IndexError):
        print("  ✗ Invalid month.")
        _pause()
        return
    counts = Counter(a.interview_date[:10] for a in _scheduled()
                     if a.interview_date)
    print(f"\n  {calendar.month_name[month]} {year}")
    print("   Mon   Tue   Wed   Thu   Fri   Sat   Sun")
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(year,
                                                                    month):
        cells = []
        for day in week:
            if day == 0:
                cells.append("     ")
            else:
                iso = f"{year:04d}-{month:02d}-{day:02d}"
                n = counts.get(iso, 0)
                cells.append(f"{day:>2}·{n}" if n else f"{day:>2}  ")
        print("  " + " ".join(f"{c:<5}" for c in cells))
    _pause()


def bulk_schedule_flow() -> None:
    """Item 17 — schedule the unscheduled pool into sequential days."""
    print("\n═══ Bulk Schedule ═══")
    pool = (data.list_applicants(status="Submitted")
            + data.list_applicants(status="Under Review"))
    if not pool:
        print("  No applicants in 'Submitted' / 'Under Review'.")
        _pause()
        return
    try:
        start = _input(f"Schedule {len(pool)} applicant(s) from date "
                       f"(YYYY-MM-DD)", default=_date.today().isoformat())
        per_day = int(_input("Interviews per day",
                             default=str(DEFAULT_SLOT_CAP)))
        who = _input("Interviewer for all (blank = unset)")
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    try:
        start_d = _date.fromisoformat(start)
    except ValueError:
        print("  ✗ Invalid start date.")
        _pause()
        return
    if per_day < 1 or not _yes(f"Schedule {len(pool)}, {per_day}/day, "
                               f"from {start_d}?"):
        print("\n  Cancelled.")
        return
    ok, fail = 0, []
    for i, a in enumerate(pool):
        day = start_d + _timedelta(days=i // per_day)
        try:
            data.schedule_interview(a.applicant_id,
                                    interview_date=day.isoformat(),
                                    interviewer=who or None)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Scheduled {ok} of {len(pool)}.")
    for f in fail[:12]:
        print(f"  ✗ {f}")
    _pause()


def send_reminders_flow() -> None:
    """Item 18 — generate interview reminders for a given day."""
    print("\n═══ Send Interview Reminders ═══")
    default = (_date.today() + _timedelta(days=1)).isoformat()
    target = _input("Reminders for date (YYYY-MM-DD)", default=default)
    rooms = _load_json(ROOMS_FILE, {})
    due = [a for a in _scheduled()
           if a.interview_date and a.interview_date[:10] == target[:10]]
    if not due:
        print(f"  No interviews scheduled on {target}.")
        _pause()
        return
    lines = [f"Interview reminders for {target} ({len(due)})", "=" * 52, ""]
    for a in due:
        room = rooms.get(a.applicant_id, "TBC")
        lines += [f"To: {a.email or '(no email on file)'}",
                  f"Subject: Your sixth-form interview on {a.interview_date}",
                  "", f"Dear {a.first_name},", "",
                  f"Reminder: interview on {a.interview_date}. Interviewer: "
                  f"{a.interviewer or 'TBC'}. Room: {room}.",
                  "", "Please arrive 10 minutes early with your ID.",
                  "", "-" * 52, ""]
    text = "\n".join(lines)
    print("\n" + text)
    if _yes("Save to a file?"):
        path = _input("Save to path", default=f"reminders_{target}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"  ✓ Saved to {path}")
    _pause()


def export_all_ics_flow() -> None:
    """Item 19 — one combined .ics for every scheduled interview."""
    print("\n═══ Export All Interviews (.ics) ═══")
    rows = _scheduled()
    if not rows:
        print("  (no scheduled interviews)")
        _pause()
        return
    body, n = _merge_ics([a.applicant_id for a in rows])
    path = _input("Save to path", default="interviews.ics")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"  ✓ Wrote {n} interview event(s) to {path}")
    _pause()


def detect_clashes_flow() -> None:
    """Item 20 — report interviewer double-bookings."""
    print("\n═══ Detect Clashes ═══")
    from collections import Counter
    rows = _scheduled()
    slots = Counter((a.interview_date, a.interviewer)
                    for a in rows if a.interviewer)
    clashes = {k for k, v in slots.items() if v > 1}
    if not clashes:
        print("  No interviewer double-bookings.")
        _pause()
        return
    for date, who in sorted(clashes):
        members = [a for a in rows
                   if a.interview_date == date and a.interviewer == who]
        print(f"\n  {date}  {who}  ×{len(members)}")
        for a in members:
            print(f"      {a.applicant_id}  {a.full_name}")
    _pause()


def room_assignment_flow() -> None:
    """Item 21 — assign an interview room to an applicant."""
    print("\n═══ Assign Interview Room ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rooms = _load_json(ROOMS_FILE, {})
    room = _input(f"Room for {a.full_name}'s interview",
                  default=rooms.get(a.applicant_id, ""))
    if room:
        rooms[a.applicant_id] = room
        print(f"  ✓ Room set to '{room}'.")
    else:
        rooms.pop(a.applicant_id, None)
        print("  ✓ Room cleared.")
    _store_json(ROOMS_FILE, rooms)
    _pause()


def panel_view_flow() -> None:
    """Item 22 — scheduled interviews grouped by interviewer."""
    print("\n═══ Interview Panels ═══")
    by_who: dict[str, list[Applicant]] = {}
    for a in _scheduled():
        by_who.setdefault(a.interviewer or "(unassigned)", []).append(a)
    if not by_who:
        print("  (no scheduled interviews)")
        _pause()
        return
    for who in sorted(by_who):
        print(f"\n  {who}  ({len(by_who[who])})")
        for a in by_who[who]:
            print(f"      {a.interview_date or '—'}  {a.applicant_id}  "
                  f"{a.full_name[:24]:<24}  [{a.status}]")
    _pause()


def no_show_report_flow() -> None:
    """Item 23 — applicants flagged for follow-up / no-show."""
    print("\n═══ No-Show / Follow-up Report ═══")
    flagged = [a for a in data.list_applicants() if a.follow_up]
    if not flagged:
        print("  (nobody currently flagged for follow-up)")
        _pause()
        return
    for a in flagged:
        print(f"    {a.applicant_id}  {a.full_name[:24]:<24}  [{a.status}]  "
              f"interview {a.interview_date or '—'}  {a.email or ''}")
    print(f"\n  {len(flagged)} flagged.")
    _pause()


def reschedule_batch_flow() -> None:
    """Item 24 — shift every interview on a day by N days."""
    print("\n═══ Reschedule a Whole Day ═══")
    day = _input("Interview date to shift (YYYY-MM-DD)",
                 default=_date.today().isoformat())
    affected = [a for a in _scheduled()
                if a.interview_date and a.interview_date[:10] == day[:10]]
    if not affected:
        print(f"  No interviews on {day}.")
        _pause()
        return
    try:
        shift = int(_input(f"Shift all {len(affected)} interview(s) by how "
                           f"many days?", default="1"))
        base = _date.fromisoformat(day[:10])
    except (ValueError, _UserAbort):
        print("\n  Cancelled.")
        return
    new_day = (base + _timedelta(days=shift)).isoformat()
    ok, fail = 0, []
    for a in affected:
        try:
            data.reschedule_interview(a.applicant_id, new_date=new_day,
                                      reason=f"Day moved {shift:+d}d",
                                      interviewer=a.interviewer)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    print(f"\n  ✓ Moved {ok} interview(s) to {new_day}.")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def slot_capacity_flow() -> None:
    """Item 25 — daily interview capacity vs bookings."""
    print("\n═══ Slot Capacity ═══")
    from collections import Counter
    cfg = _load_json(CONFIG_FILE, {})
    cap = int(cfg.get("daily_slot_cap", DEFAULT_SLOT_CAP))
    new = _input("Daily slot cap", default=str(cap))
    if new.isdigit() and int(new) != cap:
        cap = int(new)
        cfg["daily_slot_cap"] = cap
        _store_json(CONFIG_FILE, cfg)
    counts = Counter(a.interview_date[:10] for a in _scheduled()
                     if a.interview_date)
    print(f"\n  Daily cap: {cap} slot(s)\n")
    for day in sorted(counts):
        used = counts[day]
        free = cap - used
        flag = "  ⚠ OVER" if free < 0 else ""
        print(f"    {day}   used {used:>2}  free {free:>3}{flag}")
    if not counts:
        print("    (no interviews scheduled)")
    _pause()


# ══ Analytics flows (GUI items 26–35) ═════════════════════════════

def funnel_report_flow() -> None:
    """Item 26 — conversion funnel."""
    print("\n═══ Conversion Funnel ═══")
    fn = data.funnel()
    top = fn[0][1] if fn else 0
    for stage, n in fn:
        bar = "█" * (round(30 * n / top) if top else 0)
        pct = f"{round(100 * n / top)}%" if top else "—"
        print(f"    {stage:<20} {n:>4} {pct:>4}  {bar}")
    if not fn:
        print("    (no data)")
    _pause()


def source_report_flow() -> None:
    """Item 27 — source effectiveness."""
    print("\n═══ Source Effectiveness ═══")
    print(f"    {'Source':<18}{'Total':>6}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for d in data.source_effectiveness():
        print(f"    {d['source']:<18}{d['total']:>6}{d['offers']:>8}"
              f"{d['enrolled']:>10}{d['conversion']:>7}%")
    _pause()


def weekly_trend_flow() -> None:
    """Item 28 — applications by week."""
    print("\n═══ Applications by Week ═══")
    weeks = data.applications_by_week()[-12:]
    wmax = max((n for _, n in weeks), default=0)
    for wk, n in weeks:
        bar = "█" * (round(24 * n / wmax) if wmax else 0)
        print(f"    {wk:<10} {n:>4}  {bar}")
    if not weeks:
        print("    (no applications)")
    _pause()


def subject_demand_flow() -> None:
    """Item 29 — subject demand."""
    print("\n═══ Subject Demand ═══")
    rows = data.subject_demand()
    dmax = rows[0][1] if rows else 0
    for subj, n in rows[:20]:
        bar = "█" * (round(24 * n / dmax) if dmax else 0)
        print(f"    {subj:<28} {n:>4}  {bar}")
    if not rows:
        print("    (no subject choices recorded)")
    _pause()


def time_to_decision_flow() -> None:
    """Item 30 — time-to-decision statistics."""
    print("\n═══ Time to Decision (days) ═══")
    ttd = data.time_to_decision_stats()
    if ttd["count"]:
        print(f"    n={ttd['count']}  avg={ttd['avg']}  "
              f"median={ttd['median']}  min={ttd['min']}  max={ttd['max']}")
    else:
        print("    (no decisions recorded yet)")
    _pause()


def conversion_kpi_flow() -> None:
    """Item 31 — headline offer→enrol conversion."""
    print("\n═══ Conversion KPI ═══")
    apps = data.list_applicants()
    enrolled = sum(1 for a in apps if a.status == "Enrolled")
    offers = sum(1 for a in apps
                 if a.offer_type and a.offer_type != "Not Offered")
    pct = round(100 * enrolled / offers) if offers else 0
    print(f"    Offer → Enrol conversion : {pct}%")
    print(f"    Enrolled                 : {enrolled}")
    print(f"    Offers made              : {offers}")
    _pause()


def cohort_compare_flow() -> None:
    """Item 32 — compare cohorts by application year."""
    print("\n═══ Cohort Comparison ═══")
    by_year: dict[str, dict[str, int]] = {}
    for a in data.list_applicants():
        year = (a.submitted_at or "????")[:4]
        d = by_year.setdefault(year, {"total": 0, "offers": 0,
                                      "enrolled": 0})
        d["total"] += 1
        if a.offer_type and a.offer_type != "Not Offered":
            d["offers"] += 1
        if a.status == "Enrolled":
            d["enrolled"] += 1
    print(f"\n    {'Year':<6}{'Total':>7}{'Offers':>8}"
          f"{'Enrolled':>10}{'Conv%':>8}")
    for year in sorted(by_year):
        d = by_year[year]
        conv = round(100 * d["enrolled"] / d["offers"]) if d["offers"] else 0
        print(f"    {year:<6}{d['total']:>7}{d['offers']:>8}"
              f"{d['enrolled']:>10}{conv:>7}%")
    if not by_year:
        print("    (no applicants)")
    _pause()


def export_summary_pdf_flow() -> None:
    """Item 33 — management summary PDF."""
    print("\n═══ Export Summary PDF ═══")
    path = _input("Save PDF to path", default="admissions_summary.pdf")
    try:
        _write_summary_pdf(path)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Saved to {path}")
    _pause()


def forecast_flow() -> None:
    """Item 34 — projected enrolment from the pipeline."""
    print("\n═══ Enrolment Forecast ═══")
    f = _forecast_enrolment(data.list_applicants())
    print(f"    Already enrolled     : {f['enrolled']}")
    print(f"    Expected additional  : {f['expected_additional']}  "
          f"(from {f['in_pipeline']} in pipeline)")
    print(f"    Projected total      : ~{f['projected_total']}")
    _pause()


def live_analytics_flow() -> None:
    """Item 35 — auto-refreshing analytics until interrupted."""
    print("\n═══ Live Analytics (Ctrl-C to stop) ═══")
    import time
    try:
        every = int(_input("Refresh every N seconds", default="30"))
    except (ValueError, _UserAbort):
        return
    try:
        while True:
            f = _forecast_enrolment(data.list_applicants())
            fn = data.funnel()
            print(f"\n  [{_date.today().isoformat()}]  projected ~"
                  f"{f['projected_total']} enrolments")
            for stage, n in fn:
                print(f"      {stage:<20} {n}")
            time.sleep(max(1, every))
    except KeyboardInterrupt:
        print("\n  Stopped.")


# ══ Per-applicant flows (GUI items 36–45) ═════════════════════════

def custom_email_flow(a: Applicant) -> None:
    """Item 36 — compose a custom email from the status template."""
    print(f"\n═══ Custom Email — {a.applicant_id} ═══")
    try:
        subject, body = data.render_status_email(a.applicant_id)
    except Exception:  # noqa: BLE001
        subject, body = "", f"Dear {a.first_name},\n\n"
    print(f"  To: {a.email or '(no email on file)'}")
    subject = _input("Subject", default=subject)
    print("  Enter body lines; end with a single '.' on its own line:")
    print("  (template shown below — retype or edit)")
    for line in body.splitlines():
        print(f"    | {line}")
    lines: list[str] = []
    while True:
        try:
            line = input("  | ")
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == ".":
            break
        lines.append(line)
    final_body = "\n".join(lines) if lines else body
    composed = f"To: {a.email or ''}\nSubject: {subject}\n\n{final_body}\n"
    print("\n  ── Composed email ──\n")
    print(composed)
    if _yes("Save to a file?"):
        path = _input("Save to path", default=f"email_{a.applicant_id}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(composed)
        print(f"  ✓ Saved to {path}")
    _pause()


def offer_expiry_flow(a: Applicant) -> None:
    """Item 37 — offer expiry countdown, set/extend, remind."""
    print(f"\n═══ Offer Status — {a.applicant_id} ═══")
    if not a.offer_type or a.offer_type == "Not Offered":
        print("  No offer has been made.")
        _pause()
        return
    if a.offer_expiry:
        try:
            exp = _date.fromisoformat(a.offer_expiry[:10])
            days = (exp - _date.today()).days
            state = ("EXPIRED" if days < 0 else f"{days} day(s) remaining")
        except ValueError:
            state = "unknown"
        print(f"  Offer {a.offer_type} expires {a.offer_expiry} — {state}")
    else:
        print(f"  Offer {a.offer_type} has no expiry date.")
    if _yes("Set / extend the expiry date?"):
        default = (_date.today() + _timedelta(days=14)).isoformat()
        new = _input("Expiry date (YYYY-MM-DD, blank clears)",
                     default=a.offer_expiry or default)
        try:
            data.set_offer_expiry(a.applicant_id, new.strip() or None)
            print("  ✓ Expiry updated.")
        except ValidationError as e:
            print(f"  ✗ {e}")
    _pause()


def reference_chase_all_flow() -> None:
    """Item 38 — chase every outstanding reference system-wide."""
    print("\n═══ Chase All Outstanding References ═══")
    outstanding = [a for a in data.list_applicants()
                   if a.reference_status in ("Not requested", "Requested")
                   and a.reference_contact]
    if not outstanding:
        print("  No outstanding references with a contact on file.")
        _pause()
        return
    if not _yes(f"Mark {len(outstanding)} reference(s) as 'Requested' and "
                f"build a chase list?"):
        print("\n  Cancelled.")
        return
    lines = [f"Reference chase list ({len(outstanding)})", "=" * 52, ""]
    for a in outstanding:
        try:
            data.set_reference_status(a.applicant_id, "Requested")
        except Exception:  # noqa: BLE001
            pass
        lines.append(f"To: {a.reference_contact}  (re: {a.full_name}, "
                     f"{a.applicant_id})")
    text = "\n".join(lines)
    print("\n" + text)
    if _yes("Save to a file?"):
        path = _input("Save to path", default="reference_chase.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"  ✓ Saved to {path}")
    _pause()


def print_offer_letter_flow(a: Applicant) -> None:
    """Item 39 — send the offer letter to the printer."""
    print(f"\n═══ Print Offer Letter — {a.applicant_id} ═══")
    if not a.offer_type:
        print("  No offer has been made yet.")
        _pause()
        return
    try:
        _send_to_printer(data.render_offer_letter(a.applicant_id))
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Could not print: {e}")
        _pause()
        return
    print("  ✓ Offer letter sent to the default printer.")
    _pause()


def document_preview_flow(a: Applicant) -> None:
    """Item 40 — inspect / open a document with the OS handler."""
    print(f"\n═══ Document Preview — {a.applicant_id} ═══")
    docs = data.list_documents(a.applicant_id)
    if not docs:
        print("  (no documents)")
        _pause()
        return
    for i, d in enumerate(docs, 1):
        print(f"    {i:>2}) [{d.doc_type}]  {d.label or '—'}  —  {d.path}")
    raw = _input(f"  Open which #1..{len(docs)} (blank = none)", default="")
    if raw.isdigit() and 1 <= int(raw) <= len(docs):
        d = docs[int(raw) - 1]
        print(f"  Opening {d.path} …")
        try:
            _open_path(d.path)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {e}")
    _pause()


def bulk_upload_docs_flow(a: Applicant) -> None:
    """Item 41 — attach several documents at once."""
    print(f"\n═══ Add Several Documents — {a.applicant_id} ═══")
    raw = _input("File paths (comma-separated)", allow_empty=False)
    paths = [p.strip() for p in raw.split(",") if p.strip()]
    if not paths:
        print("  ✗ No paths given.")
        _pause()
        return
    try:
        doc_type = _pick_from("Type for all", list(DOCUMENT_TYPES))
    except _UserAbort:
        return
    added, fail = 0, []
    for p in paths:
        try:
            data.add_document(a.applicant_id, p, doc_type=doc_type)
            added += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{os.path.basename(p)}: {e}")
    print(f"\n  ✓ Added {added} document(s).")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def missing_docs_flow(a: Applicant) -> None:
    """Item 42 — required-document checklist."""
    print(f"\n═══ Required Documents — {a.applicant_id} ═══")
    present = {d.doc_type for d in data.list_documents(a.applicant_id)}
    for req in REQUIRED_DOCS:
        ok = req in present
        print(f"    {'✓' if ok else '✗'}  {req}")
    missing = [r for r in REQUIRED_DOCS if r not in present]
    print(f"\n  {len(missing)} missing." if missing else "\n  All present.")
    _pause()


def score_comparison_flow(a: Applicant) -> None:
    """Item 43 — interview score vs the cohort average."""
    print(f"\n═══ Score vs Cohort — {a.applicant_id} ═══")
    mine = data.get_interview_score(a.applicant_id)
    if mine is None or mine.average is None:
        print("  This applicant has no interview score yet.")
        _pause()
        return
    averages = []
    for other in data.list_applicants():
        s = data.get_interview_score(other.applicant_id)
        if s is not None and s.average is not None:
            averages.append(s.average)
    cohort = round(sum(averages) / len(averages), 1) if averages else 0
    rank = sum(1 for v in averages if v > mine.average) + 1
    print(f"    Applicant average : {mine.average}")
    print(f"    Cohort average    : {cohort}  (n={len(averages)})")
    print(f"    Difference        : {round(mine.average - cohort, 1):+}")
    print(f"    Rank              : {rank} of {len(averages)}")
    _pause()


def communication_log_flow(a: Applicant) -> None:
    """Item 44 — merged notes + communication events."""
    print(f"\n═══ Communications — {a.applicant_id} ═══")
    entries: list[tuple[str, str, str]] = []
    for n in data.list_notes(a.applicant_id):
        entries.append((n.at, "note", f"{n.author or 'unknown'}: {n.body}"))
    for e in data.list_events(a.applicant_id):
        if e.kind in ("note", "email", "offer", "status", "reference"):
            entries.append((e.at, e.kind, e.detail))
    entries.sort(key=lambda t: t[0], reverse=True)
    if not entries:
        print("  (no communications recorded)")
    for at, kind, detail in entries:
        print(f"    {at}  [{kind}]  {detail}")
    _pause()


def quick_offer_flow(a: Applicant) -> None:
    """Item 45 — one-step standard conditional offer."""
    print(f"\n═══ Quick Standard Offer — {a.applicant_id} ═══")
    conditions = "Achieve at least grade 6 in your chosen subjects."
    if not _yes(f"Make a standard {DEFAULT_OFFER_TYPE} offer "
                f"(conditions: {conditions})?"):
        print("\n  Cancelled.")
        return
    try:
        data.make_offer(a.applicant_id, offer_type=DEFAULT_OFFER_TYPE,
                        conditions=conditions, decided_by="admissions-cli")
        print("  ✓ Offer made.")
    except ValidationError as e:
        print(f"  ✗ {e}")
    _pause()


# ══ Cross-cutting flows (GUI items 46–50) ═════════════════════════

def offers_flow() -> None:
    """Item 46 — pending offers with expiry alerts + quick decisions."""
    while True:
        print("\n═══ Pending Offers ═══")
        rows = data.list_applicants(status="Offer Made")
        if not rows:
            print("  (no pending offers)")
            _pause()
            return
        today = _date.today()
        for i, a in enumerate(rows, 1):
            left = "—"
            flag = ""
            if a.offer_expiry:
                try:
                    d = (_date.fromisoformat(a.offer_expiry[:10])
                         - today).days
                    left = str(d)
                    flag = "  ⚠" if d <= 7 else ""
                except ValueError:
                    pass
            print(f"    {i:>2}) {a.applicant_id}  {a.full_name[:22]:<22}  "
                  f"{a.offer_type or '—':<12} expires "
                  f"{a.offer_expiry or '—'} ({left}d){flag}")
        print("\n    (a)ccept <n>, (d)ecline <n>, (e)xpiry <n>, Enter) back")
        raw = _input("  Action", default="")
        if not raw:
            return
        parts = raw.split()
        cmd = parts[0].lower()
        idx = int(parts[1]) - 1 if len(parts) > 1 and parts[1].isdigit() \
            else None
        if idx is None or not (0 <= idx < len(rows)):
            print("  ✗ Give a row number, e.g. 'a 2'.")
            continue
        a = rows[idx]
        try:
            if cmd == "a":
                data.set_status(a.applicant_id, "Offer Accepted")
                print(f"  ✓ {a.applicant_id} accepted.")
            elif cmd == "d":
                data.set_status(a.applicant_id, "Offer Declined")
                print(f"  ✓ {a.applicant_id} declined.")
            elif cmd == "e":
                new = _input("Expiry (YYYY-MM-DD, blank clears)",
                             default=a.offer_expiry or "")
                data.set_offer_expiry(a.applicant_id, new.strip() or None)
                print("  ✓ Expiry updated.")
            else:
                print("  ✗ Unrecognised action.")
        except ValidationError as e:
            print(f"  ✗ {e}")


def tasks_flow() -> None:
    """Item 47 — actionable worklist across the pipeline."""
    print("\n═══ Tasks ═══")
    apps = data.list_applicants()
    today = _date.today()

    def show(title: str, items: list[str]) -> None:
        print(f"\n  {title}  ({len(items)})")
        for line in items:
            print(f"      {line}")
        if not items:
            print("      (none)")

    refs = [f"{a.applicant_id}  {a.full_name} — reference "
            f"{a.reference_status}"
            for a in apps
            if a.reference_status in ("Not requested", "Requested")
            and a.is_open]
    follow = [f"{a.applicant_id}  {a.full_name} — [{a.status}]"
              for a in apps if a.follow_up]
    expiring = []
    for a in apps:
        if a.status == "Offer Made" and a.offer_expiry:
            try:
                d = (_date.fromisoformat(a.offer_expiry[:10]) - today).days
                if d <= 7:
                    expiring.append(f"{a.applicant_id}  {a.full_name} — "
                                    f"expires {a.offer_expiry} ({d}d)")
            except ValueError:
                pass
    awaiting = [f"{a.applicant_id}  {a.full_name}"
                for a in apps if a.status == "Interviewed"]
    unscheduled = [f"{a.applicant_id}  {a.full_name}"
                   for a in apps
                   if a.status == "Under Review" and not a.interview_date]
    show("Outstanding references", refs)
    show("Flagged for follow-up / no-show", follow)
    show("Offers expiring ≤7 days", expiring)
    show("Interviewed — awaiting decision", awaiting)
    show("Under review — no interview booked", unscheduled)
    total = len(refs) + len(follow) + len(expiring) + len(awaiting) \
        + len(unscheduled)
    print(f"\n  {total} open task(s).")
    _pause()


def waitlist_auto_promote_flow() -> None:
    """Item 48 — offer to the top-ranked waitlisted applicant."""
    print("\n═══ Auto-Promote Top of Waitlist ═══")
    rows = data.get_waitlist()
    if not rows:
        print("  The waitlist is empty.")
        _pause()
        return
    top = rows[0]
    if not _yes(f"A place has opened — make an offer to {top.applicant_id} "
                f"({top.full_name}, rank {top.waitlist_rank or 1})?"):
        print("\n  Cancelled.")
        return
    try:
        data.make_offer(top.applicant_id, offer_type=DEFAULT_OFFER_TYPE,
                        conditions="Promoted from waitlist.",
                        decided_by="admissions-cli")
        data.set_waitlist_rank(top.applicant_id, None)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Offer made to {top.applicant_id} and removed from waitlist.")
    _pause()


def gdpr_batch_export_flow() -> None:
    """Item 49 — export several applicants' GDPR bundles to one file."""
    print("\n═══ GDPR Batch Export ═══")
    try:
        picks = _pick_many_applicants()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    path = _input("Save JSON to path", default="gdpr_batch.json")
    bundle, fail = {}, []
    for a in picks:
        try:
            bundle[a.applicant_id] = data.gdpr_export(a.applicant_id)
        except Exception as e:  # noqa: BLE001
            fail.append(f"{a.applicant_id}: {e}")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(bundle, fh, indent=2, default=str)
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ {e}")
        _pause()
        return
    print(f"  ✓ Exported {len(bundle)} bundle(s) to {path}")
    for f in fail:
        print(f"  ✗ {f}")
    _pause()


def activity_feed_flow(limit: int = 100) -> None:
    """Item 50 — global recent-events stream across all applicants."""
    print("\n═══ Activity Feed ═══")
    events = []
    for a in data.list_applicants():
        for e in data.list_events(a.applicant_id):
            events.append((e.at, a.applicant_id, e.kind, e.detail))
    events.sort(key=lambda t: t[0], reverse=True)
    if not events:
        print("  (no activity recorded)")
    for at, aid, kind, detail in events[:limit]:
        print(f"    {at}  {aid:<8} [{kind}]  {detail}")
    _pause()


# ── Menus ─────────────────────────────────────────────────────────

def _run_submenu(title: str,
                 items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print("  Invalid selection.")
            continue
        label, handler = items[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:  # noqa: BLE001
            logger.exception("Admissions CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


_BROWSE_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List All",                 list_all),
    ("List Open",                list_open),
    ("Filter (sort/subject/…)",  filter_applicants),
    ("Preset: Awaiting decision", preset_awaiting),
    ("Preset: Offers outstanding", preset_offers_outstanding),
    ("Preset: Interviews this week", preset_interviews_this_week),
    ("Report: Overdue / stale",  stale_report),
]

_BROWSE_MENU += [
    ("Quick search",             quick_search_flow),
    ("Filter by age range",      age_filter_flow),
    ("Choose columns…",          column_chooser_flow),
    ("Saved views…",             saved_views_flow),
    ("Duplicate report",         duplicate_report_flow),
    ("Activity feed",            activity_feed_flow),
]

_BULK_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk change status",       bulk_status_flow),
    ("Bulk reject (shared reason)", bulk_reject_flow),
    ("Bulk add note",            bulk_add_note_flow),
    ("Bulk set source",          bulk_set_source_flow),
    ("Bulk assign interviewer",  bulk_assign_interviewer_flow),
    ("Bulk toggle follow-up",    bulk_follow_up_flow),
    ("─" * 6,                    lambda: None),
    ("Copy email list",          email_list_flow),
    ("Export selection to PDF",  export_pdf_flow),
    ("Print applicant list",     print_list_flow),
    ("GDPR batch export",        gdpr_batch_export_flow),
    ("Merge duplicates",         merge_duplicates_flow),
]

_APPLICANT_MENU: list[tuple[str, Callable[[], None]]] = [
    ("View",                     view_applicant),
    ("New Applicant",            new_applicant),
    ("Edit Applicant",           edit_applicant),
    ("Actions… (per applicant)", applicant_actions_flow),
    ("─" * 6,                    lambda: None),
    ("Bulk & selection…",        lambda: _run_submenu("Bulk & Selection",
                                                       _BULK_MENU)),
    ("Delete Applicant",         delete_applicant_flow),
]

_INTERVIEW_TOOLS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Calendar (month)",         calendar_view_flow),
    ("Panel view (by interviewer)", panel_view_flow),
    ("Slot capacity",            slot_capacity_flow),
    ("Detect clashes",           detect_clashes_flow),
    ("─" * 6,                    lambda: None),
    ("Bulk schedule",            bulk_schedule_flow),
    ("Reschedule a whole day",   reschedule_batch_flow),
    ("Assign room",              room_assignment_flow),
    ("─" * 6,                    lambda: None),
    ("Send reminders",           send_reminders_flow),
    ("No-show report",           no_show_report_flow),
    ("Export all .ics",          export_all_ics_flow),
]

_INTERVIEW_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Agenda (with clashes/load)", interviews_agenda_flow),
    ("Schedule Interview",       schedule_interview_flow),
    ("Record outcome (+ score)", record_outcome_flow),
    ("Record interview notes",   record_interview_flow),
    ("Reschedule",               reschedule_flow),
    ("Cancel",                   cancel_interview_flow),
    ("No-show",                  no_show_flow),
    ("Export .ics",              export_ics_flow),
    ("─" * 6,                    lambda: None),
    ("More tools…",              lambda: _run_submenu("Interview Tools",
                                                      _INTERVIEW_TOOLS_MENU)),
]

_OFFER_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Make Offer (+ builder/expiry)", make_offer_flow),
    ("Accept Offer",             accept_offer_flow),
    ("Decline Offer",            decline_offer_flow),
    ("Reject (with reason)",     reject_flow),
    ("Withdraw",                 withdraw_flow),
    ("Change Status",            set_status_flow),
    ("─" * 6,                    lambda: None),
    ("Pending offers…",          offers_flow),
    ("Waitlist (rank/promote)",  waitlist_flow),
    ("Auto-promote top of waitlist", waitlist_auto_promote_flow),
    ("Decision day",             decision_day_flow),
    ("Expiring offers",          expiring_offers_flow),
    ("Chase all references",     reference_chase_all_flow),
]

_CONVERSION_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Convert to Student (checklist)", convert_flow),
    ("Bulk enrol accepted",      bulk_enrol_flow),
]

_ANALYTICS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Full dashboard",           analytics_flow),
    ("Conversion funnel",        funnel_report_flow),
    ("Source effectiveness",     source_report_flow),
    ("Applications by week",     weekly_trend_flow),
    ("Subject demand",           subject_demand_flow),
    ("Time to decision",         time_to_decision_flow),
    ("Conversion KPI",           conversion_kpi_flow),
    ("Cohort comparison",        cohort_compare_flow),
    ("Enrolment forecast",       forecast_flow),
    ("Live analytics (watch)",   live_analytics_flow),
    ("Export summary PDF",       export_summary_pdf_flow),
]

_DATA_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Summary",                  summary_flow),
    ("Analytics…",               lambda: _run_submenu("Analytics",
                                                       _ANALYTICS_MENU)),
    ("Tasks (worklist)",         tasks_flow),
    ("─" * 6,                    lambda: None),
    ("Export CSV",               export_csv_flow),
    ("Import CSV",               import_csv_flow),
]

_MAIN_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Browse & search…",   lambda: _run_submenu("Browse", _BROWSE_MENU)),
    ("Applicants…",        lambda: _run_submenu("Applicants",
                                                 _APPLICANT_MENU)),
    ("Interviews…",        lambda: _run_submenu("Interviews",
                                                 _INTERVIEW_MENU)),
    ("Offers & decisions…", lambda: _run_submenu("Offers & Decisions",
                                                  _OFFER_MENU)),
    ("Conversion…",        lambda: _run_submenu("Conversion",
                                                 _CONVERSION_MENU)),
    ("Reports & data…",    lambda: _run_submenu("Reports & Data",
                                                 _DATA_MENU)),
]


def run() -> None:
    _run_submenu("Admissions", _MAIN_MENU)


def dispatch(label: str) -> bool:
    if label != "Admissions":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Admissions CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
