"""
Research & Grants Management Core Service

Research projects, grant applications, publications, milestones,
equipment tracking, and IRB/ethics reviews.
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from education_system.systems.university.infrastructure.database.db import get_connection, transaction, sqlite3
from education_system.systems.university.services.feature_gui_factory import create_gui_launcher
from education_system.systems.university.infrastructure.i18n import get_text

logger = logging.getLogger("research.emails")


def _send_research_email(template_name: str, recipient_email: str,
                         vars_: Dict[str, Any]) -> bool:
    """Render ``research/<template_name>`` and dispatch best-effort.

    Skips silently when *recipient_email* is empty so wiring can be enabled
    without forcing every caller to know the email upfront."""
    if not recipient_email:
        logger.debug("research/%s skipped: no recipient", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"research/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: research/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient_email, subject=subject, body=body)
        logger.info("sent research/%s to %s", template_name, recipient_email)
        return True
    except Exception:
        logger.exception("send_email failed research/%s recipient=%s",
                         template_name, recipient_email)
        return False


class ResearchProjectManager:
    """Manages research projects"""

    @staticmethod
    def create_project(project_title: str, principal_investigator_id: str,
                      department: str, project_type: str, start_date: str,
                      description: str = "", total_budget: float = 0,
                      activity_tags: list = None) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_projects (
                        project_title, principal_investigator_id, department,
                        project_type, start_date, project_description, total_budget
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (project_title, principal_investigator_id, department,
                      project_type, start_date, description, total_budget))
                project_id = cursor.lastrowid

            # Cross-domain: high-risk research activities (biosafety,
            # human subjects, chemical, radiation, clinical, animal,
            # data_protection, field_work) auto-raise risk-register
            # entries linked back to this project so the risk GUI
            # surfaces them and the calendar shows their reviews.
            if activity_tags:
                try:
                    from education_system.systems.university.services.bus import (
                        risk_bus,
                    )
                    risk_bus.raise_research_risk(
                        project_id,
                        activity_tags=activity_tags,
                        pi_id=principal_investigator_id,
                        title=project_title,
                    )
                except Exception:
                    pass

            return project_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.create_project", "Error creating research project: {error}").format(error=e))

    @staticmethod
    def add_team_member(project_id: int, staff_id: str, role: str,
                       contribution_percentage: float = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_team_members (
                        project_id, staff_id, role, contribution_percentage
                    ) VALUES (?, ?, ?, ?)
                ''', (project_id, staff_id, role, contribution_percentage))
                member_id = cursor.lastrowid
                return member_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.add_team_member", "Error adding team member: {error}").format(error=e))


class GrantApplicationManager:
    """Manages grant applications"""

    @staticmethod
    def submit_application(grant_name: str, funding_agency: str,
                          principal_investigator_id: str, requested_amount: float,
                          application_deadline: str, project_id: int = None) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO grant_applications (
                        grant_name, funding_agency, principal_investigator_id,
                        requested_amount, application_deadline, project_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (grant_name, funding_agency, principal_investigator_id,
                      requested_amount, application_deadline, project_id))
                application_id = cursor.lastrowid
                return application_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.submit_application", "Error submitting grant application: {error}").format(error=e))

    @staticmethod
    def update_decision(application_id: int, decision_status: str,
                       awarded_amount: float = 0, grant_period_start: str = "",
                       grant_period_end: str = "") -> bool:
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE grant_applications
                    SET decision_status = ?, decision_date = ?, awarded_amount = ?,
                        grant_period_start = ?, grant_period_end = ?
                    WHERE application_id = ?
                ''', (decision_status, datetime.now().date().isoformat(),
                      awarded_amount, grant_period_start, grant_period_end, application_id))
                row = conn.execute(
                    "SELECT grant_name, principal_investigator_id "
                    "FROM grant_applications WHERE application_id = ?",
                    (application_id,),
                ).fetchone()
            try:
                from education_system.systems.university.services.bus.integration_bus import (
                    publish_grant_decision,
                )
                publish_grant_decision(
                    application_id=int(application_id),
                    status=decision_status,
                    grant_name=row[0] if row else None,
                    awarded_amount=float(awarded_amount or 0),
                    pi_id=str(row[1]) if row and row[1] else None,
                    grant_period_start=grant_period_start or None,
                    grant_period_end=grant_period_end or None,
                )
            except Exception:
                pass
            return True
        except Exception as e:
            raise Exception(get_text("research.grants.errors.update_decision", "Error updating grant decision: {error}").format(error=e))


class PublicationManager:
    """Manages research publications"""

    @staticmethod
    def record_publication(title: str, authors: str, publication_type: str,
                          project_id: int = None, journal_name: str = "",
                          publication_date: str = "", doi: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_publications (
                        project_id, title, authors, publication_type,
                        journal_name, publication_date, doi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (project_id, title, authors, publication_type,
                      journal_name, publication_date, doi))
                publication_id = cursor.lastrowid

                # Update project publication count
                if project_id:
                    conn.execute('''
                        UPDATE research_projects
                        SET publications_count = publications_count + 1
                        WHERE project_id = ?
                    ''', (project_id,))

                return publication_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.record_publication", "Error recording publication: {error}").format(error=e))


class MilestoneManager:
    """Manages research milestones"""

    @staticmethod
    def notify_supervisor_approval(milestone_id: int, approval_status: str,
                                   recipient_email: str,
                                   researcher_name: str = "Researcher",
                                   supervisor_name: str = "Supervisor",
                                   project_title: str = "",
                                   submitted_on: str = "",
                                   comments: str = "",
                                   next_steps: str = "") -> bool:
        """Email a researcher with the supervisor's decision on a milestone."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT milestone_name, project_id FROM research_milestones "
                    "WHERE milestone_id = ?",
                    (milestone_id,),
                ).fetchone()
        except Exception:
            logger.exception("milestone lookup failed mid=%s", milestone_id)
            row = None
        norm = (approval_status or '').strip().lower()
        display_map = {
            'approved':           'Approved',
            'conditional':        'Approved with Conditions',
            'changes_requested':  'Changes Requested',
            'rejected':           'Not Approved',
            'returned':           'Returned for Revision',
        }
        return _send_research_email('supervisor_approval', recipient_email, {
            'researcher_name':         researcher_name,
            'milestone_id':            milestone_id,
            'milestone_name':          row[0] if row else f"Milestone #{milestone_id}",
            'project_id':              row[1] if row else '',
            'project_title':           project_title or (f"Project #{row[1]}" if row else "(unspecified)"),
            'submitted_on':            submitted_on or '(not recorded)',
            'supervisor_name':         supervisor_name,
            'approval_status_display': display_map.get(norm, approval_status or 'Decision'),
            'decision_date':           date.today().isoformat(),
            'supervisor_comments':     comments or '(no comments left by the supervisor)',
            'next_steps':              next_steps or '(see supervisor for guidance)',
        })

    @staticmethod
    def create_milestone(project_id: int, milestone_name: str,
                        target_date: str, description: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_milestones (
                        project_id, milestone_name, milestone_description, target_date
                    ) VALUES (?, ?, ?, ?)
                ''', (project_id, milestone_name, description, target_date))
                milestone_id = cursor.lastrowid
                return milestone_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.create_milestone", "Error creating milestone: {error}").format(error=e))


class EquipmentManager:
    """Manages research equipment"""

    @staticmethod
    def register_equipment(equipment_name: str, equipment_type: str,
                          serial_number: str = "", purchase_cost: float = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_equipment (
                        equipment_name, equipment_type, serial_number, purchase_cost
                    ) VALUES (?, ?, ?, ?)
                ''', (equipment_name, equipment_type, serial_number, purchase_cost))
                equipment_id = cursor.lastrowid
                return equipment_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.register_equipment", "Error registering equipment: {error}").format(error=e))


