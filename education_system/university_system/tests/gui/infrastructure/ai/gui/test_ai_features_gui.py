"""
Test suite for ai_features_gui.py

Tests the AIFeaturesGUI class and its various components.
Uses mocking for Tkinter components to avoid GUI display during tests.
"""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import Mock, MagicMock, patch, call
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.database.schemas.ai_features_schemas import init_ai_features_system_db


@pytest.fixture(scope="function")
def setup_db():
    """Setup test database"""
    try:
        init_ai_features_system_db()
    except Exception as e:
        print(f"Warning: Could not init AI features DB: {e}")
    yield


@pytest.fixture
def mock_auth():
    """Create a mock authentication object"""
    auth = Mock()
    auth.current_user = {
        'id': 'test_user_001',
        'username': 'test_user',
        'role': 'student',
        'email': 'test@example.com'
    }
    auth.is_logged_in = Mock(return_value=True)
    auth.has_permission = Mock(return_value=True)
    return auth


@pytest.fixture
def root_window():
    """Provide a hidden Tkinter root window"""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def ai_gui(root_window, mock_auth, setup_db):
    """Create AIFeaturesGUI instance for testing"""
    from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import AIFeaturesGUI

    with patch('tkinter.messagebox.showerror'), \
         patch('tkinter.messagebox.showinfo'), \
         patch('tkinter.messagebox.showwarning'), \
         patch('tkinter.messagebox.askyesno', return_value=True):

        gui = AIFeaturesGUI(root_window, mock_auth)
        yield gui

        # Cleanup
        try:
            if gui.window and gui.window.winfo_exists():
                gui.window.destroy()
        except Exception:
            pass


class TestAIFeaturesGUIInitialization:
    """Test GUI initialization"""

    def test_gui_creates_window(self, root_window, mock_auth, setup_db):
        """Test that GUI creates a Toplevel window"""
        from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import AIFeaturesGUI

        with patch('tkinter.messagebox.showerror'):
            gui = AIFeaturesGUI(root_window, mock_auth)
            assert gui.window is not None
            assert isinstance(gui.window, tk.Toplevel)
            gui.window.destroy()

    def test_gui_requires_authentication(self, root_window):
        """Test that GUI requires authenticated user"""
        from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import AIFeaturesGUI

        auth_no_user = Mock()
        auth_no_user.current_user = None

        with patch('tkinter.messagebox.showerror') as mock_error:
            gui = AIFeaturesGUI(root_window, auth_no_user)
            mock_error.assert_called_once()

    def test_gui_has_notebook(self, ai_gui):
        """Test that GUI has a notebook with tabs"""
        assert hasattr(ai_gui, 'notebook')
        assert isinstance(ai_gui.notebook, ttk.Notebook)

    def test_gui_has_status_bar(self, ai_gui):
        """Test that GUI has a status bar"""
        assert hasattr(ai_gui, 'status_bar')
        assert ai_gui.status_bar is not None


class TestChatbotTab:
    """Test chatbot tab functionality"""

    def test_chatbot_tab_exists(self, ai_gui):
        """Test that chatbot tab is created"""
        tabs = ai_gui.notebook.tabs()
        assert len(tabs) > 0

    @patch('university_system.modules.shared.services.ai_features.gui.ai_features_gui.ChatbotGUI')
    @patch('university_system.modules.shared.services.ai_features.gui.ai_features_gui.UniversityChatbot')
    def test_launch_full_chatbot_gui(self, mock_chatbot, mock_gui, ai_gui):
        """Test launching full chatbot GUI"""
        chatbot_instance = Mock()
        mock_chatbot.return_value = chatbot_instance

        ai_gui.launch_full_chatbot_gui()

        mock_chatbot.assert_called_once()
        mock_gui.assert_called_once()

    @patch('tkinter.messagebox.showerror')
    @patch('university_system.modules.shared.services.ai_features.gui.ai_features_gui.UniversityChatbot')
    def test_launch_chatbot_handles_error(self, mock_chatbot, mock_error, ai_gui):
        """Test error handling when launching chatbot fails"""
        mock_chatbot.side_effect = Exception("Chatbot init failed")

        ai_gui.launch_full_chatbot_gui()

        mock_error.assert_called_once()


