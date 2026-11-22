from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime


def manage_sla_policies(auth):
    """Manage SLA policies"""
    print("\nSLA Policy Management")
    print("====================")
    print("1. View SLA policies")
    print("2. Create new SLA policy")
    print("3. Edit SLA policy")
    print("4. Activate/Deactivate SLA policy")
    print("5. Return to system management")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        view_sla_policies()
    elif choice == '2':
        create_sla_policy(auth)
    elif choice == '3':
        edit_sla_policy(auth)
    elif choice == '4':
        toggle_sla_policy(auth)

def view_sla_policies():
    """View existing SLA policies"""
    conn = get_connection()
    cursor = conn.cursor()

    has_team = 'team' in {r[1] for r in cursor.execute("PRAGMA table_info(sla_policies)")}
    cursor.execute(f'''
    SELECT sla_id, name, priority, impact, urgency, first_response_hours,
           resolution_hours, escalation_hours, business_hours_only, is_active,
           {'team' if has_team else 'NULL'}
    FROM sla_policies
    ORDER BY priority, impact, urgency
    ''')  # nosec B608 - fixed column name

    policies = cursor.fetchall()

    if policies:
        print("\nSLA Policies:")
        print("=" * 120)
        print(f"{'ID':<5} {'Name':<25} {'P/I/U':<10} {'Response':<8} {'Resolution':<10} {'Escalation':<10} {'Business':<8} {'Active':<6} {'Team':<18}")
        print("=" * 120)

        for policy in policies:
            p_i_u = f"{policy[2]}/{policy[3]}/{policy[4]}"
            business = "Yes" if policy[8] else "No"
            active = "Yes" if policy[9] else "No"

            print(f"{policy[0]:<5} {policy[1][:23]:<25} {p_i_u:<10} {policy[5]:<8}h "
                  f"{policy[6]:<10}h {policy[7]:<10}h {business:<8} {active:<6} "
                  f"{policy[10] or 'all teams':<18}")

        print("=" * 120)
    else:
        print("No SLA policies found.")

    conn.close()

def create_sla_policy(auth):
    """Create new SLA policy"""
    print("\nCreate New SLA Policy")
    print("====================")

    name = input("Policy name: ").strip()
    if not name:
        print("Name is required.")
        return

    description = input("Description: ").strip()

    # Priority, impact, urgency
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.creation import get_priority_selection, get_impact_selection, get_urgency_selection
    priority = get_priority_selection()
    impact = get_impact_selection()
    urgency = get_urgency_selection()

    # Time targets
    try:
        first_response = int(input("First response time (hours): ").strip())
        resolution = int(input("Resolution time (hours): ").strip())
        escalation = int(input("Escalation time (hours): ").strip())
    except ValueError:
        print("Invalid time values.")
        return

    business_hours = input("Business hours only? (y/n): ").strip().lower() == 'y'

    # A policy can be for one support team (student_support.routing) or all.
    from education_system.systems.university.domains.student_support.domain.student_support import routing
    print("Teams: " + ", ".join(t['key'] for t in routing.teams()))
    team_text = input("Team (blank = all teams): ").strip()
    team = routing.team_key(team_text) if team_text else None
    if team_text and not team:
        print("Unknown team.")
        return

    # Save policy
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO sla_policies
        (name, description, priority, impact, urgency, first_response_hours,
         resolution_hours, escalation_hours, business_hours_only, created_at, team)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, priority, impact, urgency, first_response,
              resolution, escalation, business_hours, now, team))

        conn.commit()
        sla_id = cursor.lastrowid

        print(f"\nSLA Policy #{sla_id} created successfully!")

    except sqlite3.Error as e:
        print(f"Error creating SLA policy: {e}")
    finally:
        conn.close()

def edit_sla_policy(auth):
    """Edit an existing SLA policy"""
    view_sla_policies()

    policy_id = input("\nEnter SLA policy ID to edit: ").strip()

    try:
        policy_id = int(policy_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM sla_policies WHERE sla_id = ?
        ''', (policy_id,))

        policy = cursor.fetchone()
        if not policy:
            print("SLA policy not found.")
            conn.close()
            return

        print(f"\nEditing SLA Policy: {policy['name']}")
        print(f"Current Response Time: {policy['first_response_hours']} hours")
        print(f"Current Resolution Time: {policy['resolution_hours']} hours")
        print(f"Current Escalation Time: {policy['escalation_hours']} hours")

        new_response = input(f"New response time (current: {policy['first_response_hours']}): ").strip()
        new_resolution = input(f"New resolution time (current: {policy['resolution_hours']}): ").strip()
        new_escalation = input(f"New escalation time (current: {policy['escalation_hours']}): ").strip()

        updates = []
        params = []

        if new_response:
            updates.append("first_response_hours = ?")
            params.append(int(new_response))

        if new_resolution:
            updates.append("resolution_hours = ?")
            params.append(int(new_resolution))

        if new_escalation:
            updates.append("escalation_hours = ?")
            params.append(int(new_escalation))

        if updates:
            params.append(policy_id)
            cursor.execute(
                'UPDATE sla_policies SET ' + ", ".join(updates) + ' WHERE sla_id = ?',
                params)

            conn.commit()
            print("SLA policy updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing SLA policy: {e}")

def toggle_sla_policy(auth):
    """Activate or deactivate an SLA policy"""
    view_sla_policies()

    policy_id = input("\nEnter SLA policy ID to toggle: ").strip()

    try:
        policy_id = int(policy_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT name, is_active FROM sla_policies WHERE sla_id = ?
        ''', (policy_id,))

        result = cursor.fetchone()
        if not result:
            print("SLA policy not found.")
            conn.close()
            return

        name, is_active = result
        new_status = not is_active

        cursor.execute('''
        UPDATE sla_policies SET is_active = ? WHERE sla_id = ?
        ''', (new_status, policy_id))

        conn.commit()
        conn.close()

        status_text = "activated" if new_status else "deactivated"
        print(f"SLA policy '{name}' has been {status_text}.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Error toggling SLA policy: {e}")
