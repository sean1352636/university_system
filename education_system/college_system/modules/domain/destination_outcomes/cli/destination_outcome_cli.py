"""Destination Outcome Tracking CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.destination_outcomes.services.destination_outcome_service import DestinationOutcomeService
from education_system.college_system.infrastructure.auth.core import UserAuth


def destination_outcome_menu(auth: UserAuth):
    """Destination Outcome Tracking management menu."""
    svc = DestinationOutcomeService(auth._db_path)

    while True:
        print_header("Destination Outcome Tracking")
        options = [
            ("1", "List Outcomes"),
            ("2", "Record New Outcome"),
            ("3", "Update Outcome"),
            ("4", "Verify Outcome"),
            ("5", "Mark Sustained"),
            ("6", "NEET Rate Report"),
            ("7", "Employment Statistics"),
            ("8", "University Progression Stats"),
            ("9", "Full Outcome Summary"),
            ("10", "Create Survey"),
            ("11", "List Surveys"),
            ("12", "Record Survey Response"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_outcomes(svc)
        elif choice == "2":
            _record_outcome(svc)
        elif choice == "3":
            _update_outcome(svc)
        elif choice == "4":
            _verify_outcome(svc)
        elif choice == "5":
            _mark_sustained(svc)
        elif choice == "6":
            _neet_rate(svc)
        elif choice == "7":
            _employment_stats(svc)
        elif choice == "8":
            _university_progression(svc)
        elif choice == "9":
            _outcome_summary(svc)
        elif choice == "10":
            _create_survey(svc)
        elif choice == "11":
            _list_surveys(svc)
        elif choice == "12":
            _record_survey_response(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_outcomes(svc):
    print_header("All Outcomes")
    try:
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        outcomes = svc.list_outcomes(academic_year=ay)
        if not outcomes:
            print("\n  No outcomes found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Year':<12} {'Type':<18} {'Institution/Employer':<22} {'Verified':<9} {'Sustained'}")
        print(f"  {'-'*90}")
        for o in outcomes:
            inst = o.get('institution_name') or o.get('employer_name') or '-'
            if len(inst) > 20:
                inst = inst[:17] + "..."
            verified = "Yes" if o.get('verified') else "No"
            sustained = ""
            if o.get('sustained_at_6m'):
                sustained = "6m"
            elif o.get('sustained_at_3m'):
                sustained = "3m"
            else:
                sustained = "-"
            print(f"  {o['id']:<5} {o['student_id']:<8} {(o.get('academic_year') or '-'):<12} "
                  f"{(o.get('outcome_type') or '-'):<18} {inst:<22} {verified:<9} {sustained}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_outcome(svc):
    print_header("Record New Outcome")
    try:
        sid = int(input("  Student ID: ").strip())
        ay = input("  Academic year: ").strip()
        ot = input("  Outcome type (university/apprenticeship/employment/further_education/gap_year/neet/unknown/volunteering): ").strip()
        inst = input("  Institution name (blank=none): ").strip() or None
        course = input("  Course title (blank=none): ").strip() or None
        employer = input("  Employer name (blank=none): ").strip() or None
        job = input("  Job title (blank=none): ").strip() or None
        notes = input("  Notes (blank=none): ").strip() or None
        result = svc.record_outcome(
            sid, ay, ot,
            institution_name=inst, course_title=course,
            employer_name=employer, job_title=job, notes=notes,
        )
        print(f"\n  Outcome recorded (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_outcome(svc):
    print_header("Update Outcome")
    try:
        oid = int(input("  Outcome ID: ").strip())
        print("  (Leave blank to keep current value)")
        ot = input("  Outcome type: ").strip() or None
        inst = input("  Institution name: ").strip() or None
        employer = input("  Employer name: ").strip() or None
        job = input("  Job title: ").strip() or None
        notes = input("  Notes: ").strip() or None
        updates = {}
        if ot:
            updates["outcome_type"] = ot
        if inst:
            updates["institution_name"] = inst
        if employer:
            updates["employer_name"] = employer
        if job:
            updates["job_title"] = job
        if notes:
            updates["notes"] = notes
        if not updates:
            print("\n  No changes provided.")
            return
        svc.update_outcome(oid, **updates)
        print(f"\n  Outcome {oid} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _verify_outcome(svc):
    print_header("Verify Outcome")
    try:
        oid = int(input("  Outcome ID: ").strip())
        vby = input("  Verified by (user ID): ").strip()
        vby = int(vby) if vby else None
        svc.verify_outcome(oid, vby)
        print(f"\n  Outcome {oid} verified.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _mark_sustained(svc):
    print_header("Mark Sustained")
    try:
        oid = int(input("  Outcome ID: ").strip())
        months = input("  Months (3 or 6): ").strip()
        months = int(months)
        svc.mark_sustained(oid, months)
        print(f"\n  Outcome {oid} marked sustained at {months} months.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _neet_rate(svc):
    print_header("NEET Rate Report")
    try:
        ay = input("  Academic year: ").strip()
        stats = svc.get_neet_rate(ay)
        print(f"\n  Academic Year:  {ay}")
        print(f"  Total Leavers:  {stats['total']}")
        print(f"  NEET Count:     {stats['neet_count']}")
        print(f"  NEET Rate:      {stats['rate']:.1f}%")
    except Exception as e:
        print(f"\n  Error: {e}")


def _employment_stats(svc):
    print_header("Employment Statistics")
    try:
        ay = input("  Academic year: ").strip()
        stats = svc.get_employment_stats(ay)
        print(f"\n  Academic Year:      {ay}")
        print(f"  Total Leavers:      {stats['total']}")
        print(f"  Employed:           {stats['employed']}")
        print(f"  Apprenticeships:    {stats['apprenticeships']}")
        print(f"  Employment Rate:    {stats['employment_rate']:.1f}%")
        print(f"  Sustained (6m):     {stats['sustained_6m']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _university_progression(svc):
    print_header("University Progression Stats")
    try:
        ay = input("  Academic year: ").strip()
        stats = svc.get_university_progression(ay)
        print(f"\n  Academic Year:      {ay}")
        print(f"  Total Leavers:      {stats['total']}")
        print(f"  University Count:   {stats['university_count']}")
        print(f"  Progression Rate:   {stats['progression_rate']:.1f}%")
        top = stats.get('top_institutions', [])
        if top:
            print(f"\n  Top Institutions:")
            print(f"  {'Institution':<35} {'Count'}")
            print(f"  {'-'*42}")
            for t in top:
                print(f"  {t['institution']:<35} {t['count']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _outcome_summary(svc):
    print_header("Full Outcome Summary")
    try:
        ay = input("  Academic year: ").strip()
        summary = svc.get_outcome_summary(ay)
        print(f"\n  Academic Year:  {summary['academic_year']}")
        print(f"  Total Outcomes: {summary['total']}")
        breakdown = summary.get('breakdown', {})
        percentages = summary.get('percentages', {})
        if breakdown:
            print(f"\n  {'Outcome Type':<22} {'Count':<8} {'%'}")
            print(f"  {'-'*38}")
            for otype, count in breakdown.items():
                pct = percentages.get(otype, 0)
                print(f"  {otype:<22} {count:<8} {pct:.1f}%")
        else:
            print("\n  No outcomes recorded for this year.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_survey(svc):
    print_header("Create Survey")
    try:
        sid = int(input("  Student ID: ").strip())
        ay = input("  Academic year: ").strip()
        st = input("  Survey type (3_month/6_month/12_month): ").strip()
        result = svc.create_survey(sid, ay, st)
        print(f"\n  Survey created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_surveys(svc):
    print_header("Surveys")
    try:
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        st = input("  Filter by survey type (blank=all): ").strip() or None
        surveys = svc.list_surveys(academic_year=ay, survey_type=st)
        if not surveys:
            print("\n  No surveys found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Year':<12} {'Type':<12} {'Sent':<12} {'Response':<12} {'Rating'}")
        print(f"  {'-'*75}")
        for s in surveys:
            rating = str(s.get('satisfaction_rating')) if s.get('satisfaction_rating') is not None else '-'
            print(f"  {s['id']:<5} {(s.get('student_id') or '-'):<8} "
                  f"{(s.get('academic_year') or '-'):<12} {(s.get('survey_type') or '-'):<12} "
                  f"{(s.get('sent_date') or '-'):<12} {(s.get('response_date') or '-'):<12} {rating}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_survey_response(svc):
    print_header("Record Survey Response")
    try:
        survey_id = int(input("  Survey ID: ").strip())
        status = input("  Current status: ").strip()
        satisfaction = int(input("  Satisfaction rating (1-5): ").strip())
        recommend_input = input("  Would recommend? (y/n): ").strip().lower()
        recommend = recommend_input in ("y", "yes", "1", "true")
        comments = input("  Comments (blank=none): ").strip() or None
        svc.record_survey_response(survey_id, status, satisfaction, recommend, comments)
        print(f"\n  Survey response recorded for survey {survey_id}.")
    except Exception as e:
        print(f"\n  Error: {e}")
