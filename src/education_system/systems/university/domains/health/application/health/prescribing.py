"""Prescribing safety: one check behind the GUI and CLI prescription forms.

:func:`check` looks at a new medication against

* **every** allergy on file — the health ``allergies`` table (verified or
  not) *and* the dental clinic's record (``dentist_patients.allergies``,
  sealed; linked to the student by student number, login id or username) —
  matched by drug name and by drug class (``drug_classes``), with class
  cross-reactivity (``drug_class_cross_reactivity``: penicillin →
  cephalosporin, sulfonamide → trimethoprim, NSAID → NSAID);
* the student's active prescriptions: the same drug or the same class is a
  duplicate;
* the maintained interaction table (``drug_interactions``).

A documented **severe** allergy (severe / anaphylaxis / life-threatening)
to the drug or its class is a *hard stop*: it can be overridden only by a
clinician, with a reason, through :func:`record_override` (audited).
Everything else is a warning the prescriber confirms. The tables are seeded
by ``infrastructure/health/workflow_schema`` and can be extended in place.
This is a safety screen, not a replacement for pharmacist review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from education_system.systems.university.domains.health.application.health import (
    access, sealed_fields,
)
from education_system.systems.university.domains.health.application.health.workflow import (
    ensure_schema,
)

SEVERE = ("severe", "anaphyla", "life-threatening", "life threatening", "critical")
# Words people write for a class in an allergy entry.
CLASS_ALIASES = {
    "sulfa": "sulfonamide", "sulpha": "sulfonamide", "sulphonamide": "sulfonamide",
    "sulfonamides": "sulfonamide", "nsaids": "nsaid", "anti-inflammatory": "nsaid",
    "anti-inflammatories": "nsaid", "penicillins": "penicillin",
    "cephalosporins": "cephalosporin", "macrolides": "macrolide",
    "tetracyclines": "tetracycline", "opioids": "opioid", "opiates": "opioid",
    "quinolones": "fluoroquinolone", "ssris": "ssri",
}


@dataclass
class SafetyReport:
    medication: str
    hard_stops: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def clear(self) -> bool:
        return not self.hard_stops and not self.warnings

    def summary(self) -> str:
        lines = [f"STOP: {s}" for s in self.hard_stops] + [f"Warning: {w}" for w in self.warnings]
        return "\n".join(lines) or "No allergy, duplicate or interaction problems found."


_NOISE = {"allergy", "allergic", "to", "mg", "ml", "tablet", "tablets", "capsule", "capsules",
          "oral", "cream", "the", "and", "of", "with", "v", "iv", "im", "dose", "syrup"}


def _words(text) -> list[str]:
    """Meaningful lower-case words (no doses, forms or filler)."""
    return [w for w in re.split(r"[^a-z0-9\-]+", str(text or "").lower())
            if w and w not in _NOISE and not re.fullmatch(r"[0-9.\-]+(mg|ml|mcg|g)?", w)]


def _class_table(conn) -> dict[str, str]:
    return {name.lower(): cls.lower() for name, cls in
            conn.execute("SELECT drug_name, drug_class FROM drug_classes").fetchall()}


def classify(conn, name) -> tuple[set[str], set[str]]:
    """``(drug names, classes)`` named in ``name`` (a medication or an
    allergy entry); a class word or alias counts as the class itself."""
    table = _class_table(conn)
    classes_known = set(table.values())
    drugs, classes = set(), set()
    for word in _words(name):
        if word in table:
            drugs.add(word)
            classes.add(table[word])
        word = CLASS_ALIASES.get(word, word)
        if word in classes_known:
            classes.add(word)
    return drugs, classes


def _student_logins(conn, student_id) -> list[str]:
    keys = {str(student_id)}
    try:
        for uid, username in conn.execute("SELECT id, username FROM users WHERE student_id = ?",
                                          (str(student_id),)).fetchall():
            keys.update({str(uid), str(username)})
    except Exception:
        pass                       # no users.student_id column: student number only
    return sorted(keys)


def allergies_for(conn, student_id) -> list[dict]:
    """Every allergy on file for the student: ``[{allergen, severity, source}]``
    from the health record and the dental clinic record."""
    found = []
    for allergen, severity, verified in conn.execute(
            "SELECT allergen, severity, verified FROM allergies WHERE student_id = ?",
            (str(student_id),)).fetchall():
        if allergen:
            found.append({"allergen": allergen, "severity": severity or "unknown",
                          "source": "health record" + ("" if verified else " (unverified)")})
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dentist_patients'")}
    if tables:
        keys = _student_logins(conn, student_id)
        marks = ",".join("?" * len(keys))
        for (text,) in conn.execute(
                f"SELECT allergies FROM dentist_patients WHERE CAST(user_id AS TEXT) IN ({marks})",  # nosec B608
                keys).fetchall():
            for part in re.split(r"[,;\n]+", sealed_fields.reveal(text) or ""):
                part = part.strip()
                if part and part != sealed_fields.UNREADABLE:
                    sev = "severe" if any(s in part.lower() for s in SEVERE) else "unknown"
                    found.append({"allergen": part, "severity": sev, "source": "dental record"})
    return found


def active_medications(conn, student_id) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT medication_name FROM prescriptions WHERE student_id = ? AND "
        "LOWER(COALESCE(status, 'active')) IN ('active', 'on_hold') AND medication_name IS NOT NULL",
        (str(student_id),)).fetchall()]


def interactions_between(conn, medication, others) -> list[tuple[str, str, str]]:
    """``[(other, severity, description)]`` from ``drug_interactions``."""
    new_drugs, _ = classify(conn, medication)
    new_drugs |= set(_words(medication))
    hits = []
    for other in others:
        other_drugs = classify(conn, other)[0] | set(_words(other))
        for a, b, severity, text in conn.execute(
                "SELECT drug_a, drug_b, severity, description FROM drug_interactions").fetchall():
            a, b = a.lower(), b.lower()
            if (a in new_drugs and b in other_drugs) or (b in new_drugs and a in other_drugs):
                hits.append((other, severity, text))
    return hits


def check(conn, student_id, medication) -> SafetyReport:
    """The safety screen for prescribing ``medication`` to ``student_id``."""
    ensure_schema(conn)
    report = SafetyReport(str(medication))
    drugs, classes = classify(conn, medication)
    med_words = set(_words(medication))
    cross = {(a.lower(), b.lower()): note for a, b, note in conn.execute(
        "SELECT class_a, class_b, note FROM drug_class_cross_reactivity").fetchall()}

    for allergy in allergies_for(conn, student_id):
        a_drugs, a_classes = classify(conn, allergy["allergen"])
        a_words = set(_words(allergy["allergen"]))
        severe = any(s in str(allergy["severity"]).lower() for s in SEVERE)
        label = f"{allergy['allergen']} ({allergy['severity']}, {allergy['source']})"
        direct = (a_drugs & (drugs | med_words)) or (a_words & med_words)
        same_class = a_classes & classes
        if direct or same_class:
            what = (f"{medication} is in the {', '.join(sorted(same_class))} class"
                    if same_class and not direct else f"{medication} matches")
            text = f"{what} — documented allergy: {label}"
            (report.hard_stops if severe else report.warnings).append(text)
            continue
        for a_cls in a_classes:
            for m_cls in classes:
                note = cross.get((a_cls, m_cls))
                if note:
                    report.warnings.append(
                        f"Possible cross-reactivity: {medication} ({m_cls}) with allergy "
                        f"{label}. {note}")

    for other in active_medications(conn, student_id):
        o_drugs, o_classes = classify(conn, other)
        if (o_drugs & drugs) or (not drugs and _words(other)[:1] == _words(medication)[:1]):
            report.warnings.append(f"Duplicate: {other} is already an active prescription")
        elif o_classes & classes:
            report.warnings.append(f"Duplicate class: {other} is also "
                                   f"{', '.join(sorted(o_classes & classes))}")
    for other, severity, text in interactions_between(conn, medication,
                                                      active_medications(conn, student_id)):
        report.warnings.append(f"Interaction ({severity}) with {other}: {text}")
    return report


def record_override(conn, who, student_id, medication, report: SafetyReport, reason: str) -> None:
    """A clinician overriding a hard stop, with the reason; audited in
    ``conn``'s transaction. Raises ``PermissionError`` / ``ValueError``.
    Does not commit."""
    access.require_clinician(who, "override a prescribing safety stop")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a clinical reason for overriding the safety stop")
    issue = "; ".join(report.hard_stops) or "warning acknowledged"
    conn.execute("INSERT INTO prescription_safety_overrides (student_id, medication_name, issue, "
                 "reason, overridden_by) VALUES (?, ?, ?, ?, ?)",
                 (str(student_id), str(medication), issue, reason, who.username))
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event,
    )
    log_audit_event(who.username, "PRESCRIBING_OVERRIDE", "prescription", student_id,
                    {"medication": medication, "issue": issue}, conn=conn, reason=reason)


# ── The interaction table (maintained by the health team) ───────────────

INTERACTION_SEVERITIES = ("severe", "moderate", "minor")


def list_interactions(conn, search=None) -> list[dict]:
    ensure_schema(conn)
    sql = "SELECT id, drug_a, drug_b, severity, description FROM drug_interactions"
    args: list = []
    if search:
        sql += " WHERE drug_a LIKE ? OR drug_b LIKE ? OR description LIKE ?"
        args = [f"%{search}%"] * 3
    sql += " ORDER BY CASE severity WHEN 'severe' THEN 0 WHEN 'moderate' THEN 1 ELSE 2 END, drug_a, drug_b"
    cols = ("id", "drug_a", "drug_b", "severity", "description")
    return [dict(zip(cols, tuple(r))) for r in conn.execute(sql, args).fetchall()]


def save_interaction(conn, who, *, drug_a, drug_b, severity, description,
                     interaction_id=None) -> int:
    """Add or change one interaction (clinicians only); audited in ``conn``'s
    transaction. The pair is stored in alphabetical order, so A+B and B+A
    are the same entry. Does not commit."""
    access.require_clinician(who, "maintain the drug interaction table")
    ensure_schema(conn)
    a, b = sorted((str(drug_a or "").strip().lower(), str(drug_b or "").strip().lower()))
    description = str(description or "").strip()
    if not a or not b or a == b:
        raise ValueError("Enter two different drugs")
    if severity not in INTERACTION_SEVERITIES:
        raise ValueError(f"Severity must be one of {', '.join(INTERACTION_SEVERITIES)}")
    if len(description) < 5:
        raise ValueError("Describe the interaction")
    clash = conn.execute("SELECT id FROM drug_interactions WHERE drug_a = ? AND drug_b = ?",
                         (a, b)).fetchone()
    if clash and (interaction_id is None or int(clash[0]) != int(interaction_id)):
        raise ValueError(f"{a} + {b} is already in the table (entry {clash[0]})")
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event,
    )
    if interaction_id:
        cur = conn.execute("UPDATE drug_interactions SET drug_a = ?, drug_b = ?, severity = ?, "
                           "description = ? WHERE id = ?",
                           (a, b, severity, description, int(interaction_id)))
        if not cur.rowcount:
            raise LookupError(f"Interaction {interaction_id} not found")
        row_id = int(interaction_id)
        action = "UPDATE"
    else:
        row_id = conn.execute("INSERT INTO drug_interactions (drug_a, drug_b, severity, "
                              "description) VALUES (?, ?, ?, ?)",
                              (a, b, severity, description)).lastrowid
        action = "CREATE"
    log_audit_event(who.username, action, "drug_interaction", row_id,
                    {"drug_a": a, "drug_b": b, "severity": severity}, conn=conn)
    return row_id


def delete_interaction(conn, who, interaction_id, reason) -> None:
    """Remove one interaction (clinicians only, with a reason); audited."""
    access.require_clinician(who, "maintain the drug interaction table")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for removing the interaction")
    row = conn.execute("SELECT drug_a, drug_b, severity FROM drug_interactions WHERE id = ?",
                       (int(interaction_id),)).fetchone()
    if row is None:
        raise LookupError(f"Interaction {interaction_id} not found")
    conn.execute("DELETE FROM drug_interactions WHERE id = ?", (int(interaction_id),))
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event,
    )
    log_audit_event(who.username, "DELETE", "drug_interaction", interaction_id,
                    {"drug_a": row[0], "drug_b": row[1], "severity": row[2]}, conn=conn,
                    reason=reason)
