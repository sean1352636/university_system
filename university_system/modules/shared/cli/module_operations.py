"""
Module/Course operations for CLI system.

Handles course module CRUD operations and management.
"""

from .imports import (
    logging, sqlite3, datetime, DB_PATH, logger, _t,
    log_activity, log_create, log_update, log_delete, get_auth
)

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def create_module():
    """Create a new module in the system"""
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to create modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nCreate New Module")
        print("=" * 30)
        
        # Get module code
        while True:
            module_code = input("Enter module code (e.g., CS101): ").strip().upper()
            if not module_code:
                print("Error: Module code cannot be empty.")
                continue
            
            # Check if module code already exists
            cursor.execute("SELECT module_code FROM modules WHERE module_code = ?", (module_code,))
            if cursor.fetchone():
                print(f"Error: Module code '{module_code}' already exists.")
                continue
            
            # Validate module code format (letters followed by numbers)
            import re
            if not re.match(r'^[A-Z]{2,4}\d{3,4}$', module_code):
                print("Error: Module code must be 2-4 letters followed by 3-4 digits (e.g., CS101).")
                continue
            
            break
        
        # Get module name
        while True:
            module_name = input("Enter module name: ").strip()
            if not module_name:
                print("Error: Module name cannot be empty.")
                continue
            if len(module_name) < 3:
                print("Error: Module name must be at least 3 characters long.")
                continue
            break
        
        # Get module type
        print("\nModule Types:")
        print("1. Compulsory")
        print("2. Optional")
        print("3. CS (Computer Science specific)")
        print("4. DS (Data Science specific)")
        
        while True:
            type_choice = input("Select module type (1-4): ")
            if type_choice == '1':
                module_type = 'compulsory'
                break
            elif type_choice == '2':
                module_type = 'optional'
                break
            elif type_choice == '3':
                module_type = 'CS'
                break
            elif type_choice == '4':
                module_type = 'DS'
                break
            else:
                print("Invalid choice. Please select 1-4.")
        
        # Insert the module
        cursor.execute('''
        INSERT INTO modules (module_code, module_name, module_type)
        VALUES (?, ?, ?)
        ''', (module_code, module_name, module_type))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code} - {module_name}' created successfully!")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating module: {e}")
        input("\nPress Enter to continue...")
        return False
    

