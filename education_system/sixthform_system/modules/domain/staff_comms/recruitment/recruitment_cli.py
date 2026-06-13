"""CLI flows for Sixth Form Recruitment."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.staff_comms.recruitment import (
    recruitment as data,
)
from education_system.sixthform_system.modules.domain.staff_comms.recruitment.recruitment import (
    APPLICANT_SOURCES,
    APPLICANT_STATUSES,
    Applicant,
    CONTRACT_TYPES,
    DEFAULT_APPLICANT_SOURCE,
    DEFAULT_APPLICANT_STATUS,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_ROLE_TYPE,
    DEFAULT_VACANCY_STATUS,
    ROLE_TYPES,
    VACANCY_STATUSES,
    Vacancy,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_vacancy() -> Vacancy:
    rows = data.list_vacancies()
    if not rows:
        print("    No vacancies yet.")
        raise _UserAbort
    print("\n  Vacancies:")
    for i, v in enumerate(rows, 1):
        n_app = data.applicant_count(v.vacancy_id)
        print(f"    {i:>3}) #{v.vacancy_id}  "
              f"{v.title[:32]:<32}  "
              f"{v.role_type[:18]:<18}  "
              f"closing {v.closing_date or '—'}  "
              f"[{v.status}]  {n_app} appl.")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.vacancy_id == n), None)
            if match:
                return match
        print("    No matching vacancy.")


def _pick_applicant(vacancy_id: int | None = None) -> Applicant:
    rows = (data.list_applicants(vacancy_id=vacancy_id)
            if vacancy_id is not None
            else data.list_applicants())
    if not rows:
        print("    No applicants.")
        raise _UserAbort
    print("\n  Applicants:")
    for i, a in enumerate(rows, 1):
        mark = "*" if a.shortlisted else " "
        print(f"    {i:>3}){mark} #{a.applicant_id}  "
              f"{a.full_name:<26}  "
              f"vac #{a.vacancy_id}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.applicant_id == n), None)
            if match:
                return match
        print("    No matching applicant.")


# ── Vacancy print ────────────────────────────────────────

def _print_vacancies(rows: list[Vacancy]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Title':<32}  {'Role':<18}  "
          f"{'Contract':<14}  {'Closing':<10}  "
          f"{'Status':<14}  Applicants")
    print("  " + "-" * 130)
    for v in rows:
        flag = " !" if v.closing_passed else "  "
        n = data.applicant_count(v.vacancy_id)
        print(f"  {v.vacancy_id:>4}{flag}{v.title[:32]:<32}  "
              f"{v.role_type[:18]:<18}  "
              f"{v.contract_type[:14]:<14}  "
              f"{(v.closing_date or '—'):<10}  "
              f"{v.status:<14}  {n:>10}")
    print(f"\n  {len(rows)} vacancy(ies).")


def _print_vacancy_full(v: Vacancy) -> None:
    print()
    print(f"    #{v.vacancy_id}  {v.title}")
    print(f"    Reference        : {v.reference or '—'}")
    print(f"    Department       : {v.department or '—'}")
    print(f"    Role type        : {v.role_type}")
    print(f"    Contract         : {v.contract_type}  "
          f"({v.fte_percent}% FTE)")
    if v.salary_min is not None or v.salary_max is not None:
        rng = (f"£{v.salary_min:.0f}–£{v.salary_max:.0f}"
                if v.salary_min is not None
                and v.salary_max is not None
                else f"£{v.salary_min or v.salary_max:.0f}")
        print(f"    Salary           : {rng}  "
              f"({v.salary_scale or '—'})")
    print(f"    Advertised on    : {v.advertised_on or '—'}")
    print(f"    Closing date     : {v.closing_date or '—'}"
          + ("  (PASSED)" if v.closing_passed else ""))
    print(f"    Shortlisting     : "
          f"{v.shortlisting_date or '—'}")
    print(f"    Interview        : {v.interview_date or '—'}")
    print(f"    Start date       : {v.start_date or '—'}")
    print(f"    Hiring manager   : {v.hiring_manager or '—'}")
    print(f"    Status           : {v.status}")
    print(f"    Applicants       : "
          f"{data.applicant_count(v.vacancy_id)}")
    for label, val in (
            ("Description",   v.description),
            ("Requirements",  v.requirements),
            ("Benefits",      v.benefits),
            ("Advert URL",    v.advert_url),
            ("Notes",         v.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Vacancy flows ─────────────────────────────────────────

def vacancies_list() -> None:
    print("\n═══ All Vacancies ═══")
    _print_vacancies(data.list_vacancies())
    _pause()


def vacancies_open() -> None:
    print("\n═══ Open Vacancies ═══")
    _print_vacancies(data.list_vacancies(open_only=True))
    _pause()


def vacancies_closing_passed() -> None:
    print("\n═══ Closing Date Passed ═══")
    _print_vacancies(data.list_vacancies(closing_passed=True))
    _pause()


def vacancies_filter() -> None:
    print("\n═══ Filter Vacancies ═══")
    try:
        rt = _input(
            f"Role type ({'/'.join(ROLE_TYPES[:3])}…)") or None
        ct = _input(
            f"Contract ({'/'.join(CONTRACT_TYPES[:3])}…)") or None
        st_ = _input(
            f"Status ({'/'.join(VACANCY_STATUSES[:3])}…)") or None
        dept = _input("Department contains") or None
        title = _input("Title contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_vacancies(role_type=rt, contract_type=ct,
                                    status=st_,
                                    department_like=dept,
                                    title_like=title)
    _print_vacancies(rows)
    _pause()


def vacancies_view() -> None:
    print("\n═══ View Vacancy ═══")
    try:
        v = _pick_vacancy()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_vacancy_full(v)
    _pause()


def _collect_vacancy_form(
        existing: Vacancy | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["reference"] = _input(
        "Reference",
        default=(existing.reference or "") if is_edit else "")
    payload["department"] = _input(
        "Department",
        default=(existing.department or "") if is_edit else "")
    payload["role_type"] = _pick_from(
        "Role type", list(ROLE_TYPES),
        default=(existing.role_type if is_edit
                  else DEFAULT_ROLE_TYPE))
    payload["contract_type"] = _pick_from(
        "Contract type", list(CONTRACT_TYPES),
        default=(existing.contract_type if is_edit
                  else DEFAULT_CONTRACT_TYPE))
    payload["fte_percent"] = _input(
        "FTE percent (0-100)",
        default=(str(existing.fte_percent)
                  if is_edit else "100"))
    payload["salary_min"] = _input(
        "Salary min (£)",
        default=(str(existing.salary_min)
                  if is_edit and existing.salary_min is not None
                  else ""))
    payload["salary_max"] = _input(
        "Salary max (£)",
        default=(str(existing.salary_max)
                  if is_edit and existing.salary_max is not None
                  else ""))
    payload["salary_scale"] = _input(
        "Salary scale (e.g. MPS)",
        default=(existing.salary_scale or "")
        if is_edit else "")
    payload["advertised_on"] = _input(
        "Advertised on (YYYY-MM-DD)",
        default=(existing.advertised_on or "")
        if is_edit else "")
    payload["closing_date"] = _input(
        "Closing date (YYYY-MM-DD)",
        default=(existing.closing_date or "")
        if is_edit else "")
    payload["shortlisting_date"] = _input(
        "Shortlisting date (YYYY-MM-DD)",
        default=(existing.shortlisting_date or "")
        if is_edit else "")
    payload["interview_date"] = _input(
        "Interview date (YYYY-MM-DD)",
        default=(existing.interview_date or "")
        if is_edit else "")
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date or "")
        if is_edit else "")
    payload["hiring_manager"] = _input(
        "Hiring manager",
        default=(existing.hiring_manager or "")
        if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["requirements"] = _multiline(
            "Requirements",
            default=(existing.requirements or "")
            if is_edit else "")
        payload["benefits"] = _multiline(
            "Benefits",
            default=(existing.benefits or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["safeguarding_statement"] = _yes_no(
        "Safeguarding statement included?",
        default=(existing.safeguarding_statement
                  if is_edit else True))
    payload["advert_url"] = _input(
        "Advert URL",
        default=(existing.advert_url or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(VACANCY_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_VACANCY_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def vacancies_new() -> None:
    print("\n═══ New Vacancy ═══")
    try:
        payload = _collect_vacancy_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.create_vacancy(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created vacancy #{v.vacancy_id}")
    _pause()


def vacancies_edit() -> None:
    print("\n═══ Edit Vacancy ═══")
    try:
        v = _pick_vacancy()
        payload = _collect_vacancy_form(v)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_vacancy(v.vacancy_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{v.vacancy_id}")
    _pause()


def vacancies_advertise() -> None:
    print("\n═══ Advertise Vacancy ═══")
    try:
        v = _pick_vacancy()
        when = _input("Advertised on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.advertise(v.vacancy_id, advertised_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{v.vacancy_id} → Advertised")
    _pause()


def vacancies_mark_filled() -> None:
    print("\n═══ Mark Filled ═══")
    try:
        v = _pick_vacancy()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_filled(v.vacancy_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{v.vacancy_id} → Filled")
    _pause()


def vacancies_set_status() -> None:
    print("\n═══ Change Vacancy Status ═══")
    try:
        v = _pick_vacancy()
        new_status = _pick_from("New status",
                                  list(VACANCY_STATUSES),
                                  default=v.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_vacancy_status(v.vacancy_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{v.vacancy_id} → {new_status}")
    _pause()


def vacancies_delete() -> None:
    print("\n═══ Delete Vacancy ═══")
    try:
        v = _pick_vacancy()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete vacancy #{v.vacancy_id} (and all "
              "applicants)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_vacancy(v.vacancy_id):
        print(f"\n  ✓ Deleted #{v.vacancy_id}")
    _pause()


# ── Applicant flows ─────────────────────────────────────

def _print_applicants(rows: list[Applicant]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  Vac  {'Name':<26}  "
          f"{'Source':<14}  Short  Score  {'Status':<22}")
    print("  " + "-" * 120)
    for a in rows:
        mark = "yes" if a.shortlisted else "no"
        score = (str(a.interview_score)
                  if a.interview_score is not None else "—")
        print(f"  {a.applicant_id:>4}  "
              f"{a.vacancy_id:>3}  "
              f"{a.full_name[:26]:<26}  "
              f"{a.source[:14]:<14}  {mark:<5}  "
              f"{score:>5}  {a.status}")
    print(f"\n  {len(rows)} applicant(s).")


def _print_applicant_full(a: Applicant) -> None:
    print()
    print(f"    #{a.applicant_id}  {a.full_name}  "
          f"(vacancy #{a.vacancy_id})")
    print(f"    Email           : {a.email or '—'}")
    print(f"    Phone           : {a.phone or '—'}")
    print(f"    Application rec.: {a.application_received_on}")
    print(f"    Source          : {a.source}")
    print(f"    CV / form / refs: "
          f"{'yes' if a.cv_received else 'no'} / "
          f"{'yes' if a.application_form_received else 'no'} / "
          f"{'yes' if a.references_received else 'no'}")
    print(f"    DBS clearance   : "
          f"{'yes' if a.dbs_clearance else 'no'}")
    print(f"    Shortlisted     : "
          f"{'yes' if a.shortlisted else 'no'}")
    print(f"    Interview       : {a.interview_date or '—'}  "
          f"score: "
          f"{a.interview_score if a.interview_score is not None else '—'}")
    if a.interview_notes:
        print(f"    Interview notes : "
              f"{a.interview_notes[:80]}")
    print(f"    Offer made on   : {a.offer_made_on or '—'}")
    print(f"    Offer response  : {a.offer_response_on or '—'}")
    print(f"    Offer salary    : "
          f"£{a.offer_salary:.0f}" if a.offer_salary
          else "    Offer salary    : —")
    print(f"    Started on      : {a.started_on or '—'}")
    print(f"    Status          : {a.status}")
    if a.rejection_reason:
        print(f"    Rejection reason: {a.rejection_reason}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


def applicants_list() -> None:
    print("\n═══ All Applicants ═══")
    _print_applicants(data.list_applicants())
    _pause()


def applicants_shortlisted() -> None:
    print("\n═══ Shortlisted ═══")
    _print_applicants(data.list_applicants(shortlisted_only=True))
    _pause()


def applicants_offers() -> None:
    print("\n═══ Offers Made ═══")
    _print_applicants(data.list_applicants(offer_made=True))
    _pause()


def applicants_for_vacancy() -> None:
    print("\n═══ Applicants for Vacancy ═══")
    try:
        v = _pick_vacancy()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_applicants(data.list_applicants(
        vacancy_id=v.vacancy_id))
    _pause()


def applicants_view() -> None:
    print("\n═══ View Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_applicant_full(a)
    _pause()


def _collect_applicant_form(
        existing: Applicant | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["first_name"] = _input(
        "First name",
        default=(existing.first_name if is_edit else ""),
        allow_empty=False)
    payload["last_name"] = _input(
        "Last name",
        default=(existing.last_name if is_edit else ""),
        allow_empty=False)
    payload["email"] = _input(
        "Email",
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input(
        "Phone",
        default=(existing.phone or "") if is_edit else "")
    payload["application_received_on"] = _input(
        "Application received on (YYYY-MM-DD)",
        default=(existing.application_received_on
                  if is_edit else _date.today().isoformat()),
        allow_empty=False)
    payload["source"] = _pick_from(
        "Source", list(APPLICANT_SOURCES),
        default=(existing.source if is_edit
                  else DEFAULT_APPLICANT_SOURCE))
    payload["cv_received"] = _yes_no(
        "CV received?",
        default=(existing.cv_received if is_edit else False))
    payload["application_form_received"] = _yes_no(
        "Application form received?",
        default=(existing.application_form_received
                  if is_edit else False))
    payload["references_received"] = _yes_no(
        "References received?",
        default=(existing.references_received
                  if is_edit else False))
    payload["dbs_clearance"] = _yes_no(
        "DBS clearance?",
        default=(existing.dbs_clearance if is_edit
                  else False))
    payload["shortlisted"] = _yes_no(
        "Shortlisted?",
        default=(existing.shortlisted if is_edit else False))
    payload["interview_date"] = _input(
        "Interview date (YYYY-MM-DD)",
        default=(existing.interview_date or "")
        if is_edit else "")
    payload["interview_score"] = _input(
        "Interview score (0-100)",
        default=(str(existing.interview_score)
                  if is_edit
                  and existing.interview_score is not None
                  else ""))
    try:
        payload["interview_notes"] = _multiline(
            "Interview notes",
            default=(existing.interview_notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["offer_made_on"] = _input(
        "Offer made on (YYYY-MM-DD)",
        default=(existing.offer_made_on or "")
        if is_edit else "")
    payload["offer_response_on"] = _input(
        "Offer response on (YYYY-MM-DD)",
        default=(existing.offer_response_on or "")
        if is_edit else "")
    payload["offer_salary"] = _input(
        "Offer salary (£)",
        default=(str(existing.offer_salary)
                  if is_edit and existing.offer_salary is not None
                  else ""))
    payload["rejection_reason"] = _input(
        "Rejection reason",
        default=(existing.rejection_reason or "")
        if is_edit else "")
    payload["started_on"] = _input(
        "Started on (YYYY-MM-DD)",
        default=(existing.started_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(APPLICANT_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_APPLICANT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def applicants_new() -> None:
    print("\n═══ New Applicant ═══")
    try:
        v = _pick_vacancy()
        payload = _collect_applicant_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.add_applicant(v.vacancy_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created applicant #{a.applicant_id}")
    _pause()


def applicants_edit() -> None:
    print("\n═══ Edit Applicant ═══")
    try:
        a = _pick_applicant()
        payload = _collect_applicant_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_applicant(a.applicant_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.applicant_id}")
    _pause()


def applicants_shortlist() -> None:
    print("\n═══ Shortlist / Unshortlist ═══")
    try:
        a = _pick_applicant()
        on = _yes_no("Shortlist?", default=not a.shortlisted)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.shortlist(a.applicant_id, shortlisted=on)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.applicant_id} "
          f"{'shortlisted' if on else 'removed from shortlist'}")
    _pause()


def applicants_schedule_interview() -> None:
    print("\n═══ Schedule Interview ═══")
    try:
        a = _pick_applicant()
        when = _input("Interview date (YYYY-MM-DD)",
                        default=a.interview_date or "",
                        allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule_interview(a.applicant_id,
                                      interview_date=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview scheduled on #{a.applicant_id}")
    _pause()


def applicants_record_interview() -> None:
    print("\n═══ Record Interview ═══")
    try:
        a = _pick_applicant()
        score_raw = _input(
            "Interview score (0-100, blank to keep)",
            default=(str(a.interview_score)
                      if a.interview_score is not None else ""))
        notes = _multiline("Interview notes",
                              default=a.interview_notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    score = (int(score_raw) if score_raw
              and score_raw.isdigit() else None)
    try:
        data.record_interview(a.applicant_id,
                                    score=score,
                                    notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Interview recorded on #{a.applicant_id}")
    _pause()


def applicants_make_offer() -> None:
    print("\n═══ Make Offer ═══")
    try:
        a = _pick_applicant()
        sal_raw = _input("Offer salary (£)",
                             default=str(a.offer_salary)
                             if a.offer_salary else "")
        when = _input("Made on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sal = (float(sal_raw) if sal_raw
            and sal_raw.replace(".", "", 1).isdigit() else None)
    try:
        data.make_offer(a.applicant_id, salary=sal,
                            offer_made_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Offer made on #{a.applicant_id}")
    _pause()


def applicants_offer_response() -> None:
    print("\n═══ Record Offer Response ═══")
    try:
        a = _pick_applicant()
        accepted = _yes_no("Accepted?", default=True)
        when = _input("Response on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.offer_response(a.applicant_id, accepted=accepted,
                                 response_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    status = "accepted" if accepted else "declined"
    print(f"\n  ✓ Offer {status} on #{a.applicant_id}")
    _pause()


def applicants_mark_started() -> None:
    print("\n═══ Mark Started ═══")
    try:
        a = _pick_applicant()
        when = _input("Started on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_started(a.applicant_id, started_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.applicant_id} → Started")
    _pause()


def applicants_reject() -> None:
    print("\n═══ Reject Applicant ═══")
    try:
        a = _pick_applicant()
        reason = _multiline("Reason",
                               default=a.rejection_reason or "")
        if not reason:
            print("  ✗ Reason required.")
            _pause()
            return
        post_iv = _yes_no("Post-interview?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.reject_applicant(a.applicant_id, reason=reason,
                                    post_interview=post_iv)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.applicant_id} rejected")
    _pause()


def applicants_withdraw() -> None:
    print("\n═══ Withdraw Applicant ═══")
    try:
        a = _pick_applicant()
        reason = _multiline("Reason (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw_applicant(a.applicant_id,
                                      reason=reason or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.applicant_id} withdrew")
    _pause()


def applicants_set_status() -> None:
    print("\n═══ Change Applicant Status ═══")
    try:
        a = _pick_applicant()
        new_status = _pick_from("New status",
                                  list(APPLICANT_STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_applicant_status(a.applicant_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.applicant_id} → {new_status}")
    _pause()


def applicants_delete() -> None:
    print("\n═══ Delete Applicant ═══")
    try:
        a = _pick_applicant()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete applicant #{a.applicant_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_applicant(a.applicant_id):
        print(f"\n  ✓ Deleted #{a.applicant_id}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Recruitment Summary ═══")
    s = data.summary()
    print(f"\n  Total vacancies      : {s.total_vacancies}")
    print(f"  Open                 : {s.open_vacancies}")
    print(f"  Advertised           : {s.advertised}")
    print(f"  Closing passed       : {s.closing_passed}")
    print(f"  Total applicants     : {s.total_applicants}")
    print(f"  Active               : {s.active_applicants}")
    print(f"  Shortlisted          : {s.shortlisted}")
    print(f"  Interviewed          : {s.interviewed}")
    print(f"  Offers made          : {s.offers_made}")
    print(f"  Offers accepted      : {s.offers_accepted}")
    print(f"  Started              : {s.started}")
    print(f"  Rejected             : {s.rejected}")
    print("\n  By role type:")
    for k in ROLE_TYPES:
        n = s.by_role_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By vacancy status:")
    for k in VACANCY_STATUSES:
        n = s.by_vacancy_status.get(k, 0)
        if n:
            print(f"    {k:<16}: {n}")
    print("\n  By applicant status:")
    for k in APPLICANT_STATUSES:
        n = s.by_applicant_status.get(k, 0)
        if n:
            print(f"    {k:<26}: {n}")
    print("\n  By source:")
    for k in APPLICANT_SOURCES:
        n = s.by_source.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Vacancies ──",      lambda: None),
    ("List all",             vacancies_list),
    ("Open only",            vacancies_open),
    ("Closing passed",       vacancies_closing_passed),
    ("Filter",               vacancies_filter),
    ("View",                 vacancies_view),
    ("New vacancy",          vacancies_new),
    ("Edit vacancy",         vacancies_edit),
    ("Advertise",            vacancies_advertise),
    ("Mark Filled",          vacancies_mark_filled),
    ("Change status",        vacancies_set_status),
    ("Delete vacancy",       vacancies_delete),
    ("── Applicants ──",     lambda: None),
    ("List all",             applicants_list),
    ("Shortlisted",          applicants_shortlisted),
    ("Offers made",          applicants_offers),
    ("For vacancy",          applicants_for_vacancy),
    ("View",                 applicants_view),
    ("New applicant",        applicants_new),
    ("Edit applicant",       applicants_edit),
    ("Shortlist toggle",     applicants_shortlist),
    ("Schedule interview",   applicants_schedule_interview),
    ("Record interview",     applicants_record_interview),
    ("Make offer",           applicants_make_offer),
    ("Offer response",       applicants_offer_response),
    ("Mark started",         applicants_mark_started),
    ("Reject",               applicants_reject),
    ("Withdraw",             applicants_withdraw),
    ("Change status",        applicants_set_status),
    ("Delete applicant",     applicants_delete),
    ("──",                   lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Recruitment ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Recruitment CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Recruitment":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Recruitment CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
