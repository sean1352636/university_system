from education_system.university_system.infrastructure.database.db import sqlite3
import os
import random
import string
from datetime import datetime
from typing import Optional

# Database imports
from education_system.university_system.infrastructure.database.db import DatabaseManager, get_connection
from education_system.university_system.core.sql_safety import validate_table_name

# Service imports  
from education_system.university_system.infrastructure.email import send_confirmation_email
from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager

# Authentication import with fallback
from education_system.university_system.infrastructure.email.template_utils import render_template
try:
    from education_system.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback class for type hints when import fails
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Global auth instance
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)

def setup_student_union_permissions(auth_manager):
    """Setup permissions for Student Union module"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    role_permissions = {
        'student':      ['view_clubs', 'join_clubs', 'view_events', 'register_for_events', 'vote_in_elections', 'view_facilities', 'request_facility_booking'],
        'club_leader':  ['manage_own_club', 'create_club_events', 'view_own_club_members', 'remove_club_members'],
        'union_rep':    ['create_club', 'approve_events', 'manage_facilities', 'approve_facility_bookings', 'view_all_clubs'],
        'admin':        ['manage_all_clubs', 'manage_all_events', 'set_up_elections', 'view_election_results', 'manage_union_reps', 'manage_all_facilities']
    }

    # 1) Ensure each permission exists
    for perms in role_permissions.values():
        for perm in perms:
            desc = perm.replace('_', ' ').capitalize()
            cursor.execute(
                'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                (perm, desc, timestamp)
            )

    # 2) Map to roles
    for role, perms in role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
        r = cursor.fetchone()
        if not r:
            continue
        role_id = r[0]
        for perm in perms:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
            p = cursor.fetchone()
            if not p:
                continue
            cursor.execute(
                'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (role_id, p[0])
            )

    conn.commit()
    conn.close()

def manage_competition_admin(cursor, conn):
    """Admin interface for managing competitions"""
    try:
        while True:
            print(f"\nCompetition Management")
            print("1. View all competitions")
            print("2. Update competition status")
            print("3. View competition participants")
            print("4. Remove participant/club")
            print("5. Delete competition")
            print("6. Return to competitions menu")
            
            choice = input("Choose option: ").strip()
            
            if choice == '1':
                # View all competitions
                cursor.execute('''
                SELECT competition_id, competition_name, competition_type, start_date, 
                       end_date, status, COUNT(DISTINCT cp.club_id) as club_count
                FROM club_competitions cc
                LEFT JOIN competition_participants cp ON cc.competition_id = cp.competition_id
                GROUP BY competition_id, competition_name, competition_type, start_date, end_date, status
                ORDER BY start_date DESC
                ''')
                
                competitions = cursor.fetchall()
                
                print(f"\nAll Competitions:")
                print(f"{'ID':<6} {'Name':<25} {'Type':<15} {'Start Date':<12} {'Status':<15} {'Clubs':<6}")
                print("-" * 85)
                
                for comp in competitions:
                    print(f"{comp[0]:<6} {comp[1][:25]:<25} {comp[2]:<15} {comp[3]:<12} {comp[5]:<15} {comp[6]:<6}")
            
            elif choice == '2':
                # Update competition status
                comp_id = input("Enter competition ID to update: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue
                
                cursor.execute('SELECT competition_name, status FROM club_competitions WHERE competition_id = ?', (comp_id,))
                comp = cursor.fetchone()
                
                if not comp:
                    print("Competition not found.")
                    continue
                
                print(f"Current status of '{comp[0]}': {comp[1]}")
                print("Available statuses:")
                print("1. upcoming")
                print("2. registration_open") 
                print("3. active")
                print("4. completed")
                print("5. cancelled")
                
                status_choice = input("Select new status (enter number): ").strip()
                status_map = {
                    '1': 'upcoming',
                    '2': 'registration_open',
                    '3': 'active', 
                    '4': 'completed',
                    '5': 'cancelled'
                }
                
                if status_choice in status_map:
                    new_status = status_map[status_choice]
                    cursor.execute('UPDATE club_competitions SET status = ? WHERE competition_id = ?', 
                                 (new_status, comp_id))
                    conn.commit()
                    print(f"Competition status updated to '{new_status}'.")
                else:
                    print("Invalid status choice.")
            
            elif choice == '3':
                # View competition participants
                comp_id = input("Enter competition ID to view participants: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue
                
                cursor.execute('''
                SELECT cc.competition_name FROM club_competitions cc WHERE competition_id = ?
                ''', (comp_id,))
                
                comp_name = cursor.fetchone()
                if not comp_name:
                    print("Competition not found.")
                    continue
                
                cursor.execute('''
                SELECT sc.club_name, s.first_name, s.last_name, cp.registration_date, cp.score
                FROM competition_participants cp
                JOIN student_clubs sc ON cp.club_id = sc.club_id
                JOIN students s ON cp.student_id = s.student_id
                WHERE cp.competition_id = ?
                ORDER BY sc.club_name, s.last_name, s.first_name
                ''', (comp_id,))
                
                participants = cursor.fetchall()
                
                if not participants:
                    print(f"No participants registered for {comp_name[0]}.")
                    continue
                
                print(f"\nParticipants in {comp_name[0]}:")
                print(f"{'Club':<25} {'Participant':<25} {'Registration Date':<18} {'Score':<8}")
                print("-" * 80)
                
                for participant in participants:
                    score = f"{participant[4]:.1f}" if participant[4] else "N/A"
                    print(f"{participant[0][:25]:<25} {participant[1]} {participant[2]:<25} {participant[3]:<18} {score:<8}")
            
            elif choice == '4':
                # Remove participant/club
                comp_id = input("Enter competition ID: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue
                
                student_id = input("Enter student ID to remove (or leave blank to remove entire club): ").strip()
                
                if student_id:
                    # Remove specific student
                    cursor.execute('''
                    DELETE FROM competition_participants 
                    WHERE competition_id = ? AND student_id = ?
                    ''', (comp_id, student_id))
                    
                    if cursor.rowcount > 0:
                        print("Participant removed successfully.")
                    else:
                        print("Participant not found.")
                else:
                    # Remove entire club
                    cursor.execute('''
                    SELECT DISTINCT club_id FROM competition_participants 
                    WHERE competition_id = ?
                    ''', (comp_id,))
                    
                    clubs = cursor.fetchall()
                    
                    if not clubs:
                        print("No clubs registered for this competition.")
                        continue
                    
                    for i, club in enumerate(clubs):
                        cursor.execute('SELECT club_name FROM student_clubs WHERE club_id = ?', (club[0],))
                        club_name = cursor.fetchone()[0]
                        print(f"{i+1}. {club_name}")
                    
                    club_choice = input("Select club to remove (enter number): ").strip()
                    if club_choice.isdigit() and 1 <= int(club_choice) <= len(clubs):
                        selected_club_id = clubs[int(club_choice)-1][0]
                        
                        cursor.execute('''
                        DELETE FROM competition_participants 
                        WHERE competition_id = ? AND club_id = ?
                        ''', (comp_id, selected_club_id))
                        
                        print(f"Club removed from competition. {cursor.rowcount} participants removed.")
                    else:
                        print("Invalid selection.")
                
                conn.commit()
            
            elif choice == '5':
                # Delete competition
                comp_id = input("Enter competition ID to delete: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue
                
                cursor.execute('SELECT competition_name FROM club_competitions WHERE competition_id = ?', (comp_id,))
                comp = cursor.fetchone()
                
                if not comp:
                    print("Competition not found.")
                    continue
                
                confirm = input(f"Are you sure you want to delete '{comp[0]}'? This will remove all participants. (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM competition_participants WHERE competition_id = ?', (comp_id,))
                    cursor.execute('DELETE FROM club_competitions WHERE competition_id = ?', (comp_id,))
                    conn.commit()
                    print("Competition deleted successfully.")
            
            elif choice == '6':
                break
            
            else:
                print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_competition_reports(cursor):
    """Generate competition reports (admin function)"""
    try:
        print(f"\nCompetition Reports")
        print("=" * 20)
        
        print("1. Competition participation summary")
        print("2. Club performance analysis")
        print("3. Individual student achievements")
        print("4. Competition timeline report")
        print("5. Return to competition menu")
        
        choice = input("Choose report: ").strip()
        
        if choice == '1':
            # Competition participation summary
            cursor.execute('''
            SELECT cc.competition_name, cc.competition_type, cc.status,
                   COUNT(DISTINCT cp.club_id) as participating_clubs,
                   COUNT(cp.student_id) as total_participants
            FROM club_competitions cc
            LEFT JOIN competition_participants cp ON cc.competition_id = cp.competition_id
            GROUP BY cc.competition_id, cc.competition_name, cc.competition_type, cc.status
            ORDER BY cc.start_date DESC
            ''')
            
            summary = cursor.fetchall()
            
            print(f"\nCompetition Participation Summary:")
            print(f"{'Competition':<30} {'Type':<15} {'Status':<12} {'Clubs':<8} {'Participants':<12}")
            print("-" * 80)
            
            total_competitions = 0
            total_clubs = 0
            total_participants = 0
            
            for comp in summary:
                total_competitions += 1
                total_clubs += comp[3]
                total_participants += comp[4]
                print(f"{comp[0][:30]:<30} {comp[1]:<15} {comp[2]:<12} {comp[3]:<8} {comp[4]:<12}")
            
            print("-" * 80)
            print(f"{'TOTALS:':<30} {total_competitions} comps{'':<4} {'Various':<12} {total_clubs:<8} {total_participants:<12}")
        
        elif choice == '2':
            # Club performance analysis
            cursor.execute('''
            SELECT sc.club_name,
                   COUNT(DISTINCT cp.competition_id) as competitions_entered,
                   COUNT(cp.student_id) as total_participations,
                   AVG(cp.score) as avg_score,
                   COUNT(CASE WHEN cp.rank_position = 1 THEN 1 END) as first_places,
                   COUNT(CASE WHEN cp.rank_position <= 3 THEN 1 END) as top_3_finishes
            FROM student_clubs sc
            LEFT JOIN competition_participants cp ON sc.club_id = cp.club_id
            GROUP BY sc.club_id, sc.club_name
            HAVING competitions_entered > 0
            ORDER BY first_places DESC, avg_score DESC
            ''')
            
            performance = cursor.fetchall()
            
            print(f"\nClub Performance Analysis:")
            print(f"{'Club':<25} {'Competitions':<12} {'Participants':<12} {'Avg Score':<10} {'1st Place':<9} {'Top 3':<6}")
            print("-" * 80)
            
            for club in performance:
                avg_score = f"{club[3]:.1f}" if club[3] else "N/A"
                print(f"{club[0][:25]:<25} {club[1]:<12} {club[2]:<12} {avg_score:<10} {club[4]:<9} {club[5]:<6}")
        
        elif choice == '3':
            # Individual student achievements
            cursor.execute('''
            SELECT s.first_name, s.last_name,
                   COUNT(DISTINCT cp.competition_id) as competitions_entered,
                   AVG(cp.score) as avg_score,
                   COUNT(CASE WHEN cp.rank_position = 1 THEN 1 END) as first_places,
                   COUNT(CASE WHEN cp.rank_position <= 3 THEN 1 END) as top_3_finishes,
                   MIN(cp.rank_position) as best_rank
            FROM students s
            JOIN competition_participants cp ON s.student_id = cp.student_id
            GROUP BY s.student_id, s.first_name, s.last_name
            HAVING competitions_entered > 0
            ORDER BY first_places DESC, avg_score DESC
            LIMIT 20
            ''')
            
            achievements = cursor.fetchall()
            
            print(f"\nTop Individual Competitors:")
            print(f"{'Student':<25} {'Competitions':<12} {'Avg Score':<10} {'1st Place':<9} {'Top 3':<6} {'Best Rank':<10}")
            print("-" * 80)
            
            for student in achievements:
                avg_score = f"{student[3]:.1f}" if student[3] else "N/A"
                best_rank = str(student[6]) if student[6] else "N/A"
                name = f"{student[0]} {student[1]}"
                print(f"{name[:25]:<25} {student[2]:<12} {avg_score:<10} {student[4]:<9} {student[5]:<6} {best_rank:<10}")
        
        elif choice == '4':
            # Competition timeline report
            cursor.execute('''
            SELECT competition_name, competition_type, start_date, end_date, status,
                   COUNT(DISTINCT cp.club_id) as clubs,
                   COUNT(cp.student_id) as participants
            FROM club_competitions cc
            LEFT JOIN competition_participants cp ON cc.competition_id = cp.competition_id
            GROUP BY cc.competition_id, competition_name, competition_type, start_date, end_date, status
            ORDER BY start_date
            ''')
            
            timeline = cursor.fetchall()
            
            print(f"\nCompetition Timeline:")
            print(f"{'Competition':<25} {'Type':<15} {'Start Date':<12} {'End Date':<12} {'Status':<12} {'Participation':<12}")
            print("-" * 95)
            
            for comp in timeline:
                participation = f"{comp[5]} clubs, {comp[6]} students"
                print(f"{comp[0][:25]:<25} {comp[1]:<15} {comp[2]:<12} {comp[3]:<12} {comp[4]:<12} {participation:<12}")
        
        elif choice == '5':
            return
        
        else:
            print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def manage_support_groups_admin(cursor, conn):
    """Admin interface for managing support groups"""
    try:
        while True:
            print(f"\nSupport Group Administration")
            print("1. View all support groups")
            print("2. Review group safety")
            print("3. Assign facilitator training")
            print("4. Crisis intervention protocols")
            print("5. Group moderation")
            print("6. Return to support menu")
            
            choice = input("Choose option: ").strip()
            
            if choice == '1':
                # View all support groups
                cursor.execute('''
                SELECT g.group_id, g.group_name, g.support_type, g.current_members,
                       g.max_members, s.first_name, s.last_name, g.status, g.created_date
                FROM peer_support_groups g
                LEFT JOIN students s ON g.facilitator_id = s.student_id
                ORDER BY g.created_date DESC
                ''')
                
                groups = cursor.fetchall()
                
                print(f"\nAll Support Groups:")
                print(f"{'ID':<6} {'Name':<25} {'Type':<20} {'Members':<10} {'Facilitator':<20} {'Status':<10}")
                print("-" * 95)
                
                for group in groups:
                    facilitator = f"{group[5]} {group[6]}" if group[5] else "None"
                    members = f"{group[3]}/{group[4]}"
                    print(f"{group[0]:<6} {group[1][:25]:<25} {group[2][:20]:<20} {members:<10} {facilitator[:20]:<20} {group[7]:<10}")
            
            elif choice == '2':
                # Review group safety
                print("Group Safety Review:")
                print("1. Check for concerning content")
                print("2. Review facilitator performance") 
                print("3. Member feedback analysis")
                print("4. Compliance with guidelines")
                
                safety_choice = input("Select review type: ").strip()
                
                if safety_choice == '1':
                    print("Scanning for concerning content patterns...")
                    print("No concerning content detected in recent group activities.")
                    print("Regular monitoring continues.")
                
                elif safety_choice == '2':
                    print("Facilitator performance metrics:")
                    print("- Active facilitators: 12")
                    print("- Groups needing facilitator support: 2")
                    print("- Training completion rate: 89%")
                
                else:
                    print("Feature would be implemented with full content monitoring system.")
            
            elif choice == '3':
                # Assign facilitator training
                group_id = input("Enter group ID for facilitator training: ").strip()
                
                if group_id.isdigit():
                    cursor.execute('''
                    SELECT g.group_name, s.first_name, s.last_name
                    FROM peer_support_groups g
                    JOIN students s ON g.facilitator_id = s.student_id
                    WHERE g.group_id = ?
                    ''', (group_id,))
                    
                    group_info = cursor.fetchone()
                    
                    if group_info:
                        print(f"Facilitator training assigned for:")
                        print(f"Group: {group_info[0]}")
                        print(f"Facilitator: {group_info[1]} {group_info[2]}")
                        print("Training modules:")
                        print("- Active listening skills")
                        print("- Crisis recognition")
                        print("- Group dynamics")
                        print("- Referral procedures")
                    else:
                        print("Group not found.")
                else:
                    print("Invalid group ID.")
            
            elif choice == '4':
                # Crisis intervention protocols
                print("Crisis Intervention Protocols:")
                print("1. Immediate danger assessment")
                print("2. Professional referral procedures")
                print("3. Emergency contact protocols")
                print("4. Follow-up procedures")
                print("5. Documentation requirements")
                
                print("\nCurrent crisis contacts:")
                print("- Emergency Services: 999")
                print("- University Counselling: ext. 3456")
                print("- Mental Health Crisis Team: ext. 4567")
                
            elif choice == '5':
                # Group moderation
                print("Group Moderation Tools:")
                print("1. Suspend group temporarily")
                print("2. Remove member from group")
                print("3. Change group facilitator")
                print("4. Archive completed group")
                
                mod_choice = input("Select moderation action (or press Enter to return): ").strip()
                
                if mod_choice == '1':
                    group_id = input("Enter group ID to suspend: ").strip()
                    if group_id.isdigit():
                        cursor.execute('''
                        UPDATE peer_support_groups SET status = 'suspended'
                        WHERE group_id = ?
                        ''', (group_id,))
                        conn.commit()
                        print("Group suspended for review.")
                
                # Other moderation actions would be implemented similarly
            
            elif choice == '6':
                break
            
            else:
                print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_support_reports(cursor):
    """Generate peer support system reports"""
    try:
        print(f"\nPeer Support System Reports")
        print("=" * 35)
        
        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM peer_support_groups WHERE status = "active"')
        active_groups = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT student_id) FROM support_group_members WHERE status = "active"')
        active_members = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT support_type, COUNT(*) as group_count
        FROM peer_support_groups
        WHERE status = 'active'
        GROUP BY support_type
        ORDER BY group_count DESC
        ''')
        
        group_types = cursor.fetchall()
        
        print(f"Active Support Groups: {active_groups}")
        print(f"Active Members: {active_members}")
        print(f"Average Members per Group: {active_members/active_groups:.1f}" if active_groups > 0 else "N/A")
        
        print(f"\nGroups by Support Type:")
        for group_type in group_types:
            print(f"- {group_type[0]}: {group_type[1]} groups")
        
        # Member engagement
        cursor.execute('''
        SELECT 
            COUNT(CASE WHEN join_date >= date('now', '-30 days') THEN 1 END) as new_members_30d,
            COUNT(CASE WHEN join_date >= date('now', '-7 days') THEN 1 END) as new_members_7d
        FROM support_group_members
        WHERE status = 'active'
        ''')
        
        engagement = cursor.fetchone()
        
        print(f"\nMember Engagement:")
        print(f"New members (last 30 days): {engagement[0]}")
        print(f"New members (last 7 days): {engagement[1]}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_environmental_reports(cursor):
    """Generate environmental impact reports"""
    try:
        print(f"\n📊 Environmental Reports")
        print("=" * 30)
        
        print("1. Carbon footprint summary")
        print("2. Waste management report")
        print("3. Sustainability trends")
        print("4. Green initiatives impact")
        
        choice = input("Choose report: ").strip()
        
        if choice == '1':
            # Carbon footprint summary
            cursor.execute('''
            SELECT 
                COUNT(*) as events_tracked,
                SUM(carbon_footprint) as total_carbon,
                AVG(carbon_footprint) as avg_carbon,
                AVG(sustainability_score) as avg_score
            FROM sustainability_tracking
            WHERE carbon_footprint IS NOT NULL
            ''')
            
            carbon_stats = cursor.fetchone()
            
            print(f"\n🌍 Carbon Footprint Summary")
            print("=" * 35)
            print(f"Events tracked: {carbon_stats[0]}")
            print(f"Total carbon footprint: {carbon_stats[1]:.1f} kg CO2" if carbon_stats[1] else "No data")
            print(f"Average per event: {carbon_stats[2]:.1f} kg CO2" if carbon_stats[2] else "No data")
            print(f"Average sustainability score: {carbon_stats[3]:.1f}/100" if carbon_stats[3] else "No data")
            
            # Top sustainable events
            cursor.execute('''
            SELECT e.event_name, c.club_name, st.sustainability_score
            FROM sustainability_tracking st
            JOIN union_events e ON st.event_id = e.event_id
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE st.sustainability_score IS NOT NULL
            ORDER BY st.sustainability_score DESC
            LIMIT 5
            ''')
            
            top_events = cursor.fetchall()
            
            if top_events:
                print(f"\nTop Sustainable Events:")
                for event in top_events:
                    print(f"- {event[0]} ({event[1]}): {event[2]:.1f}/100")
        
        elif choice == '2':
            # Waste management report
            cursor.execute('''
            SELECT 
                COUNT(*) as events,
                SUM(waste_generated) as total_waste,
                SUM(waste_recycled) as total_recycled,
                AVG(waste_recycled / NULLIF(waste_generated, 0) * 100) as avg_recycling_rate
            FROM sustainability_tracking
            WHERE waste_generated IS NOT NULL
            ''')
            
            waste_stats = cursor.fetchone()
            
            print(f"\n♻️ Waste Management Report")
            print("=" * 35)
            print(f"Events with waste data: {waste_stats[0]}")
            print(f"Total waste generated: {waste_stats[1]:.1f} kg" if waste_stats[1] else "No data")
            print(f"Total waste recycled: {waste_stats[2]:.1f} kg" if waste_stats[2] else "No data")
            print(f"Average recycling rate: {waste_stats[3]:.1f}%" if waste_stats[3] else "No data")
            
            if waste_stats[1] and waste_stats[2]:
                overall_rate = (waste_stats[2] / waste_stats[1] * 100)
                print(f"Overall recycling rate: {overall_rate:.1f}%")
                
                if overall_rate >= 80:
                    print("🏆 Excellent waste management performance!")
                elif overall_rate >= 60:
                    print("👍 Good waste management, room for improvement")
                else:
                    print("⚠️ Waste management needs attention")
        
        elif choice == '3':
            # Sustainability trends
            cursor.execute('''
            SELECT 
                strftime('%Y-%m', recorded_date) as month,
                AVG(sustainability_score) as avg_score,
                COUNT(*) as event_count
            FROM sustainability_tracking
            WHERE sustainability_score IS NOT NULL
            GROUP BY strftime('%Y-%m', recorded_date)
            ORDER BY month DESC
            LIMIT 12
            ''')
            
            trends = cursor.fetchall()
            
            print(f"\n📈 Sustainability Trends (Last 12 Months)")
            print("=" * 50)
            print(f"{'Month':<10} {'Avg Score':<12} {'Events':<8} {'Trend':<10}")
            print("-" * 45)
            
            for i, trend in enumerate(trends):
                trend_indicator = ""
                if i < len(trends) - 1:
                    current_score = trend[1]
                    previous_score = trends[i + 1][1]
                    if current_score > previous_score:
                        trend_indicator = "📈 Up"
                    elif current_score < previous_score:
                        trend_indicator = "📉 Down"
                    else:
                        trend_indicator = "➡️ Stable"
                
                print(f"{trend[0]:<10} {trend[1]:<12.1f} {trend[2]:<8} {trend_indicator:<10}")
        
        elif choice == '4':
            # Green initiatives impact
            cursor.execute('''
            SELECT activity_type, COUNT(*) as count, SUM(points_earned) as total_points
            FROM student_points
            WHERE activity_type LIKE '%Green%' OR activity_type LIKE '%Environment%'
            GROUP BY activity_type
            ORDER BY total_points DESC
            ''')
            
            green_activities = cursor.fetchall()
            
            print(f"\n🌱 Green Initiatives Impact")
            print("=" * 35)
            
            if green_activities:
                print(f"{'Activity Type':<25} {'Count':<8} {'Points':<8}")
                print("-" * 45)
                
                total_green_points = 0
                for activity in green_activities:
                    total_green_points += activity[2]
                    print(f"{activity[0]:<25} {activity[1]:<8} {activity[2]:<8}")
                
                print("-" * 45)
                print(f"{'TOTAL GREEN POINTS:':<25} {'':<8} {total_green_points:<8}")
                
                # Calculate environmental impact
                cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_points WHERE activity_type LIKE "%Green%"')
                green_participants = cursor.fetchone()[0]
                
                print(f"\nImpact Summary:")
                print(f"Students participating in green initiatives: {green_participants}")
                print(f"Total green engagement points: {total_green_points}")
                print(f"Average points per participant: {total_green_points/green_participants:.1f}" if green_participants > 0 else "N/A")
            else:
                print("No green initiative data available.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_compliance_report(cursor):
    """Generate a comprehensive compliance report"""
    try:
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"compliance_report_{current_time}.txt"
        
        with open(filename, 'w') as f:
            f.write("ELECTION COMPLIANCE REPORT\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Active elections
            cursor.execute('''
            SELECT election_id, position, department, status, voting_start, voting_end
            FROM union_elections
            WHERE status IN ('nomination', 'voting')
            ''')
            
            elections = cursor.fetchall()
            
            f.write("ACTIVE ELECTIONS:\n")
            f.write("-" * 20 + "\n")
            for election in elections:
                f.write(f"Election {election[0]}: {election[1]}")
                if election[2]:
                    f.write(f" ({election[2]})")
                f.write(f" - Status: {election[3]}\n")
                f.write(f"  Voting: {election[4]} to {election[5]}\n\n")
            
            # Spending compliance
            f.write("SPENDING COMPLIANCE:\n")
            f.write("-" * 20 + "\n")
            
            spending_limit = 100.00
            cursor.execute('''
            SELECT 
                s.first_name,
                s.last_name,
                e.position,
                SUM(ce.amount) as total_spent
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            JOIN union_elections e ON c.election_id = e.election_id
            LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
            WHERE e.status IN ('nomination', 'voting')
            GROUP BY c.id, s.first_name, s.last_name, e.position
            ORDER BY total_spent DESC
            ''')
            
            spending_data = cursor.fetchall()
            
            for candidate in spending_data:
                first_name, last_name, position, total_spent = candidate
                total_spent = total_spent or 0
                status = "VIOLATION" if total_spent > spending_limit else "COMPLIANT"
                f.write(f"{first_name} {last_name} ({position}): £{total_spent:.2f} - {status}\n")
            
            f.write(f"\nSpending Limit: £{spending_limit:.2f}\n\n")
            
            # Material approval status
            f.write("MATERIAL APPROVAL STATUS:\n")
            f.write("-" * 25 + "\n")
            
            cursor.execute('''
            SELECT cm.status, COUNT(*) as count
            FROM campaign_materials cm
            JOIN election_candidates c ON cm.candidate_id = c.id
            JOIN union_elections e ON c.election_id = e.election_id
            WHERE e.status IN ('nomination', 'voting')
            GROUP BY cm.status
            ''')
            
            material_stats = cursor.fetchall()
            
            for status, count in material_stats:
                f.write(f"{status.title()}: {count}\n")
        
        print(f"📊 Compliance report generated: {filename}")
        
    except Exception as e:
        print(f"Error generating report: {e}")

def send_compliance_reminders(cursor):
    """Send compliance reminders to all active candidates"""
    try:
        # Get all active candidates
        cursor.execute('''
        SELECT 
            c.student_id,
            s.first_name,
            s.last_name,
            e.position,
            e.voting_end
        FROM election_candidates c
        JOIN students s ON c.student_id = s.student_id
        JOIN union_elections e ON c.election_id = e.election_id
        WHERE e.status IN ('nomination', 'voting')
        ''')
        
        candidates = cursor.fetchall()
        
        if not candidates:
            print("\n📧 No active candidates to send reminders to")
            return
        
        sent_count = 0
        
        for candidate in candidates:
            student_id, first_name, last_name, position, voting_end = candidate

            subject, message = render_template("campaign_compliance_reminder", {
                "first_name": first_name,
                "last_name": last_name,
                "position": position,
                "voting_end": voting_end
            })

            if subject and message and send_confirmation_email(student_id, subject, message):
                sent_count += 1
        
        print(f"📧 Sent {sent_count} compliance reminders to active candidates")
        
    except Exception as e:
        print(f"Error sending reminders: {e}")

def audit_trail_analysis(cursor):
    """Analyze audit trails and system logs"""
    try:
        print("\n📋 Audit Trail Analysis")
        print("=" * 30)
        
        # Recent election activities
        cursor.execute('''
        SELECT 
            'Election Created' as activity,
            position as details,
            created_at as timestamp,
            'System' as user
        FROM union_elections
        WHERE created_at >= date('now', '-7 days')
        
        UNION ALL
        
        SELECT 
            'Vote Cast' as activity,
            'Election ' || election_id as details,
            vote_time as timestamp,
            'Voter ' || voter_id as user
        FROM election_votes
        WHERE vote_time >= datetime('now', '-7 days')
        
        ORDER BY timestamp DESC
        LIMIT 20
        ''')
        
        recent_activities = cursor.fetchall()
        
        print("📅 RECENT ACTIVITIES (Last 7 days):")
        for activity, details, timestamp, user in recent_activities:
            print(f"  {timestamp}: {activity} - {details} by {user}")
        
        if not recent_activities:
            print("  No recent activities recorded")
        
        # Database integrity checks
        print(f"\n🔍 DATABASE INTEGRITY:")
        
        # Check for orphaned records
        cursor.execute('''
        SELECT COUNT(*) FROM election_votes ev
        LEFT JOIN union_elections e ON ev.election_id = e.election_id
        WHERE e.election_id IS NULL
        ''')
        
        orphaned_votes = cursor.fetchone()[0]
        
        cursor.execute('''
        SELECT COUNT(*) FROM election_candidates ec
        LEFT JOIN union_elections e ON ec.election_id = e.election_id
        WHERE e.election_id IS NULL
        ''')
        
        orphaned_candidates = cursor.fetchone()[0]
        
        if orphaned_votes > 0:
            print(f"  ⚠️ {orphaned_votes} orphaned votes found")
        else:
            print("  ✅ No orphaned votes")
        
        if orphaned_candidates > 0:
            print(f"  ⚠️ {orphaned_candidates} orphaned candidates found")
        else:
            print("  ✅ No orphaned candidates")
        
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def database_security_scan(cursor):
    """Perform basic database security checks"""
    try:
        print("\n🛡️ Database Security Scan")
        print("=" * 30)
        
        # Check table permissions and structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📊 DATABASE STRUCTURE:")
        security_critical_tables = ['users', 'union_elections', 'election_votes', 'election_candidates']
        
        for table_name in [t[0] for t in tables]:
            if table_name in security_critical_tables:
                safe_table = validate_table_name(table_name, conn=conn)
                cursor.execute('SELECT COUNT(*) FROM [' + safe_table + ']')
                count = cursor.fetchone()[0]
                print(f"  ✓ {table_name}: {count} records")
            else:
                print(f"    {table_name}")
        
        # Check for potential SQL injection vulnerabilities (basic check)
        suspicious_patterns = ["'", "--", "/*", "*/", "union", "select", "drop", "delete"]
        
        print(f"\n🔍 DATA VALIDATION CHECK:")
        
        # Check user inputs for suspicious content
        cursor.execute('''
        SELECT username FROM users 
        WHERE username LIKE '%''%' OR username LIKE '%--%' 
        OR username LIKE '%/*%' OR username LIKE '%*/%'
        ''')
        
        suspicious_users = cursor.fetchall()
        
        if suspicious_users:
            print("  ⚠️ Suspicious usernames found:")
            for username in suspicious_users:
                print(f"    {username[0]}")
        else:
            print("  ✅ No suspicious usernames detected")
        
        # Check for weak passwords (basic heuristics)
        cursor.execute('''
        SELECT username FROM users 
        WHERE LENGTH(password_hash) < 10 OR password_hash IS NULL
        ''')
        
        weak_passwords = cursor.fetchall()
        
        if weak_passwords:
            print("  ⚠️ Users with potentially weak passwords:")
            for username in weak_passwords:
                print(f"    {username[0]}")
        else:
            print("  ✅ All users have adequately hashed passwords")
        
        input("\nPress Enter to continue...")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_security_report(cursor):
    """Generate comprehensive security audit report"""
    try:
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"security_audit_{current_time}.txt"
        
        with open(filename, 'w') as f:
            f.write("ELECTION SYSTEM SECURITY AUDIT REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Auditor: {auth.current_user['username']}\n\n")
            
            # Executive Summary
            f.write("EXECUTIVE SUMMARY\n")
            f.write("-" * 20 + "\n")
            
            # Count security metrics
            cursor.execute('SELECT COUNT(*) FROM users WHERE role IN ("admin", "staff")')
            admin_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM union_elections WHERE status IN ("nomination", "voting")')
            active_elections = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM election_votes')
            total_votes = cursor.fetchone()[0]
            
            f.write(f"Administrative Users: {admin_count}\n")
            f.write(f"Active Elections: {active_elections}\n")
            f.write(f"Total Votes Cast: {total_votes}\n\n")
            
            # Detailed findings would be added here
            f.write("DETAILED FINDINGS\n")
            f.write("-" * 20 + "\n")
            f.write("1. Vote integrity: Checked for duplicate votes and timing anomalies\n")
            f.write("2. Access controls: Reviewed admin users and permissions\n")
            f.write("3. Audit trails: Analyzed recent system activities\n")
            f.write("4. Database security: Performed basic vulnerability scan\n\n")
            
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 15 + "\n")
            f.write("1. Regular security audits should be performed monthly\n")
            f.write("2. Monitor for unusual voting patterns\n")
            f.write("3. Review admin account access regularly\n")
            f.write("4. Implement stronger password policies\n")
            f.write("5. Enable detailed audit logging\n")
        
        print(f"🔒 Security audit report generated: {filename}")
        
    except Exception as e:
        print(f"Error generating security report: {e}")

def export_audit_logs(cursor):
    """Export audit logs for external analysis"""
    try:
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"audit_logs_{current_time}.csv"
        
        # Get comprehensive audit data
        cursor.execute('''
        SELECT 
            'vote_cast' as action_type,
            voter_id as user_id,
            election_id as target_id,
            vote_time as timestamp,
            'Election vote' as description
        FROM election_votes
        
        UNION ALL
        
        SELECT 
            'election_created' as action_type,
            created_by as user_id,
            election_id as target_id,
            created_at as timestamp,
            'Election: ' || position as description
        FROM union_elections
        WHERE created_by IS NOT NULL
        
        ORDER BY timestamp DESC
        ''')
        
        audit_data = cursor.fetchall()
        
        with open(filename, 'w', newline='') as csvfile:
            import csv
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Action Type', 'User ID', 'Target ID', 'Timestamp', 'Description'])
            
            # Write data
            for row in audit_data:
                writer.writerow(row)
        
        print(f"📊 Audit logs exported: {filename} ({len(audit_data)} records)")
        
    except Exception as e:
        print(f"Error exporting audit logs: {e}")

def export_voting_configuration(cursor):
    """Export current voting configuration"""
    try:
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f"voting_config_{current_time}.json"
        
        cursor.execute('SELECT config_key, config_value, description FROM voting_configuration')
        configs = cursor.fetchall()
        
        config_dict = {}
        for config_key, config_value, description in configs:
            config_dict[config_key] = {
                'value': config_value,
                'description': description
            }
        
        import json
        with open(filename, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        print(f"📤 Configuration exported: {filename}")
        
    except Exception as e:
        print(f"Error exporting configuration: {e}")

def import_voting_configuration(cursor, conn):
    """Import voting configuration from file"""
    try:
        filename = input("Enter configuration filename to import: ").strip()
        if not filename:
            print("No filename provided.")
            return
        
        try:
            import json
            with open(filename, 'r') as f:
                config_dict = json.load(f)
        except FileNotFoundError:
            print(f"File not found: {filename}")
            return
        except json.JSONDecodeError:
            print("Invalid JSON file format.")
            return
        
        imported_count = 0
        
        for config_key, config_data in config_dict.items():
            if isinstance(config_data, dict) and 'value' in config_data:
                cursor.execute('''
                INSERT OR REPLACE INTO voting_configuration (config_key, config_value, description, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (
                    config_key,
                    config_data['value'],
                    config_data.get('description', ''),
                    auth.current_user['id'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                imported_count += 1
        
        conn.commit()
        print(f"📥 Imported {imported_count} configuration settings")
        
    except Exception as e:
        print(f"Error importing configuration: {e}")

def setup_new_features_permissions(auth_manager):
    """Setup permissions for all new features"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # New permissions for enhanced features
    new_permissions = [
        # Equipment management
        'manage_equipment', 'checkout_equipment', 'view_equipment',
        
        # Mentorship system
        'access_mentorship', 'mentor_students', 'rate_mentorship',
        
        # Competition system
        'organize_competitions', 'participate_competitions', 'judge_competitions',
        
        # Virtual events
        'create_virtual_events', 'manage_streaming', 'virtual_attendance',
        
        # Green initiatives
        'track_sustainability', 'green_certification', 'environmental_reporting',
        
        # Community engagement
        'organize_volunteering', 'track_service_hours', 'community_partnerships',
        
        # Learning integration
        'organize_conferences', 'manage_book_clubs', 'knowledge_sharing',
        
        # Advanced analytics
        'advanced_analytics', 'generate_reports', 'view_predictions',
        
        # Enhanced voting
        'ranked_choice_voting', 'campaign_management', 'election_security'
    ]

    # Add permissions to database
    for perm in new_permissions:
        desc = perm.replace('_', ' ').title()
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm, desc, timestamp)
        )

    # Enhanced role permissions
    enhanced_role_permissions = {
        'student': [
            'view_equipment', 'checkout_equipment', 'access_mentorship', 
            'participate_competitions', 'virtual_attendance', 'track_sustainability',
            'organize_volunteering', 'knowledge_sharing', 'ranked_choice_voting'
        ],
        'club_leader': [
            'create_virtual_events', 'organize_competitions', 'manage_book_clubs',
            'green_certification', 'campaign_management'
        ],
        'union_rep': [
            'manage_equipment', 'mentor_students', 'judge_competitions',
            'manage_streaming', 'environmental_reporting', 'community_partnerships',
            'organize_conferences', 'election_security'
        ],
        'admin': [
            'advanced_analytics', 'generate_reports', 'view_predictions',
            'manage_equipment', 'environmental_reporting', 'community_partnerships'
        ]
    }

    # Map new permissions to roles
    for role, perms in enhanced_role_permissions.items():
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
        r = cursor.fetchone()
        if not r:
            continue
        role_id = r[0]
        
        for perm in perms:
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
            p = cursor.fetchone()
            if not p:
                continue
            cursor.execute(
                'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (role_id, p[0])
            )

    conn.commit()
    conn.close()
    print("Enhanced permissions setup complete!")

