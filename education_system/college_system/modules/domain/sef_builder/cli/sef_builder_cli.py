"""Ofsted SEF Builder CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.sef_builder.services.sef_builder_service import SEFBuilderService
from education_system.college_system.infrastructure.auth.core import UserAuth


def sef_builder_menu(auth: UserAuth):
    """Ofsted SEF Builder management menu."""
    svc = SEFBuilderService(auth._db_path)

    while True:
        print_header("Ofsted SEF Builder")
        options = [
            ("1", "List SEF Documents"),
            ("2", "Create New SEF"),
            ("3", "View SEF Details"),
            ("4", "Update SEF"),
            ("5", "Add Judgement Area"),
            ("6", "View Judgement Areas"),
            ("7", "Update Judgement Area"),
            ("8", "Add Evidence Link"),
            ("9", "View Evidence"),
            ("10", "Remove Evidence"),
            ("11", "Pull System Data"),
            ("12", "Approve SEF"),
            ("13", "Export SEF"),
            ("14", "SEF Summary"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_sefs(svc)
        elif choice == "2":
            _create_sef(svc)
        elif choice == "3":
            _view_sef(svc)
        elif choice == "4":
            _update_sef(svc)
        elif choice == "5":
            _add_judgement_area(svc)
        elif choice == "6":
            _view_judgement_areas(svc)
        elif choice == "7":
            _update_judgement_area(svc)
        elif choice == "8":
            _add_evidence(svc)
        elif choice == "9":
            _view_evidence(svc)
        elif choice == "10":
            _remove_evidence(svc)
        elif choice == "11":
            _pull_system_data(svc)
        elif choice == "12":
            _approve_sef(svc)
        elif choice == "13":
            _export_sef(svc)
        elif choice == "14":
            _sef_summary(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_sefs(svc):
    print_header("SEF Documents")
    try:
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        sefs = svc.list_sefs(academic_year=ay)
        if not sefs:
            print("\n  No SEF documents found.")
            return
        print(f"\n  {'ID':<5} {'Year':<12} {'Title':<25} {'Version':<8} {'Overall':<22} {'Status'}")
        print(f"  {'-'*80}")
        for s in sefs:
            print(f"  {s['id']:<5} {(s.get('academic_year') or '-'):<12} "
                  f"{(s.get('title') or '-'):<25} {(s.get('version') or '1.0'):<8} "
                  f"{(s.get('overall_effectiveness') or '-'):<22} {(s.get('status') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_sef(svc):
    print_header("Create New SEF")
    try:
        ay = input("  Academic year: ").strip()
        title = input("  Title: ").strip()
        cby = input("  Created by (user ID, blank=none): ").strip()
        cby = int(cby) if cby else None
        result = svc.create_sef(ay, title, cby)
        print(f"\n  SEF created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_sef(svc):
    print_header("SEF Details")
    try:
        sid = int(input("  SEF ID: ").strip())
        s = svc.get_sef(sid)
        print(f"\n  ID:                    {s['id']}")
        print(f"  Academic Year:         {s.get('academic_year', '-')}")
        print(f"  Title:                 {s.get('title', '-')}")
        print(f"  Version:               {s.get('version', '1.0')}")
        print(f"  Overall Effectiveness: {s.get('overall_effectiveness') or '-'}")
        print(f"  Status:                {s.get('status', '-')}")
        print(f"  Created By:            {s.get('created_by') or '-'}")
        print(f"  Approved By:           {s.get('approved_by') or '-'}")
        print(f"  Approved Date:         {s.get('approved_date') or '-'}")
        print(f"  Created:               {s.get('created_at', '-')}")
        print(f"  Updated:               {s.get('updated_at', '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_sef(svc):
    print_header("Update SEF")
    try:
        sid = int(input("  SEF ID: ").strip())
        print("  (Leave blank to keep current value)")
        title = input("  Title: ").strip() or None
        version = input("  Version: ").strip() or None
        overall = input("  Overall effectiveness (outstanding/good/requires_improvement/inadequate): ").strip() or None
        updates = {}
        if title:
            updates["title"] = title
        if version:
            updates["version"] = version
        if overall:
            updates["overall_effectiveness"] = overall
        if not updates:
            print("\n  No changes provided.")
            return
        svc.update_sef(sid, **updates)
        print(f"\n  SEF {sid} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_judgement_area(svc):
    print_header("Add Judgement Area")
    try:
        sid = int(input("  SEF ID: ").strip())
        name = input("  Area name: ").strip()
        num = input("  Area number: ").strip()
        grade = input("  Self grade (outstanding/good/requires_improvement/inadequate, blank=none): ").strip() or None
        result = svc.add_judgement_area(sid, name, num, self_grade=grade)
        print(f"\n  Judgement area added (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_judgement_areas(svc):
    print_header("Judgement Areas")
    try:
        sid = int(input("  SEF ID: ").strip())
        areas = svc.list_judgement_areas(sid)
        if not areas:
            print("\n  No judgement areas found.")
            return
        print(f"\n  {'ID':<5} {'#':<5} {'Area Name':<30} {'Grade':<22} {'Narrative'}")
        print(f"  {'-'*80}")
        for a in areas:
            narrative = (a.get('narrative') or '-')
            if len(narrative) > 20:
                narrative = narrative[:17] + "..."
            print(f"  {a['id']:<5} {(a.get('area_number') or '-'):<5} "
                  f"{(a.get('area_name') or '-'):<30} "
                  f"{(a.get('self_grade') or '-'):<22} {narrative}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_judgement_area(svc):
    print_header("Update Judgement Area")
    try:
        aid = int(input("  Judgement area ID: ").strip())
        print("  (Leave blank to keep current value)")
        narrative = input("  Narrative: ").strip() or None
        strengths = input("  Strengths: ").strip() or None
        afi = input("  Areas for improvement: ").strip() or None
        actions = input("  Key actions: ").strip() or None
        grade = input("  Self grade (outstanding/good/requires_improvement/inadequate): ").strip() or None
        updates = {}
        if narrative:
            updates["narrative"] = narrative
        if strengths:
            updates["strengths"] = strengths
        if afi:
            updates["areas_for_improvement"] = afi
        if actions:
            updates["key_actions"] = actions
        if grade:
            updates["self_grade"] = grade
        if not updates:
            print("\n  No changes provided.")
            return
        svc.update_judgement_area(aid, **updates)
        print(f"\n  Judgement area {aid} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_evidence(svc):
    print_header("Add Evidence Link")
    try:
        aid = int(input("  Judgement area ID: ").strip())
        etype = input("  Evidence type (data/document/observation/survey/outcome/external): ").strip()
        desc = input("  Description: ").strip()
        source = input("  Data source (blank=none): ").strip() or None
        value = input("  Data value (blank=none): ").strip() or None
        result = svc.add_evidence_link(aid, etype, desc, data_source=source, data_value=value)
        print(f"\n  Evidence linked (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_evidence(svc):
    print_header("Evidence Links")
    try:
        aid = int(input("  Judgement area ID: ").strip())
        evidence = svc.list_evidence(aid)
        if not evidence:
            print("\n  No evidence found for this area.")
            return
        print(f"\n  {'ID':<5} {'Type':<14} {'Description':<35} {'Source':<16} {'Value'}")
        print(f"  {'-'*80}")
        for ev in evidence:
            desc = (ev.get('evidence_description') or '-')
            if len(desc) > 33:
                desc = desc[:30] + "..."
            print(f"  {ev['id']:<5} {(ev.get('evidence_type') or '-'):<14} "
                  f"{desc:<35} {(ev.get('data_source') or '-'):<16} "
                  f"{(ev.get('data_value') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _remove_evidence(svc):
    print_header("Remove Evidence")
    try:
        eid = int(input("  Evidence ID: ").strip())
        svc.remove_evidence(eid)
        print(f"\n  Evidence {eid} removed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _pull_system_data(svc):
    print_header("Pull System Data")
    try:
        sid = int(input("  SEF ID: ").strip())
        count = svc.pull_system_data(sid)
        print(f"\n  Pulled {count} evidence items from system data.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _approve_sef(svc):
    print_header("Approve SEF")
    try:
        sid = int(input("  SEF ID: ").strip())
        aby = input("  Approved by (user ID): ").strip()
        aby = int(aby) if aby else None
        svc.approve_sef(sid, aby)
        print(f"\n  SEF {sid} approved.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _export_sef(svc):
    print_header("Export SEF")
    try:
        sid = int(input("  SEF ID: ").strip())
        data = svc.export_sef(sid)
        print(f"\n  SEF: {data.get('title', '-')} (v{data.get('version', '1.0')})")
        print(f"  Year: {data.get('academic_year', '-')}")
        print(f"  Status: {data.get('status', '-')}")
        print(f"  Overall Effectiveness: {data.get('overall_effectiveness') or '-'}")
        areas = data.get('judgement_areas', [])
        if areas:
            print(f"\n  Judgement Areas ({len(areas)}):")
            print(f"  {'-'*70}")
            for a in areas:
                print(f"\n  {a.get('area_number', '-')}. {a.get('area_name', '-')} [{a.get('self_grade') or 'ungraded'}]")
                if a.get('narrative'):
                    print(f"     Narrative:  {a['narrative'][:60]}{'...' if len(a.get('narrative', '')) > 60 else ''}")
                if a.get('strengths'):
                    print(f"     Strengths:  {a['strengths'][:60]}{'...' if len(a.get('strengths', '')) > 60 else ''}")
                if a.get('areas_for_improvement'):
                    print(f"     AFI:        {a['areas_for_improvement'][:60]}{'...' if len(a.get('areas_for_improvement', '')) > 60 else ''}")
                if a.get('key_actions'):
                    print(f"     Actions:    {a['key_actions'][:60]}{'...' if len(a.get('key_actions', '')) > 60 else ''}")
                ev = a.get('evidence', [])
                if ev:
                    print(f"     Evidence ({len(ev)}):")
                    for e in ev:
                        print(f"       - [{e.get('evidence_type', '-')}] {e.get('evidence_description', '-')}")
        else:
            print("\n  No judgement areas defined.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _sef_summary(svc):
    print_header("SEF Summary")
    try:
        sid = int(input("  SEF ID: ").strip())
        summary = svc.get_sef_summary(sid)
        print(f"\n  SEF ID:                {summary['sef_id']}")
        print(f"  Title:                 {summary['title']}")
        print(f"  Version:               {summary['version']}")
        print(f"  Status:                {summary['status']}")
        print(f"  Overall Effectiveness: {summary.get('overall_effectiveness') or '-'}")
        print(f"  Total Areas:           {summary['total_areas']}")
        print(f"  Total Evidence Links:  {summary['total_evidence_links']}")
        grade_dist = summary.get('grade_distribution', {})
        if grade_dist:
            print(f"\n  Grade Distribution:")
            for grade, count in grade_dist.items():
                print(f"    {grade:<22} {count}")
    except Exception as e:
        print(f"\n  Error: {e}")
