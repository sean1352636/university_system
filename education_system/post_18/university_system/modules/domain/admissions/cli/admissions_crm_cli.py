"""
Admissions & Recruitment CRM — interactive CLI.

Wired to the managers in ``admissions.services.admissions_crm_core``, which
read/write the shared ``student_records.db`` — the same database the Admissions
CRM GUI (``admissions_crm_gui.py``) uses. Anything created here is visible in
the GUI and vice-versa.

Covers the seven areas the old stub menu only advertised: Prospects,
Applications, Review Workflow, Document Management, Recruitment Campaigns,
Campus Tours, and Yield Prediction Analytics.
"""

from __future__ import annotations

from typing import Optional

from education_system.post_18.university_system.modules.domain.admissions.services.admissions_crm_core import (
    ProspectManager,
    ApplicationManager,
    ReviewWorkflowManager,
    CampaignManager,
    TourManager,
    YieldPredictionManager,
)


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


def _prompt_bool(text: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = input(f"{text} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


# --------------------------------------------------------------------------- #
# 1. Prospects
# --------------------------------------------------------------------------- #
def _list_prospects() -> None:
    status = _prompt("Status filter (prospect/applicant/..., blank = all)")
    search = _prompt("Search name/email (optional)")
    prospects = ProspectManager.list_prospects(status=status or None, search=search)
    if not prospects:
        print("\nNo prospects found.")
        return
    print(f"\n{'ID':<5}{'Name':<26}{'Email':<28}{'Status':<12}Major")
    print("-" * 84)
    for p in prospects:
        name = f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()
        print(f"{p['prospect_id']:<5}{name[:25]:<26}"
              f"{(p.get('email') or '')[:27]:<28}"
              f"{(p.get('status') or '')[:11]:<12}"
              f"{(p.get('intended_major') or '')[:20]}")


def _create_prospect() -> None:
    first = _prompt("First name")
    last = _prompt("Last name")
    email = _prompt("Email")
    if not first or not last or not email:
        print("First name, last name and email are required.")
        return
    phone = _prompt("Phone (optional)")
    country = _prompt("Country (optional)")
    high_school = _prompt("High school (optional)")
    major = _prompt("Intended major (optional)")
    source = _prompt("Source (optional)")
    try:
        pid = ProspectManager.create_prospect(
            first, last, email, phone=phone, country=country,
            high_school=high_school, intended_major=major, source=source)
        print(f"\n✓ Created prospect '{first} {last}' (id={pid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_prospect() -> None:
    pid = _prompt_int("Prospect id", allow_blank=False)
    prospect = ProspectManager.get_prospect(pid)
    if not prospect:
        print(f"\nNo prospect with id {pid}.")
        return
    print(f"\n--- Prospect {pid} ---")
    for key in ("first_name", "last_name", "email", "phone", "country",
                "high_school", "intended_major", "source", "status",
                "created_at", "last_contact_date"):
        print(f"  {key:<18}: {prospect.get(key) or '-'}")
    interactions = ProspectManager.get_interactions(pid)
    print(f"\n  Interactions ({len(interactions)}):")
    for i in interactions:
        print(f"    [{i.get('interaction_date') or '?'}] "
              f"{i.get('interaction_type') or ''} — "
              f"{(i.get('notes') or '')[:50]} "
              f"(by {i.get('staff_member') or '-'})")


def _update_prospect_status() -> None:
    pid = _prompt_int("Prospect id", allow_blank=False)
    status = _prompt("New status (prospect/applicant/admitted/enrolled/lost)")
    if not status:
        print("Status is required.")
        return
    try:
        ProspectManager.update_prospect_status(pid, status)
        print(f"\n✓ Updated prospect {pid} → {status}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _log_interaction(auth) -> None:
    pid = _prompt_int("Prospect id", allow_blank=False)
    itype = _prompt("Interaction type (email/call/meeting/event)", default="email")
    notes = _prompt("Notes (optional)")
    followup = _prompt("Next follow-up date (YYYY-MM-DD, optional)")
    try:
        iid = ProspectManager.log_interaction(
            pid, itype, notes=notes, staff_member=_current_username(auth),
            next_followup_date=followup)
        print(f"\n✓ Logged interaction {iid} for prospect {pid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _prospects_menu(auth) -> None:
    while True:
        _header("Manage Prospects")
        print("[1] List prospects")
        print("[2] Add prospect")
        print("[3] View prospect (+ interactions)")
        print("[4] Update prospect status")
        print("[5] Log interaction")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_prospects()
        elif choice == "2":
            _create_prospect()
        elif choice == "3":
            _view_prospect()
        elif choice == "4":
            _update_prospect_status()
        elif choice == "5":
            _log_interaction(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Applications
# --------------------------------------------------------------------------- #
def _list_applications() -> None:
    status = _prompt("Status filter (submitted/in_review.../decision_made, blank = all)")
    apps = ApplicationManager.list_applications(status=status or None)
    if not apps:
        print("\nNo applications found.")
        return
    print(f"\n{'ID':<5}{'Applicant':<24}{'Program':<22}{'Status':<18}Decision")
    print("-" * 80)
    for a in apps:
        name = f"{a.get('first_name') or ''} {a.get('last_name') or ''}".strip()
        print(f"{a['application_id']:<5}{name[:23]:<24}"
              f"{(a.get('program_applied') or '')[:21]:<22}"
              f"{(a.get('status') or '')[:17]:<18}"
              f"{a.get('decision') or '-'}")


def _submit_application() -> None:
    pid = _prompt_int("Prospect id", allow_blank=False)
    app_type = _prompt("Application type (undergraduate/postgraduate)",
                       default="undergraduate")
    program = _prompt("Program applied for")
    year = _prompt("Academic year (e.g. 2026/27)")
    semester = _prompt("Semester (e.g. Autumn)")
    if not program or not year or not semester:
        print("Program, academic year and semester are required.")
        return
    fee_paid = _prompt_bool("Application fee paid?", default=False)
    try:
        aid = ApplicationManager.submit_application(
            pid, app_type, program, year, semester, application_fee_paid=fee_paid)
        print(f"\n✓ Submitted application {aid} for prospect {pid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_application() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    app = ApplicationManager.get_application(aid)
    if not app:
        print(f"\nNo application with id {aid}.")
        return
    name = f"{app.get('first_name') or ''} {app.get('last_name') or ''}".strip()
    print(f"\n--- Application {aid} ---")
    print(f"  Applicant   : {name} <{app.get('email') or '-'}>")
    for key in ("application_type", "program_applied", "academic_year",
                "semester", "status", "decision", "decision_date",
                "application_fee_paid", "enrollment_confirmed",
                "submission_date"):
        print(f"  {key:<20}: {app.get(key) if app.get(key) is not None else '-'}")
    reviews = ReviewWorkflowManager.get_application_reviews(aid)
    print(f"\n  Reviews ({len(reviews)}):")
    for r in reviews:
        print(f"    #{r.get('review_id')} stage={r.get('review_stage')} "
              f"score={r.get('score')} rec={r.get('recommendation') or '-'} "
              f"by {r.get('reviewer_id')}")


def _update_application_status() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    status = _prompt("New status")
    if not status:
        print("Status is required.")
        return
    try:
        ApplicationManager.update_application_status(aid, status)
        print(f"\n✓ Updated application {aid} → {status}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _make_decision() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    decision = _prompt("Decision (accept/reject/waitlist/defer)")
    if not decision:
        print("Decision is required.")
        return
    try:
        ApplicationManager.make_decision(aid, decision)
        print(f"\n✓ Recorded decision '{decision}' for application {aid}.")
        print("  (An applicant notification email was attempted — best-effort.)")
    except Exception as e:
        print(f"\n✗ {e}")


def _applications_menu(auth) -> None:
    while True:
        _header("Applications")
        print("[1] List applications")
        print("[2] Submit application")
        print("[3] View application (+ reviews)")
        print("[4] Update application status")
        print("[5] Make decision")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_applications()
        elif choice == "2":
            _submit_application()
        elif choice == "3":
            _view_application()
        elif choice == "4":
            _update_application_status()
        elif choice == "5":
            _make_decision()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Review Workflow
# --------------------------------------------------------------------------- #
def _assign_reviewer(auth) -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    reviewer = _prompt("Reviewer id", default=_current_username(auth))
    stage = _prompt("Review stage (initial/committee/final)", default="initial")
    try:
        rid = ReviewWorkflowManager.assign_reviewer(aid, reviewer, stage)
        print(f"\n✓ Assigned {reviewer} to application {aid} (review id={rid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _create_review(auth) -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    reviewer = _prompt("Reviewer id", default=_current_username(auth))
    stage = _prompt("Review stage (initial/committee/final)", default="initial")
    score = _prompt_int("Score (0-100, optional)")
    recommendation = _prompt("Recommendation (accept/reject/waitlist)")
    comments = _prompt("Comments (optional)")
    try:
        rid = ReviewWorkflowManager.create_review(
            aid, reviewer, stage, score, recommendation, comments)
        print(f"\n✓ Recorded review {rid} for application {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_reviews() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    reviews = ReviewWorkflowManager.get_application_reviews(aid)
    if not reviews:
        print(f"\nNo reviews for application {aid}.")
        return
    print(f"\n{'ID':<5}{'Stage':<14}{'Score':<7}{'Recommend':<14}Reviewer")
    print("-" * 55)
    for r in reviews:
        print(f"{r.get('review_id'):<5}{(r.get('review_stage') or '')[:13]:<14}"
              f"{r.get('score') if r.get('score') is not None else '-':<7}"
              f"{(r.get('recommendation') or '')[:13]:<14}"
              f"{r.get('reviewer_id') or ''}")


def _review_menu(auth) -> None:
    while True:
        _header("Application Review Workflow")
        print("[1] Assign reviewer")
        print("[2] Create/submit review")
        print("[3] View reviews for an application")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _assign_reviewer(auth)
        elif choice == "2":
            _create_review(auth)
        elif choice == "3":
            _view_reviews()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Document Management
# --------------------------------------------------------------------------- #
def _upload_document() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    doc_type = _prompt("Document type (transcript/reference/personal_statement)")
    doc_name = _prompt("Document name / filename")
    file_url = _prompt("File path or URL")
    if not doc_type or not doc_name or not file_url:
        print("Document type, name and file path are required.")
        return
    try:
        did = ApplicationManager.upload_document(aid, doc_type, doc_name, file_url)
        print(f"\n✓ Attached document {did} to application {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _documents_menu(auth) -> None:
    while True:
        _header("Document Management")
        print("[1] Upload document for an application")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _upload_document()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 5. Recruitment Campaigns
# --------------------------------------------------------------------------- #
def _list_campaigns() -> None:
    campaigns = CampaignManager.list_campaigns()
    if not campaigns:
        print("\nNo campaigns found.")
        return
    print(f"\n{'ID':<5}{'Name':<26}{'Type':<14}{'Status':<10}Sent")
    print("-" * 62)
    for c in campaigns:
        print(f"{c['campaign_id']:<5}{(c.get('campaign_name') or '')[:25]:<26}"
              f"{(c.get('campaign_type') or '')[:13]:<14}"
              f"{(c.get('status') or '')[:9]:<10}"
              f"{c.get('sent_count') if c.get('sent_count') is not None else 0}")


def _create_campaign() -> None:
    name = _prompt("Campaign name")
    ctype = _prompt("Campaign type (email/sms/event)", default="email")
    audience = _prompt("Target audience (e.g. undergraduate prospects)")
    start = _prompt("Start date (YYYY-MM-DD)")
    end = _prompt("End date (YYYY-MM-DD)")
    template = _prompt("Message template / body")
    if not name or not audience:
        print("Campaign name and target audience are required.")
        return
    try:
        cid = CampaignManager.create_campaign(
            name, ctype, audience, start, end, template)
        print(f"\n✓ Created campaign '{name}' (id={cid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _send_campaign_message() -> None:
    cid = _prompt_int("Campaign id", allow_blank=False)
    pid = _prompt_int("Prospect id", allow_blank=False)
    try:
        mid = CampaignManager.send_campaign_message(cid, pid)
        print(f"\n✓ Recorded campaign message {mid} (campaign {cid} → prospect {pid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _campaigns_menu(auth) -> None:
    while True:
        _header("Recruitment Campaigns")
        print("[1] List campaigns")
        print("[2] Create campaign")
        print("[3] Send campaign message to a prospect")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_campaigns()
        elif choice == "2":
            _create_campaign()
        elif choice == "3":
            _send_campaign_message()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 6. Campus Tours
# --------------------------------------------------------------------------- #
def _list_tours() -> None:
    upcoming = _prompt_bool("Only upcoming tours?", default=True)
    tours = TourManager.list_tours(upcoming_only=upcoming)
    if not tours:
        print("\nNo tours found.")
        return
    print(f"\n{'ID':<5}{'Date':<12}{'Time':<8}{'Guide':<16}{'Attend':<12}Status")
    print("-" * 62)
    for t in tours:
        attend = f"{t.get('current_attendees', 0)}/{t.get('max_attendees', 0)}"
        print(f"{t['tour_id']:<5}{(t.get('tour_date') or '')[:11]:<12}"
              f"{(t.get('tour_time') or '')[:7]:<8}"
              f"{(t.get('tour_guide') or '-')[:15]:<16}"
              f"{attend:<12}{t.get('status') or ''}")


def _create_tour() -> None:
    date = _prompt("Tour date (YYYY-MM-DD)")
    time = _prompt("Tour time (HH:MM)")
    if not date or not time:
        print("Date and time are required.")
        return
    guide = _prompt("Tour guide (optional)")
    max_att = _prompt_int("Max attendees (default 20)") or 20
    meeting = _prompt("Meeting point (optional)")
    duration = _prompt_int("Duration minutes (default 90)") or 90
    try:
        tid = TourManager.create_tour(
            date, time, tour_guide=guide, max_attendees=max_att,
            meeting_point=meeting, duration_minutes=duration)
        print(f"\n✓ Scheduled tour {tid} on {date} {time}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _register_for_tour() -> None:
    tid = _prompt_int("Tour id", allow_blank=False)
    pid = _prompt_int("Prospect id", allow_blank=False)
    guests = _prompt_int("Number of guests (default 0)") or 0
    try:
        rid = TourManager.register_for_tour(tid, pid, num_guests=guests)
        print(f"\n✓ Registered prospect {pid} for tour {tid} (reg id={rid}).")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_tour_registrations() -> None:
    tid = _prompt_int("Tour id", allow_blank=False)
    regs = TourManager.get_tour_registrations(tid)
    if not regs:
        print(f"\nNo registrations for tour {tid}.")
        return
    print(f"\n{'RegID':<7}{'Prospect':<24}{'Guests':<8}Registered")
    print("-" * 55)
    for r in regs:
        name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
        print(f"{r.get('registration_id'):<7}{name[:23]:<24}"
              f"{r.get('num_guests') if r.get('num_guests') is not None else 0:<8}"
              f"{(r.get('registered_at') or '')[:19]}")


def _tours_menu(auth) -> None:
    while True:
        _header("Campus Tours")
        print("[1] List tours")
        print("[2] Schedule tour")
        print("[3] Register a prospect for a tour")
        print("[4] View tour registrations")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_tours()
        elif choice == "2":
            _create_tour()
        elif choice == "3":
            _register_for_tour()
        elif choice == "4":
            _view_tour_registrations()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 7. Yield Prediction Analytics
# --------------------------------------------------------------------------- #
def _create_prediction() -> None:
    aid = _prompt_int("Application id", allow_blank=False)
    prob = _prompt_float("Predicted enrollment probability (0.0-1.0)",
                         allow_blank=False)
    model = _prompt("Model version", default="manual-1.0")
    factors = _prompt("Factors / notes (optional)")
    try:
        pid = YieldPredictionManager.create_prediction(aid, prob, model, factors)
        print(f"\n✓ Recorded yield prediction {pid} for application {aid}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_predictions() -> None:
    aid = _prompt_int("Application id (blank = all)")
    predictions = YieldPredictionManager.list_predictions(application_id=aid)
    if not predictions:
        print("\nNo predictions found.")
        return
    print(f"\n{'ID':<5}{'App':<6}{'Probability':<13}{'Model':<16}Date")
    print("-" * 58)
    for p in predictions:
        prob = p.get('predicted_enrollment_probability')
        prob_str = f"{prob:.1%}" if prob is not None else "-"
        print(f"{p['prediction_id']:<5}{p.get('application_id'):<6}"
              f"{prob_str:<13}{(p.get('model_version') or '')[:15]:<16}"
              f"{(p.get('prediction_date') or '')[:10]}")


def _yield_menu(auth) -> None:
    while True:
        _header("Yield Prediction Analytics")
        print("[1] Record a prediction")
        print("[2] View predictions")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _create_prediction()
        elif choice == "2":
            _view_predictions()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_admissions_crm_menu(auth) -> None:
    """Run the Admissions & Recruitment CRM CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("    ADMISSIONS & RECRUITMENT CRM")
        print("=" * 50)
        print("1. Manage Prospects")
        print("2. Applications")
        print("3. Application Review Workflow")
        print("4. Document Management")
        print("5. Recruitment Campaigns")
        print("6. Campus Tours")
        print("7. Yield Prediction Analytics")
        print("8. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-8): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _prospects_menu(auth)
            elif choice == "2":
                _applications_menu(auth)
            elif choice == "3":
                _review_menu(auth)
            elif choice == "4":
                _documents_menu(auth)
            elif choice == "5":
                _campaigns_menu(auth)
            elif choice == "6":
                _tours_menu(auth)
            elif choice == "7":
                _yield_menu(auth)
            elif choice == "8":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