def edit_module():
    """Edit an existing module"""
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to edit modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to edit modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nEdit Module")
        print("=" * 30)
        
        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type 
        FROM modules 
        ORDER BY module_type, module_code
        ''')
        
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False
        
        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)
        
        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")
        
        # Get module to edit
        while True:
            module_code = input("\nEnter module code to edit (or 'cancel' to exit): ").strip().upper()
            
            if module_code.lower() == 'cancel':
                print("Edit operation cancelled.")
                conn.close()
                return False
            
            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()
            
            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue
            
            break
        
        # Display current module information
        print(f"\nCurrent module information:")
        print(f"Code: {module[0]}")
        print(f"Name: {module[1]}")
        print(f"Type: {module[2]}")
        
        # Choose what to edit
        print("\nWhat would you like to edit?")
        print("1. Module Name")
        print("2. Module Type")
        print("3. Both")
        print("4. Cancel")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '4':
            print("Edit operation cancelled.")
            conn.close()
            return False
        
        new_name = module[1]  # Keep current name by default
        new_type = module[2]  # Keep current type by default
        
        # Edit module name
        if choice in ['1', '3']:
            while True:
                new_name = input(f"Enter new module name (current: {module[1]}): ").strip()
                if not new_name:
                    print("Error: Module name cannot be empty.")
                    continue
                if len(new_name) < 3:
                    print("Error: Module name must be at least 3 characters long.")
                    continue
                break
        
        # Edit module type
        if choice in ['2', '3']:
            print("\nModule Types:")
            print("1. Compulsory")
            print("2. Optional")
            print("3. CS (Computer Science specific)")
            print("4. DS (Data Science specific)")
            
            while True:
                type_choice = input("Select new module type (1-4): ")
                if type_choice == '1':
                    new_type = 'compulsory'
                    break
                elif type_choice == '2':
                    new_type = 'optional'
                    break
                elif type_choice == '3':
                    new_type = 'CS'
                    break
                elif type_choice == '4':
                    new_type = 'DS'
                    break
                else:
                    print("Invalid choice. Please select 1-4.")
        
        # Update the module
        cursor.execute('''
        UPDATE modules 
        SET module_name = ?, module_type = ?
        WHERE module_code = ?
        ''', (new_name, new_type, module_code))
        
        # Update module name in student_modules table
        if new_name != module[1]:
            cursor.execute('''
            UPDATE student_modules 
            SET module_name = ?
            WHERE module_code = ?
            ''', (new_name, module_code))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code}' updated successfully!")
        print(f"New name: {new_name}")
        print(f"New type: {new_type}")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error editing module: {e}")
        input("\nPress Enter to continue...")
        return False


def delete_module():
    """Delete a module from the system"""
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to delete modules.")
        return False
    
    if not auth.check_permission('manage_modules'):
        print("You don't have permission to delete modules.")
        return False
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("\nDelete Module")
        print("=" * 30)
        
        # Display all modules
        cursor.execute('''
        SELECT module_code, module_name, module_type 
        FROM modules 
        ORDER BY module_type, module_code
        ''')
        
        modules = cursor.fetchall()
        
        if not modules:
            print("No modules found in the system.")
            conn.close()
            input("\nPress Enter to continue...")
            return False
        
        print("\nExisting Modules:")
        print(f"{'Code':<10} {'Name':<40} {'Type':<15}")
        print("-" * 70)
        
        for module in modules:
            print(f"{module[0]:<10} {module[1]:<40} {module[2]:<15}")
        
        # Get module to delete
        while True:
            module_code = input("\nEnter module code to delete (or 'cancel' to exit): ").strip().upper()
            
            if module_code.lower() == 'cancel':
                print("Delete operation cancelled.")
                conn.close()
                return False
            
            cursor.execute("SELECT * FROM modules WHERE module_code = ?", (module_code,))
            module = cursor.fetchone()
            
            if not module:
                print(f"Error: Module code '{module_code}' not found.")
                continue
            
            break
        
        # Check if module is assigned to any students
        cursor.execute('''
        SELECT COUNT(*) FROM student_modules WHERE module_code = ?
        ''', (module_code,))
        
        student_count = cursor.fetchone()[0]
        
        if student_count > 0:
            print(f"\nWarning: This module is currently assigned to {student_count} student(s).")
            print("Deleting this module will remove it from all student records.")
        
        # Confirm deletion
        print(f"\nAre you sure you want to delete module '{module_code} - {module[1]}'?")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        
        if confirm != 'yes':
            print("Delete operation cancelled.")
            conn.close()
            return False
        
        # Delete module from student_modules first (foreign key constraint)
        cursor.execute('''
        DELETE FROM student_modules WHERE module_code = ?
        ''', (module_code,))
        
        # Delete module from modules table
        cursor.execute('''
        DELETE FROM modules WHERE module_code = ?
        ''', (module_code,))
        
        conn.commit()
        conn.close()
        
        print(f"\nModule '{module_code}' deleted successfully!")
        if student_count > 0:
            print(f"Module removed from {student_count} student record(s).")
        input("\nPress Enter to continue...")
        return True
        
    except sqlite3.IntegrityError as e:
        print(f"Cannot delete module: {e}")
        print("This module may be referenced in other tables.")
        input("\nPress Enter to continue...")
        return False
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        input("\nPress Enter to continue...")
        return False
    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error deleting module: {e}")
        input("\nPress Enter to continue...")
        return False


def search_module_by_module_name():
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return
    
    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or 
            auth.check_permission('view_assigned_modules') or 
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return
    
    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
        
        # Ask the user for the name of the module to search for
        module_name = input("Enter the name of the module to search for: ")
        
        # Find the module code that matches the name
        cursor.execute('''
        SELECT module_code, module_name FROM modules
        WHERE LOWER(module_name) LIKE LOWER(?)
        ''', (f"%{module_name}%",))
        
        modules = cursor.fetchall()
        
        if not modules:
            # Try searching in the module dictionary if not found in database
            found_modules = []
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]
            
            for module in all_modules:
                if module_name.lower() in module['name'].lower():
                    found_modules.append((module['code'], module['name']))
            
            if not found_modules:
                print("No module was found with that name.")
                conn.close()
                return
            else:
                modules = found_modules
        
        # If multiple modules match, let the user choose
        if len(modules) > 1:
            print("Multiple modules found:")
            for i, module in enumerate(modules):
                print(f"{i+1}. {module[0]} - {module[1]}")
            
            choice = input("Enter the number of the module you want to view: ")
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(modules):
                    raise ValueError
                module_code = modules[index][0]
                module_name = modules[index][1]
            except (ValueError, IndexError):
                print("Error: Invalid choice.")
                conn.close()
                return
        else:
            module_code = modules[0][0]
            module_name = modules[0][1]
        
        # Display the data associated with the module
        print(f"\nModule Code: {module_code}")
        print(f"Module Name: {module_name}")
        print("Students taking this module:")
        
        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))
        
        students = cursor.fetchall()
        
        if not students:
            print("No students are currently taking this module.")
        else:
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)
        
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")


def search_module_by_module_code():
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search module information.")
        return
    
    # Check for appropriate permissions
    if not (auth.check_permission('manage_modules') or 
            auth.check_permission('view_assigned_modules') or 
            auth.check_permission('view_any_student')):
        print("You don't have permission to search module information.")
        return
    
    # First check if the modules table exists - if not, initialize the database
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Check if the modules table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
        if not cursor.fetchone():
            conn.close()
            init_db()  # Initialize the database if it doesn't exist
            conn = get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
        
        # ask the user to input the module code
        module_code = input("Enter the module code: ")
        
        # check if the module code is valid
        cursor.execute('''
        SELECT module_name FROM modules
        WHERE module_code = ?
        ''', (module_code,))
        
        module = cursor.fetchone()
        
        if not module:
            # Try searching in the module dictionary if not found in database
            module_name = None
            all_modules = [
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
            ]
            
            for mod in all_modules:
                if mod['code'] == module_code:
                    module_name = mod['name']
                    break
            
            if not module_name:
                print("Invalid module code")
                conn.close()
                return
            else:
                # display module name
                print(f"Module name: {module_name}")
                print("No students are currently taking this module.")
                conn.close()
                return
        
        # display module name
        print(f"Module name: {module[0]}")
        
        # Find students taking this module
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.middle_name, s.last_name
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        WHERE sm.module_code = ?
        ''', (module_code,))
        
        students = cursor.fetchall()
        
        if not students:
            print("No students are currently taking this module.")
        else:
            print("Students taking this module:")
            for student in students:
                print(f"Student ID: {student[0]}")
                print(f"Name: {student[1]} {student[2]} {student[3]}")
                print("-" * 30)
        
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        print("Initializing database...")
        init_db()
        print("Please try your search again.")


