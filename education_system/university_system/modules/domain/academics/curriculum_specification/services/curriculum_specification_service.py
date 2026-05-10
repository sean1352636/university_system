"""Programme specification & module descriptor service.

Models QAA-style programme specs, module descriptors with explicit learning
outcomes, assessment strategy components, programme handbook generation, and
a change-control log so versioned curriculum revisions are auditable.
"""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import (
    get_connection,
    transaction,
)


VALID_PROG_STATUSES = ("draft", "approved", "active", "withdrawn", "under_review")
VALID_LO_DOMAINS = ("knowledge", "skills", "professional", "transferable")
VALID_ASSESS_TYPES = (
    "exam",
    "coursework",
    "presentation",
    "practical",
    "dissertation",
    "portfolio",
    "lab_report",
    "other",
)


class CurriculumSpecificationService:
    """CRUD + change-control for programme specs and module descriptors."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curr_programmes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    award TEXT,
                    level TEXT,
                    credits INTEGER,
                    duration_years REAL,
                    department TEXT,
                    faculty TEXT,
                    version TEXT DEFAULT '1.0',
                    status TEXT DEFAULT 'draft',
                    aims TEXT,
                    educational_aims TEXT,
                    target_qualification TEXT,
                    qaa_benchmark TEXT,
                    pedagogic_approach TEXT,
                    entry_requirements TEXT,
                    progression_routes TEXT,
                    last_review_date TEXT,
                    next_review_date TEXT,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, version)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curr_module_descriptors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    programme_id INTEGER,
                    module_code TEXT NOT NULL,
                    title TEXT NOT NULL,
                    credits INTEGER,
                    level TEXT,
                    semester TEXT,
                    is_core INTEGER DEFAULT 1,
                    version TEXT DEFAULT '1.0',
                    status TEXT DEFAULT 'draft',
                    aims TEXT,
                    indicative_content TEXT,
                    teaching_methods TEXT,
                    contact_hours INTEGER,
                    independent_study_hours INTEGER,
                    prerequisites TEXT,
                    co_requisites TEXT,
                    reading_list TEXT,
                    module_leader TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (programme_id) REFERENCES curr_programmes(id),
                    UNIQUE(module_code, version)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curr_learning_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_type TEXT NOT NULL,
                    parent_id INTEGER NOT NULL,
                    code TEXT,
                    domain TEXT,
                    description TEXT NOT NULL,
                    bloom_level TEXT,
                    sort_order INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curr_assessment_components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_descriptor_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    assessment_type TEXT,
                    weighting_pct REAL,
                    word_count INTEGER,
                    duration_minutes INTEGER,
                    week_due TEXT,
                    learning_outcomes_assessed TEXT,
                    feedback_method TEXT,
                    notes TEXT,
                    FOREIGN KEY (module_descriptor_id) REFERENCES curr_module_descriptors(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS curr_change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_type TEXT NOT NULL,
                    parent_id INTEGER NOT NULL,
                    from_version TEXT,
                    to_version TEXT,
                    change_type TEXT,
                    summary TEXT NOT NULL,
                    rationale TEXT,
                    impact TEXT,
                    proposed_by TEXT,
                    approved_by TEXT,
                    status TEXT DEFAULT 'proposed',
                    proposed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    approved_at TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_curr_md_prog ON curr_module_descriptors(programme_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_curr_lo_parent ON curr_learning_outcomes(parent_type, parent_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_curr_assess_md ON curr_assessment_components(module_descriptor_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_curr_change_parent ON curr_change_log(parent_type, parent_id)"
            )
            conn.commit()

    # ------------------------------------------------------------ Programmes
    def create_programme(self, **kwargs) -> int:
        if not kwargs.get("code") or not kwargs.get("title"):
            raise ValueError("code and title are required")
        kwargs.setdefault("status", "draft")
        kwargs.setdefault("version", "1.0")
        if kwargs["status"] not in VALID_PROG_STATUSES:
            raise ValueError(f"invalid status: {kwargs['status']}")
        cols = (
            "code", "title", "award", "level", "credits", "duration_years",
            "department", "faculty", "version", "status", "aims",
            "educational_aims", "target_qualification", "qaa_benchmark",
            "pedagogic_approach", "entry_requirements", "progression_routes",
            "last_review_date", "next_review_date", "created_by",
        )
        values = [kwargs.get(c) for c in cols]
        placeholders = ", ".join("?" for _ in cols)
        with transaction() as conn:
            cursor = conn.execute(
                f"INSERT INTO curr_programmes ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return cursor.lastrowid

    def get_programme(self, programme_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM curr_programmes WHERE id = ?", (programme_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_programmes(self, status: str = None, department: str = None) -> List[Dict]:
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if department:
            clauses.append("department = ?")
            params.append(department)
        sql = "SELECT * FROM curr_programmes"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY code, version"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def update_programme(self, programme_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        if "status" in kwargs and kwargs["status"] not in VALID_PROG_STATUSES:
            raise ValueError(f"invalid status: {kwargs['status']}")
        from education_system.shared.database.sql_safety import validate_identifier  # nosec B608
        sets = ", ".join(f"{validate_identifier(k)} = ?" for k in kwargs)
        with transaction() as conn:
            conn.execute(
                f"UPDATE curr_programmes SET {sets} WHERE id = ?",
                (*kwargs.values(), programme_id),
            )
            conn.commit()
            return True

    def approve_programme(self, programme_id: int, approver: str) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE curr_programmes SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
                (approver, datetime.now().isoformat(), programme_id),
            )
            conn.commit()
            return True

    def new_programme_version(self, programme_id: int, new_version: str, created_by: str = None) -> int:
        """Clone a programme (and its module list) to a new version in 'draft'."""
        prog = self.get_programme(programme_id)
        if not prog:
            raise ValueError(f"programme {programme_id} not found")
        clone = {k: v for k, v in prog.items() if k not in ("id", "created_at", "approved_at", "approved_by")}
        clone["version"] = new_version
        clone["status"] = "draft"
        clone["created_by"] = created_by
        new_id = self.create_programme(**clone)
        return new_id

    # ----------------------------------------------------- Module Descriptors
    def create_module_descriptor(self, **kwargs) -> int:
        if not kwargs.get("module_code") or not kwargs.get("title"):
            raise ValueError("module_code and title are required")
        kwargs.setdefault("version", "1.0")
        kwargs.setdefault("status", "draft")
        kwargs.setdefault("is_core", 1)
        cols = (
            "programme_id", "module_code", "title", "credits", "level",
            "semester", "is_core", "version", "status", "aims",
            "indicative_content", "teaching_methods", "contact_hours",
            "independent_study_hours", "prerequisites", "co_requisites",
            "reading_list", "module_leader", "created_by",
        )
        values = [kwargs.get(c) for c in cols]
        placeholders = ", ".join("?" for _ in cols)
        with transaction() as conn:
            cursor = conn.execute(
                f"INSERT INTO curr_module_descriptors ({', '.join(cols)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return cursor.lastrowid

    def get_module_descriptor(self, descriptor_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM curr_module_descriptors WHERE id = ?", (descriptor_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_module_descriptors(self, programme_id: int = None) -> List[Dict]:
        with get_connection() as conn:
            if programme_id:
                rows = conn.execute(
                    "SELECT * FROM curr_module_descriptors WHERE programme_id = ? ORDER BY level, module_code",
                    (programme_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM curr_module_descriptors ORDER BY module_code, version"
                ).fetchall()
            return [dict(r) for r in rows]

    def update_module_descriptor(self, descriptor_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        from education_system.shared.database.sql_safety import validate_identifier  # nosec B608
        sets = ", ".join(f"{validate_identifier(k)} = ?" for k in kwargs)
        with transaction() as conn:
            conn.execute(
                f"UPDATE curr_module_descriptors SET {sets} WHERE id = ?",
                (*kwargs.values(), descriptor_id),
            )
            conn.commit()
            return True

    # ---------------------------------------------------- Learning Outcomes
    def add_learning_outcome(self, parent_type: str, parent_id: int, description: str,
                             code: str = None, domain: str = None,
                             bloom_level: str = None, sort_order: int = 0) -> int:
        if parent_type not in ("programme", "module"):
            raise ValueError("parent_type must be 'programme' or 'module'")
        if domain and domain not in VALID_LO_DOMAINS:
            raise ValueError(f"invalid domain: {domain}")
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO curr_learning_outcomes (parent_type, parent_id, code, domain, description, bloom_level, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (parent_type, parent_id, code, domain, description, bloom_level, sort_order),
            )
            conn.commit()
            return cursor.lastrowid

    def list_learning_outcomes(self, parent_type: str, parent_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM curr_learning_outcomes WHERE parent_type = ? AND parent_id = ? ORDER BY sort_order, id",
                (parent_type, parent_id),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_learning_outcome(self, lo_id: int) -> bool:
        with transaction() as conn:
            conn.execute("DELETE FROM curr_learning_outcomes WHERE id = ?", (lo_id,))
            conn.commit()
            return True

    # -------------------------------------------------- Assessment Strategy
    def add_assessment_component(self, module_descriptor_id: int, name: str,
                                 assessment_type: str = None, weighting_pct: float = None,
                                 word_count: int = None, duration_minutes: int = None,
                                 week_due: str = None, learning_outcomes_assessed: str = None,
                                 feedback_method: str = None, notes: str = None) -> int:
        if assessment_type and assessment_type not in VALID_ASSESS_TYPES:
            raise ValueError(f"invalid assessment_type: {assessment_type}")
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO curr_assessment_components (module_descriptor_id, name, assessment_type, weighting_pct, word_count, duration_minutes, week_due, learning_outcomes_assessed, feedback_method, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (module_descriptor_id, name, assessment_type, weighting_pct, word_count,
                 duration_minutes, week_due, learning_outcomes_assessed, feedback_method, notes),
            )
            conn.commit()
            return cursor.lastrowid

    def list_assessment_components(self, module_descriptor_id: int) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM curr_assessment_components WHERE module_descriptor_id = ? ORDER BY id",
                (module_descriptor_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def assessment_weighting_total(self, module_descriptor_id: int) -> float:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(weighting_pct), 0) AS total FROM curr_assessment_components WHERE module_descriptor_id = ?",
                (module_descriptor_id,),
            ).fetchone()
            return float(row["total"]) if row else 0.0

    def validate_assessment_strategy(self, module_descriptor_id: int) -> Dict:
        """Returns {'valid': bool, 'total': float, 'issues': [...]}."""
        components = self.list_assessment_components(module_descriptor_id)
        total = sum((c.get("weighting_pct") or 0) for c in components)
        issues = []
        if not components:
            issues.append("No assessment components defined")
        if abs(total - 100.0) > 0.01 and components:
            issues.append(f"Weightings total {total:.2f}%, should be 100%")
        for c in components:
            if not c.get("learning_outcomes_assessed"):
                issues.append(f"Component '{c.get('name')}' has no LOs mapped")
        return {"valid": not issues, "total": total, "issues": issues}

    def delete_assessment_component(self, component_id: int) -> bool:
        with transaction() as conn:
            conn.execute("DELETE FROM curr_assessment_components WHERE id = ?", (component_id,))
            conn.commit()
            return True

    # --------------------------------------------------------- Change Control
    def propose_change(self, parent_type: str, parent_id: int, summary: str,
                       from_version: str = None, to_version: str = None,
                       change_type: str = None, rationale: str = None,
                       impact: str = None, proposed_by: str = None) -> int:
        if parent_type not in ("programme", "module"):
            raise ValueError("parent_type must be 'programme' or 'module'")
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO curr_change_log (parent_type, parent_id, from_version, to_version, change_type, summary, rationale, impact, proposed_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (parent_type, parent_id, from_version, to_version, change_type,
                 summary, rationale, impact, proposed_by),
            )
            conn.commit()
            return cursor.lastrowid

    def approve_change(self, change_id: int, approver: str) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE curr_change_log SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
                (approver, datetime.now().isoformat(), change_id),
            )
            conn.commit()
            return True

    def reject_change(self, change_id: int, approver: str, reason: str = None) -> bool:
        with transaction() as conn:
            conn.execute(
                "UPDATE curr_change_log SET status = 'rejected', approved_by = ?, approved_at = ?, impact = COALESCE(impact, '') || CASE WHEN ? IS NULL THEN '' ELSE ' | rejected: ' || ? END WHERE id = ?",
                (approver, datetime.now().isoformat(), reason, reason, change_id),
            )
            conn.commit()
            return True

    def list_changes(self, parent_type: str = None, parent_id: int = None,
                     status: str = None) -> List[Dict]:
        clauses, params = [], []
        if parent_type:
            clauses.append("parent_type = ?")
            params.append(parent_type)
        if parent_id:
            clauses.append("parent_id = ?")
            params.append(parent_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM curr_change_log"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY proposed_at DESC"
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # -------------------------------------------- Cross-module integrations
    def examiner_findings_for_module(self, descriptor_id: int) -> List[Dict]:
        """Return external-examiner visit findings that reference this module."""
        md = self.get_module_descriptor(descriptor_id)
        if not md:
            return []
        code = md["module_code"]
        with get_connection() as conn:
            try:
                rows = conn.execute(
                    """SELECT v.id, v.visit_date, v.department, v.findings,
                              v.recommendations, v.overall_rating, e.name AS examiner
                         FROM examiner_visits v
                         LEFT JOIN external_examiners e ON e.id = v.examiner_id
                        WHERE v.modules_reviewed LIKE ?
                        ORDER BY v.visit_date DESC""",
                    (f"%{code}%",),
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

    def hesa_programme_payload(self, programme_id: int) -> Dict:
        """Map a programme spec into HESA-style fields for export."""
        prog = self.get_programme(programme_id)
        if not prog:
            return {}
        return {
            "programme_code": prog["code"],
            "programme_title": prog["title"],
            "qualification_award": prog.get("award"),
            "level": prog.get("level"),
            "credit_value": prog.get("credits"),
            "duration_years": prog.get("duration_years"),
            "department": prog.get("department"),
            "faculty": prog.get("faculty"),
            "version": prog.get("version"),
            "status": prog.get("status"),
            "qaa_benchmark": prog.get("qaa_benchmark"),
        }

    # ------------------------------------------------------ Handbook export
    def generate_handbook(self, programme_id: int) -> str:
        """Render a plain-text course handbook for a programme version."""
        prog = self.get_programme(programme_id)
        if not prog:
            raise ValueError(f"programme {programme_id} not found")

        out = []
        title_line = f"{prog['code']} v{prog['version']} — {prog['title']}"
        out.append("=" * len(title_line))
        out.append(title_line)
        out.append("=" * len(title_line))
        out.append(f"Award: {prog.get('award') or 'n/a'}    Level: {prog.get('level') or 'n/a'}    "
                   f"Credits: {prog.get('credits') or 'n/a'}")
        out.append(f"Status: {prog.get('status')}    Department: {prog.get('department') or 'n/a'}")
        out.append("")

        for label, key in (
            ("Educational Aims", "educational_aims"),
            ("Programme Aims", "aims"),
            ("QAA Benchmark", "qaa_benchmark"),
            ("Pedagogic Approach", "pedagogic_approach"),
            ("Entry Requirements", "entry_requirements"),
            ("Progression Routes", "progression_routes"),
        ):
            val = prog.get(key)
            if val:
                out.append(f"{label}")
                out.append("-" * len(label))
                out.append(val)
                out.append("")

        prog_los = self.list_learning_outcomes("programme", programme_id)
        if prog_los:
            out.append("Programme Learning Outcomes")
            out.append("-" * 27)
            for lo in prog_los:
                out.append(f"  [{lo.get('code') or '·'}] ({lo.get('domain') or 'general'}) "
                           f"{lo['description']}")
            out.append("")

        modules = self.list_module_descriptors(programme_id)
        if modules:
            out.append("Module Descriptors")
            out.append("-" * 18)
            for m in modules:
                core = "Core" if m.get("is_core") else "Optional"
                out.append(f"\n{m['module_code']} v{m['version']} — {m['title']}  "
                           f"({m.get('credits') or '?'} credits, {core})")
                if m.get("aims"):
                    out.append(f"  Aims: {m['aims']}")
                los = self.list_learning_outcomes("module", m["id"])
                for lo in los:
                    out.append(f"   LO[{lo.get('code') or '·'}]: {lo['description']}")
                comps = self.list_assessment_components(m["id"])
                if comps:
                    out.append("  Assessment:")
                    for c in comps:
                        w = f"{c.get('weighting_pct') or 0:.0f}%"
                        out.append(f"   - {c['name']} ({c.get('assessment_type') or 'n/a'}, {w})")
        return "\n".join(out)

    # ------------------------------------------------------------- Summaries
    def programme_summary(self, programme_id: int) -> Dict:
        prog = self.get_programme(programme_id)
        if not prog:
            return {}
        modules = self.list_module_descriptors(programme_id)
        prog_los = self.list_learning_outcomes("programme", programme_id)
        pending_changes = self.list_changes("programme", programme_id, "proposed")
        total_credits = sum((m.get("credits") or 0) for m in modules)
        core_count = sum(1 for m in modules if m.get("is_core"))
        return {
            "programme": prog,
            "module_count": len(modules),
            "core_modules": core_count,
            "optional_modules": len(modules) - core_count,
            "total_credits": total_credits,
            "programme_los": len(prog_los),
            "pending_changes": len(pending_changes),
        }
