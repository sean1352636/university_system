"""Question-Level Analysis CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.question_analysis.services.question_analysis_service import QuestionAnalysisService
from education_system.college_system.infrastructure.auth.core import UserAuth


def _list_papers(svc):
    """List assessment papers."""
    print_header("List Assessment Papers")
    course = input("  Course ID filter (Enter for all): ").strip()
    course_id = int(course) if course else None
    year = input("  Academic year filter (Enter for all): ").strip() or None
    try:
        papers = svc.list_papers(course_id=course_id, academic_year=year)
        if not papers:
            print("\n  No assessment papers found.")
        else:
            print(f"\n  {'ID':<5} {'Course':<8} {'Title':<25} {'Board':<12} {'Marks':>6} {'Date':<12}")
            print("  " + "-" * 72)
            for p in papers:
                print(f"  {p['id']:<5} {str(p.get('course_id') or '-'):<8} "
                      f"{(p.get('title') or '')[:25]:<25} "
                      f"{(p.get('exam_board') or '-'):<12} "
                      f"{p.get('total_marks', 0):>6} "
                      f"{(p.get('assessment_date') or '-'):<12}")
            print(f"\n  Total: {len(papers)} paper(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_paper(svc):
    """Create an assessment paper."""
    print_header("Create Assessment Paper")
    try:
        cid = input("  Course ID (blank=none): ").strip()
        cid = int(cid) if cid else None
        title = input("  Title: ").strip()
        if not title:
            print("\n  Error: Title is required.")
            return
        marks = int(input("  Total marks: ").strip())
        board = input("  Exam board (blank=none): ").strip() or None
        code = input("  Paper code (blank=none): ").strip() or None
        date = input("  Assessment date (YYYY-MM-DD, blank=none): ").strip() or None
        year = input("  Academic year (blank=none): ").strip() or None
        result = svc.create_paper(cid, title, marks, exam_board=board,
                                  paper_code=code, assessment_date=date,
                                  academic_year=year)
        pid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Paper #{pid} created.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_questions(svc):
    """View questions for a paper."""
    print_header("Paper Questions")
    try:
        pid = int(input("  Paper ID: ").strip())
        questions = svc.list_questions(pid)
        if not questions:
            print("\n  No questions found for this paper.")
        else:
            print(f"\n  {'ID':<5} {'Q#':<6} {'Topic':<20} {'Subtopic':<15} "
                  f"{'Max':>5} {'Skill':<12} {'Diff':<10}")
            print("  " + "-" * 78)
            for q in questions:
                print(f"  {q['id']:<5} {str(q.get('question_number', '')):<6} "
                      f"{(q.get('topic') or '')[:20]:<20} "
                      f"{(q.get('subtopic') or '-')[:15]:<15} "
                      f"{q.get('max_marks', 0):>5} "
                      f"{(q.get('skill_type') or '-'):<12} "
                      f"{(q.get('difficulty') or '-'):<10}")
            print(f"\n  Total: {len(questions)} question(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_question(svc):
    """Add a question to a paper."""
    print_header("Add Question to Paper")
    try:
        pid = int(input("  Paper ID: ").strip())
        qn = input("  Question number: ").strip()
        topic = input("  Topic: ").strip()
        if not qn or not topic:
            print("\n  Error: Question number and topic are required.")
            return
        mm = int(input("  Max marks: ").strip())
        subtopic = input("  Subtopic (blank=none): ").strip() or None
        skill = input("  Skill type (blank=none): ").strip() or None
        diff = input("  Difficulty (blank=none): ").strip() or None
        spec = input("  Specification ref (blank=none): ").strip() or None
        result = svc.add_question(pid, qn, topic, mm, subtopic=subtopic,
                                  skill_type=skill, difficulty=diff,
                                  specification_ref=spec)
        qid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Question #{qid} added to paper #{pid}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_score(svc):
    """Record a student score for a question."""
    print_header("Record Student Score")
    try:
        qid = int(input("  Question ID: ").strip())
        sid = int(input("  Student ID: ").strip())
        marks = int(input("  Marks awarded: ").strip())
        svc.record_score(qid, sid, marks)
        print("\n  Score recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _bulk_record_scores(svc):
    """Bulk record scores for a paper."""
    print_header("Bulk Record Scores")
    try:
        pid = int(input("  Paper ID: ").strip())
        scores = []
        print("  Enter scores (blank student ID to finish):")
        while True:
            sid = input("    Student ID: ").strip()
            if not sid:
                break
            qn = input("    Question number: ").strip()
            marks = int(input("    Marks awarded: ").strip())
            scores.append({"student_id": int(sid), "question_number": qn, "marks": marks})
        if not scores:
            print("\n  No scores entered.")
            return
        count = svc.bulk_record_scores(pid, scores)
        print(f"\n  {count} score(s) recorded for paper #{pid}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _question_analysis(svc):
    """Question-level analysis for a paper."""
    print_header("Question-Level Analysis")
    try:
        pid = int(input("  Paper ID: ").strip())
        analysis = svc.get_question_analysis(pid)
        if not analysis:
            print("\n  No analysis data available.")
        else:
            print(f"\n  {'Q#':<6} {'Avg Marks':>10} {'Max':>5} {'Facility %':>12}")
            print("  " + "-" * 38)
            for q in analysis:
                avg = q.get('avg_marks', 0) or 0
                mx = q.get('max_marks', 0)
                fi = q.get('facility_index', 0) or 0
                pct = fi * 100
                print(f"  {str(q.get('question_number', '')):<6} "
                      f"{avg:>10.1f} {mx:>5} {pct:>11.1f}%")
            print(f"\n  Total: {len(analysis)} question(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _topic_analysis(svc):
    """Topic-level analysis for a paper."""
    print_header("Topic Analysis")
    try:
        pid = int(input("  Paper ID: ").strip())
        topics = svc.get_topic_analysis(pid)
        if not topics:
            print("\n  No topic analysis data available.")
        else:
            print(f"\n  {'Topic':<25} {'Avg %':>8}")
            print("  " + "-" * 36)
            for t in topics:
                avg = t.get('avg_pct', 0) or 0
                print(f"  {(t.get('topic') or '-')[:25]:<25} {avg:>7.1f}%")
            print(f"\n  Total: {len(topics)} topic(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _cohort_weaknesses(svc):
    """Show cohort weaknesses below threshold."""
    print_header("Cohort Weaknesses")
    try:
        pid = int(input("  Paper ID: ").strip())
        threshold = input("  Threshold % (default 50): ").strip()
        threshold = int(threshold) if threshold else 50
        weak = svc.get_cohort_weaknesses(pid, threshold)
        if not weak:
            print(f"\n  No topics below {threshold}% threshold.")
        else:
            print(f"\n  Topics below {threshold}% threshold:")
            print(f"\n  {'Topic':<25} {'Avg %':>8}")
            print("  " + "-" * 36)
            for w in weak:
                avg = w.get('avg_pct', 0) or 0
                print(f"  {(w.get('topic') or '-')[:25]:<25} {avg:>7.1f}%")
            print(f"\n  {len(weak)} weak topic(s) identified.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _student_analysis(svc):
    """Per-student analysis for a paper."""
    print_header("Student Analysis")
    try:
        pid = int(input("  Paper ID: ").strip())
        sid = int(input("  Student ID: ").strip())
        result = svc.get_student_analysis(pid, sid)
        print(f"\n  Student {result['student_id']} — Paper {result['paper_id']}")
        print(f"  Overall: {result['total_marks']}/{result['total_max']} "
              f"({result['overall_pct']:.1f}%)")
        questions = result.get('questions', [])
        if questions:
            print(f"\n  {'Q#':<6} {'Topic':<20} {'Marks':>6} {'Max':>5} {'%':>7}")
            print("  " + "-" * 48)
            for q in questions:
                print(f"  {str(q.get('question_number', '')):<6} "
                      f"{(q.get('topic') or '')[:20]:<20} "
                      f"{q.get('marks_awarded', 0):>6} "
                      f"{q.get('max_marks', 0):>5} "
                      f"{q.get('pct', 0):>6.1f}%")
    except Exception as e:
        print(f"\n  Error: {e}")


def _skill_analysis(svc):
    """Skill type analysis for a paper."""
    print_header("Skill Type Analysis")
    try:
        pid = int(input("  Paper ID: ").strip())
        skills = svc.get_skill_analysis(pid)
        if not skills:
            print("\n  No skill analysis data available.")
        else:
            print(f"\n  {'Skill Type':<20} {'Questions':>10} {'Total Max':>10} {'Avg %':>8}")
            print("  " + "-" * 52)
            for s in skills:
                avg = s.get('avg_pct', 0) or 0
                print(f"  {(s.get('skill_type') or 'Unset'):<20} "
                      f"{s.get('num_questions', 0):>10} "
                      f"{s.get('total_max', 0):>10} "
                      f"{avg:>7.1f}%")
    except Exception as e:
        print(f"\n  Error: {e}")


def question_analysis_menu(auth: UserAuth):
    """Question-Level Analysis management menu."""
    svc = QuestionAnalysisService(auth._db_path)

    while True:
        print_header("Question-Level Analysis")
        options = [
            ("1", "List Assessment Papers"),
            ("2", "Create Paper"),
            ("3", "View Paper Questions"),
            ("4", "Add Question to Paper"),
            ("5", "Record Student Score"),
            ("6", "Bulk Record Scores"),
            ("7", "Question-Level Analysis"),
            ("8", "Topic Analysis"),
            ("9", "Cohort Weaknesses"),
            ("10", "Student Analysis"),
            ("11", "Skill Type Analysis"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_papers(svc)
        elif choice == "2":
            _create_paper(svc)
        elif choice == "3":
            _view_questions(svc)
        elif choice == "4":
            _add_question(svc)
        elif choice == "5":
            _record_score(svc)
        elif choice == "6":
            _bulk_record_scores(svc)
        elif choice == "7":
            _question_analysis(svc)
        elif choice == "8":
            _topic_analysis(svc)
        elif choice == "9":
            _cohort_weaknesses(svc)
        elif choice == "10":
            _student_analysis(svc)
        elif choice == "11":
            _skill_analysis(svc)
        else:
            print("\n  Invalid option.")
