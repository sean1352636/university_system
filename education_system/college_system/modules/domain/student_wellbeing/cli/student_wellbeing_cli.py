"""Student Wellbeing CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.student_wellbeing.services.student_wellbeing_service import (
    StudentWellbeingService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def student_wellbeing_menu(auth: UserAuth):
    """Student Wellbeing management menu."""
    svc = StudentWellbeingService(auth._db_path)

    while True:
        print_header("Student Wellbeing")
        options = [
            ("1", "List Referrals"),
            ("2", "View Referral"),
            ("3", "New Referral"),
            ("4", "Update Referral"),
            ("5", "Resolve Referral"),
            ("6", "Delete Referral"),
            ("7", "High Risk Students"),
            ("8", "List Wellbeing Logs"),
            ("9", "New Log"),
            ("A", "Update Log"),
            ("B", "List Counselling Sessions"),
            ("C", "New Session"),
            ("D", "Update Session"),
            ("E", "Student Wellbeing Summary"),
            ("F", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_referrals(svc)
        elif choice == "2":
            _view_referral(svc)
        elif choice == "3":
            _new_referral(svc, auth)
        elif choice == "4":
            _update_referral(svc)
        elif choice == "5":
            _resolve_referral(svc)
        elif choice == "6":
            _delete_referral(svc)
        elif choice == "7":
            _high_risk_students(svc)
        elif choice == "8":
            _list_logs(svc)
        elif choice == "9":
            _new_log(svc, auth)
        elif choice == "A":
            _update_log(svc)
        elif choice == "B":
            _list_sessions(svc)
        elif choice == "C":
            _new_session(svc)
        elif choice == "D":
            _update_session(svc)
        elif choice == "E":
            _student_summary(svc)
        elif choice == "F":
            _show_stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


# ================================================================
# Referrals
# ================================================================

def _list_referrals(svc):
    print_header("Wellbeing Referrals")
    try:
        status_f = input("  Filter by status (open/in_progress/referred_externally/resolved/closed) [all]: ").strip() or None
        risk_f = input("  Filter by risk level (low/medium/high/critical) [all]: ").strip() or None
        cat_f = input("  Filter by category [all]: ").strip() or None

        items = svc.list_referrals(status=status_f, risk_level=risk_f, concern_category=cat_f)
        if not items:
            print("\n  No referrals found.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Type':<10} {'Category':<15} {'Risk':<10} {'Status'}")
        print(f"  {'-'*70}")
        for r in items:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r['student_id'])
            print(f"  {r['id']:<5} {name:<20} {r.get('referral_type', ''):<10} "
                  f"{r.get('concern_category', '') or '':<15} {r.get('risk_level', ''):<10} "
                  f"{r.get('status', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_referral(svc):
    print_header("View Referral")
    try:
        rid = int(input("  Referral ID: ").strip())
        r = svc.get_referral(rid)
        if not r:
            print("\n  Referral not found.")
            return
        name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or "N/A"
        print(f"\n  ID:                 {r['id']}")
        print(f"  Student:            {name} (ID: {r['student_id']})")
        print(f"  Type:               {r.get('referral_type', '')}")
        print(f"  Category:           {r.get('concern_category', '') or ''}")
        print(f"  Risk Level:         {r.get('risk_level', '')}")
        print(f"  Status:             {r.get('status', '')}")
        print(f"  Service Referred:   {r.get('service_referred_to', '') or ''}")
        print(f"  External Agency:    {r.get('external_agency', '') or ''}")
        print(f"  Consent Obtained:   {'Yes' if r.get('consent_obtained') else 'No'}")
        print(f"  Appointment Date:   {r.get('appointment_date', '') or ''}")
        print(f"  Outcome:            {r.get('outcome', '') or ''}")
        print(f"  Created:            {r.get('created_at', '')}")
        print(f"  Updated:            {r.get('updated_at', '') or ''}")
        print(f"\n  Concern Details:\n  {r.get('concern_details', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_referral(svc, auth):
    print_header("New Referral")
    try:
        student_id = int(input("  Student PK: ").strip())
        concern_details = input("  Concern Details: ").strip()
        if not concern_details:
            print("\n  Concern details are required.")
            return
        referral_type = input("  Type (internal/external/self) [internal]: ").strip() or None
        concern_category = input("  Category (anxiety/depression/family/bullying/financial/housing/"
                                 "substance/bereavement/eating_disorder/self_harm/other): ").strip() or None
        risk_level = input("  Risk Level (low/medium/high/critical) [low]: ").strip() or None
        service = input("  Service Referred To: ").strip() or None
        agency = input("  External Agency: ").strip() or None
        consent = input("  Consent Obtained (y/n) [n]: ").strip().lower()
        appointment = input("  Appointment Date (YYYY-MM-DD): ").strip() or None

        kwargs = {}
        if referral_type:
            kwargs["referral_type"] = referral_type
        if concern_category:
            kwargs["concern_category"] = concern_category
        if risk_level:
            kwargs["risk_level"] = risk_level
        if service:
            kwargs["service_referred_to"] = service
        if agency:
            kwargs["external_agency"] = agency
        if consent == "y":
            kwargs["consent_obtained"] = 1
        if appointment:
            kwargs["appointment_date"] = appointment
        kwargs["referred_by"] = auth.current_user.get("user_id")

        item = svc.create_referral(student_id, concern_details, **kwargs)
        print(f"\n  Referral created (ID: {item['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_referral(svc):
    print_header("Update Referral")
    try:
        rid = int(input("  Referral ID: ").strip())
        print("  (Leave blank to keep current)")
        referral_type = input("  Type (internal/external/self): ").strip() or None
        concern_category = input("  Category: ").strip() or None
        risk_level = input("  Risk Level (low/medium/high/critical): ").strip() or None
        status = input("  Status (open/in_progress/referred_externally/resolved/closed): ").strip() or None
        service = input("  Service Referred To: ").strip() or None
        agency = input("  External Agency: ").strip() or None
        appointment = input("  Appointment Date (YYYY-MM-DD): ").strip() or None

        updates = {}
        if referral_type:
            updates["referral_type"] = referral_type
        if concern_category:
            updates["concern_category"] = concern_category
        if risk_level:
            updates["risk_level"] = risk_level
        if status:
            updates["status"] = status
        if service:
            updates["service_referred_to"] = service
        if agency:
            updates["external_agency"] = agency
        if appointment:
            updates["appointment_date"] = appointment

        item = svc.update_referral(rid, **updates)
        print(f"\n  Referral {item['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _resolve_referral(svc):
    print_header("Resolve Referral")
    try:
        rid = int(input("  Referral ID: ").strip())
        outcome = input("  Outcome: ").strip()
        if not outcome:
            print("\n  Outcome is required.")
            return
        svc.resolve_referral(rid, outcome)
        print("\n  Referral resolved.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_referral(svc):
    try:
        rid = int(input("  Referral ID: ").strip())
        confirm = input(f"  Delete referral #{rid}? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_referral(rid)
        print("\n  Referral deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _high_risk_students(svc):
    print_header("High Risk Students")
    try:
        items = svc.get_high_risk_students()
        if not items:
            print("\n  No high-risk students found.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Category':<15} {'Risk':<10} {'Status'}")
        print(f"  {'-'*60}")
        for r in items:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r['student_id'])
            print(f"  {r['id']:<5} {name:<20} {r.get('concern_category', '') or '':<15} "
                  f"{r.get('risk_level', ''):<10} {r.get('status', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Wellbeing Logs
# ================================================================

def _list_logs(svc):
    print_header("Wellbeing Logs")
    try:
        sid_str = input("  Filter by Student PK [all]: ").strip()
        sid = int(sid_str) if sid_str else None
        fu_str = input("  Follow-up needed (y/n) [all]: ").strip().lower()
        fu = None
        if fu_str == "y":
            fu = 1
        elif fu_str == "n":
            fu = 0

        items = svc.list_logs(student_id=sid, follow_up_needed=fu)
        if not items:
            print("\n  No logs found.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Date':<12} {'Mood':<6} {'Anxiety':<8} {'Sleep':<10} {'Follow Up'}")
        print(f"  {'-'*75}")
        for l in items:
            name = f"{l.get('first_name', '')} {l.get('last_name', '')}".strip() or str(l['student_id'])
            fu_text = "Yes" if l.get("follow_up_needed") else "No"
            print(f"  {l['id']:<5} {name:<20} {l.get('log_date', ''):<12} "
                  f"{str(l.get('mood_rating', '') or '-'):<6} "
                  f"{str(l.get('anxiety_level', '') or '-'):<8} "
                  f"{l.get('sleep_quality', '') or '-':<10} {fu_text}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_log(svc, auth):
    print_header("New Wellbeing Log")
    try:
        student_id = int(input("  Student PK: ").strip())
        log_date = input("  Log Date (YYYY-MM-DD) [today]: ").strip() or None
        mood = input("  Mood Rating (1-10): ").strip()
        anxiety = input("  Anxiety Level (1-10): ").strip()
        sleep = input("  Sleep Quality (poor/fair/good/excellent): ").strip() or None
        notes = input("  Notes: ").strip() or None
        fu = input("  Follow-up Needed (y/n) [n]: ").strip().lower()

        kwargs = {}
        if log_date:
            kwargs["log_date"] = log_date
        if mood:
            kwargs["mood_rating"] = int(mood)
        if anxiety:
            kwargs["anxiety_level"] = int(anxiety)
        if sleep:
            kwargs["sleep_quality"] = sleep
        if notes:
            kwargs["notes"] = notes
        kwargs["follow_up_needed"] = 1 if fu == "y" else 0
        kwargs["logged_by"] = auth.current_user.get("user_id")

        item = svc.create_log(student_id, **kwargs)
        print(f"\n  Wellbeing log created (ID: {item['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_log(svc):
    print_header("Update Wellbeing Log")
    try:
        lid = int(input("  Log ID: ").strip())
        print("  (Leave blank to keep current)")
        mood = input("  Mood Rating (1-10): ").strip()
        anxiety = input("  Anxiety Level (1-10): ").strip()
        sleep = input("  Sleep Quality (poor/fair/good/excellent): ").strip() or None
        notes = input("  Notes: ").strip() or None
        fu = input("  Follow-up Needed (y/n): ").strip().lower()

        updates = {}
        if mood:
            updates["mood_rating"] = int(mood)
        if anxiety:
            updates["anxiety_level"] = int(anxiety)
        if sleep:
            updates["sleep_quality"] = sleep
        if notes:
            updates["notes"] = notes
        if fu in ("y", "n"):
            updates["follow_up_needed"] = 1 if fu == "y" else 0

        item = svc.update_log(lid, **updates)
        print(f"\n  Log {item['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Counselling Sessions
# ================================================================

def _list_sessions(svc):
    print_header("Counselling Sessions")
    try:
        status_f = input("  Filter by status (scheduled/completed/cancelled/no_show) [all]: ").strip() or None
        type_f = input("  Filter by type (individual/group/crisis/drop_in) [all]: ").strip() or None

        items = svc.list_sessions(status=status_f, session_type=type_f)
        if not items:
            print("\n  No sessions found.")
            return
        print(f"\n  {'ID':<5} {'Student':<20} {'Counsellor':<10} {'Date':<12} {'#':<4} {'Type':<12} {'Status'}")
        print(f"  {'-'*75}")
        for s in items:
            name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or str(s['student_id'])
            print(f"  {s['id']:<5} {name:<20} {str(s.get('counsellor_id', '') or '-'):<10} "
                  f"{s.get('session_date', ''):<12} {s.get('session_number', 1):<4} "
                  f"{s.get('session_type', ''):<12} {s.get('status', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_session(svc):
    print_header("New Counselling Session")
    try:
        student_id = int(input("  Student PK: ").strip())
        session_date = input("  Session Date (YYYY-MM-DD): ").strip()
        if not session_date:
            print("\n  Session date is required.")
            return
        counsellor_id = input("  Counsellor ID: ").strip()
        session_number = input("  Session Number [1]: ").strip()
        session_type = input("  Type (individual/group/crisis/drop_in) [individual]: ").strip() or None
        presenting = input("  Presenting Issues: ").strip() or None
        notes = input("  Session Notes: ").strip() or None
        risk = input("  Risk Assessment: ").strip() or None
        next_appt = input("  Next Appointment (YYYY-MM-DD): ").strip() or None
        status = input("  Status (scheduled/completed/cancelled/no_show) [completed]: ").strip() or None

        kwargs = {}
        if counsellor_id:
            kwargs["counsellor_id"] = int(counsellor_id)
        if session_number:
            kwargs["session_number"] = int(session_number)
        if session_type:
            kwargs["session_type"] = session_type
        if presenting:
            kwargs["presenting_issues"] = presenting
        if notes:
            kwargs["session_notes"] = notes
        if risk:
            kwargs["risk_assessment"] = risk
        if next_appt:
            kwargs["next_appointment"] = next_appt
        if status:
            kwargs["status"] = status

        item = svc.create_session(student_id, session_date, **kwargs)
        print(f"\n  Session created (ID: {item['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_session(svc):
    print_header("Update Counselling Session")
    try:
        sid = int(input("  Session ID: ").strip())
        print("  (Leave blank to keep current)")
        session_date = input("  Session Date (YYYY-MM-DD): ").strip() or None
        session_type = input("  Type (individual/group/crisis/drop_in): ").strip() or None
        status = input("  Status (scheduled/completed/cancelled/no_show): ").strip() or None
        notes = input("  Session Notes: ").strip() or None
        risk = input("  Risk Assessment: ").strip() or None
        next_appt = input("  Next Appointment (YYYY-MM-DD): ").strip() or None

        updates = {}
        if session_date:
            updates["session_date"] = session_date
        if session_type:
            updates["session_type"] = session_type
        if status:
            updates["status"] = status
        if notes:
            updates["session_notes"] = notes
        if risk:
            updates["risk_assessment"] = risk
        if next_appt:
            updates["next_appointment"] = next_appt

        item = svc.update_session(sid, **updates)
        print(f"\n  Session {item['id']} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Reporting
# ================================================================

def _student_summary(svc):
    print_header("Student Wellbeing Summary")
    try:
        student_id = int(input("  Student PK: ").strip())
        data = svc.get_student_wellbeing(student_id)

        print(f"\n  Student: {data['student_name']} (ID: {data['student_id']})")
        print(f"  Total Referrals: {data['total_referrals']}  (Open: {data['open_referrals']})")
        print(f"  Total Wellbeing Logs: {data['total_logs']}")
        print(f"  Total Counselling Sessions: {data['total_sessions']}")

        if data["referrals"]:
            print(f"\n  --- Referrals ---")
            for r in data["referrals"]:
                print(f"  [{r['id']}] {r.get('concern_category', '') or 'N/A'} - "
                      f"{r.get('risk_level', '')} - {r.get('status', '')}")

        if data["logs"]:
            print(f"\n  --- Recent Logs ---")
            for l in data["logs"][:5]:
                mood = l.get("mood_rating", "-") or "-"
                print(f"  [{l['id']}] {l.get('log_date', '')} - Mood: {mood} - "
                      f"Follow-up: {'Yes' if l.get('follow_up_needed') else 'No'}")

        if data["sessions"]:
            print(f"\n  --- Sessions ---")
            for s in data["sessions"]:
                print(f"  [{s['id']}] {s.get('session_date', '')} - "
                      f"{s.get('session_type', '')} - {s.get('status', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _show_stats(svc):
    print_header("Wellbeing Statistics")
    try:
        stats = svc.get_stats()

        print("\n  === Referrals ===")
        print(f"  Total Referrals:    {stats['total_referrals']}")
        print(f"  Open Referrals:     {stats['open_referrals']}")
        print(f"  High Risk Count:    {stats['high_risk_count']}")

        if stats["by_status"]:
            print(f"\n  By Status:")
            for k, v in stats["by_status"].items():
                print(f"    {k:<25} {v}")

        if stats["by_risk_level"]:
            print(f"\n  By Risk Level:")
            for k, v in stats["by_risk_level"].items():
                print(f"    {k:<25} {v}")

        if stats["by_category"]:
            print(f"\n  By Category:")
            for k, v in stats["by_category"].items():
                print(f"    {k:<25} {v}")

        print("\n  === Wellbeing Logs ===")
        print(f"  Total Logs:         {stats['total_logs']}")
        print(f"  Follow-ups Needed:  {stats['follow_ups_needed']}")
        print(f"  Average Mood:       {stats['avg_mood']}")

        print("\n  === Counselling Sessions ===")
        print(f"  Total Sessions:     {stats['total_sessions']}")

        if stats["by_session_type"]:
            print(f"\n  By Session Type:")
            for k, v in stats["by_session_type"].items():
                print(f"    {k:<25} {v}")
    except Exception as e:
        print(f"\n  Error: {e}")
