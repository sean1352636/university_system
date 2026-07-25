/* ── Shared UI Components ───────────────────────────────────────────
 *  Reusable HTML-string builders used by secondary.js and primary.js.
 *  Every function returns a plain HTML string; DOM binding is the
 *  caller's responsibility.
 * ─────────────────────────────────────────────────────────────────── */

/* jshint esversion: 11 */
"use strict";

// ── Utility ──────────────────────────────────────────────────────────

/** HTML-escape a value. Falls back to empty string for null/undefined. */
function _esc(v) {
  if (v === null || v === undefined) return "";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}


// ── LoadingSpinner ────────────────────────────────────────────────────

/**
 * Returns an HTML string for a centred loading spinner.
 * @returns {string}
 */
function LoadingSpinner() {
  return '<div class="loader"><div class="spinner"></div></div>';
}


// ── StatusBadge ───────────────────────────────────────────────────────

/**
 * Returns a coloured badge span for a status string.
 * @param {string} status
 * @returns {string}
 */
function StatusBadge(status) {
  const s = (status || "").toLowerCase();
  let cls = "neutral";
  if (["active", "present", "complete", "completed", "resolved", "passed", "approved", "open"].includes(s)) cls = "success";
  else if (["inactive", "absent", "failed", "closed", "rejected", "excluded"].includes(s)) cls = "danger";
  else if (["late", "pending", "partial", "warning", "at risk", "referred"].includes(s)) cls = "warning";
  else if (["draft", "planned", "scheduled"].includes(s)) cls = "info";
  return `<span class="badge badge-${cls}">${_esc(status || "—")}</span>`;
}


// ── SearchBar ─────────────────────────────────────────────────────────

/**
 * Returns the HTML for a search input.
 * Attach an `input` listener to the element with id `sc-search-${uid}`.
 * @param {string} placeholder
 * @param {string} uid  Unique suffix to avoid id collisions.
 * @returns {string}
 */
function SearchBar(placeholder, uid) {
  const id = uid || "default";
  return `
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input id="sc-search-${_esc(id)}" type="text" placeholder="${_esc(placeholder || "Search...")}">
    </div>`;
}


// ── Pagination ────────────────────────────────────────────────────────

/**
 * Returns pagination bar HTML.
 * Bind clicks to buttons with class `sc-page-btn` and `data-page` attribute.
 * @param {number} total   Total record count.
 * @param {number} page    Current page (1-based).
 * @param {number} perPage Records per page.
 * @param {string} uid
 * @returns {string}
 */
function Pagination(total, page, perPage, uid) {
  const pages = Math.max(1, Math.ceil(total / perPage));
  if (pages <= 1) return "";
  const id = uid || "pg";
  const prevDisabled = page <= 1 ? "disabled" : "";
  const nextDisabled = page >= pages ? "disabled" : "";
  return `
    <div class="sc-pagination" data-uid="${_esc(id)}">
      <button class="btn btn-outline btn-sm sc-page-btn" data-page="${page - 1}" ${prevDisabled}>Previous</button>
      <span class="sc-page-info">Page ${page} of ${pages} (${total} records)</span>
      <button class="btn btn-outline btn-sm sc-page-btn" data-page="${page + 1}" ${nextDisabled}>Next</button>
    </div>`;
}


// ── FormBuilder ───────────────────────────────────────────────────────

/**
 * Returns an HTML form body (no <form> tag) from a field config array.
 *
 * Field object shape:
 *   { name, label, type?, required?, options?, placeholder?, value? }
 *
 * `type` values: text (default), textarea, select, date, number, email,
 *                checkbox, hidden
 * `options` (for select): array of strings or { value, label } objects.
 *
 * @param {Array<object>} fields
 * @returns {string}
 */
function FormBuilder(fields) {
  return (fields || []).map((f) => {
    const id = `fb-${_esc(f.name)}`;
    const req = f.required ? "required" : "";
    const ph = f.placeholder ? `placeholder="${_esc(f.placeholder)}"` : "";
    const val = f.value !== undefined ? _esc(f.value) : "";

    if (f.type === "hidden") {
      return `<input type="hidden" id="${id}" name="${_esc(f.name)}" value="${val}">`;
    }
    if (f.type === "textarea") {
      return `
        <div class="form-group">
          <label for="${id}">${_esc(f.label)}${f.required ? ' <span style="color:var(--accent-danger)">*</span>' : ""}</label>
          <textarea id="${id}" name="${_esc(f.name)}" rows="3" class="sc-textarea" ${ph} ${req}>${val}</textarea>
        </div>`;
    }
    if (f.type === "select") {
      const opts = (f.options || []).map((o) => {
        const optVal = typeof o === "object" ? _esc(o.value) : _esc(o);
        const optLabel = typeof o === "object" ? _esc(o.label) : _esc(o);
        const sel = val && val === optVal ? "selected" : "";
        return `<option value="${optVal}" ${sel}>${optLabel}</option>`;
      }).join("");
      return `
        <div class="form-group">
          <label for="${id}">${_esc(f.label)}${f.required ? ' <span style="color:var(--accent-danger)">*</span>' : ""}</label>
          <select id="${id}" name="${_esc(f.name)}" ${req}><option value="">— Select —</option>${opts}</select>
        </div>`;
    }
    if (f.type === "checkbox") {
      const chk = val === "true" || val === "1" ? "checked" : "";
      return `
        <div class="form-group sc-checkbox-group">
          <label><input type="checkbox" id="${id}" name="${_esc(f.name)}" ${chk}> ${_esc(f.label)}</label>
        </div>`;
    }
    const inputType = f.type || "text";
    return `
      <div class="form-group">
        <label for="${id}">${_esc(f.label)}${f.required ? ' <span style="color:var(--accent-danger)">*</span>' : ""}</label>
        <input type="${inputType}" id="${id}" name="${_esc(f.name)}" value="${val}" ${ph} ${req}>
      </div>`;
  }).join("");
}