def display_module_management_menu():
    auth = get_auth()
    
    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to access module management.")
        return
    
    if not (auth.check_permission('manage_modules') or auth.check_permission('view_assigned_modules')):
        print("You don't have permission to access module management.")
        return
    
    while True:
        print("\nModule Management Menu:")
        print("=======================")
        
        # Show options based on permissions
        options = []
        option_num = 1
        
        if auth.check_permission('manage_modules'):
            print(f"{option_num}. Create new module")
            options.append('create_module')
            option_num += 1
            
            print(f"{option_num}. Edit module")
            options.append('edit_module')
            option_num += 1
            
            print(f"{option_num}. Delete module")
            options.append('delete_module')
            option_num += 1
        
        print(f"{option_num}. Search module by name")
        options.append('search_module_name')
        option_num += 1
        
        print(f"{option_num}. Search module by code")
        options.append('search_module_code')
        option_num += 1
        
        print(f"{option_num}. Return to Main Menu")
        
        choice = input("Enter your choice: ")
        
        try:
            choice_num = int(choice)
            
            # Handle the choice based on dynamic menu
            if choice_num > 0 and choice_num <= len(options):
                selected_option = options[choice_num - 1]
                
                if selected_option == 'create_module':
                    create_module()
                elif selected_option == 'edit_module':
                    edit_module()
                elif selected_option == 'delete_module':
                    delete_module()
                elif selected_option == 'search_module_name':
                    search_module_by_module_name()
                elif selected_option == 'search_module_code':
                    search_module_by_module_code()
            elif choice_num == option_num:  # Return to Main Menu
                return
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a valid number.")


__all__ = [
    'create_module',
    'edit_module',
    'delete_module',
    'search_module_by_module_name',
    'search_module_by_module_code',
    'display_module_management_menu',
]