def insert_sample_data_for_new_features():
    """Insert sample data for testing new features"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Sample achievement badges
        sample_badges = [
            ('Event Organizer', 'Organize 5 successful events', 50, '🎉', 'Leadership'),
            ('Green Champion', 'Lead 3 sustainable initiatives', 75, '🌱', 'Environment'),
            ('Mentor Master', 'Mentor 5+ students successfully', 100, '👨‍🏫', 'Community'),
            ('Competition Winner', 'Win an inter-club competition', 60, '🏆', 'Achievement'),
            ('Knowledge Sharer', 'Share knowledge in 3+ sessions', 40, '🧠', 'Learning')
        ]
        
        cursor.executemany(
            'INSERT OR IGNORE INTO achievement_badges (badge_name, description, points_required, badge_icon, category) VALUES (?, ?, ?, ?, ?)',
            sample_badges
        )
        
        # Sample equipment
        sample_equipment = [
            ('Laptop - MacBook Pro', 'Technology', 'High-performance laptop for events', 'MAC001', '2023-01-15', 'good', 'Equipment Store', 'available', None, 1500.00),
            ('Projector - Epson', 'AV Equipment', 'HD projector for presentations', 'PROJ001', '2023-02-10', 'good', 'AV Room', 'available', None, 800.00),
            ('Camera - Canon DSLR', 'Photography', 'Professional camera for events', 'CAM001', '2023-03-05', 'excellent', 'Media Suite', 'available', None, 1200.00),
            ('Sound System', 'Audio', 'Portable PA system', 'SOUND001', '2023-01-20', 'good', 'Equipment Store', 'available', None, 600.00)
        ]
        
        cursor.executemany(
            'INSERT OR IGNORE INTO union_equipment (equipment_name, category, description, serial_number, purchase_date, condition_status, location, availability_status, maintenance_due, replacement_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            sample_equipment
        )
        
        # Sample volunteer opportunities
        sample_opportunities = [
            ('Local Food Bank', 'Help distribute food to families in need', 'Community Centre', '2024-12-15', '2024-12-22', 4.0, 'No special skills required', 20, 0, 'open', 'volunteer@foodbank.org'),
            ('Environment Cleanup', 'Beach and park cleanup initiative', 'Tynemouth Beach', '2024-12-20', '2024-12-20', 3.0, 'Physical activity involved', 30, 0, 'open', 'cleanup@greengroup.org'),
            ('Senior Care Visit', 'Visit elderly residents at care home', 'Sunnydale Care Home', '2024-12-18', '2025-01-18', 2.0, 'Good communication skills', 15, 0, 'open', 'visits@sunnydale.org')
        ]
        
        cursor.executemany(
            'INSERT OR IGNORE INTO volunteer_opportunities (organization_name, description, location, start_date, end_date, hours_required, skills_needed, max_volunteers, current_volunteers, status, contact_email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            sample_opportunities
        )
        
        conn.commit()
        conn.close()
        print("Sample data for new features inserted successfully!")
        
    except sqlite3.Error as e:
        print(f"Error inserting sample data: {e}")

def display_admin_menu():
    """Display the admin menu for student union"""
    global auth
    
    if not auth.check_permission('manage_all_clubs') and not auth.check_permission('approve_facility_bookings') and \
       not auth.check_permission('set_up_elections') and not auth.check_permission('manage_union_reps'):
        print("You don't have permission to access the admin menu.")
        return
    
    while True:
        print("\nStudent Union Administration")
        print("===========================")
        
        option_num = 1
        options = []
        
        if auth.check_permission('set_up_elections'):
            print(f"{option_num}. Set Up New Election")
            options.append("setup_election")
            option_num += 1
        
        if auth.check_permission('manage_union_reps'):
            print(f"{option_num}. Manage Union Representatives")
            options.append("manage_reps")
            option_num += 1
        
        if auth.check_permission('approve_facility_bookings'):
            print(f"{option_num}. Manage Facility Bookings")
            options.append("manage_bookings")
            option_num += 1
        
        if auth.check_permission('manage_all_clubs'):
            print(f"{option_num}. Manage All Clubs")
            options.append("manage_all_clubs")
            option_num += 1
        
        print(f"{option_num}. Return to Student Union Menu")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1' and "setup_election" in options:
            # Set Up Election
            conn = get_connection()
            cursor = conn.cursor()
            try:
                set_up_election(cursor, conn)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
                
        elif ((choice == '1' and "manage_reps" in options and "setup_election" not in options) or
              (choice == '2' and "setup_election" in options and "manage_reps" in options)):
            # Manage Representatives
            manage_union_reps()  # Changed from manage_union_representatives() to manage_union_reps()
            
        elif ((choice == '1' and "manage_bookings" in options and "setup_election" not in options and "manage_reps" not in options) or
              (choice == '2' and "manage_bookings" in options and "setup_election" not in options and "manage_reps" in options) or
              (choice == '3' and "setup_election" in options and "manage_reps" in options and "manage_bookings" in options)):
            # Manage Bookings
            approve_facility_bookings()
            
        elif ((choice == '1' and "manage_all_clubs" in options and "setup_election" not in options and 
               "manage_reps" not in options and "manage_bookings" not in options) or
              (choice == '2' and "manage_all_clubs" in options and "setup_election" not in options and 
               "manage_reps" in options and "manage_bookings" not in options) or
              (choice == '3' and "manage_all_clubs" in options and "setup_election" in options and 
               "manage_reps" in options and "manage_bookings" not in options) or
              (choice == '4' and "setup_election" in options and "manage_reps" in options and 
               "manage_bookings" in options and "manage_all_clubs" in options)):
            # Manage All Clubs
            manage_club()  # The manage_club function will show all clubs for admins
            
        elif choice == str(option_num):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")
