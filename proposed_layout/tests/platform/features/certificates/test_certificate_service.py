"""Tests for CertificateService."""

import pytest


@pytest.fixture
def cert_db(tmp_path):
    return str(tmp_path / "certs.db")


@pytest.fixture
def svc(cert_db):
    from education_system.platform.features.certificates.certificate_service import CertificateService
    return CertificateService(db_path=cert_db)


class TestGenerateCertificate:
    def test_returns_dict_with_certificate_number(self, svc):
        cert = svc.generate_certificate("STU001", "completion", "Mathematics",
                                         "2026-07-15", grade="A", issued_by="Prof X")
        assert isinstance(cert, dict)
        assert cert["certificate_number"].startswith("CERT-")
        assert cert["student_id"] == "STU001"
        assert cert["status"] == "active"

    def test_invalid_type_raises(self, svc):
        with pytest.raises(ValueError, match="Invalid certificate type"):
            svc.generate_certificate("STU001", "invalid_type", "Maths", "2026-01-01")

    def test_unique_certificate_numbers(self, svc):
        c1 = svc.generate_certificate("STU001", "completion", "Maths", "2026-01-01")
        c2 = svc.generate_certificate("STU002", "merit", "English", "2026-01-01")
        assert c1["certificate_number"] != c2["certificate_number"]


class TestListCertificates:
    def test_list_all(self, svc):
        svc.generate_certificate("STU001", "completion", "Maths", "2026-01-01")
        svc.generate_certificate("STU002", "merit", "English", "2026-02-01")
        certs = svc.list_certificates()
        assert len(certs) == 2

    def test_list_by_student(self, svc):
        svc.generate_certificate("STU001", "completion", "Maths", "2026-01-01")
        svc.generate_certificate("STU001", "attendance", "Science", "2026-02-01")
        svc.generate_certificate("STU002", "merit", "English", "2026-03-01")
        stu001 = svc.list_certificates(student_id="STU001")
        assert len(stu001) == 2

    def test_list_empty(self, svc):
        assert svc.list_certificates() == []


class TestVerifyCertificate:
    def test_verify_active_certificate(self, svc):
        cert = svc.generate_certificate("STU001", "distinction", "Physics", "2026-06-01")
        result = svc.verify_certificate(cert["certificate_number"])
        assert result["valid"] is True
        assert result["status"] == "active"
        assert result["course_name"] == "Physics"

    def test_verify_nonexistent(self, svc):
        result = svc.verify_certificate("CERT-DOESNOTEXIST")
        assert result["valid"] is False

    def test_verify_no_table(self):
        from education_system.platform.features.certificates.certificate_service import CertificateService
        svc = CertificateService(db_path=":memory:")
        result = svc.verify_certificate("CERT-000")
        assert result["valid"] is False


class TestRevokeCertificate:
    def test_revoke_then_verify(self, svc):
        cert = svc.generate_certificate("STU001", "completion", "Maths", "2026-01-01")
        revoked = svc.revoke_certificate(cert["id"], reason="Issued in error")
        assert revoked["status"] == "revoked"
        # Verify shows revoked
        result = svc.verify_certificate(cert["certificate_number"])
        assert result["valid"] is False
        assert result["status"] == "revoked"

    def test_revoke_nonexistent_raises(self, svc):
        # Ensure table exists
        svc.generate_certificate("STU001", "completion", "Maths", "2026-01-01")
        with pytest.raises(RuntimeError):
            svc.revoke_certificate(9999, reason="test")

    def test_revoke_already_revoked_raises(self, svc):
        cert = svc.generate_certificate("STU001", "merit", "History", "2026-01-01")
        svc.revoke_certificate(cert["id"], reason="Error")
        with pytest.raises(RuntimeError):
            svc.revoke_certificate(cert["id"], reason="Again")


class TestExportHTML:
    def test_export_html_contains_details(self, svc):
        cert = svc.generate_certificate("STU001", "achievement", "Chemistry",
                                         "2026-05-01", grade="A*")
        html = svc.export_certificate_html(cert["id"])
        assert "Chemistry" in html
        assert cert["certificate_number"] in html
