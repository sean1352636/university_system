"""Basic CLI operations for the AI Detector."""


def _get_ai_detector():
    """Get the global ai_detector instance from the interface module."""
    import education_system.systems.university.interfaces.cli.shell.ai.ai_detector.interface as _iface
    return _iface.ai_detector


def analyze_text_interface_safe():
    """Safe version of text analysis interface"""
    ai_detector = _get_ai_detector()

    try:
        print("\nText Analysis for AI Detection")
        print("=" * 40)

        # Get basic inputs
        title = input("Enter submission title (optional): ").strip() or "Demo Analysis"

        print("\nEnter the text to analyze (press Enter twice to finish):")
        print("-" * 50)

        lines = []
        empty_lines = 0

        while empty_lines < 2:
            try:
                line = input()
                if line.strip() == "":
                    empty_lines += 1
                else:
                    empty_lines = 0
                lines.append(line)
            except KeyboardInterrupt:
                print("\nAnalysis cancelled.")
                return

        # Remove trailing empty lines
        while lines and lines[-1].strip() == "":
            lines.pop()

        text = "\n".join(lines)

        if not text.strip():
            print("\u274c No text provided for analysis.")
            return

        print(f"\nAnalyzing {len(text)} characters of text...")

        # Analyze the text with error handling
        try:
            result = ai_detector.analyze_text(text=text, title=title)
            display_analysis_results_safe(result)
        except Exception as analysis_error:
            print(f"\u274c Analysis failed: {analysis_error}")
            print("The AI detector may not be fully initialized.")

    except Exception as e:
        print(f"\u274c Interface error: {e}")


