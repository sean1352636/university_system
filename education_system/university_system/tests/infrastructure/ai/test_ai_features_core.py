"""
Test suite for ai_features_core.py

Tests all AI features managers: ChatbotManager, RecommendationEngine,
AutoGradingManager, ContentSuggestionManager, SentimentAnalysisManager,
and PlagiarismDetectionManager.
"""

import pytest
from datetime import datetime
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.database.schemas.ai_features_schemas import init_ai_features_system_db
from education_system.university_system.modules.shared.services.ai_features.ai_features_core import (
    ChatbotManager,
    RecommendationEngine,
    AutoGradingManager,
    ContentSuggestionManager,
    SentimentAnalysisManager,
    PlagiarismDetectionManager,
)


@pytest.fixture(scope="function")
def setup_db():
    """Setup test database with AI features tables"""
    try:
        init_ai_features_system_db()
    except Exception as e:
        print(f"Warning: Could not init AI features DB: {e}")

    yield

    # Cleanup test data
    try:
        with transaction() as conn:
            conn.execute("DELETE FROM ai_chatbot_conversations WHERE user_id LIKE 'test_%'")
            conn.execute("DELETE FROM ai_chatbot_messages")
            conn.execute("DELETE FROM ai_recommendations WHERE user_id LIKE 'test_%'")
            conn.execute("DELETE FROM ai_grading_results WHERE submission_id >= 9000")
            conn.execute("DELETE FROM ai_content_suggestions WHERE content_type = 'test'")
            conn.execute("DELETE FROM ai_sentiment_analysis WHERE content_id LIKE 'test_%'")
            conn.execute("DELETE FROM ai_plagiarism_checks WHERE student_id LIKE 'test_%'")
    except Exception as e:
        print(f"Cleanup warning: {e}")


class TestChatbotManager:
    """Test ChatbotManager functionality"""

    def test_start_conversation(self, setup_db):
        """Test starting a new conversation"""
        conversation_id = ChatbotManager.start_conversation(
            user_id='test_user_001',
            user_type='student'
        )
        assert conversation_id is not None
        assert isinstance(conversation_id, int)
        assert conversation_id > 0

    def test_start_multiple_conversations(self, setup_db):
        """Test starting multiple conversations"""
        conv_id1 = ChatbotManager.start_conversation('test_user_002', 'student')
        conv_id2 = ChatbotManager.start_conversation('test_user_002', 'student')

        assert conv_id1 != conv_id2
        assert conv_id1 > 0
        assert conv_id2 > 0

    def test_add_message(self, setup_db):
        """Test adding a message to a conversation"""
        conversation_id = ChatbotManager.start_conversation('test_user_003', 'student')

        message_id = ChatbotManager.add_message(
            conversation_id=conversation_id,
            sender_type='user',
            message_text='Hello, I need help with registration',
            intent_detected='registration_help',
            confidence_score=0.92
        )

        assert message_id is not None
        assert isinstance(message_id, int)
        assert message_id > 0

    def test_add_multiple_messages(self, setup_db):
        """Test adding multiple messages to a conversation"""
        conversation_id = ChatbotManager.start_conversation('test_user_004', 'student')

        msg_id1 = ChatbotManager.add_message(
            conversation_id, 'user', 'Hello'
        )
        msg_id2 = ChatbotManager.add_message(
            conversation_id, 'bot', 'Hi! How can I help?'
        )
        msg_id3 = ChatbotManager.add_message(
            conversation_id, 'user', 'I need course information'
        )

        assert msg_id1 < msg_id2 < msg_id3

    def test_message_increments_count(self, setup_db):
        """Test that adding messages increments conversation message count"""
        conversation_id = ChatbotManager.start_conversation('test_user_005', 'student')

        # Add 3 messages
        for i in range(3):
            ChatbotManager.add_message(conversation_id, 'user', f'Message {i}')

        # Verify message count
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT message_count FROM ai_chatbot_conversations WHERE conversation_id = ?',
                (conversation_id,)
            )
            row = cursor.fetchone()
            assert row['message_count'] == 3

    def test_add_message_with_confidence(self, setup_db):
        """Test adding message with confidence score"""
        conversation_id = ChatbotManager.start_conversation('test_user_006', 'student')

        message_id = ChatbotManager.add_message(
            conversation_id, 'user', 'Test message',
            intent_detected='test_intent',
            confidence_score=0.85
        )

        # Verify confidence stored
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT confidence_score FROM ai_chatbot_messages WHERE message_id = ?',
                (message_id,)
            )
            row = cursor.fetchone()
            assert abs(row['confidence_score'] - 0.85) < 0.001


