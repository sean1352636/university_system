"""Student management CLI functions for the AI Detector."""


def _get_ai_detector():
    """Get the global ai_detector instance from the interface module."""
    import education_system.systems.university.interfaces.cli.shell.ai.ai_detector.interface as _iface
    return _iface.ai_detector


def view_student_profile_cli():
    """CLI interface for viewing student profile"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f464 View Student Profile")
    print("=" * 50)

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    print("\nLoading student profile...")
    result = ai_detector.view_student_profile(student_id)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        profile = result.get('profile', {})
        print(f"\n{'='*50}")
        print(f"STUDENT PROFILE: {student_id}")
        print(f"{'='*50}")
        print(f"Total Submissions: {profile.get('total_submissions', 0)}")
        print(f"Risk Level: {profile.get('risk_level', 'unknown').upper()}")
        print(f"High Risk Submissions: {profile.get('high_risk_submissions', 0)}")
        print(f"Active Flags: {profile.get('active_flags', 0)}")

        stats = profile.get('ai_score_stats', {})
        print("\n\U0001f4ca AI Score Statistics:")
        print(f"  Average: {stats.get('average', 0):.3f}")
        print(f"  Min: {stats.get('min', 0):.3f}")
        print(f"  Max: {stats.get('max', 0):.3f}")
        print(f"  Std Dev: {stats.get('std_dev', 0):.3f}")

        courses = profile.get('courses', [])
        if courses:
            print(f"\n\U0001f4da Courses: {', '.join(courses)}")

        print(f"\n\U0001f4c5 First Submission: {profile.get('first_submission', 'N/A')}")
        print(f"\U0001f4c5 Last Submission: {profile.get('last_submission', 'N/A')}")
        print(f"\U0001f4dd Has Fingerprint: {'Yes' if profile.get('has_fingerprint') else 'No'}")

    input("\nPress Enter to continue...")


def compare_students_cli():
    """CLI interface for comparing two students"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f465 Compare Two Students")
    print("=" * 50)

    student_id_1 = input("Enter first student ID: ").strip()
    student_id_2 = input("Enter second student ID: ").strip()

    if not student_id_1 or not student_id_2:
        print("\u274c Both student IDs are required.")
        input("\nPress Enter to continue...")
        return

    print("\nComparing students...")
    result = ai_detector.compare_students(student_id_1, student_id_2)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\n{'='*50}")
        print("STUDENT COMPARISON RESULTS")
        print(f"{'='*50}")

        for key in ['student_1', 'student_2']:
            student = result.get(key, {})
            profile = student.get('profile', {})
            print(f"\n{student.get('id', 'N/A')}:")
            print(f"  Submissions: {profile.get('total_submissions', 0) if profile else 'N/A'}")
            print(f"  Risk Level: {profile.get('risk_level', 'N/A') if profile else 'N/A'}")

        similarity = result.get('similarity_analysis', {})
        if similarity:
            print("\n\U0001f4ca Similarity Analysis:")
            print(f"  Overall Similarity: {similarity.get('overall_similarity', 0):.3f}")
            print(f"  Interpretation: {similarity.get('interpretation', 'N/A')}")

            dims = similarity.get('dimension_similarities', {})
            if dims:
                for dim, score in dims.items():
                    print(f"    {dim}: {score:.3f}")

        if result.get('potential_collaboration'):
            print("\n\u26a0\ufe0f WARNING: Potential collaboration detected!")

    input("\nPress Enter to continue...")