def display_analysis_results_safe(result):
    """Safe version of results display"""
    try:
        print("\n" + "=" * 60)
        print("AI DETECTION ANALYSIS RESULTS")
        print("=" * 60)

        print(f"Submission ID: {result.get('submission_id', 'N/A')}")
        print(f"AI Score: {result.get('ai_score', 0):.3f} (0.0 = Human, 1.0 = AI)")
        print(f"Confidence Level: {result.get('confidence', 0):.3f}")

        is_ai = result.get('is_ai_generated', False)
        status = "\U0001f916 LIKELY AI-GENERATED" if is_ai else "\U0001f464 LIKELY HUMAN-WRITTEN"
        print(f"Assessment: {status}")

        methods = result.get('detection_methods', [])
        print(f"Detection Methods Used: {', '.join(methods) if methods else 'Unknown'}")

        # Show text stats if available
        text_stats = result.get('text_stats', {})
        if text_stats:
            print("\nText Statistics:")
            print(f"  Word Count: {text_stats.get('word_count', 'N/A')}")
            print(f"  Character Count: {text_stats.get('char_count', 'N/A')}")
            print(f"  Sentence Count: {text_stats.get('sentence_count', 'N/A')}")

        # Show indicators if available
        indicators = result.get('indicators', [])
        if indicators:
            print("\nDetected Indicators:")
            for indicator in indicators:
                print(f"  \u2022 {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                evidence = indicator.get('evidence')
                if evidence:
                    print(f"    Evidence: {evidence}")

        mode = result.get('mode')
        if mode:
            print(f"\nMode: {mode}")

        print("=" * 60)

    except Exception as e:
        print(f"\u274c Error displaying results: {e}")
        print("Results could not be displayed properly.")

    input("\nPress Enter to continue...")


def view_submission_history_safe():
    """Safe version of submission history with proper error handling"""
    ai_detector = _get_ai_detector()

    try:
        print("\nSubmission History")
        print("=" * 30)

        # Try to get submissions with error handling
        try:
            submissions = ai_detector.list_submissions(limit=20)
        except Exception as list_error:
            print(f"\u274c Error accessing submission data: {list_error}")
            print("This might be a database schema issue. Attempting to fix...")

            # Try to fix the database schema
            from education_system.systems.university.interfaces.cli.shell.ai.ai_detector.interface import fix_ai_detector_database_schema
            if fix_ai_detector_database_schema():
                print("\u2705 Database schema fixed. Trying again...")
                try:
                    submissions = ai_detector.list_submissions(limit=20)
                except Exception as retry_error:
                    print(f"\u274c Still having issues: {retry_error}")
                    submissions = {'submissions': [], 'total': 0, 'error': str(retry_error)}
            else:
                submissions = {'submissions': [], 'total': 0, 'error': 'Database schema fix failed'}

        if not submissions.get('submissions'):
            reason = submissions.get('error') or submissions.get('message', 'No submissions found')
            print(f"No submission history available. Reason: {reason}")
        else:
            print(f"Showing {len(submissions['submissions'])} of {submissions['total']} submissions:")
            print()

            for submission in submissions['submissions']:
                try:
                    print(f"ID: {submission.get('id', 'N/A')}")

                    # Handle different possible column names
                    title = (submission.get('title') or
                            submission.get('submission_title') or
                            'Untitled')
                    print(f"Title: {title}")

                    print(f"Date: {submission.get('submission_date', 'N/A')}")

                    if submission.get('student_id'):
                        print(f"Student ID: {submission['student_id']}")
                    if submission.get('course_code'):
                        print(f"Course: {submission['course_code']}")

                    ai_score = submission.get('ai_score')
                    if ai_score is not None:
                        status = "AI-Generated" if ai_score >= ai_detector.detection_threshold else "Human-Written"
                        print(f"AI Score: {ai_score:.3f} ({status})")

                    print("-" * 40)

                except Exception as display_error:
                    print(f"\u274c Error displaying submission: {display_error}")
                    print(f"Raw data: {submission}")
                    print("-" * 40)

    except Exception as e:
        print(f"\u274c Error viewing history: {e}")
        print("The submission history feature is currently unavailable.")

    input("\nPress Enter to continue...")


def display_detailed_submission(submission):
    """Display detailed information about a submission"""
    print("\n" + "=" * 60)
    print("DETAILED SUBMISSION VIEW")
    print("=" * 60)

    print(f"Submission ID: {submission['id']}")
    print(f"Title: {submission['submission_title']}")
    print(f"Student ID: {submission.get('student_id', 'N/A')}")
    print(f"Course Code: {submission.get('course_code', 'N/A')}")
    print(f"Assignment ID: {submission.get('assignment_id', 'N/A')}")
    print(f"Submission Date: {submission['submission_date']}")
    print(f"Word Count: {submission['word_count']}")
    print(f"Character Count: {submission['character_count']}")

    if submission.get('results'):
        latest_result = submission['results'][0]  # Most recent result
        print("\nLatest Analysis:")
        print(f"AI Score: {latest_result['ai_score']:.3f}")
        print(f"Confidence: {latest_result['confidence_level']:.3f}")
        print(f"Detection Method: {latest_result['detection_method']}")
        print(f"Analysis Date: {latest_result['analysis_date']}")

        if latest_result.get('indicators_found'):
            print("\nIndicators Found:")
            for indicator in latest_result['indicators_found']:
                print(f"  \u2022 {indicator.get('name', 'Unknown')}: {indicator.get('score', 0):.3f}")
                if indicator.get('evidence'):
                    print(f"    Evidence: {indicator['evidence']}")

    print("=" * 60)
    input("\nPress Enter to continue...")


def view_ai_detector_statistics_safe():
    """Safe version of statistics viewing"""
    ai_detector = _get_ai_detector()

    try:
        print("\nAI Detector System Statistics")
        print("=" * 40)

        stats = ai_detector.get_enhanced_statistics()

        print(f"Detection Threshold: {stats.get('detection_threshold', 'Unknown')}")
        print(f"Total Submissions: {stats.get('total_submissions', 0)}")
        print(f"Unique Students: {stats.get('unique_students', 0)}")
        print(f"Average AI Score: {stats.get('average_ai_score', 0):.3f}")
        print(f"Recent Activity (7 days): {stats.get('recent_submissions_7_days', 0)}")
        print(f"High Risk Submissions: {stats.get('high_risk_submissions', 0)}")
        print(f"Database Status: {stats.get('database_status', 'Unknown')}")

        mode = stats.get('mode')
        if mode:
            print(f"Operating Mode: {mode}")

        print("=" * 40)

    except Exception as e:
        print(f"\u274c Error retrieving statistics: {e}")
        print("Statistics are not available at this time.")

    input("\nPress Enter to continue...")


def run_ai_detector_demo_safe():
    """Safe version of demo"""
    ai_detector = _get_ai_detector()

    try:
        print("\nRunning AI Detector Demo...")
        print("=" * 40)

        # Simple demo that should always work
        demo_text = "This is a demonstration of the AI content detection system. It analyzes text for patterns that might indicate artificial intelligence generation."

        result = ai_detector.analyze_text(
            text=demo_text,
            title="Demo Analysis"
        )

        display_analysis_results_safe(result)

    except Exception as e:
        print(f"\u274c Demo failed: {e}")
        print("This indicates the AI detector system needs attention.")

    input("\nPress Enter to continue...")
