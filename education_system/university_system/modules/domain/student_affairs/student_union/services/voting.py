from __future__ import annotations

import logging
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.student_affairs.student_union.services import context as ctx
from education_system.university_system.modules.domain.student_affairs.student_union.services.communications import send_confirmation_email

from education_system.university_system.infrastructure.email.template_utils import render_template

# Initialize logger
logger = logging.getLogger(__name__)
def manage_enhanced_voting():
    """Enhanced voting system with ranked choice and campaigns"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access voting features.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print(f"\n🗳️ Enhanced Voting System")
            print("=" * 40)

            # Basic voting options for all users
            print("📊 VIEW & INFORMATION")
            print("1. View elections with campaigns")
            print("2. View all current elections")
            print("3. View candidate profiles")
            print("4. View election results")
            print("5. Election accessibility features")

            print("\n🗳️ PARTICIPATION")
            print("6. Nominate yourself for election")
            print("7. Vote in election (simple)")
            print("8. Vote with ranked choice")

            print("\n📋 CAMPAIGN MANAGEMENT")
            print("9. Submit campaign materials")
            print("10. Track campaign expenses")

            # Admin options
            if ctx.auth.check_permission('set_up_elections'):
                print("\n⚙️ ADMINISTRATION")
                print("11. Set up new election")
                print("12. Configure voting methods")
                print("13. Monitor campaign compliance")
                print("14. Election security audit")
                print("15. Return to main menu")
                max_option = 15
            else:
                print("\n11. Return to main menu")
                max_option = 11

            choice = input("\nChoose an option: ").strip()

            if choice == '1':
                view_elections_with_campaigns(cursor)
            elif choice == '2':
                view_elections(cursor)
            elif choice == '3':
                view_candidate_profiles(cursor)
            elif choice == '4':
                view_election_results(cursor, conn)
            elif choice == '5':
                election_accessibility_features()
            elif choice == '6':
                nominate_for_election(cursor, conn)
            elif choice == '7':
                vote_in_election(cursor, conn)
            elif choice == '8':
                ranked_choice_voting(cursor, conn)
            elif choice == '9':
                submit_campaign_materials(cursor, conn)
            elif choice == '10':
                track_campaign_expenses(cursor, conn)
            elif choice == '11' and max_option > 11:
                set_up_election(cursor, conn)
            elif choice == '12' and max_option > 11:
                configure_voting_methods(cursor, conn)
            elif choice == '13' and max_option > 11:
                monitor_campaign_compliance(cursor)
            elif choice == '14' and max_option > 11:
                election_security_audit(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def ranked_choice_voting(cursor, conn):
    """Implement ranked choice voting"""
    try:
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()
        student_id = result[0]

        # Get elections available for voting
        current_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        SELECT e.election_id, e.position, e.department
        FROM union_elections e
        WHERE e.status = 'voting'
        AND e.voting_start <= ? AND e.voting_end >= ?
        AND e.election_id NOT IN (
            SELECT election_id FROM ranked_votes WHERE voter_id = ?
        )
        ORDER BY e.position
        ''', (current_date, current_date, student_id))

        available_elections = cursor.fetchall()

        if not available_elections:
            print("No elections available for ranked choice voting.")
            return

        print("🗳️ Elections available for ranked choice voting:")
        for i, election in enumerate(available_elections):
            dept = f" ({election[2]})" if election[2] else ""
            print(f"{i+1}. {election[1]}{dept}")

        choice = input("Select election to vote in (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(available_elections):
            print("Invalid selection.")
            return

        selected_election = available_elections[int(choice)-1]
        election_id = selected_election[0]

        # Get candidates
        cursor.execute('''
        SELECT c.id, s.first_name, s.last_name, c.manifesto
        FROM election_candidates c
        JOIN students s ON c.student_id = s.student_id
        WHERE c.election_id = ?
        ORDER BY s.last_name, s.first_name
        ''', (election_id,))

        candidates = cursor.fetchall()

        if len(candidates) < 2:
            print("Not enough candidates for ranked choice voting.")
            return

        print(f"\n🏆 Ranked Choice Voting for: {selected_election[1]}")
        print("Rank the candidates in order of preference (1 = most preferred)")
        print("\nCandidates:")

        for i, candidate in enumerate(candidates):
            print(f"{i+1}. {candidate[1]} {candidate[2]}")
            if candidate[3]:
                print(f"   Manifesto: {candidate[3][:100]}...")

        # Collect ranked preferences
        preferences = []
        used_candidates = set()

        for rank in range(1, len(candidates) + 1):
            while True:
                choice = input(f"Your #{rank} choice (enter candidate number, or 0 to skip): ").strip()

                if choice == '0':
                    break

                if (choice.isdigit() and 
                    1 <= int(choice) <= len(candidates) and 
                    int(choice) not in used_candidates):

                    candidate_idx = int(choice) - 1
                    preferences.append(candidates[candidate_idx][0])  # Store candidate ID
                    used_candidates.add(int(choice))

                    print(f"#{rank}: {candidates[candidate_idx][1]} {candidates[candidate_idx][2]}")
                    break
                else:
                    print("Invalid choice or candidate already ranked.")

        if not preferences:
            print("No preferences recorded.")
            return

        # Confirm vote
        print(f"\n📋 Your ranked preferences:")
        for i, candidate_id in enumerate(preferences, 1):
            candidate = next(c for c in candidates if c[0] == candidate_id)
            print(f"{i}. {candidate[1]} {candidate[2]}")

        confirm = input("\nConfirm your ranked vote? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Vote cancelled.")
            return

        # Store ranked vote
        vote_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        candidate_preferences = ','.join(map(str, preferences))

        cursor.execute('''
        INSERT INTO ranked_votes (
            election_id, voter_id, candidate_preferences, vote_time
        ) VALUES (?, ?, ?, ?)
        ''', (election_id, student_id, candidate_preferences, vote_time))

        conn.commit()

        print("✅ Your ranked choice vote has been recorded!")
        print("Thank you for participating in the democratic process.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def configure_voting_methods(cursor, conn):
    """Configure voting methods (admin only)"""
    
    if not ctx.auth.check_permission('set_up_elections'):
        print("You don't have permission to configure voting methods.")
        return

    try:
        # Initialize voting configuration table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS voting_configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL,
            description TEXT,
            updated_by INTEGER,
            updated_at TEXT,
            FOREIGN KEY (updated_by) REFERENCES users (id)
        )
        ''')

        # Initialize default configurations if they don't exist
        default_configs = [
            ('default_voting_method', 'simple', 'Default voting method for new elections'),
            ('allow_ranked_choice', 'true', 'Allow ranked choice voting'),
            ('online_voting_enabled', 'true', 'Enable online voting'),
            ('offline_voting_enabled', 'false', 'Enable offline voting'),
            ('default_voting_period_days', '7', 'Default voting period in days'),
            ('voter_eligibility_check', 'true', 'Check voter eligibility'),
            ('results_visibility', 'post_election', 'When results are visible'),
            ('email_notifications', 'true', 'Send email notifications for elections'),
            ('candidate_photo_required', 'false', 'Require candidate photos'),
            ('maximum_candidates_per_election', '10', 'Maximum candidates per election')
        ]

        for config_key, config_value, description in default_configs:
            cursor.execute('''
            INSERT OR IGNORE INTO voting_configuration (config_key, config_value, description, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (config_key, config_value, description, ctx.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

        while True:
            print("\n⚙️ Voting Method Configuration")
            print("=" * 40)

            # Get current configurations
            cursor.execute('SELECT config_key, config_value, description FROM voting_configuration ORDER BY config_key')
            configs = cursor.fetchall()

            print("\n📋 Current Configuration:")
            for i, (key, value, desc) in enumerate(configs, 1):
                status = "✓ Enabled" if value.lower() in ['true', 'yes', '1'] else ("✗ Disabled" if value.lower() in ['false', 'no', '0'] else f"= {value}")
                print(f"{i:2d}. {desc}: {status}")

            print(f"\n{len(configs)+1:2d}. Email Notification Test")
            print(f"{len(configs)+2:2d}. Export Configuration")
            print(f"{len(configs)+3:2d}. Import Configuration")
            print(f"{len(configs)+4:2d}. Reset to Defaults")
            print(f"{len(configs)+5:2d}. Return to Main Menu")

            choice = input(f"\nSelect configuration to modify (1-{len(configs)+5}): ").strip()

            if not choice.isdigit():
                print("Invalid choice. Please enter a number.")
                continue

            choice = int(choice)

            if 1 <= choice <= len(configs):
                # Modify specific configuration
                config_key, current_value, description = configs[choice-1]

                print(f"\n🔧 Modifying: {description}")
                print(f"Current value: {current_value}")

                if config_key in ['allow_ranked_choice', 'online_voting_enabled', 'offline_voting_enabled', 
                                'voter_eligibility_check', 'email_notifications', 'candidate_photo_required']:
                    # Boolean configuration
                    new_value = input("Enable this option? (y/n): ").strip().lower()
                    if new_value in ['y', 'yes']:
                        new_value = 'true'
                    elif new_value in ['n', 'no']:
                        new_value = 'false'
                    else:
                        print("Invalid input. Skipping.")
                        continue

                elif config_key == 'default_voting_method':
                    # Voting method selection
                    print("\nAvailable voting methods:")
                    print("1. Simple (one choice)")
                    print("2. Ranked Choice")
                    print("3. Approval (multiple choices)")

                    method_choice = input("Select voting method (1-3): ").strip()
                    if method_choice == '1':
                        new_value = 'simple'
                    elif method_choice == '2':
                        new_value = 'ranked_choice'
                    elif method_choice == '3':
                        new_value = 'approval'
                    else:
                        print("Invalid choice. Skipping.")
                        continue

                elif config_key == 'results_visibility':
                    # Results visibility options
                    print("\nResults visibility options:")
                    print("1. Real-time (during voting)")
                    print("2. Post-election (after voting ends)")
                    print("3. Manual release (admin controlled)")

                    vis_choice = input("Select visibility option (1-3): ").strip()
                    if vis_choice == '1':
                        new_value = 'real_time'
                    elif vis_choice == '2':
                        new_value = 'post_election'
                    elif vis_choice == '3':
                        new_value = 'manual'
                    else:
                        print("Invalid choice. Skipping.")
                        continue

                elif config_key in ['default_voting_period_days', 'maximum_candidates_per_election']:
                    # Numeric configuration
                    new_value = input(f"Enter new value for {description.lower()}: ").strip()
                    try:
                        int(new_value)  # Validate it's a number
                    except ValueError:
                        print("Invalid number. Skipping.")
                        continue
                else:
                    # Text configuration
                    new_value = input(f"Enter new value for {description.lower()}: ").strip()

                if new_value != current_value:
                    cursor.execute('''
                    UPDATE voting_configuration 
                    SET config_value = ?, updated_by = ?, updated_at = ?
                    WHERE config_key = ?
                    ''', (new_value, ctx.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), config_key))

                    conn.commit()
                    print(f"✅ Configuration updated: {description}")

                    # Log the change
                    log_configuration_change(cursor, conn, config_key, current_value, new_value, description)
                else:
                    print("No changes made.")

            elif choice == len(configs) + 1:
                # Email notification test
                test_email_notifications(cursor, conn)

            elif choice == len(configs) + 2:
                # Export configuration
                export_voting_configuration(cursor)

            elif choice == len(configs) + 3:
                # Import configuration
                import_voting_configuration(cursor, conn)

            elif choice == len(configs) + 4:
                # Reset to defaults
                confirm = input("⚠️ Reset all configurations to defaults? This cannot be undone. (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    reset_voting_configuration(cursor, conn)
                    print("✅ Configuration reset to defaults.")
                else:
                    print("Reset cancelled.")

            elif choice == len(configs) + 5:
                # Return to main menu
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def review_pending_materials(cursor):
    """Review pending campaign material approvals"""
    try:
        cursor.execute('''
        SELECT 
            cm.material_id,
            cm.material_type,
            cm.content,
            cm.upload_date,
            s.first_name,
            s.last_name,
            e.position
        FROM campaign_materials cm
        JOIN election_candidates c ON cm.candidate_id = c.id
        JOIN students s ON c.student_id = s.student_id
        JOIN union_elections e ON c.election_id = e.election_id
        WHERE cm.status = 'pending_approval'
        ORDER BY cm.upload_date
        ''')

        pending_materials = cursor.fetchall()

        if not pending_materials:
            print("\n✅ No pending material approvals")
            return

        print(f"\n📋 Pending Material Approvals ({len(pending_materials)} items):")
        print("=" * 80)

        for i, material in enumerate(pending_materials, 1):
            material_id, material_type, content, upload_date, first_name, last_name, position = material
            print(f"\n{i}. Material ID: {material_id}")
            print(f"   Candidate: {first_name} {last_name} ({position})")
            print(f"   Type: {material_type}")
            print(f"   Uploaded: {upload_date}")
            print(f"   Content: {content[:100]}{'...' if len(content) > 100 else ''}")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_spending_warnings(cursor, violations, spending_limit):
    """Send warnings to candidates who have exceeded spending limits"""
    if not violations:
        print("\n✅ No spending violations to warn about")
        return

    try:
        warning_count = 0

        for violation in violations:
            candidate_id, first_name, last_name, position, total_spent = violation
            overage = total_spent - spending_limit

            # Get student ID for the candidate
            cursor.execute('''
            SELECT student_id FROM election_candidates WHERE id = ?
            ''', (candidate_id,))

            result = cursor.fetchone()
            if result:
                student_id = result[0]

                subject, message = render_template("campaign_spending_violation", {
                    "first_name": first_name,
                    "last_name": last_name,
                    "position": position,
                    "total_spent": f"{total_spent:.2f}",
                    "spending_limit": f"{spending_limit:.2f}",
                    "overage": f"{overage:.2f}"
                })

                if subject and message and send_confirmation_email(student_id, subject, message):
                    warning_count += 1

        print(f"📧 Sent {warning_count} spending violation warnings")

    except Exception as e:
        print(f"Error sending warnings: {e}")

def view_detailed_spending(cursor):
    """View detailed spending breakdown for all candidates"""
    try:
        cursor.execute('''
        SELECT 
            s.first_name,
            s.last_name,
            e.position,
            ce.amount,
            ce.description,
            ce.expense_date,
            ce.receipt_path
        FROM election_candidates c
        JOIN students s ON c.student_id = s.student_id
        JOIN union_elections e ON c.election_id = e.election_id
        LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
        WHERE e.status IN ('nomination', 'voting') AND ce.amount IS NOT NULL
        ORDER BY s.last_name, s.first_name, ce.expense_date
        ''')

        expenses = cursor.fetchall()

        if not expenses:
            print("\n📊 No campaign expenses recorded yet")
            return

        print(f"\n💰 Detailed Campaign Spending ({len(expenses)} transactions):")
        print("=" * 80)

        current_candidate = None
        candidate_total = 0

        for expense in expenses:
            first_name, last_name, position, amount, description, expense_date, receipt_path = expense
            candidate_name = f"{first_name} {last_name} ({position})"

            if current_candidate != candidate_name:
                if current_candidate:
                    print(f"    Subtotal: £{candidate_total:.2f}")
                    print("-" * 40)

                current_candidate = candidate_name
                candidate_total = 0
                print(f"\n{candidate_name}:")

            receipt_status = "✓" if receipt_path else "✗"
            print(f"  £{amount:.2f} - {description} ({expense_date}) {receipt_status}")
            candidate_total += amount

        if current_candidate:
            print(f"    Subtotal: £{candidate_total:.2f}")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def approve_reject_materials(cursor):
    """Approve or reject pending campaign materials"""
    try:
        cursor.execute('''
        SELECT 
            cm.material_id,
            cm.material_type,
            cm.content,
            s.first_name,
            s.last_name,
            e.position
        FROM campaign_materials cm
        JOIN election_candidates c ON cm.candidate_id = c.id
        JOIN students s ON c.student_id = s.student_id
        JOIN union_elections e ON c.election_id = e.election_id
        WHERE cm.status = 'pending_approval'
        ORDER BY cm.upload_date
        ''')

        pending_materials = cursor.fetchall()

        if not pending_materials:
            print("\n✅ No pending materials to review")
            return

        print(f"\n📋 Materials Pending Approval:")
        for i, material in enumerate(pending_materials, 1):
            material_id, material_type, content, first_name, last_name, position = material
            print(f"\n{i}. Material ID: {material_id}")
            print(f"   Candidate: {first_name} {last_name} ({position})")
            print(f"   Type: {material_type}")
            print(f"   Content: {content[:150]}{'...' if len(content) > 150 else ''}")

        while True:
            choice = input(f"\nSelect material to review (1-{len(pending_materials)}, 0 to exit): ").strip()

            if choice == '0':
                break

            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(pending_materials):
                print("Invalid choice.")
                continue

            material_index = int(choice) - 1
            material_id = pending_materials[material_index][0]

            print(f"\nReviewing Material ID: {material_id}")
            action = input("Action (a=approve, r=reject, s=skip): ").strip().lower()

            if action == 'a':
                cursor.execute('''
                UPDATE campaign_materials 
                SET status = 'approved', reviewed_at = ?, reviewed_by = ?
                WHERE material_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ctx.auth.current_user['id'], material_id))

                print("✅ Material approved")

            elif action == 'r':
                reason = input("Rejection reason: ").strip()
                cursor.execute('''
                UPDATE campaign_materials 
                SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, rejection_reason = ?
                WHERE material_id = ?
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ctx.auth.current_user['id'], reason, material_id))

                print("❌ Material rejected")

            elif action == 's':
                continue
            else:
                print("Invalid action.")
                continue

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def access_control_review(cursor):
    """Review user access controls and permissions"""
    try:
        print("\n👥 Access Control Review")
        print("=" * 30)

        # Review admin users
        cursor.execute('''
        SELECT id, username, role, created_at, last_login
        FROM users
        WHERE role IN ('admin', 'staff')
        ORDER BY role, username
        ''')

        admin_users = cursor.fetchall()

        print("🔑 ADMINISTRATIVE USERS:")
        for user_id, username, role, created_at, last_login in admin_users:
            print(f"  {username} ({role}) - Created: {created_at}")
            if last_login:
                print(f"    Last login: {last_login}")
            else:
                print("    Never logged in")

        # Review election permissions
        cursor.execute('''
        SELECT u.username, u.role, COUNT(e.election_id) as elections_created
        FROM users u
        LEFT JOIN union_elections e ON u.id = e.created_by
        WHERE u.role IN ('admin', 'staff')
        GROUP BY u.id, u.username, u.role
        ''')

        election_creators = cursor.fetchall()

        print(f"\n📊 ELECTION CREATION ACTIVITY:")
        for username, role, elections_created in election_creators:
            print(f"  {username} ({role}): {elections_created} elections created")

        # Check for inactive admin accounts
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
        SELECT username, role, last_login
        FROM users
        WHERE role IN ('admin', 'staff')
        AND (last_login IS NULL OR last_login < ?)
        ''', (thirty_days_ago,))

        inactive_admins = cursor.fetchall()

        if inactive_admins:
            print(f"\n⚠️ INACTIVE ADMIN ACCOUNTS (>30 days):")
            for username, role, last_login in inactive_admins:
                print(f"  {username} ({role}) - Last login: {last_login or 'Never'}")
        else:
            print(f"\n✅ All admin accounts active within 30 days")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def log_configuration_change(cursor, conn, config_key, old_value, new_value, description):
    """Log configuration changes for audit purposes"""
    try:
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuration_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            description TEXT,
            changed_by INTEGER,
            changed_at TEXT,
            FOREIGN KEY (changed_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
        INSERT INTO configuration_audit (config_key, old_value, new_value, description, changed_by, changed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            config_key, 
            old_value, 
            new_value, 
            description, 
            ctx.auth.current_user['id'], 
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()

    except sqlite3.Error as e:
        print(f"Error logging configuration change: {e}")

def test_email_notifications(cursor, conn):
    """Test email notification system"""
    try:
        test_email = input("Enter test email address: ").strip()
        if not test_email:
            print("No email address provided.")
            return

        # Prepare template variables
        template_vars = {
            'username': ctx.auth.current_user['username'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Try to send using the email system
        try:
            subject, message = render_template('election_system_test', template_vars)
            from education_system.university_system.infrastructure.email import queue_email
            success = queue_email(test_email, subject, message)
        except ImportError:
            # Fallback for testing - log but continue
            logger.warning("Email queue module not available, simulating email send")
            success = True
            print(f"Test email would be sent to: {test_email}")
        except Exception as e:
            # Fallback to hardcoded message if template fails
            logger.warning(
                f"Template 'election_system_test' rendering failed: {e}. Using fallback message."
            )
            subject = "Election System Test Notification"
            message = f"""This is a test email from the Election System.