// ── Modal ─────────────────────────────────────────────────────────────

/**
 * Returns a modal overlay HTML string.
 *
 * The modal overlay has id `sc-modal-overlay`.
 * The save button has id `sc-modal-save`.
 * The cancel/close button has id `sc-modal-close`.
 * The form body is rendered inside a <form id="sc-modal-form">.
 *
 * @param {string} title
 * @param {string} body  Inner HTML for the modal body (usually FormBuilder output).
 * @param {string} [saveLabel]
 * @returns {string}
 */
function Modal(title, body, saveLabel) {
  return `
    <div class="modal-overlay" id="sc-modal-overlay">
      <div class="modal sc-modal">
        <div class="sc-modal-header">
          <h2>${_esc(title)}</h2>
          <button class="sc-modal-x" id="sc-modal-close" type="button">&times;</button>
        </div>
        <div id="sc-modal-alert"></div>
        <form id="sc-modal-form" autocomplete="off">
          ${body || ""}
          <div class="modal-actions">
            <button type="button" class="btn btn-outline btn-sm" id="sc-modal-cancel">Cancel</button>
            <button type="submit" class="btn btn-primary btn-sm" id="sc-modal-save">
              ${_esc(saveLabel || "Save")}
            </button>
          </div>
        </form>
      </div>
    </div>`;
}


// ── ConfirmDialog ─────────────────────────────────────────────────────

/**
 * Returns an HTML confirmation dialog overlay.
 *
 * Overlay id: `sc-confirm-overlay`.
 * Confirm button id: `sc-confirm-ok`.
 * Cancel button id: `sc-confirm-cancel`.
 *
 * @param {string} message
 * @param {string} [confirmLabel]
 * @returns {string}
 */
function ConfirmDialog(message, confirmLabel) {
  return `
    <div class="modal-overlay" id="sc-confirm-overlay">
      <div class="modal sc-confirm-modal">
        <p class="sc-confirm-msg">${_esc(message)}</p>
        <div class="modal-actions">
          <button type="button" class="btn btn-outline btn-sm" id="sc-confirm-cancel">Cancel</button>
          <button type="button" class="btn btn-danger btn-sm" id="sc-confirm-ok">
            ${_esc(confirmLabel || "Delete")}
          </button>
        </div>
      </div>
    </div>`;
}


// ── DataTable ─────────────────────────────────────────────────────────

/**
 * Returns a full data table HTML string.
 *
 * config shape:
 * {
 *   id?:        string,      // table element id (default: "sc-data-table")
 *   columns:    string[],    // column header labels
 *   rows:       string[][],  // pre-rendered cell HTML per row
 *   emptyMsg?:  string,
 *   actions?:   boolean,     // add an Actions column
 * }
 *
 * @param {object} config
 * @returns {string}
 */
function DataTable(config) {
  const id = config.id || "sc-data-table";
  const cols = config.columns || [];
  const rows = config.rows || [];
  const emptyMsg = config.emptyMsg || "No records found.";
  const withActions = config.actions !== false;

  const thead = `<thead><tr>
    ${cols.map((c) => `<th>${_esc(c)}</th>`).join("")}
    ${withActions ? "<th>Actions</th>" : ""}
  </tr></thead>`;

  const tbody = rows.length === 0
    ? `<tr><td colspan="${cols.length + (withActions ? 1 : 0)}" class="sc-empty-cell">${_esc(emptyMsg)}</td></tr>`
    : rows.map((cells) => `<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("");

  return `
    <div class="section" style="overflow-x:auto;">
      <table class="data-table" id="${_esc(id)}">
        ${thead}
        <tbody>${tbody}</tbody>
      </table>
    </div>`;
}


// ── Page Toolbar ──────────────────────────────────────────────────────

/**
 * Returns a standard page toolbar with title, search bar, and an
 * optional "Add New" button.
 *
 * @param {string}  title
 * @param {string}  searchUid  Passed to SearchBar()
 * @param {boolean} canAdd
 * @param {string}  [addLabel]
 * @returns {string}
 */
function PageToolbar(title, searchUid, canAdd, addLabel) {
  return `
    <div class="page-header">
      <h1>${_esc(title)}</h1>
      <div style="display:flex;gap:8px;align-items:center;">
        ${SearchBar("Search...", searchUid)}
        ${canAdd ? `<button class="btn btn-primary btn-sm" id="sc-add-btn">+ ${_esc(addLabel || "Add New")}</button>` : ""}
      </div>
    </div>`;
}


// ── Exports ──────────────────────────────────────────────────────────
// These are attached to window so app.js and module scripts can use them
// without a module bundler.

window.SC = window.SC || {};
Object.assign(window.SC, {
  esc: _esc,
  LoadingSpinner,
  StatusBadge,
  SearchBar,
  Pagination,
  FormBuilder,
  Modal,
  ConfirmDialog,
  DataTable,
  PageToolbar,
});
