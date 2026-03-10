"""Student Council CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.student_council.services.student_council_service import (
    StudentCouncilService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def student_council_menu(auth: UserAuth):
    """Student Council management menu."""
    svc = StudentCouncilService(auth._db_path)

    while True:
        print_header("Student Council")
        options = [
            ("1", "List Members"),
            ("2", "View Member"),
            ("3", "New Member"),
            ("4", "Update Member"),
            ("5", "End Term"),
            ("6", "Delete Member"),
            ("7", "List Meetings"),
            ("8", "New Meeting"),
            ("9", "Complete Meeting"),
            ("A", "List Proposals"),
            ("B", "New Proposal"),
            ("C", "Record Votes"),
            ("D", "Management Response"),
            ("E", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_members(svc)
        elif choice == "2":
            _view_member(svc)
        elif choice == "3":
            _new_member(svc)
        elif choice == "4":
            _update_member(svc)
        elif choice == "5":
            _end_term(svc)
        elif choice == "6":
            _delete_member(svc)
        elif choice == "7":
            _list_meetings(svc)
        elif choice == "8":
            _new_meeting(svc)
        elif choice == "9":
            _complete_meeting(svc)
        elif choice == "A":
            _list_proposals(svc)
        elif choice == "B":
            _new_proposal(svc)
        elif choice == "C":
            _record_votes(svc)
        elif choice == "D":
            _management_response(svc)
        elif choice == "E":
            _statistics(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


# ── Members ──

def _list_members(svc):
    print_header("Council Members")
    try:
        status = input("  Filter by status (active/resigned/removed/term_ended) [all]: ").strip() or None
        role = input("  Filter by role (representative/chair/vice_chair/secretary/treasurer/welfare_officer) [all]: ").strip() or None
        members = svc.list_members(status=status, role=role)
        if not members:
            print("\n  No members found.")
            return
        print(f"\n  {'ID':<5} {'Student':<8} {'Name':<20} {'Role':<15} {'Year':<8} {'Dept':<12} {'Status'}")
        print(f"  {'-'*75}")
        for m in members:
            name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "-"
            print(f"  {m['id']:<5} {m['student_id']:<8} {name:<20} {m['role']:<15} "
                  f"{(m.get('year_group') or '-'):<8} {(m.get('department') or '-'):<12} {m['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_member(svc):
    try:
        member_id = int(input("  Member ID: ").strip())
        m = svc.get_member(member_id)
        if not m:
            print("\n  Member not found.")
            return
        name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or "N/A"
        print(f"\n  ID:           {m['id']}")
        print(f"  Student ID:   {m['student_id']}")
        print(f"  Name:         {name}")
        print(f"  Role:         {m['role']}")
        print(f"  Year Group:   {m.get('year_group') or 'N/A'}")
        print(f"  Department:   {m.get('department') or 'N/A'}")
        print(f"  Elected:      {m.get('elected_date') or 'N/A'}")
        print(f"  Term End:     {m.get('term_end_date') or 'N/A'}")
        print(f"  Status:       {m['status']}")
        print(f"  Created:      {m.get('created_at') or 'N/A'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_member(svc):
    print_header("New Council Member")
    try:
        student_id = int(input("  Student PK: ").strip())
        role = input("  Role (representative/chair/vice_chair/secretary/treasurer/welfare_officer) [representative]: ").strip() or "representative"
        year_group = input("  Year Group: ").strip() or None
        department = input("  Department: ").strip() or None
        elected_date = input("  Elected Date (YYYY-MM-DD): ").strip() or None
        term_end_date = input("  Term End Date (YYYY-MM-DD): ").strip() or None

        member = svc.create_member(student_id, role=role, year_group=year_group,
                                   department=department, elected_date=elected_date,
                                   term_end_date=term_end_date)
        print(f"\n  Member created (ID: {member['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_member(svc):
    print_header("Update Council Member")
    try:
        member_id = int(input("  Member ID: ").strip())
        m = svc.get_member(member_id)
        if not m:
            print("\n  Member not found.")
            return
        print(f"  Current role: {m['role']}, status: {m['status']}")
        print("  Press Enter to keep current values.\n")

        role = input(f"  Role [{m['role']}]: ").strip() or None
        year_group = input(f"  Year Group [{m.get('year_group') or ''}]: ").strip() or None
        department = input(f"  Department [{m.get('department') or ''}]: ").strip() or None
        status = input(f"  Status [{m['status']}]: ").strip() or None

        updates = {}
        if role:
            updates["role"] = role
        if year_group:
            updates["year_group"] = year_group
        if department:
            updates["department"] = department
        if status:
            updates["status"] = status

        if not updates:
            print("\n  No changes made.")
            return

        svc.update_member(member_id, **updates)
        print("\n  Member updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _end_term(svc):
    try:
        member_id = int(input("  Member ID: ").strip())
        svc.end_term(member_id)
        print("\n  Term ended.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_member(svc):
    try:
        member_id = int(input("  Member ID: ").strip())
        confirm = input(f"  Delete member #{member_id}? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_member(member_id)
        print("\n  Member deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Meetings ──

def _list_meetings(svc):
    print_header("Council Meetings")
    try:
        status = input("  Filter by status (scheduled/completed/cancelled) [all]: ").strip() or None
        meetings = svc.list_meetings(status=status)
        if not meetings:
            print("\n  No meetings found.")
            return
        print(f"\n  {'ID':<5} {'Date':<12} {'Chair':<20} {'Status':<12} {'Agenda'}")
        print(f"  {'-'*70}")
        for m in meetings:
            chair = ""
            if m.get("chair_first_name"):
                chair = f"{m['chair_first_name']} {m['chair_last_name']}"
            agenda = (m.get("agenda") or "-")[:40]
            print(f"  {m['id']:<5} {m['meeting_date']:<12} {(chair or '-'):<20} "
                  f"{m['status']:<12} {agenda}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_meeting(svc):
    print_header("New Council Meeting")
    try:
        meeting_date = input("  Meeting Date (YYYY-MM-DD): ").strip()
        if not meeting_date:
            print("\n  Date is required.")
            return
        chair_str = input("  Chair Member ID (optional): ").strip()
        chair_id = int(chair_str) if chair_str else None
        agenda = input("  Agenda: ").strip() or None

        meeting = svc.create_meeting(meeting_date, chair_id=chair_id, agenda=agenda)
        print(f"\n  Meeting created (ID: {meeting['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_meeting(svc):
    print_header("Complete Meeting")
    try:
        meeting_id = int(input("  Meeting ID: ").strip())
        minutes = input("  Minutes: ").strip()
        if not minutes:
            print("\n  Minutes are required.")
            return
        attendees = input("  Attendees (comma-separated): ").strip()
        if not attendees:
            print("\n  Attendees are required.")
            return

        svc.complete_meeting(meeting_id, minutes, attendees)
        print("\n  Meeting completed.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Proposals ──

def _list_proposals(svc):
    print_header("Council Proposals")
    try:
        category = input("  Filter by category (general/facilities/welfare/academic/social/environmental/financial) [all]: ").strip() or None
        impl_status = input("  Filter by status (pending/approved/rejected/in_progress/implemented/deferred) [all]: ").strip() or None
        proposals = svc.list_proposals(category=category, implementation_status=impl_status)
        if not proposals:
            print("\n  No proposals found.")
            return
        print(f"\n  {'ID':<5} {'Title':<25} {'Proposed By':<18} {'Category':<12} "
              f"{'For':<5} {'Against':<8} {'Outcome':<12} {'Impl. Status'}")
        print(f"  {'-'*95}")
        for p in proposals:
            proposer = ""
            if p.get("proposer_first_name"):
                proposer = f"{p['proposer_first_name']} {p['proposer_last_name']}"
            print(f"  {p['id']:<5} {p['title'][:24]:<25} {(proposer or '-'):<18} "
                  f"{p['category']:<12} {p['vote_for']:<5} {p['vote_against']:<8} "
                  f"{(p.get('outcome') or '-'):<12} {p['implementation_status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_proposal(svc):
    print_header("New Proposal")
    try:
        title = input("  Title: ").strip()
        if not title:
            print("\n  Title is required.")
            return
        by_str = input("  Proposed By (Member ID, optional): ").strip()
        proposed_by = int(by_str) if by_str else None
        mtg_str = input("  Meeting ID (optional): ").strip()
        meeting_id = int(mtg_str) if mtg_str else None
        category = input("  Category (general/facilities/welfare/academic/social/environmental/financial) [general]: ").strip() or "general"
        description = input("  Description: ").strip() or None

        proposal = svc.create_proposal(title, proposed_by=proposed_by,
                                        meeting_id=meeting_id, description=description,
                                        category=category)
        print(f"\n  Proposal created (ID: {proposal['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_votes(svc):
    print_header("Record Votes")
    try:
        proposal_id = int(input("  Proposal ID: ").strip())
        vote_for = int(input("  Votes For: ").strip() or "0")
        vote_against = int(input("  Votes Against: ").strip() or "0")
        vote_abstain = int(input("  Votes Abstain: ").strip() or "0")
        outcome = input("  Outcome: ").strip()
        if not outcome:
            print("\n  Outcome is required.")
            return

        svc.record_votes(proposal_id, vote_for, vote_against, vote_abstain, outcome)
        print("\n  Votes recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _management_response(svc):
    print_header("Management Response")
    try:
        proposal_id = int(input("  Proposal ID: ").strip())
        response = input("  Management Response: ").strip()
        if not response:
            print("\n  Response is required.")
            return
        impl_status = input("  Implementation Status (pending/approved/rejected/in_progress/implemented/deferred) [pending]: ").strip() or "pending"

        svc.respond_to_proposal(proposal_id, response, impl_status)
        print("\n  Response recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ──

def _statistics(svc):
    print_header("Student Council Statistics")
    try:
        stats = svc.get_stats()

        print(f"\n  --- Members ---")
        print(f"  Total Members:    {stats['total_members']}")
        print(f"  Active Members:   {stats['active_members']}")
        if stats["by_role"]:
            print(f"  By Role:")
            for role, count in stats["by_role"].items():
                print(f"    {role}: {count}")

        print(f"\n  --- Meetings ---")
        print(f"  Total Meetings:     {stats['total_meetings']}")
        print(f"  Completed Meetings: {stats['completed_meetings']}")

        print(f"\n  --- Proposals ---")
        print(f"  Total Proposals:    {stats['total_proposals']}")
        print(f"  Implemented:        {stats['proposals_implemented']}")
        if stats["by_category"]:
            print(f"  By Category:")
            for cat, count in stats["by_category"].items():
                print(f"    {cat}: {count}")
        if stats["by_implementation_status"]:
            print(f"  By Implementation Status:")
            for status, count in stats["by_implementation_status"].items():
                print(f"    {status}: {count}")
    except Exception as e:
        print(f"\n  Error: {e}")
