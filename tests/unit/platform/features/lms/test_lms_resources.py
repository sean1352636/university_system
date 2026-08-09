"""Tests for LMS ResourceLibraryService."""
import pytest
import sqlite3


@pytest.fixture
def lms_db(tmp_path):
    db = str(tmp_path / "test_lms.db")
    conn = sqlite3.connect(db)
    from education_system.platform.features.lms.schema import create_lms_tables
    create_lms_tables(conn)
    conn.close()
    return db


@pytest.fixture
def course_id(lms_db):
    from education_system.platform.features.lms.course_management_service import CourseManagementService
    return CourseManagementService(lms_db).create_course("CS101", "inst1")


class TestUploadAndList:
    def test_upload_resource(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        rid = svc.upload_resource("Lecture Notes", "Week 1 notes", "/files/notes.pdf",
                                  resource_type="document", uploaded_by="inst1",
                                  course_id=course_id)
        assert rid is not None

    def test_list_resources_by_course(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        svc.upload_resource("Notes 1", "Desc", "/f1.pdf", course_id=course_id)
        svc.upload_resource("Notes 2", "Desc", "/f2.pdf", course_id=course_id)
        svc.upload_resource("Other", "Desc", "/f3.pdf", course_id=999)
        resources = svc.list_resources(course_id=course_id)
        assert len(resources) == 2

    def test_list_resources_by_type(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        svc.upload_resource("Video", "A video", "/v.mp4", resource_type="video", course_id=course_id)
        svc.upload_resource("Doc", "A doc", "/d.pdf", resource_type="document", course_id=course_id)
        videos = svc.list_resources(resource_type="video")
        assert len(videos) == 1
        assert videos[0]["title"] == "Video"


class TestDownload:
    def test_download_increments_count(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        rid = svc.upload_resource("Notes", "Desc", "/notes.pdf", course_id=course_id)
        r = svc.download_resource(rid)
        assert r["download_count"] == 1
        r = svc.download_resource(rid)
        assert r["download_count"] == 2

    def test_download_nonexistent(self, lms_db):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        assert svc.download_resource(9999) is None


class TestSearchAndDelete:
    def test_search_resources(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        svc.upload_resource("Python Tutorial", "Learn Python basics", "/py.pdf", course_id=course_id)
        svc.upload_resource("Java Guide", "Java programming", "/java.pdf", course_id=course_id)
        svc.upload_resource("Advanced Python", "Deep dive", "/py2.pdf", course_id=course_id)
        results = svc.search_resources("Python")
        assert len(results) == 2

    def test_search_by_description(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        svc.upload_resource("Notes", "Machine learning intro", "/ml.pdf", course_id=course_id)
        results = svc.search_resources("machine learning")
        assert len(results) == 1

    def test_delete_resource(self, lms_db, course_id):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        rid = svc.upload_resource("Temp", "Temporary", "temp.pdf", course_id=course_id)
        svc.delete_resource(rid)
        resources = svc.list_resources(course_id=course_id)
        assert len(resources) == 0

    def test_search_no_results(self, lms_db):
        from education_system.platform.features.lms.resource_library_service import ResourceLibraryService
        svc = ResourceLibraryService(lms_db)
        assert svc.search_resources("nonexistent") == []
