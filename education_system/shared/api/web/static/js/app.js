/* ── Education System — Single Page Application ───────────────────── */

(function () {
  "use strict";

  const API = "/api/v1";
  const app = document.getElementById("app");

  // ── State ────────────────────────────────────────────────────────
  let state = {
    token: localStorage.getItem("edu_token"),
    refreshToken: localStorage.getItem("edu_refresh_token"),
    user: JSON.parse(localStorage.getItem("edu_user") || "null"),
    activeSystem: localStorage.getItem("edu_active_system") || null,
    mfaToken: null,
    mfaUsername: null,
  };

  function saveAuth(token, refreshToken, user) {
    state.token = token;
    state.refreshToken = refreshToken;
    state.user = user;
    localStorage.setItem("edu_token", token);
    localStorage.setItem("edu_refresh_token", refreshToken);
    localStorage.setItem("edu_user", JSON.stringify(user));
  }

  function clearAuth() {
    state.token = null;
    state.refreshToken = null;
    state.user = null;
    state.activeSystem = null;
    state.mfaToken = null;
    localStorage.removeItem("edu_token");
    localStorage.removeItem("edu_refresh_token");
    localStorage.removeItem("edu_user");
    localStorage.removeItem("edu_active_system");
    stopHeartbeat();
    stopSessionRefresh();
  }

  function setActiveSystem(sk) {
    state.activeSystem = sk;
    localStorage.setItem("edu_active_system", sk);
  }

  // ── API helpers ──────────────────────────────────────────────────
  async function apiFetch(path, opts = {}) {
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    if (state.token && !opts.skipAuth) {
      headers["Authorization"] = "Bearer " + state.token;
    }
    const res = await fetch(API + path, { ...opts, headers });
    if (res.status === 401 && state.refreshToken && !opts._retried) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        return apiFetch(path, { ...opts, _retried: true });
      }
      clearAuth();
      render();
      return null;
    }
    return res;
  }

  async function tryRefresh() {
    try {
      const res = await fetch(API + "/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      state.token = data.token;
      state.refreshToken = data.refresh_token;
      localStorage.setItem("edu_token", data.token);
      localStorage.setItem("edu_refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  // ── SVG Icons ────────────────────────────────────────────────────
  const icons = {
    user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
    lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
    award: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/></svg>',
    settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    clipboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/></svg>',
    shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    menu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>',
    activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
    zap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    archive: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
  };

  const systemMeta = {
    university: { icon: "\u{1F3EB}", label: "University", color: "#2980b9", desc: "Higher education management" },
    college: { icon: "\u{1F4DA}", label: "Sixth Form College", color: "#27ae60", desc: "Post-16 education management" },
    school: { icon: "\u{1F392}", label: "Secondary School", color: "#8e44ad", desc: "Years 7-11 management" },
    primary: { icon: "\u270F\uFE0F", label: "Primary School", color: "#e67e22", desc: "Reception to Year 6" },
  };

  // ── Superadmin detection ───────────────────────────────────────────
  function isSuperadmin() {
    if (!state.user || !state.user.systems) return false;
    const adminKeys = new Set(
      state.user.systems.filter(s => s.role === "admin").map(s => s.system_key)
    );
    return adminKeys.has("university") && adminKeys.has("college") &&
           adminKeys.has("school") && adminKeys.has("primary");
  }

  // ── Routing ──────────────────────────────────────────────────────
  function render() {
    if (!state.token || !state.user) {
      if (state.mfaToken) {
        renderMFA();
      } else {
        renderLogin();
      }
    } else if (!state.activeSystem) {
      // Superadmin gets the cross-system dashboard
      if (isSuperadmin()) {
        setActiveSystem("__superadmin__");
        renderSuperadminApp();
        return;
      }
      // Single-system users skip the picker entirely
      const systems = state.user.systems || [];
      if (systems.length === 1) {
        setActiveSystem(systems[0].system_key);
        renderApp();
        return;
      }
      renderSystemPicker();
    } else if (state.activeSystem === "__superadmin__") {
      renderSuperadminApp();
    } else {
      renderApp();
    }
  }

  // ── Login Page ───────────────────────────────────────────────────
  function renderLogin() {
    app.innerHTML = `
      <div class="login-page">
        <div class="login-container">
          <div class="login-card">
            <div class="login-header">
              <div class="logo">\u{1F393}</div>
              <h1>Education System</h1>
              <p>Sign in to your account</p>
            </div>
            <div id="login-alert"></div>
            <form id="login-form">
              <div class="form-group">
                <label for="username">Username</label>
                <div class="input-icon">
                  ${icons.user}
                  <input id="username" name="username" type="text" placeholder="Enter your username" required autofocus>
                </div>
              </div>
              <div class="form-group">
                <label for="password">Password</label>
                <div class="input-icon">
                  ${icons.lock}
                  <input id="password" name="password" type="password" placeholder="Enter your password" required>
                </div>
              </div>
              <button type="submit" class="btn btn-primary" id="login-btn">
                Sign In
              </button>
            </form>
            <div class="login-footer">
              Education System &copy; ${new Date().getFullYear()}
            </div>
          </div>
        </div>
      </div>`;

    document.getElementById("login-form").addEventListener("submit", handleLogin);
  }

  async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById("login-btn");
    const alertBox = document.getElementById("login-alert");
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    if (!username || !password) {
      alertBox.innerHTML = '<div class="alert alert-error">Please enter both username and password.</div>';
      return;
    }

    btn.disabled = true;
    btn.textContent = "Signing in...";
    alertBox.innerHTML = "";

    try {
      const res = await fetch(API + "/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        alertBox.innerHTML = `<div class="alert alert-error">${esc(data.error || "Login failed")}</div>`;
        btn.disabled = false;
        btn.textContent = "Sign In";
        return;
      }

      if (data.mfa_required) {
        state.mfaToken = data.mfa_token;
        state.mfaUsername = data.username;
        renderMFA();
        return;
      }

      saveAuth(data.token, data.refresh_token, data.user);
      startHeartbeat();
      render();
    } catch (err) {
      alertBox.innerHTML = '<div class="alert alert-error">Connection error. Is the API server running?</div>';
      btn.disabled = false;
      btn.textContent = "Sign In";
    }
  }

  // ── MFA Page ─────────────────────────────────────────────────────
  function renderMFA() {
    app.innerHTML = `
      <div class="login-page">
        <div class="login-container">
          <div class="login-card">
            <div class="login-header">
              <div class="logo">${icons.shield}</div>
              <h1>Two-Factor Authentication</h1>
              <p>Enter the 6-digit code from your authenticator app</p>
            </div>
            <div id="mfa-alert"></div>
            <form id="mfa-form">
              <div class="form-group">
                <label for="mfa-code">Verification Code</label>
                <input id="mfa-code" type="text" class="mfa-input" maxlength="6" pattern="[0-9]{6}"
                       placeholder="000000" required autofocus autocomplete="one-time-code">
              </div>
              <button type="submit" class="btn btn-primary" id="mfa-btn">Verify</button>
            </form>
            <div class="sa-text-center sa-mt-1">
              <button class="btn btn-outline btn-sm" onclick="window.__backToLogin()">Back to login</button>
            </div>
          </div>
        </div>
      </div>`;

    document.getElementById("mfa-form").addEventListener("submit", handleMFA);
    window.__backToLogin = () => { state.mfaToken = null; state.mfaUsername = null; render(); };
  }

  async function handleMFA(e) {
    e.preventDefault();
    const code = document.getElementById("mfa-code").value.trim();
    const alertBox = document.getElementById("mfa-alert");
    const btn = document.getElementById("mfa-btn");

    btn.disabled = true;
    btn.textContent = "Verifying...";

    try {
      const res = await fetch(API + "/auth/mfa/verify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + state.mfaToken,
        },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();

      if (!res.ok) {
        alertBox.innerHTML = `<div class="alert alert-error">${esc(data.error || "Verification failed")}</div>`;
        btn.disabled = false;
        btn.textContent = "Verify";
        return;
      }

      state.mfaToken = null;
      state.mfaUsername = null;
      saveAuth(data.token, data.refresh_token, data.user);
      startHeartbeat();
      render();
    } catch {
      alertBox.innerHTML = '<div class="alert alert-error">Connection error.</div>';
      btn.disabled = false;
      btn.textContent = "Verify";
    }
  }

  // ── System Picker ────────────────────────────────────────────────
  function renderSystemPicker() {
    const systems = (state.user.systems || []).map((s) => {
      const m = systemMeta[s.system_key] || { icon: "\u{1F4BB}", label: s.system_key, color: "#64748b", desc: "" };
      return { ...s, ...m };
    });

    app.innerHTML = `
      <div class="login-page picker-bg">
        <button class="btn btn-outline btn-sm picker-logout" id="picker-logout">${icons.logout} Sign Out</button>
        <div class="picker-body">
          <div class="picker-welcome">
            <h1>Welcome, ${esc(state.user.display_name || state.user.username)}</h1>
            <p>Select a system to continue</p>
          </div>
          <div class="system-grid-2x2">
            ${systems.map((s) => `
              <div class="system-card" data-system="${s.system_key}">
                <div class="system-icon">${s.icon}</div>
                <div class="system-name">${esc(s.label)}</div>
                <div class="system-role">${esc(s.role)}</div>
                <div class="system-desc">${esc(s.desc)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      </div>`;

    document.querySelectorAll(".system-card").forEach((el) => {
      el.addEventListener("click", () => {
        setActiveSystem(el.dataset.system);
        render();
      });
    });
    document.getElementById("picker-logout").addEventListener("click", () => { clearAuth(); render(); });
  }

  // ══════════════════════════════════════════════════════════════════
  //  SUPERADMIN APP SHELL
  // ══════════════════════════════════════════════════════════════════

  let saCurrentPage = "dashboard";

  function renderSuperadminApp() {
    const displayName = state.user.display_name || state.user.username || "Admin";

    app.innerHTML = `
      <div class="app sa-app">
        <aside class="sidebar sa-sidebar" id="sidebar">
          <div class="sidebar-header sa-header">
            <div class="brand-icon sa-brand">\u{1F393}</div>
            <div><h2>Education System</h2><span>Super Admin</span></div>
          </div>
          <nav class="sidebar-nav">
            <div class="nav-section">
              <div class="nav-section-label">Navigation</div>
              ${saNavItem("dashboard", icons.home, "Dashboard")}
              ${saNavItem("health", icons.activity, "System Health")}
              ${saNavItem("users", icons.users, "User Management")}
              ${saNavItem("analytics", icons.award, "Student Analytics")}
              ${saNavItem("notifications", icons.bell, "Notifications")}
              ${saNavItem("search", icons.search, "Student Search")}
              ${saNavItem("journey", icons.layers, "Student Journey")}
              ${saNavItem("permissions", icons.shield, "Permission Matrix")}
              ${saNavItem("audit", icons.clipboard, "Audit Log")}
              ${saNavItem("backup", icons.archive, "Backup / Restore")}
              ${saNavItem("batch", icons.zap, "Batch Operations")}
              ${saNavItem("sessions", icons.eye, "Active Sessions")}
              ${saNavItem("launch", icons.play, "Quick Launch")}
            </div>
          </nav>
          <div class="sidebar-footer">
            <div class="sa-version">v7.23.0</div>
          </div>
        </aside>
        <div class="main">
          <header class="topbar sa-topbar">
            <div class="topbar-left">
              <button class="mobile-toggle" id="mobile-toggle">${icons.menu}</button>
              <h1 id="sa-page-title">Dashboard</h1>
            </div>
            <div class="topbar-actions">
              <span class="sa-user-badge">Logged in as: ${esc(displayName)}</span>
              <button class="btn btn-outline btn-sm" id="sa-switch" title="Switch to single-system view">${icons.grid} Systems</button>
              <button class="btn btn-danger btn-sm" id="sa-logout">${icons.logout} Logout</button>
            </div>
          </header>
          <div class="content sa-content" id="sa-page-content">
            <div class="loader"><div class="spinner"></div></div>
          </div>
        </div>
      </div>`;

    // Bind sidebar nav
    document.querySelectorAll(".sa-nav-item[data-page]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        saCurrentPage = el.dataset.page;
        renderSuperadminApp();
      });
    });

    document.getElementById("sa-switch").addEventListener("click", () => {
      state.activeSystem = null;
      localStorage.removeItem("edu_active_system");
      saCurrentPage = "dashboard";
      renderSystemPicker();
    });
    document.getElementById("sa-logout").addEventListener("click", () => {
      clearAuth();
      saCurrentPage = "dashboard";
      render();
    });
    document.getElementById("mobile-toggle").addEventListener("click", () => {
      document.getElementById("sidebar").classList.toggle("open");
    });

    loadSuperadminPage(saCurrentPage);
  }

  function saNavItem(key, icon, label) {
    const active = saCurrentPage === key ? " active" : "";
    return `<a class="nav-item sa-nav-item${active}" data-page="${key}">${icon}<span>${label}</span></a>`;
  }

  // ── Superadmin Page Loader ─────────────────────────────────────────
  async function loadSuperadminPage(page) {
    stopSessionRefresh();
    const content = document.getElementById("sa-page-content");
    const title = document.getElementById("sa-page-title");
    const titles = {
      dashboard: "Dashboard Overview",
      health: "System Health",
      users: "User Management",
      analytics: "Student Analytics",
      notifications: "Notifications",
      search: "Student Search",
      journey: "Student Journey",
      permissions: "Permission Matrix",
      audit: "Audit Log",
      backup: "Backup / Restore",
      batch: "Batch Operations",
      sessions: "Active Sessions",
      launch: "Quick Launch",
    };
    title.textContent = titles[page] || "Dashboard";
    content.innerHTML = '<div class="loader"><div class="spinner"></div></div>';

    try {
      switch (page) {
        case "dashboard": await loadSADashboard(content); break;
        case "health": await loadSAHealth(content); break;
        case "users": await loadSAUsers(content); break;
        case "analytics": await loadSAAnalytics(content); break;
        case "notifications": await loadSANotifications(content); break;
        case "search": await loadSASearch(content); break;
        case "journey": await loadSAJourney(content); break;
        case "permissions": await loadSAPermissions(content); break;
        case "audit": await loadSAAudit(content); break;
        case "backup": await loadSABackup(content); break;
        case "batch": loadSABatch(content); break;
        case "sessions": await loadSASessions(content); break;
        case "launch": loadSALaunch(content); break;
        default: content.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F4CB}</div><p>Page not found</p></div>'; break;
      }
    } catch (err) {
      content.innerHTML = `<div class="alert alert-error">Failed to load: ${esc(err.message)}</div>`;
    }
  }

  // ── Superadmin: Dashboard Overview ─────────────────────────────────
  async function loadSADashboard(el) {
    const res = await apiFetch("/web/superadmin/overview");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
      return;
    }

    const systems = d.systems || [];
    const today = new Date().toLocaleDateString("en-GB", {
      weekday: "long", day: "numeric", month: "long", year: "numeric"
    });

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Dashboard Overview</h2>
        <p>Welcome back. Today is ${today}.</p>
      </div>

      <div class="sa-system-cards">
        ${systems.map(s => {
          const meta = systemMeta[s.system] || { icon: "\u{1F4BB}", label: s.label, color: "#95a5a6" };
          const statusColor = s.status === "online" ? "#2ecc71" : (s.status === "error" ? "#e74c3c" : "#95a5a6");
          return `
          <div class="sa-sys-card">
            <div class="sa-sys-accent" style="background:${meta.color}"></div>
            <div class="sa-sys-body">
              <div class="sa-sys-title-row">
                <span class="sa-sys-name">${esc(s.label)}</span>
                <span class="sa-sys-dot" style="background:${statusColor}" title="${esc(s.status)}"></span>
              </div>
              <div class="sa-sys-stats">
                <div class="sa-sys-stat"><span class="sa-stat-label">Students</span><span class="sa-stat-val">${s.student_count}</span></div>
                <div class="sa-sys-stat"><span class="sa-stat-label">Staff</span><span class="sa-stat-val">${s.staff_count}</span></div>
                <div class="sa-sys-stat"><span class="sa-stat-label">DB Size</span><span class="sa-stat-val">${s.db_size_mb} MB</span></div>
              </div>
            </div>
          </div>`;
        }).join("")}
      </div>

      <div class="sa-summary-row">
        ${saSummaryCard("Total Students", d.total_students || 0, "#2980b9")}
        ${saSummaryCard("Total Staff", d.total_staff || 0, "#27ae60")}
        ${saSummaryCard("Total Transfers", d.total_transfers || 0, "#8e44ad")}
        ${saSummaryCard("Registered Users", d.total_users || 0, "#e67e22")}
      </div>

      <div class="sa-section">
        <h3>Recent Activity</h3>
        <div class="sa-activity-list">
          ${(d.recent_activity && d.recent_activity.length) ? d.recent_activity.map(a => `
            <div class="sa-activity-item">
              <span class="sa-activity-dot"></span>
              <span class="sa-activity-text">${esc(a.action || a.description || a.type || "Activity")}: ${esc(a.details || a.username || a.user_id || "")}</span>
              <span class="sa-activity-time">${esc(a.timestamp || a.created_at || "")}</span>
            </div>
          `).join("") : '<p class="sa-empty">No recent activity recorded.</p>'}
        </div>
      </div>`;
  }

  function saSummaryCard(label, value, color) {
    return `
      <div class="sa-stat-card">
        <div class="sa-stat-accent" style="background:${color}"></div>
        <div class="sa-stat-label">${label}</div>
        <div class="sa-stat-value">${value}</div>
      </div>`;
  }

  // ── Superadmin: System Health ──────────────────────────────────────
  async function loadSAHealth(el) {
    const res = await apiFetch("/web/superadmin/health");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
      return;
    }

    el.innerHTML = `
      <div class="sa-health-grid">
        ${(d.systems || []).map(s => {
          const meta = systemMeta[s.system] || { color: "#95a5a6" };
          const statusColor = s.status === "online" ? "#2ecc71" : (s.status === "error" ? "#e74c3c" : "#95a5a6");
          const statusText = s.status === "online" ? "Online" : (s.status === "error" ? "Error" : "Offline");
          return `
          <div class="sa-health-card">
            <div class="sa-health-accent" style="background:${meta.color}"></div>
            <div class="sa-health-body">
              <h3>${esc(s.label)}</h3>
              <div class="sa-health-row"><span>Status</span><span class="badge badge-${s.status === 'online' ? 'success' : 'danger'}">${statusText}</span></div>
              <div class="sa-health-row"><span>Database</span><span>${s.db_path ? 'Exists' : 'Not found'}</span></div>
              <div class="sa-health-row"><span>DB Size</span><span>${s.db_size_mb} MB</span></div>
              <div class="sa-health-row"><span>Students</span><span>${s.student_count}</span></div>
              <div class="sa-health-row"><span>Staff</span><span>${s.staff_count}</span></div>
              <div class="sa-health-row"><span>Tables</span><span>${s.table_count || 'N/A'}</span></div>
              ${s.last_activity ? `<div class="sa-health-row"><span>Last Activity</span><span>${esc(s.last_activity)}</span></div>` : ''}
              <div class="sa-health-row sa-health-path"><span>Path</span><span title="${esc(s.db_path || '')}">${esc(s.db_path ? s.db_path.split('/').slice(-3).join('/') : 'N/A')}</span></div>
            </div>
          </div>`;
        }).join("")}
      </div>`;
  }

  // ── Superadmin: User Management ───────────────────────────────────
  async function loadSAUsers(el) {
    const res = await apiFetch("/web/users");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
      return;
    }

    const users = d.users || [];

    el.innerHTML = `
      <div class="sa-users-toolbar">
        <div class="sa-filter-group">
          <label>System:</label>
          <select id="sa-filter-system">
            <option value="">All</option>
            <option value="primary">Primary</option>
            <option value="school">Secondary</option>
            <option value="college">College</option>
            <option value="university">University</option>
          </select>
        </div>
        <div class="sa-filter-group">
          <label>Role:</label>
          <select id="sa-filter-role">
            <option value="">All</option>
            <option value="admin">Admin</option>
            <option value="staff">Staff</option>
            <option value="student">Student</option>
            <option value="parent">Parent</option>
          </select>
        </div>
        <div class="search-box">
          ${icons.search}
          <input id="sa-user-search" placeholder="Search users..." type="text">
        </div>
      </div>
      <div class="section">
        <table class="data-table" id="sa-user-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Display Name</th>
              <th>Email</th>
              <th>System(s)</th>
              <th>Role(s)</th>
              <th>Active</th>
              <th>Last Login</th>
            </tr>
          </thead>
          <tbody>
            ${users.map(u => `
              <tr data-systems="${(u.systems || []).map(s => s.system_key).join(',')}"
                  data-roles="${(u.systems || []).map(s => s.role).join(',')}">
                <td><strong>${esc(u.username)}</strong></td>
                <td>${esc(u.display_name || '-')}</td>
                <td>${esc(u.email || '-')}</td>
                <td>${(u.systems || []).map(s =>
                  `<span class="badge badge-info badge-spaced">${esc(s.system_key)}</span>`
                ).join("")}</td>
                <td>${(u.systems || []).map(s =>
                  `<span class="badge badge-neutral badge-spaced">${esc(s.role)}</span>`
                ).join("")}</td>
                <td><span class="badge badge-${u.is_active ? 'success' : 'danger'}">${u.is_active ? 'Yes' : 'No'}</span></td>
                <td>${esc(u.last_login || '-')}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    // Filter logic
    function filterUsers() {
      const q = (document.getElementById("sa-user-search").value || "").toLowerCase();
      const sys = document.getElementById("sa-filter-system").value;
      const role = document.getElementById("sa-filter-role").value;
      document.querySelectorAll("#sa-user-table tbody tr").forEach(row => {
        const textMatch = !q || row.textContent.toLowerCase().includes(q);
        const sysMatch = !sys || (row.dataset.systems || "").includes(sys);
        const roleMatch = !role || (row.dataset.roles || "").includes(role);
        row.classList.toggle("sa-hidden", !(textMatch && sysMatch && roleMatch));
      });
    }
    document.getElementById("sa-user-search").addEventListener("input", filterUsers);
    document.getElementById("sa-filter-system").addEventListener("change", filterUsers);
    document.getElementById("sa-filter-role").addEventListener("change", filterUsers);
  }

  // ── Live Sessions (shared by superadmin + admin dashboards) ──────
  let _sessionRefreshTimer = null;

  function stopSessionRefresh() {
    if (_sessionRefreshTimer) { clearInterval(_sessionRefreshTimer); _sessionRefreshTimer = null; }
  }

  async function loadSASessions(el) {
    stopSessionRefresh();

    async function refresh() {
      const res = await apiFetch("/web/admin/sessions");
      if (!res) return;
      const d = await res.json();
      if (!res.ok) {
        el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
        return;
      }

      const sessions = d.sessions || [];
      const myId = state.user ? state.user.user_id || state.user.id : null;
      const now = new Date().toLocaleTimeString();

      el.innerHTML = `
        <div class="section">
          <div class="section-header" style="display:flex;justify-content:space-between;align-items:center">
            <h2>${sessions.length} Active User${sessions.length !== 1 ? 's' : ''}</h2>
            <span style="font-size:.8rem;color:var(--text-muted)">Live — last updated ${now}</span>
          </div>
          ${sessions.length ? `
          <table class="data-table">
            <thead><tr><th>Username</th><th>Display Name</th><th>Sessions</th><th>Last Login</th><th>Expires</th><th>Action</th></tr></thead>
            <tbody>
              ${sessions.map(s => `
                <tr>
                  <td><strong>${esc(s.username || '-')}</strong>${s.user_id == myId ? ' <span style="color:var(--accent);font-size:.75rem">(you)</span>' : ''}</td>
                  <td>${esc(s.display_name || '-')}</td>
                  <td>${s.session_count || 1}</td>
                  <td>${esc(s.last_login || '-')}</td>
                  <td>${esc(s.expires_at || '-')}</td>
                  <td>${s.user_id != myId ? `<button class="btn btn-sm btn-danger force-logout-btn" data-uid="${s.user_id}" data-uname="${esc(s.username || s.user_id)}">Force Logout</button>` : ''}</td>
                </tr>`).join("")}
            </tbody>
          </table>` : '<p class="sa-empty">No active sessions found.</p>'}
        </div>`;

      el.querySelectorAll(".force-logout-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const uid = btn.dataset.uid;
          const uname = btn.dataset.uname;
          if (!confirm(`Force logout all sessions for "${uname}"?`)) return;
          btn.disabled = true;
          btn.textContent = "Logging out...";
          try {
            const r = await apiFetch("/web/admin/force-logout", {
              method: "POST",
              body: JSON.stringify({ user_id: parseInt(uid) }),
            });
            const rd = await r.json();
            if (r.ok) {
              refresh();
            } else {
              alert(rd.error || "Failed to force logout.");
              btn.disabled = false;
              btn.textContent = "Force Logout";
            }
          } catch (e) {
            alert("Error: " + e.message);
            btn.disabled = false;
            btn.textContent = "Force Logout";
          }
        });
      });
    }

    await refresh();
    _sessionRefreshTimer = setInterval(refresh, 5000);
  }

  // ── Superadmin: Audit Log ─────────────────────────────────────────
  async function loadSAAudit(el) {
    const res = await apiFetch("/web/superadmin/audit");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load")}</div>`;
      return;
    }

    const entries = d.entries || [];

    el.innerHTML = `
      <div class="section">
        <div class="section-header"><h2>Audit Log (${entries.length} entries)</h2></div>
        ${entries.length ? `
        <table class="data-table">
          <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Details</th></tr></thead>
          <tbody>
            ${entries.map(e => `
              <tr>
                <td>${esc(e.timestamp || e.created_at || '-')}</td>
                <td><strong>${esc(e.username || e.user_id || '-')}</strong></td>
                <td>${esc(e.action || e.type || '-')}</td>
                <td>${esc(e.details || e.description || '-')}</td>
              </tr>`).join("")}
          </tbody>
        </table>` : '<p class="sa-empty">No audit entries found.</p>'}
      </div>`;
  }

  // ── Superadmin: Quick Launch ──────────────────────────────────────
  function loadSALaunch(el) {
    el.innerHTML = `
      <div class="sa-launch-info">
        <p>Launch an individual education system. You will enter as superadmin.</p>
      </div>
      <div class="sa-launch-grid">
        ${["primary", "school", "college", "university"].map(sk => {
          const m = systemMeta[sk] || { icon: "\u{1F4BB}", label: sk, color: "#64748b" };
          return `
          <div class="sa-launch-card" data-system="${sk}">
            <div class="sa-launch-accent" style="background:${m.color}"></div>
            <div class="sa-launch-icon">${m.icon}</div>
            <div class="sa-launch-name">${esc(m.label)}</div>
            <div class="sa-launch-desc">${esc(m.desc || "")}</div>
            <button class="btn btn-primary btn-sm sa-launch-btn" data-system="${sk}">Launch</button>
          </div>`;
        }).join("")}
      </div>`;

    el.querySelectorAll(".sa-launch-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        setActiveSystem(btn.dataset.system);
        currentPage = "dashboard";
        renderApp();
      });
    });
  }

  // ── Superadmin: Student Analytics ───────────────────────────────────
  async function loadSAAnalytics(el) {
    const res = await apiFetch("/web/superadmin/analytics");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) { el.innerHTML = `<div class="alert alert-error">${esc(d.error)}</div>`; return; }

    const s = d.summary || {};
    const perSystem = d.per_system || [];
    const retention = d.retention || [];
    const transfers = d.transfers || [];
    const trends = d.trends || [];

    const systemLabels = { primary: "Primary School", school: "Secondary School", secondary: "Secondary School", college: "Sixth Form College", university: "University" };

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Student Analytics</h2>
        <p>Cross-system student statistics, transfer rates, and retention data.</p>
      </div>

      <div class="sa-summary-row">
        ${saSummaryCard("Total Students", s.total_students || 0, "#2980b9")}
        ${saSummaryCard("Active", s.total_active || 0, "#27ae60")}
        ${saSummaryCard("Transferred", s.total_transferred || 0, "#8e44ad")}
        ${saSummaryCard("Graduated", s.total_graduated || 0, "#e67e22")}
      </div>

      ${perSystem.length ? `
      <div class="sa-section">
        <h3>Per-System Breakdown</h3>
        <div class="sa-system-cards">
          ${perSystem.map(ps => {
            const color = systemMeta[ps.system] ? systemMeta[ps.system].color : "#95a5a6";
            return `
            <div class="sa-sys-card">
              <div class="sa-sys-accent" style="background:${color}"></div>
              <div class="sa-sys-body">
                <div class="sa-sys-name sa-sys-name-bold">${esc(ps.label || ps.system)}</div>
                <div class="sa-sys-stats">
                  <div class="sa-sys-stat"><span class="sa-stat-label">Total</span><span class="sa-stat-val">${ps.total || 0}</span></div>
                  <div class="sa-sys-stat"><span class="sa-stat-label">Active</span><span class="sa-stat-val">${ps.active || 0}</span></div>
                  <div class="sa-sys-stat"><span class="sa-stat-label">Transferred</span><span class="sa-stat-val">${ps.transferred || 0}</span></div>
                  <div class="sa-sys-stat"><span class="sa-stat-label">Graduated</span><span class="sa-stat-val">${ps.graduated || 0}</span></div>
                  <div class="sa-sys-stat"><span class="sa-stat-label">Dropped Out</span><span class="sa-stat-val">${ps.dropped_out || 0}</span></div>
                </div>
              </div>
            </div>`;
          }).join("")}
        </div>
      </div>` : ''}

      ${retention.length ? `
      <div class="sa-section">
        <h3>Retention Statistics</h3>
        <table class="data-table">
          <thead><tr><th>System</th><th>Total</th><th>Active</th><th>Retained %</th><th>Dropped Out</th><th>Dropout %</th></tr></thead>
          <tbody>${retention.map(r => `
            <tr>
              <td><strong>${esc(r.label || r.system || '')}</strong></td>
              <td>${r.total || 0}</td>
              <td>${r.active || 0}</td>
              <td>${r.retained_pct || 0}%</td>
              <td>${r.dropped_out || 0}</td>
              <td>${r.dropout_pct || 0}%</td>
            </tr>`).join("")}</tbody>
        </table>
      </div>` : ''}

      ${transfers.length ? `
      <div class="sa-section">
        <h3>Transfer Rates</h3>
        <table class="data-table">
          <thead><tr><th>Source</th><th>Destination</th><th>Count</th><th>Rate %</th></tr></thead>
          <tbody>${transfers.map(t => `
            <tr>
              <td>${esc(systemLabels[t.source_system] || t.source_system || '')}</td>
              <td>${esc(systemLabels[t.destination_system] || t.destination_system || '')}</td>
              <td>${t.count || 0}</td>
              <td>${t.rate_pct || 0}%</td>
            </tr>`).join("")}</tbody>
        </table>
      </div>` : ''}

      ${trends.length ? `
      <div class="sa-section">
        <h3>Year-over-Year Trends</h3>
        <table class="data-table">
          <thead><tr><th>System</th><th>Year</th><th>Student Count</th></tr></thead>
          <tbody>${trends.map(t => `
            <tr>
              <td>${esc(t.label || t.system || '')}</td>
              <td>${t.year || ''}</td>
              <td>${t.student_count || 0}</td>
            </tr>`).join("")}</tbody>
        </table>
      </div>` : ''}
    `;
  }

  // ── Superadmin: Notifications ─────────────────────────────────────
  async function loadSANotifications(el) {
    const res = await apiFetch("/web/superadmin/notifications");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) { el.innerHTML = `<div class="alert alert-error">${esc(d.error)}</div>`; return; }

    const notifs = d.notifications || [];
    const unread = d.unread_count || 0;

    el.innerHTML = `
      <div class="sa-notif-toolbar">
        <span class="badge badge-${unread > 0 ? 'danger' : 'success'} sa-notif-count">${unread} unread</span>
        ${unread > 0 ? '<button class="btn btn-outline btn-sm" id="sa-mark-read">Mark All Read</button>' : ''}
        <button class="btn btn-primary btn-sm" id="sa-send-notif">${icons.bell} Send Notification</button>
        <button class="btn btn-outline btn-sm sa-broadcast-btn" id="sa-broadcast">Broadcast to Role</button>
      </div>
      <div class="section">
        ${notifs.length ? `
        <table class="data-table" id="sa-notif-table">
          <thead><tr><th>ID</th><th>From</th><th>Title</th><th>Message</th><th>Priority</th><th>Read</th><th>Date</th></tr></thead>
          <tbody>${notifs.map(n => `
            <tr>
              <td>${n.id || ''}</td>
              <td>${esc(n.sender_system || '')}</td>
              <td><strong>${esc(n.title || '')}</strong></td>
              <td>${esc((n.message || '').substring(0, 80))}</td>
              <td><span class="badge badge-${n.priority === 'urgent' || n.priority === 'high' ? 'danger' : 'neutral'}">${esc(n.priority || 'normal')}</span></td>
              <td>${n.is_read ? 'Yes' : '<strong>No</strong>'}</td>
              <td>${esc((n.created_at || '').substring(0, 16))}</td>
            </tr>`).join("")}</tbody>
        </table>` : '<p class="sa-empty">No notifications found.</p>'}
      </div>

      <div class="modal-overlay" id="sa-notif-modal">
        <div class="modal">
          <h2 id="sa-notif-modal-title">Send Notification</h2>
          <div id="sa-notif-modal-alert"></div>
          <form id="sa-notif-form">
            <div class="form-group" id="sa-notif-recip-group">
              <label>Recipient User ID</label>
              <input type="number" id="sa-notif-recip">
            </div>
            <div class="form-group">
              <label>Target System</label>
              <select id="sa-notif-system">
                <option value="primary">Primary</option><option value="school">Secondary</option>
                <option value="college">College</option><option value="university" selected>University</option>
              </select>
            </div>
            <div class="form-group sa-hidden" id="sa-notif-role-group">
              <label>Target Role</label>
              <select id="sa-notif-role">
                <option value="student">Student</option><option value="staff">Staff</option>
                <option value="admin">Admin</option><option value="parent">Parent</option>
              </select>
            </div>
            <div class="form-group">
              <label>Title</label>
              <input type="text" id="sa-notif-title" required>
            </div>
            <div class="form-group">
              <label>Priority</label>
              <select id="sa-notif-priority">
                <option value="low">Low</option><option value="normal" selected>Normal</option>
                <option value="high">High</option><option value="urgent">Urgent</option>
              </select>
            </div>
            <div class="form-group">
              <label>Message</label>
              <textarea id="sa-notif-msg" rows="3" class="sa-textarea"></textarea>
            </div>
            <div class="modal-actions">
              <button type="button" class="btn btn-outline btn-sm" id="sa-notif-cancel">Cancel</button>
              <button type="submit" class="btn btn-primary btn-sm" id="sa-notif-submit">Send</button>
            </div>
          </form>
        </div>
      </div>`;

    // Mark all read
    const markBtn = document.getElementById("sa-mark-read");
    if (markBtn) {
      markBtn.addEventListener("click", async () => {
        await apiFetch("/web/superadmin/notifications/mark-read", { method: "POST" });
        saCurrentPage = "notifications";
        renderSuperadminApp();
      });
    }

    // Modal helpers
    let isBroadcast = false;
    const modal = document.getElementById("sa-notif-modal");
    const closeModal = () => modal.classList.remove("active");
    document.getElementById("sa-notif-cancel").addEventListener("click", closeModal);

    document.getElementById("sa-send-notif").addEventListener("click", () => {
      isBroadcast = false;
      document.getElementById("sa-notif-modal-title").textContent = "Send Notification";
      document.getElementById("sa-notif-recip-group").classList.remove("sa-hidden");
      document.getElementById("sa-notif-role-group").classList.add("sa-hidden");
      document.getElementById("sa-notif-modal-alert").innerHTML = "";
      modal.classList.add("active");
    });

    document.getElementById("sa-broadcast").addEventListener("click", () => {
      isBroadcast = true;
      document.getElementById("sa-notif-modal-title").textContent = "Broadcast to Role";
      document.getElementById("sa-notif-recip-group").classList.add("sa-hidden");
      document.getElementById("sa-notif-role-group").classList.remove("sa-hidden");
      document.getElementById("sa-notif-modal-alert").innerHTML = "";
      modal.classList.add("active");
    });

    document.getElementById("sa-notif-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("sa-notif-modal-alert");
      const endpoint = isBroadcast ? "/web/superadmin/notifications/broadcast" : "/web/superadmin/notifications/send";
      const payload = {
        title: document.getElementById("sa-notif-title").value,
        message: document.getElementById("sa-notif-msg").value,
        priority: document.getElementById("sa-notif-priority").value,
      };
      if (isBroadcast) {
        payload.target_system = document.getElementById("sa-notif-system").value;
        payload.target_role = document.getElementById("sa-notif-role").value;
      } else {
        payload.recipient_user_id = document.getElementById("sa-notif-recip").value;
        payload.recipient_system = document.getElementById("sa-notif-system").value;
      }
      const r = await apiFetch(endpoint, { method: "POST", body: JSON.stringify(payload) });
      if (!r) return;
      const data = await r.json();
      if (!r.ok) {
        alertBox.innerHTML = `<div class="alert alert-error">${esc(data.error)}</div>`;
        return;
      }
      closeModal();
      saCurrentPage = "notifications";
      renderSuperadminApp();
    });
  }

  // ── Superadmin: Student Search ────────────────────────────────────
  async function loadSASearch(el) {
    const systemLabels = { primary: "Primary School", school: "Secondary School", secondary: "Secondary School", college: "Sixth Form College", university: "University" };

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Student Search</h2>
        <p>Search for students across all 4 education systems.</p>
      </div>
      <div class="sa-search-bar">
        <div class="search-box sa-search-grow">
          ${icons.search}
          <input id="sa-search-input" placeholder="Enter student name or ID..." type="text" class="sa-w-full">
        </div>
        <button class="btn btn-primary btn-sm" id="sa-search-btn">Search</button>
      </div>
      <div class="section" id="sa-search-results">
        <p class="sa-empty">Enter at least 2 characters and click Search.</p>
      </div>
      <div class="sa-section sa-hidden" id="sa-search-detail">
        <h3>Student Details</h3>
        <div id="sa-search-detail-body"></div>
      </div>`;

    const doSearch = async () => {
      const q = document.getElementById("sa-search-input").value.trim();
      if (q.length < 2) return;
      const resultsEl = document.getElementById("sa-search-results");
      resultsEl.innerHTML = '<div class="loader"><div class="spinner"></div></div>';
      const res = await apiFetch(`/web/superadmin/search?q=${encodeURIComponent(q)}`);
      if (!res) return;
      const d = await res.json();
      const results = d.results || [];
      if (!results.length) {
        resultsEl.innerHTML = '<p class="sa-empty">No students found matching your query.</p>';
        return;
      }
      resultsEl.innerHTML = `
        <div class="section-header"><h2>${results.length} Result(s)</h2></div>
        <table class="data-table">
          <thead><tr><th>System</th><th>Student ID</th><th>Name</th><th>Status</th><th>Year / Group</th></tr></thead>
          <tbody>${results.map((r, i) => `
            <tr class="sa-search-row sa-cursor-pointer" data-idx="${i}">
              <td><span class="badge badge-info">${esc(systemLabels[r.system] || r.system)}</span></td>
              <td><strong>${esc(r.student_id || r.id || '')}</strong></td>
              <td>${esc(r.name || '')}</td>
              <td>${esc(r.status || '')}</td>
              <td>${esc(r.year_group || '')}</td>
            </tr>`).join("")}</tbody>
        </table>`;
      // Click to show detail
      resultsEl.querySelectorAll(".sa-search-row").forEach(row => {
        row.addEventListener("click", () => {
          const idx = parseInt(row.dataset.idx);
          const r = results[idx];
          const detailEl = document.getElementById("sa-search-detail");
          detailEl.classList.remove("sa-hidden");
          document.getElementById("sa-search-detail-body").innerHTML = `
            <table class="data-table sa-max-w-400">
              <tr><td class="sa-fw-bold">System</td><td>${esc(systemLabels[r.system] || r.system)}</td></tr>
              <tr><td class="sa-fw-bold">Student ID</td><td>${esc(r.student_id || r.id || '')}</td></tr>
              <tr><td class="sa-fw-bold">Name</td><td>${esc(r.name || '')}</td></tr>
              <tr><td class="sa-fw-bold">Status</td><td>${esc(r.status || '')}</td></tr>
              <tr><td class="sa-fw-bold">Year / Group</td><td>${esc(r.year_group || '')}</td></tr>
            </table>`;
        });
      });
    };

    document.getElementById("sa-search-btn").addEventListener("click", doSearch);
    document.getElementById("sa-search-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  }

  // ── Superadmin: Student Journey ───────────────────────────────────
  async function loadSAJourney(el) {
    const systemLabels = { primary: "Primary School", school: "Secondary School", secondary: "Secondary School", college: "Sixth Form College", university: "University" };
    const systemColors = { primary: "#e67e22", school: "#8e44ad", secondary: "#8e44ad", college: "#27ae60", university: "#2980b9" };

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Student Journey Timeline</h2>
        <p>Visualise a student's path through Primary, Secondary, College, and University.</p>
      </div>
      <div class="sa-search-bar">
        <div class="search-box sa-search-grow">
          ${icons.search}
          <input id="sa-journey-input" placeholder="Enter student name or ID..." type="text" class="sa-w-full">
        </div>
        <button class="btn btn-primary btn-sm" id="sa-journey-btn">Search</button>
      </div>
      <div id="sa-journey-status" class="sa-empty sa-journey-status">Enter a student name or ID and click Search.</div>
      <div id="sa-journey-timeline"></div>`;

    const doSearch = async () => {
      const q = document.getElementById("sa-journey-input").value.trim();
      if (q.length < 2) return;
      const statusEl = document.getElementById("sa-journey-status");
      const timelineEl = document.getElementById("sa-journey-timeline");
      statusEl.textContent = "Searching...";
      timelineEl.innerHTML = "";

      // First search for the student
      const searchRes = await apiFetch(`/web/superadmin/search?q=${encodeURIComponent(q)}`);
      if (!searchRes) return;
      const searchData = await searchRes.json();
      const results = searchData.results || [];
      if (!results.length) {
        statusEl.textContent = "No students found.";
        return;
      }

      const first = results[0];
      // Get journey
      const journeyRes = await apiFetch(`/web/superadmin/journey?name=${encodeURIComponent(first.name || q)}&student_id=${encodeURIComponent(first.student_id || first.id || '')}&system=${encodeURIComponent(first.system || '')}`);
      if (!journeyRes) return;
      const jd = await journeyRes.json();
      const journey = jd.journey;

      if (!journey || !journey.stages || !journey.stages.length) {
        statusEl.textContent = `Found ${first.name || 'student'} in ${systemLabels[first.system] || first.system}, but no cross-system journey data available.`;
        // Show single stage
        timelineEl.innerHTML = renderJourneyCard(first.system, { name: first.name, status: first.status, student_id: first.student_id || first.id }, true);
        return;
      }

      statusEl.textContent = `Journey for: ${journey.name || first.name} (${journey.stages.length} stage(s))`;
      timelineEl.innerHTML = journey.stages.map((stage, i) =>
        renderJourneyCard(stage.system, stage, i === journey.stages.length - 1)
      ).join("");
    };

    function renderJourneyCard(sysKey, stage, isLast) {
      const color = systemColors[sysKey] || "#95a5a6";
      const label = systemLabels[sysKey] || (sysKey || "").replace(/^\w/, c => c.toUpperCase());
      const infoParts = [];
      if (stage.name) infoParts.push(`Name: ${stage.name}`);
      if (stage.student_id || stage.id) infoParts.push(`ID: ${stage.student_id || stage.id}`);
      if (stage.status) infoParts.push(`Status: ${stage.status}`);
      if (stage.enrollment_date || stage.enrolled_date) infoParts.push(`Enrolled: ${(stage.enrollment_date || stage.enrolled_date || '').substring(0, 10)}`);
      if (stage.year_group) infoParts.push(`Year: ${stage.year_group}`);

      return `
        <div class="sa-journey-stage">
          <div class="sa-journey-dot-col">
            <div class="sa-journey-dot" style="background:${color}"></div>
            ${!isLast ? '<div class="sa-journey-line"></div>' : ''}
          </div>
          <div class="sa-journey-card">
            <div class="sa-sys-accent" style="background:${color}"></div>
            <div class="sa-journey-card-body">
              <strong>${esc(label)}</strong>
              ${infoParts.length ? `<div class="sa-journey-info">${infoParts.map(p => esc(p)).join('  |  ')}</div>` : ''}
              ${(stage.academic_history || []).map(h => `<div class="sa-journey-hist">- ${esc(h)}</div>`).join("")}
            </div>
          </div>
        </div>`;
    }

    document.getElementById("sa-journey-btn").addEventListener("click", doSearch);
    document.getElementById("sa-journey-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
  }

  // ── Superadmin: Permission Matrix ─────────────────────────────────
  async function loadSAPermissions(el) {
    const res = await apiFetch("/web/superadmin/permissions");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) { el.innerHTML = `<div class="alert alert-error">${esc(d.error)}</div>`; return; }

    const matrix = d.matrix || [];

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Permission Matrix</h2>
        <p>View user roles across all education systems at a glance.</p>
      </div>
      <div class="section">
        <table class="data-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Display Name</th>
              <th class="sa-text-center">Primary</th>
              <th class="sa-text-center">Secondary</th>
              <th class="sa-text-center">College</th>
              <th class="sa-text-center">University</th>
            </tr>
          </thead>
          <tbody>
            ${matrix.map(u => `
              <tr>
                <td><strong>${esc(u.username)}</strong></td>
                <td>${esc(u.display_name || '-')}</td>
                <td class="sa-text-center">${u.primary ? `<span class="badge badge-info">${esc(u.primary)}</span>` : '<span class="sa-text-muted">\u2014</span>'}</td>
                <td class="sa-text-center">${u.school ? `<span class="badge badge-info">${esc(u.school)}</span>` : '<span class="sa-text-muted">\u2014</span>'}</td>
                <td class="sa-text-center">${u.college ? `<span class="badge badge-info">${esc(u.college)}</span>` : '<span class="sa-text-muted">\u2014</span>'}</td>
                <td class="sa-text-center">${u.university ? `<span class="badge badge-info">${esc(u.university)}</span>` : '<span class="sa-text-muted">\u2014</span>'}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // ── Superadmin: Backup / Restore ──────────────────────────────────
  async function loadSABackup(el) {
    const res = await apiFetch("/web/superadmin/backup/info");
    if (!res) return;
    const d = await res.json();
    if (!res.ok) { el.innerHTML = `<div class="alert alert-error">${esc(d.error)}</div>`; return; }

    const systems = d.systems || [];
    const systemColors = { primary: "#e67e22", school: "#8e44ad", college: "#27ae60", university: "#2980b9", auth: "#e74c3c" };

    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Backup / Restore</h2>
        <p>Create timestamped backups of system databases.</p>
      </div>
      <div class="sa-section">
        <h3>Database Backups</h3>
        ${systems.map(s => `
          <div class="sa-backup-row">
            <div class="sa-backup-accent" style="background:${systemColors[s.system] || '#95a5a6'}"></div>
            <div class="sa-backup-info">
              <strong>${esc(s.label)}</strong>
              <span class="sa-backup-size">${s.db_size_mb} MB</span>
            </div>
            <span class="sa-backup-status" id="sa-backup-status-${s.system}"></span>
            <button class="btn btn-sm sa-backup-btn" data-system="${s.system}" data-color="${systemColors[s.system] || '#95a5a6'}">Backup Now</button>
          </div>`).join("")}
      </div>`;

    // Apply dynamic background colors to backup buttons
    el.querySelectorAll(".sa-backup-btn[data-color]").forEach(btn => {
      btn.style.backgroundColor = btn.dataset.color;
    });

    el.querySelectorAll("[data-system]").forEach(btn => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Backing up...";
        const statusEl = document.getElementById(`sa-backup-status-${btn.dataset.system}`);
        const r = await apiFetch("/web/superadmin/backup", {
          method: "POST",
          body: JSON.stringify({ system: btn.dataset.system }),
        });
        if (!r) return;
        const data = await r.json();
        if (r.ok) {
          statusEl.textContent = `Backed up: ${data.backup}`;
          statusEl.classList.remove("sa-text-danger");
          statusEl.classList.add("sa-text-success");
        } else {
          statusEl.textContent = `Error: ${data.error}`;
          statusEl.classList.remove("sa-text-success");
          statusEl.classList.add("sa-text-danger");
        }
        btn.disabled = false;
        btn.textContent = "Backup Now";
      });
    });
  }

  // ── Superadmin: Batch Operations ──────────────────────────────────
  function loadSABatch(el) {
    el.innerHTML = `
      <div class="sa-welcome">
        <h2>Batch Operations</h2>
        <p>Perform bulk changes across users and systems.</p>
      </div>

      <div class="sa-section">
        <h3>Bulk Role Change</h3>
        <div class="sa-batch-form">
          <div class="sa-filter-group"><label>System:</label>
            <select id="sa-batch-sys"><option value="primary">Primary</option><option value="school">Secondary</option><option value="college">College</option><option value="university" selected>University</option></select>
          </div>
          <div class="sa-filter-group"><label>Current Role:</label>
            <select id="sa-batch-from"><option value="student" selected>Student</option><option value="staff">Staff</option><option value="admin">Admin</option><option value="parent">Parent</option></select>
          </div>
          <div class="sa-filter-group"><label>New Role:</label>
            <select id="sa-batch-to"><option value="student">Student</option><option value="staff" selected>Staff</option><option value="admin">Admin</option><option value="parent">Parent</option></select>
          </div>
          <button class="btn btn-sm sa-batch-apply-btn" id="sa-batch-role-btn">Apply Batch Role Change</button>
        </div>
        <div id="sa-batch-role-result" class="sa-batch-result"></div>
      </div>

      <div class="sa-section">
        <h3>Bulk Deactivation</h3>
        <div class="sa-batch-form">
          <div class="sa-filter-group"><label>System:</label>
            <select id="sa-deact-sys"><option value="primary">Primary</option><option value="school">Secondary</option><option value="college">College</option><option value="university" selected>University</option></select>
          </div>
          <div class="sa-filter-group"><label>Role:</label>
            <select id="sa-deact-role"><option value="student" selected>Student</option><option value="staff">Staff</option><option value="admin">Admin</option><option value="parent">Parent</option></select>
          </div>
          <button class="btn btn-danger btn-sm" id="sa-deact-btn">Deactivate All Matching</button>
        </div>
        <div id="sa-deact-result" class="sa-batch-result"></div>
      </div>`;

    document.getElementById("sa-batch-role-btn").addEventListener("click", async () => {
      const sys = document.getElementById("sa-batch-sys").value;
      const from = document.getElementById("sa-batch-from").value;
      const to = document.getElementById("sa-batch-to").value;
      const resultEl = document.getElementById("sa-batch-role-result");
      if (from === to) { resultEl.innerHTML = '<span class="sa-text-danger">Current and new roles must differ.</span>'; return; }
      if (!confirm(`Change all users with role '${from}' to '${to}' in ${sys}?`)) return;
      const r = await apiFetch("/web/superadmin/batch/role-change", {
        method: "POST", body: JSON.stringify({ system: sys, from_role: from, to_role: to }),
      });
      if (!r) return;
      const data = await r.json();
      if (r.ok) {
        resultEl.innerHTML = `<span class="sa-text-success">Updated ${data.count} user(s) to role '${to}'.</span>`;
      } else {
        resultEl.innerHTML = `<span class="sa-text-danger">${esc(data.error)}</span>`;
      }
    });

    document.getElementById("sa-deact-btn").addEventListener("click", async () => {
      const sys = document.getElementById("sa-deact-sys").value;
      const role = document.getElementById("sa-deact-role").value;
      const resultEl = document.getElementById("sa-deact-result");
      if (!confirm(`Deactivate ALL active users with role '${role}' in ${sys}? This cannot be undone easily.`)) return;
      const r = await apiFetch("/web/superadmin/batch/deactivate", {
        method: "POST", body: JSON.stringify({ system: sys, role: role }),
      });
      if (!r) return;
      const data = await r.json();
      if (r.ok) {
        resultEl.innerHTML = `<span class="sa-text-success">Deactivated ${data.count} user(s).</span>`;
      } else {
        resultEl.innerHTML = `<span class="sa-text-danger">${esc(data.error)}</span>`;
      }
    });
  }

  // ══════════════════════════════════════════════════════════════════
  //  REGULAR (PER-SYSTEM) APP SHELL
  // ══════════════════════════════════════════════════════════════════

  let currentPage = "dashboard";

  function navItem(page, icon, label) {
    return `<a class="nav-item${currentPage === page ? ' active' : ''}" data-page="${page}">${icon}<span>${esc(label)}</span></a>`;
  }

  function renderApp() {
    const sys = systemMeta[state.activeSystem] || { icon: "\u{1F4BB}", label: state.activeSystem, color: "#64748b" };
    const role = getUserRole();
    const isAdmin = role === "admin";
    const isStaff = role === "admin" || role === "staff" || role === "teacher";

    app.innerHTML = `
      <div class="app">
        <aside class="sidebar" id="sidebar">
          <div class="sidebar-header">
            <div class="brand-icon">${sys.icon}</div>
            <div><h2>${esc(sys.label)}</h2><span>Management System</span></div>
          </div>
          <nav class="sidebar-nav">
            <div class="nav-section">
              <div class="nav-section-label">Main</div>
              ${navItem('dashboard', icons.home, 'Dashboard')}
              ${isStaff ? navItem('students', icons.users, state.activeSystem === 'primary' ? 'Pupils' : 'Students') : ''}
              ${navItem('courses', icons.book, 'Courses')}
              ${navItem('attendance', icons.check, 'Attendance')}
              ${navItem('grades', icons.award, 'Grades')}
            </div>
            ${state.activeSystem === 'university' ? `
            <div class="nav-section">
              <div class="nav-section-label">Academics</div>
              ${navItem('tbl:modules', icons.layers, 'Modules')}
              ${navItem('tbl:enrollments', icons.clipboard, 'Enrollments')}
              ${navItem('tbl:assignments', icons.clipboard, 'Assignments')}
              ${navItem('tbl:assessments', icons.award, 'Assessments')}
              ${navItem('tbl:exams', icons.clipboard, 'Exams')}
              ${navItem('tbl:degree_programs', icons.award, 'Degree Programs')}
              ${navItem('tbl:academic_calendar_events', icons.calendar, 'Academic Calendar')}
              ${navItem('tbl:syllabi', icons.book, 'Syllabi')}
              ${navItem('tbl:learning_outcomes', icons.check, 'Learning Outcomes')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Student Life</div>
              ${navItem('tbl:housing_applications', icons.home, 'Housing')}
              ${navItem('tbl:meal_accounts', icons.activity, 'Dining')}
              ${navItem('tbl:student_clubs', icons.users, 'Clubs')}
              ${navItem('tbl:events', icons.calendar, 'Events')}
              ${navItem('tbl:books', icons.book, 'Library')}
              ${navItem('tbl:study_groups', icons.users, 'Study Groups')}
              ${navItem('tbl:virtual_study_rooms', icons.layers, 'Study Rooms')}
              ${navItem('tbl:extracurricular_activities', icons.activity, 'Activities')}
              ${navItem('tbl:lost_found', icons.search, 'Lost & Found')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Career & Finance</div>
              ${navItem('tbl:job_postings', icons.clipboard, 'Job Postings')}
              ${navItem('tbl:internships', icons.clipboard, 'Internships')}
              ${navItem('tbl:scholarships', icons.award, 'Scholarships')}
              ${navItem('tbl:financial_aid_applications', icons.clipboard, 'Financial Aid')}
              ${navItem('tbl:payments', icons.activity, 'Payments')}
              ${navItem('tbl:student_budgets', icons.clipboard, 'Budgets')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Facilities</div>
              ${navItem('tbl:buildings', icons.home, 'Buildings')}
              ${navItem('tbl:rooms', icons.grid, 'Rooms')}
              ${navItem('tbl:room_bookings', icons.calendar, 'Room Bookings')}
              ${navItem('tbl:equipment', icons.settings, 'Equipment')}
              ${navItem('tbl:parking_permits', icons.shield, 'Parking')}
              ${navItem('tbl:maintenance_requests', icons.settings, 'Maintenance')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Health & Wellness</div>
              ${navItem('tbl:health_records', icons.activity, 'Health Records')}
              ${navItem('tbl:counseling_appointments', icons.users, 'Counseling')}
              ${navItem('tbl:wellness_checkins', icons.check, 'Wellness Check-ins')}
              ${navItem('tbl:mental_health_resources', icons.activity, 'Mental Health')}
              ${navItem('tbl:gym_memberships', icons.activity, 'Gym')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Communication</div>
              ${navItem('tbl:announcements', icons.bell, 'Announcements')}
              ${navItem('tbl:notifications', icons.bell, 'Notifications')}
              ${navItem('tbl:chat_rooms', icons.activity, 'Chat')}
              ${navItem('tbl:emails', icons.clipboard, 'Email')}
              ${navItem('tbl:calendar_events', icons.calendar, 'Calendar')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Staff & Research</div>
              ${isStaff ? navItem('tbl:staff', icons.users, 'Staff Directory') : ''}
              ${isStaff ? navItem('tbl:teaching_assistants', icons.users, 'Teaching Assistants') : ''}
              ${isStaff ? navItem('tbl:office_hours', icons.calendar, 'Office Hours') : ''}
              ${navItem('tbl:research_projects', icons.book, 'Research')}
              ${navItem('tbl:research_publications', icons.book, 'Publications')}
            </div>
            ` : ''}
            ${state.activeSystem === 'college' ? `
            <div class="nav-section">
              <div class="nav-section-label">Academics</div>
              ${navItem('tbl:enrollments', icons.clipboard, 'Enrollments')}
              ${navItem('tbl:assignments', icons.clipboard, 'Assignments')}
              ${navItem('tbl:timetable_slots', icons.calendar, 'Timetable')}
              ${navItem('tbl:teaching_groups', icons.users, 'Teaching Groups')}
              ${navItem('tbl:academic_years', icons.calendar, 'Academic Years')}
              ${navItem('tbl:markbook_entries', icons.award, 'Markbook')}
              ${navItem('tbl:lesson_plans', icons.book, 'Lesson Plans')}
              ${navItem('tbl:baseline_assessments', icons.award, 'Baseline Assessment')}
              ${navItem('tbl:progress_reports', icons.clipboard, 'Progress Reports')}
              ${navItem('tbl:study_programmes', icons.book, 'Study Programmes')}
              ${navItem('tbl:functional_skills_enrollments', icons.book, 'Functional Skills')}
              ${navItem('tbl:ilp_plans', icons.clipboard, 'ILPs')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Exams & Qualifications</div>
              ${navItem('tbl:exam_entries', icons.clipboard, 'Exam Entries')}
              ${navItem('tbl:exam_results', icons.award, 'Exam Results')}
              ${navItem('tbl:exam_timetable', icons.calendar, 'Exam Timetable')}
              ${navItem('tbl:tlevel_enrollments', icons.book, 'T-Levels')}
              ${navItem('tbl:apprenticeship_enrollments', icons.book, 'Apprenticeships')}
              ${navItem('tbl:ucas_applications', icons.clipboard, 'UCAS')}
              ${navItem('tbl:value_added_predictions', icons.activity, 'Value Added')}
              ${navItem('tbl:iv_plans', icons.check, 'Internal Verification')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Pastoral & Welfare</div>
              ${navItem('tbl:behaviour_records', icons.shield, 'Behaviour')}
              ${navItem('tbl:pastoral_notes', icons.clipboard, 'Pastoral Notes')}
              ${navItem('tbl:safeguarding_concerns', icons.shield, 'Safeguarding')}
              ${navItem('tbl:send_records', icons.users, 'SEND')}
              ${navItem('tbl:wellbeing_referrals', icons.activity, 'Student Wellbeing')}
              ${navItem('tbl:counselling_sessions', icons.users, 'Counselling')}
              ${navItem('tbl:disciplinary_cases', icons.shield, 'Disciplinary')}
              ${navItem('tbl:complaints', icons.clipboard, 'Complaints')}
              ${navItem('tbl:prevent_referrals', icons.shield, 'Prevent Duty')}
              ${navItem('tbl:early_warning_alerts', icons.bell, 'Early Warning')}
              ${navItem('tbl:first_aid_incidents', icons.activity, 'First Aid')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Student Services</div>
              ${navItem('tbl:applications', icons.clipboard, 'Admissions')}
              ${navItem('tbl:bursary_records', icons.award, 'Bursary')}
              ${navItem('tbl:careers_activities', icons.clipboard, 'Careers')}
              ${navItem('tbl:destinations', icons.clipboard, 'Destinations')}
              ${navItem('tbl:enrichment_activities', icons.activity, 'Enrichment')}
              ${navItem('tbl:library_items', icons.book, 'Library')}
              ${navItem('tbl:meal_orders', icons.activity, 'Meal Ordering')}
              ${navItem('tbl:transport_records', icons.activity, 'Transport')}
              ${navItem('tbl:todo_items', icons.check, 'Todo')}
              ${navItem('tbl:portfolio_items', icons.layers, 'Portfolio')}
              ${navItem('tbl:skills_passport', icons.award, 'Skills Passport')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Parents & Communication</div>
              ${navItem('tbl:parent_links', icons.users, 'Parent Portal')}
              ${navItem('tbl:parents_evenings', icons.calendar, 'Parents Evenings')}
              ${navItem('tbl:announcements', icons.bell, 'Announcements')}
              ${navItem('tbl:notifications', icons.bell, 'Notifications')}
              ${navItem('tbl:messages', icons.clipboard, 'Messages')}
              ${navItem('tbl:calendar_events', icons.calendar, 'Calendar')}
              ${navItem('tbl:forum_threads', icons.users, 'Forums')}
              ${navItem('tbl:surveys', icons.clipboard, 'Surveys')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Staff & HR</div>
              ${isStaff ? navItem('tbl:staff', icons.users, 'Staff Directory') : ''}
              ${isStaff ? navItem('tbl:staff_hr', icons.users, 'Staff HR') : ''}
              ${isStaff ? navItem('tbl:staff_absences', icons.calendar, 'Staff Absence') : ''}
              ${isStaff ? navItem('tbl:cover_arrangements', icons.calendar, 'Cover') : ''}
              ${isStaff ? navItem('tbl:cpd_records', icons.book, 'CPD') : ''}
              ${isStaff ? navItem('tbl:appraisals', icons.award, 'Appraisals') : ''}
              ${isStaff ? navItem('tbl:teaching_observations', icons.eye, 'Observations') : ''}
              ${isStaff ? navItem('tbl:wellbeing_checkins', icons.activity, 'Staff Wellbeing') : ''}
              ${isStaff ? navItem('tbl:job_vacancies', icons.clipboard, 'Recruitment') : ''}
              ${isStaff ? navItem('tbl:tutor_assignments', icons.users, 'Tutorials') : ''}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Finance</div>
              ${navItem('tbl:payments', icons.activity, 'Payments')}
              ${navItem('tbl:invoices', icons.clipboard, 'Invoices')}
              ${navItem('tbl:expense_claims', icons.clipboard, 'Expense Claims')}
              ${navItem('tbl:funding_records', icons.award, 'Funding')}
              ${navItem('tbl:print_accounts', icons.clipboard, 'Print Credits')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Facilities</div>
              ${navItem('tbl:rooms', icons.grid, 'Rooms')}
              ${navItem('tbl:resource_bookings', icons.calendar, 'Resource Bookings')}
              ${navItem('tbl:asset_loans', icons.settings, 'Assets')}
              ${navItem('tbl:lettings_bookings', icons.calendar, 'Lettings')}
              ${navItem('tbl:visitors', icons.users, 'Visitors')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Compliance & Quality</div>
              ${isStaff ? navItem('tbl:quality_reviews', icons.check, 'Quality Assurance') : ''}
              ${isStaff ? navItem('tbl:compliance_checks', icons.shield, 'Compliance') : ''}
              ${isStaff ? navItem('tbl:dbs_checks', icons.shield, 'DBS Checks') : ''}
              ${isStaff ? navItem('tbl:hs_incidents', icons.shield, 'Health & Safety') : ''}
              ${isStaff ? navItem('tbl:risk_register', icons.shield, 'Risk Management') : ''}
              ${isStaff ? navItem('tbl:equality_impact_assessments', icons.check, 'Equality & Diversity') : ''}
              ${isStaff ? navItem('tbl:governors', icons.users, 'Governance') : ''}
              ${isStaff ? navItem('tbl:sef_sections', icons.clipboard, 'Self Assessment') : ''}
              ${isStaff ? navItem('tbl:policies', icons.clipboard, 'Policies') : ''}
              ${isStaff ? navItem('tbl:audit_log', icons.eye, 'Audit Log') : ''}
            </div>
            ` : ''}
            ${state.activeSystem === 'school' ? `
            <div class="nav-section">
              <div class="nav-section-label">Overview</div>
              ${navItem('sec:dashboard', icons.home, 'Dashboard')}
              ${isStaff ? navItem('sec:students', icons.users, 'Students') : ''}
              ${navItem('sec:subjects', icons.book, 'Subjects')}
              ${navItem('sec:grades', icons.award, 'Grades')}
              ${navItem('sec:attendance', icons.check, 'Attendance')}
              ${navItem('sec:timetable', icons.calendar, 'Timetable')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Pastoral Care</div>
              ${navItem('sec:behaviour', icons.shield, 'Behaviour')}
              ${navItem('sec:detentions', icons.shield, 'Detentions')}
              ${navItem('sec:pastoral', icons.clipboard, 'Pastoral Notes')}
              ${navItem('sec:safeguarding', icons.shield, 'Safeguarding')}
              ${navItem('sec:send', icons.users, 'SEND')}
              ${navItem('sec:form_groups', icons.users, 'Form Groups')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Curriculum</div>
              ${navItem('sec:homework', icons.book, 'Homework')}
              ${navItem('sec:exams', icons.clipboard, 'Exams')}
              ${navItem('sec:parents_evening', icons.calendar, 'Parents Evening')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Academics (Tables)</div>
              ${navItem('tbl:enrollments', icons.clipboard, 'Enrollments')}
              ${navItem('tbl:exam_results', icons.award, 'Exam Results')}
              ${navItem('tbl:homework_submissions', icons.check, 'Submissions')}
              ${navItem('tbl:progress_targets', icons.activity, 'Progress Targets')}
              ${navItem('tbl:intervention_groups', icons.users, 'Interventions')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Student Life</div>
              ${navItem('tbl:clubs', icons.users, 'Clubs')}
              ${navItem('tbl:trips', icons.activity, 'Trips')}
              ${navItem('tbl:careers_records', icons.clipboard, 'Careers')}
              ${navItem('tbl:work_experience', icons.clipboard, 'Work Experience')}
              ${navItem('tbl:library_books', icons.book, 'Library')}
              ${navItem('tbl:library_loans', icons.book, 'Library Loans')}
              ${navItem('tbl:meal_registrations', icons.activity, 'Meals')}
              ${navItem('tbl:medical_conditions', icons.activity, 'Medical')}
              ${navItem('tbl:first_aid_log', icons.activity, 'First Aid')}
              ${navItem('tbl:consent_records', icons.check, 'Consent')}
              ${navItem('tbl:transport_routes', icons.activity, 'Transport')}
              ${navItem('tbl:exclusions', icons.shield, 'Exclusions')}
              ${navItem('tbl:rewards', icons.award, 'Rewards')}
              ${navItem('tbl:house_points', icons.award, 'House Points')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Communication</div>
              ${navItem('tbl:announcements', icons.bell, 'Announcements')}
              ${navItem('tbl:notifications', icons.bell, 'Notifications')}
              ${navItem('tbl:emails', icons.clipboard, 'Email')}
              ${navItem('tbl:school_events', icons.calendar, 'Calendar')}
              ${navItem('tbl:communication_log', icons.clipboard, 'Communication Log')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Staff & HR</div>
              ${isStaff ? navItem('tbl:staff', icons.users, 'Staff Directory') : ''}
              ${isStaff ? navItem('tbl:staff_hr', icons.users, 'Staff HR') : ''}
              ${isStaff ? navItem('tbl:staff_leave', icons.calendar, 'Staff Leave') : ''}
              ${isStaff ? navItem('tbl:cover_lessons', icons.calendar, 'Cover') : ''}
              ${isStaff ? navItem('tbl:cpd_records', icons.book, 'CPD') : ''}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Facilities</div>
              ${navItem('tbl:room_bookings', icons.calendar, 'Room Bookings')}
              ${navItem('tbl:assets', icons.settings, 'Assets')}
              ${navItem('tbl:visitors', icons.users, 'Visitors')}
              ${navItem('tbl:incidents', icons.shield, 'Incidents')}
              ${navItem('tbl:seating_plans', icons.grid, 'Seating Plans')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Finance</div>
              ${navItem('tbl:finance_transactions', icons.activity, 'Transactions')}
              ${navItem('tbl:finance_budgets', icons.clipboard, 'Budgets')}
            </div>
            ` : ''}
            ${state.activeSystem === 'primary' ? `
            <div class="nav-section">
              <div class="nav-section-label">Overview</div>
              ${navItem('pri:dashboard', icons.home, 'Dashboard')}
              ${isStaff ? navItem('pri:pupils', icons.users, 'Pupils') : ''}
              ${navItem('pri:classes', icons.users, 'Classes')}
              ${navItem('pri:subjects', icons.book, 'Subjects')}
              ${navItem('pri:attendance', icons.check, 'Attendance')}
              ${navItem('pri:timetable', icons.calendar, 'Timetable')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Assessment</div>
              ${navItem('pri:assessment', icons.award, 'Assessment')}
              ${navItem('pri:homework', icons.book, 'Homework')}
              ${navItem('pri:sats', icons.award, 'SATs')}
              ${navItem('pri:phonics', icons.book, 'Phonics')}
              ${navItem('pri:reading_records', icons.book, 'Reading Records')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Pastoral Care</div>
              ${navItem('pri:behaviour', icons.shield, 'Behaviour')}
              ${navItem('pri:rewards', icons.award, 'Rewards')}
              ${navItem('pri:safeguarding', icons.shield, 'Safeguarding')}
              ${navItem('pri:send', icons.users, 'SEND')}
              ${navItem('pri:pastoral', icons.clipboard, 'Pastoral Notes')}
              ${navItem('pri:parents_evening', icons.calendar, 'Parents Evening')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Pupil Life (Tables)</div>
              ${navItem('tbl:clubs', icons.users, 'Clubs')}
              ${navItem('tbl:trips', icons.activity, 'Trips')}
              ${navItem('tbl:library_books', icons.book, 'Library')}
              ${navItem('tbl:library_loans', icons.book, 'Library Loans')}
              ${navItem('tbl:meals', icons.activity, 'Meals')}
              ${navItem('tbl:medical_records', icons.activity, 'Medical')}
              ${navItem('tbl:consent_records', icons.check, 'Consent')}
              ${navItem('tbl:transport', icons.activity, 'Transport')}
              ${navItem('tbl:progress_records', icons.activity, 'Progress')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Communication</div>
              ${navItem('tbl:announcements', icons.bell, 'Announcements')}
              ${navItem('tbl:notifications', icons.bell, 'Notifications')}
              ${navItem('tbl:email_log', icons.clipboard, 'Email')}
              ${navItem('tbl:calendar_events', icons.calendar, 'Calendar')}
              ${navItem('tbl:communication_log', icons.clipboard, 'Communication Log')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Staff & HR</div>
              ${isStaff ? navItem('tbl:staff', icons.users, 'Staff Directory') : ''}
              ${isStaff ? navItem('tbl:staff_hr', icons.users, 'Staff HR') : ''}
              ${isStaff ? navItem('tbl:staff_leave', icons.calendar, 'Staff Leave') : ''}
              ${isStaff ? navItem('tbl:cover_lessons', icons.calendar, 'Cover') : ''}
              ${isStaff ? navItem('tbl:cpd_records', icons.book, 'CPD') : ''}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Facilities</div>
              ${navItem('tbl:room_bookings', icons.calendar, 'Room Bookings')}
              ${navItem('tbl:assets', icons.settings, 'Assets')}
              ${navItem('tbl:visitors', icons.users, 'Visitors')}
              ${navItem('tbl:incidents', icons.shield, 'Incidents')}
            </div>
            <div class="nav-section">
              <div class="nav-section-label">Finance</div>
              ${navItem('tbl:finance_transactions', icons.activity, 'Transactions')}
              ${navItem('tbl:finance_budgets', icons.clipboard, 'Budgets')}
            </div>
            ` : ''}
            ${isStaff ? `
            <div class="nav-section">
              <div class="nav-section-label">Reports</div>
              ${navItem('reports', icons.clipboard, 'Reports')}
            </div>` : ''}
            ${isAdmin ? `
            <div class="nav-section">
              <div class="nav-section-label">Administration</div>
              ${navItem('users', icons.users, 'User Management')}
              ${state.activeSystem === 'university' ? `
              ${navItem('tbl:departments', icons.grid, 'Departments')}
              ${navItem('tbl:security_incidents', icons.shield, 'Security')}
              ${navItem('tbl:documents', icons.clipboard, 'Documents')}
              ${navItem('tbl:audit_log', icons.eye, 'Audit Log')}
              ${navItem('tbl:system_settings', icons.settings, 'System Settings')}
              ` : ''}
              ${state.activeSystem === 'college' ? `
              ${navItem('tbl:departments', icons.grid, 'Departments')}
              ${navItem('tbl:documents', icons.clipboard, 'Documents')}
              ${navItem('tbl:data_subjects', icons.shield, 'GDPR')}
              ${navItem('tbl:system_settings', icons.settings, 'System Settings')}
              ${navItem('tbl:onboarding_checklists', icons.check, 'Onboarding')}
              ${navItem('tbl:marketing_campaigns', icons.activity, 'Marketing')}
              ${navItem('tbl:alumni_records', icons.users, 'Alumni')}
              ${navItem('tbl:council_members', icons.users, 'Student Council')}
              ${navItem('tbl:portal_pages', icons.layers, 'Student Portal')}
              ${navItem('tbl:letter_templates', icons.clipboard, 'Letter Templates')}
              ${navItem('tbl:export_jobs', icons.archive, 'Data Export')}
              ` : ''}
              ${state.activeSystem === 'school' ? `
              ${navItem('tbl:admissions_applications', icons.clipboard, 'Admissions')}
              ${navItem('tbl:documents', icons.clipboard, 'Documents')}
              ${navItem('tbl:policies', icons.clipboard, 'Policies')}
              ${navItem('tbl:school_settings', icons.settings, 'Settings')}
              ${navItem('tbl:audit_log', icons.eye, 'Audit Log')}
              ` : ''}
              ${state.activeSystem === 'primary' ? `
              ${navItem('tbl:admissions', icons.clipboard, 'Admissions')}
              ${navItem('tbl:documents', icons.clipboard, 'Documents')}
              ${navItem('tbl:policies', icons.clipboard, 'Policies')}
              ${navItem('tbl:settings', icons.settings, 'Settings')}
              ${navItem('tbl:audit_log', icons.eye, 'Audit Log')}
              ` : ''}
              ${navItem('sessions', icons.eye, 'Active Sessions')}
              ${navItem('browse_tables', icons.database, 'Browse All Tables')}
            </div>` : ''}
            <div class="nav-section">
              <div class="nav-section-label">Account</div>
              ${navItem('settings', icons.settings, 'Settings')}
            </div>
          </nav>
          <div class="sidebar-footer">
            <div class="user-info">
              <div class="user-avatar">${(state.user.display_name || state.user.username || "?")[0].toUpperCase()}</div>
              <div class="user-details">
                <div class="name">${esc(state.user.display_name || state.user.username)}</div>
                <div class="role">${esc(role)}</div>
              </div>
            </div>
          </div>
        </aside>
        <div class="main">
          <header class="topbar">
            <div class="topbar-left">
              <button class="mobile-toggle" id="mobile-toggle">${icons.menu}</button>
              <h1 id="page-title">Dashboard</h1>
            </div>
            <div class="topbar-actions">
              <span class="system-badge">${esc(sys.label)}</span>
              ${isSuperadmin() ? `<button class="btn btn-outline btn-sm" id="back-superadmin">${icons.shield} Admin Dashboard</button>` : ''}
              <button class="btn btn-outline btn-sm" id="switch-system">${icons.grid} Switch</button>
              <button class="btn btn-outline btn-sm" id="logout-btn">${icons.logout} Sign Out</button>
            </div>
          </header>
          <div class="content" id="page-content">
            <div class="loader"><div class="spinner"></div></div>
          </div>
        </div>
      </div>`;

    // Event listeners
    document.querySelectorAll(".nav-item[data-page]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        currentPage = el.dataset.page;
        renderApp();
      });
    });
    document.getElementById("switch-system").addEventListener("click", () => {
      state.activeSystem = null;
      localStorage.removeItem("edu_active_system");
      currentPage = "dashboard";
      render();
    });
    document.getElementById("logout-btn").addEventListener("click", () => { clearAuth(); currentPage = "dashboard"; render(); });
    document.getElementById("mobile-toggle").addEventListener("click", () => {
      document.getElementById("sidebar").classList.toggle("open");
    });

    // Back to superadmin dashboard button
    const backBtn = document.getElementById("back-superadmin");
    if (backBtn) {
      backBtn.addEventListener("click", () => {
        setActiveSystem("__superadmin__");
        currentPage = "dashboard";
        saCurrentPage = "dashboard";
        render();
      });
    }

    // Load page content
    loadPage(currentPage);
  }

  function getUserRole() {
    if (!state.user || !state.user.systems) return "student";
    const sys = state.user.systems.find((s) => s.system_key === state.activeSystem);
    return sys ? sys.role : "student";
  }

  // ── Page Loader ──────────────────────────────────────────────────
  async function loadPage(page) {
    stopSessionRefresh();
    const content = document.getElementById("page-content");
    const title = document.getElementById("page-title");
    const titles = {
      dashboard: "Dashboard",
      students: state.activeSystem === "primary" ? "Pupils" : "Students",
      courses: "Courses",
      attendance: "Attendance",
      grades: "Grades",
      reports: "Reports",
      users: "User Management",
      sessions: "Active Sessions",
      settings: "Account Settings",
      browse_tables: "Browse All Tables",
    };
    if (page.startsWith("tbl:")) {
      title.textContent = page.slice(4).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    } else if (page.startsWith("sec:") || page.startsWith("pri:")) {
      const prefix = page.startsWith("sec:") ? "sec:" : "pri:";
      const pageTitles = {
        "sec:dashboard": "Secondary School Dashboard",
        "sec:students": "Students",
        "sec:subjects": "Subjects",
        "sec:grades": "Grades",
        "sec:attendance": "Attendance",
        "sec:timetable": "Timetable",
        "sec:behaviour": "Behaviour Records",
        "sec:detentions": "Detentions",
        "sec:pastoral": "Pastoral Notes",
        "sec:safeguarding": "Safeguarding Concerns",
        "sec:send": "SEND Records",
        "sec:form_groups": "Form Groups",
        "sec:homework": "Homework",
        "sec:exams": "Exams",
        "sec:parents_evening": "Parents Evening",
        "pri:dashboard": "Primary School Dashboard",
        "pri:pupils": "Pupils",
        "pri:classes": "Classes",
        "pri:subjects": "Subjects",
        "pri:assessment": "Assessment",
        "pri:attendance": "Attendance",
        "pri:timetable": "Timetable",
        "pri:homework": "Homework",
        "pri:sats": "SATs Results",
        "pri:phonics": "Phonics Screening",
        "pri:reading_records": "Reading Records",
        "pri:behaviour": "Behaviour Records",
        "pri:rewards": "Rewards",
        "pri:safeguarding": "Safeguarding Concerns",
        "pri:send": "SEND Records",
        "pri:pastoral": "Pastoral Notes",
        "pri:parents_evening": "Parents Evening",
      };
      title.textContent = pageTitles[page] || page.slice(4).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    } else {
      title.textContent = titles[page] || "Dashboard";
    }

    content.innerHTML = '<div class="loader"><div class="spinner"></div></div>';

    try {
      if (page.startsWith("tbl:")) {
        _genericTablePage = 1;
        await loadGenericTable(page.slice(4), content);
      } else if (page.startsWith("sec:")) {
        await loadSecondaryPage(page.slice(4), content);
      } else if (page.startsWith("pri:")) {
        await loadPrimaryPage(page.slice(4), content);
      } else {
        switch (page) {
          case "dashboard": await loadDashboard(content); break;
          case "students": await loadStudents(content); break;
          case "courses": await loadCourses(content); break;
          case "attendance": await loadAttendance(content); break;
          case "grades": await loadGrades(content); break;
          case "reports": await loadReports(content); break;
          case "users": await loadUsers(content); break;
          case "sessions": await loadSASessions(content); break;
          case "settings": loadSettings(content); break;
          case "browse_tables": await loadBrowseTables(content); break;
          default: content.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F4CB}</div><p>Page not found</p></div>';
        }
      }
    } catch (err) {
      content.innerHTML = `<div class="alert alert-error">Failed to load data: ${esc(err.message)}</div>`;
    }
  }

  // ── Secondary & Primary module page dispatchers ─────────────────

  async function loadSecondaryPage(subPage, el) {
    if (typeof SecondaryModule === "undefined") {
      el.innerHTML = '<div class="alert alert-error">Secondary module not loaded. Check that secondary.js is included.</div>';
      return;
    }
    const map = {
      dashboard:      SecondaryModule.renderSecondaryDashboard,
      students:       SecondaryModule.renderStudentsPage,
      subjects:       SecondaryModule.renderSubjectsPage,
      grades:         SecondaryModule.renderGradesPage,
      attendance:     SecondaryModule.renderAttendancePage,
      timetable:      SecondaryModule.renderTimetablePage,
      behaviour:      SecondaryModule.renderBehaviourPage,
      detentions:     SecondaryModule.renderDetentionsPage,
      pastoral:       SecondaryModule.renderPastoralPage,
      safeguarding:   SecondaryModule.renderSafeguardingPage,
      send:           SecondaryModule.renderSENDPage,
      form_groups:    SecondaryModule.renderFormGroupsPage,
      homework:       SecondaryModule.renderHomeworkPage,
      exams:          SecondaryModule.renderExamsPage,
      parents_evening: SecondaryModule.renderParentsEveningPage,
    };
    const fn = map[subPage];
    if (fn) {
      await fn(el);
      // Wire any quick-link sc-nav-link elements rendered by dashboard
      el.querySelectorAll(".sc-nav-link[data-page]").forEach((a) => {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          currentPage = a.dataset.page;
          renderApp();
        });
      });
    } else {
      el.innerHTML = `<div class="empty-state"><div class="empty-icon">&#128203;</div><p>Page "${esc(subPage)}" not found.</p></div>`;
    }
  }

  async function loadPrimaryPage(subPage, el) {
    if (typeof PrimaryModule === "undefined") {
      el.innerHTML = '<div class="alert alert-error">Primary module not loaded. Check that primary.js is included.</div>';
      return;
    }
    const map = {
      dashboard:       PrimaryModule.renderPrimaryDashboard,
      pupils:          PrimaryModule.renderPupilsPage,
      classes:         PrimaryModule.renderClassesPage,
      subjects:        PrimaryModule.renderSubjectsPage,
      assessment:      PrimaryModule.renderAssessmentPage,
      attendance:      PrimaryModule.renderAttendancePage,
      timetable:       PrimaryModule.renderTimetablePage,
      homework:        PrimaryModule.renderHomeworkPage,
      sats:            PrimaryModule.renderSATsPage,
      phonics:         PrimaryModule.renderPhonicsPage,
      reading_records: PrimaryModule.renderReadingRecordsPage,
      behaviour:       PrimaryModule.renderBehaviourPage,
      rewards:         PrimaryModule.renderRewardsPage,
      safeguarding:    PrimaryModule.renderSafeguardingPage,
      send:            PrimaryModule.renderSENDPage,
      pastoral:        PrimaryModule.renderPastoralPage,
      parents_evening: PrimaryModule.renderParentsEveningPage,
    };
    const fn = map[subPage];
    if (fn) {
      await fn(el);
      // Wire any quick-link sc-nav-link elements rendered by dashboard
      el.querySelectorAll(".sc-nav-link[data-page]").forEach((a) => {
        a.addEventListener("click", (e) => {
          e.preventDefault();
          currentPage = a.dataset.page;
          renderApp();
        });
      });
    } else {
      el.innerHTML = `<div class="empty-state"><div class="empty-icon">&#128203;</div><p>Page "${esc(subPage)}" not found.</p></div>`;
    }
  }

  // ── Dashboard ────────────────────────────────────────────────────
  async function loadDashboard(el) {
    const res = await apiFetch(`/web/dashboard/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load dashboard")}</div>`;
      return;
    }

    const role = getUserRole();
    const isStaff = role === "admin" || role === "staff" || role === "teacher";

    el.innerHTML = `
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_students || 0}</div>
            <div class="stat-label">${state.activeSystem === 'primary' ? 'Pupils' : 'Students'}</div></div>
            <div class="stat-icon blue">${icons.users}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_courses || 0}</div>
            <div class="stat-label">Courses</div></div>
            <div class="stat-icon purple">${icons.book}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.attendance_rate != null ? d.attendance_rate + '%' : 'N/A'}</div>
            <div class="stat-label">Attendance Rate</div></div>
            <div class="stat-icon green">${icons.check}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_grades || 0}</div>
            <div class="stat-label">Assessments</div></div>
            <div class="stat-icon amber">${icons.award}</div>
          </div>
        </div>
      </div>

      <div class="chart-grid">
        <div class="section">
          <div class="section-header"><h2>Attendance Overview</h2></div>
          ${renderAttendanceBars(d.attendance_breakdown || {})}
        </div>
        <div class="section">
          <div class="section-header"><h2>Quick Actions</h2></div>
          <div class="quick-actions">
            ${isStaff ? `<a class="quick-action" data-page="students"><div class="qa-icon">${icons.users}</div><div class="qa-label">View ${state.activeSystem === 'primary' ? 'Pupils' : 'Students'}</div></a>` : ''}
            <a class="quick-action" data-page="courses"><div class="qa-icon">${icons.book}</div><div class="qa-label">Courses</div></a>
            <a class="quick-action" data-page="attendance"><div class="qa-icon">${icons.check}</div><div class="qa-label">Attendance</div></a>
            <a class="quick-action" data-page="grades"><div class="qa-icon">${icons.award}</div><div class="qa-label">Grades</div></a>
            ${isStaff ? `<a class="quick-action" data-page="reports"><div class="qa-icon">${icons.clipboard}</div><div class="qa-label">Reports</div></a>` : ''}
          </div>
        </div>
      </div>

      ${d.recent_enrollments && d.recent_enrollments.length ? `
      <div class="section">
        <div class="section-header"><h2>Recent Enrollments</h2></div>
        <table class="data-table">
          <tr><th>Student</th><th>Course</th><th>Date</th><th>Status</th></tr>
          ${d.recent_enrollments.map((r) => `
            <tr>
              <td>${esc(r.student_name || r.student_id || '-')}</td>
              <td>${esc(r.course_name || r.course_code || '-')}</td>
              <td>${esc(r.enrollment_date || r.date || '-')}</td>
              <td><span class="badge badge-${r.status === 'active' ? 'success' : 'neutral'}">${esc(r.status || 'active')}</span></td>
            </tr>`).join("")}
        </table>
      </div>` : ''}`;

    // Set dynamic widths on chart bar fills
    el.querySelectorAll(".fill[data-width]").forEach((bar) => {
      bar.style.width = bar.dataset.width + "%";
    });

    // Bind quick action clicks
    el.querySelectorAll(".quick-action[data-page]").forEach((qa) => {
      qa.addEventListener("click", (e) => {
        e.preventDefault();
        currentPage = qa.dataset.page;
        renderApp();
      });
    });
  }

  function renderAttendanceBars(breakdown) {
    const total = Object.values(breakdown).reduce((a, b) => a + b, 0) || 1;
    const items = [
      { label: "Present", key: "present", cls: "green" },
      { label: "Late", key: "late", cls: "amber" },
      { label: "Absent", key: "absent", cls: "red" },
    ];
    return items.map((it) => {
      const count = (breakdown[it.key] || 0) + (breakdown[it.key.charAt(0).toUpperCase() + it.key.slice(1)] || 0);
      const pct = Math.round((count / total) * 100);
      return `<div class="att-bar-row">
        <div class="att-bar-header">
          <span>${it.label}</span><span class="att-bar-count">${count} (${pct}%)</span>
        </div>
        <div class="chart-bar"><div class="fill ${it.cls}" data-width="${pct}"></div></div>
      </div>`;
    }).join("");
  }

  // ── Students Page ────────────────────────────────────────────────
  async function loadStudents(el) {
    const res = await apiFetch(`/web/students/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!d.students || !d.students.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F464}</div><p>No student records found.</p></div>';
      return;
    }

    el.innerHTML = `
      <div class="page-header">
        <h1>${d.students.length} ${state.activeSystem === 'primary' ? 'Pupils' : 'Students'}</h1>
        <div class="search-box">
          ${icons.search}
          <input id="student-search" placeholder="Search students..." type="text">
        </div>
      </div>
      <div class="section">
        <table class="data-table" id="student-table">
          <thead><tr><th>ID</th><th>Name</th><th>Email</th><th>Year / Group</th><th>Status</th></tr></thead>
          <tbody>
            ${d.students.map((s) => `
              <tr>
                <td><strong>${esc(s.student_id || s.id || '-')}</strong></td>
                <td>${esc(s.name || ((s.first_name || '') + ' ' + (s.last_name || '')).trim() || '-')}</td>
                <td>${esc(s.email || '-')}</td>
                <td>${esc(s.year_group || s.year || s.class_name || '-')}</td>
                <td><span class="badge badge-${s.status === 'active' || s.status === 'Active' ? 'success' : 'neutral'}">${esc(s.status || 'active')}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    document.getElementById("student-search").addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll("#student-table tbody tr").forEach((row) => {
        row.classList.toggle("sa-hidden", !row.textContent.toLowerCase().includes(q));
      });
    });
  }

  // ── Courses Page ─────────────────────────────────────────────────
  async function loadCourses(el) {
    const res = await apiFetch(`/web/courses/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!d.courses || !d.courses.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F4DA}</div><p>No courses found.</p></div>';
      return;
    }

    el.innerHTML = `
      <div class="page-header">
        <h1>${d.courses.length} Courses</h1>
      </div>
      <div class="section">
        <table class="data-table">
          <thead><tr><th>Code</th><th>Name</th><th>Department</th><th>Credits</th><th>Status</th></tr></thead>
          <tbody>
            ${d.courses.map((c) => `
              <tr>
                <td><strong>${esc(c.course_code || c.code || c.id || '-')}</strong></td>
                <td>${esc(c.course_name || c.name || c.title || '-')}</td>
                <td>${esc(c.department || c.subject || '-')}</td>
                <td>${esc(c.credits || c.credit_hours || '-')}</td>
                <td><span class="badge badge-${c.status === 'active' || c.status === 'Active' || !c.status ? 'success' : 'neutral'}">${esc(c.status || 'active')}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // ── Attendance Page ──────────────────────────────────────────────
  async function loadAttendance(el) {
    const res = await apiFetch(`/web/attendance/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!d.records || !d.records.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">\u2705</div><p>No attendance records found.</p></div>';
      return;
    }

    el.innerHTML = `
      <div class="page-header">
        <h1>Attendance Records</h1>
      </div>
      <div class="section">
        <table class="data-table">
          <thead><tr><th>Date</th><th>Student</th><th>Course</th><th>Status</th></tr></thead>
          <tbody>
            ${d.records.map((r) => {
              const statusCls = (r.status || '').toLowerCase();
              const badge = statusCls.includes('present') ? 'success' : statusCls.includes('late') ? 'warning' : 'danger';
              return `<tr>
                <td>${esc(r.date || '-')}</td>
                <td>${esc(r.student_name || r.student_id || '-')}</td>
                <td>${esc(r.course_name || r.course_code || '-')}</td>
                <td><span class="badge badge-${badge}">${esc(r.status || '-')}</span></td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // ── Grades Page ──────────────────────────────────────────────────
  async function loadGrades(el) {
    const res = await apiFetch(`/web/grades/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!d.grades || !d.grades.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F3C6}</div><p>No grade records found.</p></div>';
      return;
    }

    el.innerHTML = `
      <div class="page-header">
        <h1>Grades</h1>
      </div>
      <div class="section">
        <table class="data-table">
          <thead><tr><th>Student</th><th>Course</th><th>Type</th><th>Grade</th><th>Date</th></tr></thead>
          <tbody>
            ${d.grades.map((g) => `
              <tr>
                <td>${esc(g.student_name || g.student_id || '-')}</td>
                <td>${esc(g.course_name || g.course_code || '-')}</td>
                <td>${esc(g.assessment_type || g.type || '-')}</td>
                <td><strong>${esc(g.grade || g.score || '-')}</strong></td>
                <td>${esc(g.date || g.graded_at || '-')}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  // ── Reports Page ─────────────────────────────────────────────────
  async function loadReports(el) {
    const res = await apiFetch(`/web/reports/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    el.innerHTML = `
      <div class="page-header"><h1>Reports Summary</h1></div>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_students || 0}</div><div class="stat-label">Total ${state.activeSystem === 'primary' ? 'Pupils' : 'Students'}</div></div>
            <div class="stat-icon blue">${icons.users}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_enrollments || 0}</div><div class="stat-label">Active Enrollments</div></div>
            <div class="stat-icon purple">${icons.clipboard}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.attendance_rate != null ? d.attendance_rate + '%' : 'N/A'}</div><div class="stat-label">Attendance Rate</div></div>
            <div class="stat-icon green">${icons.check}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-header">
            <div><div class="stat-value">${d.total_grades || 0}</div><div class="stat-label">Total Grades</div></div>
            <div class="stat-icon amber">${icons.award}</div>
          </div>
        </div>
      </div>
      ${d.grade_distribution && d.grade_distribution.length ? `
      <div class="section">
        <div class="section-header"><h2>Grade Distribution</h2></div>
        <table class="data-table">
          <thead><tr><th>Grade</th><th>Count</th></tr></thead>
          <tbody>${d.grade_distribution.map((g) => `<tr><td><strong>${esc(g.grade)}</strong></td><td>${g.count}</td></tr>`).join("")}</tbody>
        </table>
      </div>` : ''}
      ${d.attendance_by_status && d.attendance_by_status.length ? `
      <div class="section">
        <div class="section-header"><h2>Attendance by Status</h2></div>
        <table class="data-table">
          <thead><tr><th>Status</th><th>Count</th></tr></thead>
          <tbody>${d.attendance_by_status.map((a) => `<tr><td>${esc(a.status)}</td><td>${a.count}</td></tr>`).join("")}</tbody>
        </table>
      </div>` : ''}`;
  }

  // ── Users Page (Admin) ───────────────────────────────────────────
  async function loadUsers(el) {
    const res = await apiFetch(`/web/users`);
    if (!res) return;
    const d = await res.json();

    if (!d.users || !d.users.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">\u{1F465}</div><p>No users found.</p></div>';
      return;
    }

    el.innerHTML = `
      <div class="page-header">
        <h1>${d.users.length} Users</h1>
        <div class="search-box">
          ${icons.search}
          <input id="user-search" placeholder="Search users..." type="text">
        </div>
      </div>
      <div class="section">
        <table class="data-table" id="user-table">
          <thead><tr><th>Username</th><th>Display Name</th><th>Email</th><th>Systems</th><th>Status</th></tr></thead>
          <tbody>
            ${d.users.map((u) => `
              <tr>
                <td><strong>${esc(u.username)}</strong></td>
                <td>${esc(u.display_name || '-')}</td>
                <td>${esc(u.email || '-')}</td>
                <td>${(u.systems || []).map((s) =>
                  `<span class="badge badge-info badge-spaced">${esc(s.system_key)}:${esc(s.role)}</span>`
                ).join("")}</td>
                <td><span class="badge badge-${u.is_active ? 'success' : 'danger'}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    document.getElementById("user-search").addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll("#user-table tbody tr").forEach((row) => {
        row.classList.toggle("sa-hidden", !row.textContent.toLowerCase().includes(q));
      });
    });
  }

  // ── Generic Table Page ──────────────────────────────────────────
  async function loadGenericTable(tableName, el) {
    const res = await apiFetch(`/web/table/${tableName}/${state.activeSystem}?page=${_genericTablePage}`);
    if (!res) return;
    const d = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load data")}</div>`;
      return;
    }

    const prettyName = tableName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    const cols = d.columns || [];
    const rows = d.rows || [];
    const displayCols = cols.slice(0, 10);

    el.innerHTML = `
      <div class="page-header">
        <h1>${esc(prettyName)} (${d.total || 0} records)</h1>
        <div class="search-box">
          ${icons.search}
          <input id="gen-search" placeholder="Search ${esc(prettyName)}..." type="text">
        </div>
      </div>
      ${d.pages > 1 ? `<div class="pagination" style="margin-bottom:12px; display:flex; gap:8px; align-items:center;">
        ${d.page > 1 ? `<button class="btn btn-outline btn-sm" id="gen-prev">Previous</button>` : ''}
        <span>Page ${d.page} of ${d.pages}</span>
        ${d.page < d.pages ? `<button class="btn btn-outline btn-sm" id="gen-next">Next</button>` : ''}
      </div>` : ''}
      <div class="section" style="overflow-x:auto;">
        <table class="data-table" id="gen-table">
          <thead><tr>${displayCols.map(c => `<th>${esc(c)}</th>`).join("")}</tr></thead>
          <tbody>
            ${rows.length === 0 ? `<tr><td colspan="${displayCols.length}" style="text-align:center">No records</td></tr>` :
              rows.map(r => `<tr>${displayCols.map(c => {
                const v = r[c];
                const s = v === null || v === undefined ? '-' : String(v);
                return `<td>${esc(s.length > 80 ? s.slice(0, 80) + '...' : s)}</td>`;
              }).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>`;

    // Client-side search filter
    const searchEl = document.getElementById("gen-search");
    if (searchEl) {
      searchEl.addEventListener("input", (e) => {
        const q = e.target.value.toLowerCase();
        document.querySelectorAll("#gen-table tbody tr").forEach((row) => {
          row.classList.toggle("sa-hidden", !row.textContent.toLowerCase().includes(q));
        });
      });
    }

    // Pagination
    const prevBtn = document.getElementById("gen-prev");
    if (prevBtn) prevBtn.addEventListener("click", () => { loadGenericTablePage(tableName, el, d.page - 1); });
    const nextBtn = document.getElementById("gen-next");
    if (nextBtn) nextBtn.addEventListener("click", () => { loadGenericTablePage(tableName, el, d.page + 1); });
  }

  let _genericTablePage = 1;

  async function loadGenericTablePage(tableName, el, page) {
    _genericTablePage = page;
    await loadGenericTable(tableName, el);
  }

  // ── Browse All Tables Page ────────────────────────────────────────
  async function loadBrowseTables(el) {
    const res = await apiFetch(`/web/tables/${state.activeSystem}`);
    if (!res) return;
    const d = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="alert alert-error">${esc(d.error || "Failed to load tables")}</div>`;
      return;
    }

    const tables = d.tables || [];
    el.innerHTML = `
      <div class="page-header">
        <h1>${tables.length} Tables</h1>
        <div class="search-box">
          ${icons.search}
          <input id="tbl-search" placeholder="Search tables..." type="text">
        </div>
      </div>
      <div class="section">
        <div id="tbl-grid" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:12px;">
          ${tables.map(t => `
            <a class="stat-card table-link" data-table="${esc(t)}" style="cursor:pointer; text-decoration:none;">
              <div class="stat-header">
                <div>
                  <div class="stat-value" style="font-size:14px;">${esc(t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()))}</div>
                  <div class="stat-label" style="font-size:11px;">${esc(t)}</div>
                </div>
                ${icons.database}
              </div>
            </a>`).join("")}
        </div>
      </div>`;

    document.querySelectorAll(".table-link").forEach(link => {
      link.addEventListener("click", () => {
        currentPage = "tbl:" + link.dataset.table;
        renderApp();
      });
    });

    const searchEl = document.getElementById("tbl-search");
    if (searchEl) {
      searchEl.addEventListener("input", (e) => {
        const q = e.target.value.toLowerCase();
        document.querySelectorAll(".table-link").forEach((card) => {
          card.style.display = card.dataset.table.toLowerCase().includes(q) ? "" : "none";
        });
      });
    }
  }

  // ── Settings Page ────────────────────────────────────────────────
  function loadSettings(el) {
    el.innerHTML = `
      <div class="section settings-form">
        <div class="section-header"><h2>Change Password</h2></div>
        <div id="settings-alert"></div>
        <form id="password-form">
          <div class="form-group">
            <label>Current Password</label>
            <input type="password" id="old-password" required>
          </div>
          <div class="form-group">
            <label>New Password</label>
            <input type="password" id="new-password" required minlength="12">
            <small class="settings-password-hint">Minimum 12 characters with uppercase, lowercase, digit, and special character</small>
          </div>
          <div class="form-group">
            <label>Confirm New Password</label>
            <input type="password" id="confirm-password" required>
          </div>
          <button type="submit" class="btn btn-primary settings-submit-btn">Change Password</button>
        </form>
      </div>
      <div class="section settings-account">
        <div class="section-header"><h2>Account Info</h2></div>
        <table class="data-table">
          <tr><td class="sa-fw-bold">Username</td><td>${esc(state.user.username)}</td></tr>
          <tr><td class="sa-fw-bold">Display Name</td><td>${esc(state.user.display_name || '-')}</td></tr>
          <tr><td class="sa-fw-bold">User ID</td><td>${state.user.user_id}</td></tr>
          <tr><td class="sa-fw-bold">Systems</td><td>${(state.user.systems || []).map((s) =>
            `<span class="badge badge-info badge-spaced">${esc(s.system_key)}: ${esc(s.role)}</span>`
          ).join("")}</td></tr>
        </table>
      </div>`;

    document.getElementById("password-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const alertBox = document.getElementById("settings-alert");
      const oldPw = document.getElementById("old-password").value;
      const newPw = document.getElementById("new-password").value;
      const confirm = document.getElementById("confirm-password").value;

      if (newPw !== confirm) {
        alertBox.innerHTML = '<div class="alert alert-error">Passwords do not match.</div>';
        return;
      }

      try {
        const res = await apiFetch("/auth/change-password", {
          method: "POST",
          body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
        });
        const data = await res.json();
        if (!res.ok) {
          alertBox.innerHTML = `<div class="alert alert-error">${esc(data.error)}</div>`;
        } else {
          alertBox.innerHTML = '<div class="alert alert-success">Password changed successfully.</div>';
          document.getElementById("password-form").reset();
        }
      } catch {
        alertBox.innerHTML = '<div class="alert alert-error">Connection error.</div>';
      }
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────
  function esc(s) {
    if (s == null) return "";
    const d = document.createElement("div");
    d.textContent = String(s);
    return d.innerHTML;
  }

  // ── Session heartbeat — detects force-logout ─────────────────────
  let _heartbeatTimer = null;

  function startHeartbeat() {
    stopHeartbeat();
    _heartbeatTimer = setInterval(async () => {
      if (!state.token) return;
      try {
        const res = await fetch(API + "/web/session/heartbeat", {
          headers: { "Authorization": "Bearer " + state.token },
        });
        if (res.status === 401) {
          stopHeartbeat();
          clearAuth();
          render();
          setTimeout(() => {
            const alertBox = document.querySelector(".alert-box");
            if (alertBox) {
              alertBox.innerHTML = '<div class="alert alert-error">Your session was terminated by an administrator.</div>';
            }
          }, 100);
        }
      } catch (_) { /* network error — skip */ }
    }, 5000);
  }

  function stopHeartbeat() {
    if (_heartbeatTimer) { clearInterval(_heartbeatTimer); _heartbeatTimer = null; }
  }

  // ── Expose globals for module scripts (secondary.js, primary.js) ─
  // apiFetch and state are defined inside the IIFE; expose them so
  // module scripts loaded before app.js finishes can call them at
  // runtime (after the IIFE has run).
  window.apiFetch = apiFetch;
  window.state    = state;

  // ── Boot ─────────────────────────────────────────────────────────
  render();
  if (state.token) startHeartbeat();
})();
