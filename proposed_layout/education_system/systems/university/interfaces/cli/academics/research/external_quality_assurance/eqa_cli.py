"""External Quality Assurance CLI (OfS / TEF / REF).

Thin CLI wrapper over ``qa_service`` — mirrors the GUI dashboard.
"""

from __future__ import annotations

import os

from education_system.systems.university.domain.academics.research.external_quality_assurance.services import (
    qa_service as svc,
)


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title.center(70))
    print("=" * 70)


def _ask_int(prompt: str, default: int | None = None) -> int | None:
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("  ! not an integer")
        return default


def _submissions_menu() -> None:
    while True:
        _header("Submissions Tracker")
        print("  1. List submissions")
        print("  2. Create / update submission")
        print("  3. Sign off submission")
        print("  0. Back")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            rows = svc.list_submissions()
            if not rows:
                print("\n  (no submissions)")
            else:
                print(f"\n{'ID':<5}{'Framework':<10}{'Year':<6}{'Status':<14}{'Assigned':<10}")
                print("-" * 50)
                for r in rows:
                    print(f"{r['id']:<5}{r['framework']:<10}{r['submission_year']:<6}"
                          f"{r['status']:<14}{str(r.get('assigned_to') or ''):<10}")
            _pause()
        elif choice == "2":
            fw = input(f"Framework {svc.FRAMEWORKS}: ").strip().upper()
            year = _ask_int("Submission year: ")
            status = input(f"Status {svc.QA_STATUSES} [draft]: ").strip() or "draft"
            assigned = _ask_int("Assigned-to user id (blank = none): ")
            notes = input("Notes (optional): ").strip() or None
            try:
                sid = svc.upsert_submission(fw, year, status=status,
                                            assigned_to=assigned, notes=notes)
                print(f"\n  ✓ submission {sid}")
            except ValueError as e:
                print(f"\n  ! {e}")
            _pause()
        elif choice == "3":
            sid = _ask_int("Submission ID: ")
            uid = _ask_int("Signed-off-by user id: ")
            if sid and uid and svc.sign_off_submission(sid, uid):
                print("\n  ✓ signed off")
            else:
                print("\n  ! failed (not found or already submitted)")
            _pause()


