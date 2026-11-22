"""Alumni office screens on the alumni rules: giving (gifts, Gift Aid,
claims, pledges, campaigns), the alumnus's own giving, and chapters.

Mentoring, moderation, the forum and stories are in
``alumni_office_mentoring``; this module re-exports their entry points so
the main window imports one place.

Every action runs one rule from ``university/application/alumni/`` in its
own transaction through ``infrastructure.ui.record_screens.call``; the rules check
permissions, the screens only decide what to offer.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.university.infrastructure.ui import record_screens as common

Field = common.Field


def _rules(name):
    import importlib
    return importlib.import_module(f"education_system.systems.university.application.alumni.{name}")


# ── shared bits ─────────────────────────────────────────────────────────


def who_of(app):
    """The signed-in AlumniUser (cached on the app)."""
    who = getattr(app, "who", None)
    if who is None:
        user = getattr(app, "current_user", None)
        who = common.call(app.root, _rules("access").from_user, user, write=True,
                          quiet=True) if user else None
        app.who = who
    return who


def page(app, title, subtitle=""):
    if hasattr(app, "clear_content"):
        app.clear_content()
    else:
        for child in app.content_frame.winfo_children():
            child.destroy()
    frame = ttk.Frame(app.content_frame, padding=8)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=title, font=("Arial", 16, "bold")).pack(anchor="w")
    if subtitle:
        ttk.Label(frame, text=subtitle, foreground="#555555", wraplength=1000).pack(anchor="w")
    return frame


def refuse(frame, message):
    ttk.Label(frame, text=message, padding=30, wraplength=700).pack()


def bar(parent):
    """Button bar packed at the bottom before the list, so it stays visible."""
    frame = ttk.Frame(parent, padding=(0, 4))
    frame.pack(side="bottom", fill="x")
    return frame


def button(parent, text, command):
    ttk.Button(parent, text=text, command=command).pack(side="left", padx=3)


def sel(tree):
    return common.selected(tree)


def need(app, tree, what="a row"):
    rid = sel(tree)
    if rid is None:
        common.info(app.root, f"Select {what} first.")
    return rid


def write(app, fn, *args, then=None, **kwargs):
    result = common.call(app.root, fn, *args, write=True, **kwargs)
    if result is not None and then:
        then()
    return result


def money(v):
    return common.money(v)


def notebook(frame):
    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True, pady=(6, 0))
    return nb


def tab(nb, text):
    t = ttk.Frame(nb, padding=6)
    nb.add(t, text=f"  {text}  ")
    return t


# ── giving (fundraising staff) ──────────────────────────────────────────


def _campaign_choices(app):
    rows = common.call(app.root, _rules("giving").campaigns, quiet=True) or []
    return [(None, "")] + [(c["campaign_id"], c["campaign_name"]) for c in rows]


def _gifts_tab(app, nb, who):
    ag = _rules("giving")
    t = tab(nb, "Gifts")
    top = ttk.Frame(t)
    top.pack(side="top", fill="x")
    ttk.Label(top, text="Search").pack(side="left")
    search = tk.StringVar()
    ttk.Entry(top, textvariable=search, width=22).pack(side="left", padx=4)
    ttk.Label(top, text="Campaign").pack(side="left", padx=(8, 0))
    camp = tk.StringVar()
    campaigns = dict((label, cid) for cid, label in _campaign_choices(app))
    ttk.Combobox(top, textvariable=camp, values=list(campaigns), width=28,
                 state="readonly").pack(side="left", padx=4)
    b = bar(t)
    tree = common.make_tree(t, [("date", "Date", 90), ("alumni", "Alumnus", 90),
                                ("donor", "Donor", 150), ("amount", "Amount", 80),
                                ("campaign", "Campaign", 150), ("aid", "Gift Aid", 70),
                                ("status", "Status", 80), ("receipt", "Receipt", 120)])

    def refresh():
        rows = common.call(app.root, ag.gifts, who, campaign_id=campaigns.get(camp.get()),
                           search=search.get().strip() or None) or []
        common.fill(tree, rows, lambda r: r["donation_id"],
                    lambda r: (r["donation_date"], r["alumni_id"], r.get("donor_name"),
                               money(r["amount"]), r.get("campaign_name"),
                               "yes" if r.get("is_gift_aided") else "no",
                               r.get("status") or "received", r.get("receipt_number")))

    def record():
        ans = common.ask(app.root, "Record a gift", [
            Field("alumni_id", "Alumnus (id)", required=True),
            Field("amount", "Amount (£)", "number", required=True),
            Field("gift_date", "Gift date", "date"),
            Field("campaign_id", "Campaign", "combo", _campaign_choices(app)),
            Field("method", "Payment method", "combo", list(ag.METHODS)),
            Field("gift_aid", "Claim Gift Aid (needs a declaration)", "check"),
            Field("notes", "Notes", "multiline")], {"method": "card"})
        if not ans:
            return
        result = write(app, ag.record_gift, who, ans["alumni_id"], ans["amount"],
                       gift_date=ans["gift_date"] or None, campaign_id=ans["campaign_id"] or None,
                       method=ans["method"] or "card", gift_aid=ans["gift_aid"],
                       notes=ans["notes"], then=refresh)
        if result:
            ag.post_to_finance(result, who.username)
            common.info(app.root, f"Recorded {result['receipt_number']}"
                        + (" with Gift Aid." if result["gift_aided"] else "."))

    def refund():
        rid = need(app, tree, "a gift")
        if rid is None:
            return
        reason = common.ask_text(app.root, "Refund gift", "Reason for the refund")
        if reason:
            result = write(app, ag.refund_gift, who, int(rid), reason, then=refresh)
            if result and result["gift_aid_to_repay"]:
                common.info(app.root, f"This gift was in a Gift Aid claim: "
                                      f"{money(result['gift_aid_to_repay'])} comes off the next "
                                      "claim.")

    button(b, "Record gift…", record)
    button(b, "Refund…", refund)
    button(b, "Refresh", refresh)
    ttk.Button(top, text="Search", command=refresh).pack(side="left", padx=4)
    refresh()


def _declarations_panel(app, parent, who, alumni_id_var, online=False):
    ag = _rules("giving")
    b = bar(parent)
    tree = common.make_tree(parent, [("made", "Made on", 90), ("name", "Name", 160),
                                     ("postcode", "Postcode", 80), ("method", "Method", 70),
                                     ("past", "Covers 4 yrs", 90), ("cancelled", "Cancelled",
                                                                     110)], height=6)

    def refresh():
        aid = alumni_id_var.get().strip()
        rows = (common.call(app.root, ag.declarations, aid, quiet=True) or []) if aid else []
        common.fill(tree, rows, lambda r: r["declaration_id"],
                    lambda r: (r["made_on"], r["full_name"], r["postcode"], r["method"],
                               "yes" if r["covers_past_four_years"] else "no",
                               r.get("cancelled_at") or ""))

    def add():
        aid = alumni_id_var.get().strip()
        if not aid:
            common.info(app.root, "Enter the alumnus first.")
            return
        fields = [Field("full_name", "Full name", required=True),
                  Field("house", "House name or number", required=True),
                  Field("postcode", "Postcode", required=True)]
        if not online:
            fields += [Field("method", "How given", "combo", ["written", "oral"]),
                       Field("made_on", "Made on", "date")]
        fields += [Field("covers_past_four_years", "Also covers gifts in the last 4 years",
                         "check"),
                   Field("taxpayer_confirmed", "I pay enough UK Income or Capital Gains Tax to "
                                               "cover the Gift Aid on my gifts", "check")]
        ans = common.ask(app.root, "Gift Aid declaration", fields,
                         {"method": "written", "covers_past_four_years": True})
        if ans:
            write(app, ag.add_declaration, who, aid, full_name=ans["full_name"],
                  house=ans["house"], postcode=ans["postcode"],
                  method=ans.get("method") or "online", made_on=ans.get("made_on") or None,
                  covers_past_four_years=ans["covers_past_four_years"],
                  taxpayer_confirmed=ans["taxpayer_confirmed"], then=refresh)

    def cancel():
        rid = need(app, tree, "a declaration")
        if rid and common.confirm(app.root, "Cancel this Gift Aid declaration?"):
            write(app, ag.cancel_declaration, who, int(rid), then=refresh)

    button(b, "Add declaration…", add)
    button(b, "Cancel declaration", cancel)
    return refresh


def _declarations_tab(app, nb, who):
    t = tab(nb, "Gift Aid declarations")
    top = ttk.Frame(t)
    top.pack(side="top", fill="x")
    ttk.Label(top, text="Alumnus (id)").pack(side="left")
    aid = tk.StringVar()
    ttk.Entry(top, textvariable=aid, width=16).pack(side="left", padx=4)
    refresh = _declarations_panel(app, t, who, aid)
    ttk.Button(top, text="Show", command=refresh).pack(side="left", padx=4)


def _claims_tab(app, nb, who):
    ag = _rules("giving")
    t = tab(nb, "Gift Aid claims")
    b = bar(t)
    tree = common.make_tree(t, [("period", "Period", 190), ("gifts", "Gifts", 60),
                                ("total", "Donations", 100), ("adjust", "Adjustments", 100),
                                ("claim", "Claim", 100), ("status", "Status", 80),
                                ("ref", "HMRC ref", 120)])

    def refresh():
        rows = common.call(app.root, ag.claims) or []
        common.fill(tree, rows, lambda r: r["claim_id"],
                    lambda r: (f"{r['period_from']} – {r['period_to']}", r["gift_count"],
                               money(r["donations_total"]), money(r.get("adjustments_total")),
                               money(r["claim_total"]), r["status"], r.get("hmrc_reference")))

    def build():
        ans = common.ask(app.root, "Build a Gift Aid claim", [
            Field("from", "From", "date", required=True), Field("to", "To", "date",
                                                                  required=True)])
        if ans:
            result = write(app, ag.build_claim, who, ans["from"], ans["to"], then=refresh)
            if result:
                common.info(app.root, f"Draft claim: {result['gifts']} gift(s), "
                                      f"{money(result['donations_total'])} given, adjustments "
                                      f"{money(result['adjustments'])}, claim "
                                      f"{money(result['claim_total'])}.")

    def delete():
        rid = need(app, tree, "a claim")
        if rid and common.confirm(app.root, "Delete this draft claim?"):
            write(app, ag.delete_draft_claim, who, int(rid), then=refresh)

    def submit():
        rid = need(app, tree, "a claim")
        if rid:
            ref = common.ask_text(app.root, "Submit claim", "HMRC reference", multiline=False)
            if ref:
                write(app, ag.submit_claim, who, int(rid), ref, then=refresh)

    def paid():
        rid = need(app, tree, "a claim")
        if rid:
            write(app, ag.mark_claim_paid, who, int(rid), then=refresh)

    for text, cmd in (("Build claim…", build), ("Delete draft", delete), ("Submit…", submit),
                      ("Mark paid", paid), ("Refresh", refresh)):
        button(b, text, cmd)
    refresh()


def _pledge_columns():
    return [("alumni", "Alumnus", 90), ("amount", "Amount", 80), ("freq", "Frequency", 90),
            ("paid", "Paid", 70), ("next", "Next due", 90), ("status", "Status", 90)]


def _pledge_values(r):
    return (r["alumni_id"], money(r["amount"]), r["frequency"],
            f"{r['paid_instalments']}/{r['instalments']}", r.get("next_due") or "", r["status"])


def _pledge_fields(app, with_alumnus):
    ag = _rules("giving")
    fields = [Field("alumni_id", "Alumnus (id)", required=True)] if with_alumnus else []
    return fields + [Field("amount", "Amount per instalment (£)", "number", required=True),
                     Field("frequency", "Frequency", "combo", list(ag.FREQUENCIES)),
                     Field("instalments", "Instalments"),
                     Field("start", "First payment", "date"),
                     Field("campaign_id", "Campaign", "combo", _campaign_choices(app))]


def _pledges_tab(app, nb, who):
    ag = _rules("giving")
    t = tab(nb, "Pledges")
    top = ttk.Frame(t)
    top.pack(side="top", fill="x")
    ttk.Label(top, text="Due by").pack(side="left")
    due = tk.StringVar()
    ttk.Entry(top, textvariable=due, width=12).pack(side="left", padx=4)
    overdue = tk.BooleanVar()
    ttk.Checkbutton(top, text="Overdue only", variable=overdue).pack(side="left", padx=6)
    b = bar(t)
    tree = common.make_tree(t, _pledge_columns())

    def refresh():
        if overdue.get():
            rows = common.call(app.root, ag.overdue_pledges) or []
        else:
            rows = common.call(app.root, ag.pledges, who, due_by=due.get().strip() or None) or []
        common.fill(tree, rows, lambda r: r["pledge_id"], _pledge_values)

    def create():
        ans = common.ask(app.root, "New pledge", _pledge_fields(app, True),
                         {"frequency": "monthly", "instalments": "12"})
        if ans:
            write(app, ag.create_pledge, who, ans["alumni_id"], ans["amount"], ans["frequency"],
                  int(ans["instalments"] or 1), start=ans["start"] or None,
                  campaign_id=ans["campaign_id"] or None, then=refresh)

    def pay():
        rid = need(app, tree, "a pledge")
        if rid is None:
            return
        ans = common.ask(app.root, "Record pledge payment", [
            Field("method", "Payment method", "combo", list(ag.METHODS)),
            Field("paid_on", "Paid on", "date"),
            Field("gift_aid", "Claim Gift Aid", "check")], {"method": "direct_debit"})
        if ans:
            result = write(app, ag.record_pledge_payment, who, int(rid),
                           method=ans["method"] or "direct_debit",
                           paid_on=ans["paid_on"] or None, gift_aid=ans["gift_aid"],
                           then=refresh)
            if result:
                ag.post_to_finance(result, who.username)
                common.info(app.root, f"Recorded {result['receipt_number']}. "
                            + ("The pledge is complete." if result["pledge_completed"] else
                               f"Next due {result['next_due']}."))

    def cancel():
        rid = need(app, tree, "a pledge")
        if rid:
            reason = common.ask_text(app.root, "Cancel pledge", "Reason")
            if reason:
                write(app, ag.cancel_pledge, who, int(rid), reason, then=refresh)

    for text, cmd in (("New pledge…", create), ("Record payment…", pay), ("Cancel…", cancel),
                      ("Refresh", refresh)):
        button(b, text, cmd)
    ttk.Button(top, text="Show", command=refresh).pack(side="left", padx=4)
    refresh()


def _campaign_fields():
    return [Field("campaign_name", "Name", required=True), Field("description", "Description",
                                                                 "multiline"),
            Field("goal_amount", "Goal (£)", "number"), Field("start_date", "Starts", "date"),
            Field("end_date", "Ends", "date"), Field("category", "Category")]


def _campaigns_tab(app, nb, who):
    ag = _rules("giving")
    t = tab(nb, "Campaigns")
    b = bar(t)
    tree = common.make_tree(t, [("name", "Campaign", 220), ("goal", "Goal", 100),
                                ("raised", "Raised", 100), ("pct", "Progress", 80),
                                ("dates", "Dates", 190), ("status", "Status", 80)])
    rows_by_id = {}

    def refresh():
        rows = common.call(app.root, ag.campaigns) or []
        rows_by_id.clear()
        rows_by_id.update({str(r["campaign_id"]): r for r in rows})
        common.fill(tree, rows, lambda r: r["campaign_id"],
                    lambda r: (r["campaign_name"], money(r.get("goal_amount")),
                               money(r["raised"]), f"{r['progress_pct']}%"
                               if r["progress_pct"] is not None else "—",
                               f"{r.get('start_date') or ''} – {r.get('end_date') or ''}",
                               r.get("status") or "active"))

    def new():
        ans = common.ask(app.root, "New campaign", _campaign_fields())
        if ans:
            write(app, ag.save_campaign, who, ans, then=refresh)

    def edit():
        rid = need(app, tree, "a campaign")
        if rid:
            ans = common.ask(app.root, "Edit campaign", _campaign_fields(), rows_by_id[rid])
            if ans:
                write(app, ag.save_campaign, who, ans, int(rid), then=refresh)

    def close():
        rid = need(app, tree, "a campaign")
        if rid and common.confirm(app.root, "Close this campaign?"):
            write(app, ag.close_campaign, who, int(rid), then=refresh)

    for text, cmd in (("New…", new), ("Edit…", edit), ("Close", close), ("Refresh", refresh)):
        button(b, text, cmd)
    refresh()


def show_giving(app):
    who = who_of(app)
    frame = page(app, "Giving", "Gifts, Gift Aid, pledges and campaigns.")
    if who is None or not who.is_fundraiser:
        refuse(frame, "Giving is managed by fundraising staff and the alumni office.")
        return
    nb = notebook(frame)
    _gifts_tab(app, nb, who)
    _declarations_tab(app, nb, who)
    _claims_tab(app, nb, who)
    _pledges_tab(app, nb, who)
    _campaigns_tab(app, nb, who)


# ── my giving (alumnus) ─────────────────────────────────────────────────


def show_my_giving(app):
    ag = _rules("giving")
    who = who_of(app)
    frame = page(app, "My giving", "Your gifts, pledges and Gift Aid declaration.")
    if who is None or who.alumni_id is None:
        refuse(frame, "This is for alumni.")
        return
    summary = ttk.Label(frame, text="", font=("Arial", 11))
    summary.pack(anchor="w", pady=4)
    nb = notebook(frame)
    t_gifts = tab(nb, "My gifts")
    gifts_tree = common.make_tree(t_gifts, [("date", "Date", 100), ("amount", "Amount", 90),
                                            ("campaign", "Campaign", 200),
                                            ("aid", "Gift Aid", 80), ("receipt", "Receipt",
                                                                      140)])
    t_pl = tab(nb, "My pledges")
    b = bar(t_pl)
    pl_tree = common.make_tree(t_pl, _pledge_columns())
    t_decl = tab(nb, "Gift Aid")
    ttk.Label(t_decl, text="Gift Aid adds 25p to every £1 you give, at no cost to you, if you "
                           "pay enough UK tax.", wraplength=900).pack(side="top", anchor="w")
    aid = tk.StringVar(value=who.alumni_id)
    decl_refresh = _declarations_panel(app, t_decl, who, aid, online=True)

    def refresh():
        s = common.call(app.root, ag.donor_summary, who, who.alumni_id, quiet=True) or {}
        summary.configure(text=f"Given in total: {money(s.get('total'))} in {s.get('gifts', 0)} "
                               f"gift(s)" + (f" · {s['recognition']}" if s.get("recognition")
                                             else "")
                               + (" · Gift Aid declared" if s.get("gift_aid_declared") else ""))
        rows = common.call(app.root, ag.gifts, who) or []
        common.fill(gifts_tree, rows, lambda r: r["donation_id"],
                    lambda r: (r["donation_date"], money(r["amount"]), r.get("campaign_name"),
                               "yes" if r.get("is_gift_aided") else "no", r.get("receipt_number")))
        common.fill(pl_tree, common.call(app.root, ag.pledges, who) or [],
                    lambda r: r["pledge_id"], _pledge_values)
        decl_refresh()

    def new_pledge():
        ans = common.ask(app.root, "Make a pledge", _pledge_fields(app, False),
                         {"frequency": "monthly", "instalments": "12"})
        if ans:
            write(app, ag.create_pledge, who, who.alumni_id, ans["amount"], ans["frequency"],
                  int(ans["instalments"] or 1), start=ans["start"] or None,
                  campaign_id=ans["campaign_id"] or None, then=refresh)

    def cancel():
        rid = need(app, pl_tree, "a pledge")
        if rid:
            reason = common.ask_text(app.root, "Cancel pledge", "Reason")
            if reason:
                write(app, ag.cancel_pledge, who, int(rid), reason, then=refresh)

    button(b, "Make a pledge…", new_pledge)
    button(b, "Cancel pledge…", cancel)
    refresh()


# ── chapters ────────────────────────────────────────────────────────────


def _chapter_columns():
    return [("name", "Chapter", 220), ("location", "Location", 160), ("members", "Members", 80),
            ("contact", "Contact", 200)]


def _chapter_values(r):
    return (r["chapter_name"], r.get("location"), r.get("members"), r.get("contact_email"))


def _members_window(app, who, chapter_id, leader_tools=False, after=None):
    acm = _rules("community")
    rows = common.call(app.root, acm.members, who, int(chapter_id))
    if rows is None:
        return
    win = tk.Toplevel(app.root)
    win.title("Chapter members")
    win.geometry("640x420")
    b = bar(win)
    tree = common.make_tree(win, [("id", "Alumnus", 100), ("name", "Name", 200),
                                  ("role", "Role", 80), ("email", "E-mail (if shared)", 220)])

    def load():
        data = common.call(app.root, acm.members, who, int(chapter_id)) or []
        common.fill(tree, data, lambda r: r["alumni_id"],
                    lambda r: (r["alumni_id"], f"{r.get('first_name') or ''} "
                                               f"{r.get('last_name') or ''}".strip(),
                               r["role"], r.get("email") or ""))

    if leader_tools:
        def make_leader():
            aid = need(app, tree, "a member")
            if aid:
                write(app, acm.set_leader, who, int(chapter_id), aid, then=load)
                if after:
                    after()

        def remove():
            aid = need(app, tree, "a member")
            if aid and common.confirm(app.root, f"Remove {aid} from the chapter?"):
                write(app, acm.leave, who, int(chapter_id), aid, then=load)
                if after:
                    after()
        button(b, "Make leader", make_leader)
        button(b, "Remove member", remove)
    button(b, "Close", win.destroy)
    load()


def show_chapters(app):
    acm = _rules("community")
    who = who_of(app)
    frame = page(app, "Regional chapters")
    if who is None or not who.is_office:
        refuse(frame, "Chapters are managed by the alumni office. Alumni can join chapters "
                      "under My chapters.")
        return
    b = bar(frame)
    tree = common.make_tree(frame, _chapter_columns())
    rows_by_id = {}

    def refresh():
        rows = common.call(app.root, acm.chapters) or []
        rows_by_id.clear()
        rows_by_id.update({str(r["chapter_id"]): r for r in rows})
        common.fill(tree, rows, lambda r: r["chapter_id"], _chapter_values)

    fields = [Field("chapter_name", "Name", required=True), Field("location", "Location"),
              Field("contact_email", "Contact e-mail"), Field("description", "Description",
                                                              "multiline")]

    def new():
        ans = common.ask(app.root, "New chapter", fields)
        if ans:
            write(app, acm.save_chapter, who, ans, then=refresh)

    def edit():
        rid = need(app, tree, "a chapter")
        if rid:
            ans = common.ask(app.root, "Edit chapter", fields, rows_by_id[rid])
            if ans:
                write(app, acm.save_chapter, who, ans, int(rid), then=refresh)

    def close():
        rid = need(app, tree, "a chapter")
        if rid and common.confirm(app.root, "Close this chapter?"):
            write(app, acm.close_chapter, who, int(rid), then=refresh)

    def members():
        rid = need(app, tree, "a chapter")
        if rid:
            _members_window(app, who, rid, leader_tools=True, after=refresh)

    for text, cmd in (("New…", new), ("Edit…", edit), ("Close", close),
                      ("Members / leader…", members), ("Refresh", refresh)):
        button(b, text, cmd)
    refresh()


def show_my_chapters(app):
    acm = _rules("community")
    who = who_of(app)
    frame = page(app, "My chapters", "Join a regional chapter to meet alumni near you.")
    if who is None or who.alumni_id is None:
        refuse(frame, "Chapters are for alumni.")
        return
    nb = notebook(frame)
    t_all = tab(nb, "All chapters")
    b_all = bar(t_all)
    all_tree = common.make_tree(t_all, _chapter_columns())
    t_mine = tab(nb, "My chapters")
    b_mine = bar(t_mine)
    mine_tree = common.make_tree(t_mine, _chapter_columns()[:2] + [("role", "My role", 90)])
    roles = {}

    def refresh():
        common.fill(all_tree, common.call(app.root, acm.chapters) or [],
                    lambda r: r["chapter_id"], _chapter_values)
        mine = common.call(app.root, acm.my_chapters, who) or []
        roles.clear()
        roles.update({str(r["chapter_id"]): r["role"] for r in mine})
        common.fill(mine_tree, mine, lambda r: r["chapter_id"],
                    lambda r: (r["chapter_name"], r.get("location"), r["role"]))

    def join():
        rid = need(app, all_tree, "a chapter")
        if rid:
            write(app, acm.join, who, int(rid), then=refresh)

    def leave():
        rid = need(app, mine_tree, "a chapter")
        if rid and common.confirm(app.root, "Leave this chapter?"):
            write(app, acm.leave, who, int(rid), then=refresh)

    def members():
        rid = need(app, mine_tree, "a chapter")
        if rid:
            if roles.get(rid) != "leader":
                common.info(app.root, "Only the chapter leader can see the member list.")
                return
            _members_window(app, who, rid)

    button(b_all, "Join", join)
    button(b_all, "Refresh", refresh)
    button(b_mine, "Leave", leave)
    button(b_mine, "Members (leaders)…", members)
    refresh()


# Mentoring, moderation, forum and stories live in the sibling module; they
# are looked up on first use so the two modules can import each other.
_SIBLING = ("show_forum", "show_mentoring", "show_moderation", "show_my_mentoring",
            "show_stories")


def __getattr__(name):
    if name in _SIBLING:
        from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
            alumni_office_mentoring,
        )
        return getattr(alumni_office_mentoring, name)
    raise AttributeError(name)


__all__ = ["show_giving", "show_my_giving", "show_chapters", "show_my_chapters",
           "show_mentoring", "show_my_mentoring", "show_moderation", "show_forum",
           "show_stories", "who_of"]
