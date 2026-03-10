/* ============================================================
   University Management System — Web Portal Application
   ============================================================ */

(function () {
  "use strict";

  // ============ Configuration ============
  var API_BASE = "/api";

  // ============ State ============
  var state = {
    token: localStorage.getItem("ums_token") || null,
    refreshToken: localStorage.getItem("ums_refresh") || null,
    user: JSON.parse(localStorage.getItem("ums_user") || "null"),
  };

  // ============ DOM References ============
  var dom = {};

  function cacheDom() {
    dom.loginPage = document.getElementById("login-page");
    dom.app = document.getElementById("app");
    dom.loginForm = document.getElementById("login-form");
    dom.loginError = document.getElementById("login-error");
    dom.loginBtn = document.getElementById("login-btn");
    dom.usernameInput = document.getElementById("login-username");
    dom.passwordInput = document.getElementById("login-password");
    dom.headerTitle = document.getElementById("header-title");
    dom.headerUser = document.getElementById("header-user-name");
    dom.userAvatar = document.getElementById("user-avatar");
    dom.logoutBtn = document.getElementById("logout-btn");
    dom.content = document.getElementById("content");
    dom.sidebarNav = document.getElementById("sidebar-nav");
    dom.modalOverlay = document.getElementById("modal-overlay");
    dom.modalTitle = document.getElementById("modal-title");
    dom.modalBody = document.getElementById("modal-body");
    dom.modalSaveBtn = document.getElementById("modal-save-btn");
    dom.modalCloseBtn = document.getElementById("modal-close-btn");
    dom.modalCancelBtn = document.getElementById("modal-cancel-btn");
    dom.toastContainer = document.getElementById("toast-container");
    dom.sidebarToggle = document.getElementById("sidebar-toggle");
    dom.sidebar = document.getElementById("sidebar");
  }

  // ============ API Client ============
  function apiFetch(endpoint, options) {
    options = options || {};
    var headers = { "Content-Type": "application/json" };
    if (state.token) {
      headers["Authorization"] = "Bearer " + state.token;
    }
    if (options.headers) {
      for (var k in options.headers) headers[k] = options.headers[k];
    }
    options.headers = headers;

    return fetch(API_BASE + endpoint, options)
      .then(function (resp) {
        if (resp.status === 401) {
          return tryRefreshToken().then(function (ok) {
            if (ok) {
              headers["Authorization"] = "Bearer " + state.token;
              options.headers = headers;
              return fetch(API_BASE + endpoint, options);
            }
            handleUnauthorized();
            return null;
          });
        }
        return resp;
      })
      .catch(function (err) {
        showToast("Network error: " + err.message, "error");
        return null;
      });
  }

  function apiGet(endpoint) {
    return apiFetch(endpoint, { method: "GET" });
  }

  function apiPost(endpoint, data) {
    return apiFetch(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  function apiPut(endpoint, data) {
    return apiFetch(endpoint, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  function apiDelete(endpoint) {
    return apiFetch(endpoint, { method: "DELETE" });
  }

  // ============ Token Refresh ============
  function tryRefreshToken() {
    if (!state.refreshToken) return Promise.resolve(false);
    return fetch(API_BASE + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    })
      .then(function (resp) {
        if (!resp.ok) return false;
        return resp.json().then(function (data) {
          state.token = data.access_token;
          localStorage.setItem("ums_token", data.access_token);
          return true;
        });
      })
      .catch(function () {
        return false;
      });
  }

  // ============ Authentication ============
  var _mfaState = { token: null, methods: [], selectedMethod: "totp" };

  function handleLogin(e) {
    e.preventDefault();
    var username = dom.usernameInput.value.trim();
    var password = dom.passwordInput.value;

    if (!username || !password) {
      showLoginError("Please enter both username and password.");
      return;
    }

    dom.loginBtn.disabled = true;
    dom.loginBtn.textContent = "Signing in...";

    fetch(API_BASE + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: username, password: password }),
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { ok: resp.ok, status: resp.status, data: data };
        });
      })
      .then(function (result) {
        dom.loginBtn.disabled = false;
        dom.loginBtn.textContent = "Sign In";

        if (!result.ok) {
          showLoginError(result.data.error || "Login failed.");
          return;
        }

        if (result.data.password_reset_required) {
          showLoginError(
            "Password reset required. Please use the main application."
          );
          return;
        }

        if (result.data.mfa_required) {
          // Show MFA verification form
          _mfaState.token = result.data.mfa_token;
          _mfaState.methods = result.data.mfa_methods || [];
          _mfaState.selectedMethod = _mfaState.methods.length > 0
            ? (_mfaState.methods[0].type || "totp") : "totp";
          showMfaForm();
          return;
        }

        if (result.data.requires_2fa) {
          showLoginError(
            "Two-factor authentication required. Please use the main application."
          );
          return;
        }

        // Success
        completeLogin(result.data);
      })
      .catch(function (err) {
        dom.loginBtn.disabled = false;
        dom.loginBtn.textContent = "Sign In";
        showLoginError("Connection error. Is the API server running?");
      });
  }

  function completeLogin(data) {
    state.token = data.access_token;
    state.refreshToken = data.refresh_token;
    state.user = data.user;
    localStorage.setItem("ums_token", state.token);
    localStorage.setItem("ums_refresh", state.refreshToken);
    localStorage.setItem("ums_user", JSON.stringify(state.user));

    showApp();
    navigate("dashboard");
    showToast("Welcome back, " + state.user.username + "!", "success");
  }

  function showMfaForm() {
    dom.loginError.classList.remove("show");
    var loginCard = dom.loginForm.parentElement;

    var html = '<div class="mfa-form" id="mfa-form">';
    html += '<div class="mfa-info">Enter your verification code to complete sign-in.</div>';

    // Method selector (if multiple methods)
    if (_mfaState.methods.length > 1) {
      html += '<div class="mfa-method-selector">';
      _mfaState.methods.forEach(function (m) {
        var mType = m.type || m;
        var label = mType === "totp" ? "Authenticator" : mType === "sms" ? "SMS" : mType === "email" ? "Email" : mType;
        var active = mType === _mfaState.selectedMethod ? " active" : "";
        html += '<button type="button" class="mfa-method-btn' + active + '" data-method="' + mType + '">' + escHtml(label) + '</button>';
      });
      html += '</div>';
    }

    html += '<div class="mfa-code-row">';
    html += '<div class="form-group"><label>Verification Code</label>';
    html += '<input class="form-control mfa-code-input" type="text" id="mfa-code" maxlength="10" placeholder="000000" autocomplete="one-time-code"></div>';
    html += '<button class="btn btn-primary btn-lg" id="mfa-verify-btn" type="button">Verify</button>';
    html += '</div>';

    // Send code button for SMS/email
    var selType = _mfaState.selectedMethod;
    if (selType === "sms" || selType === "email") {
      html += '<button class="btn btn-outline btn-sm" id="mfa-send-btn" type="button" style="margin-top:10px">Send Code</button>';
    }

    html += '<div class="mfa-back-link" id="mfa-back">Back to login</div>';
    html += '</div>';

    // Hide the login form, show MFA
    dom.loginForm.style.display = "none";
    var existing = document.getElementById("mfa-form");
    if (existing) existing.remove();
    loginCard.insertAdjacentHTML("beforeend", html);

    // Attach events
    document.getElementById("mfa-verify-btn").addEventListener("click", handleMfaVerify);
    document.getElementById("mfa-code").addEventListener("keypress", function (e) {
      if (e.key === "Enter") handleMfaVerify();
    });
    document.getElementById("mfa-back").addEventListener("click", function () {
      document.getElementById("mfa-form").remove();
      dom.loginForm.style.display = "";
      _mfaState.token = null;
    });

    var sendBtn = document.getElementById("mfa-send-btn");
    if (sendBtn) {
      sendBtn.addEventListener("click", handleMfaSendCode);
    }

    // Method selector clicks
    var methodBtns = document.querySelectorAll(".mfa-method-btn");
    for (var i = 0; i < methodBtns.length; i++) {
      methodBtns[i].addEventListener("click", function () {
        _mfaState.selectedMethod = this.getAttribute("data-method");
        // Re-render
        document.getElementById("mfa-form").remove();
        dom.loginForm.style.display = "none";
        loginCard.insertAdjacentHTML("beforeend", "");
        showMfaForm();
      });
    }

    document.getElementById("mfa-code").focus();
  }

  function handleMfaVerify() {
    var code = document.getElementById("mfa-code").value.trim();
    if (!code) { showToast("Please enter a verification code.", "error"); return; }

    var btn = document.getElementById("mfa-verify-btn");
    btn.disabled = true;
    btn.textContent = "Verifying...";

    fetch(API_BASE + "/auth/mfa/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _mfaState.token,
      },
      body: JSON.stringify({ code: code, method: _mfaState.selectedMethod }),
    })
      .then(function (resp) {
        return resp.json().then(function (data) {
          return { ok: resp.ok, data: data };
        });
      })
      .then(function (result) {
        btn.disabled = false;
        btn.textContent = "Verify";

        if (!result.ok) {
          showToast(result.data.error || "Verification failed.", "error");
          return;
        }

        // MFA passed — complete login
        var mfaForm = document.getElementById("mfa-form");
        if (mfaForm) mfaForm.remove();
        dom.loginForm.style.display = "";
        _mfaState.token = null;

        completeLogin(result.data);
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Verify";
        showToast("Connection error during MFA verification.", "error");
      });
  }

  function handleMfaSendCode() {
    var btn = document.getElementById("mfa-send-btn");
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = "Sending...";

    fetch(API_BASE + "/auth/mfa/send-code", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + _mfaState.token,
      },
      body: JSON.stringify({ method: _mfaState.selectedMethod }),
    })
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        btn.disabled = false;
        btn.textContent = "Send Code";
        showToast(data.message || "Code sent!", "success");
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Send Code";
        showToast("Failed to send code.", "error");
      });
  }

  function handleLogout() {
    apiPost("/auth/logout", {}).finally(function () {
      state.token = null;
      state.refreshToken = null;
      state.user = null;
      localStorage.removeItem("ums_token");
      localStorage.removeItem("ums_refresh");
      localStorage.removeItem("ums_user");
      showLogin();
    });
  }

  function handleUnauthorized() {
    state.token = null;
    state.refreshToken = null;
    state.user = null;
    localStorage.removeItem("ums_token");
    localStorage.removeItem("ums_refresh");
    localStorage.removeItem("ums_user");
    showLogin();
    showToast("Session expired. Please log in again.", "warning");
  }

  function showLoginError(msg) {
    dom.loginError.textContent = msg;
    dom.loginError.classList.add("show");
  }

  function showLogin() {
    dom.loginPage.style.display = "flex";
    dom.app.classList.remove("active");
    dom.loginError.classList.remove("show");
    dom.usernameInput.value = "";
    dom.passwordInput.value = "";
    window.location.hash = "";
  }

  function showApp() {
    dom.loginPage.style.display = "none";
    dom.app.classList.add("active");
    if (state.user) {
      dom.headerUser.textContent = state.user.username;
      dom.userAvatar.textContent = (state.user.username || "U")
        .charAt(0)
        .toUpperCase();
    }
  }

  // ============ Router ============
  var navItems = [
    {
      section: "Overview",
      items: [{ id: "dashboard", label: "Dashboard", icon: "\u25A3" }],
    },
    {
      section: "Academic",
      items: [
        { id: "students", label: "Students", icon: "\u25CB" },
        { id: "courses", label: "Courses", icon: "\u25C7" },
        { id: "modules", label: "Modules", icon: "\u25A1" },
        { id: "enrollments", label: "Enrollments", icon: "\u25B7" },
        { id: "grades", label: "Grades", icon: "\u2606" },
        { id: "assignments", label: "Assignments", icon: "\u2610" },
        { id: "attendance", label: "Attendance", icon: "\u2714" },
        { id: "exams", label: "Exams", icon: "\u2637" },
      ],
    },
    {
      section: "Services",
      items: [
        { id: "finance", label: "Finance", icon: "\u00A4" },
        { id: "housing", label: "Housing", icon: "\u2302" },
        { id: "library", label: "Library", icon: "\u2261" },
        { id: "events", label: "Events", icon: "\u2605" },
        { id: "dining", label: "Dining", icon: "\u2615" },
        { id: "facilities", label: "Facilities", icon: "\u2692" },
      ],
    },
    {
      section: "People",
      items: [
        { id: "users", label: "Users", icon: "\u263A" },
        { id: "alumni", label: "Alumni", icon: "\u2660" },
        { id: "clubs", label: "Clubs", icon: "\u2663" },
      ],
    },
    {
      section: "Support",
      items: [
        { id: "announcements", label: "Announcements", icon: "\u266A" },
        { id: "helpdesk", label: "Help Desk", icon: "\u2709" },
      ],
    },
    {
      section: "Account",
      items: [
        { id: "settings", label: "Settings", icon: "\u2699" },
      ],
    },
  ];

  function buildSidebar() {
    var html = "";
    navItems.forEach(function (section) {
      html += '<div class="nav-section">';
      html +=
        '<div class="nav-section-title">' + escHtml(section.section) + "</div>";
      section.items.forEach(function (item) {
        html +=
          '<a class="nav-link" data-page="' +
          item.id +
          '" href="#/' +
          item.id +
          '">';
        html += '<span class="nav-icon">' + item.icon + "</span>";
        html += escHtml(item.label);
        html += "</a>";
      });
      html += "</div>";
    });
    dom.sidebarNav.innerHTML = html;

    // Attach click handlers
    var links = dom.sidebarNav.querySelectorAll(".nav-link");
    for (var i = 0; i < links.length; i++) {
      links[i].addEventListener("click", function (e) {
        e.preventDefault();
        var page = this.getAttribute("data-page");
        navigate(page);
        // Close sidebar on mobile
        dom.sidebar.classList.remove("open");
      });
    }
  }

  function navigate(page) {
    window.location.hash = "#/" + page;
  }

  function handleRoute() {
    var hash = window.location.hash.replace(/^#\/?/, "") || "dashboard";
    var pageName = hash.split("/")[0];

    if (!state.token) {
      showLogin();
      return;
    }

    showApp();
    updateActiveNav(pageName);
    renderPage(pageName);
  }

  function updateActiveNav(page) {
    var links = dom.sidebarNav.querySelectorAll(".nav-link");
    for (var i = 0; i < links.length; i++) {
      var linkPage = links[i].getAttribute("data-page");
      if (linkPage === page) {
        links[i].classList.add("active");
      } else {
        links[i].classList.remove("active");
      }
    }
    // Update header title
    var title = page.charAt(0).toUpperCase() + page.slice(1).replace(/-/g, " ");
    dom.headerTitle.textContent = title;
  }

  // ============ UI Utilities ============
  function escHtml(str) {
    if (str === null || str === undefined) return "";
    var d = document.createElement("div");
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
  }

  function showToast(message, type) {
    type = type || "success";
    var toast = document.createElement("div");
    toast.className = "toast toast-" + type;

    var icons = { success: "\u2713", error: "\u2717", warning: "\u26A0", info: "\u2139" };
    toast.innerHTML =
      "<span>" +
      (icons[type] || "") +
      "</span><span>" +
      escHtml(message) +
      '</span><button class="toast-close">\u00D7</button>';

    dom.toastContainer.appendChild(toast);

    var closeBtn = toast.querySelector(".toast-close");
    closeBtn.addEventListener("click", function () {
      removeToast(toast);
    });

    setTimeout(function () {
      removeToast(toast);
    }, 4000);
  }

  function removeToast(toast) {
    if (!toast.parentNode) return;
    toast.classList.add("removing");
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }

  var _modalSaveHandler = null;

  function showModal(title, bodyHtml, onSave, saveLabel) {
    dom.modalTitle.textContent = title;
    dom.modalBody.innerHTML = bodyHtml;
    dom.modalSaveBtn.textContent = saveLabel || "Save";
    dom.modalOverlay.classList.add("active");

    if (_modalSaveHandler) {
      dom.modalSaveBtn.removeEventListener("click", _modalSaveHandler);
    }
    _modalSaveHandler = onSave;
    if (onSave) {
      dom.modalSaveBtn.style.display = "";
      dom.modalSaveBtn.addEventListener("click", _modalSaveHandler);
    } else {
      dom.modalSaveBtn.style.display = "none";
    }
  }

  function closeModal() {
    dom.modalOverlay.classList.remove("active");
    if (_modalSaveHandler) {
      dom.modalSaveBtn.removeEventListener("click", _modalSaveHandler);
      _modalSaveHandler = null;
    }
  }

  function showConfirm(title, message, onConfirm) {
    var html =
      '<div class="confirm-dialog">' +
      '<div class="confirm-title">' +
      escHtml(title) +
      "</div>" +
      "<p>" +
      escHtml(message) +
      "</p></div>";
    showModal(
      "Confirm",
      html,
      function () {
        closeModal();
        onConfirm();
      },
      "Confirm"
    );
  }

  function showLoading() {
    return '<div class="loading"><div class="spinner"></div> Loading...</div>';
  }

  function buildTable(columns, rows, actions) {
    if (!rows || rows.length === 0) {
      return (
        '<div class="table-empty"><p>No records found.</p></div>'
      );
    }
    var html = '<div class="table-wrapper"><table><thead><tr>';
    columns.forEach(function (col) {
      html += "<th>" + escHtml(col.label) + "</th>";
    });
    if (actions) html += "<th>Actions</th>";
    html += "</tr></thead><tbody>";

    rows.forEach(function (row, idx) {
      html += "<tr>";
      columns.forEach(function (col) {
        var val = row[col.key];
        if (col.render) {
          html += "<td>" + col.render(val, row) + "</td>";
        } else {
          html += "<td>" + escHtml(val !== undefined && val !== null ? val : "-") + "</td>";
        }
      });
      if (actions) {
        html += '<td><div class="table-actions">';
        actions.forEach(function (action) {
          html +=
            '<button class="btn btn-sm ' +
            (action.cls || "btn-secondary") +
            '" data-action="' +
            action.name +
            '" data-index="' +
            idx +
            '">' +
            escHtml(action.label) +
            "</button>";
        });
        html += "</div></td>";
      }
      html += "</tr>";
    });

    html += "</tbody></table></div>";
    return html;
  }

  function buildPagination(pagination) {
    if (!pagination || pagination.total_pages <= 1) return "";
    var html = '<div class="pagination-bar">';
    html +=
      '<div class="pagination-info">Showing page ' +
      pagination.page +
      " of " +
      pagination.total_pages +
      " (" +
      pagination.total +
      " total)</div>";
    html += '<div class="pagination-controls">';

    html +=
      '<button data-pg-page="' +
      (pagination.page - 1) +
      '"' +
      (pagination.has_prev ? "" : " disabled") +
      '>&laquo; Prev</button>';

    var start = Math.max(1, pagination.page - 2);
    var end = Math.min(pagination.total_pages, pagination.page + 2);
    for (var p = start; p <= end; p++) {
      html +=
        '<button data-pg-page="' +
        p +
        '"' +
        (p === pagination.page ? ' class="active"' : "") +
        ">" +
        p +
        "</button>";
    }

    html +=
      '<button data-pg-page="' +
      (pagination.page + 1) +
      '"' +
      (pagination.has_next ? "" : " disabled") +
      ">Next &raquo;</button>";

    html += "</div></div>";
    return html;
  }

  function buildFormField(name, label, type, value, options) {
    type = type || "text";
    value = value !== undefined && value !== null ? value : "";
    var html = '<div class="form-group">';
    html += "<label>" + escHtml(label) + "</label>";
    if (type === "select" && options) {
      html += '<select class="form-control" name="' + name + '">';
      options.forEach(function (opt) {
        var optVal = typeof opt === "string" ? opt : opt.value;
        var optLabel = typeof opt === "string" ? opt : opt.label;
        var selected = optVal == value ? " selected" : "";
        html +=
          "<option value=\"" +
          escHtml(optVal) +
          '"' +
          selected +
          ">" +
          escHtml(optLabel) +
          "</option>";
      });
      html += "</select>";
    } else if (type === "textarea") {
      html +=
        '<textarea class="form-control" name="' +
        name +
        '" rows="3">' +
        escHtml(value) +
        "</textarea>";
    } else {
      html +=
        '<input class="form-control" type="' +
        type +
        '" name="' +
        name +
        '" value="' +
        escHtml(value) +
        '">';
    }
    html += "</div>";
    return html;
  }

  function getFormData(container) {
    var data = {};
    var inputs = container.querySelectorAll("input, select, textarea");
    for (var i = 0; i < inputs.length; i++) {
      var el = inputs[i];
      var name = el.getAttribute("name");
      if (name) {
        data[name] = el.value;
      }
    }
    return data;
  }

  function badgeHtml(text, type) {
    type = type || "secondary";
    return '<span class="badge badge-' + type + '">' + escHtml(text) + "</span>";
  }

  // ============ Page Rendering ============
  function renderPage(page) {
    var renderer = pageRenderers[page];
    if (renderer) {
      renderer();
    } else {
      renderGenericList(page);
    }
  }

  // ============ Page: Dashboard ============
  function renderDashboard() {
    dom.content.innerHTML = showLoading();
    apiGet("/dashboard/stats").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var s = data.stats || {};
        var role = data.role || (state.user && state.user.role) || "student";
        var username = (state.user && state.user.username) || "";

        var html = '<div class="dashboard-welcome"><h2>Welcome back, ' + escHtml(username) + '</h2>';
        html += '<p>' + escHtml(role.charAt(0).toUpperCase() + role.slice(1)) + ' Dashboard</p></div>';

        if (role === "admin") {
          html += renderAdminDashboard(s);
        } else if (role === "staff") {
          html += renderStaffDashboard(s);
        } else if (role === "instructor") {
          html += renderInstructorDashboard(s);
        } else {
          html += renderStudentDashboard(s);
        }

        dom.content.innerHTML = html;
      });
    });
  }

  function renderAdminDashboard(s) {
    var html = '<div class="quick-stats">';
    html += quickStatCard("Students", s.students, "S", "qs-blue");
    html += quickStatCard("Courses", s.courses, "C", "qs-green");
    html += quickStatCard("Modules", s.modules, "M", "qs-orange");
    html += quickStatCard("Users", s.users, "U", "qs-cyan");
    html += quickStatCard("Active Users", s.active_users, "A", "qs-purple");
    html += quickStatCard("Payments", s.payments, "P", "qs-red");
    html += "</div>";

    html += '<div class="section-grid">';
    html += sectionCard("User Breakdown", [
      ["Admin Users", s.admin_users],
      ["Staff Users", s.staff_users],
      ["Instructors", s.instructor_users],
      ["Students", s.student_users],
      ["Enrollments", s.enrollments],
    ]);
    html += sectionCard("Academic", [
      ["Assignments", s.assignments],
      ["Attendance Sessions", s.attendance_sessions],
      ["Assessments", s.assessments],
      ["Exams", s.exams],
      ["Degree Programs", s.degree_programs],
      ["Misconduct Cases", s.misconduct_cases],
    ]);
    html += sectionCard("Campus Services", [
      ["Housing Applications", s.housing_applications],
      ["Books in Library", s.books],
      ["Active Loans", s.book_loans],
      ["Events", s.events],
      ["Facility Bookings", s.facility_bookings],
      ["Parking Permits", s.parking_permits],
    ]);
    html += sectionCard("Support & Operations", [
      ["Open Support Tickets", s.open_support_tickets],
      ["Pending Leave Requests", s.pending_leave_requests],
      ["Health Appointments", s.health_appointments],
      ["Maintenance Requests", s.maintenance_requests],
      ["Staff Members", s.staff],
      ["Departments", s.departments],
    ]);
    html += "</div>";
    return html;
  }

  function renderStaffDashboard(s) {
    var html = '<div class="quick-stats">';
    html += quickStatCard("Staff", s.staff, "S", "qs-blue");
    html += quickStatCard("Departments", s.departments, "D", "qs-green");
    html += quickStatCard("Leave Requests", s.leave_requests, "L", "qs-orange");
    html += quickStatCard("Open Tickets", s.open_support_tickets, "T", "qs-red");
    html += "</div>";

    html += '<div class="section-grid">';
    html += sectionCard("HR Overview", [
      ["Pending Leave", s.pending_leave_requests],
      ["Approved Leave", s.approved_leave_requests],
      ["Shifts", s.shifts],
      ["Timesheets", s.timesheets],
    ]);
    html += sectionCard("Operations", [
      ["Support Tickets", s.support_tickets],
      ["Maintenance Requests", s.maintenance_requests],
      ["Announcements", s.announcements],
      ["Events", s.events],
    ]);
    html += "</div>";
    return html;
  }

  function renderInstructorDashboard(s) {
    var html = '<div class="quick-stats">';
    html += quickStatCard("My Modules", s.assigned_modules, "M", "qs-blue");
    html += quickStatCard("My Students", s.total_students, "S", "qs-green");
    html += quickStatCard("Assignments", s.assignments, "A", "qs-orange");
    html += quickStatCard("Exams", s.exams, "E", "qs-purple");
    html += "</div>";

    html += '<div class="section-grid">';
    html += sectionCard("Teaching", [
      ["Assessments", s.assessments],
      ["Attendance Sessions", s.attendance_sessions],
      ["Misconduct Cases", s.misconduct_cases],
      ["Course Evaluations", s.course_evaluations],
    ]);
    html += "</div>";
    return html;
  }

  function renderStudentDashboard(s) {
    var html = '<div class="quick-stats">';
    html += quickStatCard("Enrolled Modules", s.enrolled_modules, "M", "qs-blue");
    html += quickStatCard("Assignments", s.total_assignments, "A", "qs-orange");
    html += quickStatCard("Grades", s.grades_recorded, "G", "qs-green");
    html += quickStatCard("Attendance", (s.attendance_percentage || 0) + "%", "%", "qs-purple");
    html += "</div>";

    html += '<div class="section-grid">';
    html += sectionCard("Academic Progress", [
      ["Enrolled Modules", s.enrolled_modules],
      ["Assignments", s.total_assignments],
      ["Grades Recorded", s.grades_recorded],
      ["Upcoming Exams", s.upcoming_exams],
    ]);

    var attPct = s.attendance_percentage || 0;
    var balanceStr = s.financial_balance !== undefined ? "$" + s.financial_balance : "$0.00";
    html += '<div class="section-card"><h3>Status</h3>';
    html += '<div class="stat-row"><span class="stat-key">Attendance</span><span class="stat-val">' + attPct + '%</span></div>';
    html += '<div class="progress-bar-container"><div class="progress-bar-fill" style="width:' + Math.min(attPct, 100) + '%"></div></div>';
    html += '<div class="stat-row" style="margin-top:12px"><span class="stat-key">Financial Balance</span><span class="stat-val">' + escHtml(balanceStr) + '</span></div>';
    html += '<div class="stat-row"><span class="stat-key">Announcements</span><span class="stat-val">' + (s.announcements || 0) + '</span></div>';
    html += '</div>';

    html += "</div>";
    return html;
  }

  function quickStatCard(label, value, icon, colorClass) {
    return (
      '<div class="quick-stat">' +
      '<div class="qs-icon ' +
      colorClass +
      '">' +
      icon +
      "</div>" +
      '<div class="qs-info">' +
      '<div class="qs-label">' +
      escHtml(label) +
      "</div>" +
      '<div class="qs-value">' +
      (value !== undefined ? escHtml(value) : "0") +
      "</div>" +
      "</div></div>"
    );
  }

  function sectionCard(title, rows) {
    var html = '<div class="section-card"><h3>' + escHtml(title) + "</h3>";
    rows.forEach(function (r) {
      html +=
        '<div class="stat-row"><span class="stat-key">' +
        escHtml(r[0]) +
        '</span><span class="stat-val">' +
        (r[1] !== undefined ? escHtml(r[1]) : "0") +
        "</span></div>";
    });
    html += "</div>";
    return html;
  }

  // ============ Page: Students ============
  var _studentsSearch = "";
  var _studentsPage = 1;

  function renderStudents() {
    var html = '<div class="page-header"><h2>Students</h2>';
    html += '<div class="page-actions">';
    html +=
      '<div class="search-bar"><span class="search-icon">\u2315</span><input type="text" id="student-search" placeholder="Search students..." value="' +
      escHtml(_studentsSearch) +
      '"></div>';
    html += '<button class="btn btn-primary" id="add-student-btn">+ Add Student</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="students-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-student-btn").addEventListener("click", function () {
      showStudentForm();
    });

    var searchInput = document.getElementById("student-search");
    var searchTimeout;
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      var val = this.value;
      searchTimeout = setTimeout(function () {
        _studentsSearch = val;
        _studentsPage = 1;
        loadStudents();
      }, 400);
    });

    loadStudents();
  }

  function loadStudents() {
    var container = document.getElementById("students-table");
    if (!container) return;
    container.innerHTML = showLoading();

    var url = "/students?page=" + _studentsPage + "&per_page=15";
    if (_studentsSearch) url += "&search=" + encodeURIComponent(_studentsSearch);

    apiGet(url).then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.students || [];
        var pagination = data.pagination;

        var columns = [
          { key: "student_id", label: "ID" },
          { key: "first_name", label: "First Name" },
          { key: "last_name", label: "Last Name" },
          { key: "email", label: "Email" },
          { key: "course", label: "Course" },
          {
            key: "status",
            label: "Status",
            render: function (v) {
              var type = v === "active" ? "success" : v === "graduated" ? "info" : "secondary";
              return badgeHtml(v || "N/A", type);
            },
          },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
          { name: "delete", label: "Delete", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showStudentForm(item);
          else if (action === "delete") confirmDeleteStudent(item);
        });

        attachPagination(container, function (page) {
          _studentsPage = page;
          loadStudents();
        });
      });
    });
  }

  function showStudentForm(student) {
    var isEdit = !!student;
    var html = '<div class="form-row">';
    html += buildFormField("first_name", "First Name", "text", isEdit ? student.first_name : "");
    html += buildFormField("last_name", "Last Name", "text", isEdit ? student.last_name : "");
    html += "</div>";
    html += buildFormField("email", "Email", "email", isEdit ? student.email : "");
    html += '<div class="form-row">';
    html += buildFormField("date_of_birth", "Date of Birth", "date", isEdit ? student.date_of_birth : "");
    html += buildFormField("course", "Course", "text", isEdit ? student.course : "");
    html += "</div>";
    if (!isEdit) {
      html += buildFormField("student_id", "Student ID", "text", "");
    }
    html += buildFormField("status", "Status", "select", isEdit ? student.status : "active", [
      "active", "inactive", "graduated", "suspended",
    ]);

    showModal(
      isEdit ? "Edit Student" : "Add Student",
      html,
      function () {
        var formData = getFormData(dom.modalBody);
        if (!formData.first_name || !formData.last_name || !formData.email) {
          showToast("Please fill in all required fields.", "error");
          return;
        }
        dom.modalSaveBtn.disabled = true;

        var promise;
        if (isEdit) {
          promise = apiPut("/students/" + student.student_id, formData);
        } else {
          promise = apiPost("/students", formData);
        }

        promise.then(function (resp) {
          dom.modalSaveBtn.disabled = false;
          if (!resp) return;
          if (resp.ok) {
            closeModal();
            showToast(isEdit ? "Student updated." : "Student created.", "success");
            loadStudents();
          } else {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to save.", "error");
            });
          }
        });
      },
      isEdit ? "Update" : "Create"
    );
  }

  function confirmDeleteStudent(student) {
    showConfirm(
      "Delete Student",
      "Are you sure you want to delete " + student.first_name + " " + student.last_name + "?",
      function () {
        apiDelete("/students/" + student.student_id).then(function (resp) {
          if (resp && resp.ok) {
            showToast("Student deleted.", "success");
            loadStudents();
          } else if (resp) {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to delete.", "error");
            });
          }
        });
      }
    );
  }

  // ============ Page: Courses ============
  var _coursesSearch = "";
  var _coursesPage = 1;

  function renderCourses() {
    var html = '<div class="page-header"><h2>Courses</h2>';
    html += '<div class="page-actions">';
    html +=
      '<div class="search-bar"><span class="search-icon">\u2315</span><input type="text" id="course-search" placeholder="Search courses..." value="' +
      escHtml(_coursesSearch) +
      '"></div>';
    html += '<button class="btn btn-primary" id="add-course-btn">+ Add Course</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="courses-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-course-btn").addEventListener("click", function () {
      showCourseForm();
    });

    var searchInput = document.getElementById("course-search");
    var searchTimeout;
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      var val = this.value;
      searchTimeout = setTimeout(function () {
        _coursesSearch = val;
        _coursesPage = 1;
        loadCourses();
      }, 400);
    });

    loadCourses();
  }

  function loadCourses() {
    var container = document.getElementById("courses-table");
    if (!container) return;
    container.innerHTML = showLoading();

    var url = "/courses?page=" + _coursesPage + "&per_page=15";
    if (_coursesSearch) url += "&search=" + encodeURIComponent(_coursesSearch);

    apiGet(url).then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.courses || [];
        var pagination = data.pagination;

        var columns = [
          { key: "course_id", label: "Course ID" },
          { key: "course_name", label: "Course Name" },
          { key: "department", label: "Department" },
          { key: "credits", label: "Credits" },
          { key: "max_capacity", label: "Capacity" },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
          { name: "delete", label: "Delete", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showCourseForm(item);
          else if (action === "delete") confirmDeleteCourse(item);
        });

        attachPagination(container, function (page) {
          _coursesPage = page;
          loadCourses();
        });
      });
    });
  }

  function showCourseForm(course) {
    var isEdit = !!course;
    html = buildFormField("course_id", "Course ID", "text", isEdit ? course.course_id : "");
    html += buildFormField("course_name", "Course Name", "text", isEdit ? course.course_name : "");
    html += '<div class="form-row">';
    html += buildFormField("department", "Department", "text", isEdit ? course.department : "");
    html += buildFormField("credits", "Credits", "number", isEdit ? course.credits : "");
    html += "</div>";
    html += buildFormField("max_capacity", "Max Capacity", "number", isEdit ? course.max_capacity : "");
    html += buildFormField("description", "Description", "textarea", isEdit ? course.description : "");

    showModal(
      isEdit ? "Edit Course" : "Add Course",
      html,
      function () {
        var formData = getFormData(dom.modalBody);
        if (!formData.course_name) {
          showToast("Course name is required.", "error");
          return;
        }
        if (formData.credits) formData.credits = parseInt(formData.credits) || 0;
        if (formData.max_capacity) formData.max_capacity = parseInt(formData.max_capacity) || 0;
        dom.modalSaveBtn.disabled = true;

        var promise = isEdit
          ? apiPut("/courses/" + course.course_id, formData)
          : apiPost("/courses", formData);

        promise.then(function (resp) {
          dom.modalSaveBtn.disabled = false;
          if (!resp) return;
          if (resp.ok) {
            closeModal();
            showToast(isEdit ? "Course updated." : "Course created.", "success");
            loadCourses();
          } else {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to save.", "error");
            });
          }
        });
      },
      isEdit ? "Update" : "Create"
    );
  }

  function confirmDeleteCourse(course) {
    showConfirm(
      "Delete Course",
      "Are you sure you want to delete " + (course.course_name || course.course_id) + "?",
      function () {
        apiDelete("/courses/" + course.course_id).then(function (resp) {
          if (resp && resp.ok) {
            showToast("Course deleted.", "success");
            loadCourses();
          } else if (resp) {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to delete.", "error");
            });
          }
        });
      }
    );
  }

  // ============ Page: Modules ============
  var _modulesSearch = "";
  var _modulesPage = 1;

  function renderModules() {
    var html = '<div class="page-header"><h2>Modules</h2>';
    html += '<div class="page-actions">';
    html +=
      '<div class="search-bar"><span class="search-icon">\u2315</span><input type="text" id="module-search" placeholder="Search modules..." value="' +
      escHtml(_modulesSearch) +
      '"></div>';
    html += '<button class="btn btn-primary" id="add-module-btn">+ Add Module</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="modules-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-module-btn").addEventListener("click", function () {
      showModuleForm();
    });

    var searchInput = document.getElementById("module-search");
    var searchTimeout;
    searchInput.addEventListener("input", function () {
      clearTimeout(searchTimeout);
      var val = this.value;
      searchTimeout = setTimeout(function () {
        _modulesSearch = val;
        _modulesPage = 1;
        loadModules();
      }, 400);
    });

    loadModules();
  }

  function loadModules() {
    var container = document.getElementById("modules-table");
    if (!container) return;
    container.innerHTML = showLoading();

    var url = "/modules?page=" + _modulesPage + "&per_page=15";
    if (_modulesSearch) url += "&search=" + encodeURIComponent(_modulesSearch);

    apiGet(url).then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.modules || [];
        var pagination = data.pagination;

        var columns = [
          { key: "module_code", label: "Code" },
          { key: "module_name", label: "Module Name" },
          { key: "credits", label: "Credits" },
          { key: "department", label: "Department" },
          { key: "semester", label: "Semester" },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
          { name: "delete", label: "Delete", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showModuleForm(item);
          else if (action === "delete") confirmDeleteModule(item);
        });

        attachPagination(container, function (page) {
          _modulesPage = page;
          loadModules();
        });
      });
    });
  }

  function showModuleForm(mod) {
    var isEdit = !!mod;
    var html = buildFormField("module_code", "Module Code", "text", isEdit ? mod.module_code : "");
    html += buildFormField("module_name", "Module Name", "text", isEdit ? mod.module_name : "");
    html += '<div class="form-row">';
    html += buildFormField("credits", "Credits", "number", isEdit ? mod.credits : "");
    html += buildFormField("department", "Department", "text", isEdit ? mod.department : "");
    html += "</div>";
    html += buildFormField("semester", "Semester", "text", isEdit ? mod.semester : "");

    showModal(
      isEdit ? "Edit Module" : "Add Module",
      html,
      function () {
        var formData = getFormData(dom.modalBody);
        if (!formData.module_code || !formData.module_name) {
          showToast("Module code and name are required.", "error");
          return;
        }
        if (formData.credits) formData.credits = parseInt(formData.credits) || 0;
        dom.modalSaveBtn.disabled = true;

        var promise = isEdit
          ? apiPut("/modules/" + mod.module_code, formData)
          : apiPost("/modules", formData);

        promise.then(function (resp) {
          dom.modalSaveBtn.disabled = false;
          if (!resp) return;
          if (resp.ok) {
            closeModal();
            showToast(isEdit ? "Module updated." : "Module created.", "success");
            loadModules();
          } else {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to save.", "error");
            });
          }
        });
      },
      isEdit ? "Update" : "Create"
    );
  }

  function confirmDeleteModule(mod) {
    showConfirm(
      "Delete Module",
      "Are you sure you want to delete " + (mod.module_name || mod.module_code) + "?",
      function () {
        apiDelete("/modules/" + mod.module_code).then(function (resp) {
          if (resp && resp.ok) {
            showToast("Module deleted.", "success");
            loadModules();
          } else if (resp) {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to delete.", "error");
            });
          }
        });
      }
    );
  }

  // ============ Page: Enrollments ============
  var _enrollPage = 1;

  function renderEnrollments() {
    var html = '<div class="page-header"><h2>Enrollments</h2>';
    html += '<div class="page-actions">';
    html += '<button class="btn btn-primary" id="add-enrollment-btn">+ Enroll Student</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="enrollments-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-enrollment-btn").addEventListener("click", function () {
      showEnrollmentForm();
    });

    loadEnrollments();
  }

  function loadEnrollments() {
    var container = document.getElementById("enrollments-table");
    if (!container) return;
    container.innerHTML = showLoading();

    apiGet("/enrollments?page=" + _enrollPage + "&per_page=15").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.enrollments || [];
        var pagination = data.pagination;

        var columns = [
          { key: "enrollment_id", label: "ID" },
          { key: "student_id", label: "Student ID" },
          { key: "student_name", label: "Student" },
          { key: "module_code", label: "Module" },
          { key: "module_name", label: "Module Name" },
          { key: "enrollment_date", label: "Date" },
          {
            key: "status",
            label: "Status",
            render: function (v) {
              var type = v === "active" ? "success" : v === "dropped" ? "danger" : "secondary";
              return badgeHtml(v || "N/A", type);
            },
          },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "delete", label: "Drop", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "delete") confirmDropEnrollment(item);
        });

        attachPagination(container, function (page) {
          _enrollPage = page;
          loadEnrollments();
        });
      });
    });
  }

  function showEnrollmentForm() {
    var html = buildFormField("student_id", "Student ID", "text", "");
    html += buildFormField("module_code", "Module Code", "text", "");

    showModal("Enroll Student", html, function () {
      var formData = getFormData(dom.modalBody);
      if (!formData.student_id || !formData.module_code) {
        showToast("Student ID and Module Code are required.", "error");
        return;
      }
      dom.modalSaveBtn.disabled = true;

      apiPost("/enrollments", formData).then(function (resp) {
        dom.modalSaveBtn.disabled = false;
        if (!resp) return;
        if (resp.ok) {
          closeModal();
          showToast("Student enrolled successfully.", "success");
          loadEnrollments();
        } else {
          resp.json().then(function (err) {
            showToast(err.error || "Enrollment failed.", "error");
          });
        }
      });
    }, "Enroll");
  }

  function confirmDropEnrollment(enrollment) {
    var id = enrollment.enrollment_id || enrollment.id;
    showConfirm(
      "Drop Enrollment",
      "Are you sure you want to drop this enrollment?",
      function () {
        apiDelete("/enrollments/" + id).then(function (resp) {
          if (resp && resp.ok) {
            showToast("Enrollment dropped.", "success");
            loadEnrollments();
          } else if (resp) {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to drop.", "error");
            });
          }
        });
      }
    );
  }

  // ============ Page: Grades ============
  var _gradesPage = 1;

  function renderGrades() {
    var html = '<div class="page-header"><h2>Grades</h2>';
    html += '<div class="page-actions">';
    html += '<button class="btn btn-primary" id="add-grade-btn">+ Record Grade</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="grades-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-grade-btn").addEventListener("click", function () {
      showGradeForm();
    });

    loadGrades();
  }

  function loadGrades() {
    var container = document.getElementById("grades-table");
    if (!container) return;
    container.innerHTML = showLoading();

    apiGet("/grades?page=" + _gradesPage + "&per_page=15").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.grades || [];
        var pagination = data.pagination;

        var columns = [
          { key: "grade_id", label: "ID" },
          { key: "student_id", label: "Student ID" },
          { key: "student_name", label: "Student" },
          { key: "assessment_id", label: "Assessment" },
          { key: "score", label: "Score" },
          {
            key: "grade",
            label: "Grade",
            render: function (v) {
              if (!v) return "-";
              var type = "secondary";
              if (v === "A" || v === "A+") type = "success";
              else if (v === "B" || v === "B+") type = "info";
              else if (v === "C" || v === "C+") type = "warning";
              else if (v === "D" || v === "F") type = "danger";
              return badgeHtml(v, type);
            },
          },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
          { name: "delete", label: "Delete", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showGradeForm(item);
          else if (action === "delete") confirmDeleteGrade(item);
        });

        attachPagination(container, function (page) {
          _gradesPage = page;
          loadGrades();
        });
      });
    });
  }

  function showGradeForm(grade) {
    var isEdit = !!grade;
    var html = '<div class="form-row">';
    html += buildFormField("student_id", "Student ID", "text", isEdit ? grade.student_id : "");
    html += buildFormField("assessment_id", "Assessment ID", "text", isEdit ? grade.assessment_id : "");
    html += "</div>";
    html += '<div class="form-row">';
    html += buildFormField("score", "Score", "number", isEdit ? grade.score : "");
    html += buildFormField("grade", "Grade Letter", "select", isEdit ? grade.grade : "", [
      "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F",
    ]);
    html += "</div>";
    html += buildFormField("feedback", "Feedback", "textarea", isEdit ? grade.feedback : "");

    showModal(
      isEdit ? "Edit Grade" : "Record Grade",
      html,
      function () {
        var formData = getFormData(dom.modalBody);
        if (!formData.student_id || !formData.assessment_id) {
          showToast("Student ID and Assessment ID are required.", "error");
          return;
        }
        if (formData.score) formData.score = parseFloat(formData.score) || 0;
        dom.modalSaveBtn.disabled = true;

        var promise = isEdit
          ? apiPut("/grades/" + grade.grade_id, formData)
          : apiPost("/grades", formData);

        promise.then(function (resp) {
          dom.modalSaveBtn.disabled = false;
          if (!resp) return;
          if (resp.ok) {
            closeModal();
            showToast(isEdit ? "Grade updated." : "Grade recorded.", "success");
            loadGrades();
          } else {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to save.", "error");
            });
          }
        });
      },
      isEdit ? "Update" : "Record"
    );
  }

  function confirmDeleteGrade(grade) {
    showConfirm(
      "Delete Grade",
      "Are you sure you want to delete this grade record?",
      function () {
        apiDelete("/grades/" + grade.grade_id).then(function (resp) {
          if (resp && resp.ok) {
            showToast("Grade deleted.", "success");
            loadGrades();
          } else if (resp) {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to delete.", "error");
            });
          }
        });
      }
    );
  }

  // ============ Page: Finance ============
  function renderFinance() {
    var html = '<div class="page-header"><h2>Finance</h2>';
    html += '<div class="page-actions">';
    html += '<button class="btn btn-primary" id="record-payment-btn">+ Record Payment</button>';
    html += "</div></div>";

    html += '<div class="section-grid">';
    html += '<div class="card" id="fees-card"><div class="card-body"><h3>Student Fees</h3>' + showLoading() + "</div></div>";
    html += '<div class="card" id="payments-card"><div class="card-body"><h3>Recent Payments</h3>' + showLoading() + "</div></div>";
    html += "</div>";

    dom.content.innerHTML = html;

    document.getElementById("record-payment-btn").addEventListener("click", function () {
      showPaymentForm();
    });

    loadFinanceData();
  }

  function loadFinanceData() {
    apiGet("/finance/fees?per_page=10").then(function (resp) {
      var feesCard = document.getElementById("fees-card");
      if (!resp || !feesCard) return;
      resp.json().then(function (data) {
        var items = data.items || data.fees || [];
        var html = "<h3>Student Fees</h3>";
        if (items.length === 0) {
          html += '<p style="color:#64748b">No fee records found.</p>';
        } else {
          html += '<div class="table-wrapper"><table><thead><tr><th>Student</th><th>Amount</th><th>Status</th></tr></thead><tbody>';
          items.forEach(function (fee) {
            html += "<tr><td>" + escHtml(fee.student_id || fee.student_name) + "</td>";
            html += "<td>" + escHtml(fee.amount) + "</td>";
            html += "<td>" + badgeHtml(fee.status || "pending", fee.status === "paid" ? "success" : "warning") + "</td></tr>";
          });
          html += "</tbody></table></div>";
        }
        feesCard.querySelector(".card-body").innerHTML = html;
      });
    });

    apiGet("/finance/payments?per_page=10").then(function (resp) {
      var paymentsCard = document.getElementById("payments-card");
      if (!resp || !paymentsCard) return;
      resp.json().then(function (data) {
        var items = data.items || data.payments || [];
        var html = "<h3>Recent Payments</h3>";
        if (items.length === 0) {
          html += '<p style="color:#64748b">No payment records found.</p>';
        } else {
          html += '<div class="table-wrapper"><table><thead><tr><th>Student</th><th>Amount</th><th>Method</th><th>Date</th></tr></thead><tbody>';
          items.forEach(function (payment) {
            html += "<tr><td>" + escHtml(payment.student_id || payment.student_name) + "</td>";
            html += "<td>" + escHtml(payment.amount) + "</td>";
            html += "<td>" + escHtml(payment.payment_method || "-") + "</td>";
            html += "<td>" + escHtml(payment.payment_date || payment.date || "-") + "</td></tr>";
          });
          html += "</tbody></table></div>";
        }
        paymentsCard.querySelector(".card-body").innerHTML = html;
      });
    });
  }

  function showPaymentForm() {
    var html = buildFormField("student_id", "Student ID", "text", "");
    html += buildFormField("amount", "Amount", "number", "");
    html += buildFormField("payment_method", "Payment Method", "select", "cash", [
      { value: "cash", label: "Cash" },
      { value: "card", label: "Card" },
      { value: "bank_transfer", label: "Bank Transfer" },
      { value: "online", label: "Online" },
    ]);
    html += buildFormField("description", "Description", "text", "");

    showModal("Record Payment", html, function () {
      var formData = getFormData(dom.modalBody);
      if (!formData.student_id || !formData.amount) {
        showToast("Student ID and amount are required.", "error");
        return;
      }
      formData.amount = parseFloat(formData.amount) || 0;
      dom.modalSaveBtn.disabled = true;

      apiPost("/finance/payments", formData).then(function (resp) {
        dom.modalSaveBtn.disabled = false;
        if (!resp) return;
        if (resp.ok) {
          closeModal();
          showToast("Payment recorded.", "success");
          loadFinanceData();
        } else {
          resp.json().then(function (err) {
            showToast(err.error || "Failed to record payment.", "error");
          });
        }
      });
    }, "Record");
  }

  // ============ Page: Users ============
  var _usersPage = 1;

  function renderUsers() {
    var html = '<div class="page-header"><h2>Users</h2>';
    html += '<div class="page-actions">';
    html += '<button class="btn btn-primary" id="add-user-btn">+ Add User</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="users-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-user-btn").addEventListener("click", function () {
      showUserForm();
    });

    loadUsers();
  }

  function loadUsers() {
    var container = document.getElementById("users-table");
    if (!container) return;
    container.innerHTML = showLoading();

    apiGet("/users?page=" + _usersPage + "&per_page=15").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.users || [];
        var pagination = data.pagination;

        var columns = [
          { key: "id", label: "ID" },
          { key: "username", label: "Username" },
          { key: "email", label: "Email" },
          {
            key: "role",
            label: "Role",
            render: function (v) {
              var type = v === "admin" ? "danger" : v === "instructor" ? "warning" : "info";
              return badgeHtml(v || "user", type);
            },
          },
          {
            key: "is_active",
            label: "Active",
            render: function (v) {
              return badgeHtml(v ? "Yes" : "No", v ? "success" : "secondary");
            },
          },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showUserForm(item);
        });

        attachPagination(container, function (page) {
          _usersPage = page;
          loadUsers();
        });
      });
    });
  }

  function showUserForm(user) {
    var isEdit = !!user;
    var html = buildFormField("username", "Username", "text", isEdit ? user.username : "");
    html += buildFormField("email", "Email", "email", isEdit ? user.email : "");
    if (!isEdit) {
      html += buildFormField("password", "Password", "password", "");
    }
    html += buildFormField("role", "Role", "select", isEdit ? user.role : "student", [
      "student", "instructor", "admin", "staff",
    ]);

    showModal(
      isEdit ? "Edit User" : "Add User",
      html,
      function () {
        var formData = getFormData(dom.modalBody);
        if (!formData.username) {
          showToast("Username is required.", "error");
          return;
        }
        dom.modalSaveBtn.disabled = true;

        var promise = isEdit
          ? apiPut("/users/" + (user.id || user.user_id), formData)
          : apiPost("/users", formData);

        promise.then(function (resp) {
          dom.modalSaveBtn.disabled = false;
          if (!resp) return;
          if (resp.ok) {
            closeModal();
            showToast(isEdit ? "User updated." : "User created.", "success");
            loadUsers();
          } else {
            resp.json().then(function (err) {
              showToast(err.error || "Failed to save.", "error");
            });
          }
        });
      },
      isEdit ? "Update" : "Create"
    );
  }

  // ============ Page: Assignments ============
  var _assignPage = 1;

  function renderAssignments() {
    var html = '<div class="page-header"><h2>Assignments</h2>';
    html += '<div class="page-actions">';
    html += '<button class="btn btn-primary" id="add-assignment-btn">+ Create Assignment</button>';
    html += "</div></div>";
    html += '<div class="table-container" id="assignments-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    document.getElementById("add-assignment-btn").addEventListener("click", function () {
      showAssignmentForm();
    });

    loadAssignments();
  }

  function loadAssignments() {
    var container = document.getElementById("assignments-table");
    if (!container) return;
    container.innerHTML = showLoading();

    apiGet("/assignments?page=" + _assignPage + "&per_page=15").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var items = data.items || data.assignments || [];
        var pagination = data.pagination;

        var columns = [
          { key: "assignment_id", label: "ID" },
          { key: "title", label: "Title" },
          { key: "module_code", label: "Module" },
          { key: "due_date", label: "Due Date" },
          { key: "max_score", label: "Max Score" },
          {
            key: "status",
            label: "Status",
            render: function (v) {
              var t = v === "active" ? "success" : v === "closed" ? "secondary" : "info";
              return badgeHtml(v || "N/A", t);
            },
          },
        ];

        var tableHtml = buildTable(columns, items, [
          { name: "edit", label: "Edit", cls: "btn-primary" },
          { name: "delete", label: "Delete", cls: "btn-danger" },
        ]);

        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;

        attachTableActions(container, items, function (action, item) {
          if (action === "edit") showAssignmentForm(item);
          else if (action === "delete") {
            showConfirm("Delete Assignment", "Delete " + (item.title || "this assignment") + "?", function () {
              apiDelete("/assignments/" + item.assignment_id).then(function (resp) {
                if (resp && resp.ok) { showToast("Deleted.", "success"); loadAssignments(); }
                else if (resp) resp.json().then(function (e) { showToast(e.error || "Failed.", "error"); });
              });
            });
          }
        });

        attachPagination(container, function (page) {
          _assignPage = page;
          loadAssignments();
        });
      });
    });
  }

  function showAssignmentForm(a) {
    var isEdit = !!a;
    var html = buildFormField("title", "Title", "text", isEdit ? a.title : "");
    html += '<div class="form-row">';
    html += buildFormField("module_code", "Module Code", "text", isEdit ? a.module_code : "");
    html += buildFormField("due_date", "Due Date", "date", isEdit ? a.due_date : "");
    html += "</div>";
    html += buildFormField("max_score", "Max Score", "number", isEdit ? a.max_score : "100");
    html += buildFormField("description", "Description", "textarea", isEdit ? a.description : "");

    showModal(isEdit ? "Edit Assignment" : "Create Assignment", html, function () {
      var formData = getFormData(dom.modalBody);
      if (!formData.title) { showToast("Title is required.", "error"); return; }
      if (formData.max_score) formData.max_score = parseInt(formData.max_score) || 100;
      dom.modalSaveBtn.disabled = true;

      var promise = isEdit
        ? apiPut("/assignments/" + a.assignment_id, formData)
        : apiPost("/assignments", formData);

      promise.then(function (resp) {
        dom.modalSaveBtn.disabled = false;
        if (!resp) return;
        if (resp.ok) {
          closeModal();
          showToast(isEdit ? "Assignment updated." : "Assignment created.", "success");
          loadAssignments();
        } else {
          resp.json().then(function (err) { showToast(err.error || "Failed.", "error"); });
        }
      });
    }, isEdit ? "Update" : "Create");
  }

  // ============ Page: Attendance ============
  function renderAttendance() {
    var html = '<div class="page-header"><h2>Attendance</h2></div>';
    html += '<div class="table-container" id="attendance-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    apiGet("/attendance?per_page=20").then(function (resp) {
      var container = document.getElementById("attendance-table");
      if (!resp || !container) return;
      resp.json().then(function (data) {
        var items = data.items || data.sessions || data.attendance || [];

        var columns = [
          { key: "session_id", label: "Session" },
          { key: "module_code", label: "Module" },
          { key: "date", label: "Date" },
          { key: "type", label: "Type" },
          { key: "total_present", label: "Present" },
          { key: "total_absent", label: "Absent" },
        ];

        container.innerHTML = buildTable(columns, items);
      });
    });
  }

  // ============ Page: Exams ============
  function renderExams() {
    var html = '<div class="page-header"><h2>Exams</h2></div>';
    html += '<div class="table-container" id="exams-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    apiGet("/exams?per_page=20").then(function (resp) {
      var container = document.getElementById("exams-table");
      if (!resp || !container) return;
      resp.json().then(function (data) {
        var items = data.items || data.exams || [];

        var columns = [
          { key: "exam_id", label: "ID" },
          { key: "module_code", label: "Module" },
          { key: "exam_type", label: "Type" },
          { key: "date", label: "Date" },
          { key: "start_time", label: "Start" },
          { key: "end_time", label: "End" },
          { key: "location", label: "Location" },
        ];

        container.innerHTML = buildTable(columns, items);
      });
    });
  }

  // ============ Generic List Page ============
  function renderGenericList(page) {
    var endpoint = "/" + page.replace(/_/g, "-");
    var title = page.charAt(0).toUpperCase() + page.slice(1).replace(/[-_]/g, " ");

    var html = '<div class="page-header"><h2>' + escHtml(title) + "</h2></div>";
    html += '<div class="table-container" id="generic-table">' + showLoading() + "</div>";
    dom.content.innerHTML = html;

    apiGet(endpoint + "?per_page=20").then(function (resp) {
      var container = document.getElementById("generic-table");
      if (!container) return;
      if (!resp) {
        container.innerHTML = '<div class="table-empty"><p>Failed to load data.</p></div>';
        return;
      }
      resp.json().then(function (data) {
        // Try to find the items array
        var items = null;
        if (data.items) items = data.items;
        else {
          for (var key in data) {
            if (Array.isArray(data[key])) { items = data[key]; break; }
          }
        }

        if (!items || items.length === 0) {
          container.innerHTML = '<div class="table-empty"><p>No records found for this section.</p></div>';
          return;
        }

        // Auto-detect columns from first item
        var columns = [];
        var firstItem = items[0];
        var keys = Object.keys(firstItem);
        // Show up to 7 columns
        keys.slice(0, 7).forEach(function (key) {
          columns.push({
            key: key,
            label: key.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); }),
          });
        });

        var tableHtml = buildTable(columns, items);
        var pagination = data.pagination;
        if (pagination) tableHtml += buildPagination(pagination);
        container.innerHTML = tableHtml;
      }).catch(function () {
        container.innerHTML = '<div class="table-empty"><p>Error parsing response.</p></div>';
      });
    });
  }

  // ============ Shared Helpers ============
  function attachTableActions(container, items, handler) {
    var buttons = container.querySelectorAll("[data-action]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        var action = this.getAttribute("data-action");
        var index = parseInt(this.getAttribute("data-index"));
        handler(action, items[index]);
      });
    }
  }

  function attachPagination(container, handler) {
    var buttons = container.querySelectorAll("[data-pg-page]");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        var page = parseInt(this.getAttribute("data-pg-page"));
        if (!isNaN(page) && page > 0) handler(page);
      });
    }
  }

  // ============ Page: Settings ============
  var _settingsTab = "profile";

  function renderSettings() {
    var html = '<div class="page-header"><h2>Account Settings</h2></div>';

    html += '<div class="settings-tabs">';
    html += '<button class="settings-tab' + (_settingsTab === "profile" ? " active" : "") + '" data-tab="profile">Profile</button>';
    html += '<button class="settings-tab' + (_settingsTab === "security" ? " active" : "") + '" data-tab="security">Security</button>';
    html += '<button class="settings-tab' + (_settingsTab === "preferences" ? " active" : "") + '" data-tab="preferences">Preferences</button>';
    html += '</div>';

    html += '<div id="settings-content">' + showLoading() + '</div>';
    dom.content.innerHTML = html;

    // Tab clicks
    var tabs = dom.content.querySelectorAll(".settings-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function () {
        _settingsTab = this.getAttribute("data-tab");
        renderSettings();
      });
    }

    loadSettingsTab(_settingsTab);
  }

  function loadSettingsTab(tab) {
    var container = document.getElementById("settings-content");
    if (!container) return;

    if (tab === "profile") {
      loadProfileTab(container);
    } else if (tab === "security") {
      loadSecurityTab(container);
    } else if (tab === "preferences") {
      loadPreferencesTab(container);
    }
  }

  function loadProfileTab(container) {
    container.innerHTML = showLoading();
    apiGet("/account/profile").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var p = data.profile || {};
        var html = '<div class="settings-section"><h3>Profile Information</h3>';
        html += '<div class="form-row">';
        html += buildFormField("first_name", "First Name", "text", p.first_name || "");
        html += buildFormField("last_name", "Last Name", "text", p.last_name || "");
        html += '</div>';
        html += buildFormField("email", "Email", "email", p.email || "");
        html += buildFormField("phone", "Phone", "tel", p.phone || "");

        html += '<div style="margin-top:16px">';
        html += '<button class="btn btn-primary" id="save-profile-btn">Save Changes</button>';
        html += '</div></div>';

        html += '<div class="settings-section"><h3>Account Info</h3>';
        html += '<div class="settings-row"><div><div class="sr-label">Username</div></div><div class="sr-value">' + escHtml(p.username) + '</div></div>';
        html += '<div class="settings-row"><div><div class="sr-label">Role</div></div><div class="sr-value">' + badgeHtml(p.role || "user", p.role === "admin" ? "danger" : "info") + '</div></div>';
        html += '<div class="settings-row"><div><div class="sr-label">Account Created</div></div><div class="sr-value">' + escHtml(p.created_at || "-") + '</div></div>';
        html += '<div class="settings-row"><div><div class="sr-label">Last Login</div></div><div class="sr-value">' + escHtml(p.last_login || "-") + '</div></div>';
        html += '</div>';

        container.innerHTML = html;

        document.getElementById("save-profile-btn").addEventListener("click", function () {
          var formData = getFormData(container.querySelector(".settings-section"));
          this.disabled = true;
          this.textContent = "Saving...";
          var btn = this;
          apiPut("/account/profile", formData).then(function (resp) {
            btn.disabled = false;
            btn.textContent = "Save Changes";
            if (resp && resp.ok) {
              showToast("Profile updated.", "success");
            } else if (resp) {
              resp.json().then(function (e) { showToast(e.error || "Failed to update.", "error"); });
            }
          });
        });
      });
    });
  }

  function loadSecurityTab(container) {
    var html = '<div class="settings-section"><h3>Change Password</h3>';
    html += buildFormField("current_password", "Current Password", "password", "");
    html += buildFormField("new_password", "New Password", "password", "");
    html += buildFormField("confirm_password", "Confirm New Password", "password", "");
    html += '<div style="margin-top:16px"><button class="btn btn-primary" id="change-pw-btn">Change Password</button></div>';
    html += '</div>';

    html += '<div class="settings-section"><h3>Multi-Factor Authentication</h3>';
    html += '<div id="mfa-status-area">' + showLoading() + '</div>';
    html += '</div>';

    html += '<div class="settings-section"><h3>Recent Sessions</h3>';
    html += '<div id="sessions-area">' + showLoading() + '</div>';
    html += '</div>';

    container.innerHTML = html;

    document.getElementById("change-pw-btn").addEventListener("click", function () {
      var section = this.closest(".settings-section");
      var fd = getFormData(section);
      if (!fd.current_password || !fd.new_password) {
        showToast("Please fill in all password fields.", "error");
        return;
      }
      if (fd.new_password !== fd.confirm_password) {
        showToast("New passwords do not match.", "error");
        return;
      }
      this.disabled = true;
      this.textContent = "Changing...";
      var btn = this;
      apiPut("/account/password", {
        current_password: fd.current_password,
        new_password: fd.new_password,
      }).then(function (resp) {
        btn.disabled = false;
        btn.textContent = "Change Password";
        if (resp && resp.ok) {
          showToast("Password changed successfully.", "success");
          section.querySelectorAll("input").forEach(function (el) { el.value = ""; });
        } else if (resp) {
          resp.json().then(function (e) { showToast(e.error || "Failed.", "error"); });
        }
      });
    });

    // Load MFA status
    apiGet("/mfa/status").then(function (resp) {
      var area = document.getElementById("mfa-status-area");
      if (!resp || !area) return;
      resp.json().then(function (data) {
        var enabled = data.enabled;
        var methods = data.methods || [];

        var mHtml = '<div class="settings-row"><div><div class="sr-label">MFA Status</div><div class="sr-desc">Protect your account with multi-factor authentication</div></div>';
        mHtml += '<div>' + badgeHtml(enabled ? "Enabled" : "Disabled", enabled ? "success" : "secondary") + '</div></div>';

        if (methods.length > 0) {
          mHtml += '<div style="margin-top:12px"><strong style="font-size:0.85rem">Configured Methods:</strong></div>';
          methods.forEach(function (m) {
            mHtml += '<div class="settings-row"><div class="sr-label">' + escHtml(m.type || m.method_type || "Unknown") + '</div>';
            mHtml += '<div class="sr-value">' + escHtml(m.identifier || "") + '</div></div>';
          });
        }

        if (enabled) {
          mHtml += '<div style="margin-top:12px"><button class="btn btn-sm btn-danger" id="disable-mfa-btn">Disable MFA</button></div>';
        } else {
          mHtml += '<div style="margin-top:12px"><button class="btn btn-sm btn-primary" id="enable-mfa-btn">Enable MFA</button></div>';
        }

        area.innerHTML = mHtml;

        var disableBtn = document.getElementById("disable-mfa-btn");
        if (disableBtn) {
          disableBtn.addEventListener("click", function () {
            apiPost("/mfa/disable", {}).then(function (resp) {
              if (resp && resp.ok) { showToast("MFA disabled.", "success"); loadSecurityTab(container); }
              else if (resp) resp.json().then(function (e) { showToast(e.error || "Failed.", "error"); });
            });
          });
        }

        var enableBtn = document.getElementById("enable-mfa-btn");
        if (enableBtn) {
          enableBtn.addEventListener("click", function () {
            apiPost("/mfa/enable", {}).then(function (resp) {
              if (resp && resp.ok) { showToast("MFA enabled.", "success"); loadSecurityTab(container); }
              else if (resp) resp.json().then(function (e) { showToast(e.error || "Failed.", "error"); });
            });
          });
        }
      });
    });

    // Load sessions
    apiGet("/account/sessions").then(function (resp) {
      var area = document.getElementById("sessions-area");
      if (!resp || !area) return;
      resp.json().then(function (data) {
        var sessions = data.sessions || [];
        if (sessions.length === 0) {
          area.innerHTML = '<p style="color:var(--color-text-muted)">No recent sessions found.</p>';
          return;
        }
        var cols = [
          { key: "login_time", label: "Time" },
          { key: "ip_address", label: "IP Address" },
          { key: "success", label: "Status", render: function (v) { return badgeHtml(v ? "Success" : "Failed", v ? "success" : "danger"); } },
        ];
        area.innerHTML = buildTable(cols, sessions);
      });
    });
  }

  function loadPreferencesTab(container) {
    container.innerHTML = showLoading();
    apiGet("/account/preferences").then(function (resp) {
      if (!resp) return;
      resp.json().then(function (data) {
        var p = data.preferences || {};
        var html = '<div class="settings-section"><h3>Display</h3>';

        html += '<div class="settings-row"><div><div class="sr-label">Theme</div><div class="sr-desc">Choose your preferred color scheme</div></div>';
        html += '<select class="form-control" name="theme" style="width:150px">';
        html += '<option value="light"' + (p.theme === "light" ? " selected" : "") + '>Light</option>';
        html += '<option value="dark"' + (p.theme === "dark" ? " selected" : "") + '>Dark</option>';
        html += '</select></div>';

        html += '<div class="settings-row"><div><div class="sr-label">Language</div></div>';
        html += '<select class="form-control" name="language" style="width:150px">';
        html += '<option value="en"' + (p.language === "en" ? " selected" : "") + '>English</option>';
        html += '<option value="es"' + (p.language === "es" ? " selected" : "") + '>Spanish</option>';
        html += '<option value="fr"' + (p.language === "fr" ? " selected" : "") + '>French</option>';
        html += '</select></div>';

        html += '<div class="settings-row"><div><div class="sr-label">Timezone</div></div>';
        html += '<select class="form-control" name="timezone" style="width:200px">';
        var tzOpts = ["UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "Europe/London", "Europe/Paris", "Asia/Tokyo"];
        tzOpts.forEach(function (tz) {
          html += '<option value="' + tz + '"' + (p.timezone === tz ? " selected" : "") + '>' + tz + '</option>';
        });
        html += '</select></div>';
        html += '</div>';

        html += '<div class="settings-section"><h3>Notifications</h3>';

        html += '<div class="settings-row"><div><div class="sr-label">Email Notifications</div><div class="sr-desc">Receive important updates via email</div></div>';
        html += '<label class="toggle-switch"><input type="checkbox" name="email_notifications"' + (p.email_notifications === "true" || p.email_notifications === true ? " checked" : "") + '><span class="toggle-slider"></span></label></div>';

        html += '<div class="settings-row"><div><div class="sr-label">SMS Notifications</div><div class="sr-desc">Get text alerts for urgent matters</div></div>';
        html += '<label class="toggle-switch"><input type="checkbox" name="sms_notifications"' + (p.sms_notifications === "true" || p.sms_notifications === true ? " checked" : "") + '><span class="toggle-slider"></span></label></div>';

        html += '</div>';

        html += '<div style="margin-top:16px"><button class="btn btn-primary" id="save-prefs-btn">Save Preferences</button></div>';

        container.innerHTML = html;

        document.getElementById("save-prefs-btn").addEventListener("click", function () {
          var selects = container.querySelectorAll("select");
          var checks = container.querySelectorAll('input[type="checkbox"]');
          var prefsData = {};
          for (var i = 0; i < selects.length; i++) {
            prefsData[selects[i].name] = selects[i].value;
          }
          for (var j = 0; j < checks.length; j++) {
            prefsData[checks[j].name] = checks[j].checked;
          }
          this.disabled = true;
          this.textContent = "Saving...";
          var btn = this;
          apiPut("/account/preferences", prefsData).then(function (resp) {
            btn.disabled = false;
            btn.textContent = "Save Preferences";
            if (resp && resp.ok) {
              showToast("Preferences saved.", "success");
            } else if (resp) {
              resp.json().then(function (e) { showToast(e.error || "Failed.", "error"); });
            }
          });
        });
      });
    });
  }

  // ============ Page Renderer Map ============
  var pageRenderers = {
    dashboard: renderDashboard,
    students: renderStudents,
    courses: renderCourses,
    modules: renderModules,
    enrollments: renderEnrollments,
    grades: renderGrades,
    finance: renderFinance,
    users: renderUsers,
    assignments: renderAssignments,
    attendance: renderAttendance,
    exams: renderExams,
    settings: renderSettings,
  };

  // ============ Initialization ============
  function init() {
    cacheDom();
    buildSidebar();

    // Login form
    dom.loginForm.addEventListener("submit", handleLogin);

    // Logout
    dom.logoutBtn.addEventListener("click", function (e) {
      e.preventDefault();
      handleLogout();
    });

    // Modal close handlers
    dom.modalCloseBtn.addEventListener("click", closeModal);
    dom.modalCancelBtn.addEventListener("click", closeModal);
    dom.modalOverlay.addEventListener("click", function (e) {
      if (e.target === dom.modalOverlay) closeModal();
    });

    // Sidebar toggle (mobile)
    dom.sidebarToggle.addEventListener("click", function () {
      dom.sidebar.classList.toggle("open");
    });

    // Route handling
    window.addEventListener("hashchange", handleRoute);

    // Check if already logged in
    if (state.token && state.user) {
      showApp();
      handleRoute();
    } else {
      showLogin();
    }
  }

  // Start the application
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
