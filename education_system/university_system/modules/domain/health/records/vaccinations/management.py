from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import get_user_student_id


def record_vaccination(auth):
    if not auth.check_permission('manage_vaccinations'):
        print("You don't have permission to record vaccinations.")
        return
    
    backup_before_operation('record_vaccination')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    print(f"Recording vaccination for: {student[0]} {student[1]}")
    
    # Common vaccines
    common_vaccines = [
        'COVID-19',
        'Influenza (Flu)',
        'Hepatitis A',
        'Hepatitis B',
        'Measles, Mumps, Rubella (MMR)',
        'Meningococcal',
        'Tetanus, Diphtheria, Pertussis (Tdap)',
        'Varicella (Chickenpox)',
        'HPV',
        'Other'
    ]
    
    print("\nCommon Vaccines:")
    for i, vaccine in enumerate(common_vaccines):
        print(f"{i+1}. {vaccine}")
    
    while True:
        vaccine_choice = input("\nSelect vaccine (1-10): ")
        if vaccine_choice.isdigit() and 1 <= int(vaccine_choice) <= len(common_vaccines):
            vaccine_name = common_vaccines[int(vaccine_choice) - 1]
            if vaccine_name == 'Other':
                vaccine_name = input("Enter vaccine name: ")
            break
        print("Invalid choice. Please try again.")
    
    while True:
        administered_date = input("Administered date (YYYY-MM-DD) [today]: ").strip()
        if not administered_date:
            administered_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(administered_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    # Calculate expiry date based on vaccine type
    expiry_periods = {
        'COVID-19': 365,  # 1 year
        'Influenza (Flu)': 365,  # Annual
        'Hepatitis A': 365 * 10,  # 10 years
        'Hepatitis B': 365 * 20,  # 20 years lifetime
        'Measles, Mumps, Rubella (MMR)': 365 * 20,  # Lifetime
        'Meningococcal': 365 * 5,  # 5 years
        'Tetanus, Diphtheria, Pertussis (Tdap)': 365 * 10,  # 10 years
        'Varicella (Chickenpox)': 365 * 20,  # Lifetime
        'HPV': 365 * 10  # 10+ years
    }
    
    if vaccine_name in expiry_periods:
        expiry_date = (datetime.strptime(administered_date, '%Y-%m-%d') + 
                      timedelta(days=expiry_periods[vaccine_name])).strftime('%Y-%m-%d')
    else:
        while True:
            expiry_date = input("Expiry date (YYYY-MM-DD): ")
            try:
                datetime.strptime(expiry_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
    
    lot_number = input("Lot number: ")
    manufacturer = input("Manufacturer: ")
    administered_by = input(f"Administered by [Dr. {auth.current_user['username']}]: ").strip()
    if not administered_by:
        administered_by = f"Dr. {auth.current_user['username']}"
    
    location = input("Administration site (e.g., left arm): ")
    
    # Check for allergies
    cursor.execute('''
    SELECT allergen, severity FROM allergies 
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    
    allergies = cursor.fetchall()
    if allergies:
        print("\n⚠️  ALLERGY ALERT - Patient has verified allergies:")
        for allergen, severity in allergies:
            print(f"- {allergen} ({severity})")
        
        proceed = input("\nHave you checked for vaccine contraindications? (y/n): ").lower()
        if proceed != 'y':
            print("Please check for contraindications before administering vaccine.")
            conn.close()
            return
    
    # Record any adverse reactions
    adverse_reaction = input("Any adverse reactions? (y/n): ").lower() == 'y'
    reaction_description = ""
    if adverse_reaction:
        reaction_description = input("Describe adverse reaction: ")
    
    verified = 1 if auth.current_user['role'] == 'health_provider' else 0
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO vaccination_records 
    (student_id, vaccine_name, administered_date, expiry_date, lot_number, 
     manufacturer, administered_by, location, adverse_reaction, reaction_description, 
     verified, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, vaccine_name, administered_date, expiry_date, lot_number,
          manufacturer, administered_by, location, 1 if adverse_reaction else 0,
          reaction_description, verified, created_at))
    
    conn.commit()
    vaccination_id = cursor.lastrowid
    
    log_audit_event(auth.current_user['id'], 'record_vaccination', 'vaccination', vaccination_id)
    
    print(f"\nVaccination recorded successfully!")
    print(f"Vaccination ID: {vaccination_id}")
    print(f"Expires: {expiry_date}")
    
    if adverse_reaction:
        print("⚠️  ADVERSE REACTION REPORTED - Monitor patient closely")
        log_audit_event(auth.current_user['id'], 'vaccination_adverse_reaction', 'vaccination', vaccination_id,
                       reaction_description)
    
    conn.close()



def view_vaccinations(auth):
    if not (auth.check_permission('view_own_vaccinations') or auth.check_permission('manage_vaccinations') or 
            auth.check_permission('view_any_health_record')):
        print("You don't have permission to view vaccination records.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record') or auth.check_permission('manage_vaccinations'):
        student_id = input("Enter student ID (leave blank for all): ").strip()
        
        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return
            
            cursor.execute('''
            SELECT id, vaccine_name, administered_date, expiry_date, lot_number,
                   manufacturer, administered_by, location, adverse_reaction,
                   reaction_description, verified
            FROM vaccination_records
            WHERE student_id = ?
            ORDER BY administered_date DESC
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT vr.id, s.student_id, s.first_name, s.last_name, vr.vaccine_name,
                   vr.administered_date, vr.expiry_date, vr.verified
            FROM vaccination_records vr
            JOIN students s ON vr.student_id = s.student_id
            ORDER BY vr.administered_date DESC
            LIMIT 100
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
        
        cursor.execute('''
        SELECT id, vaccine_name, administered_date, expiry_date, lot_number,
               manufacturer, administered_by, location, adverse_reaction,
               reaction_description, verified
        FROM vaccination_records
        WHERE student_id = ?
        ORDER BY administered_date DESC
        ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    
    if not vaccinations:
        print("No vaccination records found.")
        conn.close()
        return
    
    print("\n===== Vaccination Records =====")
    for vaccination in vaccinations:
        if (auth.check_permission('view_any_health_record') or auth.check_permission('manage_vaccinations')) and not student_id:
            # All vaccinations view
            vax_id, student_id_val, first_name, last_name, vaccine_name, admin_date, expiry_date, verified = vaccination
            print(f"\nID: {vax_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id_val})")
            print(f"Vaccine: {vaccine_name}")
            print(f"Date: {admin_date}")
            print(f"Expires: {expiry_date}")
            print(f"Verified: {'Yes' if verified else 'No'}")
        else:
            # Specific student view
            vax_id, vaccine_name, admin_date, expiry_date, lot_number, manufacturer, admin_by, location, adverse, reaction_desc, verified = vaccination
            print(f"\nID: {vax_id}")
            print(f"Vaccine: {vaccine_name}")
            print(f"Administered: {admin_date}")
            print(f"Expires: {expiry_date}")
            print(f"Lot Number: {lot_number}")
            print(f"Manufacturer: {manufacturer}")
            print(f"Administered by: {admin_by}")
            print(f"Location: {location}")
            print(f"Verified: {'Yes' if verified else 'No'}")
            
            if adverse:
                print(f"⚠️  Adverse Reaction: {reaction_desc}")
        
        # Check expiration status
        today = datetime.now().strftime('%Y-%m-%d')
        if expiry_date and expiry_date < today:
            print("🔴 EXPIRED - Renewal needed")
        elif expiry_date and (datetime.strptime(expiry_date, '%Y-%m-%d') - datetime.now()).days <= 90:
            print("🟡 EXPIRES SOON - Consider renewal")
        else:
            print("✅ CURRENT")
        
        print("-" * 30)
    
    conn.close()



def verify_vaccination(auth):
    if not auth.check_permission('verify_vaccinations'):
        print("You don't have permission to verify vaccinations.")
        return
    
    backup_before_operation('verify_vaccination')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    vaccination_id = input("Enter vaccination ID to verify: ")
    
    cursor.execute('''
    SELECT vr.id, s.student_id, s.first_name, s.last_name, vr.vaccine_name,
           vr.administered_date, vr.administered_by, vr.verified
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.id = ?
    ''', (vaccination_id,))
    
    vaccination = cursor.fetchone()
    
    if not vaccination:
        print("Error: Vaccination record not found.")
        conn.close()
        return
    
    vax_id, student_id, first_name, last_name, vaccine_name, admin_date, admin_by, verified = vaccination
    
    print(f"\nVaccination to verify:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Vaccine: {vaccine_name}")
    print(f"Date: {admin_date}")
    print(f"Administered by: {admin_by}")
    print(f"Current Status: {'Verified' if verified else 'Unverified'}")
    
    if verified:
        print("This vaccination is already verified.")
        conn.close()
        return
    
    # Verification process
    print("\nVerification Checklist:")
    print("1. Documentation reviewed")
    print("2. Provider credentials confirmed")
    print("3. Vaccine details validated")
    
    verify = input("\nVerify this vaccination record? (y/n): ").lower()
    if verify != 'y':
        print("Verification cancelled.")
        conn.close()
        return
    
    cursor.execute('''
    UPDATE vaccination_records 
    SET verified = 1, verified_by = ?, verified_date = ?
    WHERE id = ?
    ''', (auth.current_user['username'], datetime.now().strftime('%Y-%m-%d'), vaccination_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'verify_vaccination', 'vaccination', vaccination_id)
    
    print("\nVaccination record verified successfully!")
    conn.close()



