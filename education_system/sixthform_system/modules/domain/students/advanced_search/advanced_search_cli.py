"""CLI flows for Sixth Form Advanced Search."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as data,
)
from education_system.sixthform_system.modules.domain.students.advanced_search.advanced_search import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    QUERY_SYNTAX_HELP,
    SavedSearch,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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


def _pick_scopes(default: list[str] | None = None) -> list[str]:
    """Ask the user which scopes to include. Empty = all."""
    print("\n  Scopes (Enter for all; comma list e.g. 'students,staff'):")
    for i, s in enumerate(ALL_SCOPES, 1):
        marker = " *" if default and s in default else "  "
        print(f"    {marker}{i:>2}) {SCOPE_LABELS[s]:<22} ({s})")
    while True:
        raw = _input("  Scopes",
                      default=",".join(default) if default else "")
        if not raw:
            return list(ALL_SCOPES)
        tokens = [t.strip() for t in raw.replace(" ", "").split(",")
                   if t.strip()]
        # Allow numeric picks too
        resolved: list[str] = []
        ok = True
        for t in tokens:
            if t.isdigit():
                n = int(t)
                if 1 <= n <= len(ALL_SCOPES):
                    resolved.append(ALL_SCOPES[n - 1])
                else:
                    print(f"    Out of range: {t}")
                    ok = False
                    break
            elif t in ALL_SCOPES:
                resolved.append(t)
            else:
                print(f"    Unknown scope: {t!r}")
                ok = False
                break
        if not ok:
            continue
        return resolved


# ── Print helpers ──────────────────────────────────────────────────

def _print_results(results: SearchResults) -> None:
    if results.total == 0:
        print(f"\n  No hits for query {results.query!r}.")
        if results.suggestions:
            print(f"  Did you mean:  {results.suggestions[0]}")
        return
    print(f"\n  {results.total} hit(s) for query {results.query!r}.")
    for scope in results.scopes:
        hits = results.hits_by_scope.get(scope, [])
        if not hits:
            continue
        label = SCOPE_LABELS.get(scope, scope)
        print(f"\n  ── {label} ({len(hits)}) ──")
        for h in hits:
            print(f"    [{scope}#{h.entity_id}]  {h.label}")
            if h.sublabel:
                print(f"        {h.sublabel}")
            if h.matched_field:
                print(f"        ({h.matched_field})")


def _print_saved(rows: list[SavedSearch]) -> None:
    if not rows:
        print("\n  (no saved searches)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<24}  {'Query':<26}  Scopes")
    print("  " + "-" * 90)
    for s in rows:
        scopes = ",".join(s.scopes) if s.scopes else "(all)"
        q = s.query or "(empty)"
        print(f"  {s.saved_id:>4}  {s.name[:24]:<24}  "
              f"{q[:26]:<26}  {scopes}")
    print(f"\n  {len(rows)} saved.")


# ── Flows ──────────────────────────────────────────────────────────

def syntax_help() -> None:
    print("\n═══ Query Syntax ═══\n")
    for line in QUERY_SYNTAX_HELP.splitlines():
        print(f"  {line}")
    print("\n  Examples (copy into the query bar):")
    for desc, q in data.query_examples():
        print(f"    {desc:<38} {q}")
    _pause()


def quick_search() -> None:
    print("\n═══ Quick Search (all scopes) ═══")
    try:
        q = _input("Query (empty = list everything)")
        n = int(_input("Per-scope limit", default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.run_search(q, limit_per_scope=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def scoped_search() -> None:
    print("\n═══ Scoped Search ═══")
    try:
        q = _input("Query (empty = list)")
        scopes = _pick_scopes()
        n = int(_input("Per-scope limit", default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def search_one_scope() -> None:
    print("\n═══ Search a Single Scope ═══")
    try:
        scopes = _pick_scopes()
        q = _input("Query")
        n = int(_input("Per-scope limit",
                          default=str(DEFAULT_LIMIT_PER_SCOPE)))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if not scopes:
        scopes = list(ALL_SCOPES)
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=n)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


# ── Saved searches ────────────────────────────────────────────────

def list_saved() -> None:
    print("\n═══ Saved Searches ═══")
    _print_saved(data.list_saved_searches())
    _pause()


def new_saved() -> None:
    print("\n═══ New Saved Search ═══")
    try:
        name = _input("Name", allow_empty=False)
        q = _input("Query")
        scopes = _pick_scopes()
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_saved_search({
            "name": name, "query": q, "scopes": scopes, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created saved search #{s.saved_id} {s.name!r}")
    _pause()


def edit_saved() -> None:
    print("\n═══ Edit Saved Search ═══")
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_saved_search(sid)
    if existing is None:
        print(f"  ✗ No saved search #{sid}")
        _pause()
        return
    try:
        name = _input("Name", default=existing.name, allow_empty=False)
        q = _input("Query", default=existing.query)
        scopes = _pick_scopes(default=existing.scopes)
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_saved_search(sid, {
            "name": name, "query": q, "scopes": scopes, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{sid}")
    _pause()


def run_saved() -> None:
    print("\n═══ Run Saved Search ═══")
    saved = data.list_saved_searches()
    if not saved:
        print("\n  (no saved searches yet)")
        _pause()
        return
    _print_saved(saved)
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.run_saved_search(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    _print_results(r)
    _pause()


def delete_saved() -> None:
    print("\n═══ Delete Saved Search ═══")
    try:
        sid = int(_input("Saved ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_saved_search(sid) is None:
        print(f"  ✗ No saved search #{sid}")
        _pause()
        return
    if _input(f"Delete saved search #{sid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_saved_search(sid):
        print(f"\n  ✓ Deleted #{sid}")
    _pause()


# ── History ───────────────────────────────────────────────────────

def show_history() -> None:
    print("\n═══ Search History ═══")
    rows = data.list_history(limit=50)
    if not rows:
        print("\n  (no history)")
        _pause()
        return
    print()
    print(f"  {'#':>4}  {'When':<19}  {'Hits':>5}  Query  ·  Scopes")
    print("  " + "-" * 90)
    for h in rows:
        scopes = ",".join(h.scopes) if h.scopes else "(all)"
        q = h.query or "(empty)"
        print(f"  {h.history_id:>4}  {h.ts[:19]:<19}  "
              f"{h.result_count:>5}  {q}  ·  {scopes}")
    print(f"\n  {len(rows)} entry/entries.")
    _pause()


def clear_history_flow() -> None:
    print("\n═══ Clear Search History ═══")
    if _input("Clear all history? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    n = data.clear_history()
    print(f"\n  ✓ Cleared {n} entry/entries.")
    _pause()


# ── New flows: filters, pinning, schedules, telemetry, infra ──────

def filtered_search() -> None:
    """Search with structured filters (year, tutor group, role, etc.)."""
    q = _input("Query (empty = list)")
    scopes = _pick_scopes()
    filters: dict[str, Any] = {}
    yr = _input("Year group (e.g. 12, blank=any)")
    if yr:
        filters["year_group"] = yr
    tg = _input("Tutor group name (blank=any)")
    if tg:
        filters["tutor_group"] = tg
    role = _input("Role (e.g. tutor; blank=admin)")
    if role:
        filters["role"] = role
    owner = _input("Owned by staff_id (blank=any)")
    if owner:
        filters["owned_by_staff"] = owner
    sen = _input("SEN only? y/N", default="n").lower().startswith("y")
    if sen:
        filters["sen_only"] = True
    inc_arch = _input("Include archived? y/N",
                       default="n").lower().startswith("y")
    if inc_arch:
        filters["include_archived"] = True
    actor = _input("Actor (for pinning boost; blank=none)")
    try:
        results = data.run_search(
            q, scopes=scopes, filters=filters,
            actor=actor or None, interleave=True)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        return
    _print_results(results)
    _pause()


def pin_flow() -> None:
    actor = _input("Your actor id", allow_empty=False)
    scope = _input(f"Scope (one of {','.join(ALL_SCOPES)})",
                    allow_empty=False)
    eid = _input("Entity id", allow_empty=False)
    label = _input("Label (optional)")
    try:
        p = data.pin_result(actor, scope, eid, label=label)
        print(f"\n  ✓ Pinned #{p.pin_id} ({p.scope}/{p.entity_id})")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def list_pins_flow() -> None:
    actor = _input("Actor (blank = all)")
    pins = data.list_pinned(actor or None)
    if not pins:
        print("\n  No pinned results.")
    else:
        print(f"\n  {len(pins)} pinned:")
        for p in pins:
            print(f"   #{p.pin_id}  {p.actor}  {p.scope}/{p.entity_id}"
                  f"  {p.label}")
    _pause()


def unpin_flow() -> None:
    actor = _input("Actor", allow_empty=False)
    scope = _input("Scope", allow_empty=False)
    eid = _input("Entity id", allow_empty=False)
    ok = data.unpin_result(actor, scope, eid)
    print(f"\n  {'✓ Unpinned' if ok else '✗ Not found'}")
    _pause()


def schedule_saved_flow() -> None:
    sid = _input("Saved-search id", allow_empty=False)
    cron = _input("Cron (e.g. daily/hourly)", default="daily")
    actor = _input("Notify actor", allow_empty=False)
    try:
        s = data.schedule_saved_search(
            int(sid), cron=cron, notify_actor=actor)
        print(f"\n  ✓ Scheduled #{s.schedule_id} cron={s.cron}")
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def list_schedules_flow() -> None:
    rows = data.list_scheduled_searches()
    if not rows:
        print("\n  No scheduled searches.")
    else:
        for r in rows:
            print(f"   #{r.schedule_id}  saved={r.saved_id}  "
                  f"cron={r.cron}  notify={r.notify_actor}  "
                  f"last_run={r.last_run_at or '—'}  "
                  f"last_count={r.last_count}  "
                  f"enabled={r.enabled}")
    _pause()


def poll_subscriptions_flow() -> None:
    fired = data.poll_subscriptions()
    print(f"\n  Polled. {len(fired)} subscription(s) fired.")
    for s in fired:
        print(f"   • #{s.schedule_id} → {s.notify_actor}")
    _pause()


def inbox_flow() -> None:
    actor = _input("Actor", allow_empty=False)
    unread = _input("Unread only? Y/n",
                     default="y").lower().startswith("y")
    rows = data.list_subscription_notifications(actor, unread_only=unread)
    if not rows:
        print("\n  (empty)")
    else:
        for r in rows:
            mark = "•" if not r.get("read_at") else " "
            print(f"   {mark} #{r['notif_id']}  "
                  f"+{r['delta']}/{r['total']}  "
                  f"{r.get('sample_scope') or ''}: "
                  f"{r.get('sample_label') or ''}")
    _pause()


def export_saved_flow() -> None:
    path = _input("Export file path (blank = print)")
    text = data.export_saved_searches()
    if path:
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"\n  ✓ Wrote {len(text)} chars to {path}")
        except OSError as e:
            print(f"\n  ✗ {e}")
    else:
        print("\n" + text)
    _pause()


def import_saved_flow() -> None:
    path = _input("Import file path", allow_empty=False)
    overwrite = _input("Overwrite existing? y/N",
                        default="n").lower().startswith("y")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        counts = data.import_saved_searches(text, overwrite=overwrite)
        print(f"\n  ✓ {counts}")
    except (OSError, ValidationError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def telemetry_flow() -> None:
    ts = data.telemetry_summary()
    print(f"\n  Searches: {ts.total_searches}  "
          f"Zero-result: {ts.zero_result}")
    if ts.top_queries:
        print("\n  Top queries:")
        for q, n in ts.top_queries:
            print(f"   {n:>3}× {q!r}")
    if ts.slowest_scopes_ms:
        print("\n  Slowest scopes (avg ms):")
        for s, ms in ts.slowest_scopes_ms.items():
            print(f"   {s:<22} {ms:>8.1f}")
    if ts.zero_result_queries:
        print("\n  Recent zero-result queries:")
        for q in ts.zero_result_queries:
            print(f"   • {q!r}")
    _pause()


def refresh_index_flow() -> None:
    if not data._fts_available():
        print("\n  FTS5 is not available in this SQLite build.")
        _pause()
        return
    scopes = _pick_scopes()
    print("\n  Refreshing index...")
    counts = data.refresh_index(scopes)
    total = sum(counts.values())
    print(f"\n  ✓ Indexed {total} row(s) across "
          f"{len(counts)} scope(s).")
    for s, n in counts.items():
        print(f"   {s:<22} {n}")
    _pause()


def clear_cache_flow() -> None:
    data.clear_cache()
    print("\n  ✓ Search cache cleared.")
    _pause()


def suggest_flow() -> None:
    prefix = _input("Prefix")
    out = data.suggest(prefix, limit=10)
    if not out:
        print("\n  (no suggestions)")
    else:
        for s in out:
            print(f"   • {s}")
    _pause()


# ── Relational tools (items 11–17) ────────────────────────────────

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def list_cohorts_flow() -> None:
    print("\n═══ Cohorts ═══")
    rows = data.list_cohorts()
    if not rows:
        print("\n  (no cohorts yet)")
    else:
        print()
        for c in rows:
            print(f"   #{c.cohort_id:<4} {c.name:<28} "
                  f"{c.member_count:>4} member(s)   {c.notes or ''}")
    _pause()


def save_cohort_flow() -> None:
    print("\n═══ Save Search Results as Cohort ═══")
    try:
        q = _input("Query")
        scopes = _pick_scopes()
        name = _input("Cohort name", allow_empty=False)
        notes = _input("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        results = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        c = data.create_cohort_from_results(
            name, results, notes=notes or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Cohort #{c.cohort_id} {c.name!r} "
          f"with {c.member_count} student(s).")
    _pause()


def cohort_members_flow() -> None:
    name = _input("Cohort name or id", allow_empty=False)
    members = data.cohort_members(name)
    if not members:
        print("\n  (empty or unknown cohort)")
    else:
        print(f"\n  {len(members)} member(s):")
        for sid in members:
            print(f"   • {sid}")
    _pause()


def delete_cohort_flow() -> None:
    name = _input("Cohort name or id", allow_empty=False)
    if _input(f"Delete cohort {name!r}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    print("\n  ✓ Deleted." if data.delete_cohort(name)
          else "\n  ✗ Not found.")
    _pause()


def family_flow() -> None:
    sid = _input("Student id", allow_empty=False)
    try:
        rels = data.find_relatives(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not rels:
        print("\n  No likely relatives found.")
    else:
        print(f"\n  {len(rels)} possible relative(s):")
        for r in rels:
            print(f"   • {r.student_id}  {r.full_name}  — {r.basis}")
    _pause()


def group_rollup_flow() -> None:
    gid = _input("Class group id", allow_empty=False)
    try:
        roll = data.group_rollup(int(gid))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    att = "—" if roll.avg_attendance is None else f"{roll.avg_attendance}%"
    print(f"\n  {roll.group_name}  (group #{roll.group_id})")
    print(f"   Members:           {roll.member_count}")
    print(f"   Avg attendance:    {att}")
    print(f"   Behaviour points:  {roll.behaviour_points} "
          f"({roll.behaviour_count} entries)")
    print(f"   Open concerns:     {roll.open_concerns}")
    _pause()


def ucas_peers_flow() -> None:
    uni = _input("University (substring)", allow_empty=False)
    course = _input("Course code (optional)")
    try:
        peers = data.ucas_peers(uni, course or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not peers:
        print("\n  No matching applicants.")
    else:
        print(f"\n  {len(peers)} applicant(s):")
        for p in peers:
            print(f"   • {p.student_id}  {p.university} — "
                  f"{p.course_name} ({p.course_code or '—'})  [{p.status}]")
    _pause()


def ucas_clusters_flow() -> None:
    by_course = _input("Cluster by course too? y/N",
                       default="n").lower().startswith("y")
    cl = data.ucas_choice_clusters(by_course=by_course)
    if not cl:
        print("\n  No shared choices (min 2 applicants).")
    else:
        print()
        for c in cl[:30]:
            label = c.university + (f" / {c.course_code}"
                                    if c.course_code else "")
            print(f"   {len(c.student_ids):>3}×  {label}: "
                  f"{', '.join(c.student_ids)}")
    _pause()


def clashes_flow() -> None:
    cl = data.timetable_clashes()
    if not cl:
        print("\n  No timetable clashes detected.")
    else:
        print(f"\n  {len(cl)} clash(es):")
        for c in cl[:60]:
            d = _DAYS[c.day - 1] if 1 <= c.day <= 7 else f"day{c.day}"
            print(f"   [{c.kind:<7}] {d} P{c.period}  {c.detail}  "
                  f"groups={c.group_ids}")
    _pause()


def similar_flow() -> None:
    sid = _input("Student id", allow_empty=False)
    try:
        sim = data.similar_students(sid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not sim:
        print("\n  No similar students found.")
    else:
        print(f"\n  {len(sim)} similar:")
        for s in sim:
            print(f"   {s.score:>5}  {s.student_id}  {s.full_name}  "
                  f"— {'; '.join(s.shared)}")
    _pause()


# ── Alerts, dashboards, security, exports, analytics (26–50) ──────

def schedule_delta_flow() -> None:
    sid = _input("Scheduled-search id", allow_empty=False)
    try:
        d = data.schedule_delta(int(sid))
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  Total now: {d.total}   +{len(d.added)} added   "
          f"-{len(d.removed)} removed")
    for k in d.added[:20]:
        print(f"   + {k}")
    for k in d.removed[:20]:
        print(f"   - {k}")
    _pause()


def digest_flow() -> None:
    actor = _input("Actor (blank = all)")
    dg = data.build_digest(actor or None)
    print(f"\n  Digest — {dg.total_new} new across "
          f"{len(dg.lines)} scheduled search(es):")
    for line in dg.lines:
        print(f"   {line.new_since_last:>4} new · total {line.total:<5} "
              f"{line.saved_name}  (last {line.last_run_at or '—'})")
    _pause()


def list_dashboards_flow() -> None:
    rows = data.list_dashboards()
    if not rows:
        print("\n  (no dashboards)")
    else:
        for d in rows:
            print(f"   #{d.dashboard_id:<4} {d.name:<26} "
                  f"{len(d.saved_ids)} panel(s)")
    _pause()


def create_dashboard_flow() -> None:
    name = _input("Dashboard name", allow_empty=False)
    ids = _input("Saved-search ids (comma-separated)")
    saved_ids = [int(x) for x in ids.replace(" ", "").split(",") if x.isdigit()]
    try:
        d = data.create_dashboard(name, saved_ids)
        print(f"\n  ✓ Dashboard #{d.dashboard_id} with "
              f"{len(d.saved_ids)} panel(s).")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def run_dashboard_flow() -> None:
    name = _input("Dashboard name or id", allow_empty=False)
    role = _input("Role (blank = admin)")
    try:
        panels = data.run_dashboard(name, role=role or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  {name}:")
    for p in panels:
        cnt = "err" if p.total < 0 else str(p.total)
        print(f"   {cnt:>5}  {p.name}   ({p.query or '(empty)'})")
    _pause()


def audit_flow() -> None:
    sens = _input("Sensitive only? y/N", default="n").lower().startswith("y")
    rows = data.list_search_audit(limit=50, sensitive_only=sens)
    if not rows:
        print("\n  (no audit entries)")
    else:
        for e in rows:
            bg = "  [BREAK-GLASS]" if e.break_glass else ""
            print(f"   {e.ts}  {e.actor or '—'}/{e.role or '—'}  "
                  f"{e.query!r}  sens={','.join(e.sensitive_scopes)}{bg}")
            if e.reason:
                print(f"       reason: {e.reason}")
    _pause()


def duplicates_flow() -> None:
    groups = data.find_duplicate_students()
    if not groups:
        print("\n  No likely duplicate students.")
    else:
        print(f"\n  {len(groups)} possible duplicate group(s):")
        for g in groups[:40]:
            print(f"   [{g.reason}] {g.key}: {', '.join(g.student_ids)}")
    _pause()


def data_gaps_flow() -> None:
    scope = _input("Scope", default="students")
    try:
        gaps = data.find_data_gaps(scope)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not gaps:
        print("\n  No data gaps found.")
    else:
        print(f"\n  {len(gaps)} record(s) with gaps:")
        for g in gaps[:50]:
            print(f"   {g.entity_id}  {g.label[:40]:<40}  "
                  f"missing: {', '.join(g.missing)}")
    _pause()


def export_search_flow() -> None:
    q = _input("Query")
    scopes = _pick_scopes()
    fmt = _input("Format (csv/tsv/json/html/md/xlsx/pdf)", default="csv")
    path = _input("Output file path", allow_empty=False)
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        data.export_results_file(r, path, fmt=fmt)
        print(f"\n  ✓ Wrote {r.total} row(s) to {path}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def contact_sheet_flow() -> None:
    q = _input("Query")
    scopes = _pick_scopes(default=["students"])
    path = _input("Output HTML path", allow_empty=False)
    try:
        r = data.run_search(q, scopes=scopes, limit_per_scope=1000)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data.contact_sheet(r))
        print(f"\n  ✓ Contact sheet written to {path}")
    except (ValidationError, OSError) as e:
        print(f"\n  ✗ {e}")
    _pause()


def nl_query_flow() -> None:
    text = _input("Describe what you want", allow_empty=False)
    q = data.nl_to_query(text)
    if not q:
        print("\n  (couldn't translate — try the query syntax help)")
        _pause()
        return
    print(f"\n  Suggested query:  {q}")
    if _input("Run it? Y/n", default="y").lower().startswith("y"):
        _print_results(data.run_search(q, limit_per_scope=DEFAULT_LIMIT_PER_SCOPE))
    _pause()


def index_status_flow() -> None:
    rows = data.index_status()
    print()
    for s in rows:
        flag = "STALE" if s.stale else "ok"
        print(f"   {s.scope:<22} indexed {s.indexed_rows:>5} / "
              f"current {s.current_rows:>5}  [{flag}]  "
              f"{s.last_refresh or '—'}")
    if _input("\n  Refresh stale scopes now? y/N",
              default="n").lower().startswith("y"):
        counts = data.refresh_index(only_stale=True)
        print(f"\n  ✓ Refreshed {sum(counts.values())} row(s) across "
              f"{len(counts)} scope(s).")
    _pause()


def cache_stats_flow() -> None:
    st = data.cache_stats()
    print(f"\n  Cache: {st['entries']}/{st['max_entries']} entries  ·  "
          f"hits {st['hits']}  misses {st['misses']}  "
          f"hit-rate {st['hit_rate']:.0%}  ·  TTL {st['ttl_seconds']}s")
    _pause()


def volume_flow() -> None:
    rows = data.search_volume_by_day()
    if not rows:
        print("\n  (no search history)")
    else:
        print("\n  Searches per day:")
        for d, n in rows:
            print(f"   {d}  {'█' * min(n, 40)} {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Quick search (all scopes)",  quick_search),
    ("Scoped search",              scoped_search),
    ("Single-scope search",        search_one_scope),
    ("Filtered search (advanced)", filtered_search),
    ("Suggest (type-ahead)",       suggest_flow),
    ("Query syntax help",          syntax_help),
    ("─" * 6,                      lambda: None),
    ("List saved searches",        list_saved),
    ("Run saved search",           run_saved),
    ("New saved search",           new_saved),
    ("Edit saved search",          edit_saved),
    ("Delete saved search",        delete_saved),
    ("Export saved → JSON",        export_saved_flow),
    ("Import saved ← JSON",        import_saved_flow),
    ("─" * 6,                      lambda: None),
    ("Schedule a saved search",    schedule_saved_flow),
    ("List scheduled searches",    list_schedules_flow),
    ("Poll subscriptions now",     poll_subscriptions_flow),
    ("Subscription inbox",         inbox_flow),
    ("─" * 6,                      lambda: None),
    ("Pin a result",               pin_flow),
    ("List pinned",                list_pins_flow),
    ("Unpin a result",             unpin_flow),
    ("─" * 6,                      lambda: None),
    ("Cohorts: list",              list_cohorts_flow),
    ("Cohorts: save search as…",   save_cohort_flow),
    ("Cohorts: view members",      cohort_members_flow),
    ("Cohorts: delete",            delete_cohort_flow),
    ("Find relatives (family)",    family_flow),
    ("Class-group rollup",         group_rollup_flow),
    ("UCAS peers (same uni)",      ucas_peers_flow),
    ("UCAS choice clusters",       ucas_clusters_flow),
    ("Timetable clashes",          clashes_flow),
    ("Similar students",           similar_flow),
    ("─" * 6,                      lambda: None),
    ("Recent history",             show_history),
    ("Clear history",              clear_history_flow),
    ("Telemetry summary",          telemetry_flow),
    ("─" * 6,                      lambda: None),
    ("Rebuild FTS5 index",         refresh_index_flow),
    ("Index status / refresh stale", index_status_flow),
    ("Clear search cache",         clear_cache_flow),
    ("Cache stats",                cache_stats_flow),
    ("─" * 6,                      lambda: None),
    ("Dashboards: list",           list_dashboards_flow),
    ("Dashboards: create",         create_dashboard_flow),
    ("Dashboards: run",            run_dashboard_flow),
    ("Subscription digest",        digest_flow),
    ("Schedule delta (what changed)", schedule_delta_flow),
    ("Search volume by day",       volume_flow),
    ("Sensitive-access audit log", audit_flow),
    ("─" * 6,                      lambda: None),
    ("Export search → file",       export_search_flow),
    ("Contact sheet → HTML",       contact_sheet_flow),
    ("Duplicate students",         duplicates_flow),
    ("Data-gap search",            data_gaps_flow),
    ("Natural-language query",     nl_query_flow),
]


def run() -> None:
    while True:
        print("\n── Advanced Search ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
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
            logger.exception("Advanced-search CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Advanced Search":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Advanced-search CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
