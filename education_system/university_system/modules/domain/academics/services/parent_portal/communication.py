from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.email import send_email
import datetime


class CommunicationMixin:
    def send_message_to_teacher(self):
        """Send a message to a teacher from a parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to send messages.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('message_teachers'):
            print("You don't have permission to message teachers.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect the child related to this message:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]

            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot send messages regarding this child.")
                return

            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                cursor.execute('''
                CREATE TABLE IF NOT EXISTS parent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id TEXT,
                    teacher_id INTEGER,
                    student_id TEXT,
                    message_content TEXT,
                    created_date TEXT,
                    is_read BOOLEAN DEFAULT 0,
                    is_from_parent BOOLEAN DEFAULT 1,
                    message_type TEXT DEFAULT 'individual',
                    group_id TEXT,
                    FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                    FOREIGN KEY (teacher_id) REFERENCES users (id),
                    FOREIGN KEY (student_id) REFERENCES students (student_id)
                )
                ''')

                cursor.execute('''
                SELECT DISTINCT t.id, t.username, m.module_code, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                JOIN module_teachers mt ON m.module_code = mt.module_code
                JOIN users t ON mt.teacher_id = t.id
                WHERE sm.student_id = ? AND t.role = 'teacher'
                ORDER BY m.module_code
                ''', (student_id,))

                teachers = cursor.fetchall()

                if not teachers:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_teachers'")
                    if not cursor.fetchone():
                        print("Module-teacher assignments not yet set up.")

                    cursor.execute('''
                    SELECT id, username FROM users WHERE role = 'teacher' ORDER BY username
                    ''')

                    temp_teachers = cursor.fetchall()
                    teachers = [(t[0], t[1], 'N/A', 'N/A') for t in temp_teachers]

                    if not teachers:
                        print("No teachers found in the system.")
                        return

                print("\nSelect teacher to message:")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_code, module_name = teacher
                    module_info = f" ({module_code}: {module_name})" if module_code != 'N/A' else ""
                    print(f"{i+1}. {username}{module_info}")

                teacher_choice = input("Enter the number of the teacher: ")
                try:
                    teacher_index = int(teacher_choice) - 1
                    if teacher_index < 0 or teacher_index >= len(teachers):
                        raise ValueError

                    selected_teacher = teachers[teacher_index]
                    teacher_id = selected_teacher[0]

                    print("\nCompose your message:")
                    message_content = input("Message: ")

                    if not message_content:
                        print("Message cannot be empty.")
                        return

                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return

                    created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute(
                        'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (parent_id, teacher_id, student_id, message_content, created_date, 0, 1)
                    )

                    conn.commit()
                    print("Message sent successfully.")

                    cursor.execute('SELECT email FROM users WHERE id = ?', (teacher_id,))
                    teacher_email = cursor.fetchone()

                    if teacher_email and teacher_email[0]:
                        try:
                            send_email(
                                teacher_email[0],
                                "New parent message",
                                f"You have received a new message from a parent regarding student {student_id}."
                            )
                        except Exception as e:
                            print(f"Note: Email notification could not be sent: {e}")

                except (ValueError, IndexError):
                    print("Invalid teacher choice.")

            except sqlite3.Error as e:
                print(f"Database error sending message: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_messages(self):
        """View messages between parent and teachers"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view messages.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='parent_messages'")
            if not cursor.fetchone():
                print("Messaging system is not yet set up.")
                return

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            cursor.execute('''
            SELECT DISTINCT t.id, t.username, s.student_id, s.first_name, s.last_name
            FROM parent_messages pm
            JOIN users t ON pm.teacher_id = t.id
            JOIN students s ON pm.student_id = s.student_id
            WHERE pm.parent_id = ?
            ORDER BY t.username
            ''', (parent_id,))

            conversations = cursor.fetchall()

            if not conversations:
                print("You have no message history.")
                return

            print("\nSelect conversation to view:")
            for i, convo in enumerate(conversations):
                teacher_id, teacher_name, student_id, first_name, last_name = convo
                print(f"{i+1}. With {teacher_name} regarding {first_name} {last_name}")

            print(f"{len(conversations)+1}. Back to Parent Menu")

            choice = input("Enter your choice: ")
            try:
                index = int(choice) - 1
                if index == len(conversations):
                    return

                if index < 0 or index >= len(conversations):
                    raise ValueError

                selected_convo = conversations[index]
                teacher_id = selected_convo[0]
                student_id = selected_convo[2]

                cursor.execute('''
                SELECT message_content, created_date, is_from_parent
                FROM parent_messages
                WHERE parent_id = ? AND teacher_id = ? AND student_id = ?
                ORDER BY created_date
                ''', (parent_id, teacher_id, student_id))

                messages = cursor.fetchall()

                print("\n" + "=" * 50)
                print(f"Conversation with {selected_convo[1]} about {selected_convo[3]} {selected_convo[4]}")
                print("=" * 50)

                for message in messages:
                    content, date, is_from_parent = message
                    sender = "You" if is_from_parent else selected_convo[1]
                    print(f"[{date}] {sender}: {content}")

                print("=" * 50)

                cursor.execute('''
                UPDATE parent_messages
                SET is_read = 1
                WHERE parent_id = ? AND teacher_id = ? AND student_id = ? AND is_from_parent = 0
                ''', (parent_id, teacher_id, student_id))

                conn.commit()

                reply = input("Would you like to reply? (y/n): ")
                if reply.lower() == 'y':
                    message_content = input("Your message: ")

                    if message_content:
                        created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        cursor.execute(
                            'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (parent_id, teacher_id, student_id, message_content, created_date, 0, 1)
                        )

                        conn.commit()
                        print("Reply sent successfully.")

            except (ValueError, IndexError):
                print("Invalid choice.")

        except sqlite3.Error as e:
            print(f"Database error viewing messages: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def send_group_message(self):
        """Send a message to multiple teachers at once"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to send group messages.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('group_messaging'):
            print("You don't have permission to send group messages.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child for group message:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get all teachers for this student
                cursor.execute('''
                SELECT DISTINCT t.id, t.username, m.module_name
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                JOIN module_teachers mt ON m.module_code = mt.module_code
                JOIN users t ON mt.teacher_id = t.id
                WHERE sm.student_id = ? AND t.role = 'teacher'
                ORDER BY t.username
                ''', (student_id,))

                teachers = cursor.fetchall()

                if not teachers:
                    print("No teachers found for this student.")
                    return

                print("\nSelect teachers to message (enter numbers separated by commas, or 'all'):")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_name = teacher
                    print(f"{i+1}. {username} ({module_name})")

                teacher_choice = input("Enter your selection: ")

                selected_teachers = []
                if teacher_choice.lower() == 'all':
                    selected_teachers = teachers
                else:
                    try:
                        indices = [int(x.strip()) - 1 for x in teacher_choice.split(',')]
                        selected_teachers = [teachers[i] for i in indices if 0 <= i < len(teachers)]
                    except (ValueError, IndexError):
                        print("Invalid selection.")
                        return

                if not selected_teachers:
                    print("No teachers selected.")
                    return

                print(f"\nSending to {len(selected_teachers)} teacher(s)")
                message_content = input("Message: ")

                if not message_content:
                    print("Message cannot be empty.")
                    return

                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return

                # Generate group ID for this message
                group_id = f"group_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Send message to each selected teacher
                for teacher in selected_teachers:
                    teacher_id = teacher[0]

                    cursor.execute('''
                    INSERT INTO parent_messages
                    (parent_id, teacher_id, student_id, message_content, created_date,
                     is_read, is_from_parent, message_type, group_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'group', ?)
                    ''', (parent_id, teacher_id, student_id, message_content, created_date,
                          0, 1, group_id))

                conn.commit()
                print(f"Group message sent successfully to {len(selected_teachers)} teacher(s).")

            except sqlite3.Error as e:
                print(f"Database error sending group message: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")
