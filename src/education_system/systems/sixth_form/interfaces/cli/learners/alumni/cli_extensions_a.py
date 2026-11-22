"""Alumni CLI: extension items 1-16 (engagement + career clusters).

Split out of ``alumni_cli`` (2026-10-22); that module re-exports every name.
"""

from __future__ import annotations

from ._helpers import (
    Any,
    CHAPTER_KINDS,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    JOB_STATUSES,
    JOB_TYPES,
    PROFICIENCY_LEVELS,
    SOCIAL_PLATFORMS,
    ValidationError,
    _UserAbort,
)
from education_system.systems.sixth_form.domain.learners.alumni import (
    careers as alumni_careers,
    engagement as alumni_engagement,
    mentoring as alumni_mentoring,
    models as alumni_models,
    records as alumni_records,
)
from ._helpers import (  # noqa: F401
    _input,
    _pause,
    _pick_alumnus,
    _pick_from,
    _pick_student,
    _yes_no,
)
from .cli_programmes import (  # noqa: F401
    _money_str,
)


# ── Engagement extensions (items 1–8) ─────────────────────────────

def social_handles_flow() -> None:
    print("\n═══ Social handles ═══")
    a = _pick_alumnus()
    while True:
        rows = alumni_engagement.list_social_handles(a.alumni_id)
        print(f"\n  {a.full_name} — social handles:")
        if rows:
            print(f"  {'#':>4}  {'Platform':<13}  {'Handle':<24}  Ver  URL")
            for s in rows:
                print(f"  {s.handle_id:>4}  {s.platform:<13}  "
                      f"{s.handle[:24]:<24}  "
                      f"{'✓' if s.verified else ' '}    "
                      f"{(s.url or '')[:40]}")
        else:
            print("  (none)")
        print("\n  1) Add  2) Edit  3) Verify  4) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                plat = _pick_from("Platform", list(SOCIAL_PLATFORMS))
                handle = _input("Handle", allow_empty=False)
                url = _input("URL") or None
                verified = _yes_no("Verified now?", default=False)
                alumni_engagement.add_social_handle(a.alumni_id, plat, handle,
                                          url=url, verified=verified)
                print("    ✓ Added")
            elif ch in ("2", "3", "4"):
                hid_raw = _input("Handle id", allow_empty=False)
                if not hid_raw.isdigit():
                    print("    Not a number."); continue
                hid = int(hid_raw)
                if ch == "2":
                    h = _input("New handle (blank to keep)")
                    u = _input("New URL (blank to keep)")
                    notes = _input("Notes (blank to keep)")
                    payload: dict[str, Any] = {}
                    if h: payload["handle"] = h
                    if u: payload["url"] = u
                    if notes: payload["notes"] = notes
                    if payload:
                        alumni_engagement.update_social_handle(hid, payload)
                        print("    ✓ Updated")
                elif ch == "3":
                    alumni_engagement.verify_social_handle(hid)
                    print("    ✓ Verified")
                else:
                    if _yes_no(f"Delete handle #{hid}?", default=False):
                        alumni_engagement.delete_social_handle(hid)
                        print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def connections_flow() -> None:
    print("\n═══ Connections ═══")
    a = _pick_alumnus()
    while True:
        rows = alumni_engagement.list_connections(a.alumni_id)
        print(f"\n  {a.full_name} — connections ({len(rows)}):")
        for c, other in rows:
            print(f"   #{c.connection_id}  → #{other.alumni_id} "
                  f"{other.full_name}  ({c.kind})")
        print("\n  1) Connect to another alumnus  2) Disconnect")
        print("  3) Mutuals with another  4) Degrees-between  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                b = _pick_alumnus()
                kind = _pick_from("Kind", list(CONNECTION_KINDS),
                                     default="Friend")
                since = _input("Since (YYYY-MM-DD, optional)") or None
                notes = _input("Notes (optional)") or None
                alumni_engagement.connect_alumni(a.alumni_id, b.alumni_id,
                                       kind=kind, since=since, notes=notes)
                print("    ✓ Connected")
            elif ch == "2":
                b = _pick_alumnus()
                if alumni_engagement.disconnect_alumni(a.alumni_id, b.alumni_id):
                    print("    ✓ Disconnected")
                else:
                    print("    No such connection.")
            elif ch == "3":
                b = _pick_alumnus()
                mutuals = alumni_engagement.mutuals_of(a.alumni_id, b.alumni_id)
                if not mutuals:
                    print("    (no mutuals)")
                else:
                    for m in mutuals:
                        print(f"    #{m.alumni_id}  {m.full_name}")
            elif ch == "4":
                b = _pick_alumnus()
                d = alumni_engagement.degrees_between(a.alumni_id, b.alumni_id)
                print(f"    Degrees: "
                      f"{'(unconnected within 6)' if d is None else d}")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def _pick_chapter() -> int:
    rows = alumni_engagement.list_chapters()
    if not rows:
        print("    No chapters."); raise _UserAbort
    print("\n  Chapters:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.chapter_id}  {c.name}  "
              f"[{c.kind}, {c.status}]")
    raw = _input(f"  Pick #1..{len(rows)} (or chapter id)",
                   allow_empty=False)
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(rows):
            return rows[n - 1].chapter_id
        match = next((c for c in rows if c.chapter_id == n), None)
        if match:
            return match.chapter_id
    raise _UserAbort


def chapters_flow() -> None:
    print("\n═══ Chapters ═══")
    while True:
        print("\n  1) List  2) Create  3) Edit  4) Delete")
        print("  5) View members  6) Add member  7) Set role  8) Remove member")
        print("  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for c in alumni_engagement.list_chapters():
                    print(f"   #{c.chapter_id:>3}  {c.name:<30}  "
                          f"[{c.kind}/{c.status}]  {c.region or '—'}")
            elif ch == "2":
                name = _input("Name", allow_empty=False)
                kind = _pick_from("Kind", list(CHAPTER_KINDS),
                                     default="Regional")
                region = _input("Region (optional)") or None
                desc = _input("Description (optional)") or None
                c = alumni_engagement.create_chapter(name, kind=kind,
                                           region=region, description=desc)
                print(f"    ✓ Created #{c.chapter_id}")
            elif ch == "3":
                cid = _pick_chapter()
                name = _input("New name (blank to keep)")
                region = _input("New region (blank to keep)")
                desc = _input("New description (blank to keep)")
                status = _input("New status (Active/Archived, blank to keep)")
                payload: dict[str, Any] = {}
                if name: payload["name"] = name
                if region: payload["region"] = region
                if desc: payload["description"] = desc
                if status: payload["status"] = status
                if payload:
                    alumni_engagement.update_chapter(cid, payload)
                    print("    ✓ Updated")
            elif ch == "4":
                cid = _pick_chapter()
                if _yes_no(f"Delete chapter #{cid} (members "
                              "are removed)?", default=False):
                    alumni_engagement.delete_chapter(cid)
                    print("    ✓ Deleted")
            elif ch == "5":
                cid = _pick_chapter()
                inc = _yes_no("Include former members?", default=False)
                for cm, al in alumni_engagement.list_chapter_members(
                        cid, include_left=inc):
                    tag = f" (left {cm.left_on})" if cm.left_on else ""
                    print(f"    #{al.alumni_id}  {al.full_name:<28}  "
                          f"{cm.role}{tag}")
            elif ch == "6":
                cid = _pick_chapter()
                a = _pick_alumnus()
                role = _pick_from("Role", list(CHAPTER_ROLES),
                                     default="Member")
                joined = _input("Joined on (YYYY-MM-DD, optional)") or None
                alumni_engagement.add_chapter_member(cid, a.alumni_id,
                                           role=role, joined_on=joined)
                print("    ✓ Added")
            elif ch == "7":
                cid = _pick_chapter()
                a = _pick_alumnus()
                role = _pick_from("Role", list(CHAPTER_ROLES))
                alumni_engagement.set_chapter_role(cid, a.alumni_id, role)
                print("    ✓ Role updated")
            elif ch == "8":
                cid = _pick_chapter()
                a = _pick_alumnus()
                hard = _yes_no("Hard-delete (no audit trail)?",
                                  default=False)
                if hard:
                    alumni_engagement.purge_chapter_member(cid, a.alumni_id)
                else:
                    alumni_engagement.remove_chapter_member(cid, a.alumni_id)
                print("    ✓ Removed")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def engagement_flow() -> None:
    print("\n═══ Engagement score ═══")
    print("  1) Score one alumnus  2) Leaderboard  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    try:
        if ch == "1":
            a = _pick_alumnus()
            s = alumni_engagement.compute_engagement_score(a.alumni_id)
            print(f"\n  {a.full_name}: score = {s.score}")
            print(f"    decay={s.decay}  "
                  f"months_since_contact={s.months_since_contact}")
            print(f"    opens={s.comms_opens}  "
                  f"events_attended={s.events_attended}  "
                  f"donations={s.donations_count} "
                  f"({_money_str(s.donation_total_pence)})  "
                  f"volunteer_hrs={s.volunteer_hours}")
        elif ch == "2":
            year = _input("Leaving year filter (blank = all)") or None
            n = int(_input("How many", default="20") or "20")
            rows = alumni_engagement.engagement_leaderboard(limit=n, leaving_year=year)
            with _connect_alumni_lookup() as lookup:
                for r in rows:
                    name = lookup.get(r.alumni_id, f"#{r.alumni_id}")
                    print(f"  {r.score:>7.1f}  {name}")
    except (ValidationError, ValueError) as e:
        print(f"    ✗ {e}")
    except _UserAbort:
        print("    Cancelled.")
    _pause()


class _connect_alumni_lookup:
    """Tiny context manager that caches alumni id→name for one report."""

    def __enter__(self) -> dict[int, str]:
        self._cache = {a.alumni_id: a.full_name
                          for a in alumni_records.list_alumni()}
        return self._cache

    def __exit__(self, *a) -> None:
        self._cache.clear()


def re_engagement_flow() -> None:
    print("\n═══ Re-engagement worklist ═══")
    try:
        thr = float(_input("Score threshold", default="5") or "5")
        months = int(_input("Months quiet", default="18") or "18")
        year = _input("Leaving year filter (blank = all)") or None
        lim = int(_input("Max results", default="50") or "50")
    except _UserAbort:
        return
    cands = alumni_engagement.re_engagement_worklist(
        score_threshold=thr, months_quiet=months,
        leaving_year=year, limit=lim)
    if not cands:
        print("  (none)")
    else:
        for c in cands:
            print(f"  {c.score:>6.1f}  #{c.alumnus.alumni_id:<5} "
                  f"{c.alumnus.full_name:<28}  "
                  f"{c.alumnus.leaving_year or '—':<6}  "
                  f"— {c.reason}")
    _pause()


def milestones_flow() -> None:
    print("\n═══ Upcoming milestones ═══")
    try:
        days = int(_input("Days ahead", default="30") or "30")
    except _UserAbort:
        return
    rows = alumni_engagement.upcoming_milestones(days=days)
    if not rows:
        print("  (none)")
    else:
        for m in rows:
            extra = f" ({m.years}y)" if m.years else ""
            tail = f" — {m.detail}" if m.detail else ""
            print(f"  {m.when}  {m.kind:<22}{extra:<5}  "
                  f"#{m.alumni_id:<5} {m.full_name}{tail}")
    _pause()


def lost_contact_flow() -> None:
    print("\n═══ Lost-contact / find-a-friend queue ═══")
    try:
        thr = int(_input("Hard-bounce threshold",
                            default=str(
                                alumni_models.HARD_BOUNCE_THRESHOLD)) or "3")
        need_no_phone = _yes_no("Require no phone too?", default=True)
    except _UserAbort:
        return
    rows = alumni_engagement.lost_contact_queue(
        bounce_threshold=thr, require_no_phone=need_no_phone)
    if not rows:
        print("  (none)")
    else:
        for c in rows:
            a = c.alumnus
            print(f"  #{a.alumni_id:<5} {a.full_name:<28} "
                  f"bounces={c.bounce_count}  "
                  f"email={'Y' if c.has_email else 'N'}  "
                  f"phone={'Y' if c.has_phone else 'N'}  "
                  f"addr={'Y' if c.has_address else 'N'}  "
                  f"last={a.last_contacted or '—'}")
    _pause()


def directory_flow() -> None:
    print("\n═══ Public directory ═══")
    print("  1) Opt-in alumnus  2) Opt-out alumnus  3) Check status")
    print("  4) Browse public directory  0) Back")
    try:
        ch = _input("Select", default="0")
    except _UserAbort:
        return
    try:
        if ch in ("1", "2", "3"):
            a = _pick_alumnus()
            if ch == "1":
                alumni_engagement.opt_in_directory(a.alumni_id,
                                         source="cli",
                                         actor="cli")
                print("    ✓ Opted in to public directory")
            elif ch == "2":
                n = alumni_engagement.opt_out_directory(a.alumni_id, actor="cli")
                print(f"    ✓ Withdrew {n} consent record(s)")
            else:
                print("    listed: "
                      f"{'YES' if alumni_engagement.is_in_directory(a.alumni_id) else 'NO'}")
        elif ch == "4":
            year = _input("Leaving year (blank = all)") or None
            sector = _input("Sector (blank = all)") or None
            q = _input("Search query (blank = all)") or None
            rows = alumni_engagement.list_public_directory(
                leaving_year=year, sector=sector, q=q)
            if not rows:
                print("  (none)")
            else:
                for d in rows:
                    print(f"  #{d.alumni_id:<5} {d.display_name:<28} "
                          f"{d.leaving_year or '—':<6}  "
                          f"{(d.current_role or '—'):<22}  "
                          f"{(d.current_employer or '—'):<22}  "
                          f"{d.current_sector or '—'}")
    except (ValidationError, ValueError) as e:
        print(f"    ✗ {e}")
    except _UserAbort:
        print("    Cancelled.")
    _pause()


# ── Career-cluster extensions (items 9–16) ────────────────────────

def skills_flow() -> None:
    print("\n═══ Skills ═══")
    a = _pick_alumnus()
    while True:
        rows = alumni_careers.list_skills_for(a.alumni_id)
        print(f"\n  {a.full_name} — skills:")
        if rows:
            for s in rows:
                yrs = f" ({s.years}y)" if s.years else ""
                print(f"   #{s.skill_id:>3}  {s.skill_name:<24} "
                      f"{s.proficiency:<14}{yrs}")
        else:
            print("   (none)")
        print("\n  1) Add  2) Remove  3) Find alumni by skill  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                name = _input("Skill name", allow_empty=False)
                prof = _pick_from("Proficiency",
                                     list(PROFICIENCY_LEVELS),
                                     default="Intermediate")
                yrs_raw = _input("Years of experience (blank=none)")
                yrs = float(yrs_raw) if yrs_raw else None
                alumni_careers.add_skill_to_alumnus(
                    a.alumni_id, name,
                    proficiency=prof, years=yrs)
                print("    ✓ Added")
            elif ch == "2":
                sid_raw = _input("Skill id to remove", allow_empty=False)
                if sid_raw.isdigit():
                    alumni_careers.remove_skill_from_alumnus(a.alumni_id,
                                                       int(sid_raw))
                    print("    ✓ Removed")
            elif ch == "3":
                name = _input("Skill name to search",
                                 allow_empty=False)
                min_prof = _input(
                    "Min proficiency (blank=any)") or None
                rows = alumni_careers.find_alumni_by_skill(
                    name, min_proficiency=min_prof)
                if not rows:
                    print("    (no matches)")
                else:
                    for x in rows:
                        print(f"   #{x.alumni_id:<5} {x.full_name}")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def soc_flow() -> None:
    print("\n═══ SOC/NAICS classification ═══")
    while True:
        print("\n  1) Classify a title  2) Cohort breakdown")
        print("  3) Add SOC pattern  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                t = _input("Job title", allow_empty=False)
                cls = alumni_careers.soc_classify(t)
                if cls:
                    print(f"    SOC {cls[0]}: {cls[1]}  "
                          f"(NAICS {cls[2] or '—'})")
                else:
                    print("    Unclassified")
            elif ch == "2":
                year = _input("Leaving year (blank=all)") or None
                for code, label, n in alumni_careers.soc_breakdown(
                        leaving_year=year):
                    print(f"   {code:>5}  {label:<48}  {n}")
            elif ch == "3":
                pattern = _input("Pattern (substring)",
                                    allow_empty=False)
                soc = _input("SOC code", allow_empty=False)
                lbl = _input("SOC label", allow_empty=False)
                naics = _input("NAICS code (optional)") or None
                alumni_careers.upsert_soc_pattern(pattern, soc, lbl,
                                            naics_code=naics)
                print("    ✓ Saved")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def salary_band_report_flow() -> None:
    print("\n═══ Salary band breakdown ═══")
    try:
        year = _input("Leaving year (blank=all)") or None
        sector = _input("Sector (blank=all)") or None
    except _UserAbort:
        return
    rows = alumni_careers.salary_band_breakdown(
        leaving_year=year, sector=sector)
    if not rows:
        print("  (no banded data)")
    else:
        for r in rows:
            print(f"   {r.band:<18}  {r.count:>4}  {r.pct:5.1f}%")
        med = alumni_careers.median_salary_band(leaving_year=year, sector=sector)
        print(f"   median: {med or '—'}")
    _pause()


def promotion_timeline_flow() -> None:
    print("\n═══ Promotion timeline ═══")
    a = _pick_alumnus()
    steps = alumni_careers.promotion_timeline(a.alumni_id)
    if not steps:
        print("   (no career history)")
    else:
        prev = None
        for s in steps:
            arrow = " → "
            promo = ""
            if prev and prev.role != s.role:
                promo = "  (move)"
            print(f"   {s.start_date or '—':<10}{arrow}"
                  f"{s.role:<26} @ {s.employer:<22}"
                  f"{'  [current]' if s.is_current else ''}{promo}")
            prev = s
    _pause()


def employers_flow() -> None:
    print("\n═══ Employer directory ═══")
    while True:
        print("\n  1) List  2) Add / update  3) Add alias")
        print("  4) Resolve a name  5) Top employers  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for e in alumni_careers.list_employers():
                    print(f"   #{e.employer_id:>3}  "
                          f"{e.canonical_name:<32}  "
                          f"{e.sector or '—':<18}  {e.country or '—'}")
            elif ch == "2":
                name = _input("Canonical name", allow_empty=False)
                sector = _input("Sector (optional)") or None
                website = _input("Website (optional)") or None
                country = _input("Country (optional)") or None
                e = alumni_careers.upsert_employer(name, sector=sector,
                                             website=website,
                                             country=country)
                print(f"    ✓ #{e.employer_id} saved")
            elif ch == "3":
                eid_raw = _input("Employer id", allow_empty=False)
                if not eid_raw.isdigit():
                    print("    Not a number."); continue
                alias = _input("Alias", allow_empty=False)
                alumni_careers.add_employer_alias(alias, int(eid_raw))
                print("    ✓ Added alias")
            elif ch == "4":
                name = _input("Name to resolve", allow_empty=False)
                e = alumni_careers.resolve_employer(name)
                print(f"    → {e.canonical_name if e else '(not mapped)'}")
            elif ch == "5":
                lim = int(_input("Limit", default="25") or "25")
                year = _input("Leaving year (blank=all)") or None
                for r in alumni_careers.top_employers(limit=lim, leaving_year=year):
                    print(f"   {r.alumni_count:>4}  {r.employer}")
            elif ch == "6":
                eid_raw = _input("Employer id to delete",
                                    allow_empty=False)
                if eid_raw.isdigit() and _yes_no(
                        f"Delete employer #{eid_raw}?", default=False):
                    alumni_careers.delete_employer(int(eid_raw))
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def jobs_flow() -> None:
    print("\n═══ Alumni job postings ═══")
    while True:
        print("\n  1) List open  2) Post (per alumnus)  3) View applicants")
        print("  4) Set status  5) Apply (alumnus)  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                rows = alumni_careers.list_jobs()
                if not rows:
                    print("   (none)")
                for j in rows:
                    print(f"   #{j.job_id:>4}  {j.title:<28} "
                          f"@ {j.employer or '—':<20}  "
                          f"[{j.job_type}/{j.status}]")
            elif ch == "2":
                a = _pick_alumnus()
                payload = {
                    "title": _input("Title", allow_empty=False),
                    "employer": _input("Employer") or None,
                    "sector": _input("Sector") or None,
                    "location": _input("Location") or None,
                    "job_type": _pick_from("Job type",
                                              list(JOB_TYPES),
                                              default="Graduate"),
                    "salary_band": _input("Salary band (optional)")
                                       or None,
                    "description": _input("Description") or None,
                    "apply_url": _input("Apply URL") or None,
                    "deadline": _input("Deadline (YYYY-MM-DD)") or None,
                }
                j = alumni_careers.post_job(a.alumni_id, payload)
                print(f"    ✓ Posted job #{j.job_id}")
            elif ch == "3":
                jid = int(_input("Job id", allow_empty=False))
                for r in alumni_careers.list_job_applications(jid):
                    print(f"   #{r.application_id:>4}  "
                          f"{r.applicant_kind}:{r.applicant_id:<12} "
                          f"{r.applied_on}  [{r.status}]")
            elif ch == "4":
                jid = int(_input("Job id", allow_empty=False))
                status = _pick_from("Status", list(JOB_STATUSES))
                alumni_careers.set_job_status(jid, status)
                print("    ✓ Updated")
            elif ch == "5":
                jid = int(_input("Job id", allow_empty=False))
                a = _pick_alumnus()
                alumni_careers.apply_to_job(jid, applicant_id=str(a.alumni_id))
                print("    ✓ Applied")
            elif ch == "6":
                jid = int(_input("Job id", allow_empty=False))
                if _yes_no(f"Delete job #{jid}?", default=False):
                    alumni_careers.delete_job(jid)
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def internships_flow() -> None:
    print("\n═══ Internships board ═══")
    while True:
        print("\n  1) List open  2) Post (per alumnus)  3) Applicants")
        print("  4) Set status  5) Apply (student)  6) Delete  0) Back")
        try:
            ch = _input("Select", default="0")
        except _UserAbort:
            return
        if ch == "0":
            return
        try:
            if ch == "1":
                for i in alumni_careers.list_internships():
                    paid = "PAID" if i.paid else "unpaid"
                    print(f"   #{i.internship_id:>4}  {i.title:<28} "
                          f"@ {i.employer or '—':<20}  "
                          f"[{paid}/{i.status}]  "
                          f"{i.duration_weeks or '?'}w")
            elif ch == "2":
                a = _pick_alumnus()
                paid = _yes_no("Paid?", default=True)
                payload = {
                    "title": _input("Title", allow_empty=False),
                    "employer": _input("Employer") or None,
                    "sector": _input("Sector") or None,
                    "location": _input("Location") or None,
                    "duration_weeks": _input("Duration weeks") or None,
                    "paid": paid,
                    "start_window": _input("Start window") or None,
                    "requirements": _input("Requirements") or None,
                    "apply_url": _input("Apply URL") or None,
                    "deadline": _input("Deadline (YYYY-MM-DD)") or None,
                }
                if paid:
                    p = _input("Hourly pay £ (e.g. 12.50)") or None
                    if p:
                        payload["hourly_pay"] = p
                ip = alumni_careers.post_internship(a.alumni_id, payload)
                print(f"    ✓ Posted internship #{ip.internship_id}")
            elif ch == "3":
                iid = int(_input("Internship id", allow_empty=False))
                for r in alumni_careers.list_internship_applications(iid):
                    print(f"   #{r.application_id:>4}  "
                          f"{r.student_id:<12} {r.applied_on}  "
                          f"[{r.status}]")
            elif ch == "4":
                iid = int(_input("Internship id", allow_empty=False))
                status = _pick_from("Status",
                                       list(JOB_STATUSES))
                alumni_careers.set_internship_status(iid, status)
                print("    ✓ Updated")
            elif ch == "5":
                iid = int(_input("Internship id", allow_empty=False))
                sid = _pick_student()
                alumni_careers.apply_to_internship(iid, sid)
                print("    ✓ Applied")
            elif ch == "6":
                iid = int(_input("Internship id", allow_empty=False))
                if _yes_no(f"Delete internship #{iid}?", default=False):
                    alumni_careers.delete_internship(iid)
                    print("    ✓ Deleted")
        except (ValidationError, ValueError) as e:
            print(f"    ✗ {e}")
        except _UserAbort:
            print("    Cancelled.")


def mentor_match_flow() -> None:
    print("\n═══ Mentor matching ═══")
    sid = _pick_student()
    try:
        lim = int(_input("Max matches", default="10") or "10")
        require_consent = _yes_no("Require Mentoring consent?",
                                      default=True)
    except _UserAbort:
        return
    rows = alumni_mentoring.match_mentors_for_student(
        sid, limit=lim, require_consent=require_consent)
    if not rows:
        print("   (no matches)")
    else:
        for m in rows:
            print(f"   {m.score:>6.1f}  #{m.alumnus.alumni_id:<5} "
                  f"{m.alumnus.full_name:<26}  — "
                  f"{', '.join(m.reasons) or '—'}")
    _pause()