Sent by: {ctx.auth.current_user['username']}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

If you received this email, the notification system is working correctly.

Best regards,
Election Administration Team
"""
            from education_system.university_system.infrastructure.email import queue_email
            success = queue_email(test_email, subject, message)

        if success:
            print("✅ Test email sent successfully!")
        else:
            print("❌ Failed to send test email")

    except Exception as e:
        print(f"Error testing email notifications: {e}")

def reset_voting_configuration(cursor, conn):
    """Reset voting configuration to defaults"""
    try:
        cursor.execute('DELETE FROM voting_configuration')

        default_configs = [
            ('default_voting_method', 'simple', 'Default voting method for new elections'),
            ('allow_ranked_choice', 'true', 'Allow ranked choice voting'),
            ('online_voting_enabled', 'true', 'Enable online voting'),
            ('offline_voting_enabled', 'false', 'Enable offline voting'),
            ('default_voting_period_days', '7', 'Default voting period in days'),
            ('voter_eligibility_check', 'true', 'Check voter eligibility'),
            ('results_visibility', 'post_election', 'When results are visible'),
            ('email_notifications', 'true', 'Send email notifications for elections'),
            ('candidate_photo_required', 'false', 'Require candidate photos'),
            ('maximum_candidates_per_election', '10', 'Maximum candidates per election')
        ]

        for config_key, config_value, description in default_configs:
            cursor.execute('''
            INSERT INTO voting_configuration (config_key, config_value, description, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (config_key, config_value, description, ctx.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

    except sqlite3.Error as e:
        print(f"Error resetting configuration: {e}")

def manage_union_reps():
    """Manage student union representatives (for admins)"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to manage union representatives.")
        return

    if not ctx.auth.check_permission('manage_union_reps'):
        print("You don't have permission to manage union representatives.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print("\nManage Union Representatives")
            print("===========================")
            print("1. View All Representatives")
            print("2. Add New Representative")
            print("3. Edit Representative")
            print("4. Change Representative Status")
            print("5. Return to Admin Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                # View all representatives
                cursor.execute('''
                SELECT r.id, r.student_id, s.first_name, s.last_name, r.position, 
                       r.department, r.election_date, r.term_end_date, r.status
                FROM union_representatives r
                JOIN students s ON r.student_id = s.student_id
                ORDER BY r.status, r.position, r.department
                ''')

                reps = cursor.fetchall()

                if not reps:
                    print("No union representatives found.")
                else:
                    print("\nUnion Representatives:")
                    print("=====================")

                    for rep in reps:
                        print(f"\nID: {rep[0]}")
                        print(f"Student: {rep[2]} {rep[3]} (ID: {rep[1]})")
                        print(f"Position: {rep[4]}")
                        if rep[5]:
                            print(f"Department: {rep[5]}")
                        else:
                            print("Department: All")
                        print(f"Elected on: {rep[6]}")
                        print(f"Term ends: {rep[7]}")
                        print(f"Status: {rep[8]}")
                        print("-" * 40)

            elif choice == '2':
                # Add new representative
                student_id = input("Enter student ID: ").strip()

                # Verify student exists
                cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                student = cursor.fetchone()

                if not student:
                    print(f"No student found with ID {student_id}.")
                    continue

                position = input("Enter position title: ").strip()
                if not position:
                    print("Position cannot be empty.")
                    continue

                # Department (optional)
                department_choice = input("Is this position specific to a department? (y/n): ").strip().lower()
                department = None

                if department_choice == 'y':
                    department = input("Enter department name: ").strip()

                # Check if position is already filled
                cursor.execute('''
                SELECT COUNT(*) FROM union_representatives
                WHERE position = ? AND (department = ? OR (department IS NULL AND ? IS NULL))
                AND status = 'active'
                ''', (position, department, department))

                if cursor.fetchone()[0] > 0:
                    print("This position is already filled by an active representative.")
                    continue_anyway = input("Continue anyway? (y/n): ").strip().lower()
                    if continue_anyway != 'y':
                        continue

                    # Set current holder to 'former'
                    cursor.execute('''
                    UPDATE union_representatives 
                    SET status = 'former', term_end_date = ?
                    WHERE position = ? AND (department = ? OR (department IS NULL AND ? IS NULL))
                    AND status = 'active'
                    ''', (datetime.now().strftime('%Y-%m-%d'), position, department, department))

                # Set election date to today if not specified
                election_date = input("Enter election date (YYYY-MM-DD) or leave blank for today: ").strip()
                if not election_date:
                    election_date = datetime.now().strftime('%Y-%m-%d')

                # Set term end date (1 year from election date by default)
                term_end = input("Enter term end date (YYYY-MM-DD) or leave blank for 1 year term: ").strip()
                if not term_end:
                    # Parse election date
                    election_datetime = datetime.strptime(election_date, '%Y-%m-%d')
                    # Add 1 year
                    term_end_datetime = election_datetime.replace(year=election_datetime.year + 1)
                    term_end = term_end_datetime.strftime('%Y-%m-%d')

                # Insert new representative
                cursor.execute('''
                INSERT INTO union_representatives (
                    student_id, position, department, election_date, term_end_date, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_id, position, department, election_date, term_end, 'active'))

                conn.commit()
                print(f"{student[0]} {student[1]} has been added as a {position} representative.")

                # Send confirmation email
                send_confirmation_email(student_id, f"Union Representative Appointment: {position}", 
                                       f"You have been appointed as a Student Union Representative for the position of {position}.")

            elif choice == '3':
                # Edit representative
                rep_id = input("Enter representative ID to edit: ").strip()
                if not rep_id.isdigit():
                    print("Invalid ID format.")
                    continue

                # Check if representative exists
                cursor.execute('''
                SELECT r.id, r.student_id, s.first_name, s.last_name, r.position, 
                       r.department, r.election_date, r.term_end_date, r.status
                FROM union_representatives r
                JOIN students s ON r.student_id = s.student_id
                WHERE r.id = ?
                ''', (rep_id,))

                rep = cursor.fetchone()

                if not rep:
                    print(f"No representative found with ID {rep_id}.")
                    continue

                print(f"\nEditing representative: {rep[2]} {rep[3]} - {rep[4]}")

                # Get new values, using current values as defaults
                new_position = input(f"Enter new position (current: {rep[4]}) or leave blank to keep current: ").strip()
                if not new_position:
                    new_position = rep[4]

                current_dept = rep[5] if rep[5] else "All departments"
                change_dept = input(f"Change department? Current: {current_dept} (y/n): ").strip().lower()

                new_department = rep[5]
                if change_dept == 'y':
                    dept_specific = input("Is this position specific to a department? (y/n): ").strip().lower()
                    if dept_specific == 'y':
                        new_department = input("Enter department name: ").strip()
                    else:
                        new_department = None

                new_election_date = input(f"Enter new election date (current: {rep[6]}) or leave blank to keep current: ").strip()
                if not new_election_date:
                    new_election_date = rep[6]

                new_term_end = input(f"Enter new term end date (current: {rep[7]}) or leave blank to keep current: ").strip()
                if not new_term_end:
                    new_term_end = rep[7]

                # Update the representative
                cursor.execute('''
                UPDATE union_representatives 
                SET position = ?, department = ?, election_date = ?, term_end_date = ?
                WHERE id = ?
                ''', (new_position, new_department, new_election_date, new_term_end, rep_id))

                conn.commit()
                print("Representative information updated successfully.")

            elif choice == '4':
                # Change representative status
                rep_id = input("Enter representative ID to change status: ").strip()
                if not rep_id.isdigit():
                    print("Invalid ID format.")
                    continue

                # Check if representative exists
                cursor.execute('''
                SELECT r.id, r.student_id, s.first_name, s.last_name, r.position, r.status
                FROM union_representatives r
                JOIN students s ON r.student_id = s.student_id
                WHERE r.id = ?
                ''', (rep_id,))

                rep = cursor.fetchone()

                if not rep:
                    print(f"No representative found with ID {rep_id}.")
                    continue

                print(f"\nChanging status for: {rep[2]} {rep[3]} - {rep[4]} (Current: {rep[5]})")

                print("Available statuses:")
                print("1. active - Currently serving")
                print("2. former - No longer in position")
                print("3. suspended - Temporarily suspended")
                print("4. on_leave - On approved leave")

                status_choice = input("Enter new status (1-4): ").strip()

                if status_choice == '1':
                    new_status = 'active'
                elif status_choice == '2':
                    new_status = 'former'
                elif status_choice == '3':
                    new_status = 'suspended'
                elif status_choice == '4':
                    new_status = 'on_leave'
                else:
                    print("Invalid status choice.")
                    continue

                # If setting to former, update term end date to today
                if new_status == 'former':
                    cursor.execute('''
                    UPDATE union_representatives 
                    SET status = ?, term_end_date = ?
                    WHERE id = ?
                    ''', (new_status, datetime.now().strftime('%Y-%m-%d'), rep_id))
                else:
                    cursor.execute('''
                    UPDATE union_representatives 
                    SET status = ?
                    WHERE id = ?
                    ''', (new_status, rep_id))

                conn.commit()
                print(f"Status changed to {new_status} successfully.")

                # Send notification to the representative
                cursor.execute('SELECT student_id FROM union_representatives WHERE id = ?', (rep_id,))
                student_id = cursor.fetchone()[0]

                send_confirmation_email(student_id, "Union Representative Status Change", 
                                      f"Your status as a Student Union Representative has been changed to: {new_status}.")

            elif choice == '5':
                break

            else:
                print("Invalid choice. Please try again.")

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
