from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import get_user_student_id


def view_insurance_info(auth):
    if not (auth.check_permission('update_insurance_info') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to view insurance information.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return
        
        print(f"Insurance information for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    cursor.execute('''
    SELECT insurance_provider, policy_number, group_number, subscriber_name,
           relationship_to_subscriber, effective_date, expiry_date, created_at
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC
    ''', (student_id,))
    
    insurance_records = cursor.fetchall()
    
    if not insurance_records:
        print("No insurance information found.")
        conn.close()
        return
    
    print("\n===== Insurance Information =====")
    for record in insurance_records:
        provider, policy_num, group_num, subscriber, relationship, effective, expiry, created = record
        
        print(f"\nInsurance Provider: {provider}")
        print(f"Policy Number: {policy_num}")
        print(f"Group Number: {group_num}")
        print(f"Subscriber: {subscriber}")
        print(f"Relationship: {relationship}")
        print(f"Effective Date: {effective}")
        print(f"Expiry Date: {expiry}")
        print(f"Last Updated: {created}")
        
        # Check if expired
        today = datetime.now().strftime('%Y-%m-%d')
        if expiry and expiry < today:
            print("⚠️  EXPIRED - Update needed")
        elif expiry and (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days <= 30:
            print("🟡 EXPIRES SOON")
        else:
            print("✅ CURRENT")
        
        print("-" * 30)
    
    conn.close()



def update_insurance_info(auth):
    if not (auth.check_permission('update_insurance_info') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to update insurance information.")
        return
    
    backup_before_operation('update_insurance_info')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return
        
        print(f"Updating insurance for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    # Check if insurance record exists
    cursor.execute('''
    SELECT id, insurance_provider, policy_number, group_number
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC LIMIT 1
    ''', (student_id,))
    
    existing_record = cursor.fetchone()
    
    if existing_record:
        print(f"\nCurrent insurance: {existing_record[1]} (Policy: {existing_record[2]})")
        update_existing = input("Update existing record? (y/n): ").lower()
        if update_existing == 'y':
            insurance_id = existing_record[0]
        else:
            insurance_id = None
    else:
        insurance_id = None
    
    insurance_provider = input("Insurance provider: ")
    policy_number = input("Policy number: ")
    group_number = input("Group number: ")
    subscriber_name = input("Subscriber name: ")
    
    relationships = ['Self', 'Parent', 'Spouse', 'Guardian', 'Other']
    print("\nRelationship to subscriber:")
    for i, relationship in enumerate(relationships):
        print(f"{i+1}. {relationship}")
    
    while True:
        rel_choice = input("\nSelect relationship (1-5): ")
        if rel_choice.isdigit() and 1 <= int(rel_choice) <= len(relationships):
            relationship_to_subscriber = relationships[int(rel_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        effective_date = input("Effective date (YYYY-MM-DD): ")
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD): ")
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if insurance_id:
        # Update existing record
        cursor.execute('''
        UPDATE insurance_information 
        SET insurance_provider = ?, policy_number = ?, group_number = ?,
            subscriber_name = ?, relationship_to_subscriber = ?, effective_date = ?,
            expiry_date = ?, created_at = ?
        WHERE id = ?
        ''', (insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at, insurance_id))
        
        log_audit_event(auth.current_user['id'], 'update_insurance_info', 'insurance', insurance_id, conn=conn)
        print("\nInsurance information updated successfully!")
    else:
        # Create new record
        cursor.execute('''
        INSERT INTO insurance_information 
        (student_id, insurance_provider, policy_number, group_number, subscriber_name,
         relationship_to_subscriber, effective_date, expiry_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at))
        
        log_audit_event(auth.current_user['id'], 'add_insurance_info', 'insurance', cursor.lastrowid, conn=conn)
        print("\nInsurance information added successfully!")
    
    conn.commit()
    conn.close()



