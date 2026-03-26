/* ── Secondary School Web UI Module ─────────────────────────────────
 *  Page-renderer functions for all secondary-school-specific entities.
 *
 *  Each render function:
 *   1. Shows a loading spinner immediately.
 *   2. Fetches data from the appropriate API endpoint.
 *   3. Renders a toolbar (title + search + Add button) and a DataTable.
 *   4. Wires up client-side search, pagination, Add/Edit/Delete actions.
 *
 *  Dependencies (globals expected on window):
 *   - apiFetch(path, opts)  — from app.js
 *   - state.activeSystem    — from app.js
 *   - SC.*                  — from shared_components.js
 * ─────────────────────────────────────────────────────────────────── */

/* jshint esversion: 11 */
"use strict";

(function (global) {

  // ── Constants ──────────────────────────────────────────────────────

  const YEAR_GROUPS = ["Year 7", "Year 8", "Year 9", "Year 10", "Year 11"];
  const KEY_STAGES  = ["KS3", "KS4"];
  const GCSE_GRADES = ["9", "8", "7", "6", "5", "4", "3", "2", "1", "U"];

  const BASE = "/web/api/secondary";

  // ── Utility helpers ────────────────────────────────────────────────

  function esc(v) { return SC.esc(v); }

  /** Attach live client-side search to a table by id. */
  function bindSearch(inputId, tableId) {
    const inp = document.getElementById(inputId);
    if (!inp) return;
    inp.addEventListener("input", () => {
      const q = inp.value.toLowerCase();
      document.querySelectorAll(`#${tableId} tbody tr`).forEach((row) => {
        row.classList.toggle("sa-hidden", q && !row.textContent.toLowerCase().includes(q));
      });
    });
  }

  /** Attach modal open/close/submit behaviour.
   *  onSave(formData) is called with a FormData object on submit.
   */
  function bindModal(addBtnId, onSave) {
    const addBtn = document.getElementById(addBtnId);
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const overlay = document.getElementById("sc-modal-overlay");
        if (overlay) overlay.classList.add("active");
      });
    }

    const overlay = document.getElementById("sc-modal-overlay");
    if (!overlay) return;

    ["sc-modal-close", "sc-modal-cancel"].forEach((id) => {
      const btn = document.getElementById(id);
      if (btn) btn.addEventListener("click", () => { overlay.classList.remove("active"); });
    });

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.classList.remove("active");
    });

    const form = document.getElementById("sc-modal-form");
    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        if (onSave) onSave(new FormData(form));
      });
    }
  }

  /** Attach confirm-dialog behaviour. onConfirm() called on OK. */
  function bindConfirm(onConfirm) {
    const overlay = document.getElementById("sc-confirm-overlay");
    if (!overlay) return;
    const cancelBtn = document.getElementById("sc-confirm-cancel");
    const okBtn = document.getElementById("sc-confirm-ok");
    if (cancelBtn) cancelBtn.addEventListener("click", () => { overlay.classList.remove("active"); });
    if (okBtn) okBtn.addEventListener("click", () => {
      overlay.classList.remove("active");
      if (onConfirm) onConfirm();
    });
  }

  /**
   * Render a generic CRUD page backed by a secondary-specific API endpoint.
   *
   * @param {HTMLElement} el           Target container.
   * @param {string}      endpoint     e.g. "/web/api/secondary/behaviour"
   * @param {string}      title        Page heading.
   * @param {string[]}    colLabels    Table column headers.
   * @param {Function}    rowMapper    (record) => string[]  — cell HTML per row.
   * @param {Array}       formFields   FormBuilder field config for Add modal.
   * @param {Function}    [postBody]   (FormData) => object  — build POST body.
   */
  async function renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody) {
    el.innerHTML = SC.LoadingSpinner();

    const page = (el._scPage || 1);
    const search = (el._scSearch || "");
    const perPage = 50;

    let url = `${endpoint}?page=${page}&per_page=${perPage}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const res = await apiFetch(url);
    if (!res) return;
    const d = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load data")}</div>`;
      return;
    }

    const records = d.records || d.rows || d.data || [];
    const total   = d.total   || records.length;
    const pages   = d.pages   || Math.ceil(total / perPage) || 1;

    const rows = records.map((r) => rowMapper(r));

    el.innerHTML = `
      ${SC.PageToolbar(title + " (" + total + ")", "sec-srch", true, "Add " + title.split(" ")[0])}
      ${SC.Pagination(total, page, perPage, "sec-pg")}
      ${SC.DataTable({ id: "sec-tbl", columns: colLabels, rows, actions: false })}
      ${SC.Modal("Add " + title.split(" ")[0], SC.FormBuilder(formFields), "Save")}
    `;

    // Search
    const searchEl = document.getElementById("sc-search-sec-srch");
    if (searchEl) {
      // Restore last value
      searchEl.value = search;
      searchEl.addEventListener("input", () => {
        el._scSearch = searchEl.value;
        el._scPage = 1;
        renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody);
      });
    }

    // Pagination
    el.querySelectorAll(".sc-page-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        el._scPage = parseInt(btn.dataset.page, 10);
        renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody);
      });
    });

    // Add modal
    bindModal("sc-add-btn", async (formData) => {
      const body = postBody ? postBody(formData) : Object.fromEntries(formData);
      const alertEl = document.getElementById("sc-modal-alert");
      const saveBtn = document.getElementById("sc-modal-save");
      if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "Saving..."; }

      const postRes = await apiFetch(endpoint, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!postRes) return;
      const postData = await postRes.json();

      if (!postRes.ok) {
        if (alertEl) alertEl.innerHTML = `<div class="alert alert-error">${esc(postData.error || "Save failed")}</div>`;
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "Save"; }
        return;
      }

      const overlay = document.getElementById("sc-modal-overlay");
      if (overlay) overlay.classList.remove("active");
      el._scPage = 1;
      renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody);
    });
  }


  // ══════════════════════════════════════════════════════════════════
  //  PUBLIC PAGE RENDERERS
  // ══════════════════════════════════════════════════════════════════

  // ── Dashboard ──────────────────────────────────────────────────────

  async function renderSecondaryDashboard(el) {
    el.innerHTML = SC.LoadingSpinner();

    const res = await apiFetch(`/web/dashboard/school`);
    if (!res) return;
    const d = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
      return;
    }

    const today = new Date().toLocaleDateString("en-GB", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    });

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Secondary School Dashboard</h2>
        <p>${today}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_students || 0}</div>
            <div class="stat-label">Students (Yr 7-11)</div></div>
            <div class="stat-icon blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_courses || 0}</div>
            <div class="stat-label">Subjects</div></div>
            <div class="stat-icon purple">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
            </div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.attendance_rate != null ? d.attendance_rate + "%" : "N/A"}</div>
            <div class="stat-label">Attendance Rate</div></div>
            <div class="stat-icon green">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_grades || 0}</div>
            <div class="stat-label">Grade Entries</div></div>
            <div class="stat-icon amber">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="8" r="7"/>
                <polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>
              </svg>
            </div>
          </div>
        </div>
      </div>

      <div class="chart-grid">
        <div class="section">
          <div class="section-header"><h2>Attendance by Status</h2></div>
          ${_attendanceBars(d.attendance_breakdown || {})}
        </div>
        <div class="section">
          <div class="section-header"><h2>Quick Links</h2></div>
          <div class="quick-actions">
            <a class="quick-action sc-nav-link" data-page="sec:students">
              <div class="qa-icon">&#128100;</div><div class="qa-label">Students</div></a>
            <a class="quick-action sc-nav-link" data-page="sec:behaviour">
              <div class="qa-icon">&#128737;</div><div class="qa-label">Behaviour</div></a>
            <a class="quick-action sc-nav-link" data-page="sec:attendance">
              <div class="qa-icon">&#9989;</div><div class="qa-label">Attendance</div></a>
            <a class="quick-action sc-nav-link" data-page="sec:exams">
              <div class="qa-icon">&#128221;</div><div class="qa-label">Exams</div></a>
            <a class="quick-action sc-nav-link" data-page="sec:safeguarding">
              <div class="qa-icon">&#128737;</div><div class="qa-label">Safeguarding</div></a>
            <a class="quick-action sc-nav-link" data-page="sec:parents_evening">
              <div class="qa-icon">&#128197;</div><div class="qa-label">Parents Evening</div></a>
          </div>
        </div>
      </div>`;

    // Animate bar widths
    el.querySelectorAll(".fill[data-width]").forEach((bar) => {
      bar.style.width = bar.dataset.width + "%";
    });
  }

  function _attendanceBars(breakdown) {
    const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
    return [
      { label: "Present", key: "present", cls: "green" },
      { label: "Late",    key: "late",    cls: "amber" },
      { label: "Absent",  key: "absent",  cls: "red"   },
    ].map(({ label, key, cls }) => {
      const count = (breakdown[key] || 0) + (breakdown[key.charAt(0).toUpperCase() + key.slice(1)] || 0);
      const pct = Math.round((count / total) * 100);
      return `<div class="att-bar-row">
        <div class="att-bar-header"><span>${label}</span><span class="att-bar-count">${count} (${pct}%)</span></div>
        <div class="chart-bar"><div class="fill ${cls}" data-width="${pct}"></div></div>
      </div>`;
    }).join("");
  }


  // ── Students ───────────────────────────────────────────────────────

  async function renderStudentsPage(el) {
    await renderCRUDPage(
      el,
      "/web/students/school",
      "Students",
      ["ID", "Name", "Email", "Year Group", "Key Stage", "Status"],
      (s) => [
        `<strong>${esc(s.student_id || s.id || "-")}</strong>`,
        esc(s.name || ((s.first_name || "") + " " + (s.last_name || "")).trim() || "-"),
        esc(s.email || "-"),
        esc(s.year_group || s.year || "-"),
        _ksFromYear(s.year_group || s.year),
        SC.StatusBadge(s.status || "active"),
      ],
      [
        { name: "first_name",  label: "First Name",  required: true },
        { name: "last_name",   label: "Last Name",   required: true },
        { name: "email",       label: "Email",       type: "email" },
        { name: "year_group",  label: "Year Group",  type: "select", options: YEAR_GROUPS, required: true },
        { name: "date_of_birth", label: "Date of Birth", type: "date" },
        { name: "status",      label: "Status",      type: "select", options: ["active", "inactive", "graduated", "transferred"] },
      ]
    );
  }

  function _ksFromYear(yearGroup) {
    if (!yearGroup) return "-";
    const y = String(yearGroup);
    if (["7", "8", "9", "Year 7", "Year 8", "Year 9"].some((v) => y.includes(v))) return "KS3";
    if (["10", "11", "Year 10", "Year 11"].some((v) => y.includes(v))) return "KS4";
    return "-";
  }


  // ── Subjects ───────────────────────────────────────────────────────

  async function renderSubjectsPage(el) {
    await renderCRUDPage(
      el,
      "/web/courses/school",
      "Subjects",
      ["Code", "Name", "Department", "Key Stage", "Status"],
      (s) => [
        `<strong>${esc(s.subject_code || s.code || s.id || "-")}</strong>`,
        esc(s.subject_name || s.name || s.title || "-"),
        esc(s.department || "-"),
        esc(s.key_stage || "-"),
        SC.StatusBadge(s.status || "active"),
      ],
      [
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "subject_name", label: "Subject Name", required: true },
        { name: "department",   label: "Department" },
        { name: "key_stage",    label: "Key Stage",  type: "select", options: KEY_STAGES },
        { name: "status",       label: "Status",     type: "select", options: ["active", "inactive"] },
      ]
    );
  }


  // ── Grades ─────────────────────────────────────────────────────────

  async function renderGradesPage(el) {
    await renderCRUDPage(
      el,
      "/web/grades/school",
      "Grades",
      ["Student", "Subject", "Type", "Grade (GCSE 9-1)", "Date"],
      (g) => [
        esc(g.student_name || g.student_id || "-"),
        esc(g.course_name || g.subject_name || g.course_code || "-"),
        esc(g.assessment_type || g.type || "-"),
        `<strong class="sc-grade-badge">${esc(g.grade || g.score || "-")}</strong>`,
        esc(g.date || g.graded_at || "-"),
      ],
      [
        { name: "student_id",      label: "Student ID",   required: true },
        { name: "subject_code",    label: "Subject Code", required: true },
        { name: "assessment_type", label: "Assessment Type", type: "select",
          options: ["Classwork", "Homework", "Mock Exam", "GCSE Exam", "Coursework", "Other"] },
        { name: "grade", label: "GCSE Grade (9-1)", type: "select",
          options: GCSE_GRADES, required: true },
        { name: "date", label: "Date", type: "date" },
      ]
    );
  }


  // ── Attendance ─────────────────────────────────────────────────────

  async function renderAttendancePage(el) {
    await renderCRUDPage(
      el,
      "/web/attendance/school",
      "Attendance",
      ["Date", "Student", "Session", "Subject", "Status"],
      (r) => {
        const statusBadge = SC.StatusBadge(r.status || "-");
        return [
          esc(r.date || "-"),
          esc(r.student_name || r.student_id || "-"),
          esc(r.session || r.period || "-"),
          esc(r.course_name || r.subject_name || r.course_code || "-"),
          statusBadge,
        ];
      },
      [
        { name: "student_id", label: "Student ID",  required: true },
        { name: "date",       label: "Date",         type: "date", required: true },
        { name: "session",    label: "Session",      type: "select", options: ["AM", "PM"] },
        { name: "status",     label: "Status",       type: "select",
          options: ["present", "absent", "late", "authorised", "unauthorised"], required: true },
        { name: "notes",      label: "Notes",        type: "textarea" },
      ]
    );
  }


  // ── Timetable ──────────────────────────────────────────────────────

  async function renderTimetablePage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/timetable`,
      "Timetable",
      ["Day", "Period", "Subject", "Teacher", "Room", "Year Group"],
      (r) => [
        esc(r.day || r.day_of_week || "-"),
        esc(r.period || r.period_number || "-"),
        esc(r.subject_name || r.subject_code || r.course_name || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        esc(r.room || r.room_name || "-"),
        esc(r.year_group || "-"),
      ],
      [
        { name: "day_of_week", label: "Day", type: "select",
          options: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], required: true },
        { name: "period",      label: "Period", type: "number", required: true },
        { name: "subject_code",label: "Subject Code", required: true },
        { name: "teacher_id",  label: "Teacher ID" },
        { name: "room",        label: "Room" },
        { name: "year_group",  label: "Year Group", type: "select", options: YEAR_GROUPS },
      ]
    );
  }


  // ── Behaviour ──────────────────────────────────────────────────────

  async function renderBehaviourPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/behaviour`,
      "Behaviour Records",
      ["Date", "Student", "Year", "Incident Type", "Severity", "Teacher", "Status"],
      (r) => [
        esc(r.date || r.incident_date || "-"),
        esc(r.student_name || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.incident_type || r.type || "-"),
        SC.StatusBadge(r.severity || r.status || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        SC.StatusBadge(r.status || "open"),
      ],
      [
        { name: "student_id",    label: "Student ID",    required: true },
        { name: "date",          label: "Date",           type: "date", required: true },
        { name: "incident_type", label: "Incident Type",  type: "select",
          options: ["Disruption", "Bullying", "Phone Use", "Late", "Uniform", "Violence", "Vandalism", "Other"], required: true },
        { name: "severity",      label: "Severity",       type: "select",
          options: ["low", "medium", "high"] },
        { name: "teacher_id",    label: "Teacher ID" },
        { name: "description",   label: "Description",    type: "textarea" },
        { name: "action_taken",  label: "Action Taken",   type: "textarea" },
        { name: "status",        label: "Status",         type: "select",
          options: ["open", "resolved", "escalated"] },
      ]
    );
  }


  // ── Detentions ─────────────────────────────────────────────────────

  async function renderDetentionsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/detentions`,
      "Detentions",
      ["Date", "Time", "Student", "Year", "Reason", "Supervisor", "Status"],
      (r) => [
        esc(r.date || r.detention_date || "-"),
        esc(r.time || r.detention_time || "-"),
        esc(r.student_name || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.reason || "-"),
        esc(r.supervisor_name || r.supervisor_id || r.teacher_id || "-"),
        SC.StatusBadge(r.status || "scheduled"),
      ],
      [
        { name: "student_id",  label: "Student ID",  required: true },
        { name: "date",        label: "Date",          type: "date", required: true },
        { name: "time",        label: "Time",          type: "select",
          options: ["Lunch", "After School", "Break", "Saturday"] },
        { name: "reason",      label: "Reason",        required: true },
        { name: "supervisor_id", label: "Supervisor ID" },
        { name: "duration_mins", label: "Duration (mins)", type: "number" },
        { name: "status",      label: "Status",        type: "select",
          options: ["scheduled", "attended", "missed", "cancelled"] },
        { name: "notes",       label: "Notes",         type: "textarea" },
      ]
    );
  }


  // ── Pastoral ───────────────────────────────────────────────────────

  async function renderPastoralPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/pastoral`,
      "Pastoral Notes",
      ["Date", "Student", "Year", "Form Tutor", "Category", "Summary"],
      (r) => [
        esc(r.date || r.note_date || "-"),
        esc(r.student_name || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.tutor_name || r.staff_id || "-"),
        esc(r.category || r.type || "-"),
        esc((r.summary || r.notes || "").substring(0, 80)),
      ],
      [
        { name: "student_id", label: "Student ID",  required: true },
        { name: "date",       label: "Date",         type: "date", required: true },
        { name: "category",   label: "Category",     type: "select",
          options: ["Academic", "Wellbeing", "Family", "Attendance", "Behaviour", "Careers", "Other"] },
        { name: "staff_id",   label: "Staff ID" },
        { name: "summary",    label: "Summary",      type: "textarea", required: true },
        { name: "follow_up",  label: "Follow-up Required", type: "checkbox" },
        { name: "follow_up_date", label: "Follow-up Date", type: "date" },
      ]
    );
  }


  // ── Safeguarding ───────────────────────────────────────────────────

  async function renderSafeguardingPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/safeguarding`,
      "Safeguarding Concerns",
      ["Date", "Student", "Year", "Concern Type", "Reported By", "Priority", "Status"],
      (r) => [
        esc(r.date || r.concern_date || r.reported_date || "-"),
        esc(r.student_name || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.concern_type || r.type || "-"),
        esc(r.reported_by || r.staff_id || "-"),
        SC.StatusBadge(r.priority || "normal"),
        SC.StatusBadge(r.status || "open"),
      ],
      [
        { name: "student_id",   label: "Student ID",   required: true },
        { name: "date",         label: "Date",          type: "date", required: true },
        { name: "concern_type", label: "Concern Type",  type: "select",
          options: ["Abuse", "Neglect", "Exploitation", "Radicalisation", "Bullying", "Self-Harm", "Domestic Violence", "FGM", "Other"], required: true },
        { name: "reported_by",  label: "Reported By" },
        { name: "priority",     label: "Priority",      type: "select",
          options: ["low", "normal", "high", "urgent"] },
        { name: "description",  label: "Description",   type: "textarea", required: true },
        { name: "action_taken", label: "Action Taken",  type: "textarea" },
        { name: "status",       label: "Status",        type: "select",
          options: ["open", "referred", "closed", "monitoring"] },
      ]
    );
  }


  // ── SEND ───────────────────────────────────────────────────────────

  async function renderSENDPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/send`,
      "SEND Records",
      ["Student", "Year", "SEND Category", "Support Type", "EHCP", "SENCO", "Review Date"],
      (r) => [
        esc(r.student_name || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.send_category || r.category || r.need_type || "-"),
        esc(r.support_type || r.provision || "-"),
        r.has_ehcp || r.ehcp ? '<span class="badge badge-info">Yes</span>' : '<span class="badge badge-neutral">No</span>',
        esc(r.senco_name || r.senco_id || r.staff_id || "-"),
        esc(r.review_date || "-"),
      ],
      [
        { name: "student_id",   label: "Student ID",    required: true },
        { name: "send_category", label: "SEND Category", type: "select",
          options: ["Communication & Interaction", "Cognition & Learning", "Social, Emotional & Mental Health", "Sensory & Physical"], required: true },
        { name: "support_type", label: "Support Type",  type: "select",
          options: ["SEN Support", "EHCP", "Monitoring", "Universal"] },
        { name: "has_ehcp",     label: "Has EHCP",      type: "checkbox" },
        { name: "senco_id",     label: "SENCO ID" },
        { name: "review_date",  label: "Review Date",   type: "date" },
        { name: "notes",        label: "Notes",         type: "textarea" },
      ]
    );
  }


  // ── Form Groups ────────────────────────────────────────────────────

  async function renderFormGroupsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/form_groups`,
      "Form Groups",
      ["Form Group", "Year", "Key Stage", "Form Tutor", "Room", "Students"],
      (r) => [
        `<strong>${esc(r.form_group || r.name || r.group_name || "-")}</strong>`,
        esc(r.year_group || "-"),
        _ksFromYear(r.year_group),
        esc(r.tutor_name || r.teacher_name || r.form_tutor_id || r.staff_id || "-"),
        esc(r.room || r.room_name || "-"),
        esc(r.student_count || r.count || "-"),
      ],
      [
        { name: "group_name",     label: "Form Group Name", required: true },
        { name: "year_group",     label: "Year Group", type: "select", options: YEAR_GROUPS, required: true },
        { name: "form_tutor_id",  label: "Form Tutor ID" },
        { name: "room",           label: "Room" },
      ]
    );
  }


  // ── Homework ───────────────────────────────────────────────────────

  async function renderHomeworkPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/homework`,
      "Homework",
      ["Set Date", "Due Date", "Subject", "Year Group", "Title", "Teacher", "Status"],
      (r) => [
        esc(r.set_date || r.date_set || "-"),
        esc(r.due_date || "-"),
        esc(r.subject_name || r.subject_code || r.course_name || "-"),
        esc(r.year_group || "-"),
        esc(r.title || r.description || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        SC.StatusBadge(r.status || "active"),
      ],
      [
        { name: "title",      label: "Title",        required: true },
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "year_group", label: "Year Group",   type: "select", options: YEAR_GROUPS, required: true },
        { name: "set_date",   label: "Set Date",     type: "date", required: true },
        { name: "due_date",   label: "Due Date",     type: "date", required: true },
        { name: "description", label: "Description", type: "textarea" },
        { name: "teacher_id", label: "Teacher ID" },
        { name: "estimated_mins", label: "Estimated Time (mins)", type: "number" },
      ]
    );
  }


  // ── Exams ──────────────────────────────────────────────────────────

  async function renderExamsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/exams`,
      "Exams",
      ["Date", "Subject", "Year Group", "Type", "Duration", "Room", "Status"],
      (r) => [
        esc(r.exam_date || r.date || "-"),
        esc(r.subject_name || r.subject_code || r.course_name || "-"),
        esc(r.year_group || "-"),
        esc(r.exam_type || r.type || "-"),
        esc(r.duration_mins ? r.duration_mins + " min" : r.duration || "-"),
        esc(r.room || r.room_name || "-"),
        SC.StatusBadge(r.status || "scheduled"),
      ],
      [
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "exam_date",    label: "Exam Date",    type: "date", required: true },
        { name: "start_time",   label: "Start Time",   type: "text", placeholder: "09:00" },
        { name: "year_group",   label: "Year Group",   type: "select", options: YEAR_GROUPS },
        { name: "exam_type",    label: "Exam Type",    type: "select",
          options: ["GCSE", "Mock", "End of Year", "Module Test", "AS Level", "A Level", "Other"] },
        { name: "duration_mins", label: "Duration (mins)", type: "number" },
        { name: "room",         label: "Room" },
        { name: "status",       label: "Status",       type: "select",
          options: ["scheduled", "completed", "cancelled"] },
      ]
    );
  }


  // ── Parents Evening ────────────────────────────────────────────────

  async function renderParentsEveningPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/parents_evening`,
      "Parents Evening",
      ["Event Date", "Year Group", "Teacher", "Student", "Time Slot", "Duration", "Status"],
      (r) => [
        esc(r.event_date || r.date || "-"),
        esc(r.year_group || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        esc(r.student_name || r.student_id || "-"),
        esc(r.time_slot || r.appointment_time || "-"),
        esc(r.duration_mins ? r.duration_mins + " min" : r.duration || "-"),
        SC.StatusBadge(r.status || "scheduled"),
      ],
      [
        { name: "event_date",  label: "Event Date",   type: "date", required: true },
        { name: "year_group",  label: "Year Group",   type: "select", options: YEAR_GROUPS },
        { name: "teacher_id",  label: "Teacher ID",   required: true },
        { name: "student_id",  label: "Student ID",   required: true },
        { name: "time_slot",   label: "Time Slot",    placeholder: "18:30" },
        { name: "duration_mins", label: "Duration (mins)", type: "number" },
        { name: "status",      label: "Status",       type: "select",
          options: ["scheduled", "completed", "cancelled", "no-show"] },
        { name: "notes",       label: "Notes",        type: "textarea" },
      ]
    );
  }


  // ── Namespace export ───────────────────────────────────────────────

  global.SecondaryModule = {
    renderSecondaryDashboard,
    renderStudentsPage,
    renderSubjectsPage,
    renderGradesPage,
    renderAttendancePage,
    renderTimetablePage,
    renderBehaviourPage,
    renderDetentionsPage,
    renderPastoralPage,
    renderSafeguardingPage,
    renderSENDPage,
    renderFormGroupsPage,
    renderHomeworkPage,
    renderExamsPage,
    renderParentsEveningPage,
  };

})(window);
