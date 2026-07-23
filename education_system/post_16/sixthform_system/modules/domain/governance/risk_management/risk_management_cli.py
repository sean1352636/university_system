"""CLI flows for Sixth Form Risk Management."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.governance.risk_management import (
    risk_management as data,
)
from education_system.post_16.sixthform_system.modules.domain.governance.risk_management.risk_management import (
    ACTION_STATUSES,
    CATEGORIES,
    DEFAULT_ACTION_STATUS,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    DEFAULT_TREATMENT,
    IMPACT_LABELS,
    LIKELIHOOD_LABELS,
    STATUSES,
    TREATMENTS,
    ValidationError,
    score_band,
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
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


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
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_score(label: str, labels: dict[int, str],
                 default: int | None = None) -> int:
    print(f"\n  {label}:")
    for n in range(1, 6):
        marker = " *" if n == default else "  "
        print(f"    {marker}{n}) {labels[n]}")
    while True:
        raw = _input("Pick 1..5",
                      default=str(default) if default else "",
                      allow_empty=False)
        if raw.isdigit() and 1 <= int(raw) <= 5:
            return int(raw)
        print("    Enter a number 1..5.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_risks(rows: list[data.Risk]) -> None:
    if not rows:
        print("\n  (no risks)")
        return
    print()
    print(f"  {'#':>4}  {'Title':<32}  {'Category':<14}  "
          f"{'L':>2} {'I':>2}  {'Score':>5}  {'Band':<8}  "
          f"{'Status':<12}  Owner")
    print("  " + "-" * 120)
    for r in rows:
        print(f"  {r.risk_id:>4}  {r.title[:32]:<32}  "
              f"{r.category[:14]:<14}  "
              f"{r.likelihood:>2} {r.impact:>2}  "
              f"{r.inherent_score:>5}  {r.inherent_band:<8}  "
              f"{r.status:<12}  {r.owner or '—'}")
    print(f"\n  {len(rows)} risk(s).")


def _print_actions(rows: list[data.Action]) -> None:
    if not rows:
        print("\n  (no actions)")
        return
    print()
    print(f"  {'#':>4}  {'Risk':>4}  {'Description':<42}  "
          f"{'Owner':<12}  {'Due':<10}  {'Status':<12}  Done")
    print("  " + "-" * 110)
    for a in rows:
        marker = "OVR " if a.is_overdue else ""
        print(f"  {a.action_id:>4}  {a.risk_id:>4}  "
              f"{a.description[:42]:<42}  "
              f"{(a.owner or '—')[:12]:<12}  "
              f"{(a.due_date or '—'):<10}  "
              f"{marker}{a.status[:8]:<8}  "
              f"{a.completed_date or '—'}")
    print(f"\n  {len(rows)} action(s).")


def _print_reviews(rows: list[data.Review]) -> None:
    if not rows:
        print("\n  (no reviews)")
        return
    print()
    print(f"  {'#':>4}  {'Risk':>4}  {'Date':<10}  "
          f"{'Reviewer':<14}  {'New L/I':<8}  "
          f"{'New status':<14}  Summary")
    print("  " + "-" * 110)
    for r in rows:
        li = (f"{r.new_likelihood or '—'}/{r.new_impact or '—'}"
              if r.new_likelihood or r.new_impact else "—")
        print(f"  {r.review_id:>4}  {r.risk_id:>4}  "
              f"{r.review_date:<10}  "
              f"{(r.reviewer or '—')[:14]:<14}  "
              f"{li:<8}  {(r.new_status or '—')[:14]:<14}  "
              f"{(r.summary or '')[:40]}")
    print(f"\n  {len(rows)} review(s).")


def _print_heatmap() -> None:
    grid = data.heatmap()
    print("\n  Open-risk heatmap (likelihood ↓, impact →):")
    header = "L\\I"
    print(f"    {header:<6} "
          + " ".join(f"{IMPACT_LABELS[i][:7]:>8}"
                      for i in range(1, 6)))
    for l in range(5, 0, -1):
        cells = []
        for i in range(1, 6):
            n = grid.get((l, i), 0)
            cells.append(f"{n:>8}" if n else f"{'·':>8}")
        print(f"    {LIKELIHOOD_LABELS[l][:6]:<6} " + " ".join(cells))


# ── Risk flows ────────────────────────────────────────────────────

def _collect_risk(existing: data.Risk | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["title"] = _input(
        "Title", default=existing.title if is_edit else "",
        allow_empty=not is_edit)
    p["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=existing.category if is_edit else DEFAULT_CATEGORY)
    p["description"] = _input(
        "Description",
        default=(existing.description or "") if is_edit else "")
    p["owner"] = _input(
        "Owner",
        default=(existing.owner or "") if is_edit else "")
    p["identified_date"] = _input(
        "Identified date (YYYY-MM-DD)",
        default=existing.identified_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=existing.status if is_edit else DEFAULT_STATUS)
    p["likelihood"] = _pick_score(
        "Inherent likelihood (1..5)", LIKELIHOOD_LABELS,
        default=existing.likelihood if is_edit else 3)
    p["impact"] = _pick_score(
        "Inherent impact (1..5)", IMPACT_LABELS,
        default=existing.impact if is_edit else 3)
    p["controls"] = _input(
        "Existing controls",
        default=(existing.controls or "") if is_edit else "")
    rl = _input(
        "Residual likelihood (1..5, blank = none)",
        default=(str(existing.residual_likelihood)
                  if is_edit and existing.residual_likelihood
                  else ""))
    p["residual_likelihood"] = rl or None
    ri = _input(
        "Residual impact (1..5, blank = none)",
        default=(str(existing.residual_impact)
                  if is_edit and existing.residual_impact
                  else ""))
    p["residual_impact"] = ri or None
    p["treatment"] = _pick_from(
        "Treatment", list(TREATMENTS),
        default=existing.treatment if is_edit else DEFAULT_TREATMENT)
    p["review_frequency_days"] = _input(
        "Review frequency (days)",
        default=(str(existing.review_frequency_days)
                  if is_edit else "90"))
    p["last_reviewed"] = _input(
        "Last reviewed (YYYY-MM-DD, optional)",
        default=(existing.last_reviewed or "") if is_edit else "")
    p["next_review"] = _input(
        "Next review (YYYY-MM-DD, blank = auto)",
        default=(existing.next_review or "") if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def list_open() -> None:
    print("\n═══ Open Risks ═══")
    _print_risks(data.list_risks(open_only=True))
    _pause()


def list_all() -> None:
    print("\n═══ All Risks ═══")
    _print_risks(data.list_risks())
    _pause()


def list_high() -> None:
    print("\n═══ High & Critical Risks (open) ═══")
    _print_risks(data.list_risks(open_only=True, min_score=10))
    _pause()


def list_review_due() -> None:
    print("\n═══ Risks Due for Review ═══")
    _print_risks(data.list_risks(review_due_only=True,
                                  open_only=True))
    _pause()


def filter_risks() -> None:
    print("\n═══ Filter Risks ═══")
    try:
        cat = _input(f"Category ({'/'.join(CATEGORIES[:4])}/…)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        owner = _input("Owner contains") or None
        min_score = _input("Min inherent score") or None
        q = _input("Search text") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_risks(
            category=cat, status=status, owner=owner,
            min_score=int(min_score) if min_score else None,
            search=q)
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_risks(rows)
    _pause()


def view_risk_flow(risk_id: int | None = None) -> None:
    print("\n═══ View Risk ═══")
    try:
        rid = risk_id if risk_id is not None else int(
            _input("Risk ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_risk(rid)
    if v is None:
        print(f"  ✗ No risk #{rid}")
        _pause()
        return
    r = v.risk
    print()
    print(f"    Risk #{r.risk_id}: {r.title}")
    print(f"    Category    : {r.category}")
    print(f"    Owner       : {r.owner or '—'}")
    print(f"    Identified  : {r.identified_date}")
    print(f"    Status      : {r.status}")
    print(f"    Inherent    : L={r.likelihood} × I={r.impact} "
          f"= {r.inherent_score} ({r.inherent_band})")
    if r.residual_score is not None:
        print(f"    Residual    : L={r.residual_likelihood} "
              f"× I={r.residual_impact} = {r.residual_score} "
              f"({r.residual_band})")
    else:
        print("    Residual    : —")
    print(f"    Treatment   : {r.treatment}")
    print(f"    Review every: {r.review_frequency_days} days "
          f"(last {r.last_reviewed or '—'}, "
          f"next {r.next_review or '—'})")
    if r.description:
        print(f"\n    Description:\n      {r.description}")
    if r.controls:
        print(f"\n    Controls:\n      {r.controls}")
    if r.notes:
        print(f"\n    Notes:\n      {r.notes}")
    print(f"\n    Actions: {v.action_total} total, "
          f"{v.action_open} open, {v.action_overdue} overdue")
    print(f"    Last review: {v.last_review or '—'}")
    acts = data.list_actions(risk_id=rid)
    _print_actions(acts)
    revs = data.list_reviews(risk_id=rid, limit=10)
    _print_reviews(revs)
    _pause()


def new_risk() -> None:
    print("\n═══ New Risk ═══")
    try:
        payload = _collect_risk(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_risk(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created risk #{r.risk_id} "
          f"(score {r.inherent_score} / {r.inherent_band})")
    _pause()


def edit_risk(risk_id: int | None = None) -> None:
    print("\n═══ Edit Risk ═══")
    try:
        rid = risk_id if risk_id is not None else int(
            _input("Risk ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_risk(rid)
    if existing is None:
        print(f"  ✗ No risk #{rid}")
        _pause()
        return
    try:
        payload = _collect_risk(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_risk(rid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{rid}")
    _pause()


def delete_risk_flow() -> None:
    print("\n═══ Delete Risk ═══")
    print("  ⚠ This also deletes the risk's actions and reviews.")
    try:
        rid = int(_input("Risk ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_risk(rid) is None:
        print(f"  ✗ No risk #{rid}")
        _pause()
        return
    if _input(f"Delete risk #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_risk(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


# ── Action flows ──────────────────────────────────────────────────

def add_action_flow(risk_id: int | None = None) -> None:
    print("\n═══ Add Action ═══")
    try:
        rid = risk_id if risk_id is not None else int(
            _input("Risk ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_risk(rid) is None:
        print(f"  ✗ No risk #{rid}")
        _pause()
        return
    try:
        desc = _input("Description", allow_empty=False)
        owner = _input("Owner (optional)")
        due = _input("Due date (YYYY-MM-DD, optional)")
        status = _pick_from("Status", list(ACTION_STATUSES),
                              default=DEFAULT_ACTION_STATUS)
        evidence = _input("Evidence link / note (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.add_action(rid, {
            "description": desc, "owner": owner,
            "due_date": due, "status": status,
            "evidence": evidence, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Added action #{a.action_id}")
    _pause()


def list_open_actions() -> None:
    print("\n═══ Open Actions ═══")
    _print_actions(data.list_actions(open_only=True))
    _pause()


def list_overdue_actions() -> None:
    print("\n═══ Overdue Actions ═══")
    _print_actions(data.list_actions(overdue_only=True))
    _pause()


def edit_action_flow() -> None:
    print("\n═══ Edit Action ═══")
    try:
        aid = int(_input("Action ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_action(aid)
    if existing is None:
        print(f"  ✗ No action #{aid}")
        _pause()
        return
    try:
        desc = _input("Description", default=existing.description,
                       allow_empty=False)
        owner = _input("Owner",
                        default=existing.owner or "")
        due = _input("Due date (YYYY-MM-DD)",
                       default=existing.due_date or "")
        status = _pick_from("Status", list(ACTION_STATUSES),
                              default=existing.status)
        completed = _input(
            "Completed date (YYYY-MM-DD, optional)",
            default=existing.completed_date or "")
        evidence = _input("Evidence",
                            default=existing.evidence or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_action(aid, {
            "description": desc, "owner": owner, "due_date": due,
            "status": status, "completed_date": completed,
            "evidence": evidence, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated action #{aid}")
    _pause()


def delete_action_flow() -> None:
    print("\n═══ Delete Action ═══")
    try:
        aid = int(_input("Action ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_action(aid) is None:
        print(f"  ✗ No action #{aid}")
        _pause()
        return
    if _input(f"Delete action #{aid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_action(aid):
        print(f"\n  ✓ Deleted #{aid}")
    _pause()


# ── Review flows ──────────────────────────────────────────────────

def add_review_flow(risk_id: int | None = None) -> None:
    print("\n═══ Add Review ═══")
    try:
        rid = risk_id if risk_id is not None else int(
            _input("Risk ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_risk(rid)
    if existing is None:
        print(f"  ✗ No risk #{rid}")
        _pause()
        return
    print(f"\n  Reviewing risk: {existing.title}")
    print(f"    Current L={existing.likelihood}, "
          f"I={existing.impact}, status={existing.status}")
    try:
        when = _input("Review date (YYYY-MM-DD)",
                       default=_date.today().isoformat(),
                       allow_empty=False)
        reviewer = _input("Reviewer (optional)")
        summary = _input("Summary (optional)")
        new_l = _input(
            "New likelihood (1..5, blank = keep)")
        new_i = _input(
            "New impact (1..5, blank = keep)")
        new_s = _input(
            f"New status ({'/'.join(STATUSES)}, blank = keep)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rev = data.add_review(rid, {
            "review_date": when, "reviewer": reviewer,
            "summary": summary,
            "new_likelihood": new_l or None,
            "new_impact": new_i or None,
            "new_status": new_s or None,
            "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Recorded review #{rev.review_id}")
    refreshed = data.get_risk(rid)
    if refreshed is not None:
        print(f"    Risk #{rid} now: L={refreshed.likelihood}, "
              f"I={refreshed.impact}, status={refreshed.status}, "
              f"next review {refreshed.next_review}")
    _pause()


def list_recent_reviews() -> None:
    print("\n═══ Recent Reviews ═══")
    _print_reviews(data.list_reviews(limit=50))
    _pause()


def delete_review_flow() -> None:
    print("\n═══ Delete Review ═══")
    try:
        rid = int(_input("Review ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_review(rid) is None:
        print(f"  ✗ No review #{rid}")
        _pause()
        return
    if _input(f"Delete review #{rid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_review(rid):
        print(f"\n  ✓ Deleted #{rid}")
    _pause()


# ── Summary / heatmap ────────────────────────────────────────────

def overview_flow() -> None:
    print("\n═══ Risk Overview ═══")
    o = data.overview()
    print(f"\n  Total risks         : {o.total}")
    print(f"  Open                : {o.open}")
    print(f"  Closed              : {o.closed}")
    print(f"  Reviews due (open)  : {o.reviews_due}")
    print(f"  High or Critical    : {o.high_or_critical}")
    print(f"\n  Actions             : {o.actions_total} "
          f"({o.actions_open} open, {o.actions_overdue} overdue)")
    if o.by_band:
        print("\n  By inherent band:")
        for b in ("Low", "Medium", "High", "Critical"):
            n = o.by_band.get(b, 0)
            if n:
                print(f"    {b:<10} : {n}")
    if o.by_status:
        print("\n  By status:")
        for s in STATUSES:
            n = o.by_status.get(s, 0)
            if n:
                print(f"    {s:<14} : {n}")
    if any(o.by_category.values()):
        print("\n  By category:")
        for c in CATEGORIES:
            n = o.by_category.get(c, 0)
            if n:
                print(f"    {c:<20} : {n}")
    if o.top_risks:
        print("\n  Top risks:")
        for rid, title, score, status in o.top_risks:
            print(f"    #{rid:<4}  {title[:34]:<34}  "
                  f"score {score:>3} ({score_band(score):<8})  "
                  f"{status}")
    _print_heatmap()
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Overview",                overview_flow),
    ("Open Risks",              list_open),
    ("High / Critical Risks",   list_high),
    ("Risks Due for Review",    list_review_due),
    ("All Risks",               list_all),
    ("Filter",                  filter_risks),
    ("View Risk",               view_risk_flow),
    ("New Risk",                new_risk),
    ("Edit Risk",               edit_risk),
    ("Delete Risk",             delete_risk_flow),
    ("Add Action",              add_action_flow),
    ("Open Actions",            list_open_actions),
    ("Overdue Actions",         list_overdue_actions),
    ("Edit Action",             edit_action_flow),
    ("Delete Action",           delete_action_flow),
    ("Add Review",              add_review_flow),
    ("Recent Reviews",          list_recent_reviews),
    ("Delete Review",           delete_review_flow),
]


def run() -> None:
    while True:
        print("\n── Risk Management ──")
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
        except Exception as e:
            logger.exception("Risk-management CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Risk Management":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Risk-management CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