class TestRecommendationEngine:
    """Test RecommendationEngine functionality"""

    def test_create_recommendation(self, setup_db):
        """Test creating a recommendation"""
        rec_id = RecommendationEngine.create_recommendation(
            user_id='test_user_007',
            recommendation_type='course',
            recommendation_content='Consider taking CS101 next semester',
            algorithm_used='collaborative_filtering',
            confidence_score=0.88
        )

        assert rec_id is not None
        assert isinstance(rec_id, int)
        assert rec_id > 0

    def test_create_different_recommendation_types(self, setup_db):
        """Test creating recommendations of different types"""
        types = ['course', 'resource', 'activity', 'study_path']

        for rec_type in types:
            rec_id = RecommendationEngine.create_recommendation(
                user_id='test_user_008',
                recommendation_type=rec_type,
                recommendation_content=f'Test {rec_type} recommendation'
            )
            assert rec_id > 0

    def test_recommendation_with_all_parameters(self, setup_db):
        """Test creating recommendation with all optional parameters"""
        rec_id = RecommendationEngine.create_recommendation(
            user_id='test_user_009',
            recommendation_type='content',
            recommendation_content='Read Chapter 5 for better understanding',
            algorithm_used='content_based_filtering',
            confidence_score=0.75
        )

        # Verify all fields stored
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM ai_recommendations WHERE recommendation_id = ?',
                (rec_id,)
            )
            row = cursor.fetchone()
            assert row['user_id'] == 'test_user_009'
            assert row['recommendation_type'] == 'content'
            assert 'Chapter 5' in row['recommendation_content']
            assert row['algorithm_used'] == 'content_based_filtering'
            assert abs(row['confidence_score'] - 0.75) < 0.001


class TestAutoGradingManager:
    """Test AutoGradingManager functionality"""

    def test_grade_submission(self, setup_db):
        """Test grading a submission"""
        grading_id = AutoGradingManager.grade_submission(
            submission_id=9001,
            assignment_type='essay',
            auto_score=85.0,
            max_score=100.0,
            feedback_generated='Good work, but could improve structure',
            confidence_score=0.82,
            requires_manual_review=False
        )

        assert grading_id is not None
        assert isinstance(grading_id, int)
        assert grading_id > 0

    def test_grade_different_assignment_types(self, setup_db):
        """Test grading different assignment types"""
        assignment_types = ['essay', 'quiz', 'project', 'homework', 'exam']

        for idx, atype in enumerate(assignment_types):
            grading_id = AutoGradingManager.grade_submission(
                submission_id=9010 + idx,
                assignment_type=atype,
                auto_score=80.0,
                max_score=100.0
            )
            assert grading_id > 0

    def test_grade_with_manual_review_flag(self, setup_db):
        """Test grading with manual review required"""
        grading_id = AutoGradingManager.grade_submission(
            submission_id=9020,
            assignment_type='essay',
            auto_score=65.0,
            max_score=100.0,
            requires_manual_review=True
        )

        # Verify flag stored
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT requires_manual_review FROM ai_grading_results WHERE grading_id = ?',
                (grading_id,)
            )
            row = cursor.fetchone()
            assert row['requires_manual_review'] == 1

    def test_grade_with_perfect_score(self, setup_db):
        """Test grading with perfect score"""
        grading_id = AutoGradingManager.grade_submission(
            submission_id=9030,
            assignment_type='quiz',
            auto_score=100.0,
            max_score=100.0,
            feedback_generated='Perfect score!',
            confidence_score=1.0
        )
        assert grading_id > 0


