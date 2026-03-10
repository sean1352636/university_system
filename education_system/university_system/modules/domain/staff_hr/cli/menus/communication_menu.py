"""
Communication Menu - Staff communication and collaboration CLI.
"""

from education_system.university_system.modules.domain.staff_hr.services import CommunicationManager


def display_communication_menu(user_id: str, is_admin: bool = False) -> None:
    """Display communication and collaboration menu."""
    while True:
        print("\n" + "=" * 60)
        print("COMMUNICATION & COLLABORATION")
        print("=" * 60)

        # Show unread count
        unread = CommunicationManager.get_unread_count(user_id)
        if unread > 0:
            print(f"\nYou have {unread} unread announcement(s)")

        print("\n--- Announcements ---")
        print("  1. View Announcements")
        print("  2. Post Announcement")

        print("\n--- Committees ---")
        print("  3. My Committees")
        print("  4. Committee Directory")
        print("  5. View Meeting Minutes")

        print("\n--- Directory ---")
        print("  6. Staff Directory")
        print("  7. Search by Expertise")

        print("\n--- Noticeboard ---")
        print("  8. View Noticeboard")
        print("  9. Post Notice")

        if is_admin:
            print("\n--- Admin ---")
            print("  10. Manage Committees")
            print("  11. Moderate Announcements")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_announcements(user_id)
        elif choice == '2':
            _post_announcement(user_id)
        elif choice == '3':
            _my_committees(user_id)
        elif choice == '4':
            _committee_directory()
        elif choice == '5':
            _view_minutes()
        elif choice == '6':
            _staff_directory()
        elif choice == '7':
            _search_expertise()
        elif choice == '8':
            _view_noticeboard()
        elif choice == '9':
            _post_notice(user_id)
        elif choice == '10' and is_admin:
            _manage_committees()
        elif choice == '11' and is_admin:
            _moderate_announcements()
        else:
            print("Invalid choice.")


def _view_announcements(user_id: str) -> None:
    """View announcements."""
    announcements = CommunicationManager.get_announcements(limit=20)
    print("\n" + "-" * 60)
    print("ANNOUNCEMENTS")
    print("-" * 60)

    if announcements:
        for a in announcements:
            priority = a.get('priority', 'normal')
            priority_marker = "[!]" if priority == 'high' else "[!!]" if priority == 'urgent' else ""
            print(f"\n  {priority_marker} {a.get('title')}")
            print(f"    Posted: {a.get('posted_date', 'N/A')[:10]} by {a.get('author_name', 'N/A')}")
            print(f"    Category: {a.get('category', 'General')}")
            if a.get('content'):
                content = a.get('content', '')[:100]
                print(f"    {content}...")

        # Mark as read
        CommunicationManager.mark_announcements_read(user_id)
    else:
        print("No announcements.")

    print("-" * 60)

    view_full = input("\nView full announcement? (enter number or 0 to return): ").strip()
    if view_full and view_full != '0':
        try:
            idx = int(view_full) - 1
            if 0 <= idx < len(announcements):
                _view_full_announcement(announcements[idx])
        except ValueError:
            pass

    input("Press Enter to continue...")


def _view_full_announcement(announcement: dict) -> None:
    """View full announcement."""
    print("\n" + "=" * 60)
    print(announcement.get('title', 'No Title'))
    print("=" * 60)
    print(f"\nPosted: {announcement.get('posted_date', 'N/A')}")
    print(f"By: {announcement.get('author_name', 'N/A')}")
    print(f"Category: {announcement.get('category', 'General')}")
    print("\n" + "-" * 60)
    print(announcement.get('content', 'No content'))
    print("-" * 60)


def _post_announcement(user_id: str) -> None:
    """Post a new announcement."""
    print("\n--- Post Announcement ---")
    title = input("Title: ").strip()
    print("\nCategories: general, academic, administrative, event, urgent")
    category = input("Category: ").strip() or 'general'
    print("\nPriority: normal, high, urgent")
    priority = input("Priority: ").strip() or 'normal'
    content = input("\nContent (end with empty line):\n").strip()

    # Allow multiline input
    lines = [content]
    while True:
        line = input()
        if line == '':
            break
        lines.append(line)
    content = '\n'.join(lines)

    target_dept = input("Target Department (blank for all): ").strip()
    expiry = input("Expiry Date (YYYY-MM-DD, or blank): ").strip()

    if title and content:
        try:
            announcement_id = CommunicationManager.post_announcement(
                user_id, title, content,
                category=category,
                priority=priority,
                target_department=target_dept if target_dept else None,
                expiry_date=expiry if expiry else None
            )
            print(f"\nAnnouncement posted. ID: {announcement_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nTitle and content are required.")

    input("Press Enter to continue...")


