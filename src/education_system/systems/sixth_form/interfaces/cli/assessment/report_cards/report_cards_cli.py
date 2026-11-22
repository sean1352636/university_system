"""CLI flows for Sixth Form report cards.

Terminal counterpart of the Report Cards GUI: periods and templates,
generating cards, a teacher's comment entry for their own classes,
tutor comments, completion, review/approve and publish (through the
bulk operation), and rendering files. ``dispatch("Report Cards")`` opens
it from the staff menu; the Grades Report menu links to it as well.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.assessment.report_cards import (
    report_cards as data,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    return s or default


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _d(v: Any) -> str:
    return "—" if v in (None, "") else str(v)


def _me():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access.current()


def _pick(items: list, label: Callable[[Any], str], prompt: str):
    if not items:
        print("    Nothing to choose from.")
        return None
    for i, it in enumerate(items, 1):
        print(f"  {i:>3}) {label(it)}")
    raw = _input(prompt)
    if raw.isdigit() and 1 <= int(raw) <= len(items):
        return items[int(raw) - 1]
    return None


def _pick_period():
    return _pick(data.list_periods(),
                 lambda p: f"{p.label:<28}{p.start_date} → {p.end_date}  {p.status}",
                 "Period (number)")


def _yes(prompt: str, default: bool = True) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n").lower()
    return raw.startswith("y")


# ── Setup ────────────────────────────────────────────────────────────

def periods_flow() -> None:
    print("\n  Report periods")
    for p in data.list_periods():
        t = data.get_template(p.template_id)
        print(f"   #{p.period_id:<4}{p.label:<28}{p.start_date} → {p.end_date}  "
              f"due {_d(p.comments_due):<11}{p.status:<10}{t.name if t else ''}")
    action = _input("N)ew, E)dit, O)pen, C)lose entry, D)elete, Enter to go back").lower()
    if not action:
        return
    if action == "n":
        templates = data.list_templates()
        t = None
        if templates:
            t = _pick(templates, lambda t: t.name, "Template (number, Enter for default)")
        payload = {"label": _input("Label (e.g. 2025/26 Autumn)"),
                   "academic_year": _input("Academic year"),
                   "start_date": _input("Start (YYYY-MM-DD)"),
                   "end_date": _input("End (YYYY-MM-DD)"),
                   "comments_due": _input("Comments due (YYYY-MM-DD, optional)"),
                   "template_id": t.template_id if t else None}
        p = data.create_period(payload, by=_me())
        print(f"  ✓ Created period #{p.period_id}.")
        return
    p = _pick_period()
    if p is None:
        return
    if action == "e":
        data.update_period(p.period_id, {
            "label": _input("Label", default=p.label),
            "start_date": _input("Start", default=p.start_date),
            "end_date": _input("End", default=p.end_date),
            "comments_due": _input("Comments due", default=p.comments_due or "")},
            by=_me())
    elif action == "o":
        data.set_period_status(p.period_id, data.PERIOD_OPEN, by=_me())
    elif action == "c":
        data.set_period_status(p.period_id, data.PERIOD_CLOSED, by=_me())
    elif action == "d" and _yes(f"Delete {p.label} and its draft cards?", False):
        data.delete_period(p.period_id, by=_me())
    print("  ✓ Done.")


def templates_flow() -> None:
    print("\n  Templates")
    templates = data.list_templates()
    for t in templates:
        print(f"   #{t.template_id:<4}{t.name}")
        print(f"        effort: {' | '.join(t.effort_scale)}")
        print(f"        attitude: {' | '.join(t.attitude_scale)}")
    action = _input("N)ew, E)dit, Enter to go back").lower()
    if action not in ("n", "e"):
        return
    existing = None
    if action == "e":
        existing = _pick(templates, lambda t: t.name, "Template (number)")
        if existing is None:
            return
    payload: dict[str, Any] = {"name": _input("Name",
                                               default=existing.name if existing else "")}
    for flag, label in (("include_attendance", "Attendance %"),
                        ("include_current_grade", "Current grade"),
                        ("include_target_grade", "Target grade"),
                        ("include_predicted_grade", "Predicted grade"),
                        ("include_effort", "Effort"), ("include_attitude", "Attitude"),
                        ("include_subject_comments", "Subject comments"),
                        ("include_tutor_comment", "Tutor comment"),
                        ("include_hosf_comment", "Head of sixth form comment")):
        payload[flag] = _yes(f"Include {label}?",
                             getattr(existing, flag) if existing else True)
    eff = existing.effort_scale if existing else data.DEFAULT_EFFORT_SCALE
    att = existing.attitude_scale if existing else data.DEFAULT_ATTITUDE_SCALE
    payload["effort_scale"] = _input("Effort scale (| separated)", default="|".join(eff))
    payload["attitude_scale"] = _input("Attitude scale (| separated)",
                                       default="|".join(att))
    payload["comment_max_chars"] = _input(
        "Comment length limit",
        default=str(existing.comment_max_chars if existing else data.DEFAULT_COMMENT_MAX))
    if existing:
        data.update_template(existing.template_id, payload, by=_me())
    else:
        data.create_template(payload, by=_me())
    print("  ✓ Saved.")


def generate_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    res = data.generate_cards(p.period_id, by=_me())
    print(f"  ✓ {res['created']} new cards, {res['lines_added']} subject lines, "
          f"{res['skipped']} skipped.")


# ── Comment entry ────────────────────────────────────────────────────

def my_lines_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    tmpl = data.get_template(p.template_id)
    all_lines = data.can_manage(_me()) and _yes("Show every line (lead)?", False)
    while True:
        lines = data.lines_for_teacher(p.period_id, by=_me(), all_lines=all_lines)
        print(f"\n  Lines for {p.label}: {len(lines)}")
        tl = _pick(lines, lambda tl: (
            f"{tl.line.subject[:18]:<20}{tl.student_name[:22]:<24}"
            f"{_d(tl.line.current_grade):<6}{_d(tl.line.effort)[:16]:<18}"
            f"{'comment ✓' if tl.line.comment else 'no comment'}"),
            "Write which line (number), Enter to go back")
        if tl is None:
            return
        ln = tl.line
        print(f"\n  {ln.subject} — {tl.student_name}  (target {_d(ln.target_grade)}, "
              f"predicted {_d(ln.predicted_grade)})")
        grade = _input("Current grade", default=ln.current_grade or "")
        print("    Effort: " + " | ".join(tmpl.effort_scale))
        eff = _input("Effort (exact text or number)", default=ln.effort or "")
        if eff.isdigit() and 1 <= int(eff) <= len(tmpl.effort_scale):
            eff = tmpl.effort_scale[int(eff) - 1]
        print("    Attitude: " + " | ".join(tmpl.attitude_scale))
        att = _input("Attitude (exact text or number)", default=ln.attitude or "")
        if att.isdigit() and 1 <= int(att) <= len(tmpl.attitude_scale):
            att = tmpl.attitude_scale[int(att) - 1]
        if ln.comment:
            print(f"    Current comment: {ln.comment}")
        comment = _input("Comment (Enter keeps the current one)", default=ln.comment or "")
        try:
            data.save_subject_entry(ln.line_id, current_grade=grade, effort=eff,
                                    attitude=att, comment=comment, by=_me())
            print("  ✓ Saved.")
        except data.ValidationError as e:
            print(f"  ✗ {e}")


def tutor_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    while True:
        cards = data.cards_for_tutor(p.period_id, by=_me())
        print(f"\n  Your tutees: {len(cards)}")
        c = _pick(cards, lambda c: f"{(c.student_name or c.student_id)[:28]:<30}"
                  f"{'done' if c.tutor_comment else 'outstanding':<14}{c.status}",
                  "Write for which (number), Enter to go back")
        if c is None:
            return
        if c.tutor_comment:
            print(f"    Current: {c.tutor_comment}")
        text = _input("Tutor comment", default=c.tutor_comment or "")
        try:
            data.save_tutor_comment(c.card_id, text, by=_me())
            print("  ✓ Saved.")
        except data.ValidationError as e:
            print(f"  ✗ {e}")


# ── Completion, review, publish ──────────────────────────────────────

def completion_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    s = data.period_summary(p.period_id)
    print(f"\n  {p.label}: {s['complete']}/{s['cards']} complete, {s['approved']} "
          f"approved, {s['published']} published")
    for c in data.completion(p.period_id):
        print(f"   {(c.student_name or c.student_id)[:26]:<28}{c.status:<11}"
              f"{'; '.join(c.missing)[:60] or 'complete'}")
    print("\n  By teacher")
    for t in data.teacher_progress(p.period_id):
        print(f"   {t.teacher[:30]:<32}{t.lines_done}/{t.lines_total}  "
              f"({t.outstanding} outstanding)")


def review_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    while True:
        cards = data.list_cards(p.period_id)
        print(f"\n  Review — {p.label}")
        c = _pick(cards, lambda c: f"{(c.student_name or c.student_id)[:28]:<30}"
                  f"{c.status:<11}{_d(c.review_note)[:40]}",
                  "Open which (number), Enter to go back")
        if c is None:
            return
        print()
        for line in data.render_text(data.get_card(c.card_id)).splitlines():
            print(f"  {line}")
        act = _input("H)oSF comment, S)ubmit, A)pprove, R)eturn, O)reopen, "
                     "U)pdate data, Enter").lower()
        try:
            if act == "h":
                data.save_hosf_comment(c.card_id, _input("Comment",
                                                         default=c.hosf_comment or ""),
                                       by=_me())
            elif act == "s":
                data.submit_for_review(c.card_id, by=_me())
            elif act == "a":
                data.approve(c.card_id, by=_me())
            elif act == "r":
                data.return_for_changes(c.card_id, _input("What needs changing"), by=_me())
            elif act == "o":
                data.reopen(c.card_id, by=_me())
            elif act == "u":
                data.refresh_card_data(c.card_id, by=_me())
            else:
                continue
            print("  ✓ Done.")
        except data.ValidationError as e:
            print(f"  ✗ {e}")


def approve_all_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    n, problems = data.approve_all_complete(p.period_id, by=_me())
    print(f"  ✓ {n} approved.")
    for line in problems[:20]:
        print(f"    not approved — {line}")


def publish_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    if _yes("Publish (y) or unpublish (n)?"):
        res = data.publish(p.period_id, by=_me())
        print(f"  ✓ Published {res.success_count}/{res.target_count}.")
    else:
        res = data.unpublish(p.period_id, by=_me())
        print(f"  ✓ Withdrew {res.success_count}.")
    for sid, why in res.failures[:20]:
        print(f"    {sid}: {why}")


def render_flow() -> None:
    p = _pick_period()
    if p is None:
        return
    fmt = _input("Format html / txt / pdf", default="html").lower()
    files = data.render_period(p.period_id, fmt=fmt, by=_me())
    print(f"  ✓ Wrote {len(files)} file(s)"
          + (f" to {files[0].parent}" if files else ""))


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Report periods", periods_flow),
    ("Templates", templates_flow),
    ("Generate cards for a period", generate_flow),
    ("My subject comments", my_lines_flow),
    ("Tutor comments", tutor_flow),
    ("Completion", completion_flow),
    ("Review and approve", review_flow),
    ("Approve all complete", approve_all_flow),
    ("Publish / unpublish", publish_flow),
    ("Save report files", render_flow),
]


def run() -> None:
    while True:
        print("\n── Report Cards ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except data.ValidationError as e:
            print(f"\n  ✗ {e}")
        except Exception as e:
            logger.exception("Report-cards CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def dispatch(label: str) -> bool:
    if label != "Report Cards":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Report-cards CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