class TestContentSuggestionManager:
    """Test ContentSuggestionManager functionality"""

    def test_create_suggestion(self, setup_db):
        """Test creating a content suggestion"""
        suggestion_id = ContentSuggestionManager.create_suggestion(
            content_type='test',
            context='Student struggling with algebra',
            suggested_content='Watch Khan Academy video on quadratic equations',
            relevance_score=0.91
        )

        assert suggestion_id is not None
        assert isinstance(suggestion_id, int)
        assert suggestion_id > 0

    def test_create_different_content_types(self, setup_db):
        """Test creating suggestions for different content types"""
        content_types = ['text', 'image', 'video', 'quiz', 'resource']

        for ctype in content_types:
            suggestion_id = ContentSuggestionManager.create_suggestion(
                content_type='test',
                context=f'Context for {ctype}',
                suggested_content=f'Test {ctype} content'
            )
            assert suggestion_id > 0

    def test_suggestion_with_high_relevance(self, setup_db):
        """Test creating suggestion with high relevance score"""
        suggestion_id = ContentSuggestionManager.create_suggestion(
            content_type='test',
            context='Perfect match context',
            suggested_content='Highly relevant content',
            relevance_score=0.98
        )

        # Verify relevance score
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT relevance_score FROM ai_content_suggestions WHERE suggestion_id = ?',
                (suggestion_id,)
            )
            row = cursor.fetchone()
            assert abs(row['relevance_score'] - 0.98) < 0.001


class TestSentimentAnalysisManager:
    """Test SentimentAnalysisManager functionality"""

    def test_analyze_positive_sentiment(self, setup_db):
        """Test analyzing positive sentiment"""
        analysis_id = SentimentAnalysisManager.analyze_sentiment(
            content_id='test_content_001',
            content_type='review',
            content_text='This course is excellent! I learned so much.',
            sentiment_score=0.85,
            sentiment_category='positive'
        )

        assert analysis_id is not None
        assert isinstance(analysis_id, int)
        assert analysis_id > 0

    def test_analyze_negative_sentiment(self, setup_db):
        """Test analyzing negative sentiment"""
        analysis_id = SentimentAnalysisManager.analyze_sentiment(
            content_id='test_content_002',
            content_type='feedback',
            content_text='The assignment was too difficult and unclear.',
            sentiment_score=0.25,
            sentiment_category='negative'
        )
        assert analysis_id > 0

    def test_analyze_neutral_sentiment(self, setup_db):
        """Test analyzing neutral sentiment"""
        analysis_id = SentimentAnalysisManager.analyze_sentiment(
            content_id='test_content_003',
            content_type='comment',
            content_text='The course was okay, nothing special.',
            sentiment_score=0.5,
            sentiment_category='neutral'
        )
        assert analysis_id > 0

    def test_different_content_types(self, setup_db):
        """Test sentiment analysis on different content types"""
        content_types = ['review', 'comment', 'feedback', 'essay', 'post']

        for idx, ctype in enumerate(content_types):
            analysis_id = SentimentAnalysisManager.analyze_sentiment(
                content_id=f'test_content_{100 + idx}',
                content_type=ctype,
                content_text='Test sentiment content',
                sentiment_score=0.6,
                sentiment_category='positive'
            )
            assert analysis_id > 0


