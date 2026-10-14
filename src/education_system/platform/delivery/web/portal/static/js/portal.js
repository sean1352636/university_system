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

  async function logout() {
    const token = getToken();
    const refresh = getRefresh();

    // Revoke server-side BEFORE clearing local state, and send the refresh
    // token — that is the credential worth killing. The access token expires
    // on its own; the refresh token would otherwise stay valid for days.
    // Previously this fired at an endpoint that did not exist and ignored
    // the result, so "sign out" only ever cleared the browser.
    if (token) {
      try {
        await fetch(API_BASE + "/auth/logout", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(refresh ? { refresh_token: refresh } : {}),
        });
      } catch (e) {
        // Offline, or the server is already gone. Still sign out locally —
        // refusing to would strand the user on a page they cannot use.
        console.warn("Server-side sign-out failed; clearing locally.", e);
      }
    }
    clearAuth();
    location.href = "/portal/login.html";
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
          ${system === "university"
            ? `<a href="/portal/courses.html"
                 class="${active === "courses" ? "active" : ""}">Courses</a>`
            : ""}
          ${system === "university"
            ? `<a href="/portal/operations"
                 class="${active === "operations" ? "active" : ""}">Operations</a>`
            : ""}
        </nav>
        <div class="user-chip">
          <button class="theme-toggle" data-theme-toggle
                  type="button">&#9790; Dark</button>
          ${meta ? `<span class="tag tag-${meta.key}">${meta.label}</span>` : ""}
          ${user ? `<span><strong>${escapeHtml(user.display_name || user.username)}</strong></span>` : ""}
          ${user
            ? `<button class="btn-ghost" type="button" data-logout>Sign out</button>`
            : (active === "home" ? "" : `<a class="btn" href="/portal/login.html">Sign in</a>`)}
        </div>
      </header>`;

    const host = document.getElementById("topbar");
    if (host) {
      host.innerHTML = nav;

      // Wire the chrome buttons here rather than with onclick="" attributes.
      // Portal pages are served under script-src 'self' 'nonce-...', and a
      // nonce does NOT authorise inline event-handler attributes — they need
      // 'unsafe-inline'/'unsafe-hashes'. As attributes these two silently did
      // nothing; as listeners they work with the CSP left strict.
      const themeBtn = host.querySelector("[data-theme-toggle]");
      if (themeBtn) themeBtn.addEventListener("click", () => toggleTheme());
      const logoutBtn = host.querySelector("[data-logout]");
      if (logoutBtn) logoutBtn.addEventListener("click", () => logout());

      // The button is created by this innerHTML, so its label has to be
      // set after insertion — applyTheme finds it via [data-theme-toggle].
      applyTheme(getTheme());
    }
  }


  // ── Theme ──────────────────────────────────────────────────────────
  // Applied from an inline snippet in <head> before first paint, so the
  // page never flashes light before switching. This block only handles
  // reading, toggling and persisting.

  const THEME_KEY = "edu.theme";

  function getTheme() {
    try { return localStorage.getItem(THEME_KEY) || "system"; }
    catch (e) { return "system"; }
  }

  function effectiveTheme(pref) {
    if (pref === "dark" || pref === "light") return pref;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  }

  function applyTheme(pref) {
    const root = document.documentElement;
    if (pref === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", pref);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      const eff = effectiveTheme(pref);
      btn.textContent = eff === "dark" ? "☀ Light" : "☾ Dark";
      btn.setAttribute("aria-label",
        "Switch to " + (eff === "dark" ? "light" : "dark") + " mode");
      btn.title = pref === "system"
        ? "Following your system setting" : "Theme: " + pref;
    });
  }

  function setTheme(pref) {
    try { localStorage.setItem(THEME_KEY, pref); } catch (e) { /* private mode */ }
    applyTheme(pref);
  }

  function toggleTheme() {
    // Toggle against what is actually on screen, so the first click from
    // "system" always visibly flips rather than appearing to do nothing.
    setTheme(effectiveTheme(getTheme()) === "dark" ? "light" : "dark");
  }

  function initTheme() {
    applyTheme(getTheme());
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = function () {
        if (getTheme() === "system") applyTheme("system");
      };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  }

  // ── Shutdown ───────────────────────────────────────────────────────

  async function shutdown() {
    const token = getToken();
    const res = await fetch(API_BASE + "/admin/shutdown", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token },
    });
    const data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.error || "Shutdown was refused.");
    return data;
  }

  // ── Search catalogue ───────────────────────────────────────────────
  // Static entries are the portal's own pages. Anything served by the API
  // is merged in at runtime by searchIndex(), so the list stays honest
  // about what actually exists rather than advertising dead links.

  const STATIC_ENTRIES = [
    { label: "Home",      path: "/portal/",              area: "Portal",  keywords: "welcome start main" },
    { label: "Dashboard", path: "/portal/dashboard.html", area: "Portal", keywords: "overview stats summary" },
    { label: "Students",  path: "/portal/students.html",  area: "Portal", keywords: "learners roll people" },
    { label: "Modules",   path: "/portal/module.html",    area: "Portal", keywords: "courses units subjects" },
    { label: "Sign in",   path: "/portal/login.html",     area: "Portal", keywords: "login account access" },
  ];

  async function searchIndex() {
    const entries = STATIC_ENTRIES.slice();
    const system = getActiveSystem();
    if (!system || !getToken()) return entries;
    try {
      const data = await apiFetch("/web/modules/" + system);
      (data.modules || []).forEach(function (m) {
        entries.push({
          label: m.label || m.key,
          path: m.path,
          area: getSystemMeta(system).label,
          keywords: (m.key || "").replace(/[_-]/g, " "),
          api: true,
        });
      });
    } catch (e) {
      console.warn("Could not load API modules for search.", e);
    }
    return entries;
  }

  function searchEntries(entries, query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) return [];
    const terms = q.split(/\s+/);
    return entries
      .map(function (e) {
        const hay = (e.label + " " + e.area + " " + (e.keywords || "")).toLowerCase();
        // Every term must appear somewhere, so "uni att" narrows rather
        // than widening the way an OR match would.
        if (!terms.every(function (t) { return hay.indexOf(t) !== -1; })) return null;
        const label = e.label.toLowerCase();
        // Rank: exact label, then label prefix, then label contains, then
        // a keyword-only hit.
        let score = 3;
        if (label === q) score = 0;
        else if (label.indexOf(q) === 0) score = 1;
        else if (label.indexOf(q) !== -1) score = 2;
        return { entry: e, score: score };
      })
      .filter(Boolean)
      .sort(function (a, b) {
        return a.score - b.score || a.entry.label.localeCompare(b.entry.label);
      })
      .map(function (r) { return r.entry; });
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
    // admin
    shutdown,
    // theme
    getTheme, setTheme, toggleTheme, applyTheme, initTheme, effectiveTheme,
    // search
    searchIndex, searchEntries,
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
