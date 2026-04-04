"""Tests for QuestionAnalysisService."""

import pytest


class TestQuestionAnalysisService:
    @pytest.fixture
    def service(self, db_path):
        from education_system.college_system.modules.domain.question_analysis.services.question_analysis_service import QuestionAnalysisService
        return QuestionAnalysisService(db_path)

    @pytest.fixture
    def sample_paper(self, service):
        return service.create_paper(
            course_id=1, title="Maths Paper 1",
            total_marks=100, exam_board="AQA",
            paper_code="MAT01", assessment_date="2026-06-10",
        )

    def test_create_paper(self, service):
        paper = service.create_paper(
            course_id=1, title="Physics Paper 2",
            total_marks=80, exam_board="OCR",
        )
        assert paper is not None

    def test_list_papers(self, service):
        service.create_paper(course_id=1, title="Paper A", total_marks=60)
        service.create_paper(course_id=2, title="Paper B", total_marks=80)
        papers = service.list_papers()
        assert len(papers) >= 2

    def test_list_papers_filter_course(self, service):
        service.create_paper(course_id=3, title="Specific", total_marks=50)
        papers = service.list_papers(course_id=3)
        assert all(p["course_id"] == 3 for p in papers)

    def test_add_question(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        q = service.add_question(
            paper_id=paper_id, question_number=1,
            topic="Algebra", max_marks=10, subtopic="Quadratics",
        )
        assert q is not None

    def test_list_questions(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        service.add_question(paper_id=paper_id, question_number=1, topic="Algebra", max_marks=5)
        service.add_question(paper_id=paper_id, question_number=2, topic="Geometry", max_marks=8)
        questions = service.list_questions(paper_id)
        assert len(questions) >= 2

    def test_record_score(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        q = service.add_question(paper_id=paper_id, question_number=1, topic="Stats", max_marks=10)
        q_id = q if isinstance(q, int) else q.get("id", q)
        result = service.record_score(question_id=q_id, student_id=1, marks_awarded=7)
        assert result is not None

    def test_get_question_analysis(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        q = service.add_question(paper_id=paper_id, question_number=1, topic="Calc", max_marks=10)
        q_id = q if isinstance(q, int) else q.get("id", q)
        service.record_score(question_id=q_id, student_id=1, marks_awarded=8)
        analysis = service.get_question_analysis(paper_id)
        assert analysis is not None

    def test_get_topic_analysis(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        q = service.add_question(paper_id=paper_id, question_number=1, topic="Trig", max_marks=10)
        q_id = q if isinstance(q, int) else q.get("id", q)
        service.record_score(question_id=q_id, student_id=1, marks_awarded=6)
        analysis = service.get_topic_analysis(paper_id)
        assert analysis is not None

    def test_get_cohort_weaknesses(self, service, sample_paper):
        paper_id = sample_paper if isinstance(sample_paper, int) else sample_paper.get("id", sample_paper)
        q = service.add_question(paper_id=paper_id, question_number=1, topic="Vectors", max_marks=10)
        q_id = q if isinstance(q, int) else q.get("id", q)
        service.record_score(question_id=q_id, student_id=1, marks_awarded=3)
        weaknesses = service.get_cohort_weaknesses(paper_id, threshold=50)
        assert isinstance(weaknesses, list)
