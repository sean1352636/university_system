"""Demo and main entry point functions for the AI Detector CLI."""

from education_system.systems.university.infrastructure.ai.ai_detector.detector.main import AIDetector
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth


def ultimate_demo():
    """Fixed version of the ultimate demo"""
    print("Ultimate AI Detector Demo (Fixed)")
    print("=================================")

    try:
        # Initialize ultimate detector
        detector = AIDetector()

        # Set up authentication with demo user
        demo_auth = get_auth()
        if demo_auth is None:
            demo_auth = UserAuth()
        demo_auth.current_user = {'id': 1, 'username': 'demo_user', 'role': 'instructor'}
        detector.set_auth(demo_auth)

        print("\u2713 Ultimate AI Detector initialized with all features")

        # Test basic analysis first
        test_text = """
        Artificial intelligence has fundamentally transformed numerous aspects of contemporary society.
        However, it is important to note that these developments present both opportunities and challenges.
        """

        print(f"\nAnalyzing text ({len(test_text)} characters)...")

        # Run basic analysis first
        result = detector.analyze_text_enhanced(
            text=test_text,
            title="Demo Analysis",
            student_id="DEMO_STUDENT_001",
            course_code="CS499",
            assignment_id="DEMO_PROJECT"
        )

        print("\n\U0001f3af ANALYSIS RESULTS")
        print("=" * 30)
        print(f"AI Score: {result['ai_score']:.3f}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"AI Generated: {result['is_ai_generated']}")

        # Get statistics
        stats = detector.get_enhanced_statistics()
        print("\n\U0001f4c8 STATISTICS")
        print(f"Total Submissions: {stats['total_submissions']}")
        print(f"Unique Students: {stats['unique_students']}")
        print(f"Average AI Score: {stats['average_ai_score']:.3f}")

        print("\n\U0001f389 Demo completed successfully!")

    except Exception as e:
        print(f"\n\u274c Demo failed: {e}")
        import traceback
        print(traceback.format_exc())


# Main function
def main():
    """Main function for testing the ultimate detector"""
    print("Ultimate AI Detector - Advanced Testing Mode")
    print("=" * 50)

    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'ultimate_demo':
        ultimate_demo()
        return

    try:
        # Initialize ultimate detector
        detector = AIDetector()
        print("\u2713 Ultimate AI Detector initialized successfully!")

        # Get statistics
        stats = detector.get_ultimate_statistics()
        print(f"\u2713 System ready with {len(stats['features_active'])} advanced features")

        # List active features
        active_features = [name for name, active in stats['features_active'].items() if active]
        print(f"\u2713 Active features: {', '.join(active_features)}")

    except Exception as e:
        print(f"\u274c Error: {e}")
        print("This is expected if running standalone without proper database setup.")

if __name__ == "__main__":
    main()
