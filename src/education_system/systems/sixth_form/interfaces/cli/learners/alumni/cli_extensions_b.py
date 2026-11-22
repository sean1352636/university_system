"""Alumni CLI: extension items 17-50, plus the ops/reports sub-menus.

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

from ._helpers import (
    Any,
    BEQUEST_STATUSES,
    CUSTOM_FIELD_TYPES,
    Callable,
    DONOR_STAGES,
    DRIP_STATUSES,
    MEDIA_KINDS,
    NEET_STATUSES,
    PROTECTED_CHARS,
    RECURRING_FREQS,
    RECURRING_STATUSES,
    TRACK_KINDS,
    ValidationError,
    WEBHOOK_EVENT_TYPES,
    _UserAbort,
    logger,
)
from education_system.systems.sixth_form.domain.learners.alumni import (
    compliance as alumni_compliance,
    db as alumni_db,
    events as alumni_events,
    fundraising as alumni_fundraising,
    integrations as alumni_integrations,
    mentoring as alumni_mentoring,
    messaging as alumni_messaging,
    models as alumni_models,
    outcomes as alumni_outcomes,
    surveys as alumni_surveys,
)
from ._helpers import (  # noqa: F401
    _input,
    _pause,
    _pick_alumnus,
    _pick_from,
    _yes_no,
)
from .cli_programmes import (  # noqa: F401
    _money_str,
    audit_log_flow,
    dedupe_flow,
    export_csv_flow,
    import_csv_flow,
    merge_flow,
    report_apprenticeship_outcomes,
    report_cohort_comparison,
    report_disadvantage_gap,
    report_geographic,
    report_ks5_csv,
    report_sector_breakdown,
    report_sustained,
    report_university_success,
    report_where_are_they_now,
    saved_searches_flow,
    surveys_flow,
    trash_flow,
)
from .cli_extensions_a import (  # noqa: F401
    _connect_alumni_lookup,
    lost_contact_flow,
    milestones_flow,
    re_engagement_flow,
    salary_band_report_flow,
    soc_flow,
)


# ── Mentor + comms extensions (items 17–26) ───────────────────────

def mentor_profile_flow() -> None:
    print("\n═══ Mentor profile (capacity & availability) ═══")
    a = _pick_alumnus()
    p = alumni_mentoring.get_mentor_profile(a.alumni_id)
    if p:
        print(f"  current: max={p.max_mentees}  "
              f"from={p.available_from or '—'}  "
              f"until={p.available_until or '—'}  "
              f"paused={p.paused}")
    try:
        mx = int(_input("max_mentees", default=str(p.max_mentees if p else 3)))
        af = _input("available_from (YYYY-MM-DD, blank=keep)") or \
            (p.available_from if p else None)
        au = _input("available_until (YYYY-MM-DD, blank=keep)") or \
            (p.available_until if p else None)
        paused = _yes_no("paused?", default=bool(p.paused) if p else False)
        bio = _input("bio (blank=keep)") or (p.bio if p else None)
    except _UserAbort:
        return
    try:
        out = alumni_mentoring.upsert_mentor_profile(a.alumni_id, max_mentees=mx,
            available_from=af, available_until=au, paused=paused, bio=bio)
        print(f"  ✓ saved. capacity now: "
              f"{'yes' if alumni_mentoring.mentor_has_capacity(out.alumni_id) else 'no'}")
        print(f"  active mentees: {alumni_mentoring.active_mentee_count(out.alumni_id)}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def mentor_rate_flow() -> None:
    print("\n═══ Rate a mentor session ═══")
    try:
        sid = int(_input("session id", allow_empty=False))
        mr_raw = _input("mentee rating 1-5 (blank=skip)")
        gr_raw = _input("mentor rating 1-5 (blank=skip)")
        mf = _input("mentor feedback (blank=skip)") or None
        bf = _input("mentee feedback (blank=skip)") or None
    except (_UserAbort, ValueError):
        return
    try:
        alumni_mentoring.rate_mentor_session(sid,
            mentee_rating=int(mr_raw) if mr_raw else None,
            mentor_rating=int(gr_raw) if gr_raw else None,
            mentor_feedback=mf, mentee_feedback=bf)
        print("  ✓ rated")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def mentor_safeguarding_flow() -> None:
    print("\n═══ Mentor safeguarding ═══")
    print("  1) Set / update record  2) View alerts  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            ref = _input("DBS reference") or None
            iss = _input("DBS issued (YYYY-MM-DD)") or None
            exp = _input("DBS expires (YYYY-MM-DD)") or None
            tdone = _input("Training done (YYYY-MM-DD)") or None
            texp = _input("Training expires (YYYY-MM-DD)") or None
            sg = alumni_mentoring.upsert_mentor_safeguarding(a.alumni_id,
                dbs_reference=ref, dbs_issued_on=iss,
                dbs_expires_on=exp, training_done_on=tdone,
                training_expires_on=texp)
            print(f"  ✓ status={sg.status}")
        else:
            days = int(_input("Within how many days", default="60") or "60")
            for s in alumni_mentoring.list_safeguarding_alerts(days=days):
                print(f"   #{s.alumni_id:<5}  {s.status:<14} "
                      f"DBS:{s.dbs_expires_on or '—'}  "
                      f"Training:{s.training_expires_on or '—'}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def templates_flow() -> None:
    print("\n═══ Email templates ═══")
    while True:
        print("\n  1) List  2) New  3) View  4) Render preview  5) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for t in alumni_messaging.list_email_templates():
                    print(f"   #{t.template_id:<4} {t.name:<24} v{t.version}  "
                          f"{t.category or '—':<14}  {t.subject[:40]}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                cat = _input("Category (optional)") or None
                subj = _input("Subject (use {first_name})", allow_empty=False)
                print("  Body (end with a single '.' on a line):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == ".":
                        break
                    lines.append(line)
                body = "\n".join(lines)
                t = alumni_messaging.create_email_template(name, subj, body, category=cat)
                print(f"  ✓ created #{t.template_id} v{t.version}")
            elif ch == "3":
                tid = int(_input("Template id", allow_empty=False))
                for t in alumni_messaging.list_email_templates(latest_only=False):
                    if t.template_id == tid:
                        print(f"  {t.name} v{t.version}")
                        print(f"  Subject: {t.subject}")
                        print("  Body:")
                        print(t.body)
                        break
            elif ch == "4":
                name = _input("Template name", allow_empty=False)
                a = _pick_alumnus()
                t = alumni_messaging.get_email_template(name)
                if not t:
                    print("  not found")
                else:
                    s, b = alumni_messaging.render_template(t, a.alumni_id)
                    print(f"  Subject: {s}")
                    print(f"  Body:\n{b}")
            elif ch == "5":
                tid = int(_input("Template id to delete", allow_empty=False))
                if _yes_no(f"Delete template #{tid}?", default=False):
                    alumni_messaging.delete_email_template(tid)
                    print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def drip_flow() -> None:
    print("\n═══ Drip campaigns ═══")
    while True:
        print("\n  1) List  2) Create  3) Add step  4) Status  5) Enroll  "
              "6) Tick now  7) Unsubscribe  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for d in alumni_messaging.list_drip_campaigns():
                    print(f"   #{d.drip_id:<4} {d.name:<24}  [{d.status}]  "
                          f"{d.description or ''}")
                    for s in alumni_messaging.list_drip_steps(d.drip_id):
                        print(f"      step {s.position}  +{s.delay_days}d  "
                              f"{('template #' + str(s.template_id)) if s.template_id else (s.subject or '?')}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                desc = _input("Description (optional)") or None
                d = alumni_messaging.create_drip_campaign(name, description=desc)
                print(f"  ✓ #{d.drip_id}")
            elif ch == "3":
                did = int(_input("Drip id", allow_empty=False))
                pos = int(_input("Position", allow_empty=False))
                delay = int(_input("Delay days", default="0") or "0")
                use_t = _yes_no("Use template?", default=False)
                tid = subj = body = None
                if use_t:
                    tid = int(_input("Template id", allow_empty=False))
                else:
                    subj = _input("Subject", allow_empty=False)
                    body = _input("Body", allow_empty=False)
                alumni_messaging.add_drip_step(did, position=pos, delay_days=delay,
                    template_id=tid, subject=subj, body=body)
                print("  ✓")
            elif ch == "4":
                did = int(_input("Drip id", allow_empty=False))
                st = _pick_from("Status", list(DRIP_STATUSES))
                alumni_messaging.set_drip_status(did, st)
                print("  ✓")
            elif ch == "5":
                did = int(_input("Drip id", allow_empty=False))
                a = _pick_alumnus()
                alumni_messaging.enroll_in_drip(did, a.alumni_id)
                print("  ✓")
            elif ch == "6":
                ticks = alumni_messaging.tick_drip()
                for t in ticks:
                    print(f"   sent step #{t.step_id} → alumnus #{t.alumni_id} "
                          f"({t.subject})")
                print(f"  → {len(ticks)} tick(s)")
            elif ch == "7":
                did = int(_input("Drip id", allow_empty=False))
                a = _pick_alumnus()
                alumni_messaging.unsubscribe_from_drip(did, a.alumni_id)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def ab_flow() -> None:
    print("\n═══ A/B tests ═══")
    while True:
        print("\n  1) List  2) Create  3) Add variant  4) Assign  "
              "5) Record event  6) Results  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                with _connect_alumni_lookup() as _:
                    pass  # warm cache (not used here, just structural)
                # Simple direct query: reuse list_ab_variants per test
                # Lacking a list_ab_tests helper — query via direct sql:
                import sqlite3
                with sqlite3.connect(str(alumni_db.DB_PATH)) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT * FROM alumni_ab_tests "
                        "ORDER BY created_at DESC").fetchall()
                for r in rows:
                    print(f"   #{r['test_id']:<4} {r['name']:<24} "
                          f"sent_at={r['sent_at'] or '—'}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                desc = _input("Description") or None
                t = alumni_messaging.create_ab_test(name, description=desc)
                print(f"  ✓ #{t.test_id}")
            elif ch == "3":
                tid = int(_input("Test id", allow_empty=False))
                lbl = _input("Variant label (e.g. A)", allow_empty=False)
                subj = _input("Subject", allow_empty=False)
                body = _input("Body", allow_empty=False)
                alumni_messaging.add_ab_variant(tid, label=lbl, subject=subj, body=body)
                print("  ✓")
            elif ch == "4":
                tid = int(_input("Test id", allow_empty=False))
                year = _input("Leaving year filter (blank=all)") or None
                filters = {"year": year} if year else {}
                # list_alumni filter param is 'leaving_year' not 'year';
                # accept either form for convenience:
                if "year" in filters:
                    filters["leaving_year"] = filters.pop("year")
                counts = alumni_messaging.assign_ab_audience(tid, filters=filters)
                print(f"  counts: {counts}")
            elif ch == "5":
                tid = int(_input("Test id", allow_empty=False))
                a = _pick_alumnus()
                kind = _pick_from("Kind", ["send", "open", "click"])
                alumni_messaging.record_ab_event(tid, a.alumni_id, kind)
                print("  ✓")
            elif ch == "6":
                tid = int(_input("Test id", allow_empty=False))
                for r in alumni_messaging.ab_test_results(tid):
                    print(f"   {r.label:<6}  sent={r.sent:<4} "
                          f"opens={r.opens} ({r.open_rate}%)  "
                          f"clicks={r.clicks} ({r.click_rate}%)")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def sms_flow() -> None:
    print("\n═══ SMS ═══")
    print("  1) Send to one  2) View history  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        a = _pick_alumnus()
        if ch == "1":
            body = _input("Body", allow_empty=False)
            sms = alumni_messaging.send_sms_to_alumnus(a.alumni_id, body)
            print(f"  ✓ {sms.status}")
        else:
            for s in alumni_messaging.list_sms_for(a.alumni_id):
                print(f"   #{s.sms_id:<5} {s.sent_at}  [{s.status}]  "
                      f"{s.body[:60]}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def postal_flow() -> None:
    print("\n═══ Postal mail merge ═══")
    print("  1) Generate one  2) Bulk (filters)  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        out_dir = _input("Output directory", allow_empty=False)
        subj = _input("Subject (use {first_name})", allow_empty=False)
        print("  Body (end with '.' on a line):")
        lines: list[str] = []
        while True:
            line = input()
            if line.strip() == ".":
                break
            lines.append(line)
        body = "\n".join(lines)
        if ch == "1":
            a = _pick_alumnus()
            L = alumni_messaging.generate_postal_letter(a.alumni_id,
                subject=subj, body=body, out_dir=out_dir)
            print(f"  ✓ {L.pdf_path}")
        else:
            year = _input("Leaving year (blank=all)") or None
            filters: dict[str, Any] = {}
            if year:
                filters["leaving_year"] = year
            letters = alumni_messaging.generate_postal_bulk(filters, subject=subj,
                body=body, out_dir=out_dir)
            print(f"  ✓ {len(letters)} letters")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def newsletter_flow() -> None:
    print("\n═══ Newsletters ═══")
    while True:
        print("\n  1) List  2) Create  3) Add section  4) Publish  "
              "5) Audience  6) HTML preview  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for n in alumni_messaging.list_newsletters():
                    print(f"   #{n.newsletter_id:<4} {n.issue:<16} "
                          f"{n.title[:36]:<36} [{n.status}]  "
                          f"{n.published_at or '—'}")
            elif ch == "2":
                issue = _input("Issue (e.g. 2025-Spring)",
                                  allow_empty=False)
                title = _input("Title", allow_empty=False)
                n = alumni_messaging.create_newsletter(issue, title)
                print(f"  ✓ #{n.newsletter_id}")
            elif ch == "3":
                nid = int(_input("Newsletter id", allow_empty=False))
                heading = _input("Heading", allow_empty=False)
                body = _input("Body", allow_empty=False)
                alumni_messaging.add_newsletter_section(nid, heading=heading, body=body)
                print("  ✓")
            elif ch == "4":
                nid = int(_input("Newsletter id", allow_empty=False))
                year = _input("Leaving year filter (blank=all)") or None
                filters = {"leaving_year": year} if year else None
                alumni_messaging.publish_newsletter(nid, distribution_filters=filters)
                print("  ✓ Published")
            elif ch == "5":
                nid = int(_input("Newsletter id", allow_empty=False))
                rows = alumni_messaging.newsletter_audience(nid)
                print(f"  audience size: {len(rows)}")
                for a in rows[:20]:
                    print(f"   #{a.alumni_id:<5} {a.full_name}")
                if len(rows) > 20:
                    print(f"   ... +{len(rows) - 20} more")
            elif ch == "6":
                nid = int(_input("Newsletter id", allow_empty=False))
                print(alumni_messaging.render_newsletter_html(nid))
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def tracking_flow() -> None:
    print("\n═══ Open/click tracking ═══")
    while True:
        print("\n  1) Mint pixel  2) Mint link  3) Record event  "
              "4) Resolve token  5) Summary  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                ref = _input("Campaign ref (optional)") or None
                tok = alumni_messaging.create_tracking_pixel(a.alumni_id,
                                                      campaign_ref=ref)
                print(f"  token: {tok}")
            elif ch == "2":
                a = _pick_alumnus()
                url = _input("Target URL", allow_empty=False)
                ref = _input("Campaign ref (optional)") or None
                tok = alumni_messaging.create_tracked_link(url,
                    alumni_id=a.alumni_id, campaign_ref=ref)
                print(f"  token: {tok}")
            elif ch == "3":
                tok = _input("Token", allow_empty=False)
                kind = _pick_from("Kind", list(TRACK_KINDS))
                alumni_messaging.record_track_event(tok, kind)
                print("  ✓")
            elif ch == "4":
                tok = _input("Token", allow_empty=False)
                kind, url = alumni_messaging.resolve_tracked_link(tok)
                print(f"  kind={kind}  target={url or '—'}")
            elif ch == "5":
                ref = _input("Campaign ref (blank=all)") or None
                s = alumni_messaging.tracking_summary(campaign_ref=ref)
                print(f"  sends={s.sends}  opens={s.opens}  "
                      f"clicks={s.clicks}  unique_opens={s.unique_opens}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


# ── Events / fundraising / outcomes (items 27–40) ─────────────────

def ticketing_flow() -> None:
    print("\n═══ Event ticketing ═══")
    while True:
        print("\n  1) Buy ticket  2) Refund  3) Promote waitlist  "
              "4) Finance summary  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            eid = int(_input("Event id", allow_empty=False))
            if ch == "1":
                a = _pick_alumnus()
                guests = int(_input("Guests", default="0") or "0")
                amt = _input("Amount paid pence (blank=auto)") or None
                t = alumni_events.buy_ticket(eid, a.alumni_id, guests=guests,
                    amount_paid_pence=int(amt) if amt else None)
                print(f"  ✓ rsvp #{t.rsvp_id}  "
                      f"waitlist={t.waitlisted}  paid={t.amount_paid_pence}p")
            elif ch == "2":
                a = _pick_alumnus()
                amt = _input("Amount pence (blank=full)") or None
                reason = _input("Reason (optional)") or None
                rf = alumni_events.refund_ticket(eid, a.alumni_id,
                    amount_pence=int(amt) if amt else None, reason=reason)
                print(f"  ✓ refunded {rf.amount_pence}p")
            elif ch == "3":
                promoted = alumni_events.promote_from_waitlist(eid)
                print(f"  ✓ promoted {len(promoted)}")
            elif ch == "4":
                f = alumni_events.event_finance(eid)
                print(f"  tickets={f.tickets_sold} seats={f.seats_used} "
                      f"waitlist={f.waitlist}  "
                      f"gross={_money_str(f.gross_pence)} "
                      f"refunds={_money_str(f.refunds_pence)} "
                      f"net={_money_str(f.net_pence)}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def checkin_flow() -> None:
    print("\n═══ Event check-in (QR) ═══")
    while True:
        print("\n  1) Issue tokens (event)  2) Scan token  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                eid = int(_input("Event id", allow_empty=False))
                n = alumni_events.issue_event_checkin_tokens(eid)
                print(f"  ✓ {n} token(s) minted")
            elif ch == "2":
                tok = _input("Token", allow_empty=False)
                res = alumni_events.check_in_by_token(tok)
                print(f"  ✓ rsvp #{res.rsvp_id} "
                      f"{'already' if res.already_checked_in else 'now'} "
                      f"in @ {res.checked_in_at}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def close_event_flow() -> None:
    print("\n═══ Close event with feedback survey ═══")
    try:
        eid = int(_input("Event id", allow_empty=False))
    except (ValueError, _UserAbort):
        return
    try:
        ev, survey = alumni_events.close_event_with_feedback(eid)
        print(f"  ✓ event closed, survey #{survey.survey_id} created, "
              f"{len(alumni_surveys.list_invitations(survey.survey_id))} invitations")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def reunion_planner_flow() -> None:
    print("\n═══ Reunion planner ═══")
    try:
        months = int(_input("Horizon months", default="18") or "18")
    except (ValueError, _UserAbort):
        return
    sugs = alumni_events.suggest_reunions(horizon_months=months)
    if not sugs:
        print("  (no suggestions)"); _pause(); return
    for s in sugs:
        print(f"   {s.proposed_date}  {s.proposed_name:<36} "
              f"({s.cohort_size} alumni)")
    if _yes_no("\n  Create draft events from these?", default=False):
        created = alumni_events.create_reunion_events(horizon_months=months)
        print(f"  ✓ created {len(created)} draft event(s)")
    _pause()


def gift_aid_flow() -> None:
    print("\n═══ Gift Aid declarations ═══")
    while True:
        print("\n  1) Add  2) Withdraw  3) Check active  "
              "4) Export R68 CSV  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                vfrom = _input("Valid from (YYYY-MM-DD)", allow_empty=False)
                vuntil = _input("Valid until (optional)") or None
                full = _input("Full name", allow_empty=False)
                addr = _input("Address", allow_empty=False)
                pc = _input("Postcode", allow_empty=False)
                alumni_fundraising.add_gift_aid_declaration(a.alumni_id,
                    valid_from=vfrom, valid_until=vuntil,
                    full_name=full, address=addr, postcode=pc)
                print("  ✓")
            elif ch == "2":
                did = int(_input("Declaration id", allow_empty=False))
                alumni_fundraising.withdraw_gift_aid_declaration(did)
                print("  ✓")
            elif ch == "3":
                a = _pick_alumnus()
                g = alumni_fundraising.get_active_gift_aid(a.alumni_id)
                print(f"  {'ACTIVE: ' + g.full_name if g else 'no active declaration'}")
            elif ch == "4":
                p = _input("Output CSV path", allow_empty=False)
                ys = _input("Year start (YYYY-MM-DD)", allow_empty=False)
                ye = _input("Year end   (YYYY-MM-DD)", allow_empty=False)
                n = alumni_fundraising.export_r68_csv(p, year_start=ys, year_end=ye)
                print(f"  ✓ wrote {n} rows to {p}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def recurring_flow() -> None:
    print("\n═══ Recurring donations ═══")
    while True:
        print("\n  1) List  2) Create  3) Status  4) Tick now  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for s in alumni_fundraising.list_recurring():
                    print(f"   #{s.schedule_id:<4} a#{s.alumni_id:<4} "
                          f"{_money_str(s.amount_pence)} {s.frequency} "
                          f"next={s.next_charge_on}  [{s.status}]  "
                          f"fails={s.failure_count}")
            elif ch == "2":
                a = _pick_alumnus()
                amt = int(_input("Amount pence", allow_empty=False))
                freq = _pick_from("Frequency", list(RECURRING_FREQS),
                                     default="Monthly")
                nxt = _input("First charge (YYYY-MM-DD, blank=today)") or None
                fund = _input("Fund code (optional)") or None
                pm = _input("Payment method (Direct Debit/Card/…)") or None
                sch = alumni_fundraising.create_recurring(a.alumni_id,
                    amount_pence=amt, frequency=freq,
                    next_charge_on=nxt, fund_code=fund,
                    payment_method=pm)
                print(f"  ✓ #{sch.schedule_id}")
            elif ch == "3":
                sid = int(_input("Schedule id", allow_empty=False))
                st = _pick_from("Status", list(RECURRING_STATUSES))
                alumni_fundraising.set_recurring_status(sid, st)
                print("  ✓")
            elif ch == "4":
                ticks = alumni_fundraising.tick_recurring()
                ok = sum(1 for t in ticks if t.success)
                print(f"  ✓ {ok}/{len(ticks)} succeeded")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def donor_pipeline_flow() -> None:
    print("\n═══ Donor pipeline ═══")
    while True:
        print("\n  1) Set stage  2) View per alumnus  "
              "3) List by stage  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                stage = _pick_from("Stage", list(DONOR_STAGES))
                owner = _input("Owner staff id (optional)") or None
                action = _input("Next action (optional)") or None
                when = _input("Next action on (YYYY-MM-DD)") or None
                cap_raw = _input("Capacity pence (optional)")
                cap = int(cap_raw) if cap_raw else None
                alumni_fundraising.set_donor_stage(a.alumni_id, stage,
                    owner_staff_id=owner, next_action=action,
                    next_action_on=when, capacity_pence=cap)
                print("  ✓")
            elif ch == "2":
                a = _pick_alumnus()
                p = alumni_fundraising.get_donor_pipeline(a.alumni_id)
                print(f"  {p}" if p else "  (no record)")
            elif ch == "3":
                stage = _pick_from("Stage", list(DONOR_STAGES))
                for p in alumni_fundraising.list_donor_pipeline(stage=stage):
                    print(f"   a#{p.alumni_id:<5} owner={p.owner_staff_id or '—'}  "
                          f"next={p.next_action or '—'} on {p.next_action_on or '—'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def funds_flow() -> None:
    print("\n═══ Funds ═══")
    while True:
        print("\n  1) List  2) Upsert  3) Tag donation  4) Totals  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for f in alumni_fundraising.list_funds():
                    r = "R" if f.restricted else "U"
                    print(f"   #{f.fund_id:<3} {f.code:<10} [{r}] {f.name}")
            elif ch == "2":
                code = _input("Code", allow_empty=False)
                name = _input("Name", allow_empty=False)
                restr = _yes_no("Restricted?", default=False)
                alumni_fundraising.upsert_fund(code, name, restricted=restr)
                print("  ✓")
            elif ch == "3":
                did = int(_input("Donation id", allow_empty=False))
                code = _input("Fund code", allow_empty=False)
                alumni_fundraising.tag_donation_fund(did, code)
                print("  ✓")
            elif ch == "4":
                for t in alumni_fundraising.fund_totals():
                    r = "R" if t.restricted else "U"
                    print(f"   {t.fund_code:<14} [{r}] "
                          f"{_money_str(t.raised_pence):>12} "
                          f"({t.fund_name})")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def bequests_flow() -> None:
    print("\n═══ Bequests / legacies ═══")
    while True:
        print("\n  1) List  2) Add  3) Set status  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                status = _input("Status filter (blank=all)") or None
                for b in alumni_fundraising.list_bequests(status=status):
                    print(f"   #{b.bequest_id:<3} a#{b.alumni_id:<4} "
                          f"{_money_str(b.estimated_pence):>12} "
                          f"[{b.status}] confirmed={b.confirmed_on or '—'}")
            elif ch == "2":
                a = _pick_alumnus()
                est_raw = _input("Estimated pence (optional)")
                est = int(est_raw) if est_raw else None
                exec_name = _input("Executor name (optional)") or None
                exec_email = _input("Executor email (optional)") or None
                conf = _input("Confirmed on (YYYY-MM-DD, optional)") or None
                alumni_fundraising.add_bequest(a.alumni_id, estimated_pence=est,
                    executor_name=exec_name, executor_email=exec_email,
                    confirmed_on=conf)
                print("  ✓")
            elif ch == "3":
                bid = int(_input("Bequest id", allow_empty=False))
                st = _pick_from("Status", list(BEQUEST_STATUSES))
                rdate = _input("Realised on (YYYY-MM-DD, optional)") or None
                alumni_fundraising.set_bequest_status(bid, st, realised_on=rdate)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def matched_giving_flow() -> None:
    print("\n═══ Matched giving ═══")
    while True:
        print("\n  1) List schemes  2) Upsert scheme  "
              "3) Apply to donation  4) Find for employer  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for s in alumni_fundraising.list_matched_schemes():
                    cap = _money_str(s.cap_pence) if s.cap_pence else "—"
                    print(f"   #{s.scheme_id:<3} {s.employer:<22} "
                          f"×{s.multiplier} cap={cap}")
            elif ch == "2":
                emp = _input("Employer", allow_empty=False)
                mult = float(_input("Multiplier", default="1.0") or "1.0")
                cap_raw = _input("Cap pence (optional)")
                cap = int(cap_raw) if cap_raw else None
                alumni_fundraising.upsert_matched_scheme(emp, multiplier=mult,
                                              cap_pence=cap)
                print("  ✓")
            elif ch == "3":
                did = int(_input("Donation id", allow_empty=False))
                matched = alumni_fundraising.auto_apply_matched_giving(did)
                print(f"  ✓ matched {matched}p")
            elif ch == "4":
                emp = _input("Employer", allow_empty=False)
                s = alumni_fundraising.find_matched_scheme(emp)
                print(f"  {s if s else '(no scheme)'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def neet_flow() -> None:
    print("\n═══ NEET tracking ═══")
    while True:
        print("\n  1) Record check  2) View alumnus  "
              "3) Breakdown  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                m = int(_input("Months after (3/6/12/24)",
                                  allow_empty=False))
                st = _pick_from("Status", list(NEET_STATUSES))
                alumni_outcomes.record_neet_check(a.alumni_id, months_after=m,
                                          status=st)
                print("  ✓")
            elif ch == "2":
                a = _pick_alumnus()
                for c in alumni_outcomes.list_neet_checks(a.alumni_id):
                    print(f"   {c.months_after}m: {c.status}  ({c.checked_on})")
            elif ch == "3":
                year = _input("Leaving year (blank=all)") or None
                for r in alumni_outcomes.neet_breakdown(leaving_year=year):
                    print(f"   {r.months_after:>2}m  cohort={r.cohort}  "
                          f"neet={r.neet}  not_neet={r.not_neet}  "
                          f"unk={r.unknown}  rate={r.neet_rate_pct}%")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def russell_oxbridge_flow() -> None:
    print("\n═══ Russell Group / Oxbridge breakout ═══")
    year = _input("Leaving year (blank=all)") or None
    r = alumni_outcomes.russell_group_breakdown(leaving_year=year)
    print(f"  cohort={r.cohort}  RG={r.russell_group} ({r.russell_rate_pct}%)  "
          f"Oxbridge={r.oxbridge} ({r.oxbridge_rate_pct}%)")
    _pause()


def pg_progression_flow() -> None:
    print("\n═══ Postgraduate progression ═══")
    year = _input("Leaving year (blank=all)") or None
    r = alumni_outcomes.postgraduate_rate(leaving_year=year)
    print(f"  cohort={r.cohort}  PG={r.pg_count} ({r.pg_rate_pct}%)")
    for p in alumni_outcomes.postgraduate_progression(leaving_year=year):
        print(f"   a#{p.alumni_id:<5} {p.full_name:<24} "
              f"{', '.join(p.pg_qualifications)} @ "
              f"{', '.join(p.pg_institutions)}")
    _pause()


def first_gen_flow() -> None:
    print("\n═══ First-generation HE outcomes ═══")
    while True:
        print("\n  1) Flag alumnus  2) Outcome report  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                val = _yes_no("First-generation HE?", default=True)
                alumni_outcomes.set_first_gen_he(a.alumni_id, val)
                print("  ✓")
            elif ch == "2":
                year = _input("Leaving year (blank=all)") or None
                for r in alumni_outcomes.first_gen_outcomes(leaving_year=year):
                    print(f"   {r.bucket:<16} cohort={r.cohort}  "
                          f"in_HE={r.in_he} ({r.he_rate_pct}%)  "
                          f"RG={r.russell_group} ({r.russell_rate_pct}%)")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


# ── Final cluster (items 41–50) ───────────────────────────────────

def protected_chars_flow() -> None:
    print("\n═══ Protected characteristics ═══")
    print("  1) Set flag  2) Set ethnicity  3) Gap report  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            char = _pick_from("Characteristic", list(PROTECTED_CHARS))
            val = _yes_no("Set true?", default=False)
            alumni_compliance.set_protected_characteristic(a.alumni_id, char, val)
            print("  ✓")
        elif ch == "2":
            a = _pick_alumnus()
            val = _input("Ethnicity (blank=clear)") or None
            alumni_compliance.set_ethnicity(a.alumni_id, val)
            print("  ✓")
        elif ch == "3":
            year = _input("Leaving year (blank=all)") or None
            for r in alumni_compliance.protected_characteristic_gaps(leaving_year=year):
                rate = ("(suppressed)" if r.suppressed
                          else f"{r.he_rate_pct}%")
                print(f"   {r.characteristic:<14} {r.bucket:<8} "
                      f"cohort={r.cohort:<4} HE={rate}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def hesa_flow() -> None:
    print("\n═══ HESA benchmarks ═══")
    print("  1) List  2) Upsert  3) Compare cohort  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    if ch == "0":
        return
    try:
        if ch == "1":
            for b in alumni_outcomes.list_hesa_benchmarks():
                print(f"   {b.leaving_year}  {b.metric:<18} "
                      f"{b.rate_pct:>5.1f}%  ({b.source or '—'})")
        elif ch == "2":
            year = _input("Leaving year", allow_empty=False)
            metric = _pick_from("Metric",
                ["he_entry", "russell_group", "oxbridge",
                 "postgraduate"])
            rate = float(_input("Rate %", allow_empty=False))
            src = _input("Source (optional)") or None
            alumni_outcomes.upsert_hesa_benchmark(year, metric, rate, source=src)
            print("  ✓")
        elif ch == "3":
            year = _input("Leaving year", allow_empty=False)
            for d in alumni_outcomes.compare_with_hesa(year):
                sign = "+" if d.delta_pct >= 0 else ""
                print(f"   {d.metric:<18}  school={d.school_rate_pct}%  "
                      f"HESA={d.hesa_rate_pct}%  "
                      f"Δ={sign}{d.delta_pct}%")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def dfe_export_flow() -> None:
    print("\n═══ DfE 16-18 destinations export ═══")
    try:
        year = _input("Leaving year", allow_empty=False)
        path = _input("Output CSV path", allow_empty=False)
    except _UserAbort:
        return
    try:
        n = alumni_outcomes.export_dfe_destinations_csv(path, leaving_year=year)
        print(f"  ✓ wrote {n} rows to {path}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def sar_flow() -> None:
    print("\n═══ SAR bundle ═══")
    try:
        a = _pick_alumnus()
        out_dir = _input("Output directory", allow_empty=False)
    except _UserAbort:
        return
    try:
        path = alumni_compliance.generate_sar_bundle(a.alumni_id, out_dir)
        print(f"  ✓ {path}")
    except (ValidationError, ValueError) as e:
        print(f"  ✗ {e}")
    _pause()


def erasure_flow() -> None:
    print("\n═══ Right-to-erasure workflow ═══")
    while True:
        print("\n  1) Request  2) Review  3) Complete  4) List  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                by = _input("Requested by (staff id)") or None
                reason = _input("Reason (optional)") or None
                req = alumni_compliance.request_erasure(a.alumni_id,
                    requested_by=by, reason=reason)
                print(f"  ✓ request #{req.request_id}")
            elif ch == "2":
                rid = int(_input("Request id", allow_empty=False))
                reviewer = _input("Reviewer", allow_empty=False)
                decision = _pick_from("Decision",
                    ["Approved", "Rejected"])
                notes = _input("Notes (optional)") or None
                alumni_compliance.review_erasure(rid, reviewer=reviewer,
                    decision=decision, review_notes=notes)
                print("  ✓")
            elif ch == "3":
                rid = int(_input("Request id", allow_empty=False))
                if _yes_no("Anonymise now?", default=False):
                    alumni_compliance.complete_erasure(rid)
                    print("  ✓ anonymised")
            elif ch == "4":
                status = _input(
                    "Status filter (blank=all)") or None
                for r in alumni_compliance.list_erasure_requests(status=status):
                    print(f"   #{r.request_id:<3} a#{r.alumni_id:<4} "
                          f"[{r.status}] requested={r.requested_at}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def quality_flow() -> None:
    print("\n═══ Data quality dashboard ═══")
    q = alumni_compliance.data_quality_report()
    print(f"  total={q.total}")
    print(f"  email%={q.with_email_pct}  phone%={q.with_phone_pct}  "
          f"address%={q.with_address_pct}")
    print(f"  missing destination%={q.missing_destination_pct}")
    print(f"  stale (24mo)%={q.stale_24mo_pct}  "
          f"bounce%={q.bounce_rate_pct}")
    print(f"  opt-in%={q.opt_in_pct}  "
          f"data-storage consent%={q.consent_data_storage_pct}")
    _pause()


def dedupe_buckets_flow() -> None:
    print("\n═══ Dedupe — confidence buckets ═══")
    b = alumni_compliance.dedupe_buckets()
    def show(label: str, rows) -> None:
        if not rows: return
        print(f"\n  {label} ({len(rows)}):")
        for c in rows:
            print(f"   {c.score:.2f}  keep #{c.keep_id} ⇐ #{c.merge_id}")
    show("Very high (≥0.95)", b.very_high)
    show("High (0.85–0.95)", b.high)
    show("Medium (0.70–0.85)", b.medium)
    if _yes_no("\nBatch-merge all very-high pairs?", default=False):
        pairs = [(c.keep_id, c.merge_id) for c in b.very_high]
        ok, errs = alumni_compliance.batch_confirm_merges(pairs)
        print(f"  ✓ merged {ok}/{len(pairs)}, errors={len(errs)}")
        for e in errs[:5]:
            print(f"    {e}")
    _pause()


def webhooks_flow() -> None:
    print("\n═══ Webhooks ═══")
    while True:
        print("\n  1) List  2) Register  3) Toggle  4) Delete  "
              "5) Recent events  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for w in alumni_integrations.list_webhooks():
                    print(f"   #{w.webhook_id:<3} "
                          f"{'A' if w.active else 'I'}  {w.url}  → "
                          f"{','.join(w.event_types)}")
            elif ch == "2":
                url = _input("URL", allow_empty=False)
                evs = _input(
                    f"Event types (comma-separated; one of: "
                    f"{', '.join(WEBHOOK_EVENT_TYPES)})",
                    allow_empty=False)
                events = [e.strip() for e in evs.split(",") if e.strip()]
                secret = _input("Secret (optional)") or None
                w = alumni_integrations.register_webhook(url, event_types=events,
                                              secret=secret)
                print(f"  ✓ #{w.webhook_id}")
            elif ch == "3":
                wid = int(_input("Webhook id", allow_empty=False))
                active = _yes_no("Active?", default=True)
                alumni_integrations.set_webhook_active(wid, active)
                print("  ✓")
            elif ch == "4":
                wid = int(_input("Webhook id", allow_empty=False))
                if _yes_no(f"Delete webhook #{wid}?", default=False):
                    alumni_integrations.delete_webhook(wid)
                    print("  ✓")
            elif ch == "5":
                for ev in alumni_integrations.list_recent_webhook_events(limit=20):
                    print(f"   #{ev['event_id']:<5} {ev['queued_at']}  "
                          f"{ev['event_type']:<22} "
                          f"delivered={ev['delivered_at'] or '—'}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def custom_fields_flow() -> None:
    print("\n═══ Custom fields ═══")
    while True:
        print("\n  1) List  2) Add  3) Delete  4) Set value  "
              "5) Search by value  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for f in alumni_integrations.list_custom_fields():
                    print(f"   #{f.field_id:<3} {f.name:<18} "
                          f"[{f.type}]  {f.label}")
            elif ch == "2":
                name = _input("Name (machine)", allow_empty=False)
                label = _input("Label (display)", allow_empty=False)
                tp = _pick_from("Type", list(CUSTOM_FIELD_TYPES),
                                   default="text")
                alumni_integrations.add_custom_field(name, label, type=tp)
                print("  ✓")
            elif ch == "3":
                fid = int(_input("Field id", allow_empty=False))
                if _yes_no(f"Delete field #{fid}?", default=False):
                    alumni_integrations.delete_custom_field(fid)
                    print("  ✓")
            elif ch == "4":
                a = _pick_alumnus()
                name = _input("Field name", allow_empty=False)
                val = _input("Value (blank=clear)")
                alumni_integrations.set_custom_value(a.alumni_id, name, val)
                print("  ✓")
            elif ch == "5":
                name = _input("Field name", allow_empty=False)
                val = _input("Value", allow_empty=False)
                for x in alumni_integrations.search_by_custom(name, val):
                    print(f"   #{x.alumni_id:<5} {x.full_name}")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


def media_flow() -> None:
    print("\n═══ Media attachments ═══")
    while True:
        print("\n  1) List  2) Attach  3) Set profile  "
          "4) Set consent  5) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                a = _pick_alumnus()
                for m in alumni_integrations.list_media(a.alumni_id):
                    star = " ★" if m.is_profile else "  "
                    print(f"   #{m.media_id:<3}{star} [{m.kind}] "
                          f"consent={'Y' if m.consent_granted else 'N'}  "
                          f"exif_stripped="
                          f"{'Y' if m.exif_stripped else 'N'}  "
                          f"{m.file_path}")
            elif ch == "2":
                a = _pick_alumnus()
                path = _input("File path", allow_empty=False)
                kind = _pick_from("Kind", list(MEDIA_KINDS),
                                     default="photo")
                cap = _input("Caption (optional)") or None
                consent = _yes_no("Consent granted?", default=False)
                strip = _yes_no("Strip EXIF?", default=True)
                profile = _yes_no("Set as profile photo?", default=False)
                m = alumni_integrations.attach_media(a.alumni_id, path, kind=kind,
                    caption=cap, consent_granted=consent,
                    strip_exif=strip, is_profile=profile)
                print(f"  ✓ media #{m.media_id} "
                      f"(exif_stripped={m.exif_stripped})")
            elif ch == "3":
                a = _pick_alumnus()
                mid = int(_input("Media id", allow_empty=False))
                alumni_integrations.set_profile_media(a.alumni_id, mid)
                print("  ✓")
            elif ch == "4":
                mid = int(_input("Media id", allow_empty=False))
                granted = _yes_no("Consent granted?", default=True)
                alumni_integrations.set_media_consent(mid, granted)
                print("  ✓")
            elif ch == "5":
                mid = int(_input("Media id", allow_empty=False))
                delfile = _yes_no("Also delete file from disk?",
                                     default=False)
                alumni_integrations.delete_media(mid, delete_file=delfile)
                print("  ✓")
        except (ValidationError, ValueError) as e:
            print(f"  ✗ {e}")
        except _UserAbort:
            print("  Cancelled.")


_OPS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Bulk CSV import",         import_csv_flow),
    ("Bulk CSV export",         export_csv_flow),
    ("Duplicate detection",     dedupe_flow),
    ("Merge by id",             merge_flow),
    ("Audit log",               audit_log_flow),
    ("Soft-delete trash",       trash_flow),
    ("Saved searches",          saved_searches_flow),
    ("Surveys",                 surveys_flow),
    ("SAR bundle",              sar_flow),
    ("Right-to-erasure",        erasure_flow),
    ("Dedupe (confidence buckets)", dedupe_buckets_flow),
    ("Webhooks",                webhooks_flow),
]


def ops_flow() -> None:
    alumni_models._log_action("cli.menu_entered", menu="alumni.ops")
    while True:
        print("\n── Alumni — Operational quality ──")
        for i, (label, _) in enumerate(_OPS_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            alumni_models._log_action("cli.menu_exited", menu="alumni.ops")
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_OPS_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _OPS_MENU[int(choice) - 1]
        alumni_models._log_action("cli.menu_select",
                          menu="alumni.ops", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception(
                "Alumni ops handler crashed (option=%s)", label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


_REPORTS_MENU: list[tuple[str, Callable[[], None]]] = [
    ("KS5 destinations CSV (DfE-style)", report_ks5_csv),
    ("Sustained destinations (1/3/5y)",   report_sustained),
    ("Cohort comparison",                   report_cohort_comparison),
    ("University success rates",            report_university_success),
    ("Apprenticeship outcomes",             report_apprenticeship_outcomes),
    ("Disadvantage gap",                    report_disadvantage_gap),
    ("Geographic distribution",             report_geographic),
    ("Sector breakdown",                    report_sector_breakdown),
    ("'Where are they now' site",          report_where_are_they_now),
    ("Re-engagement worklist",              re_engagement_flow),
    ("Upcoming milestones",                 milestones_flow),
    ("Lost-contact queue",                  lost_contact_flow),
    ("SOC/NAICS breakdown",                 soc_flow),
    ("Salary band breakdown",               salary_band_report_flow),
    ("Russell Group / Oxbridge breakout",   russell_oxbridge_flow),
    ("Postgraduate progression",            pg_progression_flow),
    ("HESA benchmark comparison",           hesa_flow),
    ("DfE 16-18 destinations export",       dfe_export_flow),
    ("Data quality dashboard",              quality_flow),
]


def reports_flow() -> None:
    alumni_models._log_action("cli.menu_entered", menu="alumni.reports")
    while True:
        print("\n── Alumni — Reports ──")
        for i, (label, _) in enumerate(_REPORTS_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            alumni_models._log_action("cli.menu_exited", menu="alumni.reports")
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_REPORTS_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _REPORTS_MENU[int(choice) - 1]
        alumni_models._log_action("cli.menu_select",
                          menu="alumni.reports", option=label)
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception(
                "Alumni reports handler crashed (option=%s)", label)
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()
