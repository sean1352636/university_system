/* Education System — Multi-system Web Portal
 *
 * Shared helpers used by every HTML page in the portal:
 *   - Auth token storage & silent refresh
 *   - API client with 401 retry
 *   - Navigation rendering (top bar + user chip)
 *   - System metadata (icons, labels, routes)
 */
(function (global) {
  "use strict";

  const API_BASE = "/api/v1";
  const STORE = {
    token: "edu_portal_token",
    refresh: "edu_portal_refresh",
    user: "edu_portal_user",
    activeSystem: "edu_portal_active_system",
  };

  const SYSTEMS = [
    {
      key: "university",
      label: "University",
      tagline: "Degrees, research, and campus life",
      icon: "U",
      emoji: "\uD83C\uDF93",
    },
    {
      key: "college",
      label: "Sixth Form College",
      tagline: "16–19 learners: A-levels, T-levels, apprenticeships",
      icon: "C",
      emoji: "\uD83D\uDCDA",
    },
    {
      key: "school",
      label: "Secondary School",
      tagline: "Years 7–11 · KS3/KS4 · GCSE prep",
      icon: "S",
      emoji: "\uD83C\uDFEB",
    },
    {
      key: "primary",
      label: "Primary School",
      tagline: "Reception–Y6 · EYFS/KS1/KS2 · phonics",
      icon: "P",
      emoji: "\uD83C\uDFAE",
    },
    {
      key: "nursery",
      label: "Nursery",
      tagline: "Early years \u00B7 ages 0\u20134 \u00B7 EYFS",
      icon: "N",
      emoji: "\uD83D\uDC76",
    },
  ];

  // Where each system lands after sign-in. All systems currently share the
  // system-aware dashboard (it reads ?system=), but routing through this one
  // helper means a system can later get its own dedicated page without
  // touching the login flow.
  const SYSTEM_ROUTES = {
    // university: "/portal/university/home.html",
  };
  function routeForSystem(key) {
    return SYSTEM_ROUTES[key] || ("/portal/dashboard.html?system=" + encodeURIComponent(key));
  }

  // ── Storage ────────────────────────────────────────────────────────

  function saveAuth(token, refreshToken, user) {
    localStorage.setItem(STORE.token, token);
    localStorage.setItem(STORE.refresh, refreshToken);
    localStorage.setItem(STORE.user, JSON.stringify(user));
  }
  function clearAuth() {
    localStorage.removeItem(STORE.token);
    localStorage.removeItem(STORE.refresh);
    localStorage.removeItem(STORE.user);
    localStorage.removeItem(STORE.activeSystem);
  }
  function getToken()   { return localStorage.getItem(STORE.token); }
  function getRefresh() { return localStorage.getItem(STORE.refresh); }
  function getUser()    {
    try { return JSON.parse(localStorage.getItem(STORE.user) || "null"); }
    catch { return null; }
  }
  function setActiveSystem(key) { if (key) localStorage.setItem(STORE.activeSystem, key); }
  function getActiveSystem() {
    const saved = localStorage.getItem(STORE.activeSystem);
    const user = getUser();
    if (!user) return null;
    const keys = (user.systems || []).map(s => s.system_key);
    if (saved && keys.includes(saved)) return saved;
    return keys[0] || null;
  }

  // ── API client ─────────────────────────────────────────────────────

  async function apiFetch(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const token = getToken();
    if (token && !opts.skipAuth) headers["Authorization"] = "Bearer " + token;

    const res = await fetch(API_BASE + path, {
      method: opts.method || "GET",
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });

    // Try to silently refresh on 401
    if (res.status === 401 && !opts.skipAuth && !opts._retry) {
      const refreshed = await tryRefresh();
      if (refreshed) return apiFetch(path, Object.assign({}, opts, { _retry: true }));
      clearAuth();
      if (!path.startsWith("/auth/")) location.href = "/portal/login.html";
    }

    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }

    if (!res.ok) {
      const msg = (data && data.error) || ("HTTP " + res.status);
      const err = new Error(msg);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  async function tryRefresh() {
    const rt = getRefresh();
    if (!rt) return false;
    try {
      const res = await fetch(API_BASE + "/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      if (data && data.token) {
        localStorage.setItem(STORE.token, data.token);
        if (data.refresh_token) localStorage.setItem(STORE.refresh, data.refresh_token);
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }

  // ── System helpers ─────────────────────────────────────────────────

  function userHasSystem(key) {
    const u = getUser();
    if (!u) return false;
    return (u.systems || []).some(s => s.system_key === key);
  }

  function getSystemMeta(key) {
    return SYSTEMS.find(s => s.key === key) || { key, label: key, icon: "?", emoji: "" };
  }

  // ── Auth guards ────────────────────────────────────────────────────

  function requireAuth() {
    if (!getToken() || !getUser()) {
      const next = encodeURIComponent(location.pathname + location.search);
      location.href = "/portal/login.html?next=" + next;
      return false;
    }
    return true;
  }

  function logout() {
    const token = getToken();
    clearAuth();
    // Fire and forget — the server-side logout is best-effort
    if (token) {
      fetch(API_BASE + "/auth/logout", {
        method: "POST",
        headers: { "Authorization": "Bearer " + token },
      }).catch(() => {});
    }
    location.href = "/portal/";
  }

  // ── Chrome rendering ───────────────────────────────────────────────

  function renderTopbar(active) {
    const user = getUser();
    const system = getActiveSystem();
    const meta = system ? getSystemMeta(system) : null;

    const nav = `
      <header class="topbar">
        <a class="brand" href="/portal/">
          <span class="dot"></span>
          <span>Education System</span>
        </a>
        <nav>
          <a href="/portal/" class="${active === "home" ? "active" : ""}">Home</a>
          <a href="/portal/dashboard.html${system ? "?system=" + system : ""}"
             class="${active === "dashboard" ? "active" : ""}">Dashboard</a>
          <a href="/portal/students.html${system ? "?system=" + system : ""}"
             class="${active === "students" ? "active" : ""}">Students</a>
        </nav>
        <div class="user-chip">
          ${meta ? `<span class="tag tag-${meta.key}">${meta.label}</span>` : ""}
          ${user ? `<span><strong>${escapeHtml(user.display_name || user.username)}</strong></span>` : ""}
          ${user
            ? `<button class="btn-ghost" onclick="EduPortal.logout()">Sign out</button>`
            : `<a class="btn" href="/portal/login.html">Sign in</a>`}
        </div>
      </header>`;

    const host = document.getElementById("topbar");
    if (host) host.innerHTML = nav;
  }

  // ── Utilities ──────────────────────────────────────────────────────

  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function qs(name) {
    return new URLSearchParams(location.search).get(name);
  }

  // ── Public API ─────────────────────────────────────────────────────

  global.EduPortal = {
    API_BASE,
    SYSTEMS,
    // auth
    saveAuth, clearAuth, getToken, getUser, getRefresh,
    requireAuth, logout, tryRefresh,
    // api
    apiFetch,
    // systems
    userHasSystem, getSystemMeta, setActiveSystem, getActiveSystem, routeForSystem,
    // chrome
    renderTopbar,
    // utils
    escapeHtml, qs,
  };
})(window);