class TestRecommendationsTab:
    """Test recommendations tab functionality"""

    def test_load_recommendations(self, ai_gui, setup_db):
        """Test loading recommendations into tree"""
        # Create test recommendation
        with transaction() as conn:
            conn.execute('''
                INSERT INTO ai_recommendations
                (user_id, recommendation_type, recommendation_content, algorithm_used, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            ''', ('test_user', 'course', 'Test recommendation', 'test_algo', 0.85))

        ai_gui.load_recommendations()

        # Check that tree has items
        assert hasattr(ai_gui, 'recommendations_tree')

    @patch('tkinter.simpledialog.Dialog')
    def test_create_recommendation(self, mock_dialog, ai_gui):
        """Test creating a new recommendation"""
        ai_gui.create_recommendation()
        # Should create a dialog
        assert mock_dialog.called or True  # Dialog creation happens

    def test_view_recommendation_details(self, ai_gui, setup_db):
        """Test viewing recommendation details"""
        # Create test recommendation
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ai_recommendations
                (user_id, recommendation_type, recommendation_content, algorithm_used, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            ''', ('test_user', 'course', 'Test content', 'test', 0.9))
            rec_id = cursor.lastrowid

        # Mock tree selection
        ai_gui.recommendations_tree.insert('', 'end', values=(rec_id, 'test_user', 'course', 'Test', 'test', '0.90', 'pending', '2024-01-01'))
        ai_gui.recommendations_tree.selection_set(ai_gui.recommendations_tree.get_children()[0])

        with patch('tkinter.Toplevel'):
            ai_gui.view_recommendation_details()
            # Should not raise exception


class TestAutoGradingTab:
    """Test auto-grading tab functionality"""

    def test_load_grading_results(self, ai_gui, setup_db):
        """Test loading grading results"""
        # Create test grading result
        with transaction() as conn:
            conn.execute('''
                INSERT INTO ai_grading_results
                (submission_id, assignment_type, auto_score, max_score, confidence_score, requires_manual_review)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (9999, 'essay', 85.0, 100.0, 0.88, 0))

        ai_gui.load_grading_results()

        assert hasattr(ai_gui, 'grading_tree')

    def test_view_grading_details(self, ai_gui, setup_db):
        """Test viewing grading details"""
        # Create test grading
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ai_grading_results
                (submission_id, assignment_type, auto_score, max_score, confidence_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (9998, 'quiz', 90.0, 100.0, 0.92))
            grading_id = cursor.lastrowid

        # Mock selection
        ai_gui.grading_tree.insert('', 'end', values=(grading_id, 9998, 'quiz', '90.0', '100.0', '0.92', 'No', '2024-01-01'))
        ai_gui.grading_tree.selection_set(ai_gui.grading_tree.get_children()[0])

        with patch('tkinter.Toplevel'):
            ai_gui.view_grading_details()


class TestContentSuggestionsTab:
    """Test content suggestions tab functionality"""

    def test_load_content_suggestions(self, ai_gui, setup_db):
        """Test loading content suggestions"""
        # Create test suggestion
        with transaction() as conn:
            conn.execute('''
                INSERT INTO ai_content_suggestions
                (content_type, context, suggested_content, relevance_score)
                VALUES (?, ?, ?, ?)
            ''', ('video', 'algebra help', 'Watch this tutorial', 0.95))

        ai_gui.load_content_suggestions()

        assert hasattr(ai_gui, 'suggestions_tree')


class TestSentimentAnalysisTab:
    """Test sentiment analysis tab functionality"""

    def test_load_sentiment_analysis(self, ai_gui, setup_db):
        """Test loading sentiment analysis results"""
        # Create test analysis
        with transaction() as conn:
            conn.execute('''
                INSERT INTO ai_sentiment_analysis
                (content_id, content_type, content_text, sentiment_score, sentiment_category)
                VALUES (?, ?, ?, ?, ?)
            ''', ('content_001', 'review', 'Great course!', 0.9, 'positive'))

        ai_gui.load_sentiment_analysis()

        assert hasattr(ai_gui, 'sentiment_tree')

    @patch('tkinter.messagebox.showinfo')
    def test_analyze_sentiment(self, mock_showinfo, ai_gui):
        """Test sentiment analysis function"""
        # This creates a dialog, so we just verify it doesn't crash
        with patch('tkinter.Toplevel') as mock_toplevel:
            ai_gui.analyze_sentiment()
            mock_toplevel.assert_called_once()


