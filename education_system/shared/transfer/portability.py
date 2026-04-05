"""Student data portability — import/export in standardised formats.

Improvement #15: Student Data Portability

Supports:
- CTF (Common Transfer File) — UK standard for student transfers
- JSON — internal transfer format between education systems
- CSV — simple flat export
"""

import csv
import io
import json
import logging
import defusedxml.ElementTree as SafeET
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from defusedxml.minidom import parseString

logger = logging.getLogger(__name__)


class StudentDataExporter:
    """Export student data in standardised formats for portability."""

    def __init__(self, system_name: str, system_key: str):
        self.system_name = system_name
        self.system_key = system_key

    def to_json(self, students: list[dict], *, include_grades: bool = False) -> str:
        """Export student records as a JSON transfer document."""
        doc = {
            "format": "education-system-transfer",
            "version": "1.0",
            "source_system": self.system_name,
            "source_key": self.system_key,
            "exported_at": datetime.now().isoformat(),
            "student_count": len(students),
            "students": [],
        }
        for s in students:
            record = {
                "student_id": s.get("student_id", ""),
                "first_name": s.get("first_name", ""),
                "last_name": s.get("last_name", ""),
                "date_of_birth": s.get("date_of_birth", ""),
                "gender": s.get("gender", ""),
                "email": s.get("email", ""),
                "phone": s.get("phone", ""),
                "address": s.get("address", ""),
                "year_group": s.get("year_group", ""),
                "form_group": s.get("form_group", ""),
                "enrolment_date": s.get("enrolment_date", s.get("enrollment_date", "")),
                "status": s.get("status", "active"),
                "sen_status": s.get("sen_status", s.get("send_status", "")),
                "fsm_eligible": s.get("fsm_eligible", s.get("free_school_meals", False)),
                "emergency_contact_name": s.get("emergency_contact_name", ""),
                "emergency_contact_phone": s.get("emergency_contact_phone", ""),
            }
            if include_grades and "grades" in s:
                record["grades"] = s["grades"]
            doc["students"].append(record)
        return json.dumps(doc, indent=2)

    def to_csv(self, students: list[dict]) -> str:
        """Export student records as CSV."""
        if not students:
            return ""
        fields = ["student_id", "first_name", "last_name", "date_of_birth",
                   "gender", "email", "phone", "address", "year_group",
                   "form_group", "status", "enrolment_date"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for s in students:
            row = {f: s.get(f, "") for f in fields}
            if not row["enrolment_date"]:
                row["enrolment_date"] = s.get("enrollment_date", "")
            writer.writerow(row)
        return buffer.getvalue()

    def to_ctf_xml(self, students: list[dict], *, dest_school: str = "") -> str:
        """Export student records as UK Common Transfer File (CTF) XML."""
        root = ET.Element("CTfile")

        header = ET.SubElement(root, "Header")
        ET.SubElement(header, "DocumentName").text = "Common Transfer File"
        ET.SubElement(header, "CTFVersion").text = "18.0"
        ET.SubElement(header, "DateTime").text = datetime.now().isoformat()

        source = ET.SubElement(header, "SourceSchool")
        ET.SubElement(source, "SchoolName").text = self.system_name

        if dest_school:
            dest = ET.SubElement(header, "DestSchool")
            ET.SubElement(dest, "SchoolName").text = dest_school

        pupils = ET.SubElement(root, "CTFpupilData")

        for s in students:
            pupil = ET.SubElement(pupils, "Pupil")
            ET.SubElement(pupil, "UPN").text = s.get("student_id", "")
            ET.SubElement(pupil, "Surname").text = s.get("last_name", "")
            ET.SubElement(pupil, "Forename").text = s.get("first_name", "")
            ET.SubElement(pupil, "DOB").text = s.get("date_of_birth", "")
            ET.SubElement(pupil, "Gender").text = s.get("gender", "")

            if s.get("email"):
                ET.SubElement(pupil, "Email").text = s["email"]
            if s.get("address"):
                addresses = ET.SubElement(pupil, "Addresses")
                addr = ET.SubElement(addresses, "Address")
                ET.SubElement(addr, "AddressLine1").text = s["address"]

            school_hist = ET.SubElement(pupil, "SchoolHistory")
            school = ET.SubElement(school_hist, "School")
            ET.SubElement(school, "SchoolName").text = self.system_name
            ET.SubElement(school, "EntryDate").text = s.get("enrolment_date", s.get("enrollment_date", ""))

        xml_str = ET.tostring(root, encoding="unicode")
        return parseString(xml_str).toprettyxml(indent="  ")

    def save(self, filepath: str | Path, students: list[dict], **kwargs) -> Path:
        """Auto-detect format from extension and save."""
        filepath = Path(filepath)
        ext = filepath.suffix.lower()
        if ext == ".json":
            data = self.to_json(students, **kwargs)
        elif ext == ".csv":
            data = self.to_csv(students)
        elif ext == ".xml":
            data = self.to_ctf_xml(students, **kwargs)
        else:
            raise ValueError(f"Unsupported format: {ext}")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(data, encoding="utf-8")
        logger.info("Exported %d students to %s", len(students), filepath)
        return filepath


class StudentDataImporter:
    """Import student data from standardised formats."""

    def from_json(self, data: str | Path) -> list[dict]:
        if isinstance(data, Path) or (isinstance(data, str) and len(data) < 500 and Path(data).is_file()):
            data = Path(data).read_text(encoding="utf-8")
        doc = json.loads(data)
        return doc.get("students", [])

    def from_csv(self, data: str | Path) -> list[dict]:
        if isinstance(data, Path) or (isinstance(data, str) and len(data) < 500 and Path(data).is_file()):
            data = Path(data).read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(data))
        return [dict(row) for row in reader]

    def from_ctf_xml(self, data: str | Path) -> list[dict]:
        if isinstance(data, Path) or (isinstance(data, str) and len(data) < 500 and Path(data).is_file()):
            data = Path(data).read_text(encoding="utf-8")
        root = SafeET.fromstring(data)
        students = []
        for pupil in root.iter("Pupil"):
            s = {
                "student_id": self._text(pupil, "UPN"),
                "last_name": self._text(pupil, "Surname"),
                "first_name": self._text(pupil, "Forename"),
                "date_of_birth": self._text(pupil, "DOB"),
                "gender": self._text(pupil, "Gender"),
                "email": self._text(pupil, "Email"),
            }
            addr_el = pupil.find(".//AddressLine1")
            if addr_el is not None:
                s["address"] = addr_el.text or ""
            entry_el = pupil.find(".//EntryDate")
            if entry_el is not None:
                s["enrolment_date"] = entry_el.text or ""
            students.append(s)
        return students

    def load(self, filepath: str | Path) -> list[dict]:
        """Auto-detect format from extension and load."""
        filepath = Path(filepath)
        ext = filepath.suffix.lower()
        if ext == ".json":
            return self.from_json(filepath)
        elif ext == ".csv":
            return self.from_csv(filepath)
        elif ext == ".xml":
            return self.from_ctf_xml(filepath)
        else:
            raise ValueError(f"Unsupported format: {ext}")

    @staticmethod
    def _text(element, tag: str) -> str:
        el = element.find(tag)
        return (el.text or "") if el is not None else ""
