from datetime import datetime, timedelta
from university_system.infrastructure.database.db import sqlite3, DatabaseManager
import random
import contextlib
import re
import os
import csv
import pandas as pd
import json
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import time
import threading
from collections import defaultdict
from university_system.modules.shared.utils.finance_integration import record_revenue_to_finance
from university_system.core.sql_safety import validate_identifier

# Import statements for external integrations (would need to be installed)
try:
    import qrcode
    from PIL import Image
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.cluster import KMeans
    import stripe  # For payment processing
    import twilio  # For SMS
    from linkedin_api import Linkedin  # For LinkedIn integration
except ImportError as e:
    print(f"Optional dependency not installed: {e}")

# Original imports
# Use utilities from the refactored modules
from university_system.infrastructure.email import (
    send_alumni_welcome_email,
    send_event_invitation,
    send_donation_receipt,
    send_mentorship_notification,
)
from university_system.infrastructure.email.email_service import send_email
from university_system.infrastructure.email.template_utils import load_template, render_template
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.constants import paths

DB_PATH = str(paths.DEFAULT_DB_PATH)

# Use this function for all DB operations safely
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

# Retry wrapper for locked DB
def safe_execute(cursor, query, params=(), retries=3, delay=1.0):
    for attempt in range(retries):
        try:
            cursor.execute(query, params)
            return
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e).lower():
                print(f"[Retry] DB locked, retrying ({attempt+1}/{retries})...")
                time.sleep(delay)
            else:
                raise
    raise sqlite3.OperationalError("DB is locked after multiple retries.")

# Import auth instance management from user_authentication
import threading

try:
    from university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# Thread-safe auth instance management
_auth = None
_auth_lock = threading.Lock()


def get_auth():
    """Get the auth instance in a thread-safe manner."""
    with _auth_lock:
        return _auth


def set_auth(auth_instance):
    """Set the auth instance in a thread-safe manner."""
    global _auth
    with _auth_lock:
        _auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)


# Backward compatibility: 'auth' property for legacy code
# NOTE: Direct access to 'auth' is deprecated; use get_auth() instead
class _AuthProxy:
    """Proxy class for backward-compatible 'auth' global access."""
    def __getattr__(self, name):
        instance = get_auth()
        if instance is None:
            return None
        return getattr(instance, name)

    def __bool__(self):
        return get_auth() is not None


auth = _AuthProxy()

