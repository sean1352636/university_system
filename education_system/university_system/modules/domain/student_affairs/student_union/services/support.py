from __future__ import annotations

import random
import string
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.student_affairs.student_union.services import context as ctx
from education_system.university_system.modules.domain.student_affairs.student_union.services.union_context import auto_award_points

def manage_peer_support_system():
    """Main peer support system interface"""

    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access peer support.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        while True:
            print(f"\nPeer Support System")
            print("1. Browse support groups")
            print("2. Join a support group")
            print("3. My support groups")
            print("4. Create support group")
            print("5. Anonymous matching")
            print("6. Wellness resources")

            if ctx.auth.check_permission('manage_union_reps') or ctx.auth.check_permission('manage_all_clubs'):
                print("7. Manage support groups")
                print("8. Support group reports")
                print("9. Return to main menu")
                max_option = 9
            else:
                print("7. Return to main menu")
                max_option = 7

            choice = input("Choose an option: ").strip()

            if choice == '1':
                browse_support_groups(cursor)
            elif choice == '2':
                join_support_group(student_id, cursor, conn)
            elif choice == '3':
                view_my_support_groups(student_id, cursor)
            elif choice == '4':
                create_support_group(student_id, cursor, conn)
            elif choice == '5':
                anonymous_peer_matching(student_id, cursor, conn)
            elif choice == '6':
                view_wellness_resources()
            elif choice == '7' and max_option > 7:
                manage_support_groups_admin(cursor, conn)
            elif choice == '8' and max_option > 7:
                generate_support_reports(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def browse_support_groups(cursor):
    """Browse available support groups"""
    try:
        cursor.execute('''
        SELECT g.group_id, g.group_name, g.description, g.support_type,
               s.first_name, s.last_name, g.current_members, g.max_members,
               g.meeting_schedule, g.status
        FROM peer_support_groups g
        LEFT JOIN students s ON g.facilitator_id = s.student_id
        WHERE g.status = 'active' AND g.current_members < g.max_members
        ORDER BY g.support_type, g.group_name
        ''')

        groups = cursor.fetchall()

        if not groups:
            print("No support groups currently available.")
            return

        print(f"\nAvailable Support Groups:")
        print("=" * 50)

        current_type = ""
        for group in groups:
            if group[3] != current_type:
                current_type = group[3]
                print(f"\n--- {current_type.upper()} SUPPORT ---")

            facilitator = f"{group[4]} {group[5]}" if group[4] else "TBD"
            print(f"\nID: {group[0]}")
            print(f"Name: {group[1]}")
            print(f"Description: {group[2]}")
            print(f"Facilitator: {facilitator}")
            print(f"Members: {group[6]}/{group[7]}")
            print(f"Meeting Schedule: {group[8]}")
            print("-" * 40)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def join_support_group(student_id, cursor, conn):
    """Join a support group"""
    try:
        # First browse available groups
        browse_support_groups(cursor)

        group_id = input("\nEnter group ID to join: ").strip()
        if not group_id.isdigit():
            print("Invalid group ID.")
            return

        group_id = int(group_id)

        # Check if group exists and has space
        cursor.execute('''
        SELECT group_name, current_members, max_members, status
        FROM peer_support_groups
        WHERE group_id = ?
        ''', (group_id,))

        group = cursor.fetchone()

        if not group:
            print("Support group not found.")
            return

        if group[3] != 'active':
            print("This support group is not currently active.")
            return

        if group[1] >= group[2]:
            print("This support group is full.")
            return

        # Check if already a member
        cursor.execute('''
        SELECT COUNT(*) FROM support_group_members
        WHERE group_id = ? AND student_id = ? AND status = 'active'
        ''', (group_id, student_id))

        if cursor.fetchone()[0] > 0:
            print("You are already a member of this support group.")
            return

        print(f"Joining support group: {group[0]}")
        print("\nPlease note:")
        print("- All discussions in support groups are confidential")
        print("- Respect and support all group members")
        print("- Regular attendance is encouraged")

        confirm = input("\nDo you agree to these guidelines? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Support group join cancelled.")
            return

        # Generate anonymous ID for the group
        import random
        import string
        anonymous_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        join_date = datetime.now().strftime('%Y-%m-%d')

        # Add to group
        cursor.execute('''
        INSERT INTO support_group_members (
            group_id, student_id, join_date, anonymous_id, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (group_id, student_id, join_date, anonymous_id, 'active'))

        # Update member count
        cursor.execute('''
        UPDATE peer_support_groups
        SET current_members = current_members + 1
        WHERE group_id = ?
        ''', (group_id,))

        conn.commit()

        print(f"Successfully joined {group[0]}!")
        print(f"Your anonymous ID for this group: {anonymous_id}")
        print("Please remember this ID for group communications.")

        # Award points for joining
        auto_award_points(student_id, "Peer Support", 20,
                        f"Joined support group: {group[0]}", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_my_support_groups(student_id, cursor):
    """View support groups the student is a member of"""
    try:
        cursor.execute('''
        SELECT g.group_name, g.support_type, m.join_date, m.anonymous_id,
               g.meeting_schedule, s.first_name, s.last_name
        FROM support_group_members m
        JOIN peer_support_groups g ON m.group_id = g.group_id
        LEFT JOIN students s ON g.facilitator_id = s.student_id
        WHERE m.student_id = ? AND m.status = 'active'
        ORDER BY m.join_date DESC
        ''', (student_id,))

        groups = cursor.fetchall()

        if not groups:
            print("You are not a member of any support groups.")
            return

        print(f"\nYour Support Groups:")
        print("=" * 40)

        for group in groups:
            facilitator = f"{group[5]} {group[6]}" if group[5] else "TBD"
            print(f"\nGroup: {group[0]}")
            print(f"Type: {group[1]}")
            print(f"Joined: {group[2]}")
            print(f"Your Anonymous ID: {group[3]}")
            print(f"Meeting Schedule: {group[4]}")
            print(f"Facilitator: {facilitator}")
            print("-" * 30)

        print(f"\nRemember:")
        print("- Use your anonymous ID when communicating in groups")
        print("- Maintain confidentiality of all group discussions")
        print("- Contact your facilitator if you need support")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_support_group(student_id, cursor, conn):
    """Create a new support group"""
    try:
        print(f"\nCreate New Support Group")
        print("=" * 30)

        group_name = input("Group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.")
            return

        description = input("Group description: ").strip()
        if not description:
            print("Description cannot be empty.")
            return

        support_types = [
            "Academic Stress", "Social Anxiety", "General Wellness",
            "Grief & Loss", "Relationship Issues", "Career Concerns",
            "Identity & Self-Esteem", "Addiction Recovery", "Other"
        ]

        print(f"\nSupport types:")
        for i, stype in enumerate(support_types):
            print(f"{i+1}. {stype}")

        type_choice = input("Select support type (enter number): ").strip()
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(support_types):
            support_type = support_types[int(type_choice)-1]
        else:
            support_type = input("Enter custom support type: ").strip()

        try:
            max_members = int(input("Maximum group size (recommended 6-12): ").strip())
            if max_members < 3 or max_members > 20:
                print("Group size should be between 3 and 20 members.")
                return
        except ValueError:
            print("Invalid number format.")
            return

        meeting_schedule = input("Meeting schedule (e.g., 'Tuesdays 6pm', 'Bi-weekly Fridays'): ").strip()

        created_date = datetime.now().strftime('%Y-%m-%d')

        # Create the group
        cursor.execute('''
        INSERT INTO peer_support_groups (
            group_name, description, support_type, facilitator_id,
            max_members, current_members, meeting_schedule, status, created_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            group_name, description, support_type, student_id,
            max_members, 1, meeting_schedule, 'active', created_date
        ))

        group_id = cursor.lastrowid

        # Add creator as first member
        anonymous_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        cursor.execute('''
        INSERT INTO support_group_members (
            group_id, student_id, join_date, anonymous_id, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (group_id, student_id, created_date, anonymous_id, 'active'))

        conn.commit()

        print(f"Support group '{group_name}' created successfully!")
        print(f"Group ID: {group_id}")
        print(f"Your facilitator anonymous ID: {anonymous_id}")
        print("\nAs the facilitator, you can:")
        print("- Guide group discussions")
        print("- Welcome new members")
        print("- Ensure a safe and supportive environment")

        # Award points for creating group
        auto_award_points(student_id, "Peer Support", 50,
                        f"Created support group: {group_name}", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def anonymous_peer_matching(student_id, cursor, conn):
    """Anonymous peer matching for one-on-one support"""
    try:
        print(f"\nAnonymous Peer Support Matching")
        print("=" * 40)
        print("This feature connects you with a peer for confidential, one-on-one support.")
        print("Both parties remain anonymous unless you choose to reveal your identity.")

        # Check if already in a matching process
        # This would require additional tables for matching queue and sessions
        # For now, showing the concept

        support_areas = [
            "Academic pressure", "Social anxiety", "Homesickness",
            "Relationship concerns", "Family issues", "Financial stress",
            "Career uncertainty", "Health concerns", "General wellness"
        ]

        print(f"\nWhat type of support are you seeking?")
        for i, area in enumerate(support_areas):
            print(f"{i+1}. {area}")

        area_choice = input("Select area (enter number): ").strip()
        if area_choice.isdigit() and 1 <= int(area_choice) <= len(support_areas):
            selected_area = support_areas[int(area_choice)-1]
        else:
            print("Invalid selection.")
            return

        print(f"\nYou've selected: {selected_area}")
        print("You will be matched with someone who can provide peer support in this area.")
        print("Both of you will be given anonymous contact methods.")

        # In a real implementation, this would:
        # 1. Add to matching queue
        # 2. Find compatible peers
        # 3. Create secure anonymous communication channel
        # 4. Set up check-in protocols

        confirm = input("Would you like to join the matching queue? (y/n): ").strip().lower()
        if confirm == 'y':
            print("You have been added to the anonymous peer support matching queue.")
            print("You will be contacted within 24 hours if a suitable match is found.")
            print("In the meantime, please review our crisis resources if you need immediate support.")

            # Award points for seeking support
            auto_award_points(student_id, "Peer Support", 10,
                            "Sought anonymous peer support", cursor, conn)

    except Exception as e:
        print(f"An error occurred: {e}")

def view_wellness_resources():
    """Display wellness and crisis intervention resources"""
    try:
        print(f"\nWellness Resources")
        print("=" * 20)

        print("CRISIS RESOURCES (24/7):")
        print("- Emergency Services: 999")
        print("- Samaritans: 116 123 (free)")
        print("- Crisis Text Line: Text SHOUT to 85258")
        print("- NHS 111: 111")

        print(f"\nUNIVERSITY SUPPORT:")
        print("- Student Counselling Service: ext. 3456")
        print("- Student Union Advice Centre: ext. 2890")
        print("- Mental Health First Aid Team: ext. 4567")
        print("- Disability Services: ext. 3344")

        print(f"\nONLINE RESOURCES:")
        print("- Mind: www.mind.org.uk")
        print("- Young Minds: www.youngminds.org.uk")
        print("- Student Minds: www.studentminds.org.uk")
        print("- Headspace (meditation app)")

        print(f"\nSELF-CARE ACTIVITIES:")
        print("- Campus gym and sports facilities")
        print("- Mindfulness sessions (Wednesdays 4pm)")
        print("- Study skills workshops")
        print("- Peer support circles")
        print("- Art therapy sessions")

        print(f"\nREMEMBER:")
        print("- It's okay to ask for help")
        print("- Your mental health matters")
        print("- You are not alone")
        print("- Professional support is available")

    except Exception as e:
        print(f"An error occurred: {e}")

def manage_academic_support():
    """Main academic support system interface"""

    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access academic support.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        while True:
            print(f"\nAcademic Support System")
            print("1. Study groups")
            print("2. Peer tutoring")
            print("3. Shared resources")
            print("4. Exam preparation")
            print("5. Academic workshops")
            print("6. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                manage_study_groups(student_id, cursor, conn)
            elif choice == '2':
                manage_peer_tutoring(student_id, cursor, conn)
            elif choice == '3':
                manage_shared_resources(student_id, cursor, conn)
            elif choice == '4':
                exam_preparation_groups(student_id, cursor, conn)
            elif choice == '5':
                view_academic_workshops(cursor)
            elif choice == '6':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_study_groups(student_id, cursor, conn):
    """Manage study groups"""
    try:
        while True:
            print(f"\nStudy Groups")
            print("1. Browse study groups")
            print("2. Create study group")
            print("3. Join study group")
            print("4. My study groups")
            print("5. Return to academic support")

            choice = input("Choose option: ").strip()

            if choice == '1':
                # Browse study groups
                cursor.execute('''
                SELECT sg.study_group_id, sg.subject, sg.topic, sg.organizer_id,
                       s.first_name, s.last_name, sg.current_members, sg.max_members,
                       sg.meeting_time, sg.location, sg.study_date, sg.status
                FROM study_groups sg
                JOIN students s ON sg.organizer_id = s.student_id
                WHERE sg.status = 'open' AND sg.study_date >= date('now')
                ORDER BY sg.subject, sg.study_date
                ''')

                groups = cursor.fetchall()

                if not groups:
                    print("No open study groups found.")
                    continue

                print(f"\nAvailable Study Groups:")
                print(f"{'ID':<6} {'Subject':<15} {'Topic':<20} {'Organizer':<20} {'Date':<12} {'Members':<10}")
                print("-" * 90)

                for group in groups:
                    organizer = f"{group[4]} {group[5]}"
                    members = f"{group[6]}/{group[7]}"
                    print(f"{group[0]:<6} {group[1]:<15} {group[2][:20]:<20} {organizer[:20]:<20} {group[10]:<12} {members:<10}")

            elif choice == '2':
                # Create study group
                subject = input("Subject: ").strip()
                if not subject:
                    print("Subject cannot be empty.")
                    continue

                topic = input("Specific topic: ").strip()
                meeting_time = input("Meeting time (e.g., '2pm-4pm'): ").strip()
                location = input("Location: ").strip()
                study_date = input("Study date (YYYY-MM-DD): ").strip()

                try:
                    datetime.strptime(study_date, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format.")
                    continue

                try:
                    max_members = int(input("Maximum group size (2-10): ").strip())
                    if max_members < 2 or max_members > 10:
                        print("Group size must be between 2 and 10.")
                        continue
                except ValueError:
                    print("Invalid number format.")
                    continue

                description = input("Description (optional): ").strip()

                cursor.execute('''
                INSERT INTO study_groups (
                    subject, topic, organizer_id, max_members, current_members,
                    meeting_time, location, study_date, status, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    subject, topic, student_id, max_members, 1,
                    meeting_time, location, study_date, 'open', description
                ))

                conn.commit()
                group_id = cursor.lastrowid

                print(f"Study group created successfully! Group ID: {group_id}")

                # Award points for organizing
                auto_award_points(student_id, "Academic Support", 25,
                                f"Organized study group: {subject} - {topic}", cursor, conn)

            elif choice == '3':
                # Join study group
                group_id = input("Enter study group ID to join: ").strip()
                if not group_id.isdigit():
                    print("Invalid group ID.")
                    continue

                cursor.execute('''
                SELECT subject, topic, current_members, max_members, organizer_id
                FROM study_groups
                WHERE study_group_id = ? AND status = 'open'
                ''', (group_id,))

                group = cursor.fetchone()

                if not group:
                    print("Study group not found or not open.")
                    continue

                if group[4] == student_id:
                    print("You are already the organizer of this group.")
                    continue

                if group[2] >= group[3]:
                    print("Study group is full.")
                    continue

                # Check if already joined (simplified - would need separate members table)
                cursor.execute('''
                UPDATE study_groups
                SET current_members = current_members + 1
                WHERE study_group_id = ?
                ''', (group_id,))

                conn.commit()

                print(f"Successfully joined study group: {group[0]} - {group[1]}")

                # Award points for joining
                auto_award_points(student_id, "Academic Support", 15,
                                f"Joined study group: {group[0]} - {group[1]}", cursor, conn)

            elif choice == '4':
                # My study groups
                cursor.execute('''
                SELECT study_group_id, subject, topic, meeting_time, location,
                       study_date, current_members, status
                FROM study_groups
                WHERE organizer_id = ?
                ORDER BY study_date DESC
                ''', (student_id,))

                my_groups = cursor.fetchall()

                if not my_groups:
                    print("You have not organized any study groups.")
                    continue

                print(f"\nYour Study Groups:")
                print(f"{'ID':<6} {'Subject':<15} {'Topic':<20} {'Date':<12} {'Members':<8} {'Status':<10}")
                print("-" * 75)

                for group in my_groups:
                    print(f"{group[0]:<6} {group[1]:<15} {group[2][:20]:<20} {group[5]:<12} {group[6]:<8} {group[7]:<10}")

            elif choice == '5':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_peer_tutoring(student_id, cursor, conn):
    """Manage peer tutoring offers and requests"""
    try:
        while True:
            print(f"\nPeer Tutoring")
            print("1. Browse tutoring offers")
            print("2. Offer tutoring services")
            print("3. My tutoring offers")
            print("4. Request tutoring")
            print("5. Tutoring statistics")
            print("6. Return to academic support")

            choice = input("Choose option: ").strip()

            if choice == '1':
                # Browse tutoring offers
                subject_filter = input("Filter by subject (or press Enter for all): ").strip()

                if subject_filter:
                    cursor.execute('''
                    SELECT t.offer_id, t.subject, t.topic, s.first_name, s.last_name,
                           t.hourly_rate, t.experience_level, t.rating, t.total_sessions
                    FROM tutoring_offers t
                    JOIN students s ON t.tutor_id = s.student_id
                    WHERE t.status = 'available' AND t.subject LIKE ?
                    ORDER BY t.rating DESC, t.total_sessions DESC
                    ''', (f'%{subject_filter}%',))
                else:
                    cursor.execute('''
                    SELECT t.offer_id, t.subject, t.topic, s.first_name, s.last_name,
                           t.hourly_rate, t.experience_level, t.rating, t.total_sessions
                    FROM tutoring_offers t
                    JOIN students s ON t.tutor_id = s.student_id
                    WHERE t.status = 'available'
                    ORDER BY t.rating DESC, t.total_sessions DESC
                    ''')

                offers = cursor.fetchall()

                if not offers:
                    print("No tutoring offers found.")
                    continue

                print(f"\nAvailable Tutoring:")
                print(f"{'ID':<6} {'Subject':<15} {'Topic':<20} {'Tutor':<20} {'Rate':<8} {'Rating':<8} {'Sessions':<8}")
                print("-" * 90)

                for offer in offers:
                    tutor = f"{offer[3]} {offer[4]}"
                    rate = f"£{offer[5]:.2f}/hr" if offer[5] > 0 else "Free"
                    rating = f"{offer[7]:.1f}/5" if offer[7] else "New"
                    print(f"{offer[0]:<6} {offer[1]:<15} {offer[2][:20]:<20} {tutor[:20]:<20} {rate:<8} {rating:<8} {offer[8]:<8}")

            elif choice == '2':
                # Offer tutoring services
                subject = input("Subject you can tutor: ").strip()
                if not subject:
                    print("Subject cannot be empty.")
                    continue

                topic = input("Specific topics (optional): ").strip()

                try:
                    hourly_rate = float(input("Hourly rate (£, enter 0 for free): ").strip())
                    if hourly_rate < 0:
                        print("Rate cannot be negative.")
                        continue
                except ValueError:
                    print("Invalid rate format.")
                    continue

                experience_levels = ["Beginner", "Intermediate", "Advanced", "Expert"]
                print("Experience levels:")
                for i, level in enumerate(experience_levels):
                    print(f"{i+1}. {level}")

                exp_choice = input("Select your experience level: ").strip()
                if exp_choice.isdigit() and 1 <= int(exp_choice) <= len(experience_levels):
                    experience_level = experience_levels[int(exp_choice)-1]
                else:
                    experience_level = "Intermediate"

                availability = input("Availability (e.g., 'Weekday evenings', 'Weekends'): ").strip()
                description = input("Additional description: ").strip()

                cursor.execute('''
                INSERT INTO tutoring_offers (
                    tutor_id, subject, topic, hourly_rate, availability,
                    experience_level, description, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, subject, topic, hourly_rate, availability,
                    experience_level, description, 'available'
                ))

                conn.commit()
                offer_id = cursor.lastrowid

                print(f"Tutoring offer created successfully! Offer ID: {offer_id}")

                # Award points for offering tutoring
                auto_award_points(student_id, "Academic Support", 30,
                                f"Offered tutoring in {subject}", cursor, conn)

            elif choice == '3':
                # My tutoring offers
                cursor.execute('''
                SELECT offer_id, subject, topic, hourly_rate, rating,
                       total_sessions, status
                FROM tutoring_offers
                WHERE tutor_id = ?
                ORDER BY subject
                ''', (student_id,))

                my_offers = cursor.fetchall()

                if not my_offers:
                    print("You have no tutoring offers.")
                    continue

                print(f"\nYour Tutoring Offers:")
                print(f"{'ID':<6} {'Subject':<15} {'Topic':<20} {'Rate':<10} {'Rating':<8} {'Sessions':<8} {'Status':<10}")
                print("-" * 80)

                for offer in my_offers:
                    rate = f"£{offer[3]:.2f}/hr" if offer[3] > 0 else "Free"
                    rating = f"{offer[4]:.1f}/5" if offer[4] else "No rating"
                    print(f"{offer[0]:<6} {offer[1]:<15} {offer[2][:20]:<20} {rate:<10} {rating:<8} {offer[5]:<8} {offer[6]:<10}")

                # Option to update offers
                update_id = input("\nEnter offer ID to update status (or press Enter to continue): ").strip()
                if update_id.isdigit():
                    new_status = input("New status (available/unavailable/paused): ").strip().lower()
                    if new_status in ['available', 'unavailable', 'paused']:
                        cursor.execute('''
                        UPDATE tutoring_offers SET status = ? WHERE offer_id = ? AND tutor_id = ?
                        ''', (new_status, update_id, student_id))
                        conn.commit()
                        print("Status updated.")

            elif choice == '4':
                # Request tutoring (simplified)
                print("To request tutoring:")
                print("1. Find a tutor from the browse list")
                print("2. Contact them directly using their student ID")
                print("3. Arrange session details")
                print("Note: Full booking system would be implemented in production")

            elif choice == '5':
                # Tutoring statistics
                cursor.execute('''
                SELECT COUNT(*) as total_offers,
                       COUNT(CASE WHEN status = 'available' THEN 1 END) as available_offers,
                       AVG(hourly_rate) as avg_rate,
                       COUNT(DISTINCT subject) as subjects_covered
                FROM tutoring_offers
                ''')

                stats = cursor.fetchone()

                print(f"\nTutoring System Statistics:")
                print(f"Total Tutoring Offers: {stats[0]}")
                print(f"Currently Available: {stats[1]}")
                print(f"Average Hourly Rate: £{stats[2]:.2f}" if stats[2] else "N/A")
                print(f"Subjects Covered: {stats[3]}")

                # Most popular subjects
                cursor.execute('''
                SELECT subject, COUNT(*) as offer_count
                FROM tutoring_offers
                GROUP BY subject
                ORDER BY offer_count DESC
                LIMIT 5
                ''')

                popular = cursor.fetchall()

                if popular:
                    print(f"\nMost Popular Subjects:")
                    for subj in popular:
                        print(f"- {subj[0]}: {subj[1]} offers")

            elif choice == '6':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_shared_resources(student_id, cursor, conn):
    """Manage shared academic resources"""
    try:
        while True:
            print(f"\nShared Academic Resources")
            print("1. Browse resources")
            print("2. Upload resource")
            print("3. My uploads")
            print("4. Download resource")
            print("5. Rate resource")
            print("6. Return to academic support")

            choice = input("Choose option: ").strip()

            if choice == '1':
                # Browse resources
                subject_filter = input("Filter by subject (or press Enter for all): ").strip()
                type_filter = input("Filter by type (notes/slides/papers/assignments/other, or press Enter for all): ").strip()

                query = '''
                SELECT r.resource_id, r.resource_title, r.resource_type, r.subject,
                       s.first_name, s.last_name, r.upload_date, r.downloads, r.rating
                FROM shared_resources r
                JOIN students s ON r.uploader_id = s.student_id
                WHERE 1=1
                '''
                params = []

                if subject_filter:
                    query += ' AND r.subject LIKE ?'
                    params.append(f'%{subject_filter}%')

                if type_filter:
                    query += ' AND r.resource_type LIKE ?'
                    params.append(f'%{type_filter}%')

                query += ' ORDER BY r.rating DESC, r.downloads DESC'

                cursor.execute(query, params)
                resources = cursor.fetchall()

                if not resources:
                    print("No resources found.")
                    continue

                print(f"\nAvailable Resources:")
                print(f"{'ID':<6} {'Title':<25} {'Type':<12} {'Subject':<15} {'Uploader':<20} {'Downloads':<10} {'Rating':<8}")
                print("-" * 100)

                for resource in resources:
                    uploader = f"{resource[4]} {resource[5]}"
                    rating = f"{resource[8]:.1f}/5" if resource[8] else "No rating"
                    print(f"{resource[0]:<6} {resource[1][:25]:<25} {resource[2]:<12} {resource[3]:<15} {uploader[:20]:<20} {resource[7]:<10} {rating:<8}")

            elif choice == '2':
                # Upload resource
                title = input("Resource title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    continue

                resource_types = ["notes", "slides", "papers", "assignments", "textbooks", "other"]
                print("Resource types:")
                for i, rtype in enumerate(resource_types):
                    print(f"{i+1}. {rtype}")

                type_choice = input("Select resource type: ").strip()
                if type_choice.isdigit() and 1 <= int(type_choice) <= len(resource_types):
                    resource_type = resource_types[int(type_choice)-1]
                else:
                    resource_type = input("Enter custom resource type: ").strip()

                subject = input("Subject: ").strip()
                file_path = input("File path/URL: ").strip()
                description = input("Description: ").strip()

                upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO shared_resources (
                    uploader_id, resource_title, resource_type, subject,
                    file_path, description, upload_date, downloads, rating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, title, resource_type, subject,
                    file_path, description, upload_date, 0, 0.0
                ))

                conn.commit()
                resource_id = cursor.lastrowid

                print(f"Resource uploaded successfully! Resource ID: {resource_id}")

                # Award points for sharing
                auto_award_points(student_id, "Academic Support", 20,
                                f"Shared resource: {title}", cursor, conn)

            elif choice == '3':
                # My uploads
                cursor.execute('''
                SELECT resource_id, resource_title, resource_type, subject,
                       upload_date, downloads, rating
                FROM shared_resources
                WHERE uploader_id = ?
                ORDER BY upload_date DESC
                ''', (student_id,))

                my_resources = cursor.fetchall()

                if not my_resources:
                    print("You have not uploaded any resources.")
                    continue

                print(f"\nYour Uploaded Resources:")
                print(f"{'ID':<6} {'Title':<30} {'Type':<12} {'Subject':<15} {'Downloads':<10} {'Rating':<8}")
                print("-" * 85)

                for resource in my_resources:
                    rating = f"{resource[6]:.1f}/5" if resource[6] else "No rating"
                    print(f"{resource[0]:<6} {resource[1][:30]:<30} {resource[2]:<12} {resource[3]:<15} {resource[5]:<10} {rating:<8}")

            elif choice == '4':
                # Download resource
                resource_id = input("Enter resource ID to download: ").strip()
                if not resource_id.isdigit():
                    print("Invalid resource ID.")
                    continue

                cursor.execute('''
                SELECT resource_title, file_path, uploader_id
                FROM shared_resources
                WHERE resource_id = ?
                ''', (resource_id,))

                resource = cursor.fetchone()

                if not resource:
                    print("Resource not found.")
                    continue

                print(f"Downloading: {resource[0]}")
                print(f"File location: {resource[1]}")

                # Update download count
                cursor.execute('''
                UPDATE shared_resources
                SET downloads = downloads + 1
                WHERE resource_id = ?
                ''', (resource_id,))

                conn.commit()

                # Award points to uploader
                if resource[2] != student_id:
                    auto_award_points(resource[2], "Academic Support", 5,
                                    f"Resource downloaded: {resource[0]}", cursor, conn)

                print("Download count updated.")

            elif choice == '5':
                # Rate resource
                resource_id = input("Enter resource ID to rate: ").strip()
                if not resource_id.isdigit():
                    print("Invalid resource ID.")
                    continue

                try:
                    rating = float(input("Rate from 1.0 to 5.0: ").strip())
                    if rating < 1.0 or rating > 5.0:
                        print("Rating must be between 1.0 and 5.0.")
                        continue
                except ValueError:
                    print("Invalid rating format.")
                    continue

                # In a full implementation, this would track individual ratings
                # For now, we'll update the average
                cursor.execute('''
                UPDATE shared_resources
                SET rating = (COALESCE(rating, 0) + ?) / 2
                WHERE resource_id = ?
                ''', (rating, resource_id))

                conn.commit()
                print("Rating submitted!")

            elif choice == '6':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def exam_preparation_groups(student_id, cursor, conn):
    """Manage exam preparation groups"""
    try:
        print(f"\nExam Preparation Groups")
        print("=======================")

        # This would be similar to study groups but specifically for exam prep
        print("Exam preparation features:")
        print("- Subject-specific study groups")
        print("- Exam technique workshops")
        print("- Past paper discussion groups")
        print("- Stress management sessions")
        print("- Last-minute revision groups")

        # Create exam-specific study group
        create_exam_group = input("\nCreate exam preparation group? (y/n): ").strip().lower()

        if create_exam_group == 'y':
            subject = input("Exam subject: ").strip()
            exam_date = input("Exam date (YYYY-MM-DD): ").strip()

            try:
                datetime.strptime(exam_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format.")
                return

            focus_areas = input("Focus areas (e.g., 'past papers, key concepts'): ").strip()

            cursor.execute('''
            INSERT INTO study_groups (
                subject, topic, organizer_id, max_members, current_members,
                meeting_time, location, study_date, status, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                subject, f"Exam Preparation - {focus_areas}", student_id, 8, 1,
                "TBD", "TBD", exam_date, 'open', f"Exam preparation group for {subject}"
            ))

            conn.commit()
            print("Exam preparation group created!")

            # Award points
            auto_award_points(student_id, "Academic Support", 25,
                            f"Created exam prep group: {subject}", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_academic_workshops(cursor):
    """View upcoming academic workshops"""
    try:
        print(f"\nUpcoming Academic Workshops")
        print("=" * 35)

        # This would integrate with the events system
        workshops = [
            ("Study Skills", "Learn effective study techniques", "2024-12-15", "Library Room 3"),
            ("Time Management", "Balance studies and social life", "2024-12-18", "Student Union Hall"),
            ("Research Methods", "Academic research techniques", "2024-12-20", "Online"),
            ("Presentation Skills", "Confident academic presentations", "2024-12-22", "Room 204"),
            ("Essay Writing", "Structure and argumentation", "2024-12-25", "Library Room 1")
        ]

        print(f"{'Workshop':<20} {'Description':<35} {'Date':<12} {'Location':<15}")
        print("-" * 85)

        for workshop in workshops:
            print(f"{workshop[0]:<20} {workshop[1]:<35} {workshop[2]:<12} {workshop[3]:<15}")

        print(f"\nTo register for workshops:")
        print("- Contact Academic Support Office")
        print("- Visit the Student Success Centre")
        print("- Check the events calendar")

    except Exception as e:
        print(f"An error occurred: {e}")
