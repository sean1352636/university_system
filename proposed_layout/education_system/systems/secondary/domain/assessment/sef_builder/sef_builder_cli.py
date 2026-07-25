"""CLI handlers for the SEF builder."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.assessment.sef_builder import (
    sef_builder as data,
)
from education_system.systems.secondary.domain.assessment.sef_builder.sef_builder import (
    JUDGEMENTS, SEF_STATUSES, DEFAULT_SECTIONS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_docs(rows: list[data.SEFDocument]) -> None:
    if not rows:
        print("  (no SEF documents)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Ver':<6} {'Title':<28} "
          f"{'Status':<10} {'Headline':<22} {'Author':<16}")
    print(f"  {'-'*4} {'-'*8} {'-'*6} {'-'*28} {'-'*10} {'-'*22} "
          f"{'-'*16}")
    for d in rows:
        print(f"  {d.sef_id:<4} {d.academic_year:<8} {d.version:<6} "
              f"{(d.title or '-')[:28]:<28} {d.status:<10} "
              f"{d.headline_judgement[:22]:<22} "
              f"{(d.author or '-')[:16]:<16}")


def _print_sections(rows: list[data.SEFSection]) -> None:
    if not rows:
        print("  (no sections)")
        return
    print(f"  {'ID':<4} {'Code':<10} {'Title':<32} "
          f"{'Judgement':<22} {'Updated by':<16}")
    print(f"  {'-'*4} {'-'*10} {'-'*32} {'-'*22} {'-'*16}")
    for s in rows:
        print(f"  {s.section_id:<4} {s.section_code:<10} "
              f"{s.section_title[:32]:<32} "
              f"{s.judgement[:22]:<22} "
              f"{(s.last_updated_by or '-')[:16]:<16}")


@_safe
def open_sef_builder() -> None:
    logger.debug("CLI: open_sef_builder")
    while True:
        print("\n  ── SEF Builder ──")
        print("  Documents")
        print("    1) New SEF document")
        print("    2) List documents")
        print("    3) View document + sections")
        print("    4) Edit document")
        print("    5) Set status")
        print("    6) Delete document")
        print("  Sections")
        print("    7) Seed default sections")
        print("    8) Add / update section")
        print("    9) View section")
        print("   10) Delete section")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _new_doc, "2": _list_docs, "3": _view,
            "4": _edit_doc, "5": _set_status, "6": _delete_doc,
            "7": _seed, "8": _upsert_section,
            "9": _view_section, "10": _delete_section,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_doc(existing: data.SEFDocument | None = None
                  ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["academic_year"]      = ask("Academic year (YYYY/YY)",
                                     existing.academic_year if existing
                                     else None)
    f["version"]            = ask("Version (e.g. v1)",
                                     existing.version if existing
                                     else "v1")
    f["title"]              = ask("Title",
                                     existing.title if existing else None)
    f["status"]             = ask(f"Status ({'/'.join(SEF_STATUSES)})",
                                     existing.status if existing
                                     else "Draft")
    f["headline_judgement"] = ask(
        f"Headline judgement ({'/'.join(JUDGEMENTS)})",
        existing.headline_judgement if existing
        else "Not yet evaluated")
    f["author"]             = ask("Author",
                                     existing.author if existing
                                     else None)
    f["approved_by"]        = ask("Approved by",
                                     existing.approved_by if existing
                                     else None)
    f["approved_date"]      = ask("Approved date (YYYY-MM-DD, blank ok)",
                                     existing.approved_date if existing
                                     else None)
    f["notes"]              = ask("Notes",
                                     existing.notes if existing
                                     else None)
    return f


@_safe
def _new_doc() -> None:
    print("\n  ── New SEF Document ──")
    fields = _collect_doc()
    d = data.create_document(fields, seed_sections=True)
    print(f"  Created SEF #{d.sef_id} {d.academic_year}/{d.version} "
          f"(seeded {len(DEFAULT_SECTIONS)} sections)")


@_safe
def _list_docs() -> None:
    ay = _prompt("  Academic year (blank): ") or None
    status = _prompt(f"  Status ({'/'.join(SEF_STATUSES)}, blank): ") or None
    rows = data.list_documents(academic_year=ay, status=status)
    print(f"\n  {len(rows)} document(s):")
    _print_docs(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    s = data.document_summary(sid)
    d = s["document"]
    print(f"\n  ── SEF #{d.sef_id} ──")
    print(f"  Academic year / version: {d.academic_year} / {d.version}")
    print(f"  Title:        {d.title or '-'}")
    print(f"  Status:       {d.status}    "
          f"Headline: {d.headline_judgement}")
    print(f"  Author:       {d.author or '-'}    "
          f"Approved by: {d.approved_by or '-'}")
    print(f"  Approved on:  {d.approved_date or '-'}")
    print(f"  Notes:        {d.notes or '-'}")
    print(f"\n  Sections: {s['section_count']}    "
          f"Evaluated: {s['evaluated']}")
    if s["by_judgement"]:
        print("  By judgement: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_judgement"].items()))
    _print_sections(s["sections"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _edit_doc() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    existing = data.get_document(sid)
    if existing is None:
        print("  No document with that ID.")
        return
    print("  Press Enter to keep existing value.")
    fields = _collect_doc(existing)
    d = data.update_document(sid, fields)
    print(f"  Updated SEF #{d.sef_id} (status {d.status})")


@_safe
def _set_status() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    d = data.get_document(sid)
    if d is None:
        print("  No document with that ID.")
        return
    print(f"  Current: {d.status}    Allowed: "
          f"{', '.join(SEF_STATUSES)}")
    new = _prompt("  New status: ")
    if not new:
        return
    approver = None
    if new == "Approved":
        approver = _prompt("  Approved by: ")
        if not approver:
            print("  Approver required for Approved status.")
            return
    d = data.set_status(sid, new, approved_by=approver)
    print(f"  Status now: {d.status}")


@_safe
def _delete_doc() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    d = data.get_document(sid)
    if d is None:
        print("  No document with that ID.")
        return
    confirm = _prompt(
        f"  Delete SEF {d.academic_year}/{d.version} and ALL its "
        f"sections? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_document(sid)
    print(f"  Deleted SEF #{sid}.")


@_safe
def _seed() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    added = data.init_sections(sid)
    print(f"  Seeded {added} default section(s).")


@_safe
def _upsert_section() -> None:
    sid = _ask_id("SEF ID")
    if sid is None:
        return
    if data.get_document(sid) is None:
        print("  No document with that ID.")
        return
    code = _prompt("  Section code (e.g. QUAL_ED): ")
    if not code:
        return
    print("  Default codes:")
    for c, t in DEFAULT_SECTIONS:
        print(f"    {c:<12} {t}")
    title = _prompt("  Section title: ")
    if not title:
        print("  Title required.")
        return
    f: dict[str, Any] = {
        "sef_id": sid, "section_code": code, "section_title": title,
    }
    f["judgement"] = _prompt(
        f"  Judgement ({'/'.join(JUDGEMENTS)}) "
        f"[Not yet evaluated]: ") or "Not yet evaluated"
    f["strengths"] = _prompt("  Strengths: ") or None
    f["areas_for_development"] = _prompt(
        "  Areas for development: ") or None
    f["evidence"]     = _prompt("  Evidence: ") or None
    f["action_plan"]  = _prompt("  Action plan: ") or None
    f["last_updated_by"] = _prompt("  Updated by: ") or None
    rec = data.upsert_section(f)
    print(f"  Saved section #{rec.section_id} {rec.section_code} — "
          f"{rec.section_title} ({rec.judgement})")


@_safe
def _view_section() -> None:
    sid = _ask_id("Section ID")
    if sid is None:
        return
    s = data.get_section(sid)
    if s is None:
        print("  No section with that ID.")
        return
    print(f"\n  ── Section #{s.section_id} ──")
    print(f"  SEF:     #{s.sef_id}")
    print(f"  Code:    {s.section_code}")
    print(f"  Title:   {s.section_title}")
    print(f"  Judgement: {s.judgement}")
    print(f"\n  Strengths:\n    {s.strengths or '-'}")
    print(f"\n  Areas for development:\n    "
          f"{s.areas_for_development or '-'}")
    print(f"\n  Evidence:\n    {s.evidence or '-'}")
    print(f"\n  Action plan:\n    {s.action_plan or '-'}")
    print(f"\n  Last updated by: {s.last_updated_by or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_section() -> None:
    sid = _ask_id("Section ID")
    if sid is None:
        return
    s = data.get_section(sid)
    if s is None:
        print("  No section with that ID.")
        return
    confirm = _prompt(
        f"  Delete section #{sid} ({s.section_code} — "
        f"{s.section_title})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_section(sid)
    print(f"  Deleted section #{sid}.")


_DISPATCH = {"SEF Builder": open_sef_builder}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching sef_builder CLI label: %s", label)
    handler()
    return True
