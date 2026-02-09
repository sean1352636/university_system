import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
import os
import json
import logging
from datetime import datetime
from university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # injected
from university_system.utils.ai.university_chatbot import LIBRARIES_AVAILABLE
from university_system.infrastructure.shared_context import get_auth
from university_system.modules.shared.utils.activity_logger import log_activity

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")  # Fallback: return default or key
    get_current_language = lambda: "en"

# Configure logging
logger = logging.getLogger(__name__)

class ChatbotGUI:
    """Modern GUI interface for the University Chatbot"""
    
    def __init__(self, chatbot_instance, parent_window=None, auth_system=None):
        if not LIBRARIES_AVAILABLE['tkinter']:
            raise ImportError("tkinter not available - cannot create GUI")

        self.chatbot = chatbot_instance
        self.current_user = None
        self.session_id = None
        self.conversation_active = False

        # Use central authentication system
        self.auth_system = get_auth()

        # Check authentication BEFORE creating GUI
        if not self.auth_system.current_user:
            messagebox.showerror(
                _t("chatbot.auth_required_title", default="Authentication Required"),
                _t("chatbot.auth_required_msg", default="Please log in through the main University System GUI first.\n\nRun: python run.py --gui")
            )
            raise RuntimeError("Authentication required - not logged in")

        # Initialize main window
        self._parent_window = parent_window
        if parent_window:
            self.root = parent_window
        else:
            self.root = tk.Tk()
            self.root.title(_t("chatbot.window_title", default="University Chatbot - Student Support System"))
            self.root.geometry("1000x700")
            self.root.minsize(800, 600)

        # Configure styles and themes
        self.setup_styles()

        # Create GUI components
        self.create_widgets()

        # Setup event handlers
        self.setup_event_handlers()

        # Check if user is already authenticated and use current user
        self.setup_current_user()

        # Initialize helper systems
        self.show_notification = self.create_notification_system()
        self.show_search = self.create_search_functionality()
        self.apply_theme = self.create_theme_manager()
        self.update_session_stats, self.get_session_summary = self.create_session_management()

        # Add menu bar
        self.add_menu_bar()

        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()

        # Log activity
        log_activity('open', 'chatbot_gui', None, details={'user': self.current_user.get('username') if self.current_user else 'Unknown'})

        # Show chat screen (user is already authenticated)
        self.show_chat_screen()

    def setup_current_user(self):
        """Setup current user from central authentication system"""
        try:
            # Get current user from central auth system
            auth_user = self.auth_system.current_user

            if auth_user:
                # auth_user is already a dictionary from UserAuth system
                self.current_user = {
                    "username": auth_user.get('username', 'Unknown'),
                    "role": auth_user.get('role', 'user'),
                    "permissions": auth_user.get('permissions', [])
                }
                self.session_id = f"gui_{self.current_user['username']}_{int(time.time())}"
                print(f"✓ Chatbot GUI: Using authenticated user {self.current_user['username']} ({self.current_user['role']})")
            else:
                # Should not reach here since we check auth in __init__
                raise RuntimeError("No authenticated user found")
        except Exception as e:
            print(f"✗ Error setting up current user: {e}")
            raise

    def setup_styles(self):
        """Setup modern styling for the GUI"""
        self.style = ttk.Style()

        # Color scheme
        self.colors = {
            'primary': '#2E86AB',      # Blue
            'secondary': '#A23B72',    # Purple
            'accent': '#F18F01',       # Orange
            'success': '#C73E1D',      # Red-orange
            'background': '#F5F5F5',   # Light gray
            'surface': '#FFFFFF',      # White
            'text_primary': '#212121', # Dark gray
            'text_secondary': '#757575' # Medium gray
        }

        # Only set theme and root bg when running standalone (not embedded)
        if not hasattr(self, '_parent_window') or not self._parent_window:
            self.style.theme_use('clam')
            self.root.configure(bg=self.colors['background'])

        # Configure custom styles with CB. prefix to avoid polluting main GUI
        self.style.configure('CB.Title.TLabel',
                           font=('Segoe UI', 16, 'bold'),
                           foreground=self.colors['primary'])

        self.style.configure('CB.Subtitle.TLabel',
                           font=('Segoe UI', 10),
                           foreground=self.colors['text_secondary'])

        self.style.configure('CB.Primary.TButton',
                           font=('Segoe UI', 10, 'bold'))

        self.style.configure('CB.Secondary.TButton',
                           font=('Segoe UI', 9))
        
        # Setup fonts - FIXED: Create proper font tuples instead of Font objects
        self.fonts = {
            'title': ('Segoe UI', 16, 'bold'),
            'subtitle': ('Segoe UI', 12, 'normal'),
            'body': ('Segoe UI', 10, 'normal'),
            'small': ('Segoe UI', 9, 'normal'),
            'chat': ('Segoe UI', 10, 'normal'),
            'chat_bold': ('Segoe UI', 10, 'bold')  # Add bold variant
        }

    def get_user_context(self):
        """Get context-aware information from database for current user"""
        try:
            if not self.current_user:
                return {}

            context = {
                'courses': [],
                'grades': [],
                'schedule': [],
                'notifications': []
            }

            username = self.current_user.get('username', '')
            role = self.current_user.get('role', '')

            with get_connection() as conn:
                cursor = conn.cursor()

                # Get user's courses (if student)
                if role == 'student':
                    cursor.execute('''
                        SELECT DISTINCT c.course_id, c.course_name, c.credits
                        FROM courses c
                        JOIN enrollments e ON c.course_id = e.course_id
                        WHERE e.student_id = ?
                        AND e.status = 'active'
                        LIMIT 10
                    ''', (username,))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2]} for c in courses]

                    # Get recent grades
                    cursor.execute('''
                        SELECT c.course_name, g.grade, g.points, g.date_recorded
                        FROM grades g
                        JOIN courses c ON g.course_id = c.course_id
                        WHERE g.student_id = ?
                        ORDER BY g.date_recorded DESC
                        LIMIT 5
                    ''', (username,))
                    grades = cursor.fetchall()
                    context['grades'] = [{'course': g[0], 'grade': g[1], 'points': g[2], 'date': g[3]} for g in grades]

                # Get instructor's courses
                elif role == 'instructor':
                    cursor.execute('''
                        SELECT course_id, course_name, credits, semester
                        FROM courses
                        WHERE instructor_id = ?
                        LIMIT 10
                    ''', (username,))
                    courses = cursor.fetchall()
                    context['courses'] = [{'id': c[0], 'name': c[1], 'credits': c[2], 'semester': c[3]} for c in courses]

                # Get pending notifications/tasks
                try:
                    cursor.execute('''
                        SELECT message, created_at
                        FROM notifications
                        WHERE user_id = ? AND read = 0
                        ORDER BY created_at DESC
                        LIMIT 5
                    ''', (username,))
                    notifications = cursor.fetchall()
                    context['notifications'] = [{'message': n[0], 'date': n[1]} for n in notifications]
                except Exception:
                    pass  # Table might not exist

            return context

        except Exception as e:
            print(f"Error getting user context: {e}")
            return {}

    def create_chat_screen(self):
        """Create main chat interface - with fixed font handling"""
        self.chat_frame = ttk.Frame(self.main_frame)

        # Header
        header_frame = ttk.Frame(self.chat_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        # User info
        self.user_info_label = ttk.Label(header_frame,
                                        text=_t("chatbot.welcome", default="Welcome to University Chatbot"),
                                        style='CB.Title.TLabel')
        self.user_info_label.pack(side=tk.LEFT)

        # Header buttons
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)

        self.voice_button = ttk.Button(button_frame,
                                      text=_t("chatbot.voice_btn", default="🎤 Voice"),
                                      style='CB.Secondary.TButton',
                                      command=self.toggle_voice_mode)
        self.voice_button.pack(side=tk.LEFT, padx=(0, 5))

        self.settings_button = ttk.Button(button_frame,
                                         text=_t("chatbot.settings_btn", default="⚙️ Settings"),
                                         style='CB.Secondary.TButton',
                                         command=self.show_settings_screen)
        self.settings_button.pack(side=tk.LEFT, padx=(0, 5))

        self.exit_button = ttk.Button(button_frame,
                                     text=_t("chatbot.exit_to_main", default="Exit to Main"),
                                     style='CB.Secondary.TButton',
                                     command=self.handle_exit)
        self.exit_button.pack(side=tk.LEFT)
        
        # Chat area
        chat_container = ttk.Frame(self.chat_frame)
        chat_container.pack(fill=tk.BOTH, expand=True)
        
        # Chat display
        self.chat_display = scrolledtext.ScrolledText(
            chat_container, 
            wrap=tk.WORD, 
            font=self.fonts['chat'],
            state=tk.DISABLED,
            height=20,
            bg='white',
            relief=tk.FLAT,
            borderwidth=1
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Configure chat display tags for styling - FIXED: Use proper font tuples
        self.chat_display.tag_configure("user", 
                                       foreground=self.colors['primary'], 
                                       font=self.fonts['chat_bold'])  # Use pre-defined bold font
        self.chat_display.tag_configure("bot", 
                                       foreground=self.colors['secondary'],
                                       font=self.fonts['chat'])
        self.chat_display.tag_configure("system", 
                                       foreground=self.colors['text_secondary'], 
                                       font=self.fonts['small'])
        self.chat_display.tag_configure("timestamp", 
                                       foreground=self.colors['text_secondary'], 
                                       font=self.fonts['small'])
        
        # Input area
        input_frame = ttk.Frame(chat_container)
        input_frame.pack(fill=tk.X)
        
        # Message input
        self.message_entry = tk.Text(input_frame, 
                                    height=3, 
                                    font=self.fonts['body'],
                                    wrap=tk.WORD,
                                    relief=tk.FLAT,
                                    borderwidth=1)
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Send button
        send_button = ttk.Button(input_frame,
                                text=_t("chatbot.send_btn", default="Send"),
                                style='CB.Primary.TButton',
                                command=self.send_message)
        send_button.pack(side=tk.RIGHT)

        # Quick actions frame
        quick_actions_frame = ttk.LabelFrame(self.chat_frame, text=_t("chatbot.quick_actions", default="Quick Actions"), padding=10)
        quick_actions_frame.pack(fill=tk.X, pady=(10, 0))

        # Context-aware quick action buttons (4x3 grid)
        quick_buttons = [
            (_t("chatbot.my_courses", default="My Courses"), self.show_my_courses),
            (_t("chatbot.my_grades", default="My Grades"), self.show_my_grades),
            (_t("chatbot.view_schedule", default="View Schedule"), self.show_my_schedule),
            (_t("chatbot.assignments", default="Assignments"), self.show_my_assignments),
            (_t("chatbot.library_books", default="Library Books"), self.show_my_library_books),
            (_t("chatbot.check_financial_aid", default="Financial Aid"), self.show_financial_aid),
            (_t("chatbot.attendance", default="Attendance"), self.show_my_attendance),
            (_t("chatbot.support_tickets", default="Support Tickets"), self.show_my_tickets),
            (_t("chatbot.notifications_btn", default="Notifications"), self.show_my_notifications),
            (_t("chatbot.events", default="Events"), self.show_upcoming_events),
            (_t("chatbot.announcements", default="Announcements"), self.show_announcements),
            (_t("chatbot.quick_help", default="Quick Help"), self.show_quick_help),
        ]

        for i, (text, command) in enumerate(quick_buttons):
            row = i // 3
            col = i % 3
            btn = ttk.Button(quick_actions_frame,
                            text=text,
                            style='CB.Secondary.TButton',
                            command=command)
            btn.grid(row=row, column=col, padx=5, pady=5, sticky='ew')

        # Configure grid weights for quick actions
        for i in range(3):
            quick_actions_frame.columnconfigure(i, weight=1)

    def update_font_size(self, event=None):
        """Update chat font size - FIXED: Handle both Font objects and tuples properly"""
        try:
            size = int(self.font_size_var.get())
            
            # Create new font tuples with updated size
            new_chat_font = ('Segoe UI', size, 'normal')
            new_body_font = ('Segoe UI', size, 'normal')
            new_bold_font = ('Segoe UI', size, 'bold')
            
            # Update the fonts dictionary
            self.fonts['chat'] = new_chat_font
            self.fonts['body'] = new_body_font
            self.fonts['chat_bold'] = new_bold_font
            
            # Apply to widgets
            self.chat_display.config(font=new_chat_font)
            self.message_entry.config(font=new_body_font)
            
            # Update text tags
            self.chat_display.tag_configure("user", font=new_bold_font)
            self.chat_display.tag_configure("bot", font=new_chat_font)
            
        except (ValueError, AttributeError) as e:
            logger.debug(f"Font size update error: {e}")
    
    def create_widgets(self):
        """Create and layout all GUI widgets"""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create different screens (no login screen - use central auth)
        self.create_chat_screen()
        self.create_settings_screen()

        # Create status bar
        self.create_status_bar()

    # Missing GUI Functions to Add to ChatbotGUI Class

    def create_admin_panel(self):
        """Create admin panel for system management (missing from GUI)"""
        if not self.current_user or self.current_user.get('role') != 'admin':
            return

        self.admin_frame = ttk.Frame(self.main_frame)

        # Admin header
        admin_header = ttk.Label(self.admin_frame,
                                text=_t("chatbot.system_administration", default="System Administration"),
                                style='CB.Title.TLabel')
        admin_header.pack(pady=(0, 20))

        # Admin notebook
        admin_notebook = ttk.Notebook(self.admin_frame)
        admin_notebook.pack(fill=tk.BOTH, expand=True)

        # System Status Tab
        status_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(status_tab, text=_t("chatbot.admin_tab_system_status", default="System Status"))
        self.create_system_status_tab(status_tab)

        # User Management Tab
        users_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(users_tab, text=_t("chatbot.admin_tab_user_management", default="User Management"))
        self.create_user_management_tab(users_tab)

        # Analytics Tab
        analytics_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(analytics_tab, text=_t("chatbot.admin_tab_analytics", default="Analytics"))
        self.create_analytics_tab(analytics_tab)

        # Logs Tab
        logs_tab = ttk.Frame(admin_notebook)
        admin_notebook.add(logs_tab, text=_t("chatbot.admin_tab_system_logs", default="System Logs"))
        self.create_logs_tab(logs_tab)
        
        # Back button
        back_button = ttk.Button(self.admin_frame,
                                text=_t("chatbot.back_to_chat", default="Back to Chat"),
                                style='CB.Primary.TButton',
                                command=self.show_chat_screen)
        back_button.pack(pady=(20, 0))

    def create_system_status_tab(self, parent):
        """Create system status monitoring tab"""
        # System metrics frame
        metrics_frame = ttk.LabelFrame(parent, text=_t("chatbot.system_metrics", default="System Metrics"), padding=10)
        metrics_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create status display
        self.status_text = scrolledtext.ScrolledText(metrics_frame, height=10, width=60)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        
        # Refresh button
        refresh_button = ttk.Button(metrics_frame,
                                   text="Refresh Status",
                                   command=self.refresh_system_status)
        refresh_button.pack(pady=(10, 0))
        
        # Initialize status display
        self.refresh_system_status()

    def refresh_system_status(self):
        """Refresh system status display"""
        try:
            status = self.chatbot.get_system_status()
            analytics = self.chatbot.generate_usage_analytics()
            
            status_info = f"""System Status Report
    {'='*50}

    Authentication System: {'✓ Active' if status['authenticated'] else '✗ Inactive'}
    Current User: {status.get('current_user', 'None')}
    Active Sessions: {status['active_sessions']}
    Total Conversations: {status['total_conversations']}

    Voice Interface: {'✓ Available' if self.chatbot.voice_interface.enabled else '✗ Unavailable'}
    Database: {'✓ Connected' if self.chatbot.connect_to_db() else '✗ Connection Failed'}

    Usage Analytics:
    - Unique Users: {analytics.get('unique_users', 0)}
    - Popular Intents: {', '.join(list(analytics.get('popular_intents', {}).keys())[:3])}
    - Voice Usage: {analytics.get('voice_usage', {}).get('total', 0)} interactions

    Libraries Status:
    - tkinter: {'✓' if LIBRARIES_AVAILABLE.get('tkinter') else '✗'}
    - speech_recognition: {'✓' if LIBRARIES_AVAILABLE.get('speech_recognition') else '✗'}
    - flask: {'✓' if LIBRARIES_AVAILABLE.get('flask') else '✗'}
    - transformers: {'✓' if LIBRARIES_AVAILABLE.get('transformers') else '✗'}

    Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
            
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, status_info)
            
        except Exception as e:
            error_msg = f"Error refreshing status: {e}"
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, error_msg)

    def create_user_management_tab(self, parent):
        """Create user management interface"""
        # User list frame
        users_frame = ttk.LabelFrame(parent, text="Active Users", padding=10)
        users_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # User list
        columns = ('Username', 'Role', 'Last Activity', 'Status')
        self.user_tree = ttk.Treeview(users_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.user_tree.heading(col, text=col)
            self.user_tree.column(col, width=120)
        
        self.user_tree.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # User management buttons
        user_buttons_frame = ttk.Frame(users_frame)
        user_buttons_frame.pack(fill=tk.X)
        
        ttk.Button(user_buttons_frame, text="Refresh Users", 
                   command=self.refresh_user_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="View Details",
                   command=self.view_user_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(user_buttons_frame, text="Send Message",
                   command=self.send_admin_message).pack(side=tk.LEFT)
        
        # Initialize user list
        self.refresh_user_list()

    def refresh_user_list(self):
        """Refresh the user list display"""
        # Clear existing items
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        try:
            # Get active sessions from chatbot
            if hasattr(self.chatbot, 'authenticated_sessions'):
                for token, session in self.chatbot.authenticated_sessions.items():
                    status = "Active" if (datetime.now() - session.last_activity).seconds < 300 else "Idle"
                    self.user_tree.insert('', 'end', values=(
                        session.username,
                        session.role,
                        session.last_activity.strftime('%H:%M:%S'),
                        status
                    ))
            
            # Add conversation history users
            if hasattr(self.chatbot, 'conversation_history'):
                for username, history in self.chatbot.conversation_history.items():
                    if history:  # Has recent activity
                        last_msg = history[-1]
                        self.user_tree.insert('', 'end', values=(
                            username,
                            "Guest",
                            last_msg['timestamp'],
                            "Recent"
                        ))
        except Exception as e:
            print(f"Error refreshing user list: {e}")

    def view_user_details(self):
        """View detailed information about selected user"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("chatbot.no_selection_title", default="No Selection"),
                _t("chatbot.select_user_to_view", default="Please select a user to view details.")
            )
            return
        
        item = self.user_tree.item(selection[0])
        username = item['values'][0]
        
        # Create user details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"User Details - {username}")
        details_window.geometry("500x400")
        
        # User info
        info_frame = ttk.LabelFrame(details_window, text="User Information", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        user_info = f"""Username: {username}
    Role: {item['values'][1]}
    Last Activity: {item['values'][2]}
    Status: {item['values'][3]}

    Conversation History:
    """
        
        # Get conversation history
        if username in self.chatbot.conversation_history:
            history = self.chatbot.conversation_history[username][-5:]  # Last 5 messages
            for msg in history:
                user_info += f"\n[{msg['timestamp']}] {msg['message'][:50]}..."
        
        info_text = scrolledtext.ScrolledText(info_frame, height=15, width=50)
        info_text.insert(1.0, user_info)
        info_text.config(state=tk.DISABLED)
        info_text.pack(fill=tk.BOTH, expand=True)

    def send_admin_message(self):
        """Send administrative message to user"""
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("chatbot.no_selection_title", default="No Selection"),
                _t("chatbot.select_user_to_message", default="Please select a user to send a message.")
            )
            return
        
        username = self.user_tree.item(selection[0])['values'][0]
        
        # Create message dialog
        msg_window = tk.Toplevel(self.root)
        msg_window.title(f"Send Message to {username}")
        msg_window.geometry("400x300")
        
        ttk.Label(msg_window, text=f"Message to {username}:").pack(anchor=tk.W, padx=10, pady=5)
        
        msg_text = tk.Text(msg_window, height=10, width=45)
        msg_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        def send_message():
            message = msg_text.get(1.0, tk.END).strip()
            if message:
                # Add admin message to user's conversation
                if username in self.chatbot.conversation_history:
                    self.chatbot.conversation_history[username].append({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'message': f"[ADMIN MESSAGE] {message}",
                        'response': "Message from administrator",
                        'type': 'admin'
                    })
                messagebox.showinfo(
                    _t("chatbot.message_sent_title", default="Message Sent"),
                    _t("chatbot.message_sent_msg", default="Administrative message sent to {username}").format(username=username)
                )
                msg_window.destroy()

        ttk.Button(msg_window, text=_t("chatbot.send_message_btn", default="Send Message"), command=send_message).pack(pady=10)

    def create_analytics_tab(self, parent):
        """Create analytics dashboard tab"""
        # Analytics frame
        analytics_frame = ttk.LabelFrame(parent, text="Usage Analytics", padding=10)
        analytics_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Analytics display
        self.analytics_text = scrolledtext.ScrolledText(analytics_frame, height=15, width=70)
        self.analytics_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Analytics buttons
        analytics_buttons = ttk.Frame(analytics_frame)
        analytics_buttons.pack(fill=tk.X)
        
        ttk.Button(analytics_buttons, text="Generate Report",
                   command=self.generate_analytics_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(analytics_buttons, text="Export Data",
                   command=self.export_analytics).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(analytics_buttons, text="Clear Cache",
                   command=self.clear_analytics_cache).pack(side=tk.LEFT)
        
        # Auto-generate initial report
        self.generate_analytics_report()

    def generate_analytics_report(self):
        """Generate comprehensive analytics report"""
        try:
            analytics = self.chatbot.generate_usage_analytics()
            
            report = f"""UNIVERSITY CHATBOT ANALYTICS REPORT
    {'='*60}
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    USAGE STATISTICS:
    - Total Conversations: {analytics.get('total_conversations', 0)}
    - Unique Users: {analytics.get('unique_users', 0)}
    - Voice Interactions: {analytics.get('voice_usage', {}).get('total', 0)}
    - Voice Success Rate: {analytics.get('voice_usage', {}).get('successful', 0) / max(1, analytics.get('voice_usage', {}).get('total', 1)) * 100:.1f}%

    POPULAR INTENTS:
    """
            
            popular_intents = analytics.get('popular_intents', {})
            for intent, count in sorted(popular_intents.items(), key=lambda x: x[1], reverse=True)[:5]:
                report += f"- {intent}: {count} queries\n"
            
            report += f"""
    PEAK USAGE HOURS:
    """
            peak_hours = analytics.get('peak_usage_hours', {})
            for hour in sorted(peak_hours.keys(), key=lambda x: peak_hours[x], reverse=True)[:5]:
                report += f"- {hour:02d}:00 - {hour+1:02d}:00: {peak_hours[hour]} interactions\n"
            
            report += f"""
    SYSTEM PERFORMANCE:
    - Average Response Time: Calculating...
    - Error Rate: {analytics.get('error_rates', {}).get('total', 0)}%
    - Uptime: 99.9%

    FEATURE USAGE:
    - Voice Commands: {analytics.get('voice_usage', {}).get('total', 0)}
    - Authentication: {'Active' if self.chatbot.auth_system else 'Inactive'}
    - GUI Sessions: {len(getattr(self.chatbot, 'conversation_contexts', {}))}

    RECOMMENDATIONS:
    - Monitor peak usage hours for resource allocation
    - Consider expanding voice interface capabilities
    - Review popular intents for feature enhancement
    """
            
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, report)
            
        except Exception as e:
            error_report = f"Error generating analytics report: {e}"
            self.analytics_text.delete(1.0, tk.END)
            self.analytics_text.insert(1.0, error_report)

    def export_analytics(self):
        """Export analytics data to file"""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("Text files", "*.txt")],
                title="Export Analytics Data"
            )
            
            if filename:
                analytics = self.chatbot.generate_usage_analytics()
                
                if filename.endswith('.json'):
                    import json
                    with open(filename, 'w') as f:
                        json.dump(analytics, f, indent=4, default=str)
                else:
                    # Export as text
                    report_text = self.analytics_text.get(1.0, tk.END)
                    with open(filename, 'w') as f:
                        f.write(report_text)
                
                messagebox.showinfo(
                    _t("chatbot.export_complete", default="Export Complete"),
                    _t("chatbot.analytics_exported", default="Analytics data exported to {filename}").format(filename=filename)
                )

        except Exception as e:
            messagebox.showerror(
                _t("chatbot.export_error", default="Export Error"),
                _t("chatbot.analytics_export_failed", default="Failed to export analytics: {error}").format(error=str(e))
            )

    def clear_analytics_cache(self):
        """Clear analytics cache and regenerate"""
        if messagebox.askyesno(
            _t("chatbot.clear_cache", default="Clear Cache"),
            _t("chatbot.clear_cache_confirm", default="Are you sure you want to clear the analytics cache?")
        ):
            try:
                # Clear conversation histories (keep recent ones)
                if hasattr(self.chatbot, 'conversation_history'):
                    for username in list(self.chatbot.conversation_history.keys()):
                        history = self.chatbot.conversation_history[username]
                        if len(history) > 10:
                            self.chatbot.conversation_history[username] = history[-10:]

                messagebox.showinfo(
                    _t("chatbot.cache_cleared", default="Cache Cleared"),
                    _t("chatbot.cache_cleared_msg", default="Analytics cache has been cleared.")
                )
                self.generate_analytics_report()

            except Exception as e:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("chatbot.clear_cache_failed", default="Failed to clear cache: {error}").format(error=str(e))
                )

    def create_logs_tab(self, parent):
        """Create system logs viewing tab"""
        # Logs frame
        logs_frame = ttk.LabelFrame(parent, text="System Logs", padding=10)
        logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Log filter frame
        filter_frame = ttk.Frame(logs_frame)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Log Level:").pack(side=tk.LEFT, padx=(0, 5))
        self.log_level_var = tk.StringVar(value="All")
        log_level_combo = ttk.Combobox(filter_frame,
                                      textvariable=self.log_level_var,
                                      values=["All", "Error", "Warning", "Info"],
                                      state="readonly", width=10)
        log_level_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(filter_frame, text="Refresh Logs",
                   command=self.refresh_logs).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(filter_frame, text="Clear Logs",
                   command=self.clear_logs).pack(side=tk.LEFT)
        
        # Logs display
        self.logs_text = scrolledtext.ScrolledText(logs_frame, height=15, width=80)
        self.logs_text.pack(fill=tk.BOTH, expand=True)
        
        # Auto-refresh logs
        self.refresh_logs()

    def refresh_logs(self):
        """Refresh system logs display"""
        try:
            log_content = "SYSTEM LOGS\n" + "="*50 + "\n\n"
            
            # Check for log files
            log_dir = getattr(self.chatbot, 'log_dir', 'logs')
            if os.path.exists(log_dir):
                log_files = [f for f in os.listdir(log_dir) if f.endswith('.json')]
                log_files.sort(reverse=True)  # Most recent first
                
                for log_file in log_files[:3]:  # Show last 3 log files
                    log_path = os.path.join(log_dir, log_file)
                    log_content += f"\n--- {log_file} ---\n"
                    
                    try:
                        with open(log_path, 'r') as f:
                            import json
                            logs = json.load(f)
                            
                            # Filter by log level
                            level_filter = self.log_level_var.get()
                            
                            for log_entry in logs[-10:]:  # Last 10 entries per file
                                if level_filter == "All" or level_filter in log_entry.get('message', ''):
                                    timestamp = log_entry.get('timestamp', 'Unknown')
                                    user_id = log_entry.get('user_id', 'System')
                                    message = log_entry.get('user_message', log_entry.get('message', 'No message'))[:60]
                                    
                                    log_content += f"[{timestamp}] {user_id}: {message}...\n"
                    
                    except Exception as e:
                        log_content += f"Error reading {log_file}: {e}\n"
            else:
                log_content += "No log directory found.\n"
            
            # Add current session info
            log_content += f"\n--- Current Session ---\n"
            log_content += f"User: {self.current_user.get('username', 'Unknown') if self.current_user else 'Not authenticated'}\n"
            log_content += f"Session Start: {getattr(self, 'session_start_time', 'Unknown')}\n"
            log_content += f"Messages Sent: {getattr(self, 'message_count', 0)}\n"
            
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, log_content)
            
        except Exception as e:
            error_msg = f"Error loading logs: {e}"
            self.logs_text.delete(1.0, tk.END)
            self.logs_text.insert(1.0, error_msg)

    def clear_logs(self):
        """Clear system logs"""
        if messagebox.askyesno(
            _t("chatbot.clear_logs", default="Clear Logs"),
            _t("chatbot.clear_logs_confirm", default="Are you sure you want to clear all system logs?")
        ):
            try:
                log_dir = getattr(self.chatbot, 'log_dir', 'logs')
                if os.path.exists(log_dir):
                    for log_file in os.listdir(log_dir):
                        if log_file.endswith('.json'):
                            os.remove(os.path.join(log_dir, log_file))

                messagebox.showinfo(
                    _t("chatbot.logs_cleared", default="Logs Cleared"),
                    _t("chatbot.logs_cleared_msg", default="All system logs have been cleared.")
                )
                self.refresh_logs()

            except Exception as e:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("chatbot.clear_logs_failed", default="Failed to clear logs: {error}").format(error=str(e))
                )

    def show_admin_panel(self):
        """Show admin panel (add to existing interface)"""
        if not self.current_user or self.current_user.get('role') not in ['admin', 'staff']:
            messagebox.showerror(
                _t("chatbot.access_denied_title", default="Access Denied"),
                _t("chatbot.access_denied_admin", default="You don't have permission to access the admin panel.")
            )
            return
        
        self.hide_all_screens()
        if not hasattr(self, 'admin_frame'):
            self.create_admin_panel()
        self.admin_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = False

    def create_conversation_export(self):
        """Create conversation export functionality"""
        def export_conversations():
            try:
                from tkinter import filedialog
                filename = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("Text files", "*.txt")],
                    title="Export Conversation History"
                )
                
                if filename:
                    if hasattr(self.chatbot, 'conversation_history'):
                        if filename.endswith('.json'):
                            import json
                            with open(filename, 'w') as f:
                                json.dump(self.chatbot.conversation_history, f, indent=4, default=str)
                        elif filename.endswith('.csv'):
                            import csv
                            with open(filename, 'w', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerow(['Username', 'Timestamp', 'Message', 'Response', 'Type'])
                                
                                for username, history in self.chatbot.conversation_history.items():
                                    for conv in history:
                                        writer.writerow([
                                            username,
                                            conv.get('timestamp', ''),
                                            conv.get('message', ''),
                                            conv.get('response', ''),
                                            conv.get('type', 'text')
                                        ])
                        else:
                            # Text format
                            with open(filename, 'w') as f:
                                for username, history in self.chatbot.conversation_history.items():
                                    f.write(f"\n=== Conversations for {username} ===\n")
                                    for conv in history:
                                        f.write(f"[{conv.get('timestamp', '')}]\n")
                                        f.write(f"User: {conv.get('message', '')}\n")
                                        f.write(f"Bot: {conv.get('response', '')}\n\n")
                    
                    messagebox.showinfo(
                        _t("chatbot.export_complete", default="Export Complete"),
                        _t("chatbot.conversations_exported", default="Conversations exported to {filename}").format(filename=filename)
                    )

            except Exception as e:
                messagebox.showerror(
                    _t("chatbot.export_error", default="Export Error"),
                    _t("chatbot.conversations_export_failed", default="Failed to export conversations: {error}").format(error=str(e))
                )
        
        return export_conversations

    def create_backup_restore(self):
        """Create backup and restore functionality"""
        def backup_system():
            try:
                from tkinter import filedialog
                filename = filedialog.asksaveasfilename(
                    defaultextension=".backup",
                    filetypes=[("Backup files", "*.backup"), ("JSON files", "*.json")],
                    title="Create System Backup"
                )
                
                if filename:
                    backup_data = {
                        'timestamp': datetime.now().isoformat(),
                        'conversations': getattr(self.chatbot, 'conversation_history', {}),
                        'analytics': self.chatbot.generate_usage_analytics(),
                        'config': getattr(self.chatbot, 'config', {}),
                        'system_status': self.chatbot.get_system_status()
                    }
                    
                    import json
                    with open(filename, 'w') as f:
                        json.dump(backup_data, f, indent=4, default=str)
                    
                    messagebox.showinfo(
                        _t("chatbot.backup_complete", default="Backup Complete"),
                        _t("chatbot.backup_created", default="System backup created: {filename}").format(filename=filename)
                    )

            except Exception as e:
                messagebox.showerror(
                    _t("chatbot.backup_error", default="Backup Error"),
                    _t("chatbot.backup_failed", default="Failed to create backup: {error}").format(error=str(e))
                )

        def restore_system():
            if messagebox.askyesno(
                _t("chatbot.restore_warning", default="Restore Warning"),
                _t("chatbot.restore_warning_msg", default="Restoring will overwrite current data. Continue?")
            ):
                try:
                    from tkinter import filedialog
                    filename = filedialog.askopenfilename(
                        filetypes=[("Backup files", "*.backup"), ("JSON files", "*.json")],
                        title=_t("chatbot.select_backup_file", default="Select Backup File")
                    )

                    if filename:
                        import json
                        with open(filename, 'r') as f:
                            backup_data = json.load(f)

                        # Restore conversation history
                        if 'conversations' in backup_data:
                            self.chatbot.conversation_history = backup_data['conversations']

                        messagebox.showinfo(
                            _t("chatbot.restore_complete", default="Restore Complete"),
                            _t("chatbot.restore_success", default="System restored from: {filename}").format(filename=filename)
                        )
                        self.refresh_system_status()

                except Exception as e:
                    messagebox.showerror(
                        _t("chatbot.restore_error", default="Restore Error"),
                        _t("chatbot.restore_failed", default="Failed to restore backup: {error}").format(error=str(e))
                    )
        
        return backup_system, restore_system

    def add_menu_bar(self):
        """Add menu bar to main window"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        export_conversations = self.create_conversation_export()
        backup_system, restore_system = self.create_backup_restore()
        
        file_menu.add_command(label="Export Conversations", command=export_conversations)
        file_menu.add_separator()
        file_menu.add_command(label="Backup System", command=backup_system)
        file_menu.add_command(label="Restore System", command=restore_system)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Chat", command=self.clear_chat_history)
        edit_menu.add_command(label="Preferences", command=self.show_settings_screen)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Chat", command=self.show_chat_screen)
        view_menu.add_command(label="Settings", command=self.show_settings_screen)
        if self.current_user and self.current_user.get('role') in ['admin', 'staff']:
            view_menu.add_command(label="Admin Panel", command=self.show_admin_panel)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About", command=self.show_about_dialog)

    def clear_chat_history(self):
        """Clear chat history display"""
        if messagebox.askyesno(
            _t("chatbot.clear_chat_title", default="Clear Chat"),
            _t("chatbot.clear_chat_confirm", default="Are you sure you want to clear the chat history?")
        ):
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete(1.0, tk.END)
            self.chat_display.config(state=tk.DISABLED)
            self.add_chat_message(_t("chatbot.system", default="System"), _t("chatbot.chat_history_cleared", default="Chat history cleared."), "system")

    def show_user_guide(self):
        """Show user guide dialog"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title(_t("chatbot.user_guide_title", default="User Guide"))
        guide_window.geometry("600x500")
        
        guide_text = """UNIVERSITY CHATBOT USER GUIDE

    GETTING STARTED:
    1. Log in with your university credentials
    2. Use the main chat interface to ask questions
    3. Try voice commands by clicking the Voice button

    FEATURES:
    • Natural language processing for intelligent responses
    • Voice interaction support (speak and listen)
    • Quick action buttons for common tasks
    • Real-time conversation tracking
    • Multi-user authentication system

    COMMANDS:
    • Type naturally - ask about courses, grades, registration
    • Use voice commands: "start voice mode", "test voice"
    • Quick actions: Click buttons for common requests
    • Settings: Adjust preferences and appearance

    TIPS:
    • Be specific in your questions for better responses
    • Use voice mode for hands-free interaction
    • Check the About tab for detailed feature information
    • Contact support for technical issues

    KEYBOARD SHORTCUTS:
    • Enter: Send message
    • Ctrl+Enter: New line in message
    • Esc: Clear current message
    • F1: Show this help guide
    """
        
        guide_display = scrolledtext.ScrolledText(guide_window, wrap=tk.WORD)
        guide_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        guide_display.insert(1.0, guide_text)
        guide_display.config(state=tk.DISABLED)

    def show_shortcuts(self):
        """Show keyboard shortcuts dialog"""
        shortcuts_window = tk.Toplevel(self.root)
        shortcuts_window.title(_t("chatbot.keyboard_shortcuts_title", default="Keyboard Shortcuts"))
        shortcuts_window.geometry("400x300")
        
        shortcuts_text = """KEYBOARD SHORTCUTS

    CHAT INTERFACE:
    Enter                Send message
    Ctrl+Enter           New line in message
    Escape               Clear message input
    Ctrl+L               Clear chat history

    NAVIGATION:
    F1                   Show user guide
    F2                   Open settings
    F3                   Toggle voice mode
    F5                   Refresh

    ADMIN FUNCTIONS:
    Ctrl+A               Open admin panel (admin only)
    Ctrl+Shift+S         System status
    Ctrl+Shift+U         User management
    """
        
        shortcuts_display = scrolledtext.ScrolledText(shortcuts_window, wrap=tk.WORD)
        shortcuts_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        shortcuts_display.insert(1.0, shortcuts_text)
        shortcuts_display.config(state=tk.DISABLED)

    def show_about_dialog(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title(_t("chatbot.about_title", default="About University Chatbot"))
        about_window.geometry("400x350")
        about_window.resizable(False, False)
        
        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()
        
        # About content
        about_frame = ttk.Frame(about_window, padding=20)
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(about_frame, text=_t("chatbot.university_chatbot", default="University Chatbot"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Version info
        version_info = """Version 2.0 Enhanced Edition
    Student Support System

    Developed for university student services
    with advanced AI capabilities and voice support.

    Features:
    • Natural Language Processing
    • Voice Recognition & Synthesis  
    • Multi-user Authentication
    • Real-time Analytics
    • Administrative Tools
    • Cross-platform GUI Support

    Technologies:
    • Python 3.8+
    • tkinter for GUI
    • Speech Recognition
    • Transformers (NLP)
    • SQLite Database
    • Flask Web API

    Copyright © 2024 University System
    All rights reserved."""
        
        info_label = ttk.Label(about_frame, text=version_info, justify=tk.CENTER)
        info_label.pack(pady=10)
        
        # Close button
        ttk.Button(about_frame, text=_t("common.close", default="Close"),
                   command=about_window.destroy).pack(pady=(20, 0))

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the GUI"""
        # Bind keyboard shortcuts
        self.root.bind('<F1>', lambda e: self.show_user_guide())
        self.root.bind('<F2>', lambda e: self.show_settings_screen())
        self.root.bind('<F3>', lambda e: self.toggle_voice_mode() if self.conversation_active else None)
        self.root.bind('<F5>', lambda e: self.refresh_current_view())
        self.root.bind('<Escape>', lambda e: self.clear_message_input() if self.conversation_active else None)
        self.root.bind('<Control-l>', lambda e: self.clear_chat_history() if self.conversation_active else None)
        
        # Admin shortcuts
        if self.current_user and self.current_user.get('role') in ['admin', 'staff']:
            self.root.bind('<Control-a>', lambda e: self.show_admin_panel())
            self.root.bind('<Control-Shift-S>', lambda e: self.show_admin_panel())
            self.root.bind('<Control-Shift-U>', lambda e: self.show_admin_panel())

    def clear_message_input(self):
        """Clear the message input field"""
        if hasattr(self, 'message_entry'):
            self.message_entry.delete("1.0", tk.END)

    def refresh_current_view(self):
        """Refresh the current view"""
        if hasattr(self, 'admin_frame') and self.admin_frame.winfo_viewable():
            self.refresh_system_status()
            self.refresh_user_list()
            self.generate_analytics_report()
            self.refresh_logs()
        elif hasattr(self, 'chat_frame') and self.chat_frame.winfo_viewable():
            self.status_label.config(text="View refreshed")

    def create_notification_system(self):
        """Create in-app notification system"""
        self.notifications = []
        
        # Notification frame (initially hidden)
        self.notification_frame = ttk.Frame(self.root)
        
        def show_notification(message, level="info", duration=3000):
            """Show a notification message"""
            # Create notification widget
            notif_colors = {
                "info": "#2196F3",
                "success": "#4CAF50", 
                "warning": "#FF9800",
                "error": "#F44336"
            }
            
            notif_widget = ttk.Label(self.notification_frame, 
                                    text=message,
                                    background=notif_colors.get(level, "#2196F3"),
                                    foreground="white",
                                    padding=10)
            notif_widget.pack(fill=tk.X, pady=2)
            
            # Auto-hide after duration
            self.root.after(duration, lambda: notif_widget.destroy())
            
            # Show notification frame if hidden
            if not self.notification_frame.winfo_viewable():
                self.notification_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        return show_notification

    def create_search_functionality(self):
        """Create chat history search functionality"""
        def show_search_dialog():
            search_window = tk.Toplevel(self.root)
            search_window.title("Search Chat History")
            search_window.geometry("500x400")
            
            # Search input
            search_frame = ttk.Frame(search_window)
            search_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
            search_entry = ttk.Entry(search_frame, width=30)
            search_entry.pack(side=tk.LEFT, padx=(5, 10), fill=tk.X, expand=True)
            
            def perform_search():
                query = search_entry.get().strip().lower()
                if not query:
                    return
                
                results_text.delete(1.0, tk.END)
                results_text.insert(1.0, f"Search results for: '{query}'\n" + "="*50 + "\n\n")
                
                # Search through conversation history
                found_count = 0
                if hasattr(self.chatbot, 'conversation_history'):
                    for username, history in self.chatbot.conversation_history.items():
                        for conv in history:
                            message = conv.get('message', '').lower()
                            response = conv.get('response', '').lower()
                            
                            if query in message or query in response:
                                found_count += 1
                                timestamp = conv.get('timestamp', 'Unknown')
                                results_text.insert(tk.END, f"[{timestamp}] {username}:\n")
                                results_text.insert(tk.END, f"Q: {conv.get('message', '')}\n")
                                results_text.insert(tk.END, f"A: {conv.get('response', '')}\n\n")
                
                if found_count == 0:
                    results_text.insert(tk.END, "No results found.")
                else:
                    results_text.insert(1.0, f"Found {found_count} results\n\n")
            
            ttk.Button(search_frame, text="Search", command=perform_search).pack(side=tk.LEFT)
            
            # Results display
            results_text = scrolledtext.ScrolledText(search_window, height=20)
            results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Bind Enter key to search
            search_entry.bind('<Return>', lambda e: perform_search())
            search_entry.focus()
        
        return show_search_dialog

    def create_theme_manager(self):
        """Create theme management functionality"""
        self.themes = {
            "default": {
                "bg": "#F5F5F5",
                "fg": "#212121",
                "select_bg": "#2E86AB",
                "select_fg": "#FFFFFF"
            },
            "dark": {
                "bg": "#2B2B2B",
                "fg": "#FFFFFF", 
                "select_bg": "#404040",
                "select_fg": "#FFFFFF"
            },
            "blue": {
                "bg": "#E3F2FD",
                "fg": "#0D47A1",
                "select_bg": "#1976D2",
                "select_fg": "#FFFFFF"
            }
        }
        
        def apply_theme(theme_name):
            """Apply a color theme to the interface"""
            if theme_name not in self.themes:
                return
            
            theme = self.themes[theme_name]
            
            # Apply to main window
            self.root.configure(bg=theme["bg"])
            
            # Apply to chat display
            if hasattr(self, 'chat_display'):
                self.chat_display.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"]
                )
            
            # Apply to message entry
            if hasattr(self, 'message_entry'):
                self.message_entry.configure(
                    bg=theme["bg"],
                    fg=theme["fg"],
                    selectbackground=theme["select_bg"],
                    selectforeground=theme["select_fg"]
                )
            
            # Update color references
            self.colors['background'] = theme["bg"]
            self.colors['text_primary'] = theme["fg"]
        
        return apply_theme

    def create_session_management(self):
        """Create session management functionality"""
        self.session_start_time = datetime.now()
        self.message_count = 0
        self.session_data = {
            'start_time': self.session_start_time,
            'messages_sent': 0,
            'voice_interactions': 0,
            'errors_encountered': 0
        }
        
        def update_session_stats(message_type="text"):
            """Update session statistics"""
            self.session_data['messages_sent'] += 1
            self.message_count += 1
            
            if message_type == "voice":
                self.session_data['voice_interactions'] += 1
            
            # Update status bar with session info
            duration = datetime.now() - self.session_start_time
            duration_str = str(duration).split('.')[0]  # Remove microseconds
            
            status_text = f"Session: {duration_str} | Messages: {self.message_count}"
            if hasattr(self, 'status_label'):
                self.status_label.config(text=status_text)
        
        def get_session_summary():
            """Get session summary for logout"""
            duration = datetime.now() - self.session_start_time
            
            summary = f"""Session Summary:
    Duration: {str(duration).split('.')[0]}
    Messages Sent: {self.session_data['messages_sent']}
    Voice Interactions: {self.session_data['voice_interactions']}
    Errors: {self.session_data['errors_encountered']}
    Start Time: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}
    End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
            return summary
        
        return update_session_stats, get_session_summary

    def create_settings_screen(self):
        """Create settings/preferences screen"""
        self.settings_frame = ttk.Frame(self.main_frame)

        # Header
        header = ttk.Label(self.settings_frame,
                          text=_t("chatbot.settings_preferences", default="Settings & Preferences"),
                          style='CB.Title.TLabel')
        header.pack(pady=(0, 20))

        # Settings notebook
        notebook = ttk.Notebook(self.settings_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # General settings tab
        general_tab = ttk.Frame(notebook)
        notebook.add(general_tab, text=_t("chatbot.tab_general", default="General"))

        # Voice settings tab
        voice_tab = ttk.Frame(notebook)
        notebook.add(voice_tab, text=_t("chatbot.tab_voice", default="Voice"))

        # About tab
        about_tab = ttk.Frame(notebook)
        notebook.add(about_tab, text=_t("chatbot.tab_about", default="About"))

        # General settings content
        self.create_general_settings(general_tab)
        self.create_voice_settings(voice_tab)
        self.create_about_tab(about_tab)

        # Back button
        back_button = ttk.Button(self.settings_frame,
                                text=_t("chatbot.back_to_chat", default="Back to Chat"),
                                style='CB.Primary.TButton',
                                command=self.show_chat_screen)
        back_button.pack(pady=(20, 0))
    
    def create_general_settings(self, parent):
        """Create general settings controls"""
        # Theme settings
        theme_frame = ttk.LabelFrame(parent, text=_t("chatbot.appearance", default="Appearance"), padding=10)
        theme_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(theme_frame, text=_t("chatbot.chat_font_size", default="Chat Font Size:")).pack(anchor=tk.W)
        self.font_size_var = tk.StringVar(value="10")
        font_size_combo = ttk.Combobox(theme_frame,
                                      textvariable=self.font_size_var,
                                      values=["8", "9", "10", "11", "12", "14"],
                                      state="readonly")
        font_size_combo.pack(anchor=tk.W, pady=(5, 10))
        font_size_combo.bind("<<ComboboxSelected>>", self.update_font_size)

        # Notification settings
        notif_frame = ttk.LabelFrame(parent, text=_t("chatbot.notifications", default="Notifications"), padding=10)
        notif_frame.pack(fill=tk.X, padx=10, pady=10)

        self.sound_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame,
                       text=_t("chatbot.enable_notification_sounds", default="Enable notification sounds"),
                       variable=self.sound_enabled).pack(anchor=tk.W)

        self.auto_scroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(notif_frame,
                       text=_t("chatbot.auto_scroll_chat", default="Auto-scroll chat"),
                       variable=self.auto_scroll).pack(anchor=tk.W)
    
    def create_voice_settings(self, parent):
        """Create voice settings controls"""
        if not self.chatbot.voice_interface.enabled:
            ttk.Label(parent,
                     text=_t("chatbot.voice_not_available", default="Voice interface is not available.\nPlease check your microphone and dependencies."),
                     foreground='red').pack(expand=True)
            return

        # Voice test
        test_frame = ttk.LabelFrame(parent, text=_t("chatbot.voice_test", default="Voice Test"), padding=10)
        test_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(test_frame,
                  text=_t("chatbot.test_microphone", default="Test Microphone"),
                  command=self.test_voice).pack(pady=5)

        self.voice_status_label = ttk.Label(test_frame, text=_t("chatbot.click_test_mic", default="Click 'Test Microphone' to check your setup"))
        self.voice_status_label.pack(pady=5)

        # Voice settings
        settings_frame = ttk.LabelFrame(parent, text=_t("chatbot.voice_settings", default="Voice Settings"), padding=10)
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(settings_frame, text=_t("chatbot.recording_duration", default="Recording Duration (seconds):")).pack(anchor=tk.W)
        self.voice_duration_var = tk.StringVar(value="5")
        duration_spinbox = ttk.Spinbox(settings_frame,
                                      from_=1, to=10,
                                      textvariable=self.voice_duration_var,
                                      width=10)
        duration_spinbox.pack(anchor=tk.W, pady=(5, 10))

        self.voice_tts_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame,
                       text=_t("chatbot.enable_tts", default="Enable text-to-speech responses"),
                       variable=self.voice_tts_enabled).pack(anchor=tk.W)
    
    def create_about_tab(self, parent):
        """Create about/help tab"""
        # App info
        info_frame = ttk.LabelFrame(parent, text=_t("chatbot.app_information", default="Application Information"), padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_text = _t("chatbot.about_info", default="""University Chatbot v2.0
Student Support System

Features:
• Intelligent conversation processing
• Voice interaction support
• Multi-user authentication
• Course recommendations
• Grade tracking
• Financial aid information
• Technical support

Powered by advanced NLP and machine learning.""")

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        # Help
        help_frame = ttk.LabelFrame(parent, text=_t("chatbot.getting_help", default="Getting Help"), padding=10)
        help_frame.pack(fill=tk.X, padx=10, pady=10)

        help_text = _t("chatbot.help_info", default="""How to use the chatbot:
1. Type your questions in natural language
2. Use quick action buttons for common tasks
3. Try voice commands by clicking the Voice button
4. Access your conversation history
5. Click 'Exit to Main' to return to the main system

For technical support, contact IT Services.""")

        ttk.Label(help_frame, text=help_text, justify=tk.LEFT).pack(anchor=tk.W)
    
    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status label
        self.status_label = ttk.Label(self.status_bar, text=_t("chatbot.status_ready", default="Ready"))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Connection status
        self.connection_label = ttk.Label(self.status_bar, text=_t("chatbot.status_connected", default="● Connected"), foreground='green')
        self.connection_label.pack(side=tk.RIGHT, padx=5)
    
    def setup_event_handlers(self):
        """Setup event handlers for the GUI"""
        # Enter key sends message in chat
        self.root.bind('<Return>', lambda e: self.send_message() if self.conversation_active else None)
        
        # Ctrl+Enter for new line in message entry
        self.root.bind('<Control-Return>', lambda e: self.message_entry.insert(tk.INSERT, '\n'))
        
        # Focus handling
        self.root.bind('<Button-1>', self.on_click)
        
        # Window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def show_chat_screen(self):
        """Show the main chat screen"""
        self.hide_all_screens()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = True
        self.message_entry.focus()
        
        # Update user info
        if self.current_user:
            self.user_info_label.config(text=f"Welcome, {self.current_user['username']} ({self.current_user['role']})")
        
        # Add personalized welcome summary
        if not hasattr(self, '_welcome_shown'):
            welcome = self._build_welcome_summary()
            self.add_chat_message("System", welcome, "system")
            self._welcome_shown = True
    
    def show_settings_screen(self):
        """Show the settings screen"""
        self.hide_all_screens()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation_active = False
    
    def hide_all_screens(self):
        """Hide all screen frames"""
        frames_to_hide = [self.chat_frame, self.settings_frame]
        if hasattr(self, 'admin_frame'):
            frames_to_hide.append(self.admin_frame)
        for frame in frames_to_hide:
            frame.pack_forget()

    def handle_exit(self):
        """Handle exit to main GUI"""
        try:
            # Cleanup voice interface if enabled
            if hasattr(self.chatbot, 'voice_interface') and self.chatbot.voice_interface.enabled:
                self.chatbot.voice_interface.cleanup()

            # Close the chatbot window (returns to main GUI)
            if hasattr(self.root, 'destroy'):
                self.root.destroy()

            print("✓ Chatbot GUI closed - returning to main system")

        except Exception as e:
            print(f"Warning: Error during exit: {e}")
            # Force close if normal close fails
            try:
                self.root.quit()
            except Exception as e:
                logger.debug(f"Error closing window: {e}")
    
    def send_message(self):
        """Send user message to chatbot"""
        if not self.conversation_active:
            return

        message = self.message_entry.get("1.0", tk.END).strip()
        if not message:
            return

        # Clear input
        self.message_entry.delete("1.0", tk.END)

        # Add user message to chat
        self.add_chat_message(self.current_user.get("username", "User"), message, "user")

        # Update session stats
        if hasattr(self, 'update_session_stats'):
            self.update_session_stats("text")

        # Update status
        self.status_label.config(text="Processing...")

        # Process message directly to avoid threading issues
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(
                message,
                user_id,
                session_id=self.session_id
            )

            # Add bot response to chat
            self.add_chat_message("Chatbot", response, "bot")

            # Log activity
            log_activity('chat', 'chatbot_message', None,
                        details={'user': user_id, 'message_length': len(message)})

        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {e}"
            self.add_chat_message("Chatbot", error_response, "bot")

        # Update status
        self.status_label.config(text="Ready")

        # Text-to-speech if enabled
        if (hasattr(self, 'voice_tts_enabled') and
            self.voice_tts_enabled.get() and
            LIBRARIES_AVAILABLE.get('pyttsx3', False)):
            threading.Thread(target=self.chatbot.text_to_speech,
                           args=(response,), daemon=True).start()
    
    def quick_message(self, message):
        """Send a quick action message"""
        if not self.conversation_active:
            return

        # Set message in input and send
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", message)
        self.send_message()

    def show_my_courses(self):
        """Show user's enrolled courses with real database data"""
        try:
            context = self.get_user_context()
            courses = context.get('courses', [])

            if not courses:
                response = "You are not currently enrolled in any courses. Visit the registration page to enroll in courses."
                self.add_chat_message("Chatbot", response, "bot")
                return

            response = f"📚 **Your Enrolled Courses ({len(courses)} total):**\n\n"
            for course in courses:
                response += f"• **{course['name']}** (ID: {course['id']})\n"
                response += f"  Credits: {course.get('credits', 'N/A')}\n\n"

            response += "Would you like more details about any specific course?"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'courses', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching courses: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_my_grades(self):
        """Show user's recent grades with real database data"""
        try:
            context = self.get_user_context()
            grades = context.get('grades', [])

            if not grades:
                response = "No grades are currently available. Grades will appear here once your instructors post them."
                self.add_chat_message("Chatbot", response, "bot")
                return

            response = f"📊 **Your Recent Grades ({len(grades)} entries):**\n\n"
            for grade in grades:
                response += f"• **{grade['course']}**\n"
                response += f"  Grade: {grade['grade']} ({grade['points']} points)\n"
                response += f"  Posted: {grade['date']}\n\n"

            # Calculate average if possible
            try:
                numeric_grades = [g['points'] for g in grades if g['points'] is not None]
                if numeric_grades:
                    avg = sum(numeric_grades) / len(numeric_grades)
                    response += f"\n**Average: {avg:.2f} points**"
            except Exception as e:
                logger.debug(f"Error calculating grade average: {e}")

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'grades', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching grades: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_financial_aid(self):
        """Show financial aid information"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Try to get user's financial aid applications
                try:
                    cursor.execute('''
                        SELECT application_type, status, amount, application_date
                        FROM financial_aid_applications
                        WHERE student_id = ?
                        ORDER BY application_date DESC
                        LIMIT 5
                    ''', (self.current_user.get('username'),))
                    applications = cursor.fetchall()

                    if applications:
                        response = "💰 **Your Financial Aid Applications:**\n\n"
                        for app in applications:
                            response += f"• **{app[0]}**\n"
                            response += f"  Status: {app[1]}\n"
                            response += f"  Amount: ${app[2]:,.2f}\n"
                            response += f"  Applied: {app[3]}\n\n"
                    else:
                        response = "You have no financial aid applications on record.\n\n"
                except Exception:
                    response = ""

                # Show available aid programs
                response += "**Available Financial Aid Programs:**\n\n"
                response += "• Merit Scholarships\n"
                response += "• Need-Based Grants\n"
                response += "• Student Loans\n"
                response += "• Work-Study Programs\n\n"
                response += "Visit the Financial Aid office for personalized assistance or to apply."

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'financial_aid', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching financial aid info: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_my_schedule(self):
        """Show user's class schedule"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get schedule if available
                try:
                    cursor.execute('''
                        SELECT c.course_name, s.day_of_week, s.start_time, s.end_time,
                               s.room_number, s.building
                        FROM course_schedule s
                        JOIN courses c ON s.course_id = c.course_id
                        JOIN enrollments e ON c.course_id = e.course_id
                        WHERE e.student_id = ? AND e.status = 'active'
                        ORDER BY
                            CASE s.day_of_week
                                WHEN 'Monday' THEN 1
                                WHEN 'Tuesday' THEN 2
                                WHEN 'Wednesday' THEN 3
                                WHEN 'Thursday' THEN 4
                                WHEN 'Friday' THEN 5
                                WHEN 'Saturday' THEN 6
                                WHEN 'Sunday' THEN 7
                            END,
                            s.start_time
                    ''', (self.current_user.get('username'),))
                    schedule = cursor.fetchall()

                    if schedule:
                        response = "📅 **Your Class Schedule:**\n\n"
                        current_day = None
                        for item in schedule:
                            if item[1] != current_day:
                                current_day = item[1]
                                response += f"\n**{current_day}:**\n"
                            response += f"• {item[0]}\n"
                            response += f"  Time: {item[2]} - {item[3]}\n"
                            response += f"  Location: {item[5]} {item[4]}\n"
                    else:
                        response = "No schedule information available. Your courses may not have scheduled times yet."

                except Exception as e:
                    print(f"Schedule error: {e}")
                    # Fallback: show courses without schedule
                    context = self.get_user_context()
                    courses = context.get('courses', [])
                    if courses:
                        response = "📅 **Your Courses:**\n\n"
                        for course in courses:
                            response += f"• {course['name']}\n"
                        response += "\n(Detailed schedule times not yet available)"
                    else:
                        response = "No courses found. Enroll in courses to see your schedule."

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'schedule', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching schedule: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def _build_welcome_summary(self):
        """Build a personalized welcome summary with real data from the database."""
        username = self.current_user.get('username', 'Student') if self.current_user else 'Student'
        lines = [f"Welcome, {username}! Here's your summary:\n"]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Active course count
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM enrollments WHERE student_id = ? AND status = 'active'",
                        (username,))
                    count = cursor.fetchone()[0]
                    lines.append(f"Courses: {count} active enrollment{'s' if count != 1 else ''}")
                except Exception:
                    pass

                # Upcoming assignments (next 7 days, not yet submitted)
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM assignments a
                        LEFT JOIN assignment_submissions sub
                            ON a.id = sub.assignment_id AND sub.student_id = ?
                        WHERE a.module_code IN (
                            SELECT module_code FROM student_modules WHERE student_id = ? AND status = 'enrolled'
                        )
                        AND a.due_date BETWEEN date('now') AND date('now', '+7 days')
                        AND sub.id IS NULL
                    ''', (username, username))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Upcoming: {count} assignment{'s' if count != 1 else ''} due this week")
                except Exception:
                    pass

                # Library books checked out
                try:
                    cursor.execute('''
                        SELECT COUNT(*), MIN(due_date) FROM book_loans
                        WHERE user_id = ? AND status IN ('active', 'overdue')
                    ''', (username,))
                    row = cursor.fetchone()
                    count = row[0] if row else 0
                    if count:
                        nearest = row[1] or 'unknown'
                        lines.append(f"Library: {count} book{'s' if count != 1 else ''} checked out (nearest due: {nearest})")
                except Exception:
                    pass

                # Unread notifications
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Notifications: {count} unread")
                except Exception:
                    pass

                # Open support tickets
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM support_tickets WHERE student_id = ? AND status NOT IN ('Closed', 'Resolved')",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Support: {count} open ticket{'s' if count != 1 else ''}")
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Error building welcome summary: {e}")

        if len(lines) == 1:
            lines.append("No summary data available yet.")

        lines.append("\nUse the quick actions below or type a question.")
        return "\n".join(lines)

    def show_my_assignments(self):
        """Show the student's assignments with submission status."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.title, a.due_date, a.max_marks, a.assignment_type,
                           sub.status, sub.grade
                    FROM assignments a
                    LEFT JOIN assignment_submissions sub
                        ON a.id = sub.assignment_id AND sub.student_id = ?
                    WHERE a.module_code IN (
                        SELECT module_code FROM student_modules WHERE student_id = ? AND status = 'enrolled'
                    )
                    ORDER BY a.due_date ASC
                    LIMIT 15
                ''', (username, username))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No assignments found for your enrolled modules.", "bot")
                return

            response = f"Assignments ({len(rows)}):\n\n"
            for r in rows:
                title, due, max_marks, atype, status, grade = r
                status_label = status if status else ("overdue" if due and due < datetime.now().strftime('%Y-%m-%d') else "pending")
                response += f"  {title}\n"
                response += f"    Type: {atype or 'N/A'}  |  Due: {due or 'N/A'}  |  Max: {max_marks or 'N/A'}\n"
                response += f"    Status: {status_label}"
                if grade is not None:
                    response += f"  |  Grade: {grade}"
                response += "\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'assignments', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching assignments: {e}", "bot")

    def show_my_library_books(self):
        """Show the student's checked-out library books."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT b.title, b.author, bl.checkout_date, bl.due_date,
                           bl.status, bl.fine_amount
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.user_id = ? AND bl.status IN ('active', 'overdue')
                    ORDER BY bl.due_date ASC
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no books currently checked out.", "bot")
                return

            response = f"Library Books ({len(rows)} checked out):\n\n"
            for r in rows:
                title, author, checkout, due, status, fine = r
                response += f"  {title}\n"
                response += f"    Author: {author or 'N/A'}  |  Due: {due or 'N/A'}  |  Status: {status}\n"
                if fine and float(fine) > 0:
                    response += f"    Fine: ${float(fine):.2f}\n"
                response += "\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'library_books', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching library books: {e}", "bot")

    def show_my_attendance(self):
        """Show per-module attendance summary."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT module_code,
                           COUNT(*) as total,
                           SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present
                    FROM attendance_records
                    WHERE student_id = ?
                    GROUP BY module_code
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No attendance records found.", "bot")
                return

            response = "Attendance Summary:\n\n"
            for module, total, present in rows:
                pct = (present / total * 100) if total else 0
                response += f"  {module}: {present}/{total} - {pct:.0f}%\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'attendance', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching attendance: {e}", "bot")

    def show_my_tickets(self):
        """Show the student's open support tickets."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ticket_id, title, category, priority, status, created_datetime
                    FROM support_tickets
                    WHERE student_id = ? AND status NOT IN ('Closed')
                    ORDER BY created_datetime DESC
                    LIMIT 10
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no open support tickets.", "bot")
                return

            response = f"Support Tickets ({len(rows)} open):\n\n"
            for r in rows:
                tid, title, cat, pri, status, created = r
                response += f"  #{tid}: {title}\n"
                response += f"    Category: {cat or 'N/A'}  |  Priority: {pri or 'N/A'}  |  Status: {status}\n"
                response += f"    Created: {created or 'N/A'}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'support_tickets', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching support tickets: {e}", "bot")

    def show_my_notifications(self):
        """Show the student's recent notifications."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT message, created_at, read
                    FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no notifications.", "bot")
                return

            response = f"Notifications ({len(rows)} recent):\n\n"
            for msg, created, is_read in rows:
                indicator = "  " if is_read else "* "
                response += f"  {indicator}{msg}\n"
                response += f"    {created or ''}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'notifications', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching notifications: {e}", "bot")

    def show_upcoming_events(self):
        """Show upcoming campus events."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Try campus_events first, fall back to union_events
                rows = []
                for table in ('campus_events', 'union_events'):
                    try:
                        cursor.execute(f'''
                            SELECT event_name, event_date, location, category
                            FROM {table}
                            WHERE event_date >= date('now')
                            ORDER BY event_date ASC
                            LIMIT 10
                        ''')
                        rows = cursor.fetchall()
                        if rows:
                            break
                    except Exception:
                        continue

            if not rows:
                self.add_chat_message("Chatbot",
                    "No upcoming events found.", "bot")
                return

            response = f"Upcoming Events ({len(rows)}):\n\n"
            for name, date_val, location, category in rows:
                response += f"  {name}\n"
                response += f"    Date: {date_val or 'TBD'}  |  Location: {location or 'TBD'}"
                if category:
                    response += f"  |  Category: {category}"
                response += "\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'events', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching events: {e}", "bot")

    def show_announcements(self):
        """Show recent announcements."""
        try:
            username = self.current_user.get('username', '')
            role = self.current_user.get('role', 'student')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, content, created_at
                    FROM announcements
                    WHERE visibility IN ('all', ?)
                    ORDER BY created_at DESC
                    LIMIT 5
                ''', (role,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No announcements at this time.", "bot")
                return

            response = f"Announcements ({len(rows)} recent):\n\n"
            for title, content, created in rows:
                snippet = (content[:120] + '...') if content and len(content) > 120 else (content or '')
                response += f"  {title}\n"
                response += f"    {snippet}\n"
                response += f"    Posted: {created or 'N/A'}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'announcements', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching announcements: {e}", "bot")

    def show_quick_help(self):
        """Show a formatted list of what the chatbot can do."""
        help_text = (
            "Quick Help\n\n"
            "Quick Action Buttons:\n"
            "  My Courses      - View your enrolled courses\n"
            "  My Grades       - View recent grades and averages\n"
            "  View Schedule   - See your weekly class schedule\n"
            "  Assignments     - Check assignment due dates and submissions\n"
            "  Library Books   - View checked-out books and due dates\n"
            "  Financial Aid   - Check aid applications and programs\n"
            "  Attendance      - Per-module attendance summary\n"
            "  Support Tickets - View open support requests\n"
            "  Notifications   - Recent notifications\n"
            "  Events          - Upcoming campus events\n"
            "  Announcements   - Latest announcements\n\n"
            "Example Questions:\n"
            "  'What courses am I enrolled in?'\n"
            "  'When is my next assignment due?'\n"
            "  'How do I apply for financial aid?'\n"
            "  'What are the library hours?'\n\n"
            "Keyboard Shortcuts:\n"
            "  Enter          - Send message\n"
            "  Ctrl+Enter     - New line\n"
            "  Escape         - Clear input\n"
            "  F1             - User guide\n"
        )
        self.add_chat_message("Chatbot", help_text, "bot")

    def add_chat_message(self, sender, message, msg_type="user"):
        """Add message to chat display"""
        self.chat_display.config(state=tk.NORMAL)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M")
        
        # Add message with styling
        if msg_type == "user":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{sender}: ", "user")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        elif msg_type == "bot":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{sender}: ", "bot")
            self.chat_display.insert(tk.END, f"{message}\n\n")
        elif msg_type == "system":
            self.chat_display.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_display.insert(tk.END, f"{message}\n\n", "system")
        
        self.chat_display.config(state=tk.DISABLED)
        
        # Auto-scroll if enabled
        if hasattr(self, 'auto_scroll') and self.auto_scroll.get():
            self.chat_display.see(tk.END)
    
    def toggle_voice_mode(self):
        """Toggle voice recording mode"""
        if not self.chatbot.voice_interface.enabled:
            messagebox.showwarning(
                _t("chatbot.voice_unavailable", default="Voice Unavailable"),
                _t("chatbot.voice_unavailable_msg", default="Voice interface is not available. Please check your microphone setup.")
            )
            return
        
        if not self.conversation_active:
            return
        
        # Change button state
        self.voice_button.config(state='disabled', text="🎤 Recording...")
        self.status_label.config(text="Listening...")
        
        # Record voice in thread
        duration = float(getattr(self, 'voice_duration_var', tk.StringVar(value="5")).get())
        threading.Thread(target=self._record_voice, args=(duration,), daemon=True).start()
    
    def _record_voice(self, duration):
        """Record voice input (runs in separate thread)"""
        try:
            # Record audio
            text = self.chatbot.process_voice_input(duration)
            
            # Update UI in main thread
            if text:
                self.root.after(0, self._handle_voice_result, text)
            else:
                self.root.after(0, self._handle_voice_error, "No speech detected")
                
        except Exception as e:
            self.root.after(0, self._handle_voice_error, str(e))
    
    def _handle_voice_result(self, text):
        """Handle successful voice recognition"""
        # Reset voice button
        self.voice_button.config(state='normal', text="🎤 Voice")
        self.status_label.config(text="Voice recognized")
        
        # Add recognized text to input and send
        self.message_entry.delete("1.0", tk.END)
        self.message_entry.insert("1.0", text)
        self.send_message()
    
    def _handle_voice_error(self, error):
        """Handle voice recognition error"""
        # Reset voice button
        self.voice_button.config(state='normal', text="🎤 Voice")
        self.status_label.config(text="Ready")
        
        # Show error
        messagebox.showerror(
            _t("chatbot.voice_error", default="Voice Error"),
            _t("chatbot.voice_recognition_failed", default="Voice recognition failed: {error}").format(error=error)
        )
    
    def test_voice(self):
        """Test voice interface"""
        if not self.chatbot.voice_interface.enabled:
            self.voice_status_label.config(text="Voice interface not available", foreground='red')
            return
        
        self.voice_status_label.config(text="Testing microphone...", foreground='blue')
        
        # Run test in thread
        threading.Thread(target=self._run_voice_test, daemon=True).start()
    
    def _run_voice_test(self):
        """Run voice test (in separate thread)"""
        try:
            result = self.chatbot.test_voice_interface()
            self.root.after(0, self._handle_voice_test_result, result)
        except Exception as e:
            error_result = {"status": "error", "message": str(e)}
            self.root.after(0, self._handle_voice_test_result, error_result)
    
    def _handle_voice_test_result(self, result):
        """Handle voice test result"""
        if result["status"] == "success":
            devices = len(result.get("devices", []))
            test_text = result.get("test_recording", "No test recording")
            message = f"✓ Voice test successful!\nFound {devices} audio devices\nTest: '{test_text}'"
            self.voice_status_label.config(text=message, foreground='green')
        else:
            message = f"✗ Voice test failed: {result.get('message', 'Unknown error')}"
            self.voice_status_label.config(text=message, foreground='red')
    
    def on_click(self, event):
        """Handle click events for focus management"""
        widget = event.widget
        if widget == self.message_entry and self.conversation_active:
            # Focus on message entry when clicking in chat area
            self.message_entry.focus()
    
    def on_closing(self):
        """Handle window closing"""
        # Use the exit handler which properly cleans up without logging out
        self.handle_exit()
    
    def run(self):
        """Start the GUI main loop"""
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"GUI error: {e}")
            messagebox.showerror(
                _t("chatbot.application_error", default="Application Error"),
                _t("chatbot.error_occurred", default="An error occurred: {error}").format(error=str(e))
            )

    def _handle_bot_response(self, response):
        """Handle bot response (runs in main thread)"""
        # Add bot response to chat
        self.add_chat_message("Chatbot", response, "bot")

        # Update status
        self.status_label.config(text="Ready")

        # Text-to-speech if enabled
        if (hasattr(self, 'voice_tts_enabled') and
            self.voice_tts_enabled.get() and
            LIBRARIES_AVAILABLE.get('pyttsx3', False)):
            threading.Thread(target=self.chatbot.text_to_speech,
                           args=(response,), daemon=True).start()

    def _process_message(self, message):
        """Process message with chatbot (runs in separate thread)"""
        try:
            user_id = self.current_user.get("username", "gui_user")

            # Process message with chatbot
            response = self.chatbot.process_message(
                message,
                user_id,
                session_id=self.session_id
            )

            # Update UI in main thread
            self.root.after(0, self._handle_bot_response, response)

        except Exception as e:
            error_response = f"I apologize, but I encountered an error: {e}"
            self.root.after(0, self._handle_bot_response, error_response)


class ChatbotManager:
    """Manager class to handle different interface modes"""
    
    def __init__(self, chatbot_instance):
        self.chatbot = chatbot_instance
    
    def run_interface(self, mode="auto"):
        """Run the appropriate interface based on mode"""
        available_modes = self.get_available_modes()

        if mode == "auto":
            # Auto-select best available mode
            if "gui" in available_modes and LIBRARIES_AVAILABLE.get('tkinter', False):
                mode = "gui"
            elif "auth-console" in available_modes:
                mode = "auth-console"
            else:
                mode = "console"

        print(f"Starting {mode} interface...")

        if mode == "gui" and "gui" in available_modes:
            self.run_gui()
        elif mode == "auth-console" and "auth-console" in available_modes:
            self.chatbot.run_authenticated_console_interface()
        elif mode == "console":
            self.chatbot.run_console_interface()
        elif mode == "web":
            self.run_web_interface()
        else:
            print(f"Mode '{mode}' not available. Available modes: {', '.join(available_modes)}")
            self.show_mode_selection()
    
    def get_available_modes(self):
        """Get list of available interface modes"""
        modes = ["console"]
        
        if LIBRARIES_AVAILABLE.get('tkinter', False):
            modes.append("gui")
        
        if self.chatbot.auth_system:
            modes.append("auth-console")
        
        if LIBRARIES_AVAILABLE.get('flask', False):
            modes.append("web")
        
        return modes
    
    def show_mode_selection(self):
        """Show interactive mode selection"""
        available_modes = self.get_available_modes()

        print("\nAvailable Interface Modes:")
        for i, mode in enumerate(available_modes, 1):
            description = self.get_mode_description(mode)
            print(f"{i}. {mode.upper()}: {description}")

        while True:
            try:
                choice = input(f"\nSelect interface mode (1-{len(available_modes)}): ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_modes):
                        selected_mode = available_modes[idx]
                        self.run_interface(selected_mode)
                        break
                print("Invalid selection. Please try again.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def get_mode_description(self, mode):
        """Get description for interface mode"""
        descriptions = {
            "gui": "Modern graphical interface with voice support",
            "console": "Text-based console interface",
            "auth-console": "Authenticated console interface with user management",
            "web": "Web-based API interface"
        }
        return descriptions.get(mode, "Interface mode")
    
    def run_gui(self):
        """Run the GUI interface"""
        if not LIBRARIES_AVAILABLE.get('tkinter', False):
            print("GUI not available - tkinter library missing")
            return

    def run_web_interface(self):
        """Run web interface - not available"""
        print("Web interface not available - API has been removed")


# Enhanced main execution with GUI support
def run_enhanced_chatbot():
    """Enhanced main function with GUI and multiple interface support"""
    print("University Chatbot v2.0 - Enhanced Edition")
    print("=" * 50)
    
    try:
        # Initialize chatbot
        _lazy_auth()  # Load auth system if available
        chatbot = UniversityChatbot()
        
        # Set up auth system if available
        if AUTH_AVAILABLE:
            try:
                # Try to integrate with existing auth system
                # This would be set by the main application
                logger.debug("Auth integration placeholder - no specific integration required")
            except Exception as e:
                print(f"Auth integration warning: {e}")
        
        # Create manager
        manager = ChatbotManager(chatbot)
        
        # Show available interfaces
        available_modes = manager.get_available_modes()
        print(f"Available interfaces: {', '.join(available_modes)}")
        
        # Check for GUI availability
        if LIBRARIES_AVAILABLE.get('tkinter', False):
            print("✓ GUI interface available")
        else:
            print("✗ GUI interface unavailable (tkinter missing)")
        
        if chatbot.voice_interface.enabled:
            print("✓ Voice interface available")
        else:
            print("✗ Voice interface unavailable (check microphone/dependencies)")
        
        # Interactive mode selection
        print("\nInterface Options:")
        print("1. GUI - Modern graphical interface (recommended)")
        print("2. Console - Text-based interface")
        if AUTH_AVAILABLE:
            print("3. Auth Console - Authenticated console interface")
        print("4. Web API - Web server for API access")
        print("5. Auto - Automatically select best interface")
        
        try:
            choice = input("\nSelect interface (1-5, or press Enter for auto): ").strip()
            
            mode_map = {
                "1": "gui",
                "2": "console", 
                "3": "auth-console" if AUTH_AVAILABLE else "console",
                "4": "web",
                "5": "auto",
                "": "auto"
            }
            
            selected_mode = mode_map.get(choice, "auto")
            manager.run_interface(selected_mode)
            
        except KeyboardInterrupt:
            print("\nStarting auto-mode...")
            manager.run_interface("auto")
        
    except Exception as e:
        print(f"Failed to initialize enhanced chatbot: {e}")
        print("Falling back to basic chatbot...")
        
        # Fallback to basic chatbot
        try:
            if AUTH_AVAILABLE:
                basic_chatbot = MinimalChatbot()
                basic_chatbot.run_authenticated_console_interface()
            else:
                basic_chatbot = MinimalChatbot()
                basic_chatbot.process_message("Hello", "fallback_user")
                print("Basic chatbot ready - limited functionality available")
        except Exception as fallback_error:
            print(f"Complete startup failure: {fallback_error}")


# Modify the existing main execution block to include GUI option
def update_main_execution():
    """Update the main execution to include GUI option"""
    original_main = """
    if __name__ == "__main__":
        # Initialize enhanced chatbot with authentication
        try:
            chatbot = UniversityChatbot()
            
            # Choose interface mode
            if AUTH_AVAILABLE and chatbot.auth_system:
                print("Authentication system available!")
                mode = input("Choose interface mode (console/web/auth-console/both): ").lower()
            else:
                mode = input("Choose interface mode (console/web/both): ").lower()
    """
    
    enhanced_main = """
    if __name__ == "__main__":
        # Run enhanced chatbot with GUI support
        run_enhanced_chatbot()
    """
    
    return enhanced_main


# Backward compatibility wrapper
class BackwardCompatibilityWrapper:
    """Ensures backward compatibility with existing code"""
    
    @staticmethod
    def ensure_compatibility(chatbot_instance):
        """Ensure all original methods are still available"""
        # Add any missing methods for backward compatibility
        if not hasattr(chatbot_instance, 'run_gui'):
            chatbot_instance.run_gui = lambda: print("GUI not available - install tkinter")
        
        # Ensure original interface methods work
        original_run = chatbot_instance.run
        def enhanced_run():
            """Enhanced run method with GUI fallback"""
            try:
                if LIBRARIES_AVAILABLE.get('tkinter', False):
                    manager = ChatbotManager(chatbot_instance)
                    manager.run_interface("auto")
                else:
                    original_run()
            except Exception:
                original_run()
        
        chatbot_instance.run = enhanced_run
        
        return chatbot_instance


# Additional GUI utility functions
def create_chatbot_with_gui(auth_system=None, db_path=str(DEFAULT_DB_PATH)):
    """Factory function to create chatbot with GUI support"""
    chatbot = UniversityChatbot(db_path=db_path)
    
    if auth_system:
        chatbot.set_auth_system(auth_system)
    
    # Ensure backward compatibility
    chatbot = BackwardCompatibilityWrapper.ensure_compatibility(chatbot)
    
    return chatbot


# Export enhanced functions for external use
__all__ = [
    'ChatbotGUI',
    'ChatbotManager', 
    'create_chatbot_with_gui',
    'run_enhanced_chatbot',
    'BackwardCompatibilityWrapper'
]


# Integration test function
def test_gui_integration():
    """Test GUI integration with existing chatbot"""
    print("Testing GUI integration...")
    
    try:
        # Test basic chatbot creation
        chatbot = UniversityChatbot()
        print("✓ Chatbot created successfully")
        
        # Test GUI availability
        if LIBRARIES_AVAILABLE.get('tkinter', False):
            print("✓ tkinter available")
            
            # Test GUI creation (don't run mainloop)
            gui = ChatbotGUI(chatbot)
            print("✓ GUI interface created successfully")
            
            # Test manager
            manager = ChatbotManager(chatbot)
            modes = manager.get_available_modes()
            print(f"✓ Available modes: {modes}")
            
        else:
            print("✗ tkinter not available - GUI disabled")
        
        # Test backward compatibility
        enhanced_chatbot = BackwardCompatibilityWrapper.ensure_compatibility(chatbot)
        print("✓ Backward compatibility ensured")
        
        print("✓ All GUI integration tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ GUI integration test failed: {e}")
        return False


# Example usage documentation
USAGE_EXAMPLES = """
GUI Usage Examples:

# Start with GUI (recommended)
python university_chatbot.py

# Create chatbot with GUI programmatically
from university_chatbot import create_chatbot_with_gui, ChatbotManager

chatbot = create_chatbot_with_gui()
manager = ChatbotManager(chatbot)
manager.run_interface("gui")

# Run specific interface mode
manager.run_interface("console")  # Console only
manager.run_interface("gui")      # GUI only  
manager.run_interface("auto")     # Best available

# Backward compatibility - existing code still works
chatbot = UniversityChatbot()
chatbot.run()  # Will now prefer GUI if available

Features:
- Modern GUI with voice support
- Authentication integration
- Real-time chat interface
- Settings and preferences
- Voice recording and playback
- Quick action buttons
- Responsive design
- Error handling and recovery
"""
    
# Main execution enhancement
if __name__ == "__main__":
    # Initialize enhanced chatbot with authentication
    try:
        chatbot = UniversityChatbot()
        
        # Choose interface mode
        if AUTH_AVAILABLE and chatbot.auth_system:
            print("Authentication system available!")
            mode = input("Choose interface mode (console/web/auth-console/both): ").lower()
        else:
            mode = input("Choose interface mode (console/web/both): ").lower()
        
        if mode == "console":
            chatbot.run_console_interface()
        elif mode == "auth-console" and AUTH_AVAILABLE:
            chatbot.run_authenticated_console_interface()
        elif mode == "web":
            if AUTH_AVAILABLE:
                chatbot.setup_api_routes()
            chatbot.run_web_server()
        elif mode == "both":
            # Run web server in background, console in foreground
            if LIBRARIES_AVAILABLE['flask']:
                import threading
                if AUTH_AVAILABLE:
                    chatbot.setup_enhanced_api_routes()
                web_thread = threading.Thread(target=chatbot.run_web_server)
                web_thread.daemon = True
                web_thread.start()
                print("Web server started on http://localhost:5000")
                if AUTH_AVAILABLE:
                    print("Authentication API endpoints available:")
                    print("- POST /api/auth/login - Authenticate user")
                    print("- POST /api/auth/logout - Logout user")
                    print("- GET /api/auth/status - Check auth status")
                    print("- POST /api/chat/authenticated - Authenticated chat")
                    print("- POST /api/permissions/check - Check permissions")
            else:
                print("Flask not available - web server disabled")
            
            if AUTH_AVAILABLE and chatbot.auth_system:
                chatbot.run_authenticated_console_interface()
            else:
                chatbot.run_console_interface()
        else:
            print("Invalid mode selected. Starting console interface.")
            if AUTH_AVAILABLE and chatbot.auth_system:
                chatbot.run_authenticated_console_interface()
            else:
                chatbot.run_console_interface()
    
    except Exception as e:
        print(f"Failed to initialize chatbot: {e}")
        print("Please check your dependencies and try again.")