# Enhanced permissions setup for all new features
def setup_alumni_permissions():
    permissions = [
        # Original permissions
        ('manage_alumni', 'Manage alumni records and profiles'),
        ('view_alumni', 'View all alumni records'),
        ('view_own_alumni_profile', 'View own alumni profile'),
        ('make_donation', 'Make donations to the institution'),
        ('view_own_donations', 'View own donation history'),
        ('manage_mentorships', 'Manage alumni-student mentorship programs'),
        
        # New feature permissions
        ('access_alumni_directory', 'Access public alumni directory'),
        ('manage_alumni_directory', 'Manage alumni directory settings'),
        ('send_newsletters', 'Send newsletters and bulk communications'),
        ('manage_communication', 'Manage communication system'),
        ('post_jobs', 'Post job opportunities'),
        ('view_job_board', 'View job board'),
        ('manage_job_board', 'Manage job board system'),
        ('schedule_career_counseling', 'Schedule career counseling sessions'),
        ('provide_career_counseling', 'Provide career counseling services'),
        ('manage_events_advanced', 'Advanced event management features'),
        ('process_payments', 'Process event and donation payments'),
        ('manage_campaigns', 'Manage fundraising campaigns'),
        ('view_analytics', 'View analytics and reports'),
        ('manage_social_features', 'Manage social features and engagement'),
        ('moderate_forum', 'Moderate alumni forum discussions'),
        ('manage_integrations', 'Manage system integrations'),
        ('admin_security', 'Administer security settings'),
        ('view_audit_logs', 'View system audit logs'),
        ('manage_ai_features', 'Manage AI-powered features'),
        ('manage_gamification', 'Manage gamification features'),
        ('manage_content', 'Manage content and publications'),
        ('ambassador_program', 'Participate in ambassador program'),
        ('manage_ambassadors', 'Manage ambassador program')
    ]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for perm, desc in permissions:
            safe_execute(cursor, '''
                INSERT OR IGNORE INTO permissions (permission_name, description, created_at)
                VALUES (?, ?, ?)''', (perm, desc, timestamp))

        # Enhanced role mappings
        role_mappings = {
            'admin': [p[0] for p in permissions],  # Admin gets all permissions
            'staff': [
                'manage_alumni', 'view_alumni', 'manage_alumni_directory',
                'send_newsletters', 'manage_communication', 'manage_job_board',
                'provide_career_counseling', 'manage_events_advanced',
                'process_payments', 'manage_campaigns', 'view_analytics',
                'manage_social_features', 'moderate_forum', 'manage_ambassadors'
            ],
            'student': [
                'view_own_alumni_profile', 'make_donation', 'view_own_donations',
                'access_alumni_directory', 'view_job_board', 'schedule_career_counseling'
            ],
            'alumni': [
                'view_own_alumni_profile', 'make_donation', 'view_own_donations',
                'access_alumni_directory', 'post_jobs', 'view_job_board',
                'schedule_career_counseling', 'ambassador_program'
            ],
            'parent': ['access_alumni_directory', 'view_job_board'],
            'instructor': [
                'view_alumni', 'access_alumni_directory', 'manage_job_board',
                'provide_career_counseling', 'view_analytics'
            ]
        }

        for role, perms in role_mappings.items():
            safe_execute(cursor, 'SELECT id FROM roles WHERE role_name = ?', (role,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
            role_id = role_result[0]

            for perm in perms:
                safe_execute(cursor, 'SELECT id FROM permissions WHERE permission_name = ?', (perm,))
                perm_result = cursor.fetchone()
                if perm_result:
                    perm_id = perm_result[0]
                    safe_execute(cursor, '''
                        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                        VALUES (?, ?)''', (role_id, perm_id))

        conn.commit()
        print("Enhanced alumni permissions and role mappings set up successfully.")

class Alumni:
    def __init__(self, alumni_id, student_id, email_address, title, first_name, middle_name, 
                 last_name, gender, dob, graduation_year, degree_earned, current_employer, 
                 job_title, industry, address, city, country, phone, linkedin_url, 
                 date_registered, is_donor=False, is_mentor=False, is_board_member=False):
        
        self.alumni_id = alumni_id
        self.student_id = student_id
        self.email_address = email_address
        self.title = title
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.gender = gender
        self.dob = dob
        self.graduation_year = graduation_year
        self.degree_earned = degree_earned
        self.current_employer = current_employer
        self.job_title = job_title
        self.industry = industry
        self.address = address
        self.city = city
        self.country = country
        self.phone = phone
        self.linkedin_url = linkedin_url
        self.date_registered = date_registered
        self.is_donor = is_donor
        self.is_mentor = is_mentor
        self.is_board_member = is_board_member

def init_alumni_db():
    """Initialize the enhanced alumni database with all new tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Original tables (keeping existing structure)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni (
            alumni_id TEXT PRIMARY KEY,
            student_id TEXT,
            email_address TEXT,
            title TEXT,
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            gender TEXT,
            dob TEXT,
            graduation_year INTEGER,
            degree_earned TEXT,
            current_employer TEXT,
            job_title TEXT,
            industry TEXT,
            address TEXT,
            city TEXT,
            country TEXT,
            phone TEXT,
            linkedin_url TEXT,
            date_registered TEXT,
            is_donor BOOLEAN,
            is_mentor BOOLEAN,
            is_board_member BOOLEAN,
            profile_photo TEXT,
            bio TEXT,
            skills TEXT,
            achievements TEXT,
            privacy_level INTEGER DEFAULT 1,
            engagement_score INTEGER DEFAULT 0,
            last_activity TEXT,
            social_media_links TEXT,
            is_ambassador BOOLEAN DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Enhanced alumni events table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT,
            event_date TEXT,
            event_location TEXT,
            event_description TEXT,
            registration_required BOOLEAN,
            max_attendees INTEGER,
            event_fee REAL DEFAULT 0.0,
            payment_required BOOLEAN DEFAULT 0,
            event_type TEXT DEFAULT 'in-person',
            virtual_link TEXT,
            qr_code_path TEXT,
            created_by TEXT,
            created_date TEXT,
            registration_deadline TEXT,
            waitlist_enabled BOOLEAN DEFAULT 1
        )
        ''')
        
        # Event registrations with payment info
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_registrations (
            registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            alumni_id TEXT,
            registration_date TEXT,
            attendance_confirmed BOOLEAN,
            payment_status TEXT DEFAULT 'pending',
            payment_amount REAL DEFAULT 0.0,
            payment_method TEXT,
            is_waitlisted BOOLEAN DEFAULT 0,
            check_in_time TEXT,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Enhanced donations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            donation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            amount REAL,
            donation_date TEXT,
            campaign TEXT,
            campaign_id INTEGER,
            payment_method TEXT,
            is_recurring BOOLEAN,
            recurring_frequency TEXT,
            receipt_sent BOOLEAN,
            notes TEXT,
            donation_type TEXT DEFAULT 'general',
            tribute_type TEXT,
            tribute_name TEXT,
            employer_match_eligible BOOLEAN DEFAULT 0,
            employer_match_amount REAL DEFAULT 0.0,
            recognition_level TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (campaign_id) REFERENCES fundraising_campaigns (campaign_id)
        )
        ''')
        
        # Enhanced mentorships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS mentorships (
            mentorship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_id TEXT,
            mentee_id TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT,
            focus_area TEXT,
            notes TEXT,
            match_score REAL DEFAULT 0.0,
            meeting_frequency TEXT,
            communication_preference TEXT,
            goals TEXT,
            FOREIGN KEY (mentor_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Alumni Directory Search & Networking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_directory_settings (
            alumni_id TEXT PRIMARY KEY,
            show_contact_info BOOLEAN DEFAULT 1,
            show_employment BOOLEAN DEFAULT 1,
            show_education BOOLEAN DEFAULT 1,
            searchable BOOLEAN DEFAULT 1,
            networking_available BOOLEAN DEFAULT 1,
            mentor_available BOOLEAN DEFAULT 0,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Communication System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS newsletters (
            newsletter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            template_id INTEGER,
            target_audience TEXT,
            send_date TEXT,
            created_date TEXT,
            created_by TEXT,
            status TEXT DEFAULT 'draft',
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT,
            template_content TEXT,
            template_type TEXT,
            created_date TEXT,
            created_by TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_forum (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id TEXT,
            title TEXT,
            content TEXT,
            category TEXT,
            post_date TEXT,
            last_updated TEXT,
            reply_count INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            is_pinned BOOLEAN DEFAULT 0,
            FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS forum_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            author_id TEXT,
            content TEXT,
            reply_date TEXT,
            parent_reply_id INTEGER,
            FOREIGN KEY (post_id) REFERENCES alumni_forum (post_id),
            FOREIGN KEY (author_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Job Board & Career Services
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            posted_by TEXT,
            company_name TEXT,
            job_title TEXT,
            job_description TEXT,
            location TEXT,
            job_type TEXT,
            salary_range TEXT,
            requirements TEXT,
            application_method TEXT,
            contact_email TEXT,
            post_date TEXT,
            expiry_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            category TEXT,
            experience_level TEXT,
            FOREIGN KEY (posted_by) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            applicant_id TEXT,
            application_date TEXT,
            status TEXT DEFAULT 'submitted',
            cover_letter TEXT,
            resume_path TEXT,
            FOREIGN KEY (job_id) REFERENCES job_postings (job_id),
            FOREIGN KEY (applicant_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS career_counseling (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            counselor_id TEXT,
            client_id TEXT,
            session_date TEXT,
            session_type TEXT,
            duration INTEGER,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            follow_up_required BOOLEAN DEFAULT 0,
            FOREIGN KEY (counselor_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (client_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Fundraising Campaigns
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fundraising_campaigns (
            campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT,
            description TEXT,
            goal_amount REAL,
            current_amount REAL DEFAULT 0.0,
            start_date TEXT,
            end_date TEXT,
            created_by TEXT,
            created_date TEXT,
            status TEXT DEFAULT 'active',
            category TEXT,
            is_featured BOOLEAN DEFAULT 0
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS donor_recognition (
            recognition_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            recognition_level TEXT,
            total_donated REAL,
            recognition_date TEXT,
            benefits TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Social Features & Engagement
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            achievement_title TEXT,
            achievement_description TEXT,
            achievement_date TEXT,
            category TEXT,
            verification_status TEXT DEFAULT 'pending',
            verified_by TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_reunions (
            reunion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            graduation_year INTEGER,
            reunion_date TEXT,
            location TEXT,
            organizer_id TEXT,
            description TEXT,
            registration_fee REAL DEFAULT 0.0,
            max_attendees INTEGER,
            created_date TEXT,
            FOREIGN KEY (organizer_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS regional_chapters (
            chapter_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_name TEXT,
            location TEXT,
            coordinator_id TEXT,
            description TEXT,
            created_date TEXT,
            member_count INTEGER DEFAULT 0,
            FOREIGN KEY (coordinator_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS chapter_memberships (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER,
            alumni_id TEXT,
            join_date TEXT,
            role TEXT DEFAULT 'member',
            FOREIGN KEY (chapter_id) REFERENCES regional_chapters (chapter_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Gamification System
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS engagement_points (
            point_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            activity_type TEXT,
            points_earned INTEGER,
            activity_date TEXT,
            description TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievement_badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_name TEXT,
            badge_description TEXT,
            points_required INTEGER,
            badge_icon TEXT,
            category TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_badges (
            alumni_badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            badge_id INTEGER,
            earned_date TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (badge_id) REFERENCES achievement_badges (badge_id)
        )
        ''')
        
        # Content Management
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumni_stories (
            story_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            title TEXT,
            content TEXT,
            story_type TEXT,
            publish_date TEXT,
            is_featured BOOLEAN DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            category TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS photo_gallery (
            photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            uploaded_by TEXT,
            photo_path TEXT,
            caption TEXT,
            upload_date TEXT,
            is_featured BOOLEAN DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id),
            FOREIGN KEY (uploaded_by) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Advanced Networking
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS networking_connections (
            connection_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id TEXT,
            recipient_id TEXT,
            connection_date TEXT,
            status TEXT DEFAULT 'pending',
            message TEXT,
            FOREIGN KEY (requester_id) REFERENCES alumni (alumni_id),
            FOREIGN KEY (recipient_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_directory (
            business_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            business_name TEXT,
            business_description TEXT,
            industry TEXT,
            website TEXT,
            contact_email TEXT,
            services_offered TEXT,
            location TEXT,
            created_date TEXT,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # System Integration & Analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_integrations (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            integration_name TEXT,
            integration_type TEXT,
            api_endpoint TEXT,
            api_key TEXT,
            status TEXT DEFAULT 'active',
            last_sync TEXT,
            sync_frequency TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            activity_type TEXT,
            activity_description TEXT,
            timestamp TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_data (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            metric_date TEXT,
            category TEXT,
            additional_data TEXT
        )
        ''')
        
        # Ambassador Program
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ambassador_program (
            ambassador_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumni_id TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT DEFAULT 'active',
            region TEXT,
            activities TEXT,
            performance_score REAL DEFAULT 0.0,
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Event Surveys and Feedback
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_surveys (
            survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            survey_title TEXT,
            questions TEXT,
            created_date TEXT,
            FOREIGN KEY (event_id) REFERENCES alumni_events (event_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS survey_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_id INTEGER,
            alumni_id TEXT,
            responses TEXT,
            submission_date TEXT,
            FOREIGN KEY (survey_id) REFERENCES event_surveys (survey_id),
            FOREIGN KEY (alumni_id) REFERENCES alumni (alumni_id)
        )
        ''')
        
        # Initialize default data
        init_default_enhanced_data(cursor)
        
        conn.commit()
        conn.close()
        print("Enhanced alumni database initialized successfully with all new features!")
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced alumni database: {e}")

def init_default_enhanced_data(cursor):
    """Initialize default data for enhanced features"""
    # Create default email templates
    default_templates = [
        ('Welcome Email', 'Welcome to our Alumni Network! We are excited to have you join our community.', 'welcome'),
        ('Event Invitation', 'You are invited to our upcoming alumni event. Please find details below.', 'event'),
        ('Newsletter Template', 'Alumni Newsletter - Stay connected with your alma mater and fellow alumni.', 'newsletter'),
        ('Job Posting', 'New job opportunity available through our alumni network.', 'job'),
        ('Donation Thank You', 'Thank you for your generous donation to our institution.', 'donation')
    ]
    
    for name, content, template_type in default_templates:
        cursor.execute('''
            INSERT OR IGNORE INTO email_templates (template_name, template_content, template_type, created_date, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, content, template_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'system'))
    
    # Create default achievement badges
    default_badges = [
        ('New Member', 'Welcome to the alumni community!', 0, 'badge_new.png', 'engagement'),
        ('Active Networker', 'Made 10 networking connections', 100, 'badge_network.png', 'networking'),
        ('Generous Donor', 'Made your first donation', 50, 'badge_donor.png', 'giving'),
        ('Event Enthusiast', 'Attended 5 events', 150, 'badge_events.png', 'events'),
        ('Mentor', 'Became a mentor to fellow alumni', 200, 'badge_mentor.png', 'mentoring'),
        ('Ambassador', 'Joined the ambassador program', 300, 'badge_ambassador.png', 'leadership')
    ]
    
    for name, desc, points, icon, category in default_badges:
        cursor.execute('''
            INSERT OR IGNORE INTO achievement_badges (badge_name, badge_description, points_required, badge_icon, category)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, desc, points, icon, category))
    
    # Create default fundraising campaign
    cursor.execute('''
        INSERT OR IGNORE INTO fundraising_campaigns 
        (campaign_name, description, goal_amount, start_date, end_date, created_by, created_date, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'Annual Alumni Fund 2025',
        'Support current students and enhance campus facilities through your alumni contributions.',
        100000.0,
        '2025-01-01',
        '2025-12-31',
        'system',
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Annual Fund'
    ))

# ALUMNI DIRECTORY & SEARCH FEATURES

def setup_alumni_directory():
    """Set up alumni directory preferences"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to set up directory preferences.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    print("\nAlumni Directory Privacy Settings")
    print("=================================")
    
    # Check if settings exist
    cursor.execute('SELECT * FROM alumni_directory_settings WHERE alumni_id = ?', (alumni_id,))
    existing_settings = cursor.fetchone()
    
    if existing_settings:
        print("Current settings:")
        print(f"Show Contact Info: {'Yes' if existing_settings[1] else 'No'}")
        print(f"Show Employment: {'Yes' if existing_settings[2] else 'No'}")
        print(f"Show Education: {'Yes' if existing_settings[3] else 'No'}")
        print(f"Searchable: {'Yes' if existing_settings[4] else 'No'}")
        print(f"Available for Networking: {'Yes' if existing_settings[5] else 'No'}")
        print(f"Available as Mentor: {'Yes' if existing_settings[6] else 'No'}")
    
    print("\nUpdate your directory settings:")
    show_contact = input("Show contact information in directory? (y/n): ").lower() == 'y'
    show_employment = input("Show employment information? (y/n): ").lower() == 'y'
    show_education = input("Show education information? (y/n): ").lower() == 'y'
    searchable = input("Make profile searchable? (y/n): ").lower() == 'y'
    networking_available = input("Available for networking? (y/n): ").lower() == 'y'
    mentor_available = input("Available as mentor? (y/n): ").lower() == 'y'
    
    # Update or insert settings
    cursor.execute('''
        INSERT OR REPLACE INTO alumni_directory_settings 
        (alumni_id, show_contact_info, show_employment, show_education, searchable, networking_available, mentor_available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, show_contact, show_employment, show_education, searchable, networking_available, mentor_available))
    
    conn.commit()
    conn.close()
    
    print("Directory settings updated successfully!")

def register_alumni():
    """Register a new alumni"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to register alumni.")
        return
    
    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to register alumni.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nRegister New Alumni")
        print("===================")
        
        # Generate alumni ID
        while True:
            try:
                cursor.execute('SELECT COUNT(*) FROM alumni')
                count = cursor.fetchone()[0]
                alumni_id = f"A{count + 1:06d}"  # Format: A000001, A000002, etc.
                
                # Check if ID already exists
                cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (alumni_id,))
                if not cursor.fetchone():
                    break
                    
            except sqlite3.Error as e:
                print(f"Error generating alumni ID: {e}")
                conn.close()
                return
        
        print(f"New Alumni ID: {alumni_id}")
        
        # Get student ID (optional)
        student_id = input("Student ID (if applicable, press Enter to skip): ").strip()
        if student_id:
            try:
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    print("Warning: Student ID not found in student records.")
                    confirm = input("Continue anyway? (y/n): ").lower()
                    if confirm != 'y':
                        conn.close()
                        return
            except sqlite3.Error as e:
                print(f"Error validating student ID: {e}")
        
        # Personal Information
        print("\nPersonal Information:")
        title = input("Title (Mr./Ms./Dr./etc.): ").strip()
        
        first_name = input("First Name: ").strip()
        while not first_name:
            print("Error: First name is required.")
            first_name = input("First Name: ").strip()
        
        middle_name = input("Middle Name (optional): ").strip()
        
        last_name = input("Last Name: ").strip()
        while not last_name:
            print("Error: Last name is required.")
            last_name = input("Last Name: ").strip()
        
        # Email validation
        email_address = input("Email Address: ").strip()
        while not email_address or '@' not in email_address:
            print("Error: Valid email address is required.")
            email_address = input("Email Address: ").strip()
        
        # Check for duplicate email
        try:
            cursor.execute('SELECT alumni_id FROM alumni WHERE email_address = ?', (email_address,))
            if cursor.fetchone():
                print("Error: Email address already exists in alumni records.")
                conn.close()
                return
        except sqlite3.Error as e:
            print(f"Error checking email: {e}")
        
        # Gender
        gender_options = ["Male", "Female", "Other", "Prefer not to say"]
        print("\nGender Options:")
        for i, option in enumerate(gender_options, 1):
            print(f"{i}. {option}")
        
        while True:
            try:
                gender_choice = input("Select gender (1-4): ").strip()
                if gender_choice.isdigit() and 1 <= int(gender_choice) <= 4:
                    gender = gender_options[int(gender_choice) - 1]
                    break
                else:
                    print("Please enter a number between 1 and 4.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Date of Birth
        while True:
            dob = input("Date of Birth (YYYY-MM-DD): ").strip()
            if not dob:
                break  # Optional field
            try:
                datetime.strptime(dob, "%Y-%m-%d")
                # Check if reasonable date
                birth_year = int(dob.split('-')[0])
                current_year = datetime.now().year
                if birth_year < 1900 or birth_year > current_year - 16:
                    print("Please enter a reasonable birth year.")
                    continue
                break
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD or press Enter to skip.")
        
        # Academic Information
        print("\nAcademic Information:")
        while True:
            try:
                graduation_year = int(input("Graduation Year: "))
                current_year = datetime.now().year
                if graduation_year < 1900 or graduation_year > current_year + 10:
                    print("Please enter a reasonable graduation year.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid year.")
        
        degree_earned = input("Degree Earned: ").strip()
        while not degree_earned:
            print("Error: Degree information is required.")
            degree_earned = input("Degree Earned: ").strip()
        
        # Employment Information
        print("\nEmployment Information (optional):")
        current_employer = input("Current Employer: ").strip()
        job_title = input("Job Title: ").strip()
        industry = input("Industry: ").strip()
        
        # Contact Information
        print("\nContact Information:")
        address = input("Address: ").strip()
        city = input("City: ").strip()
        country = input("Country: ").strip()
        
        phone = input("Phone Number: ").strip()
        linkedin_url = input("LinkedIn URL (optional): ").strip()
        
        # Additional Information
        print("\nAdditional Information (optional):")
        bio = input("Biography/Description: ").strip()
        skills = input("Skills (comma-separated): ").strip()
        achievements = input("Notable Achievements: ").strip()
        
        # Role assignments
        print("\nRole Assignments:")
        is_donor = input("Is this alumni a donor? (y/n): ").lower() == 'y'
        is_mentor = input("Available as mentor? (y/n): ").lower() == 'y'
        is_board_member = input("Is board member? (y/n): ").lower() == 'y'
        is_ambassador = input("Alumni ambassador? (y/n): ").lower() == 'y'
        
        # Privacy settings
        privacy_level = 1  # Default public
        privacy_choice = input("Privacy Level (1=Public, 2=Alumni Only, 3=Private): ").strip()
        if privacy_choice in ['1', '2', '3']:
            privacy_level = int(privacy_choice)
        
        # Insert alumni record
        try:
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            safe_execute(cursor, '''
                INSERT INTO alumni 
                (alumni_id, student_id, email_address, title, first_name, middle_name, 
                 last_name, gender, dob, graduation_year, degree_earned, current_employer, 
                 job_title, industry, address, city, country, phone, linkedin_url, 
                 date_registered, is_donor, is_mentor, is_board_member, bio, skills, 
                 achievements, privacy_level, is_ambassador, engagement_score, last_activity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (alumni_id, student_id, email_address, title, first_name, middle_name,
                  last_name, gender, dob, graduation_year, degree_earned, current_employer,
                  job_title, industry, address, city, country, phone, linkedin_url,
                  current_datetime, is_donor, is_mentor, is_board_member, bio, skills,
                  achievements, privacy_level, is_ambassador, 0, current_datetime))
            
            # Set up default directory settings
            safe_execute(cursor, '''
                INSERT INTO alumni_directory_settings 
                (alumni_id, show_contact_info, show_employment, show_education, 
                 searchable, networking_available, mentor_available)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (alumni_id, True, True, True, True, True, is_mentor))
            
            conn.commit()
            
            print(f"\n✅ Alumni registered successfully!")
            print(f"Alumni ID: {alumni_id}")
            print(f"Name: {first_name} {last_name}")
            print(f"Email: {email_address}")
            print(f"Graduation Year: {graduation_year}")
            
            # Award initial engagement points
            award_engagement_points(alumni_id, 'profile_complete', 50)
            
            # Send welcome email (if email utilities are available)
            try:
                send_alumni_welcome_email(alumni_id, email_address, first_name)
                print("Welcome email sent successfully!")
            except Exception as e:
                print(f"Note: Could not send welcome email: {e}")
                
        except sqlite3.Error as e:
            print(f"Error inserting alumni record: {e}")
            conn.rollback()
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def view_alumni():
    """View alumni records"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view alumni records.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nView Alumni Records")
        print("===================")
        print("1. View All Alumni")
        print("2. Search by Name")
        print("3. Search by Graduation Year")
        print("4. Search by Industry")
        print("5. Search by Location")
        print("6. View Alumni Details")
        
        choice = input("Enter your choice: ").strip()
        
        alumni_list = []
        
        if choice == '1':
            # View all alumni (with permission check)
            if not auth.check_permission('view_alumni'):
                print("You don't have permission to view all alumni records.")
                conn.close()
                return
                
            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year, 
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    ORDER BY last_name, first_name
                ''')
                alumni_list = cursor.fetchall()
                
            except sqlite3.Error as e:
                print(f"Error retrieving alumni records: {e}")
                conn.close()
                return
                
        elif choice == '2':
            # Search by name
            search_name = input("Enter name (partial match allowed): ").strip()
            if not search_name:
                print("Search term cannot be empty.")
                conn.close()
                return
                
            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year, 
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE first_name LIKE ? OR last_name LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{search_name}%', f'%{search_name}%'))
                alumni_list = cursor.fetchall()
                
            except sqlite3.Error as e:
                print(f"Error searching alumni: {e}")
                conn.close()
                return
                
        elif choice == '3':
            # Search by graduation year
            try:
                grad_year = int(input("Enter graduation year: "))
                
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year, 
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE graduation_year = ?
                    ORDER BY last_name, first_name
                ''', (grad_year,))
                alumni_list = cursor.fetchall()
                
            except ValueError:
                print("Error: Please enter a valid year.")
                conn.close()
                return
            except sqlite3.Error as e:
                print(f"Error searching by graduation year: {e}")
                conn.close()
                return
                
        elif choice == '4':
            # Search by industry
            industry = input("Enter industry: ").strip()
            if not industry:
                print("Industry cannot be empty.")
                conn.close()
                return
                
            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year, 
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE industry LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{industry}%',))
                alumni_list = cursor.fetchall()
                
            except sqlite3.Error as e:
                print(f"Error searching by industry: {e}")
                conn.close()
                return
                
        elif choice == '5':
            # Search by location
            location = input("Enter city or country: ").strip()
            if not location:
                print("Location cannot be empty.")
                conn.close()
                return
                
            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year, 
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE city LIKE ? OR country LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{location}%', f'%{location}%'))
                alumni_list = cursor.fetchall()
                
            except sqlite3.Error as e:
                print(f"Error searching by location: {e}")
                conn.close()
                return
                
        elif choice == '6':
            # View specific alumni details
            alumni_id = input("Enter Alumni ID: ").strip()
            if not alumni_id:
                print("Alumni ID cannot be empty.")
                conn.close()
                return
                
            view_alumni_details(alumni_id, cursor)
            conn.close()
            return
            
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        # Display results
        if not alumni_list:
            print("No alumni found matching your criteria.")
        else:
            print(f"\nFound {len(alumni_list)} alumni:")
            print("-" * 100)
            print(f"{'ID':<8} {'Name':<25} {'Year':<6} {'Employer':<20} {'Title':<20} {'Location':<15}")
            print("-" * 100)
            
            for alumni in alumni_list:
                alumni_id, first_name, last_name, grad_year, employer, job_title, city, country, email = alumni
                
                name = f"{first_name} {last_name}"
                employer = employer or "N/A"
                job_title = job_title or "N/A"
                location = f"{city or ''}, {country or ''}".strip(', ') or "N/A"
                
                print(f"{alumni_id:<8} {name[:24]:<25} {grad_year:<6} {employer[:19]:<20} {job_title[:19]:<20} {location[:14]:<15}")
            
            print("-" * 100)
            
            # Option to view details
            if auth.check_permission('view_alumni'):
                view_details = input("\nWould you like to view details for a specific alumni? (y/n): ").lower()
                if view_details == 'y':
                    alumni_id = input("Enter Alumni ID: ").strip()
                    if alumni_id:
                        view_alumni_details(alumni_id, cursor)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def view_alumni_details(alumni_id, cursor):
    """View detailed information for a specific alumni"""
    try:
        safe_execute(cursor, 'SELECT * FROM alumni WHERE alumni_id = ?', (alumni_id,))
        alumni_data = cursor.fetchone()
        
        if not alumni_data:
            print(f"Alumni with ID {alumni_id} not found.")
            return
        
        # Check privacy permissions
        privacy_level = alumni_data[18] if len(alumni_data) > 18 else 1
        
        current_user_id = None
        if auth and auth.current_user:
            cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            if result:
                current_user_id = result[0]
        
        # Privacy check
        if privacy_level == 3 and current_user_id != alumni_id and not auth.check_permission('view_alumni'):
            print("This alumni profile is private.")
            return
        
        print(f"\n{'='*60}")
        print(f"ALUMNI DETAILS - {alumni_data[0]}")
        print(f"{'='*60}")
        
        # Personal Information
        print("\nPersonal Information:")
        print(f"Name: {alumni_data[3] or ''} {alumni_data[4]} {alumni_data[5] or ''} {alumni_data[6]}")
        print(f"Email: {alumni_data[2]}")
        print(f"Gender: {alumni_data[7] or 'Not specified'}")
        print(f"Date of Birth: {alumni_data[8] or 'Not specified'}")
        print(f"Phone: {alumni_data[17] or 'Not specified'}")
        
        # Academic Information
        print("\nAcademic Information:")
        print(f"Student ID: {alumni_data[1] or 'Not specified'}")
        print(f"Graduation Year: {alumni_data[9]}")
        print(f"Degree: {alumni_data[10]}")
        
        # Employment Information
        if privacy_level <= 2 or current_user_id == alumni_id or auth.check_permission('view_alumni'):
            print("\nEmployment Information:")
            print(f"Current Employer: {alumni_data[11] or 'Not specified'}")
            print(f"Job Title: {alumni_data[12] or 'Not specified'}")
            print(f"Industry: {alumni_data[13] or 'Not specified'}")
        
        # Contact Information
        if privacy_level <= 1 or current_user_id == alumni_id or auth.check_permission('view_alumni'):
            print("\nContact Information:")
            print(f"Address: {alumni_data[14] or 'Not specified'}")
            print(f"City: {alumni_data[15] or 'Not specified'}")
            print(f"Country: {alumni_data[16] or 'Not specified'}")
            print(f"LinkedIn: {alumni_data[18] or 'Not specified'}")
        
        # Additional Information
        if len(alumni_data) > 23 and alumni_data[23]:  # bio
            print(f"\nBiography:")
            print(alumni_data[23])
        
        if len(alumni_data) > 24 and alumni_data[24]:  # skills
            print(f"\nSkills: {alumni_data[24]}")
        
        if len(alumni_data) > 25 and alumni_data[25]:  # achievements
            print(f"\nAchievements: {alumni_data[25]}")
        
        # Status Information
        print("\nStatus:")
        status_items = []
        if alumni_data[20]:  # is_donor
            status_items.append("Donor")
        if alumni_data[21]:  # is_mentor
            status_items.append("Mentor")
        if alumni_data[22]:  # is_board_member
            status_items.append("Board Member")
        if len(alumni_data) > 27 and alumni_data[27]:  # is_ambassador
            status_items.append("Ambassador")
        
        print(f"Roles: {', '.join(status_items) if status_items else 'None'}")
        print(f"Registration Date: {alumni_data[19]}")
        
        if len(alumni_data) > 28:  # engagement_score
            print(f"Engagement Score: {alumni_data[28] or 0}")
        
        if len(alumni_data) > 29:  # last_activity
            print(f"Last Activity: {alumni_data[29] or 'Never'}")
        
        print(f"{'='*60}")
        
    except sqlite3.Error as e:
        print(f"Error retrieving alumni details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def update_alumni():
    """Update alumni record"""
    global auth

    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to update alumni records.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Determine which alumni record to update
        if auth.check_permission("manage_alumni"):
            alumni_id = input("Enter Alumni ID to update: ").strip()
            if not alumni_id:
                print("Alumni ID cannot be empty.")
                conn.close()
                return
        else:
            cursor.execute("SELECT username FROM users WHERE id = ?", (auth.current_user["id"],))
            result = cursor.fetchone()
            if result and result[0].startswith("A"):
                alumni_id = result[0]
            else:
                print("You do not have permission to update this alumni record.")
                conn.close()
                return

        # Fetch current data
        cursor.execute("SELECT * FROM alumni WHERE alumni_id = ?", (alumni_id,))
        current_data = cursor.fetchone()
        if not current_data:
            print(f"No alumni found with ID {alumni_id}")
            conn.close()
            return

        # Map current_data to a list for index access if needed
        updates = {}

        def prompt_bool(field_name, current_value, prompt_text):
            new = input(f"{prompt_text} (current: {current_value}) (y/n): ").strip().lower()
            if new in ("y", "n"):
                return new == "y"
            return None

        # Example of updating flags
        if len(current_data) > 20:
            current_donor = current_data[20]
            new_donor = prompt_bool("is_donor", current_donor, "Is Donor")
            if new_donor is not None:
                updates["is_donor"] = new_donor

            current_mentor = current_data[21]
            new_mentor = prompt_bool("is_mentor", current_mentor, "Is Mentor")
            if new_mentor is not None:
                updates["is_mentor"] = new_mentor

            current_board = current_data[22]
            new_board = prompt_bool("is_board_member", current_board, "Is Board Member")
            if new_board is not None:
                updates["is_board_member"] = new_board

            if len(current_data) > 27:
                current_ambassador = current_data[27]
                new_ambassador = prompt_bool("is_ambassador", current_ambassador, "Is Ambassador")
                if new_ambassador is not None:
                    updates["is_ambassador"] = new_ambassador

        if not updates:
            print("No changes made.")
            conn.close()
            return

        # Build update query safely
        _ALLOWED_COLUMNS = frozenset({
            'is_donor', 'is_mentor', 'is_board_member', 'is_ambassador',
            'first_name', 'last_name', 'email', 'phone', 'address',
            'city', 'state', 'country', 'graduation_year', 'degree',
            'major', 'employer', 'job_title', 'industry', 'linkedin_url',
        })
        set_clauses = []
        values = []
        for field, value in updates.items():
            if field not in _ALLOWED_COLUMNS:
                raise ValueError(f"Invalid column name: {field}")
            set_clauses.append(f"{validate_identifier(field, 'column')} = ?")
            values.append(value)
        values.append(alumni_id)
        query = f"UPDATE alumni SET {', '.join(set_clauses)} WHERE alumni_id = ?"
        try:
            cursor.execute(query, tuple(values))
            conn.commit()
            print(f"Updated alumni {alumni_id}: {', '.join(updates.keys())}")
        except Exception as e:
            print(f"Failed to update alumni: {e}")
            conn.rollback()
        finally:
            conn.close()

    except Exception as exc:
        print(f"Unexpected error in update_alumni: {exc}")
def view_events():
   """View alumni events"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to view events.")
       return
   
   if not (auth.check_permission('view_events') or auth.check_permission('manage_events') or 
           auth.check_permission('manage_events_advanced')):
       print("You don't have permission to view events.")
       return
   
   try:
       conn = get_connection()
       cursor = conn.cursor()
       
       print("\nView Alumni Events")
       print("==================")
       print("1. View Upcoming Events")
       print("2. View Past Events")
       print("3. View All Events")
       print("4. Search Events")
       print("5. My Event Registrations")
       
       choice = input("Enter your choice: ").strip()
       
       events_list = []
       
       if choice == '1':
           # Upcoming events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, event_name, event_date, event_location, event_description, 
                          registration_required, max_attendees, event_fee, payment_required, 
                          event_type, created_by, registration_deadline
                   FROM alumni_events
                   WHERE datetime(event_date) >= datetime('now')
                   ORDER BY event_date ASC
               ''')
               events_list = cursor.fetchall()
               
           except sqlite3.Error as e:
               print(f"Error retrieving upcoming events: {e}")
               conn.close()
               return
               
       elif choice == '2':
           # Past events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, event_name, event_date, event_location, event_description, 
                          registration_required, max_attendees, event_fee, payment_required, 
                          event_type, created_by, registration_deadline
                   FROM alumni_events
                   WHERE datetime(event_date) < datetime('now')
                   ORDER BY event_date DESC
                   LIMIT 20
               ''')
               events_list = cursor.fetchall()
               
           except sqlite3.Error as e:
               print(f"Error retrieving past events: {e}")
               conn.close()
               return
               
       elif choice == '3':
           # All events
           try:
               safe_execute(cursor, '''
                   SELECT event_id, event_name, event_date, event_location, event_description, 
                          registration_required, max_attendees, event_fee, payment_required, 
                          event_type, created_by, registration_deadline
                   FROM alumni_events
                   ORDER BY event_date DESC
               ''')
               events_list = cursor.fetchall()
               
           except sqlite3.Error as e:
               print(f"Error retrieving all events: {e}")
               conn.close()
               return
               
       elif choice == '4':
           # Search events
           search_events(cursor)
           conn.close()
           return
           
       elif choice == '5':
           # My registrations
           view_my_event_registrations(cursor)
           conn.close()
           return
           
       else:
           print("Invalid choice.")
           conn.close()
           return
       
       # Display events
       if not events_list:
           print("No events found.")
       else:
           print(f"\nFound {len(events_list)} events:")
           print("-" * 120)
           print(f"{'ID':<5} {'Event Name':<30} {'Date':<19} {'Location':<20} {'Type':<10} {'Fee':<8} {'Reg Req':<8}")
           print("-" * 120)
           
           for event in events_list:
               event_id, name, date, location, desc, reg_req, max_att, fee, pay_req, event_type, created_by, reg_deadline = event
               
               # Format data for display
               name_display = name[:29] if name else "N/A"
               location_display = location[:19] if location else "N/A"
               event_type_display = event_type[:9] if event_type else "N/A"
               fee_display = f"${fee:.2f}" if fee and fee > 0 else "Free"
               reg_req_display = "Yes" if reg_req else "No"
               
               # Check if event is in the past
               try:
                   event_datetime = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
                   if event_datetime < datetime.now():
                       name_display += " (Past)"
               except (ValueError, TypeError):
                   pass
               
               print(f"{event_id:<5} {name_display:<30} {date:<19} {location_display:<20} "
                     f"{event_type_display:<10} {fee_display:<8} {reg_req_display:<8}")
           
           print("-" * 120)
           
           # Option to view event details
           view_details = input("\nWould you like to view details for a specific event? (y/n): ").lower()
           if view_details == 'y':
               try:
                   event_id = int(input("Enter Event ID: "))
                   view_event_details(event_id, cursor)
               except ValueError:
                   print("Please enter a valid Event ID.")
               except Exception as e:
                   print(f"Error viewing event details: {e}")
       
   except sqlite3.Error as e:
       print(f"Database error: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")
   finally:
       try:
           conn.close()
       except Exception:
           pass


def search_events(cursor):
   """Search events by various criteria"""
   print("\nSearch Events")
   print("=============")
   print("1. Search by Event Name")
   print("2. Search by Date Range")
   print("3. Search by Location")
   print("4. Search by Event Type")
   print("5. Search Free Events")
   
   choice = input("Enter your choice: ").strip()
   
   try:
       if choice == '1':
           # Search by name
           event_name = input("Enter event name (partial match): ").strip()
           if not event_name:
               print("Event name cannot be empty.")
               return
           
           safe_execute(cursor, '''
               SELECT event_id, event_name, event_date, event_location, event_fee, event_type
               FROM alumni_events
               WHERE event_name LIKE ?
               ORDER BY event_date DESC
           ''', (f'%{event_name}%',))
           
       elif choice == '2':
           # Search by date range
           start_date = input("Enter start date (YYYY-MM-DD): ").strip()
           end_date = input("Enter end date (YYYY-MM-DD): ").strip()
           
           try:
               datetime.strptime(start_date, "%Y-%m-%d")
               datetime.strptime(end_date, "%Y-%m-%d")
           except ValueError:
               print("Invalid date format.")
               return
           
           safe_execute(cursor, '''
               SELECT event_id, event_name, event_date, event_location, event_fee, event_type
               FROM alumni_events
               WHERE date(event_date) BETWEEN ? AND ?
               ORDER BY event_date ASC
           ''', (start_date, end_date))
           
       elif choice == '3':
           # Search by location
           location = input("Enter location: ").strip()
           if not location:
               print("Location cannot be empty.")
               return
           
           safe_execute(cursor, '''
               SELECT event_id, event_name, event_date, event_location, event_fee, event_type
               FROM alumni_events
               WHERE event_location LIKE ?
               ORDER BY event_date DESC
           ''', (f'%{location}%',))
           
       elif choice == '4':
           # Search by event type
           event_types = ["in-person", "virtual", "hybrid"]
           print("\nEvent Types:")
           for i, etype in enumerate(event_types, 1):
               print(f"{i}. {etype}")
           
           type_choice = input("Select event type (1-3): ").strip()
           if type_choice in ['1', '2', '3']:
               selected_type = event_types[int(type_choice) - 1]
               
               safe_execute(cursor, '''
                   SELECT event_id, event_name, event_date, event_location, event_fee, event_type
                   FROM alumni_events
                   WHERE event_type = ?
                   ORDER BY event_date DESC
               ''', (selected_type,))
           else:
               print("Invalid choice.")
               return
               
       elif choice == '5':
           # Search free events
           safe_execute(cursor, '''
               SELECT event_id, event_name, event_date, event_location, event_fee, event_type
               FROM alumni_events
               WHERE event_fee = 0 OR event_fee IS NULL
               ORDER BY event_date DESC
           ''')
           
       else:
           print("Invalid choice.")
           return
       
       results = cursor.fetchall()
       
       if not results:
           print("No events found matching your criteria.")
       else:
           print(f"\nFound {len(results)} events:")
           print("-" * 90)
           print(f"{'ID':<5} {'Event Name':<30} {'Date':<19} {'Location':<20} {'Fee':<10}")
           print("-" * 90)
           
           for event in results:
               event_id, name, date, location, fee, event_type = event
               name_display = name[:29] if name else "N/A"
               location_display = location[:19] if location else "N/A"
               fee_display = f"${fee:.2f}" if fee and fee > 0 else "Free"
               
               print(f"{event_id:<5} {name_display:<30} {date:<19} {location_display:<20} {fee_display:<10}")
           
           print("-" * 90)
       
   except sqlite3.Error as e:
       print(f"Error searching events: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")


def view_event_details(event_id, cursor):
   """View detailed information for a specific event"""
   try:
       safe_execute(cursor, 'SELECT * FROM alumni_events WHERE event_id = ?', (event_id,))
       event_data = cursor.fetchone()
       
       if not event_data:
           print(f"Event with ID {event_id} not found.")
           return
       
       print(f"\n{'='*70}")
       print(f"EVENT DETAILS - ID: {event_data[0]}")
       print(f"{'='*70}")
       
       print(f"Event Name: {event_data[1]}")
       print(f"Date & Time: {event_data[2]}")
       print(f"Location: {event_data[3]}")
       print(f"Event Type: {event_data[8] or 'in-person'}")
       
       if event_data[9]:  # virtual_link
           print(f"Virtual Link: {event_data[9]}")
       
       print(f"\nDescription:")
       print(event_data[4] or "No description available")
       
       print(f"\nRegistration Details:")
       print(f"Registration Required: {'Yes' if event_data[5] else 'No'}")
       
       if event_data[5]:  # registration_required
           print(f"Registration Deadline: {event_data[12] or 'Event date'}")
           
           if event_data[6]:  # max_attendees
               print(f"Maximum Attendees: {event_data[6]}")
               
               # Get current registration count
               safe_execute(cursor, '''
                   SELECT COUNT(*) FROM event_registrations 
                   WHERE event_id = ? AND is_waitlisted = 0
               ''', (event_id,))
               current_registrations = cursor.fetchone()[0]
               
               print(f"Current Registrations: {current_registrations}")
               remaining_spots = event_data[6] - current_registrations
               print(f"Remaining Spots: {max(0, remaining_spots)}")
               
               if remaining_spots <= 0 and event_data[13]:  # waitlist_enabled
                   print("Waitlist: Available")
           else:
               print("Maximum Attendees: Unlimited")
       
       print(f"\nPayment Information:")
       if event_data[7]:  # payment_required
           print(f"Event Fee: ${event_data[6]:.2f}")
           print("Payment Required: Yes")
       else:
           print("Event Fee: Free")
           print("Payment Required: No")
       
       print(f"\nEvent Management:")
       print(f"Created By: {event_data[10]}")
       print(f"Created Date: {event_data[11]}")
       
       if event_data[14]:  # qr_code_path
           print(f"QR Code: Available for check-in")
       
       print(f"{'='*70}")
       
       # Show registration status for current user
       if auth and auth.current_user:
           cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
           result = cursor.fetchone()
           if result and result[0].startswith('A'):
               user_alumni_id = result[0]
               
               safe_execute(cursor, '''
                   SELECT * FROM event_registrations 
                   WHERE event_id = ? AND alumni_id = ?
               ''', (event_id, user_alumni_id))
               
               registration = cursor.fetchone()
               
               if registration:
                   status = "Waitlisted" if registration[7] else "Registered"
                   payment_status = registration[5] if registration[5] else "N/A"
                   print(f"\nYour Status: {status}")
                   print(f"Registration Date: {registration[3]}")
                   if event_data[7]:  # payment_required
                       print(f"Payment Status: {payment_status}")
               else:
                   print(f"\nYou are not registered for this event.")
       
   except sqlite3.Error as e:
       print(f"Error retrieving event details: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")


def view_my_event_registrations(cursor):
   """View current user's event registrations"""
   global auth
   
   if not auth or not auth.current_user:
       print("You must be logged in to view your registrations.")
       return
   
   try:
       # Get current user's alumni ID
       cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
       result = cursor.fetchone()
       if not result or not result[0].startswith('A'):
           print("Alumni profile not found for current user.")
           return
       
       user_alumni_id = result[0]
       
       # Get registrations
       safe_execute(cursor, '''
           SELECT er.*, ae.event_name, ae.event_date, ae.event_location, ae.event_fee
           FROM event_registrations er
           JOIN alumni_events ae ON er.event_id = ae.event_id
           WHERE er.alumni_id = ?
           ORDER BY ae.event_date DESC
       ''', (user_alumni_id,))
       
       registrations = cursor.fetchall()
       
       if not registrations:
           print("You are not registered for any events.")
           return
       
       print(f"\nYour Event Registrations ({len(registrations)} total):")
       print("-" * 100)
       print(f"{'Event Name':<30} {'Date':<19} {'Status':<12} {'Payment':<10} {'Attended':<10}")
       print("-" * 100)
       
       for reg in registrations:
           event_name = reg[9][:29] if reg[9] else "N/A"
           event_date = reg[10]
           status = "Waitlisted" if reg[7] else "Registered"
           payment_status = reg[5] if reg[5] else "N/A"
           attended = "Yes" if reg[4] else "No"
           
           # Check if event is in the past
           try:
               event_datetime = datetime.strptime(event_date, "%Y-%m-%d %H:%M:%S")
               if event_datetime < datetime.now():
                   status += " (Past)"
           except (ValueError, TypeError):
               pass
           
           print(f"{event_name:<30} {event_date:<19} {status:<12} {payment_status:<10} {attended:<10}")
       
       print("-" * 100)
       
   except sqlite3.Error as e:
       print(f"Error retrieving your registrations: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")

def register_for_event():
    """Register for an event"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to register for events.")
        return

    try:
        event_id = input("Enter event ID to register for: ")
        if not event_id:
            print("Event ID is required.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if event exists
        cursor.execute('SELECT * FROM alumni_events WHERE event_id = ?', (event_id,))
        if not cursor.fetchone():
            print(f"Event {event_id} not found.")
            conn.close()
            return

        # Register for event
        cursor.execute('''
            INSERT INTO alumni_event_registrations (event_id, user_id, registration_date, status)
            VALUES (?, ?, ?, 'registered')
        ''', (event_id, auth.current_user['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()
        print(f"Successfully registered for event {event_id}!")
    except sqlite3.IntegrityError:
        print("You are already registered for this event.")
    except Exception as e:
        print(f"Error registering for event: {e}")

def record_donation():
    """Record a donation"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to record a donation.")
        return

    try:
        amount = float(input("Enter donation amount: $"))
        purpose = input("Enter donation purpose (scholarship/infrastructure/general): ") or "general"

        conn = get_db_connection()
        cursor = conn.cursor()

        donation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO alumni_donations (user_id, amount, purpose, donation_date, payment_status)
            VALUES (?, ?, ?, ?, 'completed')
        ''', (auth.current_user['user_id'], amount, purpose, donation_date))

        donation_id = cursor.lastrowid
        conn.commit()

        # Record donation to central finance system
        finance_payment_id = record_revenue_to_finance(
            student_id=auth.current_user.get('username', 'EXTERNAL'),
            amount=amount,
            revenue_category='Donation',
            transaction_source='Alumni',
            transaction_ref=f'DONATION-{donation_id}',
            payment_method='Various',
            notes=f'Alumni donation for {purpose}'
        )

        print(f"Donation of ${amount:.2f} recorded successfully. Thank you for your generosity!")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        # Automatically send donation receipt email
        try:
            # Get alumni ID and email from current user
            cursor.execute('''
                SELECT ap.alumni_id, ap.email
                FROM alumni_profiles ap
                JOIN users u ON ap.alumni_id = u.username
                WHERE u.id = ?
            ''', (auth.current_user['user_id'],))

            result = cursor.fetchone()
            if result:
                alumni_id, email = result
                send_donation_receipt(
                    alumni_id=alumni_id,
                    donation_id=donation_id,
                    email_address=email,
                    amount=amount,
                    donation_date=donation_date,
                    purpose=purpose
                )
                print("✉️  Donation receipt sent to your email")
            else:
                print("⚠️  Could not send receipt: Alumni profile not found")
        except Exception as e:
            print(f"⚠️  Could not send donation receipt email: {e}")

        conn.close()
    except ValueError:
        print("Invalid amount entered.")
    except Exception as e:
        print(f"Error recording donation: {e}")

def view_donations():
    """View donations"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view donations.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT donation_id, amount, purpose, donation_date, payment_status
            FROM alumni_donations
            WHERE user_id = ?
            ORDER BY donation_date DESC
        ''', (auth.current_user['user_id'],))

        donations = cursor.fetchall()
        conn.close()

        if not donations:
            print("\nNo donations found.")
            return

        print("\n--- Your Donations ---")
        print(f"{'ID':<10} {'Amount':<12} {'Purpose':<20} {'Date':<20} {'Status':<15}")
        print("-" * 80)
        for donation in donations:
            print(f"{donation[0]:<10} ${donation[1]:<11.2f} {donation[2]:<20} {donation[3]:<20} {donation[4]:<15}")

        total = sum(d[1] for d in donations)
        print(f"\nTotal donations: ${total:.2f}")
    except Exception as e:
        print(f"Error viewing donations: {e}")

def setup_mentorship():
    """Set up a mentorship"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to set up mentorship.")
        return

    try:
        print("\n--- Set Up Mentorship ---")
        print("1. Become a Mentor")
        print("2. Find a Mentor")
        choice = input("Enter your choice (1-2): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            expertise = input("Enter your area of expertise: ")
            availability = input("Enter your availability (weekly/monthly): ") or "monthly"

            cursor.execute('''
                INSERT INTO alumni_mentorships (mentor_id, expertise, availability, status, created_date)
                VALUES (?, ?, ?, 'active', ?)
            ''', (auth.current_user['user_id'], expertise, availability, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("You are now registered as a mentor!")

        elif choice == '2':
            cursor.execute('''
                SELECT mentor_id, expertise, availability
                FROM alumni_mentorships
                WHERE status = 'active'
            ''')
            mentors = cursor.fetchall()

            if not mentors:
                print("No mentors currently available.")
                conn.close()
                return

            print("\nAvailable Mentors:")
            for i, mentor in enumerate(mentors, 1):
                print(f"{i}. ID: {mentor[0]}, Expertise: {mentor[1]}, Availability: {mentor[2]}")

            mentor_choice = input("\nEnter mentor number to request mentorship (or 0 to cancel): ")
            if mentor_choice.isdigit() and 0 < int(mentor_choice) <= len(mentors):
                selected_mentor = mentors[int(mentor_choice) - 1]
                cursor.execute('''
                    INSERT INTO alumni_mentorship_requests (mentor_id, mentee_id, request_date, status)
                    VALUES (?, ?, ?, 'pending')
                ''', (selected_mentor[0], auth.current_user['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                print("Mentorship request sent!")

        conn.close()
    except Exception as e:
        print(f"Error setting up mentorship: {e}")

def view_mentorships():
    """View mentorships"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view mentorships.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # View as mentor
        cursor.execute('''
            SELECT mentee_id, request_date, status
            FROM alumni_mentorship_requests
            WHERE mentor_id = ?
            ORDER BY request_date DESC
        ''', (auth.current_user['user_id'],))
        mentee_requests = cursor.fetchall()

        # View as mentee
        cursor.execute('''
            SELECT mentor_id, request_date, status
            FROM alumni_mentorship_requests
            WHERE mentee_id = ?
            ORDER BY request_date DESC
        ''', (auth.current_user['user_id'],))
        mentor_requests = cursor.fetchall()

        conn.close()

        print("\n--- Your Mentorships ---")

        if mentee_requests:
            print("\nAs Mentor:")
            print(f"{'Mentee ID':<15} {'Request Date':<20} {'Status':<15}")
            print("-" * 50)
            for req in mentee_requests:
                print(f"{req[0]:<15} {req[1]:<20} {req[2]:<15}")

        if mentor_requests:
            print("\nAs Mentee:")
            print(f"{'Mentor ID':<15} {'Request Date':<20} {'Status':<15}")
            print("-" * 50)
            for req in mentor_requests:
                print(f"{req[0]:<15} {req[1]:<20} {req[2]:<15}")

        if not mentee_requests and not mentor_requests:
            print("No mentorships found.")
    except Exception as e:
        print(f"Error viewing mentorships: {e}")

def generate_alumni_report():
    """Generate alumni reports"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to generate alumni reports.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("\n--- Alumni Report ---")

        # Total alumni count
        cursor.execute('SELECT COUNT(*) FROM user_accounts WHERE role = "alumni"')
        total_alumni = cursor.fetchone()[0]
        print(f"Total Alumni: {total_alumni}")

        # Event participation
        cursor.execute('SELECT COUNT(*) FROM alumni_event_registrations')
        total_registrations = cursor.fetchone()[0]
        print(f"Total Event Registrations: {total_registrations}")

        # Donations
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM alumni_donations')
        donation_stats = cursor.fetchone()
        print(f"Total Donations: {donation_stats[0]}")
        print(f"Total Amount Donated: ${donation_stats[1] or 0:.2f}")

        # Mentorships
        cursor.execute('SELECT COUNT(*) FROM alumni_mentorships WHERE status = "active"')
        active_mentors = cursor.fetchone()[0]
        print(f"Active Mentors: {active_mentors}")

        conn.close()
        print("\nReport generated successfully!")
    except Exception as e:
        print(f"Error generating alumni report: {e}")

def view_my_photos():
    """View photos uploaded by current user"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view your photos.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT photo_id, title, upload_date, status
            FROM alumni_photos
            WHERE user_id = ?
            ORDER BY upload_date DESC
        ''', (auth.current_user['user_id'],))

        photos = cursor.fetchall()
        conn.close()

        if not photos:
            print("\nYou haven't uploaded any photos yet.")
            return

        print("\n--- Your Photos ---")
        print(f"{'Photo ID':<12} {'Title':<30} {'Upload Date':<20} {'Status':<15}")
        print("-" * 80)
        for photo in photos:
            print(f"{photo[0]:<12} {photo[1]:<30} {photo[2]:<20} {photo[3]:<15}")
    except Exception as e:
        print(f"Error viewing photos: {e}")

def moderate_photos():
    """Moderate photos in gallery"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to moderate photos.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to moderate photos.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT photo_id, title, user_id, upload_date, status
            FROM alumni_photos
            WHERE status = 'pending'
            ORDER BY upload_date ASC
        ''')

        photos = cursor.fetchall()

        if not photos:
            print("\nNo photos pending moderation.")
            conn.close()
            return

        print("\n--- Photos Pending Moderation ---")
        for photo in photos:
            print(f"\nPhoto ID: {photo[0]}")
            print(f"Title: {photo[1]}")
            print(f"Uploaded by: {photo[2]}")
            print(f"Upload Date: {photo[3]}")

            action = input("Action (approve/reject/skip): ").lower()

            if action == 'approve':
                cursor.execute('UPDATE alumni_photos SET status = "approved" WHERE photo_id = ?', (photo[0],))
                print(f"Photo {photo[0]} approved.")
            elif action == 'reject':
                reason = input("Enter rejection reason: ")
                cursor.execute('UPDATE alumni_photos SET status = "rejected" WHERE photo_id = ?', (photo[0],))
                print(f"Photo {photo[0]} rejected.")
            elif action == 'skip':
                continue

        conn.commit()
        conn.close()
        print("\nModeration complete!")
    except Exception as e:
        print(f"Error moderating photos: {e}")

def manage_existing_reunion():
    """Manage an existing reunion"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage reunions.")
        return

    try:
        reunion_id = input("Enter reunion ID to manage: ")
        if not reunion_id:
            print("Reunion ID is required.")
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM alumni_reunions WHERE reunion_id = ?', (reunion_id,))
        reunion = cursor.fetchone()

        if not reunion:
            print(f"Reunion {reunion_id} not found.")
            conn.close()
            return

        print("\n--- Manage Reunion ---")
        print("1. Update Details")
        print("2. View Attendees")
        print("3. Cancel Reunion")
        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            new_location = input("Enter new location (or press Enter to skip): ")
            new_date = input("Enter new date (YYYY-MM-DD, or press Enter to skip): ")

            if new_location:
                cursor.execute('UPDATE alumni_reunions SET location = ? WHERE reunion_id = ?', (new_location, reunion_id))
            if new_date:
                cursor.execute('UPDATE alumni_reunions SET reunion_date = ? WHERE reunion_id = ?', (new_date, reunion_id))

            conn.commit()
            print("Reunion updated successfully!")

        elif choice == '2':
            cursor.execute('''
                SELECT user_id, rsvp_status
                FROM alumni_reunion_attendees
                WHERE reunion_id = ?
            ''', (reunion_id,))
            attendees = cursor.fetchall()

            print("\nAttendees:")
            for attendee in attendees:
                print(f"User ID: {attendee[0]}, RSVP: {attendee[1]}")

        elif choice == '3':
            confirm = input("Are you sure you want to cancel this reunion? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute('UPDATE alumni_reunions SET status = "cancelled" WHERE reunion_id = ?', (reunion_id,))
                conn.commit()
                print("Reunion cancelled.")

        conn.close()
    except Exception as e:
        print(f"Error managing reunion: {e}")

def view_class_reunions():
    """View class reunions"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view reunions.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT reunion_id, class_year, reunion_date, location, status
            FROM alumni_reunions
            WHERE status = 'active' OR status = 'upcoming'
            ORDER BY reunion_date ASC
        ''')

        reunions = cursor.fetchall()
        conn.close()

        if not reunions:
            print("\nNo upcoming reunions scheduled.")
            return

        print("\n--- Class Reunions ---")
        print(f"{'Reunion ID':<15} {'Class Year':<12} {'Date':<20} {'Location':<25} {'Status':<12}")
        print("-" * 90)
        for reunion in reunions:
            print(f"{reunion[0]:<15} {reunion[1]:<12} {reunion[2]:<20} {reunion[3]:<25} {reunion[4]:<12}")
    except Exception as e:
        print(f"Error viewing reunions: {e}")

def view_my_chapters():
    """View chapters user belongs to"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view your chapters.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ac.chapter_id, ac.name, ac.location, acm.role, acm.join_date
            FROM alumni_chapters ac
            JOIN alumni_chapter_members acm ON ac.chapter_id = acm.chapter_id
            WHERE acm.user_id = ?
            ORDER BY acm.join_date DESC
        ''', (auth.current_user['user_id'],))

        chapters = cursor.fetchall()
        conn.close()

        if not chapters:
            print("\nYou are not a member of any chapters yet.")
            return

        print("\n--- Your Chapters ---")
        print(f"{'Chapter ID':<15} {'Name':<25} {'Location':<20} {'Your Role':<15} {'Join Date':<15}")
        print("-" * 95)
        for chapter in chapters:
            print(f"{chapter[0]:<15} {chapter[1]:<25} {chapter[2]:<20} {chapter[3]:<15} {chapter[4]:<15}")
    except Exception as e:
        print(f"Error viewing chapters: {e}")

def admin_manage_chapters():
    """Admin management of chapters"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage chapters.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to manage chapters.")
        return

    try:
        print("\n--- Manage Chapters ---")
        print("1. Create New Chapter")
        print("2. View All Chapters")
        print("3. Update Chapter")
        print("4. Delete Chapter")
        choice = input("Enter your choice (1-4): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            name = input("Enter chapter name: ")
            location = input("Enter location: ")
            description = input("Enter description: ")

            cursor.execute('''
                INSERT INTO alumni_chapters (name, location, description, created_date, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, location, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("Chapter created successfully!")

        elif choice == '2':
            cursor.execute('SELECT chapter_id, name, location, status FROM alumni_chapters')
            chapters = cursor.fetchall()

            print("\n--- All Chapters ---")
            print(f"{'Chapter ID':<15} {'Name':<30} {'Location':<25} {'Status':<12}")
            print("-" * 85)
            for chapter in chapters:
                print(f"{chapter[0]:<15} {chapter[1]:<30} {chapter[2]:<25} {chapter[3]:<12}")

        elif choice == '3':
            chapter_id = input("Enter chapter ID to update: ")
            new_name = input("Enter new name (or press Enter to skip): ")
            new_location = input("Enter new location (or press Enter to skip): ")

            if new_name:
                cursor.execute('UPDATE alumni_chapters SET name = ? WHERE chapter_id = ?', (new_name, chapter_id))
            if new_location:
                cursor.execute('UPDATE alumni_chapters SET location = ? WHERE chapter_id = ?', (new_location, chapter_id))

            conn.commit()
            print("Chapter updated successfully!")

        elif choice == '4':
            chapter_id = input("Enter chapter ID to delete: ")
            confirm = input(f"Are you sure you want to delete chapter {chapter_id}? (yes/no): ")

            if confirm.lower() == 'yes':
                cursor.execute('DELETE FROM alumni_chapters WHERE chapter_id = ?', (chapter_id,))
                conn.commit()
                print("Chapter deleted.")

        conn.close()
    except Exception as e:
        print(f"Error managing chapters: {e}")

def update_business_listing():
    """Update existing business listing"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to update business listings.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find user's existing listings
        cursor.execute('''
            SELECT listing_id, business_name, category, description
            FROM alumni_business_listings
            WHERE user_id = ?
        ''', (auth.current_user['user_id'],))

        listings = cursor.fetchall()

        if not listings:
            print("\nYou don't have any business listings yet.")
            conn.close()
            return

        print("\n--- Your Business Listings ---")
        for i, listing in enumerate(listings, 1):
            print(f"{i}. {listing[1]} ({listing[2]})")

        choice = input("\nEnter listing number to update (or 0 to cancel): ")
        if not choice.isdigit() or not (0 < int(choice) <= len(listings)):
            print("Invalid choice.")
            conn.close()
            return

        selected = listings[int(choice) - 1]
        listing_id = selected[0]

        print(f"\nUpdating: {selected[1]}")
        new_name = input(f"New business name (current: {selected[1]}, press Enter to skip): ")
        new_category = input(f"New category (current: {selected[2]}, press Enter to skip): ")
        new_description = input(f"New description (current: {selected[3]}, press Enter to skip): ")

        if new_name:
            cursor.execute('UPDATE alumni_business_listings SET business_name = ? WHERE listing_id = ?', (new_name, listing_id))
        if new_category:
            cursor.execute('UPDATE alumni_business_listings SET category = ? WHERE listing_id = ?', (new_category, listing_id))
        if new_description:
            cursor.execute('UPDATE alumni_business_listings SET description = ? WHERE listing_id = ?', (new_description, listing_id))

        cursor.execute('UPDATE alumni_business_listings SET updated_date = ? WHERE listing_id = ?',
                      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), listing_id))

        conn.commit()
        conn.close()
        print("Business listing updated successfully!")
    except Exception as e:
        print(f"Error updating business listing: {e}")

def manage_campaigns():
    """Manage fundraising campaigns"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage campaigns.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to manage campaigns.")
        return

    try:
        print("\n--- Manage Fundraising Campaigns ---")
        print("1. Create New Campaign")
        print("2. View All Campaigns")
        print("3. Update Campaign")
        print("4. View Campaign Progress")
        choice = input("Enter your choice (1-4): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            name = input("Enter campaign name: ")
            goal = float(input("Enter fundraising goal: $"))
            end_date = input("Enter end date (YYYY-MM-DD): ")
            description = input("Enter description: ")

            cursor.execute('''
                INSERT INTO alumni_campaigns (name, goal, current_amount, end_date, description, status, created_date)
                VALUES (?, ?, 0, ?, ?, 'active', ?)
            ''', (name, goal, end_date, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("Campaign created successfully!")

        elif choice == '2':
            cursor.execute('''
                SELECT campaign_id, name, goal, current_amount, end_date, status
                FROM alumni_campaigns
                ORDER BY created_date DESC
            ''')
            campaigns = cursor.fetchall()

            print("\n--- All Campaigns ---")
            print(f"{'Campaign ID':<15} {'Name':<25} {'Goal':<12} {'Current':<12} {'End Date':<15} {'Status':<12}")
            print("-" * 95)
            for campaign in campaigns:
                progress = (campaign[3] / campaign[2] * 100) if campaign[2] > 0 else 0
                print(f"{campaign[0]:<15} {campaign[1]:<25} ${campaign[2]:<11.2f} ${campaign[3]:<11.2f} {campaign[4]:<15} {campaign[5]:<12}")

        elif choice == '3':
            campaign_id = input("Enter campaign ID to update: ")
            new_goal = input("Enter new goal (or press Enter to skip): ")
            new_status = input("Enter new status (active/completed/cancelled, or press Enter to skip): ")

            if new_goal:
                cursor.execute('UPDATE alumni_campaigns SET goal = ? WHERE campaign_id = ?', (float(new_goal), campaign_id))
            if new_status:
                cursor.execute('UPDATE alumni_campaigns SET status = ? WHERE campaign_id = ?', (new_status, campaign_id))

            conn.commit()
            print("Campaign updated successfully!")

        elif choice == '4':
            campaign_id = input("Enter campaign ID: ")
            cursor.execute('''
                SELECT name, goal, current_amount, end_date, status
                FROM alumni_campaigns
                WHERE campaign_id = ?
            ''', (campaign_id,))
            campaign = cursor.fetchone()

            if campaign:
                progress = (campaign[2] / campaign[1] * 100) if campaign[1] > 0 else 0
                print(f"\n--- Campaign Progress ---")
                print(f"Name: {campaign[0]}")
                print(f"Goal: ${campaign[1]:.2f}")
                print(f"Current Amount: ${campaign[2]:.2f}")
                print(f"Progress: {progress:.1f}%")
                print(f"End Date: {campaign[3]}")
                print(f"Status: {campaign[4]}")
            else:
                print("Campaign not found.")

        conn.close()
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error managing campaigns: {e}")

def search_alumni_directory():
    """Advanced alumni directory search"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to search the alumni directory.")
        return
    
    if not auth.check_permission('access_alumni_directory'):
        print("You don't have permission to access the alumni directory.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAlumni Directory Search")
    print("=======================")
    print("1. Search by name")
    print("2. Search by graduation year")
    print("3. Search by industry")
    print("4. Search by location")
    print("5. Search by skills")
    print("6. Advanced search")
    
    choice = input("Select search type: ")
    
    if choice == '1':
        # Search by name
        name = input("Enter name (partial match allowed): ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (a.first_name LIKE ? OR a.last_name LIKE ?)
            ORDER BY a.last_name, a.first_name
        ''', (f'%{name}%', f'%{name}%'))
        
    elif choice == '2':
        # Search by graduation year
        try:
            year = int(input("Enter graduation year: "))
            cursor.execute('''
                SELECT a.*, ads.* FROM alumni a
                LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
                WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
                AND a.graduation_year = ?
                ORDER BY a.last_name, a.first_name
            ''', (year,))
        except ValueError:
            print("Invalid year format.")
            conn.close()
            return
            
    elif choice == '3':
        # Search by industry
        industry = input("Enter industry: ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND a.industry LIKE ?
            ORDER BY a.last_name, a.first_name
        ''', (f'%{industry}%',))
        
    elif choice == '4':
        # Search by location
        location = input("Enter city or country: ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (a.city LIKE ? OR a.country LIKE ?)
            ORDER BY a.last_name, a.first_name
        ''', (f'%{location}%', f'%{location}%'))
        
    elif choice == '5':
        # Search by skills
        skills = input("Enter skills (comma-separated): ")
        skill_list = [skill.strip() for skill in skills.split(',')]
        skill_conditions = " OR ".join(["a.skills LIKE ?" for _ in skill_list])
        skill_params = [f'%{skill}%' for skill in skill_list]
        
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (''' + skill_conditions + ''')
            ORDER BY a.last_name, a.first_name
        ''', skill_params)
        
    elif choice == '6':
        # Advanced search
        print("\nAdvanced Search - Enter criteria (leave blank to skip):")
        name = input("Name: ")
        year_from = input("Graduation year from: ")
        year_to = input("Graduation year to: ")
        industry = input("Industry: ")
        location = input("Location: ")
        company = input("Company: ")
        
        # Build dynamic query
        conditions = ["(ads.searchable = 1 OR ads.searchable IS NULL)"]
        params = []
        
        if name:
            conditions.append("(a.first_name LIKE ? OR a.last_name LIKE ?)")
            params.extend([f'%{name}%', f'%{name}%'])
        
        if year_from:
            try:
                year_from = int(year_from)
                conditions.append("a.graduation_year >= ?")
                params.append(year_from)
            except ValueError:
                pass
        
        if year_to:
            try:
                year_to = int(year_to)
                conditions.append("a.graduation_year <= ?")
                params.append(year_to)
            except ValueError:
                pass
        
        if industry:
            conditions.append("a.industry LIKE ?")
            params.append(f'%{industry}%')
        
        if location:
            conditions.append("(a.city LIKE ? OR a.country LIKE ?)")
            params.extend([f'%{location}%', f'%{location}%'])
        
        if company:
            conditions.append("a.current_employer LIKE ?")
            params.append(f'%{company}%')
        
        query = f'''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE {" AND ".join(conditions)}
            ORDER BY a.last_name, a.first_name
        '''
        
        cursor.execute(query, params)
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    results = cursor.fetchall()
    
    if not results:
        print("No alumni found matching your search criteria.")
    else:
        print(f"\nFound {len(results)} alumni:")
        print("-" * 80)
        
        for i, alumni in enumerate(results, 1):
            settings = alumni[23:] if len(alumni) > 23 else [1, 1, 1, 1, 1, 0]  # Default settings
            
            print(f"{i}. {alumni[4]} {alumni[6]} ({alumni[0]})")
            print(f"   Graduated: {alumni[9]} - {alumni[10]}")
            
            if len(settings) > 2 and settings[2]:  # show_employment
                print(f"   Current: {alumni[12]} at {alumni[11]}")
                print(f"   Industry: {alumni[13]}")
            
            if len(settings) > 1 and settings[1]:  # show_contact_info
                print(f"   Location: {alumni[15]}, {alumni[16]}")
                print(f"   Email: {alumni[2]}")
            
            if len(settings) > 5 and settings[5]:  # mentor_available
                print("   ✓ Available as Mentor")
            
            if len(settings) > 4 and settings[4]:  # networking_available
                print("   ✓ Available for Networking")
            
            print("-" * 80)
        
        # Option to connect with someone
        if auth.check_permission('access_alumni_directory'):
            connect_choice = input("\nWould you like to send a connection request to someone? (y/n): ").lower()
            if connect_choice == 'y':
                try:
                    selection = int(input(f"Enter number (1-{len(results)}): "))
                    if 1 <= selection <= len(results):
                        selected_alumni = results[selection - 1]
                        send_connection_request(selected_alumni[0])  # alumni_id
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Invalid input.")
    
    conn.close()

def send_connection_request(recipient_id):
    """Send a networking connection request"""
    global auth
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    requester_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        requester_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    if requester_id == recipient_id:
        print("You cannot send a connection request to yourself.")
        conn.close()
        return
    
    # Check if connection already exists
    cursor.execute('''
        SELECT * FROM networking_connections 
        WHERE (requester_id = ? AND recipient_id = ?) OR (requester_id = ? AND recipient_id = ?)
    ''', (requester_id, recipient_id, recipient_id, requester_id))
    
    existing_connection = cursor.fetchone()
    if existing_connection:
        print("A connection request already exists between you and this alumni.")
        conn.close()
        return
    
    # Get recipient info
    cursor.execute('SELECT first_name, last_name, email_address FROM alumni WHERE alumni_id = ?', (recipient_id,))
    recipient_info = cursor.fetchone()
    if not recipient_info:
        print("Recipient not found.")
        conn.close()
        return

    recipient_name = f"{recipient_info[0]} {recipient_info[1]}"
    recipient_email = recipient_info[2]

    # Get requester info for email notification
    cursor.execute('''
        SELECT first_name, last_name, graduation_year, current_employer, job_title
        FROM alumni WHERE alumni_id = ?
    ''', (requester_id,))
    requester_info = cursor.fetchone()
    requester_name = f"{requester_info[0]} {requester_info[1]}" if requester_info else "A fellow alumni"
    requester_grad_year = requester_info[2] if requester_info else "N/A"
    requester_employer = requester_info[3] if requester_info and requester_info[3] else "Not specified"
    requester_job_title = requester_info[4] if requester_info and requester_info[4] else "Not specified"

    message = input(f"Enter a message for {recipient_name} (optional): ")

    # Insert connection request
    cursor.execute('''
        INSERT INTO networking_connections (requester_id, recipient_id, connection_date, status, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (requester_id, recipient_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending', message))

    conn.commit()
    conn.close()

    print(f"Connection request sent to {recipient_name}!")

    # Send email notification to recipient
    if recipient_email:
        try:
            template = load_template('alumni/alumni_connection_request')
            if template:
                # Build personal message section
                personal_message_section = ""
                if message and message.strip():
                    personal_message_section = f"Personal Message:\n\"{message}\"\n"

                template_vars = {
                    'recipient_name': recipient_name,
                    'requester_name': requester_name,
                    'requester_grad_year': str(requester_grad_year),
                    'requester_employer': requester_employer,
                    'requester_job_title': requester_job_title,
                    'personal_message_section': personal_message_section
                }

                subject, body = render_template('alumni_connection_request', template_vars)
                if subject and body:
                    send_email(recipient_email, subject, body)
                    print("Email notification sent to recipient.")
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")

def view_connection_requests():
    """View and manage connection requests"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view connection requests.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    print("\nConnection Requests")
    print("===================")
    
    # Get pending requests received
    cursor.execute('''
        SELECT nc.*, a.first_name, a.last_name, a.current_employer, a.job_title
        FROM networking_connections nc
        JOIN alumni a ON nc.requester_id = a.alumni_id
        WHERE nc.recipient_id = ? AND nc.status = 'pending'
        ORDER BY nc.connection_date DESC
    ''', (alumni_id,))
    
    pending_requests = cursor.fetchall()
    
    if pending_requests:
        print("\nPending Requests Received:")
        for i, request in enumerate(pending_requests, 1):
            requester_name = f"{request[6]} {request[7]}"
            job_info = f"{request[9]} at {request[8]}" if request[8] else "No employment info"
            print(f"{i}. From: {requester_name}")
            print(f"   {job_info}")
            print(f"   Date: {request[3]}")
            if request[5]:  # message
                print(f"   Message: {request[5]}")
            print()
        
        # Handle requests
        handle_choice = input("Would you like to respond to any requests? (y/n): ").lower()
        if handle_choice == 'y':
            try:
                selection = int(input(f"Enter request number (1-{len(pending_requests)}): "))
                if 1 <= selection <= len(pending_requests):
                    selected_request = pending_requests[selection - 1]
                    action = input("Accept (a) or Decline (d) this request: ").lower()
                    
                    if action == 'a':
                        cursor.execute('''
                            UPDATE networking_connections 
                            SET status = 'accepted' 
                            WHERE connection_id = ?
                        ''', (selected_request[0],))
                        print("Connection request accepted!")
                        
                        # Award engagement points
                        award_engagement_points(alumni_id, 'connection_made', 10)
                        award_engagement_points(selected_request[1], 'connection_made', 10)
                        
                    elif action == 'd':
                        cursor.execute('''
                            UPDATE networking_connections 
                            SET status = 'declined' 
                            WHERE connection_id = ?
                        ''', (selected_request[0],))
                        print("Connection request declined.")
                    else:
                        print("Invalid choice.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    else:
        print("No pending connection requests.")
    
    # Show sent requests
    cursor.execute('''
        SELECT nc.*, a.first_name, a.last_name
        FROM networking_connections nc
        JOIN alumni a ON nc.recipient_id = a.alumni_id
        WHERE nc.requester_id = ?
        ORDER BY nc.connection_date DESC
    ''', (alumni_id,))
    
    sent_requests = cursor.fetchall()
    
    if sent_requests:
        print("\nRequests You've Sent:")
        for request in sent_requests:
            recipient_name = f"{request[6]} {request[7]}"
            status_color = {"pending": "⏳", "accepted": "✅", "declined": "❌"}
            print(f"{status_color.get(request[4], '?')} To: {recipient_name} - Status: {request[4]} ({request[3]})")
    
    conn.commit()
    conn.close()

# COMMUNICATION SYSTEM FEATURES

def create_newsletter():
    """Create and send newsletters"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create newsletters.")
        return
    
    if not auth.check_permission('send_newsletters'):
        print("You don't have permission to create newsletters.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nCreate Alumni Newsletter")
    print("========================")
    
    # Get available templates
    cursor.execute('SELECT template_id, template_name FROM email_templates WHERE template_type = "newsletter"')
    templates = cursor.fetchall()
    
    if templates:
        print("\nAvailable Templates:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template[1]}")
        print(f"{len(templates) + 1}. Create custom newsletter")
        
        try:
            template_choice = int(input("Select template: "))
            if 1 <= template_choice <= len(templates):
                template_id = templates[template_choice - 1][0]
                cursor.execute('SELECT template_content FROM email_templates WHERE template_id = ?', (template_id,))
                base_content = cursor.fetchone()[0]
            else:
                template_id = None
                base_content = ""
        except ValueError:
            template_id = None
            base_content = ""
    else:
        template_id = None
        base_content = ""
    
    title = input("Newsletter Title: ")
    print("\nEnter newsletter content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)
    
    content = base_content + "\n\n" + "\n".join(content_lines)
    
    # Target audience selection
    print("\nTarget Audience:")
    print("1. All Alumni")
    print("2. By Graduation Year")
    print("3. By Industry")
    print("4. By Location")
    print("5. Donors Only")
    print("6. Mentors Only")
    
    audience_choice = input("Select target audience: ")
    target_audience = "all"
    audience_filter = None
    filter_params = []

    if audience_choice == '2':
        year = input("Enter graduation year: ")
        target_audience = f"graduation_year:{year}"
        audience_filter = "graduation_year = ?"
        filter_params = [year]
    elif audience_choice == '3':
        industry = input("Enter industry: ")
        target_audience = f"industry:{industry}"
        audience_filter = "industry LIKE ?"
        filter_params = [f"%{industry}%"]
    elif audience_choice == '4':
        location = input("Enter city or country: ")
        target_audience = f"location:{location}"
        audience_filter = "city LIKE ? OR country LIKE ?"
        filter_params = [f"%{location}%", f"%{location}%"]
    elif audience_choice == '5':
        target_audience = "donors"
        audience_filter = "is_donor = 1"
        filter_params = []
    elif audience_choice == '6':
        target_audience = "mentors"
        audience_filter = "is_mentor = 1"
        filter_params = []
    
    # Schedule or send immediately
    send_choice = input("Send immediately (i) or schedule for later (s): ").lower()
    
    if send_choice == 's':
        send_date = input("Enter send date (YYYY-MM-DD HH:MM): ")
        try:
            # Validate date format
            datetime.strptime(send_date, "%Y-%m-%d %H:%M")
            status = 'scheduled'
        except ValueError:
            print("Invalid date format. Setting as draft.")
            send_date = None
            status = 'draft'
    else:
        send_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = 'sending'
    
    # Save newsletter
    cursor.execute('''
        INSERT INTO newsletters (title, content, template_id, target_audience, send_date, created_date, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, content, template_id, target_audience, send_date, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), auth.current_user['username'], status))
    
    newsletter_id = cursor.lastrowid
    
    if status == 'sending':
        # Send immediately
        send_newsletter_now(newsletter_id, audience_filter, cursor, filter_params)
        cursor.execute('UPDATE newsletters SET status = "sent" WHERE newsletter_id = ?', (newsletter_id,))
    
    conn.commit()
    conn.close()
    
    print(f"Newsletter created successfully! ID: {newsletter_id}")
    if status == 'sending':
        print("Newsletter has been sent to recipients.")
    elif status == 'scheduled':
        print(f"Newsletter scheduled for: {send_date}")

def send_newsletter_now(newsletter_id, audience_filter, cursor, filter_params=None):
    """Send newsletter to target audience"""
    # Get newsletter content
    cursor.execute('SELECT title, content FROM newsletters WHERE newsletter_id = ?', (newsletter_id,))
    newsletter_info = cursor.fetchone()
    if not newsletter_info:
        return

    title, content = newsletter_info

    # Get recipient list
    if audience_filter:
        query = f"SELECT email_address, first_name, last_name FROM alumni WHERE {audience_filter}"
        cursor.execute(query, filter_params or [])
    else:
        cursor.execute('SELECT email_address, first_name, last_name FROM alumni')

    recipients = cursor.fetchall()

    print(f"Sending newsletter to {len(recipients)} recipients...")

    # Load email template
    template = load_template('alumni/alumni_newsletter')

    sent_count = 0
    failed_count = 0
    for recipient in recipients:
        email, first_name, last_name = recipient[0], recipient[1], recipient[2] if len(recipient) > 2 else ""
        recipient_name = f"{first_name} {last_name}".strip() if last_name else first_name

        if not email:
            continue

        try:
            if template:
                template_vars = {
                    'recipient_name': recipient_name,
                    'newsletter_title': title,
                    'newsletter_content': content
                }
                subject, body = render_template('alumni_newsletter', template_vars)
                if subject and body:
                    send_email(email, subject, body)
                    sent_count += 1
                else:
                    # Fallback to direct send if template rendering fails
                    send_email(email, title, content)
                    sent_count += 1
            else:
                # No template available, send directly
                send_email(email, title, content)
                sent_count += 1

            print(f"Sent to {email}")
        except Exception as e:
            print(f"Failed to send to {email}: {e}")
            failed_count += 1

    print(f"Newsletter sent successfully to {sent_count} recipients!")
    if failed_count > 0:
        print(f"Failed to send to {failed_count} recipients.")

def manage_alumni_forum():
    """Manage alumni forum discussions"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the forum.")
        return
    
    if not auth.check_permission('access_alumni_directory'):
        print("You don't have permission to access the forum.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    while True:
        print("\nAlumni Forum")
        print("============")
        print("1. View Recent Posts")
        print("2. Create New Post")
        print("3. Search Posts")
        print("4. My Posts")
        if auth.check_permission('moderate_forum'):
            print("5. Moderate Posts")
        print("0. Return to Main Menu")
        
        choice = input("Enter your choice: ")
        
        if choice == '1':
            view_forum_posts(cursor)
        elif choice == '2':
            create_forum_post(cursor)
        elif choice == '3':
            search_forum_posts(cursor)
        elif choice == '4':
            view_my_forum_posts(cursor)
        elif choice == '5' and auth.check_permission('moderate_forum'):
            moderate_forum_posts(cursor)
        elif choice == '0':
            break
        else:
            print("Invalid choice.")
    
    conn.close()

def view_forum_posts(cursor):
    """View recent forum posts"""
    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM alumni_forum p
        JOIN alumni a ON p.author_id = a.alumni_id
        ORDER BY p.post_date DESC
        LIMIT 20
    ''')
    
    posts = cursor.fetchall()
    
    if not posts:
        print("No forum posts found.")
        return
    
    print("\nRecent Forum Posts:")
    print("-" * 80)
    
    for post in posts:
        author_name = f"{post[10]} {post[11]}"
        print(f"Title: {post[2]}")
        print(f"Author: {author_name}")
        print(f"Category: {post[4]}")
        print(f"Date: {post[5]}")
        print(f"Replies: {post[7]} | Views: {post[8]}")
        if post[9]:  # is_pinned
            print("📌 PINNED")
        print(f"Content: {post[3][:100]}...")
        print("-" * 80)
    
    # Option to view a specific post
    view_choice = input("Enter post number to view details (or press Enter to continue): ")
    if view_choice.isdigit():
        post_index = int(view_choice) - 1
        if 0 <= post_index < len(posts):
            view_forum_post_details(posts[post_index], cursor)

def create_forum_post(cursor):
    """Create a new forum post"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    print("\nCreate New Forum Post")
    print("=====================")
    
    categories = [
        "General Discussion", "Career Advice", "Networking", "Industry News",
        "Class Updates", "Events", "Mentorship", "Job Opportunities",
        "Alumni Spotlight", "Ask for Help"
    ]
    
    print("\nAvailable Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "General Discussion"
    except ValueError:
        category = "General Discussion"
    
    title = input("Post Title: ")
    print("\nEnter post content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)
    
    content = "\n".join(content_lines)
    
    if not title or not content:
        print("Title and content are required.")
        return
    
    # Insert the post
    cursor.execute('''
        INSERT INTO alumni_forum (author_id, title, content, category, post_date, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (alumni_id, title, content, category, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    post_id = cursor.lastrowid
    
    # Award engagement points
    award_engagement_points(alumni_id, 'forum_post', 15)
    
    print(f"Forum post created successfully! Post ID: {post_id}")

def view_forum_post_details(post, cursor):
    """View detailed forum post with replies"""
    print(f"\n{'='*60}")
    print(f"Title: {post[2]}")
    print(f"Category: {post[4]}")
    print(f"Date: {post[5]}")
    print(f"{'='*60}")
    print(post[3])
    print(f"{'='*60}")
    
    # Get replies
    cursor.execute('''
        SELECT r.*, a.first_name, a.last_name
        FROM forum_replies r
        JOIN alumni a ON r.author_id = a.alumni_id
        WHERE r.post_id = ?
        ORDER BY r.reply_date
    ''', (post[0],))
    
    replies = cursor.fetchall()
    
    if replies:
        print(f"\nReplies ({len(replies)}):")
        for reply in replies:
            author_name = f"{reply[6]} {reply[7]}"
            print(f"\n{author_name} - {reply[4]}:")
            print(reply[3])
    
    # Update view count
    cursor.execute('''
        UPDATE alumni_forum 
        SET view_count = view_count + 1 
        WHERE post_id = ?
    ''', (post[0],))
    
    # Option to reply
    reply_choice = input("\nWould you like to reply to this post? (y/n): ").lower()
    if reply_choice == 'y':
        add_forum_reply(post[0], cursor)

def add_forum_reply(post_id, cursor):
    """Add a reply to a forum post"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    print("\nAdd Reply")
    print("=========")
    print("Enter your reply (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)
    
    content = "\n".join(content_lines)
    
    if not content:
        print("Reply content is required.")
        return
    
    # Insert the reply
    cursor.execute('''
        INSERT INTO forum_replies (post_id, author_id, content, reply_date)
        VALUES (?, ?, ?, ?)
    ''', (post_id, alumni_id, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # Update reply count
    cursor.execute('''
        UPDATE alumni_forum 
        SET reply_count = reply_count + 1, last_updated = ?
        WHERE post_id = ?
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), post_id))
    
    # Award engagement points
    award_engagement_points(alumni_id, 'forum_reply', 5)
    
    print("Reply added successfully!")

# JOB BOARD & CAREER SERVICES

def post_job_opportunity():
    """Post a job opportunity"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to post jobs.")
        return
    
    if not auth.check_permission('post_jobs'):
        print("You don't have permission to post jobs.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    print("\nPost Job Opportunity")
    print("====================")
    
    company_name = input("Company Name: ")
    job_title = input("Job Title: ")
    
    # Job categories
    categories = [
        "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
        "Retail", "Government", "Non-profit", "Entertainment", "Consulting",
        "Marketing", "Sales", "Engineering", "Research", "Other"
    ]
    
    print("\nJob Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "Other"
    except ValueError:
        category = "Other"
    
    location = input("Location (city, state/country): ")
    
    # Job types
    job_types = ["Full-time", "Part-time", "Contract", "Internship", "Remote"]
    print("\nJob Types:")
    for i, jtype in enumerate(job_types, 1):
        print(f"{i}. {jtype}")
    
    try:
        type_choice = int(input("Select job type: "))
        if 1 <= type_choice <= len(job_types):
            job_type = job_types[type_choice - 1]
        else:
            job_type = "Full-time"
    except ValueError:
        job_type = "Full-time"
    
    # Experience levels
    exp_levels = ["Entry Level", "Mid Level", "Senior Level", "Executive", "Any"]
    print("\nExperience Levels:")
    for i, level in enumerate(exp_levels, 1):
        print(f"{i}. {level}")
    
    try:
        exp_choice = int(input("Select experience level: "))
        if 1 <= exp_choice <= len(exp_levels):
            experience_level = exp_levels[exp_choice - 1]
        else:
            experience_level = "Any"
    except ValueError:
        experience_level = "Any"
    
    salary_range = input("Salary Range (optional): ")
    
    print("\nJob Description (press Enter twice to finish):")
    desc_lines = []
    while True:
        line = input()
        if line == "" and (not desc_lines or desc_lines[-1] == ""):
            break
        desc_lines.append(line)
    job_description = "\n".join(desc_lines)
    
    print("\nRequirements (press Enter twice to finish):")
    req_lines = []
    while True:
        line = input()
        if line == "" and (not req_lines or req_lines[-1] == ""):
            break
        req_lines.append(line)
    requirements = "\n".join(req_lines)
    
    # Application method
    app_methods = ["Email", "Company Website", "LinkedIn", "Other"]
    print("\nApplication Methods:")
    for i, method in enumerate(app_methods, 1):
        print(f"{i}. {method}")
    
    try:
        app_choice = int(input("Select application method: "))
        if 1 <= app_choice <= len(app_methods):
            application_method = app_methods[app_choice - 1]
        else:
            application_method = "Email"
    except ValueError:
        application_method = "Email"
    
    contact_email = input("Contact Email: ")
    
    # Set expiry date (default 30 days)
    expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    custom_expiry = input(f"Expiry Date (default {expiry_date}, format YYYY-MM-DD): ")
    if custom_expiry:
        try:
            datetime.strptime(custom_expiry, '%Y-%m-%d')
            expiry_date = custom_expiry
        except ValueError:
            print("Invalid date format, using default.")
    
    # Insert job posting
    cursor.execute('''
        INSERT INTO job_postings 
        (posted_by, company_name, job_title, job_description, location, job_type, 
         salary_range, requirements, application_method, contact_email, post_date, 
         expiry_date, category, experience_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, company_name, job_title, job_description, location, job_type,
          salary_range, requirements, application_method, contact_email,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), expiry_date, category, experience_level))
    
    job_id = cursor.lastrowid
    
    # Award engagement points
    award_engagement_points(alumni_id, 'job_posted', 25)
    
    conn.commit()
    conn.close()
    
    print(f"Job opportunity posted successfully! Job ID: {job_id}")
    print("The job will be visible to all alumni in the job board.")

def view_job_board():
    """View available job opportunities"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view the job board.")
        return
    
    if not auth.check_permission('view_job_board'):
        print("You don't have permission to view the job board.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAlumni Job Board")
    print("================")
    print("1. View All Active Jobs")
    print("2. Search Jobs by Category")
    print("3. Search Jobs by Location")
    print("4. Search Jobs by Experience Level")
    print("5. My Posted Jobs")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # View all active jobs
        cursor.execute('''
            SELECT j.*, a.first_name, a.last_name
            FROM job_postings j
            JOIN alumni a ON j.posted_by = a.alumni_id
            WHERE j.is_active = 1 AND j.expiry_date >= date('now')
            ORDER BY j.post_date DESC
        ''')
        
    elif choice == '2':
        # Search by category
        categories = [
            "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
            "Retail", "Government", "Non-profit", "Entertainment", "Consulting",
            "Marketing", "Sales", "Engineering", "Research", "Other"
        ]
        
        print("\nJob Categories:")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        try:
            cat_choice = int(input("Select category: "))
            if 1 <= cat_choice <= len(categories):
                selected_category = categories[cat_choice - 1]
                cursor.execute('''
                    SELECT j.*, a.first_name, a.last_name
                    FROM job_postings j
                    JOIN alumni a ON j.posted_by = a.alumni_id
                    WHERE j.is_active = 1 AND j.expiry_date >= date('now') AND j.category = ?
                    ORDER BY j.post_date DESC
                ''', (selected_category,))
            else:
                print("Invalid category.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
            
    elif choice == '3':
        # Search by location
        location = input("Enter location (city, state, or country): ")
        cursor.execute('''
            SELECT j.*, a.first_name, a.last_name
            FROM job_postings j
            JOIN alumni a ON j.posted_by = a.alumni_id
            WHERE j.is_active = 1 AND j.expiry_date >= date('now') AND j.location LIKE ?
            ORDER BY j.post_date DESC
        ''', (f'%{location}%',))
        
    elif choice == '4':
        # Search by experience level
        exp_levels = ["Entry Level", "Mid Level", "Senior Level", "Executive", "Any"]
        print("\nExperience Levels:")
        for i, level in enumerate(exp_levels, 1):
            print(f"{i}. {level}")
        
        try:
            exp_choice = int(input("Select experience level: "))
            if 1 <= exp_choice <= len(exp_levels):
                selected_level = exp_levels[exp_choice - 1]
                cursor.execute('''
                    SELECT j.*, a.first_name, a.last_name
                    FROM job_postings j
                    JOIN alumni a ON j.posted_by = a.alumni_id
                    WHERE j.is_active = 1 AND j.expiry_date >= date('now') 
                    AND (j.experience_level = ? OR j.experience_level = 'Any')
                    ORDER BY j.post_date DESC
                ''', (selected_level,))
            else:
                print("Invalid choice.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
            
    elif choice == '5':
        # My posted jobs
        cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        if result and result[0].startswith('A'):
            alumni_id = result[0]
            cursor.execute('''
                SELECT j.*, a.first_name, a.last_name
                FROM job_postings j
                JOIN alumni a ON j.posted_by = a.alumni_id
                WHERE j.posted_by = ?
                ORDER BY j.post_date DESC
            ''', (alumni_id,))
        else:
            print("Alumni profile not found.")
            conn.close()
            return
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    jobs = cursor.fetchall()
    
    if not jobs:
        print("No job opportunities found.")
    else:
        print(f"\nFound {len(jobs)} job opportunities:")
        print("-" * 80)
        
        for i, job in enumerate(jobs, 1):
            poster_name = f"{job[16]} {job[17]}"
            print(f"{i}. {job[3]} at {job[2]}")  # job_title at company_name
            print(f"   Posted by: {poster_name}")
            print(f"   Location: {job[5]}")
            print(f"   Type: {job[6]} | Level: {job[14]} | Category: {job[13]}")
            if job[7]:  # salary_range
                print(f"   Salary: {job[7]}")
            print(f"   Posted: {job[11]} | Expires: {job[12]}")
            print(f"   Description: {job[4][:100]}...")
            print("-" * 80)
        
        # Option to view job details
        view_choice = input(f"\nEnter job number to view details (1-{len(jobs)}) or press Enter to continue: ")
        if view_choice.isdigit():
            job_index = int(view_choice) - 1
            if 0 <= job_index < len(jobs):
                view_job_details(jobs[job_index], cursor)
    
    conn.close()

def view_job_details(job, cursor):
    """View detailed job information"""
    print(f"\n{'='*60}")
    print(f"Job Title: {job[3]}")
    print(f"Company: {job[2]}")
    print(f"Location: {job[5]}")
    print(f"Job Type: {job[6]}")
    print(f"Experience Level: {job[14]}")
    print(f"Category: {job[13]}")
    if job[7]:
        print(f"Salary Range: {job[7]}")
    print(f"Contact: {job[10]}")
    print(f"Application Method: {job[9]}")
    print(f"Posted: {job[11]}")
    print(f"Expires: {job[12]}")
    print(f"{'='*60}")
    print("\nJob Description:")
    print(job[4])
    print(f"{'='*60}")
    print("\nRequirements:")
    print(job[8])
    print(f"{'='*60}")
    
    # Option to apply (record interest)
    apply_choice = input("\nWould you like to record your interest in this position? (y/n): ").lower()
    if apply_choice == 'y':
        record_job_interest(job[0], cursor)

def record_job_interest(job_id, cursor):
    """Record alumni interest in a job"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    # Check if already applied
    cursor.execute('SELECT * FROM job_applications WHERE job_id = ? AND applicant_id = ?', (job_id, alumni_id))
    if cursor.fetchone():
        print("You have already expressed interest in this position.")
        return
    
    cover_letter = input("Enter a brief cover letter/message (optional): ")
    
    # Record the application
    cursor.execute('''
        INSERT INTO job_applications (job_id, applicant_id, application_date, status, cover_letter)
        VALUES (?, ?, ?, ?, ?)
    ''', (job_id, alumni_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'submitted', cover_letter))
    
    # Award engagement points
    award_engagement_points(alumni_id, 'job_application', 10)
    
    print("Your interest has been recorded! The job poster will be notified.")

def schedule_career_counseling():
    """Schedule career counseling session"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to schedule career counseling.")
        return
    
    if not auth.check_permission('schedule_career_counseling'):
        print("You don't have permission to schedule career counseling.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get available counselors
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, job_title, current_employer
        FROM alumni
        WHERE is_mentor = 1
        ORDER BY last_name, first_name
    ''')
    
    counselors = cursor.fetchall()
    
    if not counselors:
        print("No career counselors are currently available.")
        conn.close()
        return
    
    print("\nAvailable Career Counselors:")
    print("============================")
    
    for i, counselor in enumerate(counselors, 1):
        print(f"{i}. {counselor[1]} {counselor[2]}")
        if counselor[3] and counselor[4]:
            print(f"   {counselor[3]} at {counselor[4]}")
        print()
    
    try:
        counselor_choice = int(input(f"Select counselor (1-{len(counselors)}): "))
        if 1 <= counselor_choice <= len(counselors):
            selected_counselor = counselors[counselor_choice - 1]
        else:
            print("Invalid selection.")
            conn.close()
            return
    except ValueError:
        print("Invalid input.")
        conn.close()
        return
    
    # Get current user's alumni ID
    client_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        client_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    # Session details
    session_types = ["Career Planning", "Resume Review", "Interview Preparation", "Industry Insights", "Networking Advice"]
    print("\nSession Types:")
    for i, stype in enumerate(session_types, 1):
        print(f"{i}. {stype}")
    
    try:
        type_choice = int(input("Select session type: "))
        if 1 <= type_choice <= len(session_types):
            session_type = session_types[type_choice - 1]
        else:
            session_type = "Career Planning"
    except ValueError:
        session_type = "Career Planning"
    
    # Schedule date/time
    session_date = input("Preferred date and time (YYYY-MM-DD HH:MM): ")
    try:
        # Validate date format
        datetime.strptime(session_date, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Invalid date format.")
        conn.close()
        return
    
    duration = input("Expected duration in minutes (default 60): ")
    try:
        duration = int(duration) if duration else 60
    except ValueError:
        duration = 60
    
    notes = input("Additional notes or specific topics to discuss: ")
    
    # Insert counseling session
    cursor.execute('''
        INSERT INTO career_counseling 
        (counselor_id, client_id, session_date, session_type, duration, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (selected_counselor[0], client_id, session_date, session_type, duration, notes, 'scheduled'))
    
    session_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    counselor_name = f"{selected_counselor[1]} {selected_counselor[2]}"
    print(f"\nCareer counseling session scheduled successfully!")
    print(f"Session ID: {session_id}")
    print(f"Counselor: {counselor_name}")
    print(f"Date/Time: {session_date}")
    print(f"Type: {session_type}")
    print("The counselor will be notified and will contact you to confirm the session.")

# ENHANCED EVENT MANAGEMENT

def create_enhanced_event():
    """Create an enhanced alumni event with payment and advanced features"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create events.")
        return
    
    if not auth.check_permission('manage_events_advanced'):
        print("You don't have permission to create advanced events.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nCreate Enhanced Alumni Event")
    print("============================")
    
    # Basic event details
    event_name = input("Event Name: ")
    while not event_name:
        print("Error: Event name is required.")
        event_name = input("Event Name: ")
    
    # Event date and time
    while True:
        event_date_str = input("Event Date and Time (YYYY-MM-DD HH:MM:SS): ")
        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d %H:%M:%S")
            if event_date < datetime.now():
                print("Error: Event date cannot be in the past.")
                continue
            event_date_str = event_date.strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD HH:MM:SS.")
    
    event_location = input("Event Location: ")
    while not event_location:
        print("Error: Event location is required.")
        event_location = input("Event Location: ")
    
    event_description = input("Event Description: ")
    
    # Event type
    event_types = ["in-person", "virtual", "hybrid"]
    print("\nEvent Types:")
    for i, etype in enumerate(event_types, 1):
        print(f"{i}. {etype}")
    
    try:
        type_choice = int(input("Select event type: "))
        if 1 <= type_choice <= len(event_types):
            event_type = event_types[type_choice - 1]
        else:
            event_type = "in-person"
    except ValueError:
        event_type = "in-person"
    
    # Virtual link for virtual/hybrid events
    virtual_link = ""
    if event_type in ["virtual", "hybrid"]:
        virtual_link = input("Virtual meeting link (Zoom, Teams, etc.): ")
    
    # Registration settings
    registration_required = input("Registration Required? (y/n): ").lower() == 'y'
    
    max_attendees = 0
    registration_deadline = None
    waitlist_enabled = False
    
    if registration_required:
        while True:
            try:
                max_attendees_str = input("Maximum Number of Attendees (0 for unlimited): ")
                max_attendees = int(max_attendees_str)
                if max_attendees < 0:
                    print("Error: Maximum attendees cannot be negative.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid number.")
        
        # Registration deadline
        deadline_input = input("Registration deadline (YYYY-MM-DD HH:MM, press Enter for event date): ")
        if deadline_input:
            try:
                registration_deadline = datetime.strptime(deadline_input, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                print("Invalid deadline format, using event date.")
                registration_deadline = event_date_str
        else:
            registration_deadline = event_date_str
        
        if max_attendees > 0:
            waitlist_enabled = input("Enable waitlist for overbooked events? (y/n): ").lower() == 'y'
    
    # Payment settings
    payment_required = input("Is payment required for this event? (y/n): ").lower() == 'y'
    event_fee = 0.0
    
    if payment_required:
        while True:
            try:
                event_fee = float(input("Event fee ($): "))
                if event_fee < 0:
                    print("Error: Fee cannot be negative.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid amount.")
    
    # Insert the event
    cursor.execute('''
        INSERT INTO alumni_events 
        (event_name, event_date, event_location, event_description, registration_required, 
         max_attendees, event_fee, payment_required, event_type, virtual_link, 
         created_by, created_date, registration_deadline, waitlist_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (event_name, event_date_str, event_location, event_description, registration_required,
          max_attendees, event_fee, payment_required, event_type, virtual_link,
          auth.current_user['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          registration_deadline, waitlist_enabled))
    
    event_id = cursor.lastrowid
    
    # Generate QR code for event check-in
    qr_code_path = generate_event_qr_code(event_id)
    if qr_code_path:
        cursor.execute('UPDATE alumni_events SET qr_code_path = ? WHERE event_id = ?', (qr_code_path, event_id))
    
    conn.commit()

    print(f"\nEnhanced event created successfully with ID: {event_id}")
    print(f"Event Type: {event_type}")
    if payment_required:
        print(f"Event Fee: ${event_fee:.2f}")
    if virtual_link:
        print(f"Virtual Link: {virtual_link}")

    # Automatically send event invitations to all alumni
    try:
        # Get all alumni
        cursor.execute('SELECT alumni_id, email, first_name, last_name FROM alumni_profiles')
        alumni_list = cursor.fetchall()

        if alumni_list:
            print(f"\n✉️  Sending event invitations to {len(alumni_list)} alumni...")
            sent_count = 0

            for alumni_id, email, first_name, last_name in alumni_list:
                try:
                    send_event_invitation(
                        alumni_id=alumni_id,
                        event_id=event_id,
                        email_address=email,
                        event_name=event_name,
                        event_date=event_date_str,
                        event_location=event_location
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"   ⚠️  Could not send invitation to {email}: {e}")

            print(f"✅ Event invitations sent successfully to {sent_count} alumni!")
        else:
            print("⚠️  No alumni found to notify.")
    except Exception as e:
        print(f"⚠️  Could not send event invitations: {e}")

    conn.close()

def generate_event_qr_code(event_id):
    """Generate QR code for event check-in"""
    try:
        import qrcode
        
        # Create QR code data
        qr_data = f"EVENT_CHECKIN:{event_id}"
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_path = f"event_qr_{event_id}.png"
        img.save(qr_path)
        
        return qr_path
    except ImportError:
        print("QR code generation requires 'qrcode' library.")
        return None
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def send_enhanced_event_notifications(event_id, cursor):
    """Send enhanced event notifications"""
    # Get event details
    cursor.execute('SELECT * FROM alumni_events WHERE event_id = ?', (event_id,))
    event = cursor.fetchone()
    if not event:
        return
    
    # Get all alumni emails
    cursor.execute('SELECT alumni_id, email_address, first_name FROM alumni')
    alumni_list = cursor.fetchall()
    
    if alumni_list:
        print(f"Sending enhanced event invitations to {len(alumni_list)} alumni...")
        
        for alumni in alumni_list:
            alumni_id, email, first_name = alumni
            # Enhanced notification with event type, fees, etc.
            send_enhanced_event_invitation(
                alumni_id, email, first_name, event_id, 
                event[1], event[2], event[3], event[8], 
                event[6], event[7], event[9]
            )
        
        print("Enhanced event invitations sent successfully!")
    else:
        print("No alumni found to notify.")

def send_enhanced_event_invitation(alumni_id, email, first_name, event_id, event_name,
                                 event_date, event_location, event_type, event_fee,
                                 payment_required, virtual_link):
    """Send enhanced event invitation with all details"""
    if not email:
        print(f"No email address for alumni {alumni_id}")
        return

    try:
        # Build payment section
        payment_section = ""
        if payment_required and event_fee:
            payment_section = f"Registration Fee: ${event_fee}\nPayment Required: Yes\nPlease complete payment through the Alumni Portal to confirm your registration."
        elif event_fee:
            payment_section = f"Registration Fee: ${event_fee}"
        else:
            payment_section = "Registration: Free"

        # Build virtual section
        virtual_section = ""
        if virtual_link:
            virtual_section = f"Virtual Attendance Option:\nJoin online at: {virtual_link}"

        template = load_template('alumni/alumni_enhanced_event_invitation')
        if template:
            template_vars = {
                'recipient_name': first_name,
                'event_name': event_name,
                'event_type': event_type if event_type else "General Event",
                'event_date': str(event_date) if event_date else "TBD",
                'event_location': event_location if event_location else "TBD",
                'payment_section': payment_section,
                'virtual_section': virtual_section
            }

            subject, body = render_template('alumni_enhanced_event_invitation', template_vars)
            if subject and body:
                send_email(email, subject, body)
                print(f"Enhanced invitation sent to {email}")
            else:
                # Fallback to simple email
                _send_simple_event_email(email, first_name, event_name, event_date,
                                        event_location, event_type, payment_section, virtual_section)
        else:
            # No template available, send simple email
            _send_simple_event_email(email, first_name, event_name, event_date,
                                    event_location, event_type, payment_section, virtual_section)
    except Exception as e:
        print(f"Failed to send enhanced invitation to {email}: {e}")


def _send_simple_event_email(email, first_name, event_name, event_date, event_location,
                            event_type, payment_section, virtual_section):
    """Fallback simple event email when template is not available - now uses template system"""
    from university_system.infrastructure.email.template_utils import render_template

    template_vars = {
        'first_name': first_name,
        'event_name': event_name,
        'event_type': event_type if event_type else 'Alumni Event',
        'event_date': event_date if event_date else 'TBD',
        'event_location': event_location if event_location else 'TBD',
        'payment_section': payment_section,
        'virtual_section': virtual_section
    }

    subject, body = render_template('alumni_enhanced_event_invitation', template_vars)

    if not subject or not body:
        # Final fallback if template fails
        subject = f"Invitation: {event_name} - {event_type if event_type else 'Alumni Event'}"
        body = f"""Dear {first_name},

You are cordially invited to our upcoming alumni event!

Event Details:
--------------
Event: {event_name}
Type: {event_type if event_type else 'General Event'}
Date: {event_date if event_date else 'TBD'}
Location: {event_location if event_location else 'TBD'}

{payment_section}

{virtual_section}

To RSVP or register for this event, please log in to the Alumni Portal.

We hope to see you there!

Best regards,
The Alumni Relations Team
University Alumni Network"""

    send_email(email, subject, body)
    print(f"Simple invitation sent to {email}")

def event_check_in_system():
    """Event check-in system using QR codes or manual entry"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to use the check-in system.")
        return
    
    if not auth.check_permission('manage_events_advanced'):
        print("You don't have permission to manage event check-ins.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nEvent Check-In System")
    print("=====================")
    
    # Get today's events
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT event_id, event_name, event_date, event_location
        FROM alumni_events
        WHERE date(event_date) = ?
        ORDER BY event_date
    ''', (today,))
    
    today_events = cursor.fetchall()
    
    if not today_events:
        print("No events scheduled for today.")
        conn.close()
        return
    
    print("Today's Events:")
    for i, event in enumerate(today_events, 1):
        print(f"{i}. {event[1]} - {event[2]} at {event[3]}")
    
    try:
        event_choice = int(input(f"Select event for check-in (1-{len(today_events)}): "))
        if 1 <= event_choice <= len(today_events):
            selected_event = today_events[event_choice - 1]
            event_id = selected_event[0]
        else:
            print("Invalid selection.")
            conn.close()
            return
    except ValueError:
        print("Invalid input.")
        conn.close()
        return
    
    print(f"\nCheck-In for: {selected_event[1]}")
    print("1. Manual Check-In (Enter Alumni ID)")
    print("2. QR Code Check-In (Scan QR Code)")
    print("3. View Current Attendance")
    
    checkin_choice = input("Select check-in method: ")
    
    if checkin_choice == '1':
        # Manual check-in
        alumni_id = input("Enter Alumni ID: ")
        process_event_checkin(event_id, alumni_id, cursor)
        
    elif checkin_choice == '2':
        # QR Code check-in (simulated)
        print("QR Code scanner ready...")
        qr_data = input("Scan QR code or enter QR data: ")
        
        if qr_data.startswith("EVENT_CHECKIN:"):
            scanned_event_id = qr_data.split(":")[1]
            if scanned_event_id == str(event_id):
                alumni_id = input("Enter Alumni ID from registration: ")
                process_event_checkin(event_id, alumni_id, cursor)
            else:
                print("QR code is for a different event.")
        else:
            print("Invalid QR code format.")
            
    elif checkin_choice == '3':
        # View attendance
        cursor.execute('''
            SELECT er.*, a.first_name, a.last_name
            FROM event_registrations er
            JOIN alumni a ON er.alumni_id = a.alumni_id
            WHERE er.event_id = ? AND er.attendance_confirmed = 1
            ORDER BY er.check_in_time
        ''', (event_id,))
        
        attendees = cursor.fetchall()
        
        print(f"\nCurrent Attendance: {len(attendees)}")
        if attendees:
            print("-" * 60)
            for attendee in attendees:
                name = f"{attendee[7]} {attendee[8]}"
                checkin_time = attendee[6] if attendee[6] else "Unknown"
                print(f"{name} - Checked in: {checkin_time}")
    else:
        print("Invalid choice.")
    
    conn.commit()
    conn.close()

def process_event_checkin(event_id, alumni_id, cursor):
    """Process event check-in for an alumni"""
    # Check if alumni is registered
    cursor.execute('''
        SELECT * FROM event_registrations 
        WHERE event_id = ? AND alumni_id = ?
    ''', (event_id, alumni_id))
    
    registration = cursor.fetchone()
    
    if not registration:
        print(f"Alumni {alumni_id} is not registered for this event.")
        return
    
    if registration[4]:  # attendance_confirmed
        print(f"Alumni {alumni_id} has already checked in.")
        return
    
    # Check payment status if required
    if registration[5] == 'pending':  # payment_status
        print(f"Alumni {alumni_id} has pending payment. Please process payment first.")
        return
    
    # Update check-in
    check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        UPDATE event_registrations 
        SET attendance_confirmed = 1, check_in_time = ?
        WHERE event_id = ? AND alumni_id = ?
    ''', (check_in_time, event_id, alumni_id))
    
    # Get alumni name for confirmation
    cursor.execute('SELECT first_name, last_name FROM alumni WHERE alumni_id = ?', (alumni_id,))
    alumni_info = cursor.fetchone()
    
    if alumni_info:
        name = f"{alumni_info[0]} {alumni_info[1]}"
        print(f"✅ {name} ({alumni_id}) checked in successfully at {check_in_time}")
        
        # Award engagement points
        award_engagement_points(alumni_id, 'event_attendance', 20)

# ADVANCED DONATION FEATURES

def create_fundraising_campaign():
    """Create a new fundraising campaign"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create fundraising campaigns.")
        return
    
    if not auth.check_permission('manage_campaigns'):
        print("You don't have permission to create fundraising campaigns.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nCreate Fundraising Campaign")
    print("===========================")
    
    campaign_name = input("Campaign Name: ")
    while not campaign_name:
        print("Error: Campaign name is required.")
        campaign_name = input("Campaign Name: ")
    
    description = input("Campaign Description: ")
    
    # Goal amount
    while True:
        try:
            goal_amount = float(input("Goal Amount ($): "))
            if goal_amount <= 0:
                print("Error: Goal amount must be greater than zero.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid amount.")
    
    # Campaign dates
    start_date = input("Start Date (YYYY-MM-DD, press Enter for today): ")
    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    else:
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format, using today.")
            start_date = datetime.now().strftime('%Y-%m-%d')
    
    end_date = input("End Date (YYYY-MM-DD): ")
    while True:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            if end_date_obj <= start_date_obj:
                print("Error: End date must be after start date.")
                end_date = input("End Date (YYYY-MM-DD): ")
                continue
            break
        except ValueError:
            print("Error: Invalid date format.")
            end_date = input("End Date (YYYY-MM-DD): ")
    
    # Campaign categories
    categories = [
        "Annual Fund", "Scholarship Fund", "Building Fund", "Research Fund",
        "Athletics Fund", "Library Fund", "Emergency Fund", "Endowment",
        "Student Support", "Faculty Support", "Infrastructure", "Other"
    ]
    
    print("\nCampaign Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "Other"
    except ValueError:
        category = "Other"
    
    is_featured = input("Feature this campaign on the main page? (y/n): ").lower() == 'y'
    
    # Insert campaign
    cursor.execute('''
        INSERT INTO fundraising_campaigns 
        (campaign_name, description, goal_amount, start_date, end_date, 
         created_by, created_date, category, is_featured)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (campaign_name, description, goal_amount, start_date, end_date,
          auth.current_user['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          category, is_featured))
    
    campaign_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    print(f"\nFundraising campaign created successfully!")
    print(f"Campaign ID: {campaign_id}")
    print(f"Goal: ${goal_amount:,.2f}")
    print(f"Duration: {start_date} to {end_date}")

def view_fundraising_campaigns():
    """View and manage fundraising campaigns"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view campaigns.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nFundraising Campaigns")
    print("=====================")
    print("1. View Active Campaigns")
    print("2. View All Campaigns")
    print("3. Campaign Performance")
    if auth.check_permission('manage_campaigns'):
        print("4. Manage Campaigns")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # Active campaigns
        cursor.execute('''
            SELECT * FROM fundraising_campaigns
            WHERE status = 'active' AND end_date >= date('now')
            ORDER BY is_featured DESC, created_date DESC
        ''')
        
    elif choice == '2':
        # All campaigns
        cursor.execute('''
            SELECT * FROM fundraising_campaigns
            ORDER BY created_date DESC
        ''')
        
    elif choice == '3':
        # Campaign performance
        view_campaign_performance(cursor)
        conn.close()
        return
        
    elif choice == '4' and auth.check_permission('manage_campaigns'):
        # Manage campaigns
        manage_campaigns(cursor)
        conn.close()
        return
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    campaigns = cursor.fetchall()
    
    if not campaigns:
        print("No campaigns found.")
    else:
        print(f"\nFound {len(campaigns)} campaigns:")
        print("-" * 80)
        
        for campaign in campaigns:
            progress_percentage = (campaign[4] / campaign[3] * 100) if campaign[3] > 0 else 0
            
            print(f"Campaign: {campaign[1]}")
            print(f"Goal: ${campaign[3]:,.2f} | Raised: ${campaign[4]:,.2f} ({progress_percentage:.1f}%)")
            print(f"Period: {campaign[5]} to {campaign[6]}")
            print(f"Category: {campaign[9]} | Status: {campaign[8]}")
            if campaign[10]:  # is_featured
                print("⭐ FEATURED CAMPAIGN")
            print(f"Description: {campaign[2][:100]}...")
            print("-" * 80)
    
    conn.close()

def view_campaign_performance(cursor):
    """View detailed campaign performance analytics"""
    # Get campaign performance data
    cursor.execute('''
        SELECT 
            fc.campaign_id,
            fc.campaign_name,
            fc.goal_amount,
            fc.current_amount,
            COUNT(d.donation_id) as total_donations,
            AVG(d.amount) as avg_donation,
            MAX(d.amount) as largest_donation,
            COUNT(DISTINCT d.alumni_id) as unique_donors
        FROM fundraising_campaigns fc
        LEFT JOIN donations d ON fc.campaign_id = d.campaign_id
        GROUP BY fc.campaign_id
        ORDER BY fc.current_amount DESC
    ''')
    
    performance_data = cursor.fetchall()
    
    if not performance_data:
        print("No campaign performance data available.")
        return
    
    print("\nCampaign Performance Report")
    print("===========================")
    
    for data in performance_data:
        campaign_id, name, goal, current, total_donations, avg_donation, largest, unique_donors = data
        progress = (current / goal * 100) if goal > 0 else 0
        
        print(f"\nCampaign: {name}")
        print(f"Progress: ${current:,.2f} / ${goal:,.2f} ({progress:.1f}%)")
        print(f"Total Donations: {total_donations}")
        print(f"Unique Donors: {unique_donors}")
        if avg_donation:
            print(f"Average Donation: ${avg_donation:.2f}")
        if largest:
            print(f"Largest Donation: ${largest:.2f}")
        
        # Progress bar
        bar_length = 40
        filled_length = int(bar_length * progress / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"[{bar}] {progress:.1f}%")
        print("-" * 50)

def manage_donor_recognition():
    """Manage donor recognition levels and benefits"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage donor recognition.")
        return
    
    if not auth.check_permission('manage_campaigns'):
        print("You don't have permission to manage donor recognition.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nDonor Recognition Management")
    print("============================")
    print("1. View Current Recognition Levels")
    print("2. Update Alumni Recognition Levels")
    print("3. Recognition Level Report")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # View current levels
        cursor.execute('''
            SELECT dr.*, a.first_name, a.last_name
            FROM donor_recognition dr
            JOIN alumni a ON dr.alumni_id = a.alumni_id
            ORDER BY dr.total_donated DESC
        ''')
        
        recognitions = cursor.fetchall()
        
        if recognitions:
            print("\nCurrent Donor Recognition Levels:")
            print("-" * 70)
            for rec in recognitions:
                name = f"{rec[5]} {rec[6]}"
                print(f"{name}: {rec[2]} (${rec[3]:,.2f} total)")
                if rec[4]:  # benefits
                    print(f"  Benefits: {rec[4]}")
                print("-" * 70)
        else:
            print("No donor recognition records found.")
            
    elif choice == '2':
        # Update recognition levels
        update_donor_recognition_levels(cursor)
        
    elif choice == '3':
        # Recognition report
        generate_recognition_report(cursor)
    else:
        print("Invalid choice.")
    
    conn.close()

def update_donor_recognition_levels(cursor):
    """Update donor recognition levels based on total donations"""
    # Define recognition levels
    recognition_levels = [
        ("Bronze Supporter", 100, "Newsletter subscription, alumni directory access"),
        ("Silver Supporter", 500, "Event invitations, recognition in publications"),
        ("Gold Supporter", 1000, "VIP event access, annual appreciation dinner"),
        ("Platinum Supporter", 5000, "Board meeting invitations, naming opportunities"),
        ("Diamond Supporter", 10000, "Personal meetings with leadership, legacy society membership"),
        ("Benefactor", 25000, "Permanent recognition, advisory board invitation")
    ]
    
    # Get all donors with their total donations
    cursor.execute('''
        SELECT alumni_id, SUM(amount) as total_donated
        FROM donations
        GROUP BY alumni_id
        HAVING total_donated > 0
    ''')
    
    donors = cursor.fetchall()
    
    print(f"Updating recognition levels for {len(donors)} donors...")
    
    updated_count = 0
    for alumni_id, total_donated in donors:
        # Determine recognition level
        recognition_level = "Supporter"
        benefits = "Basic alumni benefits"
        
        for level_name, min_amount, level_benefits in reversed(recognition_levels):
            if total_donated >= min_amount:
                recognition_level = level_name
                benefits = level_benefits
                break
        
        # Update or insert recognition record
        cursor.execute('''
            INSERT OR REPLACE INTO donor_recognition 
            (alumni_id, recognition_level, total_donated, recognition_date, benefits)
            VALUES (?, ?, ?, ?, ?)
        ''', (alumni_id, recognition_level, total_donated, 
              datetime.now().strftime('%Y-%m-%d'), benefits))
        
        updated_count += 1
    
    print(f"Updated {updated_count} donor recognition levels.")

def generate_recognition_report(cursor):
    """Generate donor recognition report"""
    cursor.execute('''
        SELECT recognition_level, COUNT(*) as count, SUM(total_donated) as total_amount
        FROM donor_recognition
        GROUP BY recognition_level
        ORDER BY total_amount DESC
    ''')
    
    report_data = cursor.fetchall()
    
    if report_data:
        print("\nDonor Recognition Level Report")
        print("==============================")
        
        total_donors = 0
        total_amount = 0
        
        for level, count, amount in report_data:
            total_donors += count
            total_amount += amount
            print(f"{level}: {count} donors (${amount:,.2f})")
        
        print("-" * 40)
        print(f"Total: {total_donors} donors (${total_amount:,.2f})")
    else:
        print("No recognition data available.")

# SOCIAL FEATURES & ENGAGEMENT

def create_alumni_story():
    """Create an alumni success story or spotlight"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to create alumni stories.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    elif auth.check_permission('manage_social_features'):
        # Staff can create stories for any alumni
        alumni_id = input("Enter Alumni ID for the story: ")
        cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (alumni_id,))
        if not cursor.fetchone():
            print("Alumni not found.")
            conn.close()
            return
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    print("\nCreate Alumni Story")
    print("===================")
    
    # Story types
    story_types = [
        "Career Achievement", "Community Service", "Entrepreneurship",
        "Research & Innovation", "Personal Journey", "Alumni Spotlight",
        "Industry Leadership", "Social Impact", "Education & Teaching"
    ]
    
    print("\nStory Types:")
    for i, stype in enumerate(story_types, 1):
        print(f"{i}. {stype}")
    
    try:
        type_choice = int(input("Select story type: "))
        if 1 <= type_choice <= len(story_types):
            story_type = story_types[type_choice - 1]
        else:
            story_type = "Alumni Spotlight"
    except ValueError:
        story_type = "Alumni Spotlight"
    
    title = input("Story Title: ")
    while not title:
        print("Error: Title is required.")
        title = input("Story Title: ")
    
    print("\nStory Content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)
    
    content = "\n".join(content_lines)
    
    if not content:
        print("Error: Story content is required.")
        conn.close()
        return
    
    # Categories
    categories = [
        "Professional Success", "Community Impact", "Innovation",
        "Leadership", "Inspiration", "Education", "Technology", "Arts"
    ]
    
    print("\nStory Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")
    
    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "Professional Success"
    except ValueError:
        category = "Professional Success"
    
    is_featured = False
    if auth.check_permission('manage_social_features'):
        is_featured = input("Feature this story? (y/n): ").lower() == 'y'
    
    # Insert story
    cursor.execute('''
        INSERT INTO alumni_stories 
        (alumni_id, title, content, story_type, publish_date, is_featured, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, title, content, story_type, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), is_featured, category))
    
    story_id = cursor.lastrowid
    
    # Award engagement points
    award_engagement_points(alumni_id, 'story_created', 30)
    
    conn.commit()
    conn.close()
    
    print(f"\nAlumni story created successfully! Story ID: {story_id}")
    if is_featured:
        print("Story has been featured on the main page.")

def view_alumni_stories():
    """View alumni stories and spotlights"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view alumni stories.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAlumni Stories")
    print("==============")
    print("1. View Featured Stories")
    print("2. View Recent Stories")
    print("3. Search Stories by Category")
    print("4. Search Stories by Alumni")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # Featured stories
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            WHERE s.is_featured = 1
            ORDER BY s.publish_date DESC
        ''')
        
    elif choice == '2':
        # Recent stories
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            ORDER BY s.publish_date DESC
            LIMIT 20
        ''')
        
    elif choice == '3':
        # Search by category
        categories = [
            "Professional Success", "Community Impact", "Innovation",
            "Leadership", "Inspiration", "Education", "Technology", "Arts"
        ]
        
        print("\nStory Categories:")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        try:
            cat_choice = int(input("Select category: "))
            if 1 <= cat_choice <= len(categories):
                selected_category = categories[cat_choice - 1]
                cursor.execute('''
                    SELECT s.*, a.first_name, a.last_name, a.graduation_year
                    FROM alumni_stories s
                    JOIN alumni a ON s.alumni_id = a.alumni_id
                    WHERE s.category = ?
                    ORDER BY s.publish_date DESC
                ''', (selected_category,))
            else:
                print("Invalid category.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
            
    elif choice == '4':
        # Search by alumni
        search_name = input("Enter alumni name (partial match): ")
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            WHERE a.first_name LIKE ? OR a.last_name LIKE ?
            ORDER BY s.publish_date DESC
        ''', (f'%{search_name}%', f'%{search_name}%'))
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    stories = cursor.fetchall()
    
    if not stories:
        print("No stories found.")
    else:
        print(f"\nFound {len(stories)} stories:")
        print("-" * 80)
        
        for i, story in enumerate(stories, 1):
            author_name = f"{story[9]} {story[10]}"
            graduation_year = story[11]
            
            print(f"{i}. {story[2]} ⭐" if story[6] else f"{i}. {story[2]}")
            print(f"   By: {author_name} (Class of {graduation_year})")
            print(f"   Type: {story[4]} | Category: {story[8]}")
            print(f"   Published: {story[5]}")
            print(f"   Views: {story[7]}")
            print(f"   {story[3][:150]}...")
            print("-" * 80)
        
        # Option to read full story
        read_choice = input(f"\nEnter story number to read (1-{len(stories)}) or press Enter to continue: ")
        if read_choice.isdigit():
            story_index = int(read_choice) - 1
            if 0 <= story_index < len(stories):
                read_full_story(stories[story_index], cursor)
    
    conn.close()

def read_full_story(story, cursor):
    """Read full alumni story and update view count"""
    print(f"\n{'='*60}")
    print(f"Title: {story[2]}")
    print(f"Type: {story[4]} | Category: {story[8]}")
    print(f"Published: {story[5]}")
    if story[6]:  # is_featured
        print("⭐ FEATURED STORY")
    print(f"{'='*60}")
    print(story[3])
    print(f"{'='*60}")
    
    # Update view count
    cursor.execute('''
        UPDATE alumni_stories 
        SET view_count = view_count + 1 
        WHERE story_id = ?
    ''', (story[0],))

def manage_class_reunions():
    """Manage class reunion planning"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage class reunions.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nClass Reunion Management")
    print("========================")
    print("1. Create New Reunion")
    print("2. View Upcoming Reunions")
    print("3. Manage Existing Reunion")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        create_class_reunion(cursor)
    elif choice == '2':
        view_class_reunions(cursor)
    elif choice == '3':
        manage_existing_reunion(cursor)
    else:
        print("Invalid choice.")
    
    conn.close()

def create_class_reunion(cursor):
    """Create a new class reunion"""
    global auth
    
    if not (auth.check_permission('manage_social_features') or auth.check_permission('manage_events_advanced')):
        print("You don't have permission to create reunions.")
        return
    
    print("\nCreate Class Reunion")
    print("====================")
    
    # Get graduation year
    while True:
        try:
            graduation_year = int(input("Graduation Year: "))
            current_year = datetime.now().year
            if graduation_year > current_year:
                print("Error: Graduation year cannot be in the future.")
                continue
            elif graduation_year < 1900:
                print("Error: Please enter a valid graduation year.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid year.")
    
    # Check how many alumni from this year
    cursor.execute('SELECT COUNT(*) FROM alumni WHERE graduation_year = ?', (graduation_year,))
    alumni_count = cursor.fetchone()[0]
    print(f"Found {alumni_count} alumni from the Class of {graduation_year}")
    
    if alumni_count == 0:
        print("No alumni found for this graduation year.")
        return
    
    # Reunion details
    while True:
        reunion_date_str = input("Reunion Date and Time (YYYY-MM-DD HH:MM): ")
        try:
            reunion_date = datetime.strptime(reunion_date_str, "%Y-%m-%d %H:%M")
            if reunion_date < datetime.now():
                print("Error: Reunion date cannot be in the past.")
                continue
            reunion_date_str = reunion_date.strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD HH:MM.")
    
    location = input("Reunion Location: ")
    while not location:
        print("Error: Location is required.")
        location = input("Reunion Location: ")
    
    description = input("Reunion Description: ")
    
    # Registration fee
    while True:
        try:
            registration_fee = float(input("Registration Fee ($, 0 for free): "))
            if registration_fee < 0:
                print("Error: Fee cannot be negative.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid amount.")
    
    # Max attendees
    while True:
        try:
            max_attendees = int(input("Maximum Attendees (0 for unlimited): "))
            if max_attendees < 0:
                print("Error: Cannot be negative.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid number.")
    
    # Get organizer ID
    organizer_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        organizer_id = result[0]
    else:
        organizer_id = input("Enter Alumni ID of the organizer: ")
    
    # Insert reunion
    cursor.execute('''
        INSERT INTO class_reunions 
        (graduation_year, reunion_date, location, organizer_id, description, 
         registration_fee, max_attendees, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (graduation_year, reunion_date_str, location, organizer_id, description,
          registration_fee, max_attendees, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    reunion_id = cursor.lastrowid
    
    print(f"\nClass reunion created successfully! Reunion ID: {reunion_id}")
    print(f"Class of {graduation_year} Reunion")
    print(f"Date: {reunion_date_str}")
    print(f"Location: {location}")
    
    # Send invitations
    notify = input("Send invitations to all Class of {graduation_year} alumni? (y/n): ".format(graduation_year)).lower()
    if notify == 'y':
        send_reunion_invitations(graduation_year, reunion_id, cursor)

def send_reunion_invitations(graduation_year, reunion_id, cursor):
    """Send reunion invitations to alumni from specific graduation year"""
    # Get reunion details
    cursor.execute('''
        SELECT reunion_date, location, description
        FROM class_reunions
        WHERE reunion_id = ?
    ''', (reunion_id,))
    reunion_info = cursor.fetchone()
    reunion_date = reunion_info[0] if reunion_info else "TBD"
    reunion_location = reunion_info[1] if reunion_info else "TBD"
    reunion_description = reunion_info[2] if reunion_info and reunion_info[2] else "Join us for a memorable reunion with your classmates!"

    cursor.execute('''
        SELECT alumni_id, email_address, first_name, last_name
        FROM alumni
        WHERE graduation_year = ?
    ''', (graduation_year,))

    alumni_list = cursor.fetchall()

    if alumni_list:
        print(f"Sending reunion invitations to {len(alumni_list)} alumni from Class of {graduation_year}...")

        template = load_template('alumni/alumni_reunion_invitation')
        sent_count = 0
        failed_count = 0

        for alumni in alumni_list:
            alumni_id, email, first_name, last_name = alumni[0], alumni[1], alumni[2], alumni[3] if len(alumni) > 3 else ""
            recipient_name = f"{first_name} {last_name}".strip() if last_name else first_name

            if not email:
                continue

            try:
                if template:
                    template_vars = {
                        'recipient_name': recipient_name,
                        'graduation_year': str(graduation_year),
                        'reunion_date': str(reunion_date),
                        'reunion_location': reunion_location,
                        'reunion_description': reunion_description
                    }

                    subject, body = render_template('alumni_reunion_invitation', template_vars)
                    if subject and body:
                        send_email(email, subject, body)
                        sent_count += 1
                    else:
                        # Fallback to simple email
                        _send_simple_reunion_email(email, recipient_name, graduation_year,
                                                  reunion_date, reunion_location, reunion_description)
                        sent_count += 1
                else:
                    # No template, send simple email
                    _send_simple_reunion_email(email, recipient_name, graduation_year,
                                              reunion_date, reunion_location, reunion_description)
                    sent_count += 1

                print(f"Invitation sent to {email}")
            except Exception as e:
                print(f"Failed to send to {email}: {e}")
                failed_count += 1

        print(f"Reunion invitations sent successfully to {sent_count} alumni!")
        if failed_count > 0:
            print(f"Failed to send to {failed_count} alumni.")
    else:
        print("No alumni found to invite.")


def _send_simple_reunion_email(email, recipient_name, graduation_year, reunion_date,
                               reunion_location, reunion_description):
    """Fallback simple reunion email when template is not available - now uses template system"""
    from university_system.infrastructure.email.template_utils import render_template

    template_vars = {
        'recipient_name': recipient_name,
        'graduation_year': graduation_year,
        'reunion_date': reunion_date,
        'reunion_location': reunion_location,
        'reunion_description': reunion_description
    }

    subject, body = render_template('alumni_reunion_invitation', template_vars)

    if not subject or not body:
        # Final fallback if template fails
        subject = f"You're Invited: Class of {graduation_year} Reunion!"
        body = f"""Dear {recipient_name},

We are excited to invite you to the Class of {graduation_year} Reunion!

Event Details:
--------------
Date: {reunion_date}
Location: {reunion_location}
Description: {reunion_description}

This is a wonderful opportunity to reconnect with your classmates and relive your university memories.

To RSVP for this event, please log in to the Alumni Portal or reply to this email.

We look forward to seeing you there!

Best regards,
The Alumni Relations Team
University Alumni Network"""

    send_email(email, subject, body)

def manage_regional_chapters():
    """Manage regional alumni chapters"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage regional chapters.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nRegional Chapter Management")
    print("===========================")
    print("1. View All Chapters")
    print("2. Create New Chapter")
    print("3. Join a Chapter")
    print("4. My Chapters")
    if auth.check_permission('manage_social_features'):
        print("5. Manage Chapter (Admin)")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        view_regional_chapters(cursor)
    elif choice == '2':
        create_regional_chapter(cursor)
    elif choice == '3':
        join_regional_chapter(cursor)
    elif choice == '4':
        view_my_chapters(cursor)
    elif choice == '5' and auth.check_permission('manage_social_features'):
        admin_manage_chapters(cursor)
    else:
        print("Invalid choice.")
    
    conn.close()

def view_regional_chapters(cursor):
    """View all regional chapters"""
    cursor.execute('''
        SELECT c.*, a.first_name, a.last_name
        FROM regional_chapters c
        LEFT JOIN alumni a ON c.coordinator_id = a.alumni_id
        ORDER BY c.chapter_name
    ''')
    
    chapters = cursor.fetchall()
    
    if not chapters:
        print("No regional chapters found.")
        return
    
    print("\nRegional Alumni Chapters:")
    print("-" * 60)
    
    for chapter in chapters:
        coordinator_name = f"{chapter[7]} {chapter[8]}" if chapter[7] else "No coordinator"
        
        print(f"Chapter: {chapter[1]}")
        print(f"Location: {chapter[2]}")
        print(f"Coordinator: {coordinator_name}")
        print(f"Members: {chapter[6]}")
        print(f"Description: {chapter[4]}")
        print(f"Created: {chapter[5]}")
        print("-" * 60)

def create_regional_chapter(cursor):
    """Create a new regional chapter"""
    global auth
    
    if not auth.check_permission('manage_social_features'):
        print("You don't have permission to create regional chapters.")
        return
    
    print("\nCreate Regional Chapter")
    print("=======================")
    
    chapter_name = input("Chapter Name: ")
    while not chapter_name:
        print("Error: Chapter name is required.")
        chapter_name = input("Chapter Name: ")
    
    location = input("Chapter Location (city, state/country): ")
    while not location:
        print("Error: Location is required.")
        location = input("Chapter Location: ")
    
    description = input("Chapter Description: ")
    
    coordinator_id = input("Coordinator Alumni ID: ")
    
    # Verify coordinator exists
    cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (coordinator_id,))
    if not cursor.fetchone():
        print("Coordinator not found.")
        return
    
    # Insert chapter
    cursor.execute('''
        INSERT INTO regional_chapters 
        (chapter_name, location, coordinator_id, description, created_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (chapter_name, location, coordinator_id, description,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    chapter_id = cursor.lastrowid
    
    # Add coordinator as first member
    cursor.execute('''
        INSERT INTO chapter_memberships (chapter_id, alumni_id, join_date, role)
        VALUES (?, ?, ?, ?)
    ''', (chapter_id, coordinator_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'coordinator'))
    
    # Update member count
    cursor.execute('UPDATE regional_chapters SET member_count = 1 WHERE chapter_id = ?', (chapter_id,))
    
    print(f"\nRegional chapter created successfully! Chapter ID: {chapter_id}")

def join_regional_chapter(cursor):
    """Join a regional chapter"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    # Show available chapters
    cursor.execute('SELECT * FROM regional_chapters ORDER BY chapter_name')
    chapters = cursor.fetchall()
    
    if not chapters:
        print("No regional chapters available.")
        return
    
    print("\nAvailable Regional Chapters:")
    for i, chapter in enumerate(chapters, 1):
        print(f"{i}. {chapter[1]} ({chapter[2]}) - {chapter[6]} members")
    
    try:
        chapter_choice = int(input(f"Select chapter to join (1-{len(chapters)}): "))
        if 1 <= chapter_choice <= len(chapters):
            selected_chapter = chapters[chapter_choice - 1]
            chapter_id = selected_chapter[0]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    
    # Check if already a member
    cursor.execute('''
        SELECT * FROM chapter_memberships 
        WHERE chapter_id = ? AND alumni_id = ?
    ''', (chapter_id, alumni_id))
    
    if cursor.fetchone():
        print("You are already a member of this chapter.")
        return
    
    # Join chapter
    cursor.execute('''
        INSERT INTO chapter_memberships (chapter_id, alumni_id, join_date, role)
        VALUES (?, ?, ?, ?)
    ''', (chapter_id, alumni_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'member'))
    
    # Update member count
    cursor.execute('''
        UPDATE regional_chapters 
        SET member_count = member_count + 1 
        WHERE chapter_id = ?
    ''', (chapter_id,))
    
    # Award engagement points
    award_engagement_points(alumni_id, 'chapter_joined', 15)
    
    print(f"Successfully joined {selected_chapter[1]}!")

# GAMIFICATION & ENGAGEMENT

def award_engagement_points(alumni_id, activity_type, points):
    """Award engagement points for various activities"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Award points
        cursor.execute('''
            INSERT INTO engagement_points (alumni_id, activity_type, points_earned, activity_date, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (alumni_id, activity_type, points, 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
              get_activity_description(activity_type)))
        
        # Update total engagement score
        cursor.execute('''
            UPDATE alumni 
            SET engagement_score = engagement_score + ?, last_activity = ?
            WHERE alumni_id = ?
        ''', (points, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), alumni_id))
        
        # Check for badge achievements
        check_badge_achievements(alumni_id, cursor)
        
        conn.commit()
        conn.close()
        
        print(f"🎉 Earned {points} engagement points for {activity_type}!")
        
    except Exception as e:
        print(f"Error awarding points: {e}")

def get_activity_description(activity_type):
    """Get description for activity type"""
    descriptions = {
        'profile_complete': 'Completed alumni profile',
        'event_attendance': 'Attended an alumni event',
        'donation_made': 'Made a donation',
        'mentorship_created': 'Started a mentorship',
        'job_posted': 'Posted a job opportunity',
        'job_application': 'Applied for a job',
        'forum_post': 'Created a forum post',
        'forum_reply': 'Replied to a forum discussion',
        'story_created': 'Shared an alumni story',
        'connection_made': 'Made a networking connection',
        'chapter_joined': 'Joined a regional chapter',
        'newsletter_opened': 'Opened a newsletter',
        'profile_updated': 'Updated profile information'
    }
    return descriptions.get(activity_type, f'Completed {activity_type}')

def check_badge_achievements(alumni_id, cursor):
    """Check if alumni has earned any new badges"""
    # Get current total points
    cursor.execute('''
        SELECT SUM(points_earned) as total_points
        FROM engagement_points
        WHERE alumni_id = ?
    ''', (alumni_id,))
    
    result = cursor.fetchone()
    total_points = result[0] if result[0] else 0
    
    # Get badges not yet earned
    cursor.execute('''
        SELECT b.badge_id, b.badge_name, b.points_required
        FROM achievement_badges b
        WHERE b.badge_id NOT IN (
            SELECT badge_id FROM alumni_badges WHERE alumni_id = ?
        ) AND b.points_required <= ?
        ORDER BY b.points_required
    ''', (alumni_id, total_points))
    
    new_badges = cursor.fetchall()
    
    for badge_id, badge_name, points_required in new_badges:
        # Award the badge
        cursor.execute('''
            INSERT INTO alumni_badges (alumni_id, badge_id, earned_date)
            VALUES (?, ?, ?)
        ''', (alumni_id, badge_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        print(f"🏆 Congratulations! You've earned the '{badge_name}' badge!")

def view_engagement_leaderboard():
    """View alumni engagement leaderboard"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view the leaderboard.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAlumni Engagement Leaderboard")
    print("=============================")
    print("1. Overall Leaderboard")
    print("2. Monthly Leaderboard")
    print("3. My Ranking")
    print("4. Badge Leaderboard")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # Overall leaderboard
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year, a.engagement_score,
                   COUNT(ab.badge_id) as badge_count
            FROM alumni a
            LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
            WHERE a.engagement_score > 0
            GROUP BY a.alumni_id
            ORDER BY a.engagement_score DESC
            LIMIT 20
        ''')
        
        results = cursor.fetchall()
        
        if results:
            print("\nTop 20 Engaged Alumni (All Time):")
            print("-" * 70)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Points':<8} {'Badges':<8}")
            print("-" * 70)
            
            for i, (first_name, last_name, grad_year, points, badges) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {points:<8} {badges:<8}")
        else:
            print("No engagement data found.")
            
    elif choice == '2':
        # Monthly leaderboard
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year, 
                   SUM(ep.points_earned) as monthly_points
            FROM alumni a
            JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
            WHERE ep.activity_date LIKE ?
            GROUP BY a.alumni_id
            ORDER BY monthly_points DESC
            LIMIT 20
        ''', (f'{current_month}%',))
        
        results = cursor.fetchall()
        
        if results:
            print(f"\nTop 20 Engaged Alumni (This Month - {current_month}):")
            print("-" * 60)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Points':<8}")
            print("-" * 60)
            
            for i, (first_name, last_name, grad_year, points) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {points:<8}")
        else:
            print("No engagement data for this month.")
            
    elif choice == '3':
        # My ranking
        cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        if result and result[0].startswith('A'):
            alumni_id = result[0]
            
            # Get my ranking
            cursor.execute('''
                SELECT COUNT(*) + 1 as rank
                FROM alumni
                WHERE engagement_score > (
                    SELECT engagement_score FROM alumni WHERE alumni_id = ?
                )
            ''', (alumni_id,))
            
            rank = cursor.fetchone()[0]
            
            # Get my stats
            cursor.execute('''
                SELECT a.engagement_score, COUNT(ab.badge_id) as badge_count,
                       SUM(CASE WHEN ep.activity_date LIKE ? THEN ep.points_earned ELSE 0 END) as monthly_points
                FROM alumni a
                LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
                LEFT JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
                WHERE a.alumni_id = ?
                GROUP BY a.alumni_id
            ''', (datetime.now().strftime('%Y-%m') + '%', alumni_id))
            
            stats = cursor.fetchone()
            
            if stats:
                total_points, badges, monthly_points = stats
                monthly_points = monthly_points if monthly_points else 0
                
                print(f"\nYour Engagement Stats:")
                print(f"Overall Ranking: #{rank}")
                print(f"Total Points: {total_points}")
                print(f"Badges Earned: {badges}")
                print(f"Points This Month: {monthly_points}")
                
                # Show recent activities
                cursor.execute('''
                    SELECT activity_type, points_earned, activity_date, description
                    FROM engagement_points
                    WHERE alumni_id = ?
                    ORDER BY activity_date DESC
                    LIMIT 10
                ''', (alumni_id,))
                
                recent_activities = cursor.fetchall()
                
                if recent_activities:
                    print("\nRecent Activities:")
                    for activity in recent_activities:
                        print(f"  {activity[3]} (+{activity[1]} points) - {activity[2]}")
            else:
                print("No engagement data found for your profile.")
        else:
            print("Alumni profile not found.")
            
    elif choice == '4':
        # Badge leaderboard
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year, COUNT(ab.badge_id) as badge_count
            FROM alumni a
            LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
            GROUP BY a.alumni_id
            HAVING badge_count > 0
            ORDER BY badge_count DESC, a.engagement_score DESC
            LIMIT 20
        ''')
        
        results = cursor.fetchall()
        
        if results:
            print("\nTop 20 Badge Collectors:")
            print("-" * 60)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Badges':<8}")
            print("-" * 60)
            
            for i, (first_name, last_name, grad_year, badges) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {badges:<8}")
        else:
            print("No badge data found.")
    else:
        print("Invalid choice.")
    
    conn.close()

def view_my_badges():
    """View badges earned by current user"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your badges.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    # Get earned badges
    cursor.execute('''
        SELECT b.badge_name, b.badge_description, b.category, ab.earned_date
        FROM achievement_badges b
        JOIN alumni_badges ab ON b.badge_id = ab.badge_id
        WHERE ab.alumni_id = ?
        ORDER BY ab.earned_date DESC
    ''', (alumni_id,))
    
    earned_badges = cursor.fetchall()
    
    # Get available badges
    cursor.execute('''
        SELECT b.badge_name, b.badge_description, b.points_required, b.category
        FROM achievement_badges b
        WHERE b.badge_id NOT IN (
            SELECT badge_id FROM alumni_badges WHERE alumni_id = ?
        )
        ORDER BY b.points_required
    ''', (alumni_id,))
    
    available_badges = cursor.fetchall()
    
    # Get current points
    cursor.execute('''
        SELECT SUM(points_earned) as total_points
        FROM engagement_points
        WHERE alumni_id = ?
    ''', (alumni_id,))
    
    total_points = cursor.fetchone()[0] or 0
    
    print(f"\nYour Alumni Badges (Total Points: {total_points})")
    print("=" * 50)
    
    if earned_badges:
        print("\n🏆 Earned Badges:")
        print("-" * 40)
        for badge_name, description, category, earned_date in earned_badges:
            print(f"✅ {badge_name}")
            print(f"   {description}")
            print(f"   Category: {category} | Earned: {earned_date}")
            print()
    else:
        print("\nNo badges earned yet. Keep engaging to earn your first badge!")
    
    if available_badges:
        print("\n🎯 Available Badges:")
        print("-" * 40)
        for badge_name, description, points_required, category in available_badges:
            progress = "✅ Ready to claim!" if total_points >= points_required else f"Need {points_required - total_points} more points"
            print(f"🏅 {badge_name} ({points_required} points required)")
            print(f"   {description}")
            print(f"   Category: {category} | Status: {progress}")
            print()
    
    conn.close()

# CONTENT MANAGEMENT

def manage_photo_gallery():
    """Manage event photo gallery"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage photos.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nPhoto Gallery Management")
    print("========================")
    print("1. View Photo Gallery")
    print("2. Upload Photos")
    print("3. My Uploaded Photos")
    if auth.check_permission('manage_content'):
        print("4. Moderate Photos")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        view_photo_gallery(cursor)
    elif choice == '2':
        upload_photos(cursor)
    elif choice == '3':
        view_my_photos(cursor)
    elif choice == '4' and auth.check_permission('manage_content'):
        moderate_photos(cursor)
    else:
        print("Invalid choice.")
    
    conn.close()

def view_photo_gallery(cursor):
    """View photo gallery by events"""
    # Get events with photos
    cursor.execute('''
        SELECT e.event_id, e.event_name, e.event_date, COUNT(p.photo_id) as photo_count
        FROM alumni_events e
        LEFT JOIN photo_gallery p ON e.event_id = p.event_id
        GROUP BY e.event_id
        HAVING photo_count > 0
        ORDER BY e.event_date DESC
    ''')
    
    events_with_photos = cursor.fetchall()
    
    if not events_with_photos:
        print("No photos available in the gallery.")
        return
    
    print("\nEvents with Photos:")
    print("-" * 60)
    
    for i, (event_id, event_name, event_date, photo_count) in enumerate(events_with_photos, 1):
        print(f"{i}. {event_name} ({event_date}) - {photo_count} photos")
    
    try:
        event_choice = int(input(f"\nSelect event to view photos (1-{len(events_with_photos)}): "))
        if 1 <= event_choice <= len(events_with_photos):
            selected_event = events_with_photos[event_choice - 1]
            view_event_photos(selected_event[0], cursor)
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")

def view_event_photos(event_id, cursor):
    """View photos for a specific event"""
    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM photo_gallery p
        JOIN alumni a ON p.uploaded_by = a.alumni_id
        WHERE p.event_id = ?
        ORDER BY p.is_featured DESC, p.upload_date DESC
    ''', (event_id,))
    
    photos = cursor.fetchall()
    
    if photos:
        print(f"\nPhotos for this event ({len(photos)} total):")
        print("-" * 50)
        
        for photo in photos:
            uploader_name = f"{photo[6]} {photo[7]}"
            featured_mark = "⭐ " if photo[5] else ""
            
            print(f"{featured_mark}Photo: {photo[3]}")
            print(f"Uploaded by: {uploader_name}")
            print(f"Caption: {photo[4]}")
            print(f"Upload Date: {photo[5]}")
            print(f"Path: {photo[3]}")  # In real implementation, this would display the actual image
            print("-" * 50)
    else:
        print("No photos found for this event.")

def upload_photos(cursor):
    """Upload photos to event gallery"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    # Get recent events
    cursor.execute('''
        SELECT event_id, event_name, event_date
        FROM alumni_events
        WHERE event_date >= date('now', '-30 days')
        ORDER BY event_date DESC
    ''')
    
    recent_events = cursor.fetchall()
    
    if not recent_events:
        print("No recent events available for photo upload.")
        return
    
    print("\nSelect Event for Photo Upload:")
    for i, (event_id, event_name, event_date) in enumerate(recent_events, 1):
        print(f"{i}. {event_name} ({event_date})")
    
    try:
        event_choice = int(input(f"Select event (1-{len(recent_events)}): "))
        if 1 <= event_choice <= len(recent_events):
            selected_event = recent_events[event_choice - 1]
            event_id = selected_event[0]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    
    print(f"\nUploading photos for: {selected_event[1]}")
    
    # In a real implementation, this would handle actual file uploads
    # For now, we'll simulate the process
    photo_path = input("Enter photo file path: ")
    caption = input("Enter photo caption: ")
    
    if not photo_path:
        print("Photo path is required.")
        return
    
    # Insert photo record
    cursor.execute('''
        INSERT INTO photo_gallery (event_id, uploaded_by, photo_path, caption, upload_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_id, alumni_id, photo_path, caption, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # Award engagement points
    award_engagement_points(alumni_id, 'photo_uploaded', 5)
    
    print("Photo uploaded successfully to the gallery!")

# ADVANCED NETWORKING FEATURES

def manage_business_directory():
    """Manage alumni business directory"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the business directory.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nAlumni Business Directory")
    print("=========================")
    print("1. View Business Directory")
    print("2. Add My Business")
    print("3. Update My Business")
    print("4. Search Businesses")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        view_business_directory(cursor)
    elif choice == '2':
        add_business_listing(cursor)
    elif choice == '3':
        update_business_listing(cursor)
    elif choice == '4':
        search_business_directory(cursor)
    else:
        print("Invalid choice.")
    
    conn.close()

def view_business_directory(cursor):
    """View all business listings"""
    cursor.execute('''
        SELECT b.*, a.first_name, a.last_name
        FROM business_directory b
        JOIN alumni a ON b.alumni_id = a.alumni_id
        ORDER BY b.business_name
    ''')
    
    businesses = cursor.fetchall()
    
    if not businesses:
        print("No businesses found in the directory.")
        return
    
    print(f"\nAlumni Business Directory ({len(businesses)} businesses):")
    print("-" * 80)
    
    for business in businesses:
        owner_name = f"{business[10]} {business[11]}"
        
        print(f"Business: {business[2]}")
        print(f"Owner: {owner_name}")
        print(f"Industry: {business[4]}")
        print(f"Location: {business[8]}")
        print(f"Description: {business[3][:100]}...")
        if business[5]:  # website
            print(f"Website: {business[5]}")
        if business[7]:  # services_offered
            print(f"Services: {business[7][:80]}...")
        print("-" * 80)

def add_business_listing(cursor):
    """Add a new business listing"""
    global auth
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return
    
    # Check if business already exists
    cursor.execute('SELECT * FROM business_directory WHERE alumni_id = ?', (alumni_id,))
    if cursor.fetchone():
        print("You already have a business listing. Use 'Update My Business' to modify it.")
        return
    
    print("\nAdd Business Listing")
    print("====================")
    
    business_name = input("Business Name: ")
    while not business_name:
        print("Error: Business name is required.")
        business_name = input("Business Name: ")
    
    business_description = input("Business Description: ")
    
    # Industry selection
    industries = [
        "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
        "Retail", "Real Estate", "Legal Services", "Consulting", "Marketing",
        "Construction", "Hospitality", "Transportation", "Entertainment",
        "Non-profit", "Other"
    ]
    
    print("\nIndustries:")
    for i, industry in enumerate(industries, 1):
        print(f"{i}. {industry}")
    
    try:
        industry_choice = int(input("Select industry: "))
        if 1 <= industry_choice <= len(industries):
            industry = industries[industry_choice - 1]
        else:
            industry = "Other"
    except ValueError:
        industry = "Other"
    
    website = input("Website URL (optional): ")
    contact_email = input("Contact Email: ")
    
    print("\nServices Offered (press Enter twice to finish):")
    services_lines = []
    while True:
        line = input()
        if line == "" and (not services_lines or services_lines[-1] == ""):
            break
        services_lines.append(line)
    services_offered = "\n".join(services_lines)
    
    location = input("Business Location (city, state/country): ")
    
    # Insert business listing
    cursor.execute('''
        INSERT INTO business_directory 
        (alumni_id, business_name, business_description, industry, website, 
         contact_email, services_offered, location, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, business_name, business_description, industry, website,
          contact_email, services_offered, location, 
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # Award engagement points
    award_engagement_points(alumni_id, 'business_listed', 25)
    
    print("Business listing added successfully to the alumni directory!")

def search_business_directory(cursor):
    """Search business directory"""
    print("\nSearch Business Directory")
    print("=========================")
    print("1. Search by Industry")
    print("2. Search by Location")
    print("3. Search by Business Name")
    print("4. Search by Services")
    
    choice = input("Enter your choice: ")
    
    if choice == '1':
        # Search by industry
        industry = input("Enter industry: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.industry LIKE ?
            ORDER BY b.business_name
        ''', (f'%{industry}%',))
        
    elif choice == '2':
        # Search by location
        location = input("Enter location: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.location LIKE ?
            ORDER BY b.business_name
        ''', (f'%{location}%',))
        
    elif choice == '3':
        # Search by business name
        name = input("Enter business name: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.business_name LIKE ?
            ORDER BY b.business_name
        ''', (f'%{name}%',))
        
    elif choice == '4':
        # Search by services
        services = input("Enter services/keywords: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.services_offered LIKE ? OR b.business_description LIKE ?
            ORDER BY b.business_name
        ''', (f'%{services}%', f'%{services}%'))
    else:
        print("Invalid choice.")
        return
    
    results = cursor.fetchall()
    
    if not results:
        print("No businesses found matching your search criteria.")
    else:
        print(f"\nFound {len(results)} businesses:")
        print("-" * 80)
        
        for business in results:
            owner_name = f"{business[10]} {business[11]}"
            
            print(f"Business: {business[2]}")
            print(f"Owner: {owner_name}")
            print(f"Industry: {business[4]}")
            print(f"Location: {business[8]}")
            if business[5]:  # website
                print(f"Website: {business[5]}")
            if business[6]:  # contact_email
                print(f"Contact: {business[6]}")
            print("-" * 80)

# AI-POWERED FEATURES

def smart_mentorship_matching():
    """AI-powered mentorship matching based on interests, industry, etc."""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to use smart matching.")
        return
    
    if not auth.check_permission('manage_ai_features'):
        print("You don't have permission to use AI features.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nSmart Mentorship Matching")
    print("=========================")
    
    # Get all potential mentors
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, industry, job_title, 
               current_employer, skills, graduation_year
        FROM alumni
        WHERE is_mentor = 1
    ''')
    
    mentors = cursor.fetchall()
    
    # Get all potential mentees (for demo, using alumni who aren't mentors)
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, industry, job_title, 
               current_employer, skills, graduation_year
        FROM alumni
        WHERE is_mentor = 0 OR is_mentor IS NULL
    ''')
    
    mentees = cursor.fetchall()
    
    if not mentors or not mentees:
        print("Insufficient data for matching.")
        conn.close()
        return
    
    print(f"Analyzing {len(mentors)} mentors and {len(mentees)} potential mentees...")
    
    # Simple matching algorithm based on industry, skills, and experience gap
    matches = []
    
    for mentee in mentees:
        mentee_id, m_first, m_last, m_industry, m_job, m_employer, m_skills, m_grad_year = mentee
        mentee_skills = set((m_skills or "").lower().split(','))
        
        mentor_scores = []
        
        for mentor in mentors:
            mentor_id, mentor_first, mentor_last, mentor_industry, mentor_job, mentor_employer, mentor_skills, mentor_grad_year = mentor
            
            score = 0
            
            # Industry match
            if m_industry and mentor_industry and m_industry.lower() == mentor_industry.lower():
                score += 30
            
            # Skills overlap
            if m_skills and mentor_skills:
                mentor_skill_set = set(mentor_skills.lower().split(','))
                skill_overlap = len(mentee_skills.intersection(mentor_skill_set))
                score += skill_overlap * 10
            
            # Experience gap (mentor should be more experienced)
            if mentor_grad_year and m_grad_year and mentor_grad_year < m_grad_year:
                experience_gap = m_grad_year - mentor_grad_year
                if 3 <= experience_gap <= 15:  # Ideal gap
                    score += 20
                elif experience_gap > 15:
                    score += 10
            
            # Avoid self-matching
            if mentor_id != mentee_id:
                mentor_scores.append((mentor_id, mentor_first, mentor_last, score))
        
        # Get top 3 matches for this mentee
        mentor_scores.sort(key=lambda x: x[3], reverse=True)
        top_matches = mentor_scores[:3]
        
        if top_matches and top_matches[0][3] > 0:  # Only include if there's a positive score
            matches.append((mentee_id, f"{m_first} {m_last}", top_matches))
    
    if matches:
        print(f"\nGenerated {len(matches)} smart mentorship recommendations:")
        print("-" * 80)
        
        for mentee_id, mentee_name, mentor_matches in matches:
            print(f"Mentee: {mentee_name}")
            print("Recommended Mentors:")
            
            for i, (mentor_id, mentor_first, mentor_last, score) in enumerate(mentor_matches, 1):
                mentor_name = f"{mentor_first} {mentor_last}"
                match_quality = "Excellent" if score >= 50 else "Good" if score >= 30 else "Fair"
                print(f"  {i}. {mentor_name} (Match Score: {score} - {match_quality})")
            
            print("-" * 80)
        
        # Option to create mentorships from recommendations
        create_choice = input("Would you like to create mentorships from these recommendations? (y/n): ").lower()
        if create_choice == 'y':
            create_recommended_mentorships(matches, cursor)
    else:
        print("No suitable mentorship matches found.")
    
    conn.close()

def create_recommended_mentorships(matches, cursor):
    """Create mentorships from AI recommendations"""
    print("\nCreating Mentorships from Recommendations")
    print("=========================================")
    
    created_count = 0
    
    for mentee_id, mentee_name, mentor_matches in matches:
        print(f"\nMentee: {mentee_name}")
        print("Available mentors:")
        
        for i, (mentor_id, mentor_first, mentor_last, score) in enumerate(mentor_matches, 1):
            mentor_name = f"{mentor_first} {mentor_last}"
            print(f"  {i}. {mentor_name} (Score: {score})")
        
        choice = input(f"Select mentor for {mentee_name} (1-{len(mentor_matches)}, or 's' to skip): ")
        
        if choice.isdigit():
            mentor_index = int(choice) - 1
            if 0 <= mentor_index < len(mentor_matches):
                mentor_id, mentor_first, mentor_last, score = mentor_matches[mentor_index]
                
                # Create the mentorship
                start_date = datetime.now().strftime("%Y-%m-%d")
                focus_area = "AI-Matched General Mentorship"
                
                cursor.execute('''
                    INSERT INTO mentorships 
                    (mentor_id, mentee_id, start_date, status, focus_area, match_score, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (mentor_id, mentee_id, start_date, "Active", focus_area, score/100.0, 
                      f"AI-generated match with {score}% compatibility"))
                
                mentorship_id = cursor.lastrowid
                created_count += 1

                print(f"✅ Created mentorship {mentorship_id}: {mentor_first} {mentor_last} → {mentee_name}")

                # Automatically send mentorship notification emails
                try:
                    # Get mentor email
                    cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (mentor_id,))
                    mentor_result = cursor.fetchone()
                    mentor_email = mentor_result[0] if mentor_result else None

                    # Get mentee email
                    cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (mentee_id,))
                    mentee_result = cursor.fetchone()
                    mentee_email = mentee_result[0] if mentee_result else None

                    if mentor_email and mentee_email:
                        mentor_name = f"{mentor_first} {mentor_last}"
                        send_mentorship_notification(
                            mentor_email=mentor_email,
                            mentee_email=mentee_email,
                            mentor_name=mentor_name,
                            mentee_name=mentee_name,
                            focus_area=focus_area,
                            start_date=start_date,
                            end_date=None
                        )
                        print(f"   ✉️  Email notifications sent to mentor and mentee")
                    else:
                        print(f"   ⚠️  Could not send emails: Missing email address(es)")
                except Exception as e:
                    print(f"   ⚠️  Could not send email notification: {e}")
        elif choice.lower() == 's':
            print(f"Skipped {mentee_name}")
        else:
            print("Invalid choice, skipping.")
    
    print(f"\nCreated {created_count} mentorships from AI recommendations!")

def generate_engagement_recommendations():
    """Generate personalized engagement recommendations for alumni"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to get recommendations.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return
    
    print("\nPersonalized Engagement Recommendations")
    print("=======================================")
    
    # Get alumni profile and activity data
    cursor.execute('''
        SELECT a.*, 
               SUM(ep.points_earned) as total_points,
               MAX(ep.activity_date) as last_activity,
               COUNT(DISTINCT ep.activity_type) as activity_variety
        FROM alumni a
        LEFT JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
        WHERE a.alumni_id = ?
        GROUP BY a.alumni_id
    ''', (alumni_id,))
    
    profile_data = cursor.fetchone()
    
    if not profile_data:
        print("Profile data not found.")
        conn.close()
        return
    
    # Extract profile information
    industry = profile_data[13]
    graduation_year = profile_data[9]
    is_donor = profile_data[20]
    is_mentor = profile_data[21]
    total_points = profile_data[23] or 0
    last_activity = profile_data[24]
    activity_variety = profile_data[25] or 0
    
    recommendations = []
    
    # Analyze engagement patterns and generate recommendations
    
    # Low engagement recommendations
    if total_points < 50:
        recommendations.append({
            'type': 'engagement',
            'title': 'Get Started with Alumni Engagement',
            'description': 'Complete your profile and connect with fellow alumni to earn your first badges!',
            'action': 'Update your profile with skills and achievements',
            'points': 20
        })
    
    # Activity-based recommendations
    if activity_variety < 3:
        recommendations.append({
            'type': 'variety',
            'title': 'Explore More Alumni Activities',
            'description': 'Try different ways to engage with the alumni community.',
            'action': 'Join the alumni forum or attend an event',
            'points': 25
        })
    
    # Industry-specific recommendations
    if industry:
        cursor.execute('''
            SELECT COUNT(*) FROM job_postings 
            WHERE industry = ? AND is_active = 1
        ''', (industry,))
        
        industry_jobs = cursor.fetchone()[0]
        
        if industry_jobs > 0:
            recommendations.append({
                'type': 'career',
                'title': f'Explore {industry} Opportunities',
                'description': f'There are {industry_jobs} active job postings in your industry.',
                'action': 'Check the job board for new opportunities',
                'points': 10
            })
    
    # Mentorship recommendations
    if not is_mentor and graduation_year and graduation_year < (datetime.now().year - 3):
        recommendations.append({
            'type': 'mentorship',
            'title': 'Become a Mentor',
            'description': 'Share your experience with recent graduates and current students.',
            'action': 'Sign up to become a mentor',
            'points': 50
        })
    
    # Donation recommendations
    if not is_donor:
        recommendations.append({
            'type': 'giving',
            'title': 'Support Your Alma Mater',
            'description': 'Make your first donation to support current students and programs.',
            'action': 'Browse active fundraising campaigns',
            'points': 30
        })
    
    # Event recommendations
    cursor.execute('''
        SELECT COUNT(*) FROM alumni_events 
        WHERE event_date > datetime('now') AND registration_required = 1
    ''', ())
    
    upcoming_events = cursor.fetchone()[0]
    
    if upcoming_events > 0:
        recommendations.append({
            'type': 'events',
            'title': 'Attend Upcoming Events',
            'description': f'There are {upcoming_events} upcoming alumni events you can attend.',
            'action': 'Register for an upcoming event',
            'points': 20
        })
    
    # Social recommendations
    cursor.execute('''
        SELECT COUNT(*) FROM networking_connections 
        WHERE requester_id = ? OR recipient_id = ?
    ''', (alumni_id, alumni_id))
    
    connections = cursor.fetchone()[0]
    
    if connections < 5:
        recommendations.append({
            'type': 'networking',
            'title': 'Expand Your Network',
            'description': 'Connect with more alumni in your field or location.',
            'action': 'Search the alumni directory and send connection requests',
            'points': 15
        })
    
    # Display recommendations
    if recommendations:
        print(f"Based on your profile and activity, here are your personalized recommendations:")
        print("-" * 70)
        
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['title']} 🎯")
            print(f"   {rec['description']}")
            print(f"   💡 Action: {rec['action']}")
            print(f"   🏆 Potential Points: {rec['points']}")
            print(f"   Category: {rec['type'].title()}")
            print("-" * 70)
        
        # Option to mark recommendations as completed
        mark_choice = input("\nWould you like to mark any recommendations as completed? (y/n): ").lower()
        if mark_choice == 'y':
            try:
                rec_num = int(input(f"Enter recommendation number (1-{len(recommendations)}): "))
                if 1 <= rec_num <= len(recommendations):
                    selected_rec = recommendations[rec_num - 1]
                    
                    # Award points for following recommendation
                    award_engagement_points(alumni_id, f"recommendation_{selected_rec['type']}", selected_rec['points'])
                    print(f"Great! You've earned {selected_rec['points']} points for following the recommendation!")
                else:
                    print("Invalid recommendation number.")
            except ValueError:
                print("Invalid input.")
    else:
        print("🎉 You're doing great! Keep up your excellent engagement with the alumni community.")
    
    conn.close()

# ENHANCED MAIN MENU

def display_alumni_menu():
    """Display the enhanced alumni system menu with all new features"""
    global auth
    
    # Initialize the enhanced alumni database if not already done
    init_alumni_db()
    
    # Check if user is logged in
    if not auth or not auth.current_user:
        print("You must be logged in to access the alumni system.")
        return
    
    while True:
        print(f"\n🎓 Enhanced Alumni System - Welcome {auth.current_user.get('first_name', 'User')}!")
        print("=" * 70)
        
        # Display menu options based on permissions
        option_num = 1
        option_map = {}
        
        # Core Alumni Management
        print("\n📋 ALUMNI MANAGEMENT")
        if auth.check_permission('manage_alumni'):
            print(f"{option_num}. Register New Alumni")
            option_map[str(option_num)] = "register_alumni"
            option_num += 1
        
        if auth.check_permission('view_alumni') or auth.check_permission('view_own_alumni_profile'):
            print(f"{option_num}. View Alumni Records")
            option_map[str(option_num)] = "view_alumni"
            option_num += 1
        
        if auth.check_permission('manage_alumni') or auth.check_permission('update_own_alumni_profile'):
            print(f"{option_num}. Update Alumni Record")
            option_map[str(option_num)] = "update_alumni"
            option_num += 1
        
        # Alumni Directory & Networking
        print("\n🌐 NETWORKING & DIRECTORY")
        if auth.check_permission('access_alumni_directory'):
            print(f"{option_num}. Alumni Directory & Search")
            option_map[str(option_num)] = "alumni_directory"
            option_num += 1
            
            print(f"{option_num}. Connection Requests")
            option_map[str(option_num)] = "connection_requests"
            option_num += 1
            
            print(f"{option_num}. Business Directory")
            option_map[str(option_num)] = "business_directory"
            option_num += 1
        
        # Communication & Social
        print("\n💬 COMMUNICATION & SOCIAL")
        if auth.check_permission('send_newsletters') or auth.check_permission('access_alumni_directory'):
            if auth.check_permission('send_newsletters'):
                print(f"{option_num}. Create Newsletter")
                option_map[str(option_num)] = "create_newsletter"
                option_num += 1
            
            print(f"{option_num}. Alumni Forum")
            option_map[str(option_num)] = "alumni_forum"
            option_num += 1
            
            print(f"{option_num}. Alumni Stories")
            option_map[str(option_num)] = "alumni_stories"
            option_num += 1
        
        # Events
        print("\n🎉 EVENTS")
        if auth.check_permission('manage_events_advanced'):
            print(f"{option_num}. Create Enhanced Event")
            option_map[str(option_num)] = "create_enhanced_event"
            option_num += 1
            
            print(f"{option_num}. Event Check-In System")
            option_map[str(option_num)] = "event_checkin"
            option_num += 1
        
        if auth.check_permission('manage_events') or auth.check_permission('view_events'):
            print(f"{option_num}. View Alumni Events")
            option_map[str(option_num)] = "view_events"
            option_num += 1
        
        if auth.check_permission('manage_events') or auth.check_permission('register_for_events'):
            print(f"{option_num}. Register for Event")
            option_map[str(option_num)] = "register_for_event"
            option_num += 1
        
        if auth.check_permission('manage_social_features'):
            print(f"{option_num}. Manage Class Reunions")
            option_map[str(option_num)] = "manage_reunions"
            option_num += 1
        
        # Career Services
        print("\n💼 CAREER SERVICES")
        if auth.check_permission('view_job_board'):
            print(f"{option_num}. Job Board")
            option_map[str(option_num)] = "job_board"
            option_num += 1
        
        if auth.check_permission('post_jobs'):
            print(f"{option_num}. Post Job Opportunity")
            option_map[str(option_num)] = "post_job"
            option_num += 1
        
        if auth.check_permission('schedule_career_counseling'):
            print(f"{option_num}. Schedule Career Counseling")
            option_map[str(option_num)] = "career_counseling"
            option_num += 1
        
        # Donations & Fundraising
        print("\n💰 DONATIONS & FUNDRAISING")
        if auth.check_permission('manage_donations') or auth.check_permission('make_donation'):
            print(f"{option_num}. Record Donation")
            option_map[str(option_num)] = "record_donation"
            option_num += 1
        
        if auth.check_permission('manage_donations') or auth.check_permission('view_own_donations'):
            print(f"{option_num}. View Donations")
            option_map[str(option_num)] = "view_donations"
            option_num += 1
        
        if auth.check_permission('manage_campaigns'):
            print(f"{option_num}. Fundraising Campaigns")
            option_map[str(option_num)] = "manage_campaigns"
            option_num += 1
            
            print(f"{option_num}. Donor Recognition")
            option_map[str(option_num)] = "donor_recognition"
            option_num += 1
        
        # Mentorship
        print("\n👥 MENTORSHIP")
        if auth.check_permission('manage_mentorships'):
            print(f"{option_num}. Set Up Mentorship")
            option_map[str(option_num)] = "setup_mentorship"
            option_num += 1
        
        if auth.check_permission('manage_mentorships') or auth.check_permission('view_own_mentorships'):
            print(f"{option_num}. View Mentorships")
            option_map[str(option_num)] = "view_mentorships"
            option_num += 1
        
        if auth.check_permission('manage_ai_features'):
            print(f"{option_num}. Smart Mentorship Matching")
            option_map[str(option_num)] = "smart_matching"
            option_num += 1
        
        # Engagement & Gamification
        print("\n🏆 ENGAGEMENT")
        print(f"{option_num}. View Engagement Leaderboard")
        option_map[str(option_num)] = "leaderboard"
        option_num += 1
        
        print(f"{option_num}. My Badges & Points")
        option_map[str(option_num)] = "my_badges"
        option_num += 1
        
        print(f"{option_num}. Personalized Recommendations")
        option_map[str(option_num)] = "recommendations"
        option_num += 1
        
        # Content & Gallery
        print("\n📸 CONTENT")
        print(f"{option_num}. Photo Gallery")
        option_map[str(option_num)] = "photo_gallery"
        option_num += 1
        
        print(f"{option_num}. Regional Chapters")
        option_map[str(option_num)] = "regional_chapters"
        option_num += 1
        
        # Settings & Admin
        print("\n⚙️  SETTINGS")
        print(f"{option_num}. Directory Privacy Settings")
        option_map[str(option_num)] = "directory_settings"
        option_num += 1
        
        if auth.check_permission('generate_reports'):
            print(f"{option_num}. Generate Alumni Reports")
            option_map[str(option_num)] = "generate_reports"
            option_num += 1
        
        # Return option
        print(f"\n{option_num}. Return to Main Menu")
        
        print("\n" + "=" * 70)
        choice = input("Enter your choice: ")
        
        if choice in option_map:
            action = option_map[choice]
            
            try:
                if action == "register_alumni":
                    register_alumni()
                elif action == "view_alumni":
                    view_alumni()
                elif action == "update_alumni":
                    update_alumni()
                elif action == "alumni_directory":
                    search_alumni_directory()
                elif action == "connection_requests":
                    view_connection_requests()
                elif action == "business_directory":
                    manage_business_directory()
                elif action == "create_newsletter":
                    create_newsletter()
                elif action == "alumni_forum":
                    manage_alumni_forum()
                elif action == "alumni_stories":
                    view_alumni_stories()
                elif action == "create_enhanced_event":
                    create_enhanced_event()
                elif action == "event_checkin":
                    event_check_in_system()
                elif action == "view_events":
                    view_events()
                elif action == "register_for_event":
                    register_for_event()
                elif action == "manage_reunions":
                    manage_class_reunions()
                elif action == "job_board":
                    view_job_board()
                elif action == "post_job":
                    post_job_opportunity()
                elif action == "career_counseling":
                    schedule_career_counseling()
                elif action == "record_donation":
                    record_donation()
                elif action == "view_donations":
                    view_donations()
                elif action == "manage_campaigns":
                    view_fundraising_campaigns()
                elif action == "donor_recognition":
                    manage_donor_recognition()
                elif action == "setup_mentorship":
                    setup_mentorship()
                elif action == "view_mentorships":
                    view_mentorships()
                elif action == "smart_matching":
                    smart_mentorship_matching()
                elif action == "leaderboard":
                    view_engagement_leaderboard()
                elif action == "my_badges":
                    view_my_badges()
                elif action == "recommendations":
                    generate_engagement_recommendations()
                elif action == "photo_gallery":
                    manage_photo_gallery()
                elif action == "regional_chapters":
                    manage_regional_chapters()
                elif action == "directory_settings":
                    setup_alumni_directory()
                elif action == "generate_reports":
                    generate_alumni_report()
                    
            except Exception as e:
                print(f"An error occurred: {e}")
                print("Please try again or contact support.")
                
        elif choice == str(option_num):
            return
        else:
            print("Invalid choice. Please try again.")


# GUI Launcher using factory pattern
try:
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_alumni_relations_gui = create_gui_launcher(
        title="Alumni Relations & Engagement",
        description="""Comprehensive alumni management with profiles, donations, events, and engagement tracking.

Features:
• Alumni profiles & directories
• Donation management
• Giving campaigns
• Alumni events & reunions
• Registration & RSVP tracking
• Achievement recognition
• Regional chapters
• Mentorship programs
• Career networking
• Photo galleries
• Communication tools
• Engagement analytics
• Smart recommendations
• Leaderboards & badges
• Event QR codes
• Payment processing
• LinkedIn integration
• SMS notifications""",
        cli_instruction="Use CLI: Alumni Relations & Engagement"
    )
except ImportError:
    # Fallback if factory not available
    def launch_alumni_relations_gui(root, auth):
        """Launch the Alumni Relations & Engagement GUI (same as Alumni Management)"""
        try:
            from university_system.modules.domain.student_affairs.gui.alumni import launch_alumni_gui
            launch_alumni_gui(auth)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to launch Alumni GUI: {str(e)}")


# Alias for consistency with refactored naming
display_alumni_relations_menu = display_alumni_menu


# Export public API
__all__ = [
    'display_alumni_menu',
    'display_alumni_relations_menu',
    'launch_alumni_relations_gui',
    'setup_alumni_permissions',
]


if __name__ == '__main__':
    setup_alumni_permissions()