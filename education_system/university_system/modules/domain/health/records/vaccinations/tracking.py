from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import get_user_student_id


def vaccination_due_list(auth):
    """List of students with vaccinations due"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get vaccinations expiring in next 60 days
    sixty_days = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT vr.vaccine_name, vr.expiry_date, s.first_name, s.last_name, s.student_id
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.expiry_date BETWEEN ? AND ? AND vr.verified = 1
    ORDER BY vr.expiry_date
    ''', (today, sixty_days))
    
    due_vaccinations = cursor.fetchall()
    
    print("\n===== Vaccinations Due (Next 60 Days) =====")
    
    if not due_vaccinations:
        print("No vaccinations due in the next 60 days.")
        conn.close()
        return
    
    for vaccine, expiry, first_name, last_name, student_id in due_vaccinations:
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        days_until = (expiry_date - datetime.now()).days
        
        if days_until <= 0:
            urgency = "🔴 EXPIRED"
        elif days_until <= 14:
            urgency = "🟡 DUE SOON"
        else:
            urgency = "ℹ️ UPCOMING"
        
        print(f"\n{urgency}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Vaccine: {vaccine}")
        print(f"Expires: {expiry} ({days_until} days)")
    
    print(f"\nTotal students needing vaccination: {len(due_vaccinations)}")
    
    # Option to generate reminder list
    generate_reminders = input("\nGenerate vaccination reminder list? (y/n): ").lower()
    if generate_reminders == 'y':
        print("Vaccination reminder list generated for nursing staff.")
    
    conn.close()



def immunization_status(auth):
    """Show immunization status"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Your Immunization Status =====")
    
    # Get vaccination records
    cursor.execute('''
    SELECT vaccine_name, administered_date, expiry_date, verified
    FROM vaccination_records
    WHERE student_id = ?
    ORDER BY administered_date DESC
    ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    
    if not vaccinations:
        print("No vaccination records found.")
        conn.close()
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    for vaccine, admin_date, expiry_date, verified in vaccinations:
        status = "✅ Current"
        if expiry_date and expiry_date < today:
            status = "🔴 Expired"
        elif expiry_date and (datetime.strptime(expiry_date, '%Y-%m-%d') - datetime.now()).days <= 90:
            status = "🟡 Expiring Soon"
        
        verification = "✅ Verified" if verified else "⏳ Pending Verification"
        
        print(f"\n{vaccine}")
        print(f"  Administered: {admin_date}")
        print(f"  Expires: {expiry_date}")
        print(f"  Status: {status}")
        print(f"  Verification: {verification}")
    
    conn.close()



