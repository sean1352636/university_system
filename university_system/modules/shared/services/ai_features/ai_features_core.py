"""
AI-Powered Features Core Service

Chatbot conversations, AI recommendations, auto-grading,
content suggestions, sentiment analysis, and plagiarism detection.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.feature_gui_factory import create_gui_launcher
from university_system.modules.shared.utils.i18n import get_text, _


class ChatbotManager:
    """Manages AI chatbot conversations"""

    @staticmethod
    def start_conversation(user_id: str, user_type: str) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_chatbot_conversations (user_id, user_type)
                VALUES (?, ?)
            ''', (user_id, user_type))
            conversation_id = cursor.lastrowid
            conn.commit()
            return conversation_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error starting conversation: {e}")
        finally:
            conn.close()

    @staticmethod
    def add_message(conversation_id: int, sender_type: str, message_text: str,
                   intent_detected: str = "", confidence_score: float = 0) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_chatbot_messages (
                    conversation_id, sender_type, message_text,
                    intent_detected, confidence_score
                ) VALUES (?, ?, ?, ?, ?)
            ''', (conversation_id, sender_type, message_text,
                  intent_detected, confidence_score))
            message_id = cursor.lastrowid

            # Update conversation message count
            cursor.execute('''
                UPDATE ai_chatbot_conversations
                SET message_count = message_count + 1
                WHERE conversation_id = ?
            ''', (conversation_id,))

            conn.commit()
            return message_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding message: {e}")
        finally:
            conn.close()


class RecommendationEngine:
    """Manages AI-powered recommendations"""

    @staticmethod
    def create_recommendation(user_id: str, recommendation_type: str,
                             recommendation_content: str, algorithm_used: str = "",
                             confidence_score: float = 0) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_recommendations (
                    user_id, recommendation_type, recommendation_content,
                    algorithm_used, confidence_score
                ) VALUES (?, ?, ?, ?, ?)
            ''', (user_id, recommendation_type, recommendation_content,
                  algorithm_used, confidence_score))
            recommendation_id = cursor.lastrowid
            conn.commit()
            return recommendation_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating recommendation: {e}")
        finally:
            conn.close()


class AutoGradingManager:
    """Manages AI-powered auto-grading"""

    @staticmethod
    def grade_submission(submission_id: int, assignment_type: str,
                        auto_score: float, max_score: float,
                        feedback_generated: str = "",
                        confidence_score: float = 0,
                        requires_manual_review: bool = False) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_grading_results (
                    submission_id, assignment_type, auto_score, max_score,
                    feedback_generated, confidence_score, requires_manual_review
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (submission_id, assignment_type, auto_score, max_score,
                  feedback_generated, confidence_score, requires_manual_review))
            grading_id = cursor.lastrowid
            conn.commit()
            return grading_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error grading submission: {e}")
        finally:
            conn.close()


class ContentSuggestionManager:
    """Manages AI-powered content suggestions"""

    @staticmethod
    def create_suggestion(content_type: str, context: str,
                         suggested_content: str, relevance_score: float = 0) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_content_suggestions (
                    content_type, context, suggested_content, relevance_score
                ) VALUES (?, ?, ?, ?)
            ''', (content_type, context, suggested_content, relevance_score))
            suggestion_id = cursor.lastrowid
            conn.commit()
            return suggestion_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating suggestion: {e}")
        finally:
            conn.close()


class SentimentAnalysisManager:
    """Manages sentiment analysis"""

    @staticmethod
    def analyze_sentiment(content_id: str, content_type: str, content_text: str,
                         sentiment_score: float, sentiment_category: str) -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ai_sentiment_analysis (
                    content_id, content_type, content_text,
                    sentiment_score, sentiment_category
                ) VALUES (?, ?, ?, ?, ?)
            ''', (content_id, content_type, content_text,
                  sentiment_score, sentiment_category))
            analysis_id = cursor.lastrowid
            conn.commit()
            return analysis_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error analyzing sentiment: {e}")
        finally:
            conn.close()


class PlagiarismDetectionManager:
    """Manages plagiarism detection"""

    @staticmethod
    def check_plagiarism(submission_id: int, student_id: str,
                        document_text: str, similarity_score: float,
                        matched_sources: str = "") -> int:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            flagged = similarity_score > 0.3  # Flag if >30% similar

            cursor.execute('''
                INSERT INTO ai_plagiarism_checks (
                    submission_id, student_id, document_text,
                    similarity_score, matched_sources, flagged
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (submission_id, student_id, document_text,
                  similarity_score, matched_sources, flagged))
            check_id = cursor.lastrowid
            conn.commit()
            return check_id
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error checking plagiarism: {e}")
        finally:
            conn.close()


def display_ai_features_menu(auth):
    """Display the AI-Powered Features CLI menu"""
    print("\n" + "="*50)
    print("        AI-POWERED FEATURES")
    print("="*50)
    print("1. AI Chatbot")
    print("2. Recommendation Engine")
    print("3. Auto-Grading System")
    print("4. Content Suggestions")
    print("5. Sentiment Analysis")
    print("6. Plagiarism Detection")
    print("7. AI Model Performance")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🤖 Feature available via AI managers")
                print("Use: from university_system.modules.shared.services.ai_features import ChatbotManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            break


def launch_ai_features_gui(root, auth):
    """Launch the AI-Powered Features GUI"""
    try:
        from university_system.modules.shared.services.ai_features.gui.ai_features_gui import (
            launch_ai_features_gui as launch_gui
        )
        launch_gui(root, auth)
    except ImportError:
        # Fallback to placeholder if GUI module not found
        placeholder = create_gui_launcher(
            title="AI-Powered Features",
            description="""AI-powered tools including chatbot, recommendations, and auto-grading.

Features:
• AI chatbot
• Recommendation engine
• Auto-grading system
• Content suggestions
• Sentiment analysis
• Plagiarism detection""",
            cli_instruction="Use CLI: AI-Powered Features"
        )
        placeholder(root, auth)



__all__ = [
    'ChatbotManager', 'RecommendationEngine', 'AutoGradingManager',
    'ContentSuggestionManager', 'SentimentAnalysisManager', 'PlagiarismDetectionManager',
    'display_ai_features_menu',
    'launch_ai_features_gui',
]
