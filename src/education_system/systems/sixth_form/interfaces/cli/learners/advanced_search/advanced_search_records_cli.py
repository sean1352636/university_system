"""Advanced Search CLI: acting on records in the current results.

Open a record, keep a shortlist, change student status, link duplicates
and edit a student inline: the CLI side of the GUI's Open / Shortlist /
Bulk & Triage actions. Record changes go through the domain ``actions``
module, so they need ``students.manage`` and keep the student history.
"""

from __future__ import annotations

from education_system.systems.sixth_form.domain.learners.advanced_search import (
    actions as search_actions,
    exports as search_exports,
    history as search_history,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    Hit,
    SCOPE_LABELS,
    ValidationError,
)

#: Session shortlist, like the GUI's Shortlist page.
_SHORTLIST: list[Hit] = []


def _base():
    from . import advanced_search_cli
    return advanced_search_cli


def _may_manage() -> bool:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    if access.current().can(access.STUDENTS_MANAGE):
        return True
    print("\n  ✗ This needs the manage-students permission.")
    _base()._pause()
    return False


def _one_hit(prompt: str = "Entity id") -> Hit | None:
    b = _base()
    res = b._require_last()
    if res is None:
        return None
    b._print_results(res)
    eid = b._input(prompt, allow_empty=False)
    scope = ""
    if "#" in eid:                      # accept the printed scope#id form
        scope, _, eid = eid.partition("#")
    hits = [h for h in res.all_hits()
            if h.entity_id == eid and (not scope or h.scope == scope)]
    if not hits:
        print("  No such record in the current results.")
        b._pause()
        return None
    return hits[0]


# ── Open a record ─────────────────────────────────────────────────

def open_record_flow() -> None:
    """Show every field of one result, and for a record about a student,
    that student's profile summary."""
    b = _base()
    h = _one_hit()
    if h is None:
        return
    print(f"\n═══ {SCOPE_LABELS.get(h.scope, h.scope)} — {h.entity_id} ═══")
    print(f"  {h.label}")
    if h.sublabel:
        print(f"  {h.sublabel}")
    doc = (h.extra or {}).get("_doc") or {}
    for k, v in doc.items():
        if (k.startswith("_") and k not in ("_date", "_grade")) or v in (None, ""):
            continue
        print(f"  {k.lstrip('_'):>16}: {v}")
    search_exports.audit_export(b._results_from_hits([h], h.label), "open",
                                f"{h.scope}#{h.entity_id}", 1)
    sid = b._hit_student_id(h)
    if sid:
        _print_profile(sid)
    b._pause()


def _print_profile(student_id: str) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    from education_system.systems.sixth_form.domain.learners.students import directory
    try:
        prof = directory.student_profile(student_id, principal=access.current())
    except Exception as e:  # noqa: BLE001
        print(f"\n  (could not load the profile of {student_id}: {e})")
        return
    if prof is None:
        return
    s = prof.student
    print(f"\n  ── Student {s.student_id}: {s.full_name} ({s.status}) ──")
    for label, value in (("Email", s.email), ("Personal email", s.personal_email),
                         ("Phone", s.phone), ("DOB", s.date_of_birth),
                         ("Subjects", ", ".join(s.subjects or []))):
        if value:
            print(f"  {label:>16}: {value}")
    if prof.tutor_group:
        print(f"  {'Tutor group':>16}: {prof.tutor_group}"
              + (f" ({prof.tutor})" if prof.tutor else ""))
    for rec in prof.records:
        print(f"  {rec.area:>16}: {rec.summary}   (menu: {rec.menu_label})")


# ── Shortlist ─────────────────────────────────────────────────────

def shortlist_add_flow() -> None:
    b = _base()
    have = {(h.scope, h.entity_id) for h in _SHORTLIST}
    added = 0
    for h in b._pick_hits_from_last():
        if (h.scope, h.entity_id) not in have:
            _SHORTLIST.append(h)
            have.add((h.scope, h.entity_id))
            added += 1
    print(f"\n  ✓ Added {added} ({len(_SHORTLIST)} on the shortlist).")
    b._pause()


def shortlist_show_flow() -> None:
    b = _base()
    if not _SHORTLIST:
        print("\n  The shortlist is empty.")
    else:
        print(f"\n  Shortlist ({len(_SHORTLIST)}):")
        for h in _SHORTLIST:
            print(f"    [{h.scope}#{h.entity_id}]  {h.label}")
        if b._input("Use it as the current results? y/N",
                    default="n").lower().startswith("y"):
            b._store_last(b._results_from_hits(list(_SHORTLIST), "shortlist"))
            print("  ✓ The shortlist is now the current result set.")
    b._pause()


