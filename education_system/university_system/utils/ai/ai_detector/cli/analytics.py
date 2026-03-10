"""Analytics and visualization CLI functions for the AI Detector."""


def _get_ai_detector():
    """Get the global ai_detector instance from the interface module."""
    import education_system.university_system.utils.ai.ai_detector.cli.interface as _iface
    return _iface.ai_detector


def show_confidence_distribution_cli():
    """CLI interface for confidence distribution"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4ca Confidence Score Distribution")
    print("=" * 50)

    print("\nGenerating distribution...")
    result = ai_detector.show_detection_confidence_distribution()

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nTotal Analyzed: {result.get('total_analyzed', 0)}")

        ai_dist = result.get('ai_score_distribution', {})
        if ai_dist:
            print(f"\n\U0001f4c8 AI Score Statistics:")
            print(f"  Mean: {ai_dist.get('mean', 0):.3f}")
            print(f"  Median: {ai_dist.get('median', 0):.3f}")
            print(f"  Std Dev: {ai_dist.get('std_dev', 0):.3f}")

        chart = result.get('ascii_chart', '')
        if chart:
            print(f"\n{chart}")

    input("\nPress Enter to continue...")


def generate_word_cloud_cli():
    """CLI interface for word cloud generation"""
    ai_detector = _get_ai_detector()

    print("\n\u2601\ufe0f Generate Word Cloud Data")
    print("=" * 50)

    flagged_only = input("Analyze only flagged submissions? (y/n): ").strip().lower() == 'y'

    print("\nGenerating word cloud data...")
    result = ai_detector.generate_word_cloud(flagged_only=flagged_only)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nFlagged Submissions: {result.get('flagged_submissions_count', 0)}")
        print(f"Clean Submissions: {result.get('clean_submissions_count', 0)}")

        distinguishing = result.get('distinguishing_words_in_flagged', {})
        if distinguishing:
            print(f"\n\U0001f4cc Top Words More Common in Flagged Submissions:")
            for word, count in list(distinguishing.items())[:15]:
                print(f"  {word}: {count}")

    input("\nPress Enter to continue...")


def plot_submission_timeline_cli():
    """CLI interface for submission timeline"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4c5 Submission Timeline")
    print("=" * 50)

    student_id = input("Filter by student ID (optional): ").strip() or None
    days = input("Number of days to analyze (default: 30): ").strip()
    days = int(days) if days.isdigit() else 30

    print("\nGenerating timeline...")
    result = ai_detector.plot_submission_timeline(student_id=student_id, days=days)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nDays Analyzed: {result.get('days_analyzed', 0)}")
        print(f"Total Submissions: {result.get('total_submissions', 0)}")

        summary = result.get('summary', {})
        if summary:
            print(f"Busiest Day: {summary.get('busiest_day', 'N/A')}")
            print(f"Highest Risk Day: {summary.get('highest_risk_day', 'N/A')}")

        chart = result.get('ascii_visualization', '')
        if chart:
            print(f"\n{chart}")

    input("\nPress Enter to continue...")


def show_correlation_matrix_cli():
    """CLI interface for correlation matrix"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4ca Correlation Matrix")
    print("=" * 50)

    print("\nGenerating correlation matrix...")
    result = ai_detector.show_correlation_matrix()

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nSample Size: {result.get('sample_size', 0)}")

        matrix = result.get('ascii_matrix', '')
        if matrix:
            print(f"\n{matrix}")

        interpretations = result.get('interpretation', [])
        if interpretations:
            print(f"\n\U0001f4dd Interpretations:")
            for i in interpretations:
                print(f"  \u2022 {i}")

    input("\nPress Enter to continue...")


def cluster_similar_submissions_cli():
    """CLI interface for clustering similar submissions"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f50d Cluster Similar Submissions")
    print("=" * 50)
    print("Find suspiciously similar submissions using ML clustering.")

    print("\nClustering submissions...")
    result = ai_detector.cluster_similar_submissions()

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nSubmissions Analyzed: {result.get('total_submissions_analyzed', 0)}")
        print(f"Total Clusters: {result.get('total_clusters', 0)}")
        print(f"Suspicious Clusters: {result.get('suspicious_cluster_count', 0)}")
        print(f"Method: {result.get('method', 'N/A')}")

        clusters = result.get('suspicious_clusters', [])
        if clusters:
            print(f"\n\u26a0\ufe0f Suspicious Clusters:")
            for c in clusters[:5]:
                print(f"\n  Cluster {c.get('cluster_id')} [{c.get('suspicion_level', 'medium')}]:")
                print(f"    Size: {c.get('size', 0)} submissions")
                print(f"    Unique Students: {c.get('unique_students', 0)}")
                members = c.get('members', [])
                for m in members[:3]:
                    print(f"      \u2022 {m.get('student_id')}: {m.get('title', 'Untitled')[:30]}")

    input("\nPress Enter to continue...")


def generate_department_comparison_cli():
    """CLI interface for department comparison"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f3eb Department/Course Comparison")
    print("=" * 50)

    print("\nGenerating comparison...")
    result = ai_detector.generate_department_comparison()

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nCourses Analyzed: {result.get('courses_analyzed', 0)}")

        overall = result.get('overall_statistics', {})
        if overall:
            print(f"Mean AI Score: {overall.get('mean_ai_score', 0):.3f}")
            print(f"Highest Risk: {overall.get('highest_risk_course', 'N/A')}")
            print(f"Lowest Risk: {overall.get('lowest_risk_course', 'N/A')}")

        chart = result.get('ascii_chart', '')
        if chart:
            print(f"\n{chart}")

    input("\nPress Enter to continue...")


def show_weekly_trends_cli():
    """CLI interface for weekly trends"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4c8 Weekly Trends Analysis")
    print("=" * 50)

    weeks = input("Number of weeks to analyze (default: 12): ").strip()
    weeks = int(weeks) if weeks.isdigit() else 12

    print("\nGenerating weekly trends...")
    result = ai_detector.show_weekly_trends(weeks=weeks)

    if result.get('error'):
        print(f"\u274c Error: {result['error']}")
    else:
        print(f"\nWeeks Analyzed: {result.get('weeks_analyzed', 0)}")
        print(f"Overall Trend: {result.get('overall_trend', 'N/A')}")

        anomalies = result.get('anomalies', [])
        if anomalies:
            print(f"\n\u26a0\ufe0f Anomalies Detected ({len(anomalies)}):")
            for a in anomalies[:5]:
                print(f"  \u2022 {a.get('week')}: {a.get('type')} (value: {a.get('value')})")

        chart = result.get('ascii_chart', '')
        if chart:
            print(f"\n{chart}")

    input("\nPress Enter to continue...")


def export_visualization_pack_cli():
    """CLI interface for exporting visualization pack"""
    ai_detector = _get_ai_detector()

    print("\n\U0001f4e6 Export Visualization Pack")
    print("=" * 50)

    output_dir = input("Output directory (press Enter for default): ").strip() or None

    print("\nExporting visualization pack...")
    result = ai_detector.export_visualization_pack(output_dir=output_dir)

    if result.get('success'):
        print(f"\n\u2705 Export successful!")
        print(f"Directory: {result.get('export_directory', 'N/A')}")
        print(f"\n\U0001f4c1 Files Created:")
        for f in result.get('files_created', []):
            print(f"  \u2022 {f}")
        print(f"\n\U0001f4ca Visualizations Included:")
        for v in result.get('visualizations_included', []):
            print(f"  \u2022 {v}")
    else:
        print(f"\u274c Error: {result.get('error', 'Unknown error')}")

    input("\nPress Enter to continue...")
