"""
AI-Powered Features GUI

Comprehensive interface for AI chatbot, recommendations, auto-grading,
content suggestions, sentiment analysis, and plagiarism detection.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from datetime import datetime
from typing import Optional, List, Dict, Any
import traceback
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.database.schemas.ai_features_schemas import init_ai_features_system_db
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.shared.services.ai_features.ai_features_core import (
    ChatbotManager, RecommendationEngine, AutoGradingManager,
    ContentSuggestionManager, SentimentAnalysisManager, PlagiarismDetectionManager
)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t, _

# Import chatbot components
try:
    from education_system.university_system.infrastructure.ai.university_chatbot import UniversityChatbot
    from education_system.university_system.infrastructure.ai.gui.university_chatbot_gui import ChatbotGUI
    CHATBOT_AVAILABLE = True
except ImportError:
    UniversityChatbot = None
    ChatbotGUI = None
    CHATBOT_AVAILABLE = False


class AIFeaturesGUI:
    """Main GUI for AI-Powered Features"""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        self.root = root
        self.auth = auth
        self.window = None
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Permission check
        if not self.current_user:
            messagebox.showerror(_t("common.error"), _t("ai_features_gui.login_required"))
            return

        # Initialize database tables
        try:
            init_ai_features_system_db()
        except Exception as e:
            print(_t("ai_features.messages.init_db_warning", error=e))

        self.create_main_window()

    def create_main_window(self):
        """Create the main AI features window"""
        try:
            self.window = tk.Toplevel(self.root)
            self.window.title(_t("ai_features_gui.window_title"))
            self.window.geometry("1400x900")
            self.window.minsize(1200, 700)

            # Initialize status_bar FIRST to prevent AttributeError
            self.status_bar = None

            # Configure style
            style = ttk.Style()
            style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
            style.configure('Section.TLabel', font=('Arial', 12, 'bold'))
            style.configure('Accent.TButton', font=('Arial', 10, 'bold'))

            # Header frame with return button
            header_frame = ttk.Frame(self.window)
            header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

            ttk.Label(header_frame, text=_t("ai_features_gui.title"),
                     style='Header.TLabel').pack(side=tk.LEFT)

            ttk.Button(header_frame, text="← " + _t("common.return_to_main_menu"),
                      command=self.return_to_main_menu).pack(side=tk.RIGHT, padx=5)

            if self.current_user:
                user_info = _t("ai_features_gui.logged_in_as", username=self.current_user.get('username', 'User'))
                ttk.Label(header_frame, text=user_info,
                         font=('Arial', 10)).pack(side=tk.RIGHT, padx=10)

            # Main container with tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create tabs
            self.create_chatbot_tab()
            self.create_recommendations_tab()
            self.create_content_suggestions_tab()
            self.create_sentiment_tab()
            self.create_analytics_tab()

            # Status bar (already initialized to None earlier)
            self.status_bar = ttk.Label(self.window, text=_t("ai_features.status_ready"), relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            log_activity('Opened AI Features GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.create_window_error", error=str(e)))
            traceback.print_exc()

    def create_chatbot_tab(self):
        """Create the AI chatbot tab with launcher for full GUI"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("ai_features_gui.tabs.chatbot"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("ai_features_gui.chatbot.title"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Launch full chatbot GUI button
        ttk.Button(header_frame, text=_t("ai_features_gui.chatbot.launch_full"),
                  command=self.launch_full_chatbot_gui,
                  style='Accent.TButton').pack(side=tk.RIGHT, padx=5)

        # Info frame
        info_frame = ttk.LabelFrame(tab, text=_t("ai_features_gui.chatbot.about_title"), padding="20")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        info_text = """The University Chatbot provides AI-powered assistance for students, faculty, and staff.

Features:
• 24/7 automated support for common questions
• Natural language understanding
• Context-aware responses
• Multi-turn conversations
• Integration with university systems
• Personalized recommendations
• FAQ assistance
• Course information lookup
• Campus navigation help
• Administrative task guidance

The full chatbot interface provides an enhanced experience with:
✓ Rich conversation history
✓ Advanced query handling
✓ File attachment support
✓ Quick action buttons
✓ Personalized context
✓ Session management

Click the 'Launch Full Chatbot Interface' button above to access the complete chatbot experience.
"""

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=1000)
        info_label.pack(pady=10)

        # Quick stats
        stats_frame = ttk.LabelFrame(tab, text=_t("ai_features.chatbot.quick_stats"), padding="20")
        stats_frame.pack(fill=tk.X, padx=20, pady=10)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM ai_chatbot_conversations')
                total_conversations = cursor.fetchone()['count'] or 0

                cursor.execute('SELECT COUNT(*) as count FROM ai_chatbot_messages')
                total_messages = cursor.fetchone()['count'] or 0

                stats_text = _t("ai_features.chatbot.stats_combined", conversations=total_conversations, messages=total_messages)
                ttk.Label(stats_frame, text=stats_text, font=('Arial', 11)).pack()
        except Exception:
            ttk.Label(stats_frame, text=_t("ai_features.chatbot.stats_unavailable")).pack()

    def create_recommendations_tab(self):
        """Create the recommendations tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("ai_features.tabs.recommendations"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("ai_features.recommendations.title"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text=_t("ai_features.recommendations.generate"),
                  command=self.create_recommendation).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.refresh"),
                  command=self.load_recommendations).pack(side=tk.RIGHT, padx=5)

        # Recommendations list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.recommendations_tree = ttk.Treeview(tree_frame,
                                                columns=('ID', 'User', 'Type', 'Content',
                                                        'Algorithm', 'Confidence', 'Status', 'Created'),
                                                show='tree headings',
                                                yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.recommendations_tree.yview)

        self.recommendations_tree.heading('#0', text='')
        self.recommendations_tree.column('#0', width=30)

        column_names = ['id', 'user', 'type', 'content', 'algorithm', 'confidence', 'status', 'created']
        columns_config = [
            ('ID', 60), ('User', 100), ('Type', 150), ('Content', 300),
            ('Algorithm', 100), ('Confidence', 80), ('Status', 100), ('Created', 150)
        ]

        for (col, width), name in zip(columns_config, column_names):
            self.recommendations_tree.heading(col, text=_t(f"ai_features.columns.{name}"))
            self.recommendations_tree.column(col, width=width)

        self.recommendations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.recommendations_tree.bind('<Double-1>', self.view_recommendation_details)

        self.load_recommendations()

    def create_content_suggestions_tab(self):
        """Create the content suggestions tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("ai_features.tabs.content_suggestions"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("ai_features.content_suggestions.title"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text=_t("ai_features.content_suggestions.generate"),
                  command=self.create_content_suggestion).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.refresh"),
                  command=self.load_content_suggestions).pack(side=tk.RIGHT, padx=5)

        # Suggestions list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.suggestions_tree = ttk.Treeview(tree_frame,
                                            columns=('ID', 'Type', 'Context', 'Content',
                                                    'Relevance', 'Used', 'Created'),
                                            show='tree headings',
                                            yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.suggestions_tree.yview)

        self.suggestions_tree.heading('#0', text='')
        self.suggestions_tree.column('#0', width=30)

        column_names = ['id', 'type', 'context', 'content', 'relevance', 'used', 'created']
        columns_config = [
            ('ID', 60), ('Type', 150), ('Context', 200), ('Content', 300),
            ('Relevance', 80), ('Used', 80), ('Created', 150)
        ]

        for (col, width), name in zip(columns_config, column_names):
            self.suggestions_tree.heading(col, text=_t(f"ai_features.columns.{name}"))
            self.suggestions_tree.column(col, width=width)

        self.suggestions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_content_suggestions()

    def create_sentiment_tab(self):
        """Create the sentiment analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("ai_features.tabs.sentiment"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text=_t("ai_features.sentiment.title"),
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text=_t("ai_features.sentiment.analyze"),
                  command=self.analyze_sentiment).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text=_t("common.refresh"),
                  command=self.load_sentiment_analysis).pack(side=tk.RIGHT, padx=5)

        # Analysis results list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.sentiment_tree = ttk.Treeview(tree_frame,
                                          columns=('ID', 'Content ID', 'Type', 'Text',
                                                  'Score', 'Category', 'Analyzed'),
                                          show='tree headings',
                                          yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.sentiment_tree.yview)

        self.sentiment_tree.heading('#0', text='')
        self.sentiment_tree.column('#0', width=30)

        column_names = ['id', 'content_id', 'type', 'text', 'score', 'category', 'analyzed']
        columns_config = [
            ('ID', 60), ('Content ID', 100), ('Type', 120), ('Text', 300),
            ('Score', 80), ('Category', 100), ('Analyzed', 150)
        ]

        for (col, width), name in zip(columns_config, column_names):
            self.sentiment_tree.heading(col, text=_t(f"ai_features.columns.{name}"))
            self.sentiment_tree.column(col, width=width)

        # Color code by sentiment
        self.sentiment_tree.tag_configure('positive', background='#ccffcc')
        self.sentiment_tree.tag_configure('negative', background='#ffcccc')
        self.sentiment_tree.tag_configure('neutral', background='#ffffcc')

        self.sentiment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_sentiment_analysis()

    def create_analytics_tab(self):
        """Create the analytics and model performance tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("ai_features.tabs.analytics"))

        ttk.Label(tab, text=_t("ai_features.analytics.title"),
                 style='Header.TLabel').pack(pady=20)

        # Analytics frame
        analytics_frame = ttk.LabelFrame(tab, text=_t("ai_features.analytics.system_stats"), padding="20")
        analytics_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Stats display
        self.stats_text = scrolledtext.ScrolledText(analytics_frame, wrap=tk.WORD,
                                                    height=25, width=100)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text=_t("ai_features.analytics.refresh"),
                  command=self.load_ai_analytics).pack(side=tk.RIGHT)

        self.load_ai_analytics()

    # Data loading methods
    def load_conversations(self):
        """Load chat conversations"""
        try:
            for item in self.conversations_tree.get_children():
                self.conversations_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT conversation_id, start_time, message_count
                    FROM ai_chatbot_conversations
                    WHERE user_id = ?
                    ORDER BY start_time DESC
                    LIMIT 100
                ''', (str(self.current_user.get('id')),))

                for row in cursor.fetchall():
                    values = (
                        row['conversation_id'],
                        row['start_time'][:16] if row['start_time'] else '',
                        row['message_count'] or 0
                    )
                    self.conversations_tree.insert('', 'end', values=values)

            self.update_status(_t("ai_features.messages.conversations_loaded", count=len(self.conversations_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.load_conversations_error", error=str(e)))
            traceback.print_exc()

    def load_conversation_messages(self, event=None):
        """Load messages for selected conversation"""
        selection = self.conversations_tree.selection()
        if not selection:
            return

        try:
            conversation_id = self.conversations_tree.item(selection[0])['values'][0]
            self.current_conversation_id = conversation_id

            self.chat_display.config(state='normal')
            self.chat_display.delete('1.0', tk.END)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sender_type, message_text, timestamp
                    FROM ai_chatbot_messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp
                ''', (conversation_id,))

                for row in cursor.fetchall():
                    sender = "You" if row['sender_type'] == 'user' else "AI Assistant"
                    timestamp = row['timestamp'][:16] if row['timestamp'] else ''

                    self.chat_display.insert(tk.END, f"{sender}:\n",
                                           'user' if row['sender_type'] == 'user' else 'bot')
                    self.chat_display.insert(tk.END, f"{row['message_text']}\n\n")
                    self.chat_display.insert(tk.END, f"[{timestamp}]\n\n", 'timestamp')

            self.chat_display.config(state='disabled')
            self.chat_display.see(tk.END)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.load_messages_error", error=str(e)))

    def start_new_conversation(self):
        """Start a new chatbot conversation"""
        try:
            conversation_id = ChatbotManager.start_conversation(
                user_id=str(self.current_user.get('id')),
                user_type=self.current_user.get('role', 'user')
            )

            self.current_conversation_id = conversation_id
            self.chat_display.config(state='normal')
            self.chat_display.delete('1.0', tk.END)
            self.chat_display.insert(tk.END, _t("ai_features.chatbot.ai_greeting"), 'bot')
            self.chat_display.config(state='disabled')

            self.load_conversations()
            messagebox.showinfo(_t("common.success"), _t("ai_features.chatbot.new_conversation"))

            log_activity(f'Started AI conversation: {conversation_id}',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.chatbot.start_conversation_error", error=str(e)))

    def send_message(self):
        """Send a message in the chat"""
        if not self.current_conversation_id:
            messagebox.showwarning(_t("common.warning"), _t("ai_features.chatbot.no_conversation_selected"))
            return

        message = self.chat_input.get().strip()
        if not message:
            return

        try:
            # Add user message
            ChatbotManager.add_message(
                conversation_id=self.current_conversation_id,
                sender_type='user',
                message_text=message
            )

            # Display user message
            self.chat_display.config(state='normal')
            self.chat_display.insert(tk.END, "You:\n", 'user')
            self.chat_display.insert(tk.END, f"{message}\n\n")

            # Generate AI response (placeholder - in real system, call AI model)
            ai_response = self.generate_ai_response(message)

            # Add AI message
            ChatbotManager.add_message(
                conversation_id=self.current_conversation_id,
                sender_type='bot',
                message_text=ai_response,
                intent_detected='general_query',
                confidence_score=0.85
            )

            # Display AI response
            self.chat_display.insert(tk.END, "AI Assistant:\n", 'bot')
            self.chat_display.insert(tk.END, f"{ai_response}\n\n")

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            self.chat_display.insert(tk.END, f"[{timestamp}]\n\n", 'timestamp')

            self.chat_display.config(state='disabled')
            self.chat_display.see(tk.END)

            self.chat_input.delete(0, tk.END)
            self.load_conversations()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.chatbot.send_message_error", error=str(e)))

    def generate_ai_response(self, user_message: str) -> str:
        """Generate AI response (placeholder for actual AI integration)"""
        # In a real system, this would call an AI model/service
        responses = [
            "I understand. Let me help you with that.",
            "That's a great question! Here's what I can tell you...",
            "Based on the information available, I suggest...",
            "I'm here to assist. Could you provide more details?",
            "Thank you for reaching out. I can help with that."
        ]

        import random
        return random.choice(responses) + f" (Re: '{user_message[:50]}...')"

    def load_recommendations(self):
        """Load AI recommendations"""
        try:
            for item in self.recommendations_tree.get_children():
                self.recommendations_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_recommendations
                    ORDER BY created_at DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    content_preview = (row['recommendation_content'][:50] + '...') \
                                     if len(row['recommendation_content'] or '') > 50 \
                                     else (row['recommendation_content'] or '')

                    # Determine status based on was_accepted field
                    status = 'accepted' if row['was_accepted'] else 'pending'

                    values = (
                        row['recommendation_id'],
                        row['user_id'],
                        row['recommendation_type'],
                        content_preview,
                        row['algorithm_used'] or 'N/A',
                        f"{row['confidence_score']:.2f}" if row['confidence_score'] else '0.00',
                        status,
                        row['created_at'][:16] if row['created_at'] else ''
                    )
                    self.recommendations_tree.insert('', 'end', values=values)

            self.update_status(_t("ai_features.recommendations.loaded", count=len(self.recommendations_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.load_error", error=str(e)))

    def load_content_suggestions(self):
        """Load content suggestions"""
        try:
            for item in self.suggestions_tree.get_children():
                self.suggestions_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_content_suggestions
                    ORDER BY created_at DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    content_preview = (row['suggested_content'][:50] + '...') \
                                     if len(row['suggested_content'] or '') > 50 \
                                     else (row['suggested_content'] or '')

                    values = (
                        row['suggestion_id'],
                        row['content_type'],
                        (row['context'][:30] + '...') if len(row['context'] or '') > 30 else (row['context'] or ''),
                        content_preview,
                        f"{row['relevance_score']:.2f}" if row['relevance_score'] else '0.00',
                        'Yes' if row['was_used'] else 'No',
                        row['created_at'][:16] if row['created_at'] else ''
                    )
                    self.suggestions_tree.insert('', 'end', values=values)

            self.update_status(_t("ai_features.content_suggestions.loaded", count=len(self.suggestions_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.content_suggestions.load_error", error=str(e)))

    def load_sentiment_analysis(self):
        """Load sentiment analysis results"""
        try:
            for item in self.sentiment_tree.get_children():
                self.sentiment_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_sentiment_analysis
                    ORDER BY analyzed_at DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    text_preview = (row['content_text'][:50] + '...') \
                                  if len(row['content_text'] or '') > 50 \
                                  else (row['content_text'] or '')

                    values = (
                        row['analysis_id'],
                        row['content_id'],
                        row['content_type'],
                        text_preview,
                        f"{row['sentiment_score']:.2f}" if row['sentiment_score'] else '0.00',
                        row['sentiment_category'],
                        row['analyzed_at'][:16] if row['analyzed_at'] else ''
                    )

                    tag = row['sentiment_category'] if row['sentiment_category'] in ['positive', 'negative', 'neutral'] else ''
                    self.sentiment_tree.insert('', 'end', values=values, tags=(tag,))

            self.update_status(_t("ai_features.sentiment.loaded", count=len(self.sentiment_tree.get_children())))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.sentiment.load_error", error=str(e)))

    def load_ai_analytics(self):
        """Load AI system analytics"""
        try:
            self.stats_text.delete('1.0', tk.END)

            with get_connection() as conn:
                cursor = conn.cursor()

                stats = "="*80 + "\n"
                stats += _t("ai_features.analytics.header") + "\n"
                stats += "="*80 + "\n\n"

                # Chatbot stats
                cursor.execute('SELECT COUNT(*) as count, AVG(message_count) as avg_msgs FROM ai_chatbot_conversations')
                row = cursor.fetchone()
                stats += _t("ai_features.analytics.chatbot_stats") + "\n"
                stats += "  " + _t("ai_features.analytics.total_conversations", count=row['count'] or 0) + "\n"
                stats += "  " + _t("ai_features.analytics.avg_messages", avg=f"{(row['avg_msgs'] if row['avg_msgs'] else 0.0):.1f}") + "\n\n"

                # Recommendations stats
                cursor.execute('SELECT COUNT(*) as count, recommendation_type, AVG(confidence_score) as avg_conf FROM ai_recommendations GROUP BY recommendation_type')
                stats += _t("ai_features.analytics.recommendations_stats") + "\n"
                for row in cursor.fetchall():
                    stats += "  " + _t("ai_features.analytics.rec_type_line",
                                      type=row['recommendation_type'],
                                      count=row['count'],
                                      confidence=f"{(row['avg_conf'] if row['avg_conf'] else 0.0):.2f}") + "\n"
                stats += "\n"

                # Grading stats
                cursor.execute('SELECT COUNT(*) as count, AVG(auto_score/max_score*100) as avg_pct FROM ai_grading_results WHERE max_score > 0')
                row = cursor.fetchone()
                stats += _t("ai_features.analytics.grading_stats") + "\n"
                stats += "  " + _t("ai_features.analytics.total_graded", count=row['count'] or 0) + "\n"
                stats += "  " + _t("ai_features.analytics.avg_score", score=f"{(row['avg_pct'] if row['avg_pct'] else 0.0):.1f}") + "\n\n"

                # Plagiarism stats
                cursor.execute('SELECT COUNT(*) as count, AVG(similarity_score) as avg_sim FROM ai_plagiarism_checks')
                row = cursor.fetchone()
                stats += _t("ai_features.analytics.plagiarism_stats") + "\n"
                stats += "  " + _t("ai_features.analytics.total_checks", count=row['count'] or 0) + "\n"
                stats += "  " + _t("ai_features.analytics.avg_similarity", similarity=f"{(row['avg_sim']*100 if row['avg_sim'] else 0.0):.1f}") + "\n"

                cursor.execute('SELECT COUNT(*) as count FROM ai_plagiarism_checks WHERE flagged = 1')
                row = cursor.fetchone()
                stats += "  " + _t("ai_features.analytics.flagged_docs", count=row['count'] or 0) + "\n\n"

                # Sentiment stats
                cursor.execute('SELECT sentiment_category, COUNT(*) as count FROM ai_sentiment_analysis GROUP BY sentiment_category')
                stats += _t("ai_features.analytics.sentiment_stats") + "\n"
                for row in cursor.fetchall():
                    stats += "  " + _t("ai_features.analytics.sentiment_line", category=row['sentiment_category'].capitalize(), count=row['count']) + "\n"
                stats += "\n"

                stats += "="*80 + "\n"
                stats += _t("ai_features.analytics.generated_at", datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')) + "\n"
                stats += "="*80 + "\n"

                self.stats_text.insert('1.0', stats)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.analytics.load_error", error=str(e)))

    # Action methods
    def create_recommendation(self):
        """Create a new recommendation"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("ai_features.recommendations.create_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # User ID
        ttk.Label(main_frame, text=_t("ai_features.labels.user_id")).grid(row=0, column=0, sticky='w', pady=5)
        user_id_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=user_id_var, width=40).grid(row=0, column=1, pady=5)

        # Recommendation Type
        ttk.Label(main_frame, text=_t("ai_features.labels.type")).grid(row=1, column=0, sticky='w', pady=5)
        type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=type_var, width=38,
                                   values=['course', 'resource', 'activity', 'content', 'study_path'])
        type_combo.grid(row=1, column=1, pady=5)

        # Recommendation Content
        ttk.Label(main_frame, text=_t("ai_features.labels.content")).grid(row=2, column=0, sticky='nw', pady=5)
        content_text = tk.Text(main_frame, width=40, height=8)
        content_text.grid(row=2, column=1, pady=5)

        # Algorithm
        ttk.Label(main_frame, text=_t("ai_features.labels.algorithm")).grid(row=3, column=0, sticky='w', pady=5)
        algo_var = tk.StringVar(value='collaborative_filtering')
        ttk.Entry(main_frame, textvariable=algo_var, width=40).grid(row=3, column=1, pady=5)

        # Confidence Score
        ttk.Label(main_frame, text=_t("ai_features.labels.confidence_score")).grid(row=4, column=0, sticky='w', pady=5)
        conf_var = tk.StringVar(value='0.85')
        ttk.Entry(main_frame, textvariable=conf_var, width=40).grid(row=4, column=1, pady=5)

        # Context Data
        ttk.Label(main_frame, text=_t("ai_features.labels.context_data")).grid(row=5, column=0, sticky='nw', pady=5)
        context_text = tk.Text(main_frame, width=40, height=4)
        context_text.grid(row=5, column=1, pady=5)
        context_text.insert('1.0', '{}')

        def save_recommendation():
            try:
                user_id = user_id_var.get().strip()
                rec_type = type_var.get().strip()
                content = content_text.get('1.0', 'end').strip()
                algorithm = algo_var.get().strip()
                confidence = float(conf_var.get())
                context = context_text.get('1.0', 'end').strip()

                if not user_id or not rec_type or not content:
                    messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.fill_required"))
                    return

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO ai_recommendations
                        (user_id, recommendation_type, recommendation_content,
                         algorithm_used, confidence_score, context_data)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (user_id, rec_type, content, algorithm, confidence, context))

                messagebox.showinfo(_t("common.success"), _t("ai_features.recommendations.save_success"))
                log_activity('Created AI recommendation', user=self.current_user.get('username', 'Unknown'))
                dialog.destroy()
                self.load_recommendations()
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.save_error", error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.save"), command=save_recommendation).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def view_recommendation_details(self, event=None):
        """View recommendation details"""
        selection = self.recommendations_tree.selection()
        if not selection:
            messagebox.showinfo(_t("common.info"), _t("ai_features.recommendations.no_selection"))
            return

        item = self.recommendations_tree.item(selection[0])
        rec_id = item['values'][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_recommendations
                    WHERE recommendation_id = ?
                ''', (rec_id,))
                rec = cursor.fetchone()

                if not rec:
                    messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.not_found"))
                    return

                # Create details dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t("ai_features.recommendations.details_title", id=rec_id))
                dialog.geometry("700x600")
                dialog.transient(self.root)

                main_frame = ttk.Frame(dialog, padding=20)
                main_frame.pack(fill='both', expand=True)

                details = f"""
Recommendation ID: {rec['recommendation_id']}
User ID: {rec['user_id']}
Type: {rec['recommendation_type']}
Algorithm: {rec['algorithm_used'] or 'N/A'}
Confidence Score: {rec['confidence_score']:.2f if rec['confidence_score'] else 'N/A'}
Created: {rec['created_at']}
Was Accepted: {rec['was_accepted'] if rec['was_accepted'] is not None else 'Not yet'}
Feedback Rating: {rec['feedback_rating'] or 'No rating'}

Content:
{rec['recommendation_content']}

Context Data:
{rec['context_data'] or 'None'}
                """

                text_widget = tk.Text(main_frame, wrap='word', width=80, height=30)
                text_widget.pack(fill='both', expand=True)
                text_widget.insert('1.0', details.strip())
                text_widget.config(state='disabled')

                ttk.Button(main_frame, text=_t("ai_features.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.details_error", error=str(e)))

    def create_content_suggestion(self):
        """Create content suggestion"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("ai_features.content_suggestions.create_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Content Type
        ttk.Label(main_frame, text=_t("ai_features.labels.content_type")).grid(row=0, column=0, sticky='w', pady=5)
        type_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=type_var, width=38,
                    values=['text', 'image', 'video', 'quiz', 'resource']).grid(row=0, column=1, pady=5)

        # Context
        ttk.Label(main_frame, text=_t("ai_features.labels.context")).grid(row=1, column=0, sticky='nw', pady=5)
        context_text = tk.Text(main_frame, width=40, height=4)
        context_text.grid(row=1, column=1, pady=5)

        # Suggested Content
        ttk.Label(main_frame, text=_t("ai_features.labels.suggested_content")).grid(row=2, column=0, sticky='nw', pady=5)
        content_text = tk.Text(main_frame, width=40, height=8)
        content_text.grid(row=2, column=1, pady=5)

        # Relevance Score
        ttk.Label(main_frame, text=_t("ai_features.labels.relevance")).grid(row=3, column=0, sticky='w', pady=5)
        rel_var = tk.StringVar(value='0.9')
        ttk.Entry(main_frame, textvariable=rel_var, width=40).grid(row=3, column=1, pady=5)

        # Source
        ttk.Label(main_frame, text=_t("ai_features.labels.source")).grid(row=4, column=0, sticky='w', pady=5)
        source_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=source_var, width=40).grid(row=4, column=1, pady=5)

        # Created For
        ttk.Label(main_frame, text=_t("ai_features.labels.created_for")).grid(row=5, column=0, sticky='w', pady=5)
        for_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=for_var, width=40).grid(row=5, column=1, pady=5)

        def save_suggestion():
            try:
                content_type = type_var.get().strip()
                context = context_text.get('1.0', 'end').strip()
                content = content_text.get('1.0', 'end').strip()
                relevance = float(rel_var.get())
                source = source_var.get().strip()
                created_for = for_var.get().strip()

                if not content_type or not context or not content:
                    messagebox.showerror(_t("common.error"), _t("ai_features.recommendations.fill_required"))
                    return

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO ai_content_suggestions
                        (content_type, context, suggested_content, relevance_score, source, created_for)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (content_type, context, content, relevance, source, created_for))

                messagebox.showinfo(_t("common.success"), _t("ai_features.content_suggestions.save_success"))
                log_activity('Created content suggestion', user=self.current_user.get('username', 'Unknown'))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("ai_features.content_suggestions.save_error", error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.save"), command=save_suggestion).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def analyze_sentiment(self):
        """Analyze sentiment of text"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("ai_features.sentiment.analyze_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t("ai_features.sentiment.analyze_text_title"), font=('Arial', 12, 'bold')).pack(pady=10)

        # Content ID
        id_frame = ttk.Frame(main_frame)
        id_frame.pack(fill='x', pady=5)
        ttk.Label(id_frame, text=_t("ai_features.labels.content_id")).pack(side='left')
        content_id_var = tk.StringVar()
        ttk.Entry(id_frame, textvariable=content_id_var, width=30).pack(side='left', padx=5)

        # Content Type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill='x', pady=5)
        ttk.Label(type_frame, text=_t("ai_features.labels.content_type")).pack(side='left')
        type_var = tk.StringVar()
        ttk.Combobox(type_frame, textvariable=type_var, width=28,
                    values=['review', 'comment', 'feedback', 'essay', 'post']).pack(side='left', padx=5)

        # Text to analyze
        ttk.Label(main_frame, text=_t("ai_features.labels.text_to_analyze")).pack(anchor='w', pady=(10, 5))
        text_widget = tk.Text(main_frame, width=60, height=12)
        text_widget.pack(fill='both', expand=True, pady=5)

        result_label = ttk.Label(main_frame, text="", foreground='blue')
        result_label.pack(pady=10)

        def perform_analysis():
            try:
                content_id = content_id_var.get().strip()
                content_type = type_var.get().strip()
                text = text_widget.get('1.0', 'end').strip()

                if not content_id or not content_type or not text:
                    messagebox.showerror(_t("common.error"), _t("ai_features.sentiment.fill_all_fields"))
                    return

                # Simple sentiment analysis (placeholder - would use actual NLP library)
                positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love']
                negative_words = ['bad', 'terrible', 'awful', 'hate', 'horrible', 'poor', 'worst']

                text_lower = text.lower()
                pos_count = sum(word in text_lower for word in positive_words)
                neg_count = sum(word in text_lower for word in negative_words)

                if pos_count > neg_count:
                    sentiment = 'positive'
                    score = 0.6 + (pos_count * 0.1)
                elif neg_count > pos_count:
                    sentiment = 'negative'
                    score = 0.4 - (neg_count * 0.1)
                else:
                    sentiment = 'neutral'
                    score = 0.5

                score = max(0.0, min(1.0, score))

                with transaction() as conn:
                    conn.execute('''
                        INSERT INTO ai_sentiment_analysis
                        (content_id, content_type, content_text, sentiment_score, sentiment_category)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (content_id, content_type, text, score, sentiment))

                result_label.config(text=f"Sentiment: {sentiment.upper()} (Score: {score:.2f})")
                messagebox.showinfo(_t("common.success"), _t("ai_features.sentiment.analysis_complete", sentiment=sentiment.upper(), score=f"{score:.2f}"))
                log_activity('Performed sentiment analysis', user=self.current_user.get('username', 'Unknown'))

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("ai_features.sentiment.analysis_error", error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.analyze"), command=perform_analysis).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t("ai_features.buttons.close"), command=dialog.destroy).pack(side='left', padx=5)

    def update_status(self, message):
        """Update status bar"""
        if self.status_bar:
            self.status_bar.config(text=message)

    # Full GUI launchers
    def launch_full_chatbot_gui(self):
        """Launch the full University Chatbot GUI"""
        try:
            try:
                from education_system.university_system.infrastructure.ai.gui.university_chatbot_gui import ChatbotGUI
                from education_system.university_system.infrastructure.ai.university_chatbot import UniversityChatbot
            except ImportError as e:
                messagebox.showerror(
                    _t("common.error"),
                    f"Chatbot module not available: {str(e)}\n\nPlease ensure the chatbot module is installed."
                )
                return

            # Create or get chatbot instance
            try:
                chatbot_instance = UniversityChatbot()
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("ai_features.messages.chatbot_init_error", error=str(e)))
                return

            # Set authentication for chatbot
            if self.auth:
                try:
                    chatbot_instance.set_auth_system(self.auth)
                except AttributeError:
                    pass  # Chatbot may not have this method

            # Create chatbot window
            chatbot_window = tk.Toplevel(self.root)
            chatbot_window.title(_t("ai_features.window_titles.university_chatbot"))
            chatbot_window.geometry("1000x700")

            chatbot_gui = ChatbotGUI(chatbot_instance, chatbot_window, auth_system=self.auth)
            print(_t("ai_features.messages.chatbot_opened"))

            log_activity('Launched University Chatbot GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.chatbot_launch_error", error=str(e)))
            traceback.print_exc()

    def launch_full_ai_detector_gui(self):
        """Launch the full AI Detector GUI"""
        try:
            from education_system.university_system.modules.domain.academics.gui.ai_detector import AIDetectorGUI

            # Create AI detector window
            ai_window = tk.Toplevel(self.root)
            ai_window.title(_t("ai_features.window_titles.ai_content_detector"))
            ai_window.geometry("1000x700")

            ai_gui = AIDetectorGUI(ai_window, self.auth)
            print(_t("ai_features.messages.ai_detector_opened"))

            log_activity('Launched AI Content Detector GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.ai_detector_launch_error", error=str(e)))
            traceback.print_exc()

    def launch_full_plagiarism_gui(self):
        """Launch the full Plagiarism Detector GUI"""
        try:
            from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui import PlagiarismCheckerGUI

            # Create plagiarism detector window
            plagiarism_window = tk.Toplevel(self.root)
            plagiarism_window.title(_t("ai_features.window_titles.plagiarism_detection"))
            plagiarism_window.geometry("1200x800")

            plagiarism_gui = PlagiarismCheckerGUI(plagiarism_window, self.auth)
            print(_t("ai_features.messages.plagiarism_opened"))

            log_activity('Launched Plagiarism Detection GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("ai_features.messages.plagiarism_launch_error", error=str(e)))
            traceback.print_exc()

    def return_to_main_menu(self):
        """Return to main menu by closing the AI features window"""
        if messagebox.askyesno(_t("common.confirm"), _t("ai_features.messages.return_confirm")):
            try:
                # Log the action
                if self.current_user:
                    log_activity('Closed AI Features',
                               user=self.current_user.get('username', 'Unknown'))

                # Close the window
                self.window.destroy()
                print(_t("ai_features.messages.closed"))
            except Exception as e:
                print(_t("ai_features.messages.close_error", error=e))
                if self.window:
                    self.window.destroy()


def launch_ai_features_gui(root, auth):
    """Launch the AI Features GUI"""
    try:
        gui = AIFeaturesGUI(root, auth)
        print(_t("ai_features.messages.gui_opened"))
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("ai_features.messages.launch_error", error=str(e)))
        traceback.print_exc()


__all__ = ['AIFeaturesGUI', 'launch_ai_features_gui']