def generate_student_report_card_cli():
    """CLI interface for generating student report card"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4cb Generate Student Report Card")
    print("=" * 50)

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    print("\nGenerating report card...")
    result = ai_detector.generate_student_report_card(student_id)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\n{'='*50}")
        print("ACADEMIC INTEGRITY REPORT CARD")
        print(f"Student: {result.get('student_id', 'N/A')}")
        print(f"{'='*50}")

        summary = result.get('summary', {})
        print("\n\U0001f4ca Summary:")
        print(f"  Integrity Grade: {summary.get('grade', 'N/A')}")
        print(f"  Integrity Score: {summary.get('integrity_score', 0):.2f}")
        print(f"  Risk Level: {summary.get('risk_level', 'unknown').upper()}")
        print(f"  Trend: {summary.get('trend', 'stable')}")

        stats = result.get('statistics', {})
        print("\n\U0001f4c8 Statistics:")
        print(f"  Total Submissions: {stats.get('total_submissions', 0)}")
        print(f"  High Risk Submissions: {stats.get('high_risk_submissions', 0)}")
        print(f"  Average AI Score: {stats.get('average_ai_score', 0):.3f}")

        recs = result.get('recommendations', [])
        if recs:
            print("\n\U0001f4dd Recommendations:")
            for r in recs:
                print(f"  \u2022 {r}")

    input("\nPress Enter to continue...")


def flag_student_for_review_cli():
    """CLI interface for flagging a student for review"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f6a9 Flag Student for Review")
    print("=" * 50)

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    reason = input("Enter reason for flagging: ").strip()
    if not reason:
        print("\u274c Reason is required.")
        input("\nPress Enter to continue...")
        return

    print("\nSeverity options: low, medium, high, critical")
    severity = input("Enter severity (default: medium): ").strip().lower() or 'medium'
    if severity not in ['low', 'medium', 'high', 'critical']:
        severity = 'medium'

    submission_id = input("Enter submission ID (optional): ").strip()
    submission_id = int(submission_id) if submission_id.isdigit() else None

    flagged_by = input("Your name/ID (optional): ").strip() or None

    print("\nFlagging student...")
    result = ai_detector.flag_student_for_review(
        student_id=student_id,
        reason=reason,
        flagged_by=flagged_by,
        severity=severity,
        submission_id=submission_id
    )

    if result.get('success'):
        print(f"\n\u2705 {result.get('message', 'Student flagged successfully')}")
        print(f"Flag ID: {result.get('flag_id', 'N/A')}")
        print(f"Severity: {result.get('severity', 'N/A')}")
    else:
        print(f"\u274c Error: {result.get('error', 'Unknown error')}")

    input("\nPress Enter to continue...")


def view_student_progression_cli():
    """CLI interface for viewing student progression"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4c8 View Student Progression")
    print("=" * 50)
    print("Track how student's writing has evolved over time.")

    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("\u274c Student ID is required.")
        input("\nPress Enter to continue...")
        return

    print("\nAnalyzing progression...")
    result = ai_detector.view_student_progression(student_id)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\n{'='*50}")
        print(f"STUDENT PROGRESSION: {student_id}")
        print(f"{'='*50}")
        print(f"Total Submissions: {result.get('total_submissions', 0)}")

        date_range = result.get('date_range', {})
        print(f"Date Range: {date_range.get('first', 'N/A')} to {date_range.get('last', 'N/A')}")

        trends = result.get('trends', {})
        if trends:
            print("\n\U0001f4ca Trends:")
            print(f"  AI Score Trend: {trends.get('ai_score_trend', 'N/A')}")
            print(f"  Vocabulary Trend: {trends.get('vocabulary_trend', 'N/A')}")
            print(f"  Complexity Trend: {trends.get('complexity_trend', 'N/A')}")

        anomalies = result.get('anomalies', [])
        if anomalies:
            print(f"\n\u26a0\ufe0f Anomalies Found ({len(anomalies)}):")
            for a in anomalies[:5]:
                print(f"  \u2022 {a.get('type')}: {a.get('direction', '')} on {a.get('date', 'N/A')}")

        print(f"\n\U0001f4dd Summary: {result.get('summary', 'No summary available.')}")

    input("\nPress Enter to continue...")


def bulk_student_analysis_cli():
    """CLI interface for bulk student analysis"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f465 Bulk Student Analysis")
    print("=" * 50)
    print("Analyze all submissions from a class/cohort at once.")

    print("\nOptions:")
    print("1. Analyze by course code")
    print("2. Analyze all students (limit 100)")

    choice = input("Select option (1-2): ").strip()

    course_code = None
    if choice == '1':
        course_code = input("Enter course code: ").strip()
        if not course_code:
            print("\u274c Course code is required for this option.")
            input("\nPress Enter to continue...")
            return

    print("\nAnalyzing students...")
    result = ai_detector.bulk_student_analysis(course_code=course_code)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\n{'='*50}")
        print("BULK ANALYSIS RESULTS")
        print(f"{'='*50}")

        cohort = result.get('cohort_statistics', {})
        print(f"Students Analyzed: {cohort.get('total_students', 0)}")
        print(f"Average AI Score: {cohort.get('avg_ai_score', 0):.3f}")
        print(f"High Risk Students: {cohort.get('high_risk_count', 0)}")

        dist = cohort.get('risk_distribution', {})
        if dist:
            print("\n\U0001f4ca Risk Distribution:")
            print(f"  Low: {dist.get('low', 0)}")
            print(f"  Medium: {dist.get('medium', 0)}")
            print(f"  High: {dist.get('high', 0)}")
            print(f"  Critical: {dist.get('critical', 0)}")

        high_risk = result.get('high_risk_students', [])
        if high_risk:
            print("\n\u26a0\ufe0f High Risk Students:")
            for s in high_risk[:10]:
                print(f"  \u2022 {s.get('student_id')}: {s.get('risk_level')} (avg: {s.get('avg_ai_score', 0):.3f})")

    input("\nPress Enter to continue...")
