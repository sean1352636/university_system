"""Letters in the terminal.

The old Letter Templates menu keeps its numbers: 1 List all, 2 Active,
3 Drafts, 4 Archived, 5 Filter, 6 View, 8 New template, 9 Edit, 10 Activate,
11 Archive, 12 Retire, 13 Change status, 14 Duplicate, 15 Preview, 16 Render,
17 Record use, 18 Delete, 20 Summary (7 and 19 were separators). New:
21 Send a letter (mail merge), 22 Sent letters, 23 A mail merge's letters,
24 Print copies (to a text file), 25 Record a reply, 26 Replies waiting,
27 Chase replies, 28 A pupil's letters, 29 Export CSV, 30 History. Rules
live in :mod:`modules.communication.domain.letters`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.communication.domain import letters as L
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (L.ValidationError, L.PermissionDenied, L.NotFound)
_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[L.Template]) -> None:
    if not rows:
        print("\n  (no templates)")
        return
    print(f"\n  {'ID':<4} {'Name':<30} {'Category':<20} {'Recipient':<15} {'Format':<20} "
          f"{'Status':<9} Uses")
    for t in rows:
        print(f"  {t.template_id:<4} {t.name[:30]:<30} {t.category[:20]:<20} "
              f"{t.recipient_type[:15]:<15} {t.format[:20]:<20} {t.status:<9} {t.use_count}")
    print(f"\n  {len(rows)} template(s).")


def _get() -> L.Template | None:
    tid = _int("  Template ID: ")
    return L.get_template(tid) if tid else None


def _ask(label: str, cur: Any) -> str:
    return _prompt(f"  {label}" + (f" [{str(cur)[:60]}]" if cur not in (None, "") else "")
                   + ": ")


def _multiline(label: str, cur: str | None) -> str | None:
    """Several lines, ended by a line with a single '.'; Enter first keeps it."""
    print(f"  {label} - type the lines, then a line with just '.'"
          + (" (Enter first keeps the current text)" if cur else ""))
    lines: list[str] = []
    while True:
        line = _prompt("  > ")
        if line == "" and not lines and cur:
            return None
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def _details(cur: L.Template | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, label in (("name", "Name"), ("description", "Description")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = v
    for key, label, opts, default in (
            ("category", "Category", L.CATEGORIES, L.DEFAULT_CATEGORY),
            ("recipient_type", "Recipient", L.RECIPIENT_TYPES, L.DEFAULT_RECIPIENT),
            ("format", "Format", L.FORMATS, L.DEFAULT_FORMAT)):
        v = _pick(label, opts, getattr(cur, key) if cur else default)
        if v:
            out[key] = v
    v = _ask("Subject line", cur.subject_line if cur else "")
    if v:
        out["subject_line"] = v
    print("  Merge fields: " + ", ".join("{" + f + "}" for f in L.STANDARD_FIELDS))
    body = _multiline("Body", cur.body if cur else None)
    if body is not None:
        out["body"] = body
    for key, label in (("letterhead", "Letterhead"), ("signature", "Signature"),
                       ("footer", "Footer"), ("sender_role", "Sender role"),
                       ("merge_fields", "Custom fields (e.g. trip, cost)"),
                       ("attachments_ref", "Attachments note")):
        v = _ask(label, getattr(cur, key) if cur else "")
        if v:
            out[key] = "" if v == prompts.CLEAR else v
    rs = _ask("Reply slip? (y/n)", ("y" if cur.reply_slip else "n") if cur else "n")
    if rs:
        out["reply_slip"] = rs.lower().startswith("y")
    if out.get("reply_slip", cur.reply_slip if cur else False):
        v = _ask("Reply slip question", cur.reply_question if cur else "")
        if v:
            out["reply_question"] = v
    v = _ask("Notes", cur.notes if cur else "")
    if v:
        out["notes"] = "" if v == prompts.CLEAR else v
    return out


def _list(scope: str):
    def run(_p: Principal) -> None:
        _table(L.list_templates(scope=scope))
    return run


def _filter(_p: Principal) -> None:
    _table(L.list_templates(category=_pick("Category (blank = all)", L.CATEGORIES) or None,
                            recipient_type=_pick("Recipient (blank = all)",
                                                 L.RECIPIENT_TYPES) or None,
                            format=_pick("Format (blank = all)", L.FORMATS) or None,
                            search=_prompt("  Search (blank = none): ") or None))


def _view(_p: Principal) -> None:
    t = _get()
    if t is None:
        return
    print(f"\n  #{t.template_id} {t.name}  [{t.status}]  {t.category} · {t.recipient_type} · "
          f"{t.format}\n  Used {t.use_count} time(s), last {t.last_used_on or '-'}")
    if t.description:
        print(f"  {t.description}")
    print(f"\n  Subject: {t.subject_line}\n")
    print("  " + L.preview(t).body.replace("\n", "\n  "))
    print("\n  Merge fields: " + (", ".join("{" + f + "}" for f in t.detected_placeholders)
                                  or "(none)"))
    if t.reply_slip:
        print(f"  Reply slip: {t.reply_question}")


def _new(principal: Principal) -> None:
    data = _details()
    if L.is_editor(principal) and _yes("  Make it active now?"):
        data["status"] = "Active"
    t = L.create_template(data, actor=principal)
    print(f"  Created template #{t.template_id} ({t.status}).")


def _edit(principal: Principal) -> None:
    t = _get()
    if t:
        changes = _details(t)
        if changes:
            L.update_template(t.template_id, changes, actor=principal)
            print("  Saved.")


def _status_to(status: str):
    def run(principal: Principal) -> None:
        t = _get()
        if t:
            L.set_status(t.template_id, status, actor=principal)
            print(f"  {status}.")
    return run


def _status(principal: Principal) -> None:
    t = _get()
    if t:
        st = _pick("Status", L.STATUSES, t.status)
        L.set_status(t.template_id, st or t.status, actor=principal)
        print("  Status saved.")


def _duplicate(principal: Principal) -> None:
    t = _get()
    if t:
        c = L.duplicate(t.template_id, actor=principal)
        print(f"  Copied as draft #{c.template_id} '{c.name}'.")


def _custom(t: L.Template) -> dict[str, str]:
    return {f: _prompt(f"  {{{f}}}: ") for f in t.custom_fields
            if f in t.detected_placeholders}


def _preview(_p: Principal) -> None:
    t = _get()
    if t is None:
        return
    ref = _prompt("  Pupil to preview for (admission no.; blank = raw template): ")
    custom = _custom(t) if ref else {}
    r = L.preview(t, ref or None, custom,
                  reply_by=(_prompt("  Reply by (date, blank ok): ") or None) if ref and
                  t.reply_slip else None)
    print(f"\n  Subject: {r.subject}\n\n  " + r.body.replace("\n", "\n  "))


def _render(_p: Principal) -> None:
    t = _get()
    if t is None:
        return
    values = {f: _prompt(f"  {{{f}}}: ") for f in t.detected_placeholders}
    r = L.render(t, {k: v for k, v in values.items() if v})
    print(f"\n  Subject: {r.subject}\n\n  " + r.body.replace("\n", "\n  "))
    if r.missing:
        print(f"\n  Not filled in: {', '.join(r.missing)}")


def _record_use(principal: Principal) -> None:
    t = _get()
    if t:
        print(f"  Uses: {L.record_use(t.template_id, actor=principal).use_count}")


def _delete(principal: Principal) -> None:
    t = _get()
    if t and _yes(f"  Delete template '{t.name}'?"):
        L.delete_template(t.template_id, actor=principal)
        print("  Deleted.")


def _summary(_p: Principal) -> None:
    s = L.summary()
    print(f"\n  Templates: {s.total}   Active: {s.active}   Drafts: {s.drafts}   Archived: "
          f"{s.archived}   Retired: {s.retired}   Uses: {s.total_uses}   With reply slip: "
          f"{s.with_reply_slip}")
    if s.most_used:
        print("  Most used: " + ", ".join(f"{n} ({c})" for n, c in s.most_used))
    for label, d in (("By category", s.by_category), ("By recipient", s.by_recipient),
                     ("By format", s.by_format)):
        print(f"  {label}: " + ", ".join(f"{k} {v}" for k, v in d.items()))
    print(f"  Mail merges: {s.sends}   Letters sent: {s.letters_sent}   Awaiting replies: "
          f"{s.awaiting_replies}")


def _deliver(principal: Principal, message_id: int | None) -> None:
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    if not message_id:
        return
    try:
        E.deliver(message_id, principal=principal)
        print("  Sent.")
    except Exception as e:  # noqa: BLE001 - the e-mails stay in the outbox
        print(f"  Saved in the outbox; not sent yet ({e}).")


def _send(principal: Principal) -> None:
    for t in L.list_templates(scope="active"):
        print(f"    #{t.template_id:<4} {t.name} ({t.category})")
    t = _get()
    if t is None:
        return
    kinds = ("Chosen pupils", "Form", "Year group") if L.is_editor(principal) else (
        "Chosen pupils",)
    kind = _pick("Send to", kinds, kinds[0])
    audience: dict[str, Any] = {}
    if kind == "Form":
        audience["form"] = _prompt("  Form: ")
    elif kind == "Year group":
        audience["year"] = _prompt("  Year group (7-11): ")
    else:
        audience["pupil_ids"] = L.parse_pupil_refs(_prompt("  Pupils (admission nos.): "))
    custom = _custom(t)
    reply_by = (_prompt("  Reply by (YYYY-MM-DD): ") or None) if t.reply_slip else None
    c = L.check_send(t.template_id, actor=principal, custom=custom, reply_by=reply_by,
                     **audience)
    first = c["pupils"][0]
    r = L.preview(t, first.pupil_id, custom, reply_by=reply_by)
    print(f"\n  Preview for {first.display_name}:\n  Subject: {r.subject}\n\n  "
          + r.body.replace("\n", "\n  "))
    print(f"\n  {len(c['pupils'])} letter(s); {c['emails']} e-mail address(es); "
          f"{len(c['no_email'])} need a printed copy.")
    if not _yes("  Send?"):
        return
    res = L.send(t.template_id, actor=principal, custom=custom, reply_by=reply_by, **audience)
    print(f"  Mail merge #{res['send_id']}: {res['letters']} letter(s), {res['emails']} "
          "e-mail(s).")
    if res["no_email"]:
        print(f"  {len(res['no_email'])} family(ies) have no e-mail - print their copies "
              "(option 24).")
    _deliver(principal, res["message_id"])


def _sent(principal: Principal) -> None:
    mine = not L.is_editor(principal) or _yes("  Only mine?")
    rows = L.list_sends(sent_by=principal.username if mine else None)
    if not rows:
        print("  (nothing sent)")
    for s in rows:
        rep = ""
        if s.reply_question:
            r = L.reply_summary(s.send_id)
            rep = f"{r['yes']} yes / {r['no']} no / {r['no_reply']} waiting"
        print(f"  #{s.send_id:<4} {s.sent_at[:16]}  {s.template_name[:26]:<26} "
              f"{s.audience_label[:18]:<18} {s.letters:>3} letters {s.emails:>3} e-mails  {rep}")


def _send_id() -> int | None:
    return _int("  Mail merge #: ")


def _letters(_p: Principal) -> None:
    sid = _send_id()
    if not sid:
        return
    s = L.get_send(sid)
    if s.reply_question:
        print(f"  Reply slip: {s.reply_question}" + (f" (by {s.reply_by})" if s.reply_by
                                                     else ""))
    for r in L.recipients(sid):
        print(f"  letter {r.recipient_id:<5} {r.pupil_name[:24]:<24} {r.form_group or '':<5} "
              f"{r.emails} e-mail(s) {'printed' if r.printed_at else '':<8} "
              f"{r.reply or ('waiting' if s.reply_question else '')}")


def _print(principal: Principal) -> None:
    sid = _send_id()
    if not sid:
        return
    only = not _yes("  Every letter (not just families without e-mail)?")
    path = _prompt("  Save to (e.g. letters.txt): ")
    if path:
        n = L.export_text(sid, path, actor=principal, only_no_email=only)
        print(f"  Saved {n} letter(s) to {path} (a form feed between letters).")


def _reply(principal: Principal) -> None:
    rid = _int("  Letter #: ")
    if rid:
        r = L.record_reply(rid, _pick("Reply", L.REPLIES) or "", actor=principal,
                           note=_prompt("  Note (blank ok): ") or None)
        print(f"  Recorded: {r.reply}.")


def _waiting(_p: Principal) -> None:
    rows = L.chase_list()
    if not rows:
        print("  No replies waiting.")
    for r in rows:
        print(f"  letter {r.recipient_id:<5} by {r.reply_by or '-':<10} "
              f"{r.template_name[:22]:<22} {r.pupil_name[:22]:<22} {r.form_group or '':<5} "
              f"chased {r.chase_count}")


def _chase(principal: Principal) -> None:
    sid = _send_id()
    if sid and _yes(f"  E-mail a reminder to the {len(L.chase_list(sid))} family(ies) who "
                    "haven't replied?"):
        res = L.chase(sid, actor=principal)
        print(f"  {res['emails']} reminder(s) saved.")
        if res["no_email"]:
            print("  No e-mail (phone them): " + ", ".join(r.pupil_name
                                                           for r in res["no_email"]))
        _deliver(principal, res["message_id"])


def _pupil(_p: Principal) -> None:
    p = L._pupil(_prompt("  Pupil (admission no. or ID): "))
    if p is None:
        print("  No such pupil.")
        return
    rows = L.for_pupil(p.pupil_id)
    print(f"\n  {len(rows)} letter(s) sent home about {p.display_name}")
    for r in rows:
        print(f"  {r.sent_at[:10]}  {r.template_name[:32]:<32} "
              + (f"reply: {r.reply or 'waiting'}" if r.reply_question else ""))


def _export(principal: Principal) -> None:
    sid = _send_id()
    path = _prompt("  Save CSV to (e.g. letters.csv): ") if sid else ""
    if sid and path:
        print(f"  Exported {L.export_csv(sid, path, actor=principal)} letter(s).")


def _history(_p: Principal) -> None:
    t = _get()
    if t:
        for h in L.history(template_id=t.template_id):
            print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
                  + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


_OPTIONS = {"1": _list("all"), "2": _list("active"), "3": _list("drafts"),
            "4": _list("archived"), "5": _filter, "6": _view, "8": _new, "9": _edit,
            "10": _status_to("Active"), "11": _status_to("Archived"),
            "12": _status_to("Retired"), "13": _status, "14": _duplicate, "15": _preview,
            "16": _render, "17": _record_use, "18": _delete, "20": _summary, "21": _send,
            "22": _sent, "23": _letters, "24": _print, "25": _reply, "26": _waiting,
            "27": _chase, "28": _pupil, "29": _export, "30": _history}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("letters.view")
        print("\n  ── Letters ──")
        print("    1) List all\n    2) Active\n    3) Drafts\n    4) Archived\n    5) Filter"
              "\n    6) View\n    ──────\n    8) New template\n    9) Edit\n   10) Activate"
              "\n   11) Archive\n   12) Retire\n   13) Change status\n   14) Duplicate"
              "\n   15) Preview\n   16) Render\n   17) Record use\n   18) Delete\n    ──────"
              "\n   20) Summary")
        print("  More")
        print("   21) Send a letter (mail merge)\n   22) Sent letters"
              "\n   23) A mail merge's letters\n   24) Print copies (to a text file)"
              "\n   25) Record a reply\n   26) Replies waiting\n   27) Chase replies"
              "\n   28) A pupil's letters\n   29) Export CSV\n   30) History")
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
