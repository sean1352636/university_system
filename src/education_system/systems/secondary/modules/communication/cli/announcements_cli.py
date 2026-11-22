"""Announcements in the terminal.

The old menu keeps its numbers: 1 List all, 2 Live now, 3 Scheduled,
4 Pinned, 5 Banners, 6 Expired (unarchived), 7 Filter, 8 View, 10 New
announcement, 11 Edit, 12 Publish, 13 Schedule, 14 Withdraw, 15 Archive,
16 Toggle pin, 17 Toggle banner, 18 Change status, 19 Delete, 20 Auto-expire,
22 Summary (9 and 21 were separators). New: 23 Feed for an audience
(the old notices feed), 24 Search, 25 What I see now, 26 Acknowledge,
27 Read receipts, 28 E-mail the audience, 29 Duplicate, 30 Drafts,
31 Export CSV, 32 History. Rules live in
:mod:`modules.communication.domain.announcements`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.communication.domain import announcements as AN
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (AN.ValidationError, AN.PermissionDenied, AN.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[AN.Announcement]) -> None:
    if not rows:
        print("\n  (no announcements)")
        return
    print(f"\n  {'ID':<4} {'P':<2}{'B':<2} {'Category':<14} {'Pri':<10} {'Title':<30} "
          f"{'For':<20} {'Status':<10} Views")
    for a in rows:
        print(f"  {a.announcement_id:<4} {'★' if a.pinned else ' ':<2}{'▀' if a.banner else ' ':<2}"
              f" {a.category[:14]:<14} {a.priority_label:<10} {a.title[:30]:<30} "
              f"{a.audience_text[:20]:<20} {a.shown_status:<10} {a.view_count}")
    print(f"\n  {len(rows)} announcement(s).")


def _get() -> AN.Announcement | None:
    aid = _int("  Announcement ID: ")
    return AN.get(aid) if aid else None


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{cur}]" if cur not in (None, "") else "") + ": ")


def _details(cur: AN.Announcement | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label in (("title", "Title"), ("body", "Announcement"),
                       ("summary", "Summary (one line)")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = "" if v == prompts.CLEAR and key == "summary" else v
    c = _pick("Category", AN.CATEGORIES, cur.category if cur else AN.DEFAULT_CATEGORY)
    if c:
        out["category"] = c
    p = _pick("Priority", [f"{k} {v}" for k, v in AN.PRIORITY_LABELS.items()],
              f"{cur.priority} {cur.priority_label}" if cur else "2 Normal")
    if p:
        out["priority"] = p[:1]
    print("  Audiences: all staff, all pupils, parents, year 7-11, form <name> (comma "
          "separated)")
    v = _ask("For", cur.audience_text if cur else "")
    if v:
        out["audiences"] = v
    for key, label in (("pinned", "Pinned"), ("banner", "Banner"),
                       ("requires_acknowledgement", "Needs acknowledgement")):
        v = _ask(f"{label} (y/n)", ("y" if getattr(cur, key) else "n") if cur else "n")
        if v:
            out[key] = v.lower().startswith("y")
    for key, label in (("publish_on", "Publish on (YYYY-MM-DD, blank = when published)"),
                       ("expires_on", "Expires on"), ("linked_to", "Linked to"),
                       ("attachments_ref", "Attachments note"), ("notes", "Notes")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = "" if v == prompts.CLEAR else v
    return out


def _list(scope: str):
    def run(_p: Principal) -> None:
        _table(AN.list_announcements(scope=scope))
    return run


def _filter(_p: Principal) -> None:
    cat = _pick("Category (blank = all)", AN.CATEGORIES)
    st = _pick("Status (blank = all)", AN.STATUSES)
    aud = _prompt("  Audience (e.g. staff, year 9; blank = all): ")
    toks = AN.parse_audiences(aud, []) if aud else []
    minp = _prompt("  Minimum priority 1-5 (blank = any): ")
    _table(AN.list_announcements(category=cat or None, status=st or None,
                                 audience=toks[0] if toks else None,
                                 priority_min=int(minp) if minp.isdigit() else None))


def _show(a: AN.Announcement) -> None:
    print(f"\n  #{a.announcement_id}  {a.title}\n  {a.category} · {a.priority_label} · for "
          f"{a.audience_text}\n  Status: {a.shown_status}   Publish: "
          f"{a.publish_on or a.published_on or '-'}   Expires: {a.expires_on or '-'}\n"
          f"  By {a.author_name or a.author or '-'}   Views: {a.view_count}"
          + ("   Needs acknowledgement" if a.requires_acknowledgement else ""))
    if a.summary:
        print(f"\n  {a.summary}")
    print("\n  " + a.body.replace("\n", "\n  "))
    for label, v in (("Linked to", a.linked_to), ("Attachments", a.attachments_ref),
                     ("E-mailed", (a.emailed_at or "")[:16]), ("Notes", a.notes)):
        if v:
            print(f"  {label}: {v}")


def _view(principal: Principal) -> None:
    a = _get()
    if a:
        AN.mark_read(a.announcement_id, principal)
        _show(a)


def _new(principal: Principal) -> None:
    a = AN.create(_details(), actor=principal)
    print(f"  Draft #{a.announcement_id} saved.")
    if AN.can_publish(principal, a.audience_list) and _yes("  Publish it now?"):
        a = AN.publish(a.announcement_id, actor=principal)
        print(f"  {a.status}.")


def _edit(principal: Principal) -> None:
    a = _get()
    if a:
        changes = _details(a)
        if changes:
            AN.update(a.announcement_id, changes, actor=principal)
            print("  Saved.")


def _do(fn, done: str):
    def run(principal: Principal) -> None:
        a = _get()
        if a:
            a = fn(a.announcement_id, actor=principal)
            print(f"  {done}" + (f" Status: {a.shown_status}." if hasattr(a, "status") else ""))
    return run


def _schedule(principal: Principal) -> None:
    a = _get()
    if a:
        a = AN.schedule(a.announcement_id, _prompt("  Publish on (YYYY-MM-DD): "),
                        actor=principal)
        print(f"  Scheduled for {a.publish_on}.")


def _status(principal: Principal) -> None:
    a = _get()
    if a:
        st = _pick("Status", AN.STATUSES, a.status)
        AN.set_status(a.announcement_id, st or a.status, actor=principal)
        print("  Status saved.")


def _delete(principal: Principal) -> None:
    a = _get()
    if a and _yes(f"  Delete '{a.title}'?"):
        AN.delete(a.announcement_id, actor=principal)
        print("  Deleted.")


def _auto_expire(principal: Principal) -> None:
    print(f"  {AN.auto_expire(actor=principal)} announcement(s) marked Expired.")


def _summary(_p: Principal) -> None:
    s = AN.summary()
    print(f"\n  Total: {s.total}   Drafts: {s.drafts}   Scheduled: {s.scheduled}   Published: "
          f"{s.published}   Live now: {s.live_now}\n  Expired (unarchived): "
          f"{s.expired_unarchived}   Pinned: {s.pinned}   Banners: {s.banners}   Urgent: "
          f"{s.urgent_count}   Views: {s.total_views}")
    for label, d in (("By category", s.by_category), ("By status", s.by_status),
                     ("By audience", s.by_audience), ("By priority", s.by_priority)):
        print(f"  {label}: " + ", ".join(f"{k} {v}" for k, v in d.items()))


def _feed(_p: Principal) -> None:
    choices = [lab for _t, lab in AN.audience_choices()]
    got = _pick("Audience", choices)
    toks = AN.parse_audiences(got or "", [])
    if toks:
        _table(AN.feed_for_audience(toks[0]))


def _search(_p: Principal) -> None:
    _table(AN.list_announcements(search=_prompt("  Search for: ") or None))


def _mine(principal: Principal) -> None:
    rows = AN.active_for(principal)
    unread = {a.announcement_id for a in AN.unread_for(principal)}
    ack = {a.announcement_id for a in AN.needs_acknowledgement(principal)}
    if not rows:
        print("  Nothing showing for you now.")
    for a in rows:
        flag = "needs ack" if a.announcement_id in ack else (
            "new" if a.announcement_id in unread else "")
        print(f"  #{a.announcement_id:<4} {a.priority_label:<10} {a.title[:40]:<40} {flag}")


def _ack(principal: Principal) -> None:
    a = _get()
    if a:
        AN.acknowledge(a.announcement_id, principal)
        print("  Acknowledged.")


def _receipts(principal: Principal) -> None:
    a = _get()
    if a is None:
        return
    r = AN.receipts(a.announcement_id, actor=principal)
    print(f"\n  Read by {len(r['read'])}, acknowledged by {r['acknowledged']}")
    for x in r["read"]:
        print(f"    {x['read_at'][:16]}  {x['name']:<26} "
              + (f"ack {x['acknowledged_at'][:16]}" if x["acknowledged_at"] else ""))
    if r["staff_not_read"]:
        print("  Staff who haven't read it: " + ", ".join(r["staff_not_read"]))


def _email(principal: Principal) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    a = _get()
    if a is None:
        return
    who = AN.email_recipients(a.announcement_id)
    if not _yes(f"  E-mail '{a.title}' to {len(who['to'])} address(es)?"):
        return
    res = AN.email_audience(a.announcement_id, actor=principal)
    print(f"  {res['emails']} e-mail(s) saved.")
    try:
        E.deliver(res["message_id"], principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the e-mails stay in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _export(principal: Principal) -> None:
    path = _prompt("  Save CSV to (e.g. announcements.csv): ")
    if path:
        print(f"  Exported {AN.export_csv(path, actor=principal)} announcement(s).")


def _history(_p: Principal) -> None:
    a = _get()
    if a:
        for h in AN.history(a.announcement_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<12} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


_OPTIONS = {"1": _list("all"), "2": _list("live"), "3": _list("scheduled"),
            "4": _list("pinned"), "5": _list("banners"), "6": _list("expired"),
            "7": _filter, "8": _view, "10": _new, "11": _edit,
            "12": _do(lambda i, actor: AN.publish(i, actor=actor), "Published."),
            "13": _schedule, "14": _do(AN.withdraw, "Withdrawn."),
            "15": _do(AN.archive, "Archived."), "16": _do(AN.toggle_pin, "Pin toggled."),
            "17": _do(AN.toggle_banner, "Banner toggled."), "18": _status, "19": _delete,
            "20": _auto_expire, "22": _summary, "23": _feed, "24": _search, "25": _mine,
            "26": _ack, "27": _receipts, "28": _email,
            "29": _do(AN.duplicate, "Copied as a new draft."), "30": _list("drafts"),
            "31": _export, "32": _history}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("announcements.view")
        print("\n  ── Announcements ──")
        print("    1) List all\n    2) Live now\n    3) Scheduled\n    4) Pinned\n    5) Banners"
              "\n    6) Expired (unarchived)\n    7) Filter\n    8) View\n    ──────"
              "\n   10) New announcement\n   11) Edit\n   12) Publish\n   13) Schedule"
              "\n   14) Withdraw\n   15) Archive\n   16) Toggle pin\n   17) Toggle banner"
              "\n   18) Change status\n   19) Delete\n   20) Auto-expire\n    ──────"
              "\n   22) Summary")
        print("  More")
        print("   23) Feed for an audience\n   24) Search\n   25) What I see now"
              "\n   26) Acknowledge\n   27) Read receipts\n   28) E-mail the audience"
              "\n   29) Duplicate\n   30) Drafts\n   31) Export CSV\n   32) History")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
