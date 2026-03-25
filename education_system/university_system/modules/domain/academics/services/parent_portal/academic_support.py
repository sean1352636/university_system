from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.email import send_email
import datetime


class AcademicSupportMixin:
    def view_homework_tracking(self):
        """View homework assignments and completion status"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view homework.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('view_homework'):
            print("You don't have permission to view homework.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to view homework:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")
        
        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError
            
            selected_child = children[index]
            
            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view homework for this child.")
                return
            
            student_id = selected_child[0]
            
            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()
                
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                
                # Get pending homework
                cursor.execute('''
                SELECT h.assignment_title, h.description, h.due_date, m.module_name, h.assigned_date
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'pending' AND h.due_date >= ?
                ORDER BY h.due_date
                ''', (student_id, today))
                
                pending_homework = cursor.fetchall()
                
                # Get overdue homework
                cursor.execute('''
                SELECT h.assignment_title, h.description, h.due_date, m.module_name, h.assigned_date
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'pending' AND h.due_date < ?
                ORDER BY h.due_date
                ''', (student_id, today))
                
                overdue_homework = cursor.fetchall()
                
                # Get recently completed homework
                cursor.execute('''
                SELECT h.assignment_title, h.submitted_date, h.grade, m.module_name, h.teacher_comments
                FROM homework_assignments h
                JOIN modules m ON h.module_code = m.module_code
                WHERE h.student_id = ? AND h.completion_status = 'completed'
                ORDER BY h.submitted_date DESC
                LIMIT 5
                ''', (student_id,))
                
                completed_homework = cursor.fetchall()
                
                print(f"\nHomework for {selected_child[1]} {selected_child[3]}:")
                
                if overdue_homework:
                    print("\nOVERDUE HOMEWORK:")
                    for hw in overdue_homework:
                        title, description, due_date, module, assigned_date = hw
                        print(f"- {title} ({module})")
                        print(f"  Due: {due_date} (OVERDUE)")
                        print(f"  Description: {description}")
                        print()
                
                if pending_homework:
                    print("\nUpcoming Homework:")
                    for hw in pending_homework:
                        title, description, due_date, module, assigned_date = hw
                        print(f"- {title} ({module})")
                        print(f"  Due: {due_date}")
                        print(f"  Description: {description}")
                        print()
                
                if completed_homework:
                    print("\nRecently Completed:")
                    for hw in completed_homework:
                        title, submitted_date, grade, module, comments = hw
                        print(f"- {title} ({module})")
                        print(f"  Submitted: {submitted_date}")
                        if grade:
                            print(f"  Grade: {grade}")
                        if comments:
                            print(f"  Teacher comments: {comments}")
                        print()
                
                if not pending_homework and not overdue_homework and not completed_homework:
                    print("No homework assignments found.")
                
            except sqlite3.Error as e:
                print(f"Database error viewing homework: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def schedule_parent_teacher_meeting(self):
        """Schedule a meeting with teachers"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to schedule meetings.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('schedule_meetings'):
            print("You don't have permission to schedule meetings.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child for meeting:")
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
                
                # Get available teachers for this student
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
                
                print("\nSelect teacher to meet with:")
                for i, teacher in enumerate(teachers):
                    teacher_id, username, module_name = teacher
                    print(f"{i+1}. {username} ({module_name})")
                
                teacher_choice = input("Enter teacher number: ")
                try:
                    teacher_index = int(teacher_choice) - 1
                    if teacher_index < 0 or teacher_index >= len(teachers):
                        raise ValueError
                    
                    selected_teacher = teachers[teacher_index]
                    teacher_id = selected_teacher[0]
                    
                    # Get teacher availability
                    cursor.execute('''
                    SELECT day_of_week, start_time, end_time, meeting_type, location
                    FROM teacher_availability
                    WHERE teacher_id = ? AND active = 1
                    ORDER BY 
                        CASE day_of_week
                            WHEN 'Monday' THEN 1
                            WHEN 'Tuesday' THEN 2
                            WHEN 'Wednesday' THEN 3
                            WHEN 'Thursday' THEN 4
                            WHEN 'Friday' THEN 5
                        END,
                        start_time
                    ''', (teacher_id,))
                    
                    availability = cursor.fetchall()
                    
                    if not availability:
                        print("Teacher has not set availability. Please contact the school directly.")
                        return
                    
                    print(f"\nAvailability for {selected_teacher[1]}:")
                    for slot in availability:
                        day, start_time, end_time, meeting_type, location = slot
                        print(f"- {day}: {start_time} - {end_time} ({meeting_type}) at {location}")
                    
                    # Schedule meeting
                    print("\nSchedule Meeting:")
                    meeting_date = input("Meeting date (YYYY-MM-DD): ")
                    start_time = input("Start time (HH:MM): ")
                    end_time = input("End time (HH:MM): ")
                    meeting_type = input("Meeting type (in-person/phone/video): ")
                    agenda = input("Meeting agenda/topics: ")
                    
                    # Validate date format
                    try:
                        datetime.datetime.strptime(meeting_date, '%Y-%m-%d')
                        datetime.datetime.strptime(start_time, '%H:%M')
                        datetime.datetime.strptime(end_time, '%H:%M')
                    except ValueError:
                        print("Invalid date or time format.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return
                    
                    # Insert meeting request
                    cursor.execute('''
                    INSERT INTO parent_teacher_meetings 
                    (parent_id, teacher_id, student_id, meeting_date, start_time, end_time, 
                     meeting_type, status, agenda)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'requested', ?)
                    ''', (parent_id, teacher_id, student_id, meeting_date, start_time, 
                          end_time, meeting_type, agenda))
                    
                    conn.commit()
                    print("Meeting request submitted successfully. The teacher will confirm the appointment.")
                    
                    # Send notification to teacher
                    cursor.execute('SELECT email FROM users WHERE id = ?', (teacher_id,))
                    teacher_email = cursor.fetchone()
                    
                    if teacher_email and teacher_email[0]:
                        try:
                            send_email(
                                teacher_email[0],
                                "Parent-Teacher Meeting Request",
                                f"A parent has requested a meeting on {meeting_date} at {start_time} regarding student {student_id}."
                            )
                        except Exception as e:
                            print(f"Note: Email notification could not be sent: {e}")
                    
                except (ValueError, IndexError):
                    print("Invalid teacher choice.")
                
            except sqlite3.Error as e:
                print(f"Database error scheduling meeting: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")

    def manage_academic_goals(self):
        """Set and track academic goals"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage academic goals.")
            return
        
        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return
        
        if not self.auth.check_permission('set_academic_goals'):
            print("You don't have permission to set academic goals.")
            return
        
        children = self.view_children()
        
        if not children:
            print("You have no children registered in the system.")
            return
        
        print("\nSelect child to manage goals:")
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
                
                # Get existing goals
                cursor.execute('''
                SELECT id, goal_title, description, target_grade, target_date, current_progress, status, created_date
                FROM academic_goals
                WHERE student_id = ?
                ORDER BY created_date DESC
                ''', (student_id,))
                
                goals = cursor.fetchall()
                
                print(f"\nAcademic Goals for {selected_child[1]} {selected_child[3]}:")
                
                if goals:
                    print("\nExisting Goals:")
                    for goal in goals:
                        id, title, description, target_grade, target_date, progress, status, created_date = goal
                        print(f"- {title} ({status.upper()})")
                        print(f"  Target: {target_grade} by {target_date}")
                        print(f"  Progress: {progress or 'Not updated'}")
                        print(f"  Created: {created_date}")
                        print()
                
                print("\nOptions:")
                print("1. Add new goal")
                print("2. Update goal progress")
                print("3. Back to menu")
                
                option = input("Select option: ")
                
                if option == '1':
                    print("\nAdd New Academic Goal:")
                    goal_title = input("Goal title: ")
                    description = input("Description: ")
                    target_grade = input("Target grade: ")
                    target_date = input("Target date (YYYY-MM-DD): ")
                    
                    # Validate date
                    try:
                        datetime.datetime.strptime(target_date, '%Y-%m-%d')
                    except ValueError:
                        print("Invalid date format.")
                        return
                    
                    parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                    if not parent_id:
                        print("Error retrieving parent ID.")
                        return
                    
                    created_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    cursor.execute('''
                    INSERT INTO academic_goals 
                    (student_id, parent_id, goal_title, description, target_grade, target_date, 
                     current_progress, status, created_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    ''', (student_id, parent_id, goal_title, description, target_grade, 
                          target_date, 'Goal set', created_date))
                    
                    conn.commit()
                    print("Academic goal added successfully.")
                
                elif option == '2' and goals:
                    print("\nSelect goal to update:")
                    for i, goal in enumerate(goals):
                        print(f"{i+1}. {goal[1]}")
                    
                    goal_choice = input("Enter goal number: ")
                    try:
                        goal_index = int(goal_choice) - 1
                        if goal_index < 0 or goal_index >= len(goals):
                            raise ValueError
                        
                        selected_goal = goals[goal_index]
                        goal_id = selected_goal[0]
                        
                        print(f"\nCurrent progress: {selected_goal[5] or 'Not updated'}")
                        new_progress = input("Update progress: ")
                        
                        print("\nUpdate status:")
                        print("1. Active")
                        print("2. Achieved")
                        print("3. Paused")
                        print("4. Cancelled")
                        
                        status_choice = input("Select status: ")
                        status_map = {'1': 'active', '2': 'achieved', '3': 'paused', '4': 'cancelled'}
                        new_status = status_map.get(status_choice, 'active')
                        
                        cursor.execute('''
                        UPDATE academic_goals 
                        SET current_progress = ?, status = ?
                        WHERE id = ?
                        ''', (new_progress, new_status, goal_id))
                        
                        conn.commit()
                        print("Goal updated successfully.")
                        
                    except (ValueError, IndexError):
                        print("Invalid goal choice.")
                
            except sqlite3.Error as e:
                print(f"Database error managing goals: {e}")
            finally:
                if conn:
                    conn.close()
            
        except (ValueError, IndexError):
            print("Invalid choice.")