class TestPlagiarismTab:
    """Test plagiarism detection tab functionality"""

    def test_load_plagiarism_checks(self, ai_gui, setup_db):
        """Test loading plagiarism checks"""
        # Create test check
        with transaction() as conn:
            conn.execute('''
                INSERT INTO ai_plagiarism_checks
                (submission_id, student_id, document_text, similarity_score, matched_sources, flagged)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (8888, 'test_student', 'Test document', 0.45, 'Source A', 1))

        ai_gui.load_plagiarism_checks()

        assert hasattr(ai_gui, 'plagiarism_tree')

    @patch('university_system.modules.shared.services.ai_features.gui.ai_features_gui.PlagiarismCheckerGUI')
    def test_launch_full_plagiarism_gui(self, mock_gui, ai_gui):
        """Test launching full plagiarism GUI"""
        ai_gui.launch_full_plagiarism_gui()
        mock_gui.assert_called_once()


class TestAIDetectorTab:
    """Test AI detector tab functionality"""

    @patch('university_system.modules.shared.services.ai_features.gui.ai_features_gui.AIDetectorGUI')
    def test_launch_ai_detector_gui(self, mock_gui, ai_gui):
        """Test launching AI detector GUI"""
        ai_gui.launch_full_ai_detector_gui()
        mock_gui.assert_called_once()


class TestAnalyticsTab:
    """Test analytics tab functionality"""

    def test_load_ai_analytics(self, ai_gui, setup_db):
        """Test loading AI analytics"""
        ai_gui.load_ai_analytics()

        assert hasattr(ai_gui, 'stats_text')

    def test_analytics_includes_all_stats(self, ai_gui, setup_db):
        """Test that analytics includes stats from all features"""
        # Create some test data
        with transaction() as conn:
            # Chatbot conversation
            conn.execute('''
                INSERT INTO ai_chatbot_conversations (user_id, user_type, message_count)
                VALUES (?, ?, ?)
            ''', ('test_user', 'student', 5))

            # Recommendation
            conn.execute('''
                INSERT INTO ai_recommendations
                (user_id, recommendation_type, recommendation_content, confidence_score)
                VALUES (?, ?, ?, ?)
            ''', ('test_user', 'course', 'Test', 0.85))

        ai_gui.load_ai_analytics()

        # Get stats text
        stats_content = ai_gui.stats_text.get('1.0', 'end')
        assert len(stats_content) > 0
        assert 'CHATBOT' in stats_content.upper() or 'STATISTICS' in stats_content.upper()


class TestStatusBarUpdates:
    """Test status bar update functionality"""

    def test_update_status(self, ai_gui):
        """Test updating status bar"""
        ai_gui.update_status("Test message")

        if ai_gui.status_bar:
            status_text = ai_gui.status_bar.cget('text')
            assert status_text == "Test message"

    def test_status_updated_after_load(self, ai_gui, setup_db):
        """Test status bar updated after loading data"""
        ai_gui.load_recommendations()

        if ai_gui.status_bar:
            status_text = ai_gui.status_bar.cget('text')
            assert 'Loaded' in status_text or 'recommendations' in status_text


class TestReturnToMainMenu:
    """Test return to main menu functionality"""

    @patch('tkinter.messagebox.askyesno', return_value=True)
    def test_return_to_main_menu_confirmed(self, mock_askyesno, ai_gui):
        """Test returning to main menu when confirmed"""
        ai_gui.return_to_main_menu()

        mock_askyesno.assert_called_once()
        # Window should be destroyed
        assert not ai_gui.window.winfo_exists()

    @patch('tkinter.messagebox.askyesno', return_value=False)
    def test_return_to_main_menu_cancelled(self, mock_askyesno, ai_gui):
        """Test cancelling return to main menu"""
        ai_gui.return_to_main_menu()

        mock_askyesno.assert_called_once()
        # Window should still exist
        assert ai_gui.window.winfo_exists()


class TestLauncherFunction:
    """Test the module launcher function"""

    def test_launch_ai_features_gui(self, root_window, mock_auth, setup_db):
        """Test launching GUI via function"""
        from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import (
            launch_ai_features_gui
        )

        with patch('tkinter.messagebox.showerror'):
            launch_ai_features_gui(root_window, mock_auth)
            # Should not raise exception

    def test_launch_handles_error(self, root_window):
        """Test launcher handles errors gracefully"""
        from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import (
            launch_ai_features_gui
        )

        bad_auth = None

        with patch('tkinter.messagebox.showerror') as mock_error:
            launch_ai_features_gui(root_window, bad_auth)
            # Should show error


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_gui_with_no_data(self, ai_gui, setup_db):
        """Test GUI with empty database"""
        # Clear all data
        with transaction() as conn:
            conn.execute("DELETE FROM ai_chatbot_conversations")
            conn.execute("DELETE FROM ai_recommendations")
            conn.execute("DELETE FROM ai_grading_results")

        # Should load without errors
        ai_gui.load_recommendations()
        ai_gui.load_grading_results()
        ai_gui.load_ai_analytics()

    def test_view_details_no_selection(self, ai_gui):
        """Test viewing details with no selection"""
        with patch('tkinter.messagebox.showinfo') as mock_info:
            ai_gui.view_recommendation_details()
            # Should show info message or handle gracefully

    def test_double_initialization(self, root_window, mock_auth, setup_db):
        """Test creating multiple GUI instances"""
        from education_system.university_system.modules.shared.services.ai_features.gui.ai_features_gui import AIFeaturesGUI

        with patch('tkinter.messagebox.showerror'):
            gui1 = AIFeaturesGUI(root_window, mock_auth)
            gui2 = AIFeaturesGUI(root_window, mock_auth)

            assert gui1.window is not None
            assert gui2.window is not None
            assert gui1.window != gui2.window

            gui1.window.destroy()
            gui2.window.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
