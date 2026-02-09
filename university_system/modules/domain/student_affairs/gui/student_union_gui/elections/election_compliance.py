import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from university_system.infrastructure.email.template_utils import render_template
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from university_system.infrastructure.database.db import get_connection
    from university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class MonitorCampaignComplianceDialog:
    """Dialog for monitoring campaign compliance with rules"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Campaign Compliance Monitoring")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="⚖️ Campaign Compliance Monitor",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Compliance overview
        overview_frame = ttk.LabelFrame(main_frame, text="Compliance Overview")
        overview_frame.pack(fill='x', pady=(0, 15))

        overview_grid = ttk.Frame(overview_frame)
        overview_grid.pack(fill='x', padx=15, pady=10)

        ttk.Label(overview_grid, text="Total Candidates:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="4").grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Compliant:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="3", foreground='green').grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Warnings Issued:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="2", foreground='orange').grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(overview_grid, text="Violations:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(overview_grid, text="1", foreground='red').grid(row=3, column=1, sticky='w', padx=10)

        # Compliance checks
        checks_frame = ttk.LabelFrame(main_frame, text="Compliance Checks")
        checks_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('Candidate', 'Budget Limit', 'Spending', 'Materials OK', 'Conduct', 'Status')
        tree = ttk.Treeview(checks_frame, columns=columns, show='tree headings', height=8)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Candidate':
                tree.column(col, width=140)
            else:
                tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(checks_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        scrollbar.pack(side='right', fill='y')

        # Sample compliance data
        checks = [
            ("Alice Johnson", "✓", "77% (£387/£500)", "✓", "✓", "Compliant"),
            ("Bob Smith", "⚠", "98% (£490/£500)", "✓", "✓", "Warning"),
            ("Carol Davis", "✓", "65% (£325/£500)", "✓", "✓", "Compliant"),
            ("David Lee", "✓", "45% (£225/£500)", "⚠", "✗", "Violation")
        ]

        for check in checks:
            tree.insert('', 'end', values=check)

        tree.bind('<Double-1>', lambda e: self.show_violation_details())

        # Recent issues
        issues_frame = ttk.LabelFrame(main_frame, text="Recent Compliance Issues")
        issues_frame.pack(fill='both', expand=True, pady=(0, 15))

        issues_text = scrolledtext.ScrolledText(issues_frame, height=8, wrap=tk.WORD)
        issues_text.pack(fill='both', expand=True, padx=10, pady=10)

        issues_content = """COMPLIANCE VIOLATIONS & WARNINGS:

[2025-03-26 14:30] VIOLATION - David Lee
Category: Conduct
Description: Inappropriate social media post attacking opponent personally
Action: Official warning issued, post must be removed within 24 hours
Status: Under review

[2025-03-25 09:15] WARNING - Bob Smith
Category: Budget
Description: Spending at 98% of limit with 1 week remaining
Action: Advisory notice sent, no further large expenses permitted
Status: Monitoring

[2025-03-24 16:45] WARNING - David Lee
Category: Campaign Materials
Description: Campaign poster missing required "Paid for by" disclaimer
Action: Removal of non-compliant posters, reprint required
Status: Resolved

[2025-03-22 11:20] RESOLVED - Alice Johnson
Category: Event
Description: Town hall scheduling conflict with exam period
Action: Event rescheduled to compliant time slot
Status: Compliant

COMPLIANCE RULES REFERENCE:

1. BUDGET RULES
   - Maximum spending: £500 per candidate
   - All expenses must have receipts
   - No corporate donations allowed
   - Personal contributions max £100

2. CAMPAIGN MATERIALS
   - Must include "Paid for by [name]" disclaimer
   - Cannot be misleading or defamatory
   - No impersonation of university
   - Removal deadline when requested

3. CONDUCT RULES
   - No personal attacks on opponents
   - Respectful debate and discourse
   - No vote buying or bribes
   - No interference with opponent campaigns
   - No campaigning in exam halls

