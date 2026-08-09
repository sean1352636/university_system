(function () {
  "use strict";

  const token = localStorage.getItem("edu_portal_token");
  const workspace = document.body.dataset.workspace;
  const base = "/api/v1/university/institutional";
  const message = document.getElementById("page-message");

  function signOut() {
    localStorage.removeItem("edu_portal_token");
    localStorage.removeItem("edu_portal_refresh");
    localStorage.removeItem("edu_portal_user");
    localStorage.removeItem("edu_portal_active_system");
    location.href = "/portal/";
  }

  const header = document.querySelector(".site-header");
  if (header) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sign-out";
    button.textContent = "Sign out";
    button.addEventListener("click", signOut);
    header.appendChild(button);
  }

  if (!token) {
    location.href = "/portal/login.html?next=" +
      encodeURIComponent(location.pathname);
    return;
  }

  function show(text, error) {
    if (!message) return;
    message.textContent = text;
    message.hidden = false;
    message.classList.toggle("error", Boolean(error));
    message.focus();
  }

  async function api(path, options) {
    const response = await fetch(base + path, {
      method: (options && options.method) || "GET",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: options && options.body
        ? JSON.stringify(options.body)
        : undefined,
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      location.href = "/portal/login.html?next=" +
        encodeURIComponent(location.pathname);
      throw new Error("Your session has expired.");
    }
    if (!response.ok) throw new Error(data.error || ("HTTP " + response.status));
    return data;
  }

  function value(id) {
    return document.getElementById(id).value.trim();
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function rows(target, items, columns, empty) {
    const body = document.getElementById(target);
    if (!body) return;
    body.innerHTML = items.length
      ? items.map(item => "<tr>" + columns.map(key =>
        "<td>" + escapeHtml(item[key] == null ? "—" : item[key]) + "</td>"
      ).join("") + "</tr>").join("")
      : `<tr><td colspan="${columns.length}">${escapeHtml(empty)}</td></tr>`;
  }

  async function load() {
    if (workspace === "cases") {
      const data = await api("/cases");
      rows("case-rows", data.items, ["case_id", "case_type", "status", "owner_id"],
        "No active cases.");
    } else if (workspace === "connectors") {
      const data = await api("/connectors");
      rows("connector-rows", data.items,
        ["connector_name", "enabled", "status", "last_checked_at"],
        "No connector records.");
    } else if (workspace === "timetabling") {
      const data = await api("/timetables");
      rows("timetable-rows", data.items,
        ["version_id", "academic_year", "status", "published_at"],
        "No timetable versions.");
    } else if (workspace === "pgr") {
      const query = document.getElementById("pgr-project");
      const suffix = query && query.value.trim()
        ? "?q=" + encodeURIComponent(query.value.trim()) : "";
      const data = await api("/pgr" + suffix);
      rows("pgr-rows", data.items,
        ["project_id", "student_id", "proposal_title", "status"],
        "No postgraduate research projects.");
    } else if (workspace === "programmes") {
      const data = await api("/programmes");
      rows("programme-rows", data.items,
        ["programme_id", "programme_code", "programme_name", "status"],
        "No governed programmes.");
    }
  }

  const form = document.querySelector("form[data-api-form]");
  if (form) {
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      try {
        if (workspace === "cases") {
          await api("/cases", {method: "POST", body: {
            case_type: value("case-type"),
            subject_id: value("case-student"),
            summary: value("case-summary"),
            owner_id: value("case-owner"),
          }});
          show("Case created.");
        } else if (workspace === "identity") {
          const action = form.querySelector("input[name=action]:checked").value;
          const body = {
            action,
            student_id: value("identity-primary"),
            secondary_id: value("identity-secondary"),
            reason: value("identity-reason"),
            approved_by: value("identity-approver"),
          };
          if (action === "correction") {
            body.changes = {[value("identity-field")]: value("identity-value")};
          }
          await api("/identity", {method: "POST", body});
          show("Identity workflow completed.");
        } else if (workspace === "connectors") {
          const name = value("connector-name");
          await api("/connectors/" + encodeURIComponent(name), {
            method: "PUT",
            body: {enabled: true, config: {endpoint_url: value("connector-endpoint")}},
          });
          show("Connector configured.");
        } else if (workspace === "timetabling") {
          await api("/timetables", {method: "POST", body: {
            academic_year: value("timetable-year"),
            activities: JSON.parse(value("timetable-activities")),
            slots: JSON.parse(value("timetable-slots")),
            rooms: JSON.parse(value("timetable-rooms")),
          }});
          show("Optimised timetable version created.");
        } else if (workspace === "pgr") {
          await api("/pgr", {method: "POST", body: {
            student_id: value("pgr-student"),
            proposal_title: value("pgr-title"),
            abstract: value("pgr-abstract"),
            department: value("pgr-department"),
            route: value("pgr-route"),
          }});
          show("Postgraduate research project created.");
        } else if (workspace === "programmes") {
          await api("/programmes", {method: "POST", body: {
            programme_code: value("programme-code"),
            programme_name: value("programme-title"),
            award_type: value("programme-award"),
            proposed_start_year: value("programme-year"),
            rationale: value("programme-rationale"),
          }});
          show("Programme proposal created.");
        }
        form.reset();
        await load();
      } catch (error) {
        show(error.message, true);
      }
    });
  }

  const lookup = document.getElementById("pgr-lookup");
  if (lookup) {
    lookup.addEventListener("submit", async event => {
      event.preventDefault();
      try { await load(); } catch (error) { show(error.message, true); }
    });
  }

  load().catch(error => show(error.message, true));
})();