class TestPlagiarismDetectionManager:
    """Test PlagiarismDetectionManager functionality"""

    def test_check_plagiarism_low_similarity(self, setup_db):
        """Test plagiarism check with low similarity (not flagged)"""
        check_id = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9100,
            student_id='test_student_001',
            document_text='Original work by the student',
            similarity_score=0.15,
            matched_sources=''
        )

        assert check_id is not None
        assert isinstance(check_id, int)
        assert check_id > 0

        # Verify not flagged
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT flagged FROM ai_plagiarism_checks WHERE check_id = ?',
                (check_id,)
            )
            row = cursor.fetchone()
            assert row['flagged'] == 0

    def test_check_plagiarism_high_similarity(self, setup_db):
        """Test plagiarism check with high similarity (flagged)"""
        check_id = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9200,
            student_id='test_student_002',
            document_text='Copied content from multiple sources',
            similarity_score=0.65,
            matched_sources='Wikipedia, Other essay'
        )

        # Verify flagged (>30% threshold)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT flagged FROM ai_plagiarism_checks WHERE check_id = ?',
                (check_id,)
            )
            row = cursor.fetchone()
            assert row['flagged'] == 1

    def test_check_plagiarism_threshold_boundary(self, setup_db):
        """Test plagiarism check at 30% threshold"""
        # Just below threshold
        check_id1 = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9300,
            student_id='test_student_003',
            document_text='Test document',
            similarity_score=0.29
        )

        # At threshold
        check_id2 = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9301,
            student_id='test_student_004',
            document_text='Test document',
            similarity_score=0.30
        )

        # Just above threshold
        check_id3 = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9302,
            student_id='test_student_005',
            document_text='Test document',
            similarity_score=0.31
        )

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT flagged FROM ai_plagiarism_checks WHERE check_id = ?', (check_id1,))
            assert cursor.fetchone()['flagged'] == 0

            cursor.execute('SELECT flagged FROM ai_plagiarism_checks WHERE check_id = ?', (check_id2,))
            assert cursor.fetchone()['flagged'] == 0

            cursor.execute('SELECT flagged FROM ai_plagiarism_checks WHERE check_id = ?', (check_id3,))
            assert cursor.fetchone()['flagged'] == 1

    def test_check_with_matched_sources(self, setup_db):
        """Test plagiarism check with matched sources"""
        check_id = PlagiarismDetectionManager.check_plagiarism(
            submission_id=9400,
            student_id='test_student_006',
            document_text='Document with sources',
            similarity_score=0.45,
            matched_sources='Source A, Source B, Source C'
        )

        # Verify sources stored
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT matched_sources FROM ai_plagiarism_checks WHERE check_id = ?',
                (check_id,)
            )
            row = cursor.fetchone()
            assert 'Source A' in row['matched_sources']
            assert 'Source B' in row['matched_sources']


class TestErrorHandling:
    """Test error handling in managers"""

    def test_chatbot_invalid_conversation(self, setup_db):
        """Test adding message to non-existent conversation"""
        with pytest.raises(Exception):
            ChatbotManager.add_message(
                conversation_id=999999,
                sender_type='user',
                message_text='Test'
            )

    def test_empty_recommendation_content(self, setup_db):
        """Test creating recommendation with minimal data"""
        # Should still work with empty optional fields
        rec_id = RecommendationEngine.create_recommendation(
            user_id='test_user_999',
            recommendation_type='course',
            recommendation_content=''
        )
        assert rec_id > 0


class TestIntegration:
    """Integration tests across multiple managers"""

    def test_complete_chatbot_workflow(self, setup_db):
        """Test complete chatbot conversation workflow"""
        # Start conversation
        conv_id = ChatbotManager.start_conversation('test_user_integration', 'student')

        # Add user message
        msg1 = ChatbotManager.add_message(conv_id, 'user', 'Hello')

        # Add bot response
        msg2 = ChatbotManager.add_message(
            conv_id, 'bot', 'Hi! How can I help?',
            intent_detected='greeting', confidence_score=0.95
        )

        # Add follow-up
        msg3 = ChatbotManager.add_message(
            conv_id, 'user', 'I need help with courses',
            intent_detected='course_help', confidence_score=0.88
        )

        assert msg1 < msg2 < msg3

        # Verify conversation has 3 messages
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT message_count FROM ai_chatbot_conversations WHERE conversation_id = ?',
                (conv_id,)
            )
            assert cursor.fetchone()['message_count'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