class EthicsReviewManager:
    """Manages IRB/ethics reviews"""

    @staticmethod
    def decide_ethics_review(review_id: int, decision: str,
                             recipient_email: str,
                             pi_name: str = "Principal Investigator",
                             project_title: str = "",
                             reviewer: str = "Research Ethics Committee",
                             comments: str = "",
                             required_actions: str = "") -> bool:
        """Record the committee outcome and email the PI. Best-effort email."""
        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE ethics_reviews SET decision = ?, decision_date = ? "
                    "WHERE review_id = ?",
                    (decision, datetime.now().date().isoformat(), review_id),
                )
                row = conn.execute(
                    "SELECT project_id, review_type, submission_date "
                    "FROM ethics_reviews WHERE review_id = ?",
                    (review_id,),
                ).fetchone()
        except Exception:
            logger.exception("ethics decision update failed rid=%s", review_id)
            row = None

        norm = (decision or '').strip().lower()
        display_map = {
            'approved': 'Approved',
            'approve':  'Approved',
            'conditional': 'Approved with Conditions',
            'minor_revisions': 'Minor Revisions Required',
            'major_revisions': 'Major Revisions Required',
            'rejected': 'Rejected',
            'reject':   'Rejected',
        }
        message_map = {
            'approved':       "The committee has APPROVED this review. You may proceed with the research as described.",
            'approve':        "The committee has APPROVED this review. You may proceed with the research as described.",
            'conditional':    "The committee has approved this review subject to the conditions listed below. Work may commence only once those conditions are met.",
            'minor_revisions':"Minor revisions are required before approval can be granted. Address the comments below and resubmit the revised application.",
            'major_revisions':"Major revisions are required. The committee will need to re-review the application once the changes have been made.",
            'rejected':       "The committee has not approved this review. No research activity covered by this application may begin or continue.",
            'reject':         "The committee has not approved this review. No research activity covered by this application may begin or continue.",
        }
        return _send_research_email('ethics_decision', recipient_email, {
            'pi_name':           pi_name,
            'project_id':        row[0] if row else '',
            'project_title':     project_title or (f"Project #{row[0]}" if row else "(unspecified)"),
            'review_id':         review_id,
            'review_type':       row[1] if row else '',
            'submission_date':   row[2] if row else '',
            'decision_display':  display_map.get(norm, decision or 'Decision'),
            'decision_date':     date.today().isoformat(),
            'reviewer':          reviewer,
            'decision_message':  message_map.get(norm, f"The committee outcome is: {decision}."),
            'decision_comments': comments or '(no further comments)',
            'required_actions':  required_actions or '(none)',
        })

    @staticmethod
    def submit_ethics_review(project_id: int, review_type: str,
                            submission_date: str) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO ethics_reviews (
                        project_id, review_type, submission_date
                    ) VALUES (?, ?, ?)
                ''', (project_id, review_type, submission_date))
                review_id = cursor.lastrowid
                return review_id
        except Exception as e:
            raise Exception(get_text("research.grants.errors.submit_ethics_review", "Error submitting ethics review: {error}").format(error=e))


class GrantTrackerService:
    """Grant application tracker with deadline alerts and budget management (v8.2.0)."""

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        with transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS grant_tracker_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                funding_body TEXT, principal_investigator TEXT, co_investigators TEXT,
                department TEXT, amount_requested REAL DEFAULT 0, amount_awarded REAL DEFAULT 0,
                status TEXT DEFAULT 'draft', deadline TEXT, submitted_at TEXT,
                decision_date TEXT, start_date TEXT, end_date TEXT, abstract TEXT,
                created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS grant_tracker_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                milestone_title TEXT NOT NULL, description TEXT, deadline TEXT,
                status TEXT DEFAULT 'pending', completed_at TEXT, notes TEXT,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS grant_tracker_budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                category TEXT DEFAULT 'other', description TEXT, amount REAL DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS grant_tracker_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id INTEGER NOT NULL,
                alert_type TEXT DEFAULT 'submission', alert_date TEXT, message TEXT,
                is_sent INTEGER DEFAULT 0, sent_at TEXT,
                FOREIGN KEY (grant_id) REFERENCES grant_tracker_apps(id))""")
            conn.commit()

    def create_application(self, title, funding_body=None, principal_investigator=None,
                           department=None, amount_requested=0, deadline=None, abstract=None, created_by=None):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO grant_tracker_apps (title,funding_body,principal_investigator,department,amount_requested,deadline,abstract,created_by) VALUES (?,?,?,?,?,?,?,?)",
                               (title, funding_body, principal_investigator, department, amount_requested, deadline, abstract, created_by))
            conn.commit(); return cur.lastrowid

    def get_application(self, gid):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM grant_tracker_apps WHERE id=?", (gid,)).fetchone()
            return dict(row) if row else None

    def list_applications(self, status=None):
        with get_connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM grant_tracker_apps WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM grant_tracker_apps ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update_application_status(self, gid, status, amount_awarded=None):
        with transaction() as conn:
            if amount_awarded is not None:
                conn.execute("UPDATE grant_tracker_apps SET status=?,amount_awarded=? WHERE id=?", (status, amount_awarded, gid))
            else:
                conn.execute("UPDATE grant_tracker_apps SET status=? WHERE id=?", (status, gid))
            if status == 'submitted':
                conn.execute("UPDATE grant_tracker_apps SET submitted_at=? WHERE id=?", (datetime.now().isoformat(), gid))
            conn.commit()

    def add_milestone(self, gid, title, description=None, deadline=None):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO grant_tracker_milestones (grant_id,milestone_title,description,deadline) VALUES (?,?,?,?)", (gid, title, description, deadline))
            conn.commit(); return cur.lastrowid

    def update_milestone(self, mid, status):
        with transaction() as conn:
            completed = datetime.now().isoformat() if status == 'completed' else None
            conn.execute("UPDATE grant_tracker_milestones SET status=?,completed_at=? WHERE id=?", (status, completed, mid))
            conn.commit()

    def get_milestones(self, gid):
        with get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM grant_tracker_milestones WHERE grant_id=? ORDER BY deadline", (gid,)).fetchall()]

    def add_budget_item(self, gid, category, description=None, amount=0):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO grant_tracker_budget (grant_id,category,description,amount) VALUES (?,?,?,?)", (gid, category, description, amount))
            conn.commit(); return cur.lastrowid

    def get_budget_summary(self, gid):
        with get_connection() as conn:
            items = [dict(i) for i in conn.execute("SELECT * FROM grant_tracker_budget WHERE grant_id=?", (gid,)).fetchall()]
            total = sum(i['amount'] for i in items)
            by_cat = {}
            for i in items:
                by_cat[i['category']] = by_cat.get(i['category'], 0) + i['amount']
            return {"items": items, "total": round(total, 2), "by_category": by_cat}

    def get_pipeline_summary(self):
        with get_connection() as conn:
            pipeline = {}
            for row in conn.execute("SELECT status, COUNT(*) FROM grant_tracker_apps GROUP BY status").fetchall():
                pipeline[row[0]] = row[1]
            return pipeline

    def get_success_rate(self):
        with get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM grant_tracker_apps WHERE status IN ('awarded','rejected')").fetchone()[0]
            awarded = conn.execute("SELECT COUNT(*) FROM grant_tracker_apps WHERE status='awarded'").fetchone()[0]
            return {"total_decided": total, "awarded": awarded, "success_rate": round(awarded / total * 100, 1) if total > 0 else 0}

    def get_funding_by_department(self):
        with get_connection() as conn:
            return [dict(r) for r in conn.execute("""SELECT department, COUNT(*) as applications,
                SUM(amount_requested) as total_requested,
                SUM(CASE WHEN status='awarded' THEN amount_awarded ELSE 0 END) as total_awarded
                FROM grant_tracker_apps WHERE department IS NOT NULL GROUP BY department ORDER BY total_awarded DESC""").fetchall()]

    def get_upcoming_deadlines(self, days=30):
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM grant_tracker_apps WHERE deadline IS NOT NULL AND deadline>=date('now') AND deadline<=date('now',?||' days') ORDER BY deadline",
                (str(days),)).fetchall()]

    def notify_grant_deadline(self, gid: int, recipient_email: str,
                              pi_name: str = "") -> bool:
        """Email the PI a deadline reminder for grant *gid*. Best-effort."""
        app = self.get_application(gid)
        if not app:
            return False
        deadline_s = app.get('deadline') or ''
        try:
            days_remaining = (date.fromisoformat(deadline_s) - date.today()).days
        except Exception:
            days_remaining = ''
        return _send_research_email('grant_deadline_reminder', recipient_email, {
            'application_id':   gid,
            'grant_name':       app.get('title', '(untitled)'),
            'funding_agency':   app.get('funding_body') or '(not recorded)',
            'pi_name':          pi_name or app.get('principal_investigator') or 'Principal Investigator',
            'requested_amount': app.get('amount_requested') or 0,
            'deadline':         deadline_s or '(no deadline on file)',
            'days_remaining':   days_remaining,
            'status':           app.get('status') or 'draft',
            'department':       app.get('department') or '(not recorded)',
        })

    def get_pending_alerts(self):
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT a.*,g.title FROM grant_tracker_alerts a JOIN grant_tracker_apps g ON a.grant_id=g.id WHERE a.is_sent=0 ORDER BY a.alert_date").fetchall()]

    def create_deadline_alert(self, gid, alert_type, alert_date, message=None):
        with transaction() as conn:
            cur = conn.execute("INSERT INTO grant_tracker_alerts (grant_id,alert_type,alert_date,message) VALUES (?,?,?,?)", (gid, alert_type, alert_date, message))
            conn.commit(); return cur.lastrowid


def display_research_grants_menu(auth):
    """Research & Grants Management CLI — fully functional with grant tracking."""
    tracker = GrantTrackerService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("RESEARCH & GRANTS MANAGEMENT".center(70))
        print("=" * 70)
        print("\n  1. List Grant Applications")
        print("  2. Create Application")
        print("  3. Update Status")
        print("  4. View Details")
        print("  5. Pipeline Summary")
        print("  6. Milestones")
        print("  7. Budget")
        print("  8. Upcoming Deadlines")
        print("  9. Funding by Department")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            apps = tracker.list_applications()
            print(f"\n{'ID':<5} {'Title':<30} {'Funder':<20} {'Amount':<12} {'Status':<12}")
            print("-" * 80)
            for a in apps:
                print(f"{a['id']:<5} {a['title'][:28]:<30} {(a.get('funding_body','') or '')[:18]:<20} £{a.get('amount_requested',0):<10,.0f} {a['status']:<12}")
        elif choice == '2':
            title = input("Title: ").strip()
            funder = input("Funding body: ").strip()
            pi = input("Principal investigator: ").strip()
            dept = input("Department: ").strip()
            amount = float(input("Amount requested: ").strip() or '0')
            deadline = input("Deadline (YYYY-MM-DD): ").strip() or None
            gid = tracker.create_application(title, funder, pi, department=dept, amount_requested=amount, deadline=deadline)
            print(f"\nApplication created with ID: {gid}")
        elif choice == '3':
            gid = int(input("Grant ID: ").strip())
            status = input("New status (draft/submitted/under_review/shortlisted/awarded/rejected): ").strip()
            awarded = None
            if status == 'awarded':
                awarded = float(input("Amount awarded: ").strip() or '0')
            tracker.update_application_status(gid, status, awarded)
            print("Status updated.")
        elif choice == '4':
            gid = int(input("Grant ID: ").strip())
            app = tracker.get_application(gid)
            if app:
                for k, v in app.items():
                    print(f"  {k}: {v}")
            else:
                print("\nNot found.")
        elif choice == '5':
            pipeline = tracker.get_pipeline_summary()
            print("\n  Application Pipeline:")
            for s in ["draft", "submitted", "under_review", "shortlisted", "awarded", "rejected"]:
                print(f"    {s.replace('_', ' ').title()}: {pipeline.get(s, 0)}")
            success = tracker.get_success_rate()
            print(f"\n  Success Rate: {success['success_rate']}% ({success['awarded']}/{success['total_decided']})")
        elif choice == '6':
            gid = int(input("Grant ID: ").strip())
            milestones = tracker.get_milestones(gid)
            for m in milestones:
                print(f"  {m['id']}: {m['milestone_title']} | {m.get('deadline', 'No deadline')} | {m['status']}")
            sub = input("\n(a)dd milestone, (c)omplete, or Enter: ").strip().lower()
            if sub == 'a':
                title = input("Title: ").strip()
                dl = input("Deadline (YYYY-MM-DD): ").strip() or None
                tracker.add_milestone(gid, title, deadline=dl)
                print("Milestone added.")
            elif sub == 'c':
                mid = int(input("Milestone ID: ").strip())
                tracker.update_milestone(mid, 'completed')
                print("Milestone completed.")
        elif choice == '7':
            gid = int(input("Grant ID: ").strip())
            summary = tracker.get_budget_summary(gid)
            print(f"\n  Total budget: £{summary['total']:,.2f}")
            for item in summary['items']:
                print(f"    [{item['category']}] {item.get('description', '')} - £{item['amount']:,.2f}")
            if input("\nAdd item? (y/n): ").strip().lower() == 'y':
                cat = input("Category (personnel/equipment/travel/consumables/overheads/other): ").strip()
                desc = input("Description: ").strip()
                amt = float(input("Amount: ").strip())
                tracker.add_budget_item(gid, cat, desc, amt)
                print("Budget item added.")
        elif choice == '8':
            upcoming = tracker.get_upcoming_deadlines()
            if upcoming:
                for u in upcoming:
                    print(f"  [{u.get('deadline', '')}] {u['title']} ({u['status']})")
            else:
                print("\nNo upcoming deadlines.")
        elif choice == '9':
            depts = tracker.get_funding_by_department()
            print(f"\n{'Department':<20} {'Apps':<8} {'Requested':<15} {'Awarded':<15}")
            print("-" * 60)
            for d in depts:
                print(f"{(d.get('department','') or ''):<20} {d['applications']:<8} £{d.get('total_requested',0):<13,.0f} £{d.get('total_awarded',0):<13,.0f}")
        input("\nPress Enter to continue...")


# Use factory to create GUI launcher
launch_research_grants_gui = create_gui_launcher(
    title=get_text("research.grants.gui.title", "Research & Grants Management"),
    description=get_text("research.grants.gui.description", """Manage research projects, grants, publications, and equipment.

Features:
- Research project tracking
- Grant applications
- Publications management
- Milestone tracking
- Equipment inventory
- Ethics review board"""),
    cli_instruction=get_text("research.grants.gui.cli_instruction", "Use CLI: Research & Grants Management")
)



__all__ = [
    'ResearchProjectManager', 'GrantApplicationManager', 'PublicationManager',
    'MilestoneManager', 'EquipmentManager', 'EthicsReviewManager',
    'GrantTrackerService',
    'display_research_grants_menu',
    'launch_research_grants_gui',
]
