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

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.database.schemas import init_ai_features_system_db
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.utils.activity_logger import log_activity
from university_system.modules.shared.services.ai_features.ai_features_core import (
    ChatbotManager, RecommendationEngine, AutoGradingManager,
    ContentSuggestionManager, SentimentAnalysisManager, PlagiarismDetectionManager
)


class AIFeaturesGUI:
    """Main GUI for AI-Powered Features"""

    def __init__(self, root, auth: Optional[UserAuth] = None):
        self.root = root
        self.auth = auth
        self.window = None
        self.current_user = auth.current_user if auth and auth.current_user else None

        # Permission check
        if not self.current_user:
            messagebox.showerror("Error", "You must be logged in to access AI Features.")
            return

        # Initialize database tables
        try:
            init_ai_features_system_db()
        except Exception as e:
            print(f"Warning: Could not initialize AI features database: {e}")

        self.create_main_window()

    def create_main_window(self):
        """Create the main AI features window"""
        try:
            self.window = tk.Toplevel(self.root)
            self.window.title("AI-Powered Features")
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

            ttk.Label(header_frame, text="AI-Powered Features",
                     style='Header.TLabel').pack(side=tk.LEFT)

            ttk.Button(header_frame, text="← Return to Main Menu",
                      command=self.return_to_main_menu).pack(side=tk.RIGHT, padx=5)

            if self.current_user:
                user_info = f"Logged in as: {self.current_user.get('username', 'User')}"
                ttk.Label(header_frame, text=user_info,
                         font=('Arial', 10)).pack(side=tk.RIGHT, padx=10)

            # Main container with tabs
            self.notebook = ttk.Notebook(self.window)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Create tabs
            self.create_chatbot_tab()
            self.create_ai_detector_tab()
            self.create_plagiarism_tab()
            self.create_recommendations_tab()
            self.create_autograding_tab()
            self.create_content_suggestions_tab()
            self.create_sentiment_tab()
            self.create_analytics_tab()

            # Status bar (already initialized to None earlier)
            self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

            log_activity('Opened AI Features GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create window: {str(e)}")
            traceback.print_exc()

    def create_chatbot_tab(self):
        """Create the AI chatbot tab with launcher for full GUI"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="University Chatbot")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="University Chatbot",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Launch full chatbot GUI button
        ttk.Button(header_frame, text="Launch Full Chatbot Interface",
                  command=self.launch_full_chatbot_gui,
                  style='Accent.TButton').pack(side=tk.RIGHT, padx=5)

        # Info frame
        info_frame = ttk.LabelFrame(tab, text="About University Chatbot", padding="20")
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
        stats_frame = ttk.LabelFrame(tab, text="Quick Statistics", padding="20")
        stats_frame.pack(fill=tk.X, padx=20, pady=10)

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM ai_chatbot_conversations')
                total_conversations = cursor.fetchone()['count'] or 0

                cursor.execute('SELECT COUNT(*) as count FROM ai_chatbot_messages')
                total_messages = cursor.fetchone()['count'] or 0

                stats_text = f"Total Conversations: {total_conversations}  |  Total Messages: {total_messages}"
                ttk.Label(stats_frame, text=stats_text, font=('Arial', 11)).pack()
        except:
            ttk.Label(stats_frame, text="Statistics unavailable").pack()

    def create_ai_detector_tab(self):
        """Create the AI detector tab with launcher for full GUI"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="AI Content Detector")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="AI Content Detection System",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Launch full AI detector GUI button
        ttk.Button(header_frame, text="Launch Full AI Detector",
                  command=self.launch_full_ai_detector_gui,
                  style='Accent.TButton').pack(side=tk.RIGHT, padx=5)

        # Info frame
        info_frame = ttk.LabelFrame(tab, text="About AI Content Detector", padding="20")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        info_text = """The AI Content Detector helps identify AI-generated content in student submissions.

Features:
• Detection of AI-generated text
• Multi-model analysis
• Confidence scoring
• Detailed reporting
• Batch processing support
• Multiple file format support (TXT, DOCX, PDF)
• Historical analysis tracking
• Comparison with known AI patterns

Detection Capabilities:
✓ GPT-based content detection
✓ Statistical analysis
✓ Pattern recognition
✓ Writing style analysis
✓ Linguistic markers
✓ Coherence patterns
✓ Vocabulary analysis
✓ Sentence structure analysis

The full AI Detector interface provides:
→ Advanced detection algorithms
→ Detailed analysis reports
→ Visual confidence indicators
→ Submission history
→ Export capabilities
→ Bulk processing

Click the 'Launch Full AI Detector' button above to access the complete detection system.
"""

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=1000)
        info_label.pack(pady=10)

    def create_recommendations_tab(self):
        """Create the recommendations tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Recommendations")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="AI Recommendations",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Generate Recommendation",
                  command=self.create_recommendation).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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

        columns_config = [
            ('ID', 60), ('User', 100), ('Type', 150), ('Content', 300),
            ('Algorithm', 100), ('Confidence', 80), ('Status', 100), ('Created', 150)
        ]

        for col, width in columns_config:
            self.recommendations_tree.heading(col, text=col)
            self.recommendations_tree.column(col, width=width)

        self.recommendations_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.recommendations_tree.bind('<Double-1>', self.view_recommendation_details)

        self.load_recommendations()

    def create_autograding_tab(self):
        """Create the auto-grading tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Auto-Grading")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="AI Auto-Grading System",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Grade Submission",
                  command=self.grade_submission).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
                  command=self.load_grading_results).pack(side=tk.RIGHT, padx=5)

        # Grading results list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.grading_tree = ttk.Treeview(tree_frame,
                                        columns=('ID', 'Submission', 'Type', 'Score',
                                                'Max', 'Confidence', 'Review', 'Graded'),
                                        show='tree headings',
                                        yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.grading_tree.yview)

        self.grading_tree.heading('#0', text='')
        self.grading_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Submission', 100), ('Type', 150), ('Score', 80),
            ('Max', 80), ('Confidence', 90), ('Review', 120), ('Graded', 150)
        ]

        for col, width in columns_config:
            self.grading_tree.heading(col, text=col)
            self.grading_tree.column(col, width=width)

        self.grading_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.grading_tree.bind('<Double-1>', self.view_grading_details)

        self.load_grading_results()

    def create_content_suggestions_tab(self):
        """Create the content suggestions tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Content Suggestions")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="AI Content Suggestions",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Generate Suggestion",
                  command=self.create_content_suggestion).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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

        columns_config = [
            ('ID', 60), ('Type', 150), ('Context', 200), ('Content', 300),
            ('Relevance', 80), ('Used', 80), ('Created', 150)
        ]

        for col, width in columns_config:
            self.suggestions_tree.heading(col, text=col)
            self.suggestions_tree.column(col, width=width)

        self.suggestions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_content_suggestions()

    def create_sentiment_tab(self):
        """Create the sentiment analysis tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Sentiment Analysis")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="AI Sentiment Analysis",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        ttk.Button(header_frame, text="Analyze Text",
                  command=self.analyze_sentiment).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh",
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

        columns_config = [
            ('ID', 60), ('Content ID', 100), ('Type', 120), ('Text', 300),
            ('Score', 80), ('Category', 100), ('Analyzed', 150)
        ]

        for col, width in columns_config:
            self.sentiment_tree.heading(col, text=col)
            self.sentiment_tree.column(col, width=width)

        # Color code by sentiment
        self.sentiment_tree.tag_configure('positive', background='#ccffcc')
        self.sentiment_tree.tag_configure('negative', background='#ffcccc')
        self.sentiment_tree.tag_configure('neutral', background='#ffffcc')

        self.sentiment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_sentiment_analysis()

    def create_plagiarism_tab(self):
        """Create the plagiarism detection tab with launcher for full GUI"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Plagiarism Detection")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(header_frame, text="Plagiarism Detection System",
                 style='Header.TLabel').pack(side=tk.LEFT, padx=10)

        # Launch full plagiarism GUI button
        ttk.Button(header_frame, text="Launch Full Plagiarism Checker",
                  command=self.launch_full_plagiarism_gui,
                  style='Accent.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Refresh Results",
                  command=self.load_plagiarism_checks).pack(side=tk.RIGHT, padx=5)

        # Plagiarism checks list
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)

        self.plagiarism_tree = ttk.Treeview(tree_frame,
                                           columns=('ID', 'Submission', 'Student', 'Similarity',
                                                   'Flagged', 'Sources', 'Checked'),
                                           show='tree headings',
                                           yscrollcommand=v_scroll.set)

        v_scroll.config(command=self.plagiarism_tree.yview)

        self.plagiarism_tree.heading('#0', text='')
        self.plagiarism_tree.column('#0', width=30)

        columns_config = [
            ('ID', 60), ('Submission', 100), ('Student', 120), ('Similarity', 90),
            ('Flagged', 80), ('Sources', 200), ('Checked', 150)
        ]

        for col, width in columns_config:
            self.plagiarism_tree.heading(col, text=col)
            self.plagiarism_tree.column(col, width=width)

        # Color code by similarity
        self.plagiarism_tree.tag_configure('high', background='#ffcccc')
        self.plagiarism_tree.tag_configure('medium', background='#ffffcc')
        self.plagiarism_tree.tag_configure('low', background='#ccffcc')

        self.plagiarism_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.load_plagiarism_checks()

    def create_analytics_tab(self):
        """Create the analytics and model performance tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="AI Analytics")

        ttk.Label(tab, text="AI Model Performance & Analytics",
                 style='Header.TLabel').pack(pady=20)

        # Analytics frame
        analytics_frame = ttk.LabelFrame(tab, text="System Statistics", padding="20")
        analytics_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Stats display
        self.stats_text = scrolledtext.ScrolledText(analytics_frame, wrap=tk.WORD,
                                                    height=25, width=100)
        self.stats_text.pack(fill=tk.BOTH, expand=True)

        # Refresh button
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(btn_frame, text="Refresh Statistics",
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

            self.update_status(f"Loaded {len(self.conversations_tree.get_children())} conversations")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load conversations: {str(e)}")
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
            messagebox.showerror("Error", f"Failed to load messages: {str(e)}")

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
            self.chat_display.insert(tk.END, "AI Assistant: Hello! How can I help you today?\n\n", 'bot')
            self.chat_display.config(state='disabled')

            self.load_conversations()
            messagebox.showinfo("Success", "New conversation started!")

            log_activity(f'Started AI conversation: {conversation_id}',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start conversation: {str(e)}")

    def send_message(self):
        """Send a message in the chat"""
        if not self.current_conversation_id:
            messagebox.showwarning("Warning", "Please start or select a conversation first")
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
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")

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
                    status = 'accepted' if row.get('was_accepted') else 'pending'

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

            self.update_status(f"Loaded {len(self.recommendations_tree.get_children())} recommendations")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load recommendations: {str(e)}")

    def load_grading_results(self):
        """Load auto-grading results"""
        try:
            for item in self.grading_tree.get_children():
                self.grading_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_grading_results
                    ORDER BY graded_at DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['grading_id'],
                        row['submission_id'],
                        row['assignment_type'],
                        f"{row['auto_score']:.1f}" if row['auto_score'] is not None else '0.0',
                        f"{row['max_score']:.1f}" if row['max_score'] is not None else '0.0',
                        f"{row['confidence_score']:.2f}" if row['confidence_score'] else '0.00',
                        'Yes' if row['requires_manual_review'] else 'No',
                        row['graded_at'][:16] if row['graded_at'] else ''
                    )
                    self.grading_tree.insert('', 'end', values=values)

            self.update_status(f"Loaded {len(self.grading_tree.get_children())} grading results")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load grading results: {str(e)}")

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

            self.update_status(f"Loaded {len(self.suggestions_tree.get_children())} content suggestions")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load content suggestions: {str(e)}")

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

            self.update_status(f"Loaded {len(self.sentiment_tree.get_children())} sentiment analyses")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sentiment analysis: {str(e)}")

    def load_plagiarism_checks(self):
        """Load plagiarism detection results"""
        try:
            for item in self.plagiarism_tree.get_children():
                self.plagiarism_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ai_plagiarism_checks
                    ORDER BY checked_at DESC
                    LIMIT 500
                ''')

                for row in cursor.fetchall():
                    similarity = row['similarity_score'] or 0
                    tag = 'high' if similarity > 0.5 else ('medium' if similarity > 0.3 else 'low')

                    values = (
                        row['check_id'],
                        row['submission_id'],
                        row['student_id'],
                        f"{similarity * 100:.1f}%",
                        'Yes' if row['flagged'] else 'No',
                        (row['matched_sources'][:30] + '...') if len(row['matched_sources'] or '') > 30 else (row['matched_sources'] or 'None'),
                        row['checked_at'][:16] if row['checked_at'] else ''
                    )

                    self.plagiarism_tree.insert('', 'end', values=values, tags=(tag,))

            self.update_status(f"Loaded {len(self.plagiarism_tree.get_children())} plagiarism checks")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load plagiarism checks: {str(e)}")

    def load_ai_analytics(self):
        """Load AI system analytics"""
        try:
            self.stats_text.delete('1.0', tk.END)

            with get_connection() as conn:
                cursor = conn.cursor()

                stats = "="*80 + "\n"
                stats += "AI-POWERED FEATURES - SYSTEM ANALYTICS\n"
                stats += "="*80 + "\n\n"

                # Chatbot stats
                cursor.execute('SELECT COUNT(*) as count, AVG(message_count) as avg_msgs FROM ai_chatbot_conversations')
                row = cursor.fetchone()
                stats += "CHATBOT STATISTICS:\n"
                stats += f"  Total Conversations: {row['count'] or 0}\n"
                stats += f"  Average Messages per Conversation: {row['avg_msgs']:.1f if row['avg_msgs'] else 0.0}\n\n"

                # Recommendations stats
                cursor.execute('SELECT COUNT(*) as count, recommendation_type, AVG(confidence_score) as avg_conf FROM ai_recommendations GROUP BY recommendation_type')
                stats += "RECOMMENDATIONS STATISTICS:\n"
                for row in cursor.fetchall():
                    stats += f"  {row['recommendation_type']}: {row['count']} ({row['avg_conf']:.2f if row['avg_conf'] else 0.0} avg confidence)\n"
                stats += "\n"

                # Grading stats
                cursor.execute('SELECT COUNT(*) as count, AVG(auto_score/max_score*100) as avg_pct FROM ai_grading_results WHERE max_score > 0')
                row = cursor.fetchone()
                stats += "AUTO-GRADING STATISTICS:\n"
                stats += f"  Total Submissions Graded: {row['count'] or 0}\n"
                stats += f"  Average Score: {row['avg_pct']:.1f if row['avg_pct'] else 0.0}%\n\n"

                # Plagiarism stats
                cursor.execute('SELECT COUNT(*) as count, AVG(similarity_score) as avg_sim FROM ai_plagiarism_checks')
                row = cursor.fetchone()
                stats += "PLAGIARISM DETECTION STATISTICS:\n"
                stats += f"  Total Checks: {row['count'] or 0}\n"
                stats += f"  Average Similarity: {row['avg_sim']*100:.1f if row['avg_sim'] else 0.0}%\n"

                cursor.execute('SELECT COUNT(*) as count FROM ai_plagiarism_checks WHERE flagged = 1')
                row = cursor.fetchone()
                stats += f"  Flagged Documents: {row['count'] or 0}\n\n"

                # Sentiment stats
                cursor.execute('SELECT sentiment_category, COUNT(*) as count FROM ai_sentiment_analysis GROUP BY sentiment_category')
                stats += "SENTIMENT ANALYSIS STATISTICS:\n"
                for row in cursor.fetchall():
                    stats += f"  {row['sentiment_category'].capitalize()}: {row['count']}\n"
                stats += "\n"

                stats += "="*80 + "\n"
                stats += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                stats += "="*80 + "\n"

                self.stats_text.insert('1.0', stats)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load analytics: {str(e)}")

    # Action methods (stubs - would implement full dialogs)
    def create_recommendation(self):
        """Create a new recommendation"""
        messagebox.showinfo("Create Recommendation", "Recommendation creation dialog would open here.")

    def view_recommendation_details(self, event=None):
        """View recommendation details"""
        selection = self.recommendations_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Recommendation Details", "Details dialog would open here.")

    def grade_submission(self):
        """Grade a submission"""
        messagebox.showinfo("Grade Submission", "Grading dialog would open here.")

    def view_grading_details(self, event=None):
        """View grading details"""
        selection = self.grading_tree.selection()
        if not selection:
            return
        messagebox.showinfo("Grading Details", "Details dialog would open here.")

    def create_content_suggestion(self):
        """Create content suggestion"""
        messagebox.showinfo("Content Suggestion", "Suggestion dialog would open here.")

    def analyze_sentiment(self):
        """Analyze sentiment of text"""
        messagebox.showinfo("Sentiment Analysis", "Analysis dialog would open here.")

    def check_plagiarism(self):
        """Check document for plagiarism"""
        messagebox.showinfo("Plagiarism Check", "Check dialog would open here.")

    def update_status(self, message):
        """Update status bar"""
        if self.status_bar:
            self.status_bar.config(text=message)

    # Full GUI launchers
    def launch_full_chatbot_gui(self):
        """Launch the full University Chatbot GUI"""
        try:
            from university_system.utils.ai.gui.university_chatbot_gui import ChatbotGUI
            from university_system.utils.ai.university_chatbot import UniversityChatbot

            # Create or get chatbot instance
            try:
                chatbot_instance = UniversityChatbot()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to initialize chatbot: {str(e)}")
                return

            # Set authentication for chatbot
            if self.auth:
                try:
                    chatbot_instance.set_auth_system(self.auth)
                except AttributeError:
                    pass  # Chatbot may not have this method

            # Create chatbot window
            chatbot_window = tk.Toplevel(self.root)
            chatbot_window.title("University Chatbot")
            chatbot_window.geometry("1000x700")

            chatbot_gui = ChatbotGUI(chatbot_instance, chatbot_window, auth_system=self.auth)
            print("✅ University Chatbot GUI opened successfully")

            log_activity('Launched University Chatbot GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Chatbot GUI: {str(e)}\n\nMake sure the chatbot backend is properly configured.")
            traceback.print_exc()

    def launch_full_ai_detector_gui(self):
        """Launch the full AI Detector GUI"""
        try:
            from university_system.modules.domain.academics.gui.ai_detector_gui import AIDetectorGUI

            # Create AI detector window
            ai_window = tk.Toplevel(self.root)
            ai_window.title("AI Content Detector")
            ai_window.geometry("1000x700")

            ai_gui = AIDetectorGUI(ai_window, self.auth)
            print("✅ AI Detector GUI opened successfully")

            log_activity('Launched AI Content Detector GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch AI Detector GUI: {str(e)}\n\nMake sure the AI detector backend is properly configured.")
            traceback.print_exc()

    def launch_full_plagiarism_gui(self):
        """Launch the full Plagiarism Detector GUI"""
        try:
            from university_system.modules.domain.academics.gui.plagiarism_main_gui import PlagiarismCheckerGUI

            # Create plagiarism detector window
            plagiarism_window = tk.Toplevel(self.root)
            plagiarism_window.title("Plagiarism Detection System")
            plagiarism_window.geometry("1200x800")

            plagiarism_gui = PlagiarismCheckerGUI(plagiarism_window, self.auth)
            print("✅ Plagiarism Detector GUI opened successfully")

            log_activity('Launched Plagiarism Detection GUI',
                        user=self.current_user.get('username', 'unknown'))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Plagiarism Detector GUI: {str(e)}\n\nMake sure the plagiarism detector backend is properly configured.")
            traceback.print_exc()

    def return_to_main_menu(self):
        """Return to main menu by closing the AI features window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            try:
                # Log the action
                if self.current_user:
                    log_activity('Closed AI Features',
                               user=self.current_user.get('username', 'Unknown'))

                # Close the window
                self.window.destroy()
                print("AI Features GUI closed")
            except Exception as e:
                print(f"Error closing AI Features GUI: {e}")
                if self.window:
                    self.window.destroy()


def launch_ai_features_gui(root, auth):
    """Launch the AI Features GUI"""
    try:
        gui = AIFeaturesGUI(root, auth)
        print("✅ AI-Powered Features GUI opened successfully")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch AI Features: {str(e)}")
        traceback.print_exc()


__all__ = ['AIFeaturesGUI', 'launch_ai_features_gui']
