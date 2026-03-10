from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event


def show_quality_metrics(auth):
    """Delegate to Quality Assurance module."""
    try:
        from education_system.university_system.modules.domain.health.records.quality_assurance import show_quality_metrics as _show
        return _show(auth)
    except Exception as e:
        print(f"Quality metrics unavailable: {e}")
        input("\nPress Enter to return...")



def patient_safety_metrics(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view patient safety metrics.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Patient Safety Metrics =====")
    
    # Adverse events tracking
    print("ADVERSE EVENTS")
    print("-" * 15)
    
    # Vaccination adverse reactions
    cursor.execute('''
    SELECT 
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN adverse_reaction = 1 THEN 1 ELSE 0 END) as adverse_reactions
    FROM vaccination_records
    WHERE administered_date >= date('now', '-90 days')
    ''')
    
    vax_safety = cursor.fetchone()
    if vax_safety[0] > 0:
        adverse_rate = (vax_safety[1] / vax_safety[0] * 100)
        print(f"Vaccination Adverse Reaction Rate: {adverse_rate:.2f}%")
        
        if adverse_rate <= 1:
            print("  ✅ Within acceptable range")
        elif adverse_rate <= 2:
            print("  🟡 Monitor closely")
        else:
            print("  🔴 High adverse reaction rate - Investigate")
    
    # Medication safety indicators
    print("\nMEDICATION SAFETY")
    print("-" * 17)
    
    # Students with drug allergies on active medications
    cursor.execute('''
    SELECT COUNT(DISTINCT p.student_id)
    FROM prescriptions p
    JOIN allergies a ON p.student_id = a.student_id
    WHERE p.status = 'active' AND a.verified = 1
    ''')
    
    potential_interactions = cursor.fetchone()[0]
    print(f"Patients with allergies on active medications: {potential_interactions}")
    
    if potential_interactions > 0:
        print("  ⚠️  Requires medication review for interactions")
    else:
        print("  ✅ No obvious allergy conflicts")
    
    # Critical lab values follow-up
    print("\nCRITICAL VALUES MANAGEMENT")
    print("-" * 25)
    
    cursor.execute('''
    SELECT COUNT(*)
    FROM lab_results
    WHERE abnormal_flag IN ('H', 'L') 
    AND resulted_date >= date('now', '-7 days')
    ''')
    
    critical_values = cursor.fetchone()[0]
    print(f"Critical lab values (last 7 days): {critical_values}")
    
    if critical_values > 0:
        print("  ⚠️  Ensure all critical values have provider follow-up")
    
    # Emergency contact completeness
    print("\nEMERGENCY PREPAREDNESS")
    print("-" * 22)
    
    cursor.execute('''
    SELECT 
        COUNT(DISTINCT s.student_id) as total_students,
        COUNT(DISTINCT ec.student_id) as with_emergency_contacts
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    ''')
    
    emergency_data = cursor.fetchone()
    if emergency_data[0] > 0:
        emergency_completeness = (emergency_data[1] / emergency_data[0] * 100)
        print(f"Students with Emergency Contacts: {emergency_completeness:.1f}%")
        
        if emergency_completeness >= 95:
            print("  ✅ Excellent emergency preparedness")
        elif emergency_completeness >= 85:
            print("  🟡 Good emergency preparedness")
        else:
            print("  🔴 Poor emergency preparedness")
    
    # Data security indicators
    print("\nDATA SECURITY")
    print("-" * 13)
    
    # Recent audit trail activity
    cursor.execute('''
    SELECT COUNT(DISTINCT user_id)
    FROM audit_trail
    WHERE timestamp >= datetime('now', '-24 hours')
    ''')
    
    active_users = cursor.fetchone()[0]
    print(f"Active users (last 24 hours): {active_users}")
    
    # Failed login attempts
    cursor.execute('''
    SELECT COUNT(*)
    FROM audit_trail
    WHERE action = 'failed_login' 
    AND timestamp >= datetime('now', '-24 hours')
    ''')
    
    failed_logins = cursor.fetchone()[0]
    print(f"Failed login attempts (last 24 hours): {failed_logins}")
    
    if failed_logins > 10:
        print("  🔴 High number of failed login attempts")
    elif failed_logins > 5:
        print("  🟡 Monitor login security")
    else:
        print("  ✅ Normal login activity")
    
    conn.close()



