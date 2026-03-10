from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection, auth,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def create_club():
    """Create a new student club/society"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to create a club.")
        return

    if not (auth.check_permission('create_club') or auth.check_permission('manage_all_clubs')):
        print("You don't have permission to create clubs.")
        return

    club_name = input("Enter club name: ").strip()
    if not club_name:
        print("Club name cannot be empty.")
        return

    description = input("Enter club description: ").strip()
    category = input("Enter club category (e.g., Sports, Academic, Cultural): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if club name already exists
        cursor.execute('SELECT COUNT(*) FROM student_clubs WHERE club_name = ?', (club_name,))
        if cursor.fetchone()[0] > 0:
            print(f"A club named '{club_name}' already exists.")
            conn.close()
            return

        # Get president ID
        president_id = input("Enter student ID of the club president: ").strip()

        # Verify president exists
        cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (president_id,))
        if cursor.fetchone()[0] == 0:
            print(f"No student found with ID {president_id}.")
            conn.close()
            return

        treasurer_id = input("Enter student ID of the club treasurer: ").strip()
        secretary_id = input("Enter student ID of the club secretary: ").strip()

        founding_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO student_clubs (
            club_name, description, category, founding_date, status,
            president_id, treasurer_id, secretary_id, member_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            club_name, description, category, founding_date, 'active',
            president_id, treasurer_id, secretary_id, 3  # Start with 3 officers
        ))

        club_id = cursor.lastrowid

        # Add officers as members
        member_data = [
            (club_id, president_id, founding_date, 'President'),
            (club_id, treasurer_id, founding_date, 'Treasurer'),
            (club_id, secretary_id, founding_date, 'Secretary')
        ]

        cursor.executemany(
            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
            member_data
        )

        conn.commit()
        print(f"Club '{club_name}' created successfully!")
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def view_clubs():
    """View available clubs/societies"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to view clubs.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all active clubs
        cursor.execute('''
        SELECT club_id, club_name, category, description, member_count
        FROM student_clubs
        WHERE status = 'active'
        ORDER BY club_name
        ''')

        clubs = cursor.fetchall()

        if not clubs:
            print("No active clubs found.")
            conn.close()
            return

        print("\nAvailable Clubs and Societies:")
        print("==============================")

        for club in clubs:
            print(f"\nID: {club[0]}")
            print(f"Name: {club[1]}")
            print(f"Category: {club[2]}")
            print(f"Description: {club[3]}")
            print(f"Member Count: {club[4]}")
            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def manage_club():
    """Manage a club (for club officers)"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage a club.")
        return

    if not (auth.check_permission('manage_own_club') or auth.check_permission('manage_all_clubs')):
        print("You don't have permission to manage clubs.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        # If admin, show all clubs, otherwise show only clubs where user is an officer
        if auth.check_permission('manage_all_clubs'):
            cursor.execute('''
            SELECT club_id, club_name
            FROM student_clubs
            WHERE status = 'active'
            ORDER BY club_name
            ''')
        else:
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND c.status = 'active'
            ORDER BY c.club_name
            ''', (student_id, student_id, student_id))

        clubs = cursor.fetchall()

        if not clubs:
            print("You don't have any clubs to manage.")
            conn.close()
            return

        print("\nClubs you can manage:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]} (ID: {club[0]})")

        choice = input("\nSelect a club to manage (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return

        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]

        while True:
            print(f"\nManaging {club_name}:")
            print("1. View club details")
            print("2. View members")
            print("3. Add/remove members")
            print("4. Update club information")
            print("5. Organize an event")
            print("6. Back to Student Union menu")

            action = input("\nChoose an action: ").strip()

            if action == '1':
                # View club details
                cursor.execute('''
                SELECT * FROM student_clubs WHERE club_id = ?
                ''', (club_id,))
                club_details = cursor.fetchone()

                if club_details:
                    print(f"\nClub Details for {club_name}:")
                    print(f"ID: {club_details[0]}")
                    print(f"Name: {club_details[1]}")
                    print(f"Description: {club_details[2]}")
                    print(f"Category: {club_details[3]}")
                    print(f"Founded: {club_details[4]}")
                    print(f"Status: {club_details[5]}")
                    print(f"President ID: {club_details[6]}")
                    print(f"Treasurer ID: {club_details[7]}")
                    print(f"Secretary ID: {club_details[8]}")
                    print(f"Member Count: {club_details[9]}")
                    print(f"Budget: £{club_details[10]:.2f}")

            elif action == '2':
                # View members
                cursor.execute('''
                SELECT m.student_id, s.first_name, s.last_name, m.role, m.join_date
                FROM club_members m
                JOIN students s ON m.student_id = s.student_id
                WHERE m.club_id = ?
                ORDER BY m.role, m.join_date
                ''', (club_id,))

                members = cursor.fetchall()

                if not members:
                    print("No members found.")
                else:
                    print(f"\nMembers of {club_name}:")
                    print(f"{'ID':<10} {'Name':<30} {'Role':<15} {'Join Date':<15}")
                    print("-" * 70)

                    for member in members:
                        print(f"{member[0]:<10} {member[1]} {member[2]:<30} {member[3]:<15} {member[4]:<15}")

            elif action == '3':
                # Add/remove members - simplified for this example
                print("\n1. Add member")
                print("2. Remove member")

                sub_action = input("Choose an action: ").strip()

                if sub_action == '1':
                    # Add member
                    new_member_id = input("Enter student ID to add: ").strip()

                    # Check if student exists
                    cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (new_member_id,))
                    if cursor.fetchone()[0] == 0:
                        print(f"No student found with ID {new_member_id}.")
                        continue

                    # Check if already a member
                    cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?',
                                  (club_id, new_member_id))
                    if cursor.fetchone()[0] > 0:
                        print("This student is already a member.")
                        continue

                    # Add as member
                    join_date = datetime.now().strftime('%Y-%m-%d')

                    cursor.execute(
                        'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
                        (club_id, new_member_id, join_date, 'Member')
                    )

                    # Update member count
                    cursor.execute(
                        'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
                        (club_id,)
                    )

                    conn.commit()
                    print(f"Member added successfully!")

                elif sub_action == '2':
                    # Remove member
                    remove_id = input("Enter student ID to remove: ").strip()

                    # Check if is an officer
                    cursor.execute('''
                    SELECT president_id, treasurer_id, secretary_id FROM student_clubs
                    WHERE club_id = ?
                    ''', (club_id,))

                    officers = cursor.fetchone()
                    if remove_id in officers:
                        print("Cannot remove club officers. Change officer assignments first.")
                        continue

                    # Remove member
                    cursor.execute(
                        'DELETE FROM club_members WHERE club_id = ? AND student_id = ?',
                        (club_id, remove_id)
                    )

                    if cursor.rowcount > 0:
                        # Update member count
                        cursor.execute(
                            'UPDATE student_clubs SET member_count = member_count - 1 WHERE club_id = ?',
                            (club_id,)
                        )

                        conn.commit()
                        print("Member removed successfully!")
                    else:
                        print(f"No member found with ID {remove_id}.")

            elif action == '4':
                # Update club information
                print("\n1. Update description")
                print("2. Update category")
                print("3. Change club officers")

                sub_action = input("Choose an action: ").strip()

                if sub_action == '1':
                    new_desc = input("Enter new description: ").strip()
                    cursor.execute(
                        'UPDATE student_clubs SET description = ? WHERE club_id = ?',
                        (new_desc, club_id)
                    )
                    conn.commit()
                    print("Description updated!")

                elif sub_action == '2':
                    new_category = input("Enter new category: ").strip()
                    cursor.execute(
                        'UPDATE student_clubs SET category = ? WHERE club_id = ?',
                        (new_category, club_id)
                    )
                    conn.commit()
                    print("Category updated!")

                elif sub_action == '3':
                    # Change officers - simplified
                    position = input("Which position to change (President/Treasurer/Secretary)? ").strip().lower()

                    if position not in ['president', 'treasurer', 'secretary']:
                        print("Invalid position.")
                        continue

                    new_id = input(f"Enter student ID for new {position}: ").strip()

                    # Check if student exists
                    cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (new_id,))
                    if cursor.fetchone()[0] == 0:
                        print(f"No student found with ID {new_id}.")
                        continue

                    # Update position
                    if position == 'president':
                        cursor.execute(
                            'UPDATE student_clubs SET president_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )
                    elif position == 'treasurer':
                        cursor.execute(
                            'UPDATE student_clubs SET treasurer_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )
                    elif position == 'secretary':
                        cursor.execute(
                            'UPDATE student_clubs SET secretary_id = ? WHERE club_id = ?',
                            (new_id, club_id)
                        )

                    # Make sure they're a member
                    cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?',
                                  (club_id, new_id))
                    if cursor.fetchone()[0] == 0:
                        join_date = datetime.now().strftime('%Y-%m-%d')
                        cursor.execute(
                            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
                            (club_id, new_id, join_date, position.capitalize())
                        )

                        # Update member count if needed
                        cursor.execute(
                            'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
                            (club_id,)
                        )
                    else:
                        # Just update their role
                        cursor.execute(
                            'UPDATE club_members SET role = ? WHERE club_id = ? AND student_id = ?',
                            (position.capitalize(), club_id, new_id)
                        )

                    conn.commit()
                    print(f"{position.capitalize()} updated successfully!")

            elif action == '5':
                # Organize an event
                print("\nOrganize a new event:")
                event_name = input("Event name: ").strip()
                description = input("Description: ").strip()

                date = input("Date (YYYY-MM-DD): ").strip()
                start_time = input("Start time (HH:MM): ").strip()
                end_time = input("End time (HH:MM): ").strip()

                location = input("Location: ").strip()
                category = input("Category: ").strip()
                max_attendees = input("Maximum attendees (leave blank for unlimited): ").strip()

                max_attendees = int(max_attendees) if max_attendees.isdigit() else 0

                cursor.execute('''
                INSERT INTO union_events (
                    event_name, description, event_date, start_time, end_time,
                    location, organizer_id, category, max_attendees, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_name, description, date, start_time, end_time,
                    location, club_id, category, max_attendees, 'upcoming'
                ))

                conn.commit()
                print(f"Event '{event_name}' created successfully!")

            elif action == '6':
                break

            else:
                print("Invalid choice.")

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