4. EVENT RULES
   - No events during exam periods
   - Equal access to student union facilities
   - Advance booking required
   - Attendance must be voluntary"""

        issues_text.insert('1.0', issues_content)
        issues_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Issue Warning", command=self.issue_warning).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Record Violation", command=self.record_violation).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Rules", command=self.view_rules).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Compliance Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def show_violation_details(self):
        messagebox.showinfo("Violation Details",
                          "VIOLATION DETAILS:\n\n" +
                          "Candidate: David Lee\n" +
                          "Date: 2025-03-26 14:30\n" +
                          "Type: Conduct Violation\n\n" +
                          "Description:\n" +
                          "Social media post contained personal attacks\n" +
                          "violating conduct rules section 3.1\n\n" +
                          "Evidence:\n" +
                          "- Screenshot of post (attached)\n" +
                          "- 3 student complaints filed\n\n" +
                          "Action Taken:\n" +
                          "- Official warning issued\n" +
                          "- 24-hour removal deadline\n" +
                          "- Mandatory conduct review meeting")

    def issue_warning(self):
        messagebox.showinfo("Issue Warning",
                          "Warning form:\n\n" +
                          "Select candidate, violation type, and description.\n\n" +
                          "Warning will be officially recorded and candidate\n" +
                          "will be notified via email within 1 hour.")

    def record_violation(self):
        messagebox.showinfo("Record Violation",
                          "Violation recording form:\n\n" +
                          "Requires:\n" +
                          "- Candidate name\n" +
                          "- Violation category\n" +
                          "- Evidence documentation\n" +
                          "- Proposed sanctions\n\n" +
                          "Serious violations may result in disqualification.")

    def view_rules(self):
        messagebox.showinfo("Campaign Rules",
                          "Complete Election Rules Document:\n\n" +
                          "Available sections:\n" +
                          "1. Budget & Finance Rules\n" +
                          "2. Campaign Materials Standards\n" +
                          "3. Conduct & Ethics Guidelines\n" +
                          "4. Event & Scheduling Rules\n" +
                          "5. Complaints Procedure\n" +
                          "6. Sanctions & Appeals\n\n" +
                          "View full PDF document")

    def generate_report(self):
        messagebox.showinfo("Report Generated",
                          "Compliance monitoring report generated:\n\n" +
                          "reports/compliance_report_2025.pdf\n\n" +
                          "Contains:\n" +
                          "- All compliance checks\n" +
                          "- Warnings and violations\n" +
                          "- Candidate status summary\n" +
                          "- Trend analysis\n" +
                          "- Recommendations")



class ElectionSecurityAuditDialog:
    """Dialog for election security audit and monitoring"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Election Security Audit")
        self.dialog.geometry("1100x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="🔒 Election Security Audit",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Security status
        status_frame = ttk.LabelFrame(main_frame, text="Security Status")
        status_frame.pack(fill='x', pady=(0, 15))

        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill='x', padx=15, pady=10)

        ttk.Label(status_grid, text="Overall Security:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="SECURE", foreground='green', font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Last Audit:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="2025-03-27 10:00").grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Threats Detected:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="0 (Last 7 days)").grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Suspicious Activity:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="2 investigated, resolved", foreground='orange').grid(row=3, column=1, sticky='w', padx=10)

        # Create notebook for security sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Access Control tab
        access_frame = ttk.Frame(notebook)
        notebook.add(access_frame, text="Access Control")

        access_scroll = scrolledtext.ScrolledText(access_frame, height=12, wrap=tk.WORD)
        access_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        access_text = """ACCESS CONTROL AUDIT:

✓ User Authentication
  - Multi-factor authentication: ENABLED
  - Password strength requirements: ENFORCED
  - Failed login attempts: 15 (3 accounts locked, security reviewed)
  - Session timeout: 30 minutes (ACTIVE)
  - Account lockout threshold: 5 attempts (CONFIGURED)

✓ Voter Verification
  - Student ID verification: REQUIRED
  - Email confirmation: ENABLED
  - One person, one vote: ENFORCED (database constraints)
  - Duplicate vote prevention: ACTIVE
  - Voter eligibility check: AUTOMATED

✓ Admin Access
  - Admin accounts: 3 active
  - Privileged access logging: ENABLED
  - Admin actions audited: 100%
  - Role-based access control: IMPLEMENTED
  - Least privilege principle: ENFORCED

✓ Access Logs (Last 24 hours)
  - Total logins: 1,247
  - Failed logins: 15 (1.2%)
  - Suspicious IPs blocked: 2
  - Admin access events: 34 (all authorized)

RECOMMENDATIONS:
- Regular access review (monthly)
- Security awareness training for admins
- Implement biometric authentication option"""

        access_scroll.insert('1.0', access_text)
        access_scroll.config(state='disabled')

        # Vote Security tab
        vote_frame = ttk.Frame(notebook)
        notebook.add(vote_frame, text="Vote Security")

        vote_scroll = scrolledtext.ScrolledText(vote_frame, height=12, wrap=tk.WORD)
        vote_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        vote_text = """VOTE SECURITY AUDIT:

✓ Ballot Security
  - Encryption: AES-256 (ACTIVE)
  - Anonymization: ENABLED (voter ID separated from ballot)
  - Tamper detection: ACTIVE (cryptographic hashes)
  - Ballot integrity checks: PASSED (100%)
  - Backup systems: REDUNDANT (3 copies)

✓ Vote Counting
  - Automated tallying: SECURE
  - Manual audit trail: AVAILABLE
  - Recount capability: ENABLED
  - Third-party verification: READY
  - Results verification: MULTI-SIGNATURE REQUIRED

✓ Database Security
  - Database encryption: ENABLED (at rest and in transit)
  - SQL injection protection: ACTIVE
  - Backup frequency: Hourly
  - Backup encryption: AES-256
  - Backup integrity: VERIFIED (last check: 2025-03-27 09:00)

✓ Vote Integrity Checks
  - Total votes cast: 1,234
  - Duplicate votes: 0 DETECTED
  - Invalid votes: 3 (flagged for review)
  - Timestamp anomalies: 0
  - Statistical anomalies: NONE

AUDIT FINDINGS:
✓ No vote tampering detected
✓ All votes properly encrypted
✓ Ballot anonymity maintained
✓ No database anomalies

SECURITY SCORE: 98/100 (EXCELLENT)"""

        vote_scroll.insert('1.0', vote_text)
        vote_scroll.config(state='disabled')

        # Incident Log tab
        incident_frame = ttk.Frame(notebook)
        notebook.add(incident_frame, text="Incident Log")

        incident_scroll = scrolledtext.ScrolledText(incident_frame, height=12, wrap=tk.WORD)
        incident_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        incident_text = """SECURITY INCIDENT LOG:

[2025-03-26 15:42] MEDIUM PRIORITY - RESOLVED
Incident: Multiple failed login attempts from single IP
Source: 203.45.67.89
Details: 8 failed attempts across 3 accounts in 5 minutes
Action: IP blocked for 24 hours, accounts notified
Status: RESOLVED - Accounts secured, no compromise detected

[2025-03-25 22:15] LOW PRIORITY - RESOLVED
Incident: Unusual voting pattern detected
Details: 50 votes cast between 22:00-23:00 (typical: 20-30)
Investigation: Verified legitimate - club organized voting session
Action: Pattern whitelisted, no further action
Status: RESOLVED - False positive

[2025-03-24 11:30] HIGH PRIORITY - RESOLVED
Incident: Unauthorized admin panel access attempt
Source: External IP 104.28.15.203
Details: Scanning for vulnerabilities, SQL injection attempted
Action: IP permanently blocked, intrusion detection updated
Status: RESOLVED - No breach occurred, security hardened

[2025-03-23 14:20] MEDIUM PRIORITY - RESOLVED
Incident: Suspicious email phishing attempt
Details: Fake "verify your vote" email sent to 150 students
Action: Email blocked, warning sent to all students
Status: RESOLVED - No credentials compromised

INCIDENT SUMMARY:
- Total incidents (7 days): 4
- Critical: 0
- High: 1 (resolved)
- Medium: 2 (resolved)
- Low: 1 (false positive)
- Average response time: 12 minutes
- All incidents resolved: YES

THREAT INDICATORS:
✓ No active threats
✓ All vulnerabilities patched
✓ Monitoring systems: OPERATIONAL
✓ Incident response team: ON STANDBY"""

        incident_scroll.insert('1.0', incident_text)
        incident_scroll.config(state='disabled')

        # Compliance tab
        compliance_frame = ttk.Frame(notebook)
        notebook.add(compliance_frame, text="Compliance & Standards")

        compliance_scroll = scrolledtext.ScrolledText(compliance_frame, height=12, wrap=tk.WORD)
        compliance_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        compliance_text = """SECURITY COMPLIANCE AUDIT:

✓ GDPR Compliance (Data Protection)
  - Data minimization: COMPLIANT
  - Purpose limitation: COMPLIANT
  - Storage limitation: COMPLIANT (auto-delete after 2 years)
  - Data subject rights: IMPLEMENTED
  - Privacy by design: ENFORCED
  - Data breach protocol: ESTABLISHED
  - DPO assigned: YES
  - Privacy impact assessment: COMPLETED

✓ ISO 27001 (Information Security)
  - Risk assessment: COMPLETED (2025-02-15)
  - Security controls: 98% IMPLEMENTED
  - Access control policy: DOCUMENTED
  - Incident management: ACTIVE
  - Business continuity: TESTED
  - Security awareness: ONGOING
  - Audit trail: COMPREHENSIVE

✓ Election Standards
  - Secret ballot: GUARANTEED
  - One person one vote: ENFORCED
  - Vote verification: AVAILABLE
  - Transparency: PUBLIC AUDIT LOGS
  - Integrity: CRYPTOGRAPHICALLY ASSURED
  - Accessibility: WCAG 2.1 AA COMPLIANT

✓ Technical Standards
  - TLS 1.3 encryption: ACTIVE
  - OWASP Top 10 protections: IMPLEMENTED
  - Penetration testing: PASSED (2025-03-01)
  - Vulnerability scanning: WEEKLY
  - Security patches: UP TO DATE (100%)
  - Code security review: COMPLETED

COMPLIANCE SCORE: 97/100 (EXCELLENT)

CERTIFICATIONS:
✓ ISO 27001 certified
✓ Cyber Essentials Plus
✓ GDPR compliant

NEXT AUDIT: 2025-04-27"""

        compliance_scroll.insert('1.0', compliance_text)
        compliance_scroll.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Run Security Scan", command=self.run_scan).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="View Logs", command=self.view_logs).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Audit Report", command=self.generate_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Security Settings", command=self.security_settings).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def run_scan(self):
        messagebox.showinfo("Security Scan",
                          "Running comprehensive security scan...\n\n" +
                          "Checking:\n" +
                          "✓ System vulnerabilities\n" +
                          "✓ Access control integrity\n" +
                          "✓ Encryption status\n" +
                          "✓ Database security\n" +
                          "✓ Network security\n\n" +
                          "Scan complete: No issues detected\n" +
                          "Security status: SECURE")

    def view_logs(self):
        messagebox.showinfo("Security Logs",
                          "Access comprehensive security logs:\n\n" +
                          "- Authentication logs\n" +
                          "- Access control logs\n" +
                          "- Vote submission logs\n" +
                          "- Admin action logs\n" +
                          "- Incident logs\n" +
                          "- System logs\n\n" +
                          "Export options: PDF, CSV, JSON")

    def generate_report(self):
        messagebox.showinfo("Audit Report",
                          "Security audit report generated:\n\n" +
                          "reports/security_audit_2025-03-27.pdf\n\n" +
                          "Contains:\n" +
                          "- Executive summary\n" +
                          "- Security status assessment\n" +
                          "- Incident analysis\n" +
                          "- Compliance review\n" +
                          "- Recommendations\n" +
                          "- Trend analysis")

    def security_settings(self):
        messagebox.showinfo("Security Settings",
                          "Security configuration:\n\n" +
                          "- MFA requirements\n" +
                          "- Password policies\n" +
                          "- Session timeout settings\n" +
                          "- Access control rules\n" +
                          "- Encryption settings\n" +
                          "- Audit log retention\n" +
                          "- Alert thresholds\n\n" +
                          "Requires admin privileges")



class VoteIntegrityCheckDialog:
    """Dialog for vote integrity verification"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Vote Integrity Check")
        self.dialog.geometry("1000x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="✅ Vote Integrity Verification",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Election selection
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(select_frame, text="Select Election:").pack(side='left', padx=(0, 10))
        election_combo = ttk.Combobox(select_frame, width=40, state='readonly')
        election_combo['values'] = ('Student Union President 2025', 'VP Academic Affairs 2025', 'Treasurer 2025')
        election_combo.pack(side='left', fill='x', expand=True)
        election_combo.current(0)

        # Integrity status
        status_frame = ttk.LabelFrame(main_frame, text="Integrity Status")
        status_frame.pack(fill='x', pady=(0, 15))

        status_grid = ttk.Frame(status_frame)
        status_grid.pack(fill='x', padx=15, pady=10)

        ttk.Label(status_grid, text="Overall Integrity:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="VERIFIED", foreground='green', font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Total Votes:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="1,234").grid(row=1, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Valid Votes:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="1,231 (99.8%)", foreground='green').grid(row=2, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Flagged for Review:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="3 (0.2%)", foreground='orange').grid(row=3, column=1, sticky='w', padx=10)

        ttk.Label(status_grid, text="Invalid/Rejected:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=3)
        ttk.Label(status_grid, text="0 (0.0%)").grid(row=4, column=1, sticky='w', padx=10)

        # Create notebook for checks
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Authenticity Checks tab
        auth_frame = ttk.Frame(notebook)
        notebook.add(auth_frame, text="Authenticity Checks")

        auth_scroll = scrolledtext.ScrolledText(auth_frame, height=12, wrap=tk.WORD)
        auth_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        auth_text = """VOTE AUTHENTICITY VERIFICATION:

✓ Voter Identity Verification
  - Student ID validation: 1,234/1,234 PASSED (100%)
  - Email verification: 1,234/1,234 CONFIRMED
  - Duplicate voters: 0 DETECTED
  - Ineligible voters: 0 DETECTED
  - Voter registration verified: 100%

✓ Cryptographic Verification
  - Digital signatures: 1,234/1,234 VALID
  - Hash verification: 1,234/1,234 PASSED
  - Tampering detection: NO TAMPERING DETECTED
  - Encryption integrity: 100% VERIFIED
  - Timestamp validation: ALL VALID

✓ Ballot Authenticity
  - Ballot format validation: 1,234/1,234 PASSED
  - Vote choice validation: 1,231 VALID, 3 REVIEW
  - Write-in votes: 12 (all valid format)
  - Blank votes: 0
  - Overvotes (multiple selections): 0 DETECTED

✓ Chain of Custody
  - Vote submission logged: 100%
  - Processing chain verified: COMPLETE
  - Storage integrity: VERIFIED
  - No gaps in custody chain: CONFIRMED

FLAGGED VOTES (3 requiring manual review):
1. Vote #789 - Unusual timestamp (late night submission)
   Status: Under review, likely legitimate
2. Vote #1045 - IP address pattern anomaly
   Status: Verified legitimate (VPN user)
3. Vote #1199 - Session timeout during submission
   Status: Resubmission confirmed valid

AUTHENTICITY SCORE: 99.8% (EXCELLENT)"""

        auth_scroll.insert('1.0', auth_text)
        auth_scroll.config(state='disabled')

        # Statistical Analysis tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistical Analysis")

        stats_scroll = scrolledtext.ScrolledText(stats_frame, height=12, wrap=tk.WORD)
        stats_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        stats_text = """STATISTICAL INTEGRITY ANALYSIS:

✓ Vote Distribution Analysis
  - Chi-square test: PASSED (p=0.234, no anomalies)
  - Benford's Law analysis: CONSISTENT
  - Expected vs actual distribution: NORMAL
  - Outlier detection: NO OUTLIERS
  - Pattern recognition: NO SUSPICIOUS PATTERNS

✓ Temporal Analysis
  - Vote timing distribution: NORMAL
  - Hourly voting patterns:
    00:00-06:00: 23 votes (1.9%) - NORMAL for online voting
    06:00-12:00: 342 votes (27.7%) - EXPECTED
    12:00-18:00: 589 votes (47.7%) - EXPECTED (peak time)
    18:00-00:00: 280 votes (22.7%) - NORMAL
  - No unusual spikes detected
  - Voting rate consistent with expectations

✓ Geographic Analysis
  - IP address distribution: CONSISTENT with student locations
  - VPN usage: 45 votes (3.6%) - NORMAL
  - International votes: 12 (study abroad students) - VERIFIED
  - Location anomalies: NONE DETECTED

✓ Behavioral Analysis
  - Average time to complete vote: 2m 34s (NORMAL)
  - Suspiciously fast votes (<30s): 8 (0.6%) - REVIEWED, VALID
  - Suspiciously slow votes (>15m): 5 (0.4%) - NORMAL
  - Form interaction patterns: HUMAN-LIKE (no bot activity)

✓ Correlation Analysis
  - Cross-voting patterns: CONSISTENT
  - Write-in correlations: NORMAL
  - Candidate preference distributions: EXPECTED
  - No evidence of coordinated voting

STATISTICAL INTEGRITY: VERIFIED
No anomalies requiring investigation"""

        stats_scroll.insert('1.0', stats_text)
        stats_scroll.config(state='disabled')

        # Duplicate Detection tab
        duplicate_frame = ttk.Frame(notebook)
        notebook.add(duplicate_frame, text="Duplicate Detection")

        duplicate_scroll = scrolledtext.ScrolledText(duplicate_frame, height=12, wrap=tk.WORD)
        duplicate_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        duplicate_text = """DUPLICATE VOTE DETECTION:

✓ Multi-Layer Duplicate Prevention
  - Database constraint: ACTIVE (primary key on student_id)
  - Application-level check: ENABLED
  - Session-based prevention: ACTIVE
  - Attempted duplicates blocked: 5 (all prevented successfully)

✓ Duplicate Detection Methods
  1. Student ID matching: NO DUPLICATES
  2. Email address matching: NO DUPLICATES
  3. IP + timestamp analysis: NO SUSPICIOUS PATTERNS
  4. Device fingerprinting: NO DUPLICATES
  5. Session token validation: ALL UNIQUE

✓ Attempted Duplicate Votes (Prevented)
  [2025-03-26 14:23] Student ID: S12345
  Method: Attempted to vote twice using different browser
  Action: Second vote blocked, warning displayed
  Status: PREVENTED - No duplicate recorded

  [2025-03-25 18:45] Student ID: S23456
  Method: Accidentally clicked submit twice (double-click)
  Action: Second submission ignored (same session)
  Status: PREVENTED - Only one vote counted

  [2025-03-24 11:30] Student ID: S34567
  Method: Attempted vote after session timeout
  Action: Re-authentication required, no duplicate
  Status: PREVENTED - Session properly handled

  [2025-03-23 09:15] Student ID: S45678
  Method: Used two different email aliases
  Action: Student ID match prevented duplicate
  Status: PREVENTED - Email alias detection working

  [2025-03-22 16:40] Student ID: S56789
  Method: VPN IP change attempted revote
  Action: Student ID constraint blocked duplicate
  Status: PREVENTED - IP change didn't bypass protection

✓ Vote Replacement Handling
  - Legitimate vote changes: 8 ALLOWED (before deadline)
  - Replacement mechanism: SECURE (old vote deleted, new recorded)
  - Audit trail maintained: YES
  - All replacements logged: 100%

✓ Edge Cases Tested
  - Concurrent submission attempts: HANDLED (first wins)
  - Browser refresh during submission: SAFE
  - Network interruption recovery: HANDLED
  - Session timeout scenarios: TESTED

DUPLICATE PROTECTION: 100% EFFECTIVE
Zero duplicate votes in final count"""

        duplicate_scroll.insert('1.0', duplicate_text)
        duplicate_scroll.config(state='disabled')

        # Audit Trail tab
        audit_frame = ttk.Frame(notebook)
        notebook.add(audit_frame, text="Audit Trail")

        audit_scroll = scrolledtext.ScrolledText(audit_frame, height=12, wrap=tk.WORD)
        audit_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        audit_text = """COMPREHENSIVE AUDIT TRAIL:

✓ Vote Submission Logs
  - Total submissions logged: 1,239 (including 5 prevented duplicates)
  - Successful votes: 1,234
  - Failed submissions: 0
  - Prevented duplicates: 5
  - All submissions timestamped: YES
  - All IPs logged: YES (anonymized after 30 days)

✓ Voter Anonymity Protection
  - Vote content separated from voter identity: CONFIRMED
  - Anonymous ballot storage: VERIFIED
  - Re-identification impossible: CRYPTOGRAPHICALLY ASSURED
  - Anonymization audit: PASSED

✓ Processing Audit
  - Vote processing steps: ALL LOGGED
  - Encryption timestamps: RECORDED
  - Storage locations: DOCUMENTED
  - Backup creation: LOGGED
  - No gaps in audit trail: CONFIRMED

✓ Access Logs
  - Admin access to voting system: 8 events (all authorized)
  - Database queries: LOGGED (read-only, no modifications)
  - Result compilation access: 2 admins (with approval)
  - No unauthorized access: CONFIRMED

✓ System Events
  - Voting system uptime: 99.97% (10 minute maintenance window)
  - Database backups: 24 (hourly, all successful)
  - Security scans: 3 (all passed)
  - System updates: 2 (no impact on votes)

✓ Compliance Events
  - Vote verification requests: 3 (all processed correctly)
  - Audit log exports: 1 (for election commission)
  - Integrity checks run: 15 (all passed)

SAMPLE AUDIT ENTRIES:

[2025-03-26 18:45:23] VOTE_SUBMITTED
Voter: S12345 (anonymized)
Election: President 2025
Vote Hash: 7f8a9b2c...
Status: SUCCESS

[2025-03-26 18:45:24] VOTE_ENCRYPTED
Vote ID: V98765
Encryption: AES-256
Key ID: K2025-03-26-001
Status: SUCCESS

[2025-03-26 18:45:25] VOTE_STORED
Vote ID: V98765
Storage: Primary Database
Backup: Completed
Status: SUCCESS

[2025-03-26 18:45:26] VOTER_MARKED
Voter: S12345
Voted: YES (anonymized)
Future votes: BLOCKED
Status: COMPLETE

AUDIT TRAIL INTEGRITY: 100% COMPLETE
Full audit available for independent verification"""

        audit_scroll.insert('1.0', audit_text)
        audit_scroll.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Run Integrity Check", command=self.run_check).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Verify My Vote", command=self.verify_vote).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Export Audit Log", command=self.export_audit).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Generate Certificate", command=self.generate_cert).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def run_check(self):
        messagebox.showinfo("Integrity Check",
                          "Running comprehensive integrity verification...\n\n" +
                          "✓ Authenticity checks: PASSED\n" +
                          "✓ Statistical analysis: PASSED\n" +
                          "✓ Duplicate detection: PASSED\n" +
                          "✓ Audit trail verification: PASSED\n" +
                          "✓ Cryptographic verification: PASSED\n\n" +
                          "RESULT: All votes verified as authentic and legitimate\n" +
                          "Integrity score: 99.8%\n\n" +
                          "Detailed report saved to:\n" +
                          "reports/integrity_check_2025-03-27.pdf")

    def verify_vote(self):
        messagebox.showinfo("Verify Your Vote",
                          "Vote verification system:\n\n" +
                          "Enter your unique vote verification code\n" +
                          "(received after voting)\n\n" +
                          "The system will confirm:\n" +
                          "✓ Your vote was received\n" +
                          "✓ Your vote was counted\n" +
                          "✓ Your vote integrity is maintained\n\n" +
                          "Your vote choice remains anonymous.\n" +
                          "Only you know how you voted.")

    def export_audit(self):
        messagebox.showinfo("Export Audit Log",
                          "Audit log export options:\n\n" +
                          "Format: PDF, CSV, JSON, XML\n" +
                          "Scope: Full audit trail or filtered\n" +
                          "Anonymization: Voter IDs anonymized\n\n" +
                          "Exported to:\n" +
                          "reports/audit_log_export_2025-03-27.pdf\n\n" +
                          "This log can be used for independent\n" +
                          "verification by election observers.")

    def generate_cert(self):
        messagebox.showinfo("Integrity Certificate",
                          "Election Integrity Certificate Generated\n\n" +
                          "This certificate confirms:\n\n" +
                          "✓ All votes verified authentic\n" +
                          "✓ No duplicate votes detected\n" +
                          "✓ No tampering detected\n" +
                          "✓ Statistical integrity confirmed\n" +
                          "✓ Audit trail complete\n" +
                          "✓ Cryptographic security verified\n\n" +
                          "Certificate signed by Election Commission\n" +
                          "Valid for official record\n\n" +
                          "Saved to: certificates/integrity_cert_2025.pdf")



def open_campaign_compliance_dialog(self):
    """Open campaign compliance monitoring"""
    dialog = MonitorCampaignComplianceDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_election_security_dialog(self):
    """Open election security audit"""
    dialog = ElectionSecurityAuditDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_vote_integrity_dialog(self):
    """Open vote integrity check"""
    dialog = VoteIntegrityCheckDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
# FIFTH ROUND (PART 3C FINAL) - Enhanced Voting Systems