def _ofs_menu() -> None:
    while True:
        _header("OfS — B3 Metrics, APP & Protection Plans")
        print("  1. Compute B3 for a cohort year (preview)")
        print("  2. Record B3 snapshot for a cohort year")
        print("  3. List B3 snapshots")
        print("  4. Export OfS B3 return (CSV)")
        print("  5. List APP milestones")
        print("  6. Create APP milestone")
        print("  7. Update APP milestone (mark achieved / set current)")
        print("  8. List protection plans")
        print("  9. Create protection plan")
        print("  0. Back")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            yr = _ask_int("Cohort year: ")
            course = input("Course (blank = all): ").strip() or None
            if yr:
                m = svc.compute_b3_metrics(yr, course=course)
                print()
                for k, (pct, num, denom) in m.items():
                    print(f"  {k:<14} {pct:>6.2f}%   {num}/{denom}")
            _pause()
        elif choice == "2":
            yr = _ask_int("Cohort year: ")
            course = input("Course (blank = all): ").strip() or None
            if yr:
                n = svc.record_b3_snapshot(yr, course=course)
                print(f"\n  ✓ {n} metric(s) snapshotted")
            _pause()
        elif choice == "3":
            yr = _ask_int("Cohort year (blank = all): ")
            rows = svc.list_b3_snapshots(cohort_year=yr)
            if not rows:
                print("\n  (no snapshots)")
            else:
                print(f"\n{'Year':<6}{'Course':<20}{'Metric':<14}{'%':<8}{'n/d':<14}")
                print("-" * 62)
                for r in rows:
                    nd = f"{r['numerator']}/{r['denominator']}"
                    print(f"{r['cohort_year']:<6}{(r.get('course') or '-'):<20}"
                          f"{r['metric_type']:<14}{r['value_pct']:<8}{nd:<14}")
            _pause()
        elif choice == "4":
            yr = _ask_int("Year: ")
            path = input("Output CSV path: ").strip()
            if yr and path:
                n = svc.export_ofs_return(yr, path)
                print(f"\n  ✓ {n} rows → {os.path.abspath(path)}")
            _pause()
        elif choice == "5":
            yr = _ask_int("Plan year (blank = all): ")
            rows = svc.list_app_milestones(plan_year=yr)
            if not rows:
                print("\n  (no milestones)")
            else:
                print(f"\n{'ID':<5}{'Year':<6}{'Done':<6}{'Target':<10}{'Text':<40}")
                print("-" * 67)
                for r in rows:
                    print(f"{r['id']:<5}{r['plan_year']:<6}"
                          f"{('Y' if r['achieved'] else 'N'):<6}"
                          f"{str(r.get('target_value') or ''):<10}"
                          f"{(r['milestone_text'] or '')[:38]:<40}")
            _pause()
        elif choice == "6":
            yr = _ask_int("Plan year: ")
            text = input("Milestone text: ").strip()
            target = input("Target value (blank = none): ").strip()
            target_v = float(target) if target else None
            tdate = input("Target date YYYY-MM-DD (blank = none): ").strip() or None
            if yr and text:
                mid = svc.create_app_milestone(yr, text, target_value=target_v,
                                               target_date=tdate)
                print(f"\n  ✓ milestone {mid}")
            _pause()
        elif choice == "7":
            mid = _ask_int("Milestone ID: ")
            if mid:
                cur = input("Current value (blank = skip): ").strip()
                achieved = input("Mark achieved? (y/n/blank): ").strip().lower()
                fields: dict = {}
                if cur:
                    try:
                        fields["current_value"] = float(cur)
                    except ValueError:
                        pass
                if achieved == "y":
                    fields["achieved"] = 1
                elif achieved == "n":
                    fields["achieved"] = 0
                if fields and svc.update_app_milestone(mid, **fields):
                    print("\n  ✓ updated")
                else:
                    print("\n  ! nothing updated")
            _pause()
        elif choice == "8":
            rows = svc.list_protection_plans()
            if not rows:
                print("\n  (no plans)")
            else:
                print(f"\n{'Version':<12}{'From':<12}{'To':<12}")
                print("-" * 36)
                for r in rows:
                    print(f"{r['version']:<12}{r['in_force_from']:<12}"
                          f"{(r.get('in_force_to') or '-'):<12}")
            _pause()
        elif choice == "9":
            ver = input("Version label: ").strip()
            frm = input("In-force-from YYYY-MM-DD: ").strip()
            to = input("In-force-to (blank = open): ").strip() or None
            text = input("Plan text: ").strip()
            if ver and frm and text:
                pid = svc.create_protection_plan(ver, frm, text, in_force_to=to)
                print(f"\n  ✓ plan {pid}")
            _pause()


def _tef_menu() -> None:
    while True:
        _header("TEF — Provider Narratives & Indicators")
        print("  1. List narratives")
        print("  2. Add narrative version")
        print("  3. Compute TEF indicators")
        print("  4. Export TEF submission (JSON)")
        print("  0. Back")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            yr = _ask_int("Year (blank = all): ")
            rows = svc.list_tef_narratives(submission_year=yr)
            if not rows:
                print("\n  (no narratives)")
            else:
                print(f"\n{'Year':<6}{'Section':<22}{'Ver':<5}{'Excerpt':<35}")
                print("-" * 68)
                for r in rows:
                    print(f"{r['submission_year']:<6}{r['section']:<22}"
                          f"{r['version']:<5}{(r['narrative_text'] or '')[:33]:<35}")
            _pause()
        elif choice == "2":
            yr = _ask_int("Year: ")
            sec = input(f"Section {svc.TEF_SECTIONS}: ").strip()
            text = input("Narrative text: ").strip()
            if yr and sec and text:
                try:
                    nid = svc.add_tef_narrative(yr, sec, text)
                    print(f"\n  ✓ narrative {nid}")
                except ValueError as e:
                    print(f"\n  ! {e}")
            _pause()
        elif choice == "3":
            yr = _ask_int("Year (blank = current): ")
            ind = svc.compute_tef_indicators(yr)
            print()
            for k, v in ind.items():
                print(f"  {k}: {v}")
            _pause()
        elif choice == "4":
            yr = _ask_int("Year: ")
            path = input("Output JSON path: ").strip()
            if yr and path:
                n = svc.export_tef_submission(yr, path)
                print(f"\n  ✓ {n} sections → {os.path.abspath(path)}")
            _pause()