def shortlist_remove_flow() -> None:
    b = _base()
    raw = b._input("Entity ids to remove (comma list, or 'all')", default="all")
    if raw.lower() == "all":
        n = len(_SHORTLIST)
        _SHORTLIST.clear()
    else:
        ids = {t.strip() for t in raw.split(",") if t.strip()}
        keep = [h for h in _SHORTLIST if h.entity_id not in ids]
        n = len(_SHORTLIST) - len(keep)
        _SHORTLIST[:] = keep
    print(f"\n  ✓ Removed {n}.")
    b._pause()


def shortlist_cohort_flow() -> None:
    b = _base()
    ids = list(dict.fromkeys(sid for sid in (b._hit_student_id(h)
                                              for h in _SHORTLIST) if sid))
    if not ids:
        print("\n  No students on the shortlist.")
        b._pause()
        return
    name = b._input("Cohort name", default="shortlist")
    try:
        c = search_history.create_cohort(name, ids)
        print(f"\n  ✓ Cohort {c.name!r} saved with {c.member_count} student(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    b._pause()


# ── Record changes ────────────────────────────────────────────────

def bulk_status_flow() -> None:
    """Change the status of selected students in the current results,
    through the same route as the Student Directory."""
    b = _base()
    if b._require_last() is None or not _may_manage():
        return
    hits = [h for h in b._pick_hits_from_last() if h.scope == "students"]
    if not hits:
        print("\n  No student records selected.")
        b._pause()
        return
    statuses = search_actions.statuses()
    print("  Statuses: " + ", ".join(statuses))
    new = b._input("New status", allow_empty=False)
    if new not in statuses:
        print(f"\n  ✗ Unknown status {new!r}.")
        b._pause()
        return
    reason = b._input("Reason" + (" (required — they are withdrawn)"
                                  if new == "Left" else ""),
                      allow_empty=new != "Left")
    leaving = b._input("Leaving date (YYYY-MM-DD, blank = today)") \
        if new == "Left" else ""
    if b._input(f"Set status to {new!r} for {len(hits)} student(s)? Type 'yes'",
                default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        res = search_actions.bulk_set_status(
            [h.entity_id for h in hits], new, reason=reason or None,
            leaving_date=leaving or None)
    except Exception as e:  # noqa: BLE001
        print(f"\n  ✗ {e}")
        b._pause()
        return
    print(f"\n  ✓ Status → {new!r}: {len(res.changed)} changed"
          + (f", {len(res.unchanged)} already {new}" if res.unchanged else "")
          + (f", {len(res.failed)} failed" if res.failed else "") + ".")
    for sid, why in res.failed.items():
        print(f"     {sid}: {why}")
    b._pause()


def merge_duplicates_flow() -> None:
    b = _base()
    if b._require_last() is None or not _may_manage():
        return
    keep = b._input("Student id to KEEP", allow_empty=False)
    dup = b._input("Duplicate student id", allow_empty=False)
    print("\n  Empty fields on the kept record are filled from the duplicate,"
          "\n  and both records' history notes the link. The duplicate's own"
          "\n  records stay on it until it is withdrawn in the directory.")
    if b._input("Link them? Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        link = search_actions.link_duplicate(keep, dup)
    except Exception as e:  # noqa: BLE001
        print(f"\n  ✗ {e}")
        b._pause()
        return
    print(f"\n  ✓ {dup} marked as a duplicate of {keep}.")
    print(f"    Filled on {keep}: {', '.join(link.filled) or 'nothing'}")
    if link.linked_records:
        print(f"    Still on {dup}: " + ", ".join(
            f"{t} {n}" for t, n in sorted(link.linked_records.items())))
    b._pause()


def inline_edit_flow() -> None:
    b = _base()
    if not _may_manage():
        return
    h = _one_hit("Student id to edit")
    if h is None:
        return
    if h.scope != "students":
        print("\n  Pick a student row.")
        b._pause()
        return
    from education_system.systems.sixth_form.domain.learners.students import students
    stu = students.get_student(h.entity_id)
    if stu is None:
        print(f"\n  ✗ No student {h.entity_id}.")
        b._pause()
        return
    changes = {attr: b._input(label, default=getattr(stu, attr) or "")
               for attr, label in search_actions.INLINE_FIELDS}
    print("  Statuses: " + ", ".join(search_actions.statuses()))
    status = b._input("Status", default=stu.status)
    reason = b._input("Reason for the status change") \
        if status != stu.status else ""
    try:
        search_actions.inline_update(stu.student_id, changes, status=status,
                                     reason=reason or None)
        print(f"\n  ✓ Updated {stu.student_id}.")
    except Exception as e:  # noqa: BLE001
        print(f"\n  ✗ {e}")
    b._pause()