def _my_committees(user_id: str) -> None:
    """View user's committees."""
    committees = CommunicationManager.get_user_committees(user_id)
    print("\n" + "-" * 60)
    print("MY COMMITTEES")
    print("-" * 60)

    if committees:
        for c in committees:
            print(f"\n  {c.get('name')}")
            print(f"    Role: {c.get('role', 'Member')}")
            print(f"    Type: {c.get('committee_type', 'N/A')}")
            print(f"    Status: {c.get('status', 'active')}")
            if c.get('next_meeting'):
                print(f"    Next Meeting: {c.get('next_meeting')}")
    else:
        print("You are not a member of any committees.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _committee_directory() -> None:
    """View committee directory."""
    committees = CommunicationManager.get_committees()
    print("\n" + "-" * 60)
    print("COMMITTEE DIRECTORY")
    print("-" * 60)

    if committees:
        # Group by type
        types = {}
        for c in committees:
            ctype = c.get('committee_type', 'Other')
            if ctype not in types:
                types[ctype] = []
            types[ctype].append(c)

        for ctype, clist in types.items():
            print(f"\n[{ctype}]")
            for c in clist:
                print(f"  - {c.get('name')}")
                print(f"    Chair: {c.get('chair_name', 'N/A')}")
                print(f"    Members: {c.get('member_count', 0)}")
    else:
        print("No committees found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_minutes() -> None:
    """View meeting minutes."""
    committees = CommunicationManager.get_committees()
    if not committees:
        print("\nNo committees found.")
        input("Press Enter to continue...")
        return

    print("\nSelect Committee:")
    for i, c in enumerate(committees, 1):
        print(f"  {i}. {c.get('name')}")

    try:
        choice = int(input("\nSelect (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(committees):
            committee = committees[choice - 1]
            minutes = CommunicationManager.get_meeting_minutes(committee['committee_id'])

            print("\n" + "-" * 60)
            print(f"MEETING MINUTES - {committee.get('name')}")
            print("-" * 60)

            if minutes:
                for m in minutes:
                    print(f"\n  {m.get('meeting_date', 'N/A')} - {m.get('title', 'Meeting')}")
                    print(f"    Attendees: {m.get('attendee_count', 0)}")
                    print(f"    Status: {m.get('status', 'draft')}")
                    if m.get('action_items'):
                        print(f"    Action Items: {m.get('action_items')}")
            else:
                print("No meeting minutes found.")

            print("-" * 60)
    except ValueError:
        print("Invalid input.")

    input("\nPress Enter to continue...")


def _staff_directory() -> None:
    """View staff directory."""
    print("\n--- Staff Directory ---")
    print("Search by: 1. Name  2. Department  3. Job Title")
    search_type = input("Select: ").strip()

    if search_type == '1':
        query = input("Enter name: ").strip()
        staff = CommunicationManager.search_staff(name=query)
    elif search_type == '2':
        query = input("Enter department: ").strip()
        staff = CommunicationManager.search_staff(department=query)
    elif search_type == '3':
        query = input("Enter job title: ").strip()
        staff = CommunicationManager.search_staff(job_title=query)
    else:
        staff = CommunicationManager.search_staff(limit=20)

    print("\n" + "-" * 60)
    print("STAFF DIRECTORY")
    print("-" * 60)

    if staff:
        for s in staff:
            name = f"{s.get('first_name', '')} {s.get('last_name', '')}"
            print(f"\n  {name.strip()}")
            print(f"    Department: {s.get('department', 'N/A')}")
            print(f"    Title: {s.get('job_title', 'N/A')}")
            print(f"    Email: {s.get('email', 'N/A')}")
            if s.get('phone_extension'):
                print(f"    Ext: {s.get('phone_extension')}")
            if s.get('office_location'):
                print(f"    Office: {s.get('office_location')}")
    else:
        print("No staff found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _search_expertise() -> None:
    """Search staff by expertise."""
    print("\n--- Search by Expertise ---")
    expertise = input("Enter expertise/skill: ").strip()

    if not expertise:
        print("Please enter a search term.")
        input("Press Enter to continue...")
        return

    staff = CommunicationManager.search_by_expertise(expertise)
    print("\n" + "-" * 60)
    print(f"STAFF WITH EXPERTISE: {expertise}")
    print("-" * 60)

    if staff:
        for s in staff:
            name = f"{s.get('first_name', '')} {s.get('last_name', '')}"
            print(f"\n  {name.strip()}")
            print(f"    Department: {s.get('department', 'N/A')}")
            print(f"    Skills: {s.get('skills', 'N/A')}")
            if s.get('research_areas'):
                print(f"    Research: {s.get('research_areas')}")
    else:
        print("No staff found with that expertise.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_noticeboard() -> None:
    """View noticeboard."""
    notices = CommunicationManager.get_notices()
    print("\n" + "-" * 60)
    print("STAFF NOTICEBOARD")
    print("-" * 60)

    if notices:
        for n in notices:
            category = n.get('category', 'general')
            print(f"\n  [{category.upper()}] {n.get('title')}")
            print(f"    Posted: {n.get('posted_date', 'N/A')[:10]} by {n.get('author_name', 'N/A')}")
            if n.get('content'):
                print(f"    {n.get('content')[:80]}...")
    else:
        print("No notices on the board.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _post_notice(user_id: str) -> None:
    """Post a notice."""
    print("\n--- Post Notice ---")
    print("Categories: general, for_sale, wanted, events, lost_found, carpool, other")
    category = input("Category: ").strip() or 'general'
    title = input("Title: ").strip()
    content = input("Content: ").strip()
    expiry = input("Expiry Date (YYYY-MM-DD, or blank for 30 days): ").strip()

    if title and content:
        try:
            notice_id = CommunicationManager.post_notice(
                user_id, title, content,
                category=category,
                expiry_date=expiry if expiry else None
            )
            print(f"\nNotice posted. ID: {notice_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nTitle and content are required.")

    input("Press Enter to continue...")


def _manage_committees() -> None:
    """Admin: Manage committees."""
    print("\n--- Manage Committees ---")
    print("  1. Create Committee")
    print("  2. Add Member")
    print("  3. Remove Member")
    print("  4. Update Committee")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        name = input("Committee Name: ").strip()
        ctype = input("Type (academic/administrative/governance/ad_hoc): ").strip()
        description = input("Description: ").strip()

        if name:
            try:
                committee_id = CommunicationManager.create_committee(
                    name, committee_type=ctype, description=description
                )
                print(f"\nCommittee created. ID: {committee_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '2':
        committees = CommunicationManager.get_committees()
        print("\nCommittees:")
        for i, c in enumerate(committees, 1):
            print(f"  {i}. {c.get('name')}")

        try:
            idx = int(input("\nSelect committee: ").strip()) - 1
            if 0 <= idx < len(committees):
                user_id = input("User ID to add: ").strip()
                role = input("Role (member/secretary/chair): ").strip() or 'member'
                CommunicationManager.add_committee_member(
                    committees[idx]['committee_id'], user_id, role
                )
                print("\nMember added.")
        except (ValueError, IndexError):
            print("\nInvalid selection.")

    elif choice == '3':
        committees = CommunicationManager.get_committees()
        print("\nCommittees:")
        for i, c in enumerate(committees, 1):
            print(f"  {i}. {c.get('name')}")

        try:
            idx = int(input("\nSelect committee: ").strip()) - 1
            if 0 <= idx < len(committees):
                user_id = input("User ID to remove: ").strip()
                CommunicationManager.remove_committee_member(
                    committees[idx]['committee_id'], user_id
                )
                print("\nMember removed.")
        except (ValueError, IndexError):
            print("\nInvalid selection.")

    input("Press Enter to continue...")


def _moderate_announcements() -> None:
    """Admin: Moderate announcements."""
    pending = CommunicationManager.get_pending_announcements()
    print("\n" + "-" * 60)
    print("PENDING ANNOUNCEMENTS FOR APPROVAL")
    print("-" * 60)

    if not pending:
        print("No pending announcements.")
        input("\nPress Enter to continue...")
        return

    for i, a in enumerate(pending, 1):
        print(f"\n  {i}. {a.get('title')}")
        print(f"     Author: {a.get('author_name', 'N/A')}")
        print(f"     Category: {a.get('category')}")

    print("-" * 60)

    try:
        choice = int(input("\nSelect to review (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(pending):
            announcement = pending[choice - 1]
            print(f"\n{announcement.get('content', '')[:200]}...")

            action = input("\n(A)pprove or (R)eject? ").strip().upper()
            if action == 'A':
                CommunicationManager.approve_announcement(announcement['announcement_id'])
                print("\nAnnouncement approved.")
            elif action == 'R':
                reason = input("Rejection reason: ").strip()
                CommunicationManager.reject_announcement(
                    announcement['announcement_id'], reason
                )
                print("\nAnnouncement rejected.")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")