def _ref_menu() -> None:
    while True:
        _header("REF — Impact Cases, Environment & Outputs")
        print("  1. List impact cases")
        print("  2. Create impact case")
        print("  3. Update impact case status / quality rating")
        print("  4. List environment statements")
        print("  5. Add environment statement version")
        print("  6. UoA summary")
        print("  7. Export REF submission for UoA (CSV)")
        print("  0. Back")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            uoa = input("UoA (blank = all): ").strip() or None
            rows = svc.list_impact_cases(uoa=uoa)
            if not rows:
                print("\n  (no cases)")
            else:
                print(f"\n{'ID':<5}{'UoA':<8}{'Status':<14}{'Title':<40}")
                print("-" * 67)
                for r in rows:
                    print(f"{r['id']:<5}{r['uoa']:<8}{r['status']:<14}"
                          f"{(r['title'] or '')[:38]:<40}")
            _pause()
        elif choice == "2":
            uoa = input(f"UoA (e.g. one of {svc.REF_UOAS[0]}…): ").strip()
            title = input("Title: ").strip()
            summary = input("Summary (optional): ").strip() or None
            if uoa and title:
                cid = svc.create_impact_case(uoa, title, summary=summary)
                print(f"\n  ✓ case {cid}")
            _pause()
        elif choice == "3":
            cid = _ask_int("Case ID: ")
            if cid:
                status = input(f"New status {svc.REF_IMPACT_STATUSES} (blank = skip): ").strip()
                rating = input("Quality rating e.g. 4*, 3*, 2*, 1* (blank = skip): ").strip()
                fields: dict = {}
                if status:
                    fields["status"] = status
                if rating:
                    fields["quality_rating"] = rating
                if fields and svc.update_impact_case(cid, **fields):
                    print("\n  ✓ updated")
                else:
                    print("\n  ! nothing updated")
            _pause()
        elif choice == "4":
            uoa = input("UoA (blank = all): ").strip() or None
            rows = svc.list_environment_statements(uoa=uoa)
            if not rows:
                print("\n  (no statements)")
            else:
                print(f"\n{'ID':<5}{'UoA':<8}{'Ver':<5}{'Excerpt':<45}")
                print("-" * 63)
                for r in rows:
                    print(f"{r['id']:<5}{r['uoa']:<8}{r['version']:<5}"
                          f"{(r['narrative_text'] or '')[:43]:<45}")
            _pause()
        elif choice == "5":
            uoa = input("UoA: ").strip()
            text = input("Narrative text: ").strip()
            if uoa and text:
                eid = svc.add_environment_statement(uoa, text)
                print(f"\n  ✓ statement {eid}")
            _pause()
        elif choice == "6":
            uoa = input("UoA: ").strip()
            if uoa:
                s = svc.compute_uoa_summary(uoa)
                print()
                for k, v in s.items():
                    print(f"  {k}: {v}")
            _pause()
        elif choice == "7":
            uoa = input("UoA: ").strip()
            path = input("Output CSV path: ").strip()
            if uoa and path:
                n = svc.export_ref_submission(uoa, path)
                print(f"\n  ✓ {n} rows → {os.path.abspath(path)}")
            _pause()


def _kpi_menu() -> None:
    _header("External QA KPIs")
    rows = svc.compute_external_qa_kpis()
    if not rows:
        print("\n  (no KPIs computed — no underlying data yet)")
    else:
        print(f"\n{'KPI':<55}{'Value':<10}{'Target':<10}")
        print("-" * 75)
        for r in rows:
            print(f"{r['kpi_name'][:53]:<55}{r['current_value']:<10}"
                  f"{str(r.get('target_value') or '-'):<10}")
    if input("\nRecord these to KPIManager? (y/n): ").strip().lower() == "y":
        n = svc.record_external_qa_kpis()
        print(f"  ✓ recorded {n} KPI(s)")
    _pause()


def display_external_qa_menu(auth=None) -> None:
    """Top-level CLI entry — wired from menu_router."""
    svc.init_db()
    while True:
        _header("External Quality Assurance — OfS / TEF / REF")
        print("  1. Submissions tracker")
        print("  2. OfS (B3, APP, Protection plans)")
        print("  3. TEF (Narratives, indicators, export)")
        print("  4. REF (Impact, environment, outputs)")
        print("  5. KPIs")
        print("  0. Back")
        choice = input("\nSelect: ").strip()
        if choice == "0":
            return
        if choice == "1":
            _submissions_menu()
        elif choice == "2":
            _ofs_menu()
        elif choice == "3":
            _tef_menu()
        elif choice == "4":
            _ref_menu()
        elif choice == "5":
            _kpi_menu()


__all__ = ["display_external_qa_menu"]
