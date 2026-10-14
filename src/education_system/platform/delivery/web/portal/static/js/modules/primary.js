/* ── Primary School Web UI Module ───────────────────────────────────
 *  Page-renderer functions for all primary-school-specific entities.
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

  const YEAR_GROUPS = ["Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6"];
  const KEY_STAGES  = ["EYFS", "KS1", "KS2"];
  const ASSESSMENT_LEVELS = ["Emerging", "Developing", "Expected", "Greater Depth"];

  const BASE = "/web/api/primary";

  // ── Utility helpers ────────────────────────────────────────────────

  function esc(v) { return SC.esc(v); }

  /** Return key stage label for a primary year group string. */
  function _ksFromYear(yearGroup) {
    if (!yearGroup) return "-";
    const y = String(yearGroup).toLowerCase();
    if (y.includes("reception")) return "EYFS";
    if (y.includes("1") || y.includes("2")) return "KS1";
    if (["3", "4", "5", "6"].some((n) => y.includes(n))) return "KS2";
    return "-";
  }

  /**
   * Render a generic CRUD page backed by a primary-specific API endpoint.
   * (mirrors the secondary helper — kept separate for independent evolution)
   */
  async function renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody) {
    el.innerHTML = SC.LoadingSpinner();

    const page    = el._scPage   || 1;
    const search  = el._scSearch || "";
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

    const records = d.records || d.rows || d.data || d.pupils || d.classes || [];
    const total   = d.total   || records.length;
    const pages   = d.pages   || Math.ceil(total / perPage) || 1;

    const rows = records.map((r) => rowMapper(r));

    el.innerHTML = `
      ${SC.PageToolbar(title + " (" + total + ")", "pri-srch", true, "Add " + title.split(" ")[0])}
      ${SC.Pagination(total, page, perPage, "pri-pg")}
      ${SC.DataTable({ id: "pri-tbl", columns: colLabels, rows, actions: false })}
      ${SC.Modal("Add " + title.split(" ")[0], SC.FormBuilder(formFields), "Save")}
    `;

    // Search
    const searchEl = document.getElementById("sc-search-pri-srch");
    if (searchEl) {
      searchEl.value = search;
      searchEl.addEventListener("input", () => {
        el._scSearch = searchEl.value;
        el._scPage   = 1;
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
    const addBtn = document.getElementById("sc-add-btn");
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const overlay = document.getElementById("sc-modal-overlay");
        if (overlay) overlay.classList.add("active");
      });
    }

    const overlay = document.getElementById("sc-modal-overlay");
    if (overlay) {
      ["sc-modal-close", "sc-modal-cancel"].forEach((id) => {
        const btn = document.getElementById(id);
        if (btn) btn.addEventListener("click", () => { overlay.classList.remove("active"); });
      });
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.remove("active");
      });

      const form = document.getElementById("sc-modal-form");
      if (form) {
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const formData = new FormData(form);
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

          overlay.classList.remove("active");
          el._scPage = 1;
          renderCRUDPage(el, endpoint, title, colLabels, rowMapper, formFields, postBody);
        });
      }
    }
  }


  // ══════════════════════════════════════════════════════════════════
  //  PUBLIC PAGE RENDERERS
  // ══════════════════════════════════════════════════════════════════

  // ── Dashboard ──────────────────────────────────────────────────────

  async function renderPrimaryDashboard(el) {
    el.innerHTML = SC.LoadingSpinner();

    const res = await apiFetch("/web/dashboard/primary");
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
        <h2>Primary School Dashboard</h2>
        <p>${today}</p>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_students || 0}</div>
            <div class="stat-label">Pupils (Rec–Yr 6)</div></div>
            <div class="stat-icon blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
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
            <div class="stat-label">Assessments</div></div>
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
            <a class="quick-action sc-nav-link" data-page="pri:pupils">
              <div class="qa-icon">&#128100;</div><div class="qa-label">Pupils</div></a>
            <a class="quick-action sc-nav-link" data-page="pri:classes">
              <div class="qa-icon">&#127979;</div><div class="qa-label">Classes</div></a>
            <a class="quick-action sc-nav-link" data-page="pri:assessment">
              <div class="qa-icon">&#127942;</div><div class="qa-label">Assessment</div></a>
            <a class="quick-action sc-nav-link" data-page="pri:phonics">
              <div class="qa-icon">&#128218;</div><div class="qa-label">Phonics</div></a>
            <a class="quick-action sc-nav-link" data-page="pri:sats">
              <div class="qa-icon">&#128221;</div><div class="qa-label">SATs</div></a>
            <a class="quick-action sc-nav-link" data-page="pri:safeguarding">
              <div class="qa-icon">&#128737;</div><div class="qa-label">Safeguarding</div></a>
          </div>
        </div>
      </div>`;

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


  // ── Pupils ─────────────────────────────────────────────────────────

  async function renderPupilsPage(el) {
    await renderCRUDPage(
      el,
      "/web/students/primary",
      "Pupils",
      ["ID", "Name", "Year Group", "Key Stage", "Class", "UPN", "Status"],
      (p) => [
        `<strong>${esc(p.pupil_id || p.student_id || p.id || "-")}</strong>`,
        esc(p.name || ((p.first_name || "") + " " + (p.last_name || "")).trim() || "-"),
        esc(p.year_group || p.year || "-"),
        _ksFromYear(p.year_group || p.year),
        esc(p.class_name || p.class_id || "-"),
        esc(p.upn || p.uln || "-"),
        SC.StatusBadge(p.status || "active"),
      ],
      [
        { name: "first_name",   label: "First Name",     required: true },
        { name: "last_name",    label: "Last Name",       required: true },
        { name: "year_group",   label: "Year Group",      type: "select", options: YEAR_GROUPS, required: true },
        { name: "class_id",     label: "Class" },
        { name: "date_of_birth", label: "Date of Birth",  type: "date" },
        { name: "upn",          label: "UPN" },
        { name: "status",       label: "Status",          type: "select",
          options: ["active", "inactive", "transferred", "graduated"] },
      ]
    );
  }


  // ── Classes ────────────────────────────────────────────────────────

  async function renderClassesPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/classes`,
      "Classes",
      ["Class Name", "Year Group", "Key Stage", "Class Teacher", "Room", "Pupil Count"],
      (c) => [
        `<strong>${esc(c.class_name || c.name || c.group_name || "-")}</strong>`,
        esc(c.year_group || "-"),
        _ksFromYear(c.year_group),
        esc(c.teacher_name || c.class_teacher || c.staff_id || "-"),
        esc(c.room || c.classroom || "-"),
        esc(c.pupil_count || c.count || "-"),
      ],
      [
        { name: "class_name",  label: "Class Name",   required: true },
        { name: "year_group",  label: "Year Group",   type: "select", options: YEAR_GROUPS, required: true },
        { name: "staff_id",    label: "Class Teacher ID" },
        { name: "room",        label: "Room / Classroom" },
        { name: "capacity",    label: "Capacity",     type: "number" },
      ]
    );
  }


  // ── Subjects ───────────────────────────────────────────────────────

  async function renderSubjectsPage(el) {
    await renderCRUDPage(
      el,
      "/web/courses/primary",
      "Subjects",
      ["Code", "Subject Name", "Key Stage(s)", "National Curriculum", "Status"],
      (s) => [
        `<strong>${esc(s.subject_code || s.code || s.id || "-")}</strong>`,
        esc(s.subject_name || s.name || s.title || "-"),
        esc(s.key_stage || "-"),
        esc(s.national_curriculum_area || s.nc_area || "-"),
        SC.StatusBadge(s.status || "active"),
      ],
      [
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "subject_name", label: "Subject Name", required: true },
        { name: "key_stage",    label: "Key Stage",    type: "select", options: KEY_STAGES },
        { name: "nc_area",      label: "NC Area" },
        { name: "status",       label: "Status",       type: "select", options: ["active", "inactive"] },
      ]
    );
  }


  // ── Assessment ─────────────────────────────────────────────────────

  async function renderAssessmentPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/assessment`,
      "Assessment",
      ["Date", "Pupil", "Year", "Subject", "Level", "Strand", "Assessed By"],
      (r) => [
        esc(r.assessment_date || r.date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.subject_name || r.subject_code || "-"),
        `<strong class="sc-level-badge">${esc(r.level || r.assessment_level || r.grade || "-")}</strong>`,
        esc(r.strand || r.area || "-"),
        esc(r.teacher_name || r.assessed_by || r.staff_id || "-"),
      ],
      [
        { name: "pupil_id",        label: "Pupil ID",      required: true },
        { name: "subject_code",    label: "Subject Code",  required: true },
        { name: "assessment_date", label: "Assessment Date", type: "date", required: true },
        { name: "level",           label: "Level",          type: "select",
          options: ASSESSMENT_LEVELS, required: true },
        { name: "strand",          label: "Strand / Area" },
        { name: "year_group",      label: "Year Group",    type: "select", options: YEAR_GROUPS },
        { name: "notes",           label: "Notes",         type: "textarea" },
      ]
    );
  }


  // ── Attendance ─────────────────────────────────────────────────────

  async function renderAttendancePage(el) {
    await renderCRUDPage(
      el,
      "/web/attendance/primary",
      "Attendance",
      ["Date", "Pupil", "Session", "Class", "Status"],
      (r) => [
        esc(r.date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.session || r.period || "-"),
        esc(r.class_name || r.class_id || "-"),
        SC.StatusBadge(r.status || "-"),
      ],
      [
        { name: "pupil_id", label: "Pupil ID",   required: true },
        { name: "date",     label: "Date",        type: "date", required: true },
        { name: "session",  label: "Session",     type: "select", options: ["AM", "PM"] },
        { name: "status",   label: "Status",      type: "select",
          options: ["present", "absent", "late", "authorised", "unauthorised", "holiday"], required: true },
        { name: "notes",    label: "Notes",       type: "textarea" },
      ]
    );
  }


  // ── Timetable ──────────────────────────────────────────────────────

  async function renderTimetablePage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/timetable`,
      "Timetable",
      ["Day", "Period", "Class", "Subject", "Teacher", "Room"],
      (r) => [
        esc(r.day || r.day_of_week || "-"),
        esc(r.period || r.period_number || "-"),
        esc(r.class_name || r.class_id || "-"),
        esc(r.subject_name || r.subject_code || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        esc(r.room || r.room_name || "-"),
      ],
      [
        { name: "day_of_week",  label: "Day",       type: "select",
          options: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], required: true },
        { name: "period",       label: "Period",    type: "number", required: true },
        { name: "class_id",     label: "Class ID",  required: true },
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "teacher_id",   label: "Teacher ID" },
        { name: "room",         label: "Room" },
        { name: "start_time",   label: "Start Time", placeholder: "09:00" },
        { name: "end_time",     label: "End Time",   placeholder: "10:00" },
      ]
    );
  }


  // ── Homework ───────────────────────────────────────────────────────

  async function renderHomeworkPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/homework`,
      "Homework",
      ["Set Date", "Due Date", "Class", "Subject", "Title", "Teacher", "Status"],
      (r) => [
        esc(r.set_date || r.date_set || "-"),
        esc(r.due_date || "-"),
        esc(r.class_name || r.class_id || "-"),
        esc(r.subject_name || r.subject_code || "-"),
        esc(r.title || r.description || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        SC.StatusBadge(r.status || "active"),
      ],
      [
        { name: "title",       label: "Title",       required: true },
        { name: "subject_code", label: "Subject Code", required: true },
        { name: "class_id",    label: "Class ID",    required: true },
        { name: "set_date",    label: "Set Date",    type: "date", required: true },
        { name: "due_date",    label: "Due Date",    type: "date", required: true },
        { name: "year_group",  label: "Year Group",  type: "select", options: YEAR_GROUPS },
        { name: "description", label: "Description", type: "textarea" },
        { name: "estimated_mins", label: "Estimated Time (mins)", type: "number" },
      ]
    );
  }


  // ── SATs ───────────────────────────────────────────────────────────

  async function renderSATsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/sats`,
      "SATs Results",
      ["Year", "Pupil", "Subject", "SATs Level", "Raw Score", "Scaled Score", "Expected?"],
      (r) => [
        esc(r.academic_year || r.year || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.subject_name || r.subject || r.subject_code || "-"),
        esc(r.sats_level || r.level || "-"),
        esc(r.raw_score || "-"),
        esc(r.scaled_score || "-"),
        r.met_expected || r.expected
          ? '<span class="badge badge-success">Yes</span>'
          : '<span class="badge badge-danger">No</span>',
      ],
      [
        { name: "pupil_id",       label: "Pupil ID",       required: true },
        { name: "subject",        label: "Subject",         type: "select",
          options: ["Reading", "Writing", "Maths", "SPaG", "Science"], required: true },
        { name: "academic_year",  label: "Academic Year",   placeholder: "2025-2026" },
        { name: "sats_level",     label: "SATs Level",      type: "select",
          options: ["Below Expected", "Expected", "Greater Depth"] },
        { name: "raw_score",      label: "Raw Score",       type: "number" },
        { name: "scaled_score",   label: "Scaled Score",    type: "number" },
        { name: "met_expected",   label: "Met Expected Standard", type: "checkbox" },
        { name: "notes",          label: "Notes",           type: "textarea" },
      ]
    );
  }


  // ── Phonics ────────────────────────────────────────────────────────

  async function renderPhonicsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/phonics`,
      "Phonics Screening",
      ["Year", "Pupil", "Check Year", "Score", "Threshold", "Pass?", "Retake?"],
      (r) => [
        esc(r.year_group || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.check_year || r.academic_year || "-"),
        esc(r.score || r.phonics_score || "-"),
        esc(r.threshold || r.pass_threshold || "32"),
        (r.passed || r.pass) ? '<span class="badge badge-success">Pass</span>' : '<span class="badge badge-danger">Did not pass</span>',
        (r.retake || r.year2_retake) ? '<span class="badge badge-warning">Yes</span>' : '<span class="badge badge-neutral">No</span>',
      ],
      [
        { name: "pupil_id",      label: "Pupil ID",      required: true },
        { name: "check_year",    label: "Check Year",    placeholder: "2025-2026", required: true },
        { name: "score",         label: "Score (0-40)",  type: "number", required: true },
        { name: "threshold",     label: "Pass Threshold", type: "number" },
        { name: "passed",        label: "Passed",        type: "checkbox" },
        { name: "year2_retake",  label: "Year 2 Retake", type: "checkbox" },
        { name: "notes",         label: "Notes",         type: "textarea" },
      ]
    );
  }


  // ── Reading Records ────────────────────────────────────────────────

  async function renderReadingRecordsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/reading_records`,
      "Reading Records",
      ["Date", "Pupil", "Year", "Book Title", "Book Level", "Pages Read", "Comment"],
      (r) => [
        esc(r.date || r.reading_date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.book_title || r.title || "-"),
        esc(r.book_level || r.reading_level || "-"),
        esc(r.pages_read || "-"),
        esc((r.comment || r.notes || "").substring(0, 60)),
      ],
      [
        { name: "pupil_id",    label: "Pupil ID",    required: true },
        { name: "date",        label: "Date",         type: "date", required: true },
        { name: "book_title",  label: "Book Title",  required: true },
        { name: "book_level",  label: "Book Level / Band" },
        { name: "pages_read",  label: "Pages Read",  type: "number" },
        { name: "comment",     label: "Comment",     type: "textarea" },
        { name: "recorded_by", label: "Recorded By (Staff/Parent)" },
      ]
    );
  }


  // ── Behaviour ──────────────────────────────────────────────────────

  async function renderBehaviourPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/behaviour`,
      "Behaviour Records",
      ["Date", "Pupil", "Year", "Incident Type", "Severity", "Teacher", "Status"],
      (r) => [
        esc(r.date || r.incident_date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.incident_type || r.type || "-"),
        SC.StatusBadge(r.severity || "low"),
        esc(r.teacher_name || r.teacher_id || r.staff_id || "-"),
        SC.StatusBadge(r.status || "open"),
      ],
      [
        { name: "pupil_id",     label: "Pupil ID",     required: true },
        { name: "date",         label: "Date",          type: "date", required: true },
        { name: "incident_type", label: "Incident Type", type: "select",
          options: ["Disruption", "Unkind Behaviour", "Hitting/Fighting", "Damaging Property", "Defiance", "Other"], required: true },
        { name: "severity",     label: "Severity",      type: "select",
          options: ["low", "medium", "high"] },
        { name: "staff_id",     label: "Staff ID" },
        { name: "description",  label: "Description",   type: "textarea" },
        { name: "action_taken", label: "Action Taken",  type: "textarea" },
        { name: "status",       label: "Status",        type: "select",
          options: ["open", "resolved", "escalated"] },
        { name: "parent_informed", label: "Parent Informed", type: "checkbox" },
      ]
    );
  }


  // ── Rewards ────────────────────────────────────────────────────────

  async function renderRewardsPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/rewards`,
      "Rewards",
      ["Date", "Pupil", "Year", "Reward Type", "Points", "Reason", "Awarded By"],
      (r) => [
        esc(r.date || r.award_date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.reward_type || r.type || "-"),
        esc(r.points || r.value || "-"),
        esc((r.reason || r.description || "").substring(0, 60)),
        esc(r.awarded_by || r.teacher_name || r.staff_id || "-"),
      ],
      [
        { name: "pupil_id",    label: "Pupil ID",    required: true },
        { name: "date",        label: "Date",         type: "date", required: true },
        { name: "reward_type", label: "Reward Type",  type: "select",
          options: ["Star of the Week", "Sticker", "House Point", "Certificate", "Headteacher Award", "Reading Award", "Other"] },
        { name: "points",      label: "Points",       type: "number" },
        { name: "reason",      label: "Reason",       type: "textarea", required: true },
        { name: "staff_id",    label: "Staff ID" },
      ]
    );
  }


  // ── Safeguarding ───────────────────────────────────────────────────

  async function renderSafeguardingPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/safeguarding`,
      "Safeguarding Concerns",
      ["Date", "Pupil", "Year", "Concern Type", "Reported By", "Priority", "Status"],
      (r) => [
        esc(r.date || r.concern_date || r.reported_date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.concern_type || r.type || "-"),
        esc(r.reported_by || r.staff_id || "-"),
        SC.StatusBadge(r.priority || "normal"),
        SC.StatusBadge(r.status || "open"),
      ],
      [
        { name: "pupil_id",     label: "Pupil ID",     required: true },
        { name: "date",         label: "Date",          type: "date", required: true },
        { name: "concern_type", label: "Concern Type",  type: "select",
          options: ["Abuse", "Neglect", "Exploitation", "Bullying", "Self-Harm", "Domestic Violence", "FGM", "Other"], required: true },
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
      ["Pupil", "Year", "SEND Category", "Support Stage", "EHCP", "SENCO", "Review Date"],
      (r) => [
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.send_category || r.category || r.need_type || "-"),
        esc(r.support_stage || r.support_type || r.provision || "-"),
        r.has_ehcp || r.ehcp ? '<span class="badge badge-info">Yes</span>' : '<span class="badge badge-neutral">No</span>',
        esc(r.senco_name || r.senco_id || r.staff_id || "-"),
        esc(r.review_date || "-"),
      ],
      [
        { name: "pupil_id",    label: "Pupil ID",    required: true },
        { name: "send_category", label: "SEND Category", type: "select",
          options: ["Communication & Interaction", "Cognition & Learning", "Social, Emotional & Mental Health", "Sensory & Physical"], required: true },
        { name: "support_stage", label: "Support Stage", type: "select",
          options: ["Universal", "SEN Support", "EHCP", "Monitoring"] },
        { name: "has_ehcp",    label: "Has EHCP",    type: "checkbox" },
        { name: "senco_id",    label: "SENCO ID" },
        { name: "review_date", label: "Review Date", type: "date" },
        { name: "notes",       label: "Notes",       type: "textarea" },
      ]
    );
  }


  // ── Pastoral ───────────────────────────────────────────────────────

  async function renderPastoralPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/pastoral`,
      "Pastoral Notes",
      ["Date", "Pupil", "Year", "Class Teacher", "Category", "Summary"],
      (r) => [
        esc(r.date || r.note_date || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.year_group || "-"),
        esc(r.teacher_name || r.staff_id || "-"),
        esc(r.category || r.type || "-"),
        esc((r.summary || r.notes || "").substring(0, 80)),
      ],
      [
        { name: "pupil_id",   label: "Pupil ID",  required: true },
        { name: "date",       label: "Date",       type: "date", required: true },
        { name: "category",   label: "Category",   type: "select",
          options: ["Academic", "Wellbeing", "Family", "Attendance", "Behaviour", "Other"] },
        { name: "staff_id",   label: "Staff ID" },
        { name: "summary",    label: "Summary",    type: "textarea", required: true },
        { name: "follow_up",  label: "Follow-up Required", type: "checkbox" },
        { name: "follow_up_date", label: "Follow-up Date", type: "date" },
      ]
    );
  }


  // ── Parents Evening ────────────────────────────────────────────────

  async function renderParentsEveningPage(el) {
    await renderCRUDPage(
      el,
      `${BASE}/parents_evening`,
      "Parents Evening",
      ["Event Date", "Year Group", "Class", "Teacher", "Pupil", "Time Slot", "Duration", "Status"],
      (r) => [
        esc(r.event_date || r.date || "-"),
        esc(r.year_group || "-"),
        esc(r.class_name || r.class_id || "-"),
        esc(r.teacher_name || r.teacher_id || "-"),
        esc(r.pupil_name || r.student_name || r.pupil_id || r.student_id || "-"),
        esc(r.time_slot || r.appointment_time || "-"),
        esc(r.duration_mins ? r.duration_mins + " min" : r.duration || "-"),
        SC.StatusBadge(r.status || "scheduled"),
      ],
      [
        { name: "event_date",  label: "Event Date",   type: "date", required: true },
        { name: "year_group",  label: "Year Group",   type: "select", options: YEAR_GROUPS },
        { name: "teacher_id",  label: "Teacher ID",   required: true },
        { name: "pupil_id",    label: "Pupil ID",     required: true },
        { name: "time_slot",   label: "Time Slot",    placeholder: "18:30" },
        { name: "duration_mins", label: "Duration (mins)", type: "number" },
        { name: "status",      label: "Status",       type: "select",
          options: ["scheduled", "completed", "cancelled", "no-show"] },
        { name: "notes",       label: "Notes",        type: "textarea" },
      ]
    );
  }


  // ── Namespace export ───────────────────────────────────────────────

  global.PrimaryModule = {
    renderPrimaryDashboard,
    renderPupilsPage,
    renderClassesPage,
    renderSubjectsPage,
    renderAssessmentPage,
    renderAttendancePage,
    renderTimetablePage,
    renderHomeworkPage,
    renderSATsPage,
    renderPhonicsPage,
    renderReadingRecordsPage,
    renderBehaviourPage,
    renderRewardsPage,
    renderSafeguardingPage,
    renderSENDPage,
    renderPastoralPage,
    renderParentsEveningPage,
  };

})(window);
