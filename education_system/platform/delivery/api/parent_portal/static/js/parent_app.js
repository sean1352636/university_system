/**
 * Parent Portal SPA
 * =================
 * Hash-based routing, JWT auth, pull-to-refresh, offline support.
 *
 * Views: dashboard, grades, attendance, timetable, homework,
 *        behaviour, messages, parents-evening, settings
 */

'use strict';

// ── Constants ─────────────────────────────────────────────────────────
const API_BASE        = '/parent/api';
const AUTH_LOGIN_URL  = '/api/v1/auth/login';
const TOKEN_KEY       = 'parent_jwt';
const REFRESH_KEY     = 'parent_refresh';
const CHILD_KEY       = 'parent_selected_child';
const DAYS            = ['Monday','Tuesday','Wednesday','Thursday','Friday'];

// ── Utility helpers ───────────────────────────────────────────────────

function el(id) { return document.getElementById(id); }

function html(strings, ...vals) {
  return strings.reduce((acc, s, i) => acc + s + (vals[i] !== undefined ? _esc(vals[i]) : ''), '');
}

function _esc(v) {
  return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function rawHtml(s) { return { __raw: s }; }

function renderHtml(parts) {
  return parts.map(p => (p && p.__raw) ? p.__raw : _esc(p)).join('');
}

function formatDate(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' }); }
  catch { return d; }
}

function formatTime(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleTimeString('en-GB', { hour:'2-digit', minute:'2-digit' }); }
  catch { return d; }
}

function initials(name) {
  if (!name) return '?';
  return name.split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase();
}

function pct(n, d) { return d ? Math.round(n / d * 100) : 0; }

// ── Toast ─────────────────────────────────────────────────────────────
const Toast = {
  container: null,
  init() {
    this.container = document.createElement('div');
    this.container.className = 'toast-container';
    document.body.appendChild(this.container);
  },
  show(message, type = 'info', duration = 3500) {
    const t = document.createElement('div');
    t.className = `toast toast--${type}`;
    t.textContent = message;
    this.container.appendChild(t);
    setTimeout(() => t.remove(), duration);
  },
  success(m) { this.show(m, 'success'); },
  error(m)   { this.show(m, 'error'); },
  warn(m)    { this.show(m, 'warn'); },
};

// ── Storage helpers ───────────────────────────────────────────────────
const Store = {
  get(k)         { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v)      { try { localStorage.setItem(k, v); } catch {} },
  remove(k)      { try { localStorage.removeItem(k); } catch {} },
  getJson(k)     { try { return JSON.parse(this.get(k)); } catch { return null; } },
  setJson(k, v)  { this.set(k, JSON.stringify(v)); },
};

// ── API fetch wrapper ─────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = Store.get(TOKEN_KEY);
  const headers = {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`;

  let res;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (err) {
    throw new Error('Network error — check your connection');
  }

  if (res.status === 401) {
    // Try token refresh
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers.Authorization = `Bearer ${Store.get(TOKEN_KEY)}`;
      res = await fetch(url, { ...options, headers });
    } else {
      ParentApp.logout();
      throw new Error('Session expired — please log in again');
    }
  }

  const stale = res.headers.get('X-Served-From-Cache') === 'true';
  if (stale) Toast.warn('Showing cached data — you may be offline');

  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.clone().json(); msg = j.error || j.message || msg; } catch {}
    throw new Error(msg);
  }

  return res.json();
}

async function tryRefresh() {
  const rt = Store.get(REFRESH_KEY);
  if (!rt) return false;
  try {
    const res = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    Store.set(TOKEN_KEY, data.access_token || data.token);
    if (data.refresh_token) Store.set(REFRESH_KEY, data.refresh_token);
    return true;
  } catch { return false; }
}

// ── Pull-to-refresh ───────────────────────────────────────────────────
const PullToRefresh = {
  startY: 0,
  pulling: false,
  threshold: 80,
  indicator: null,

  init(onRefresh) {
    this.indicator = el('ptr-indicator');
    const main = el('app-main');
    if (!main) return;

    main.addEventListener('touchstart', (e) => {
      if (main.scrollTop === 0) {
        this.startY = e.touches[0].clientY;
        this.pulling = true;
      }
    }, { passive: true });

    main.addEventListener('touchmove', (e) => {
      if (!this.pulling) return;
      const dy = e.touches[0].clientY - this.startY;
      if (dy > 20 && this.indicator) {
        this.indicator.classList.remove('hidden');
      }
    }, { passive: true });

    main.addEventListener('touchend', async (e) => {
      if (!this.pulling) return;
      const dy = e.changedTouches[0].clientY - this.startY;
      this.pulling = false;
      if (dy > this.threshold) {
        await onRefresh();
      }
      if (this.indicator) this.indicator.classList.add('hidden');
    }, { passive: true });
  },
};

// ── Main App ──────────────────────────────────────────────────────────
const ParentApp = {
  currentView: 'dashboard',
  children: [],
  selectedChild: null,
  notificationCount: 0,
  _viewCache: {},

  // ── Bootstrap ───────────────────────────────────────────────────
  async init() {
    Toast.init();

    if (!Store.get(TOKEN_KEY)) {
      this.renderLogin();
      return;
    }

    this.renderShell();
    await this.loadChildren();
    this.bindNav();
    this.bindRouter();
    PullToRefresh.init(() => this.refreshCurrentView());
    await this.loadNotificationCount();
    this.navigate(location.hash.slice(1) || 'dashboard');
    this.registerServiceWorker();
  },

  // ── Auth ─────────────────────────────────────────────────────────
  async login(username, password) {
    const btn = el('login-btn');
    btn.disabled = true;
    btn.textContent = 'Signing in…';
    try {
      const res = await fetch(AUTH_LOGIN_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Login failed');
      if (data.mfa_required) {
        Toast.warn('MFA required — please use the full web portal');
        return;
      }
      Store.set(TOKEN_KEY, data.access_token || data.token);
      if (data.refresh_token) Store.set(REFRESH_KEY, data.refresh_token);
      // Reload to boot the full app
      location.reload();
    } catch (err) {
      Toast.error(err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Sign In';
    }
  },

  logout() {
    Store.remove(TOKEN_KEY);
    Store.remove(REFRESH_KEY);
    Store.remove(CHILD_KEY);
    location.reload();
  },

  // ── Render shell ─────────────────────────────────────────────────
  renderLogin() {
    document.body.innerHTML = `
      <div class="login-screen">
        <div class="login-logo">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin:0 auto 8px">
            <rect width="48" height="48" rx="12" fill="white" fill-opacity="0.2"/>
            <path d="M24 12L8 20v2l16 8 16-8v-2L24 12z" fill="white"/>
            <path d="M14 24v8c0 3.3 4.5 6 10 6s10-2.7 10-6v-8L24 28l-10-4z" fill="white" fill-opacity="0.8"/>
          </svg>
          Parent<span>Portal</span>
        </div>
        <div class="login-card">
          <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:4px">Welcome back</h2>
          <p style="font-size:.875rem;color:var(--color-text-2);margin-bottom:24px">
            Sign in with your school account
          </p>
          <form id="login-form">
            <div class="form-group">
              <label class="form-label" for="username">Username or email</label>
              <input class="form-input" id="username" type="text" autocomplete="username"
                     placeholder="parent@school.example" required>
            </div>
            <div class="form-group">
              <label class="form-label" for="password">Password</label>
              <input class="form-input" id="password" type="password" autocomplete="current-password"
                     placeholder="••••••••" required>
            </div>
            <button class="btn btn--primary btn--full" type="submit" id="login-btn">Sign In</button>
          </form>
        </div>
        <p style="color:rgba(255,255,255,.7);font-size:.8rem;text-align:center;max-width:320px">
          Contact your school administrator if you need access.
        </p>
      </div>`;

    el('login-form').addEventListener('submit', (e) => {
      e.preventDefault();
      this.login(el('username').value.trim(), el('password').value);
    });
  },

  renderShell() {
    document.getElementById('app').innerHTML = `
      <!-- Pull-to-refresh indicator -->
      <div id="ptr-indicator" class="ptr-indicator hidden">
        <div class="ptr-spinner"></div> Refreshing…
      </div>

      <!-- Top header -->
      <header class="app-header">
        <span class="app-header__title">Parent Portal</span>
        <div class="app-header__actions">
          <div id="child-switcher-container"></div>
          <button class="icon-btn" id="notifications-btn" title="Notifications" aria-label="Notifications">
            <svg class="bottom-nav__icon" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span class="badge hidden" id="notif-badge">0</span>
          </button>
          <button class="icon-btn" id="logout-btn" title="Sign out" aria-label="Sign out">
            <svg class="bottom-nav__icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </header>

      <!-- Desktop side nav -->
      <nav class="side-nav" id="side-nav" style="display:none">
        <div class="side-nav__logo">Parent Portal</div>
        ${this._sideNavItems()}
      </nav>

      <!-- Main content -->
      <main class="app-main" id="app-main">
        <div id="view-container"></div>
      </main>

      <!-- Mobile bottom nav -->
      <nav class="bottom-nav" id="bottom-nav">
        ${this._bottomNavItems()}
      </nav>

      <!-- Overflow menu (hidden by default) -->
      <div id="overflow-menu" class="hidden"></div>
      <div id="overlay" class="overlay hidden"></div>
    `;

    // Bind logout
    el('logout-btn').addEventListener('click', () => this.logout());
    el('notifications-btn').addEventListener('click', () => this.navigate('notifications'));

    // Show side nav on tablet+
    if (window.matchMedia('(min-width: 768px)').matches) {
      el('side-nav').style.display = 'flex';
    }
    window.matchMedia('(min-width: 768px)').addEventListener('change', (e) => {
      el('side-nav').style.display = e.matches ? 'flex' : 'none';
    });
  },

  _navItems() {
    return [
      { id: 'dashboard',       label: 'Dashboard',        icon: 'home' },
      { id: 'grades',          label: 'Grades',           icon: 'bar-chart' },
      { id: 'attendance',      label: 'Attendance',       icon: 'calendar' },
      { id: 'messages',        label: 'Messages',         icon: 'message-square' },
      { id: 'more',            label: 'More',             icon: 'grid' },
    ];
  },

  _moreItems() {
    return [
      { id: 'timetable',       label: 'Timetable',        icon: 'clock' },
      { id: 'homework',        label: 'Homework',         icon: 'book-open' },
      { id: 'behaviour',       label: 'Behaviour',        icon: 'activity' },
      { id: 'parents-evening', label: "Parents' Evening", icon: 'users' },
      { id: 'settings',        label: 'Settings',         icon: 'settings' },
    ];
  },

  _allNavItems() {
    return [
      { id: 'dashboard',       label: 'Dashboard',        icon: 'home' },
      { id: 'grades',          label: 'Grades',           icon: 'bar-chart' },
      { id: 'attendance',      label: 'Attendance',       icon: 'calendar' },
      { id: 'timetable',       label: 'Timetable',        icon: 'clock' },
      { id: 'homework',        label: 'Homework',         icon: 'book-open' },
      { id: 'behaviour',       label: 'Behaviour',        icon: 'activity' },
      { id: 'messages',        label: 'Messages',         icon: 'message-square' },
      { id: 'parents-evening', label: "Parents' Evening", icon: 'users' },
      { id: 'settings',        label: 'Settings',         icon: 'settings' },
    ];
  },

  _iconSvg(name) {
    const icons = {
      'home':          '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
      'bar-chart':     '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
      'calendar':      '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
      'message-square':'<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
      'grid':          '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
      'clock':         '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
      'book-open':     '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
      'activity':      '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
      'users':         '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      'settings':      '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
      'bell':          '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
      'chevron-right': '<polyline points="9 18 15 12 9 6"/>',
    };
    return `<svg class="bottom-nav__icon" viewBox="0 0 24 24">${icons[name] || ''}</svg>`;
  },

  _bottomNavItems() {
    return this._navItems().map(item => `
      <button class="bottom-nav__item" data-view="${item.id}" aria-label="${item.label}">
        ${this._iconSvg(item.icon)}
        <span>${item.label}</span>
        ${item.id === 'messages' ? '<span class="badge hidden" id="msg-badge">0</span>' : ''}
      </button>
    `).join('');
  },

  _sideNavItems() {
    return this._allNavItems().map(item => `
      <button class="side-nav__item" data-view="${item.id}">
        ${this._iconSvg(item.icon)}
        ${item.label}
      </button>
    `).join('');
  },

  // ── Navigation ───────────────────────────────────────────────────
  bindNav() {
    // Bottom nav
    document.querySelectorAll('[data-view]').forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        if (view === 'more') {
          this.showOverflowMenu();
        } else {
          this.navigate(view);
        }
      });
    });

    // Overlay dismiss
    el('overlay').addEventListener('click', () => this.hideOverflowMenu());
  },

  bindRouter() {
    window.addEventListener('hashchange', () => {
      const view = location.hash.slice(1) || 'dashboard';
      this._renderView(view);
    });
  },

  navigate(view) {
    location.hash = view;
    this._renderView(view);
  },

  _renderView(view) {
    this.currentView = view;
    this.hideOverflowMenu();

    // Update active states
    document.querySelectorAll('.bottom-nav__item, .side-nav__item').forEach(btn => {
      const isActive = btn.dataset.view === view ||
                       (view === 'notifications' && btn.dataset.view === 'messages');
      btn.classList.toggle('active', isActive);
    });

    this._viewCache = {};  // clear cache on navigation
    this.renderView(view);
  },

  showOverflowMenu() {
    const items = this._moreItems().map(item => `
      <div class="overflow-menu__item" data-view="${item.id}">
        ${this._iconSvg(item.icon)}
        <span>${item.label}</span>
        <svg class="bottom-nav__icon" viewBox="0 0 24 24" style="margin-left:auto;width:16px;height:16px">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </div>
    `).join('');

    el('overflow-menu').innerHTML = items;
    el('overflow-menu').classList.remove('hidden');
    el('overlay').classList.remove('hidden');

    el('overflow-menu').querySelectorAll('[data-view]').forEach(btn => {
      btn.addEventListener('click', () => this.navigate(btn.dataset.view));
    });
  },

  hideOverflowMenu() {
    el('overflow-menu').classList.add('hidden');
    el('overlay').classList.add('hidden');
  },

  // ── Child loading & switcher ─────────────────────────────────────
  async loadChildren() {
    try {
      const data = await apiFetch('/children');
      this.children = data.data || [];

      const saved = Store.getJson(CHILD_KEY);
      this.selectedChild = saved && this.children.find(c => c.child_student_id === saved.child_student_id)
        ? saved
        : this.children[0] || null;

      this.renderChildSwitcher();
    } catch (err) {
      Toast.error('Could not load children: ' + err.message);
    }
  },

  renderChildSwitcher() {
    const container = el('child-switcher-container');
    if (!container) return;

    if (this.children.length === 0) {
      container.innerHTML = '<span style="font-size:.8rem;color:var(--color-text-2)">No linked children</span>';
      return;
    }

    const child = this.selectedChild;
    const name = child?.name || child?.child_student_id || 'Child';

    if (this.children.length === 1) {
      container.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;font-size:.85rem;font-weight:600">
          <div class="child-avatar">${initials(name)}</div>
          <span class="truncate" style="max-width:120px">${_esc(name)}</span>
        </div>`;
      return;
    }

    container.innerHTML = `
      <div class="child-switcher" id="child-switcher-btn">
        <div class="child-avatar">${initials(name)}</div>
        <span class="truncate" style="max-width:90px">${_esc(name)}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </div>
      <div id="child-dropdown" class="hidden" style="
        position:absolute;top:calc(var(--header-h) + var(--safe-top));right:var(--space-md);
        background:var(--color-surface);border:1px solid var(--color-border);
        border-radius:var(--radius-md);box-shadow:0 8px 24px var(--color-shadow);
        z-index:400;min-width:180px;overflow:hidden">
        ${this.children.map(c => `
          <div class="list-item" data-child-id="${_esc(c.child_student_id)}" style="padding:12px 16px">
            <div class="child-avatar">${initials(c.name || c.child_student_id)}</div>
            <div>
              <div style="font-weight:600;font-size:.9rem">${_esc(c.name || c.child_student_id)}</div>
              <div style="font-size:.75rem;color:var(--color-text-2)">${_esc(c.child_system_key)} • ${_esc(c.year_group || '')}</div>
            </div>
          </div>
        `).join('')}
      </div>`;

    el('child-switcher-btn').addEventListener('click', () => {
      el('child-dropdown').classList.toggle('hidden');
    });

    el('child-dropdown').querySelectorAll('[data-child-id]').forEach(item => {
      item.addEventListener('click', () => {
        const found = this.children.find(c => c.child_student_id === item.dataset.childId);
        if (found) {
          this.selectedChild = found;
          Store.setJson(CHILD_KEY, found);
          this.renderChildSwitcher();
          this.renderView(this.currentView);
        }
        el('child-dropdown').classList.add('hidden');
      });
    });

    // Dismiss dropdown on outside click
    document.addEventListener('click', (e) => {
      const dd = el('child-dropdown');
      if (dd && !dd.classList.contains('hidden')) {
        if (!container.contains(e.target)) dd.classList.add('hidden');
      }
    }, { once: true });
  },

  // ── Notification badge ───────────────────────────────────────────
  async loadNotificationCount() {
    try {
      const data = await apiFetch('/notifications');
      const n = data.unread_count || 0;
      this.notificationCount = n;
      const badge = el('notif-badge');
      if (badge) {
        badge.textContent = n > 99 ? '99+' : n;
        badge.classList.toggle('hidden', n === 0);
      }
    } catch {}
  },

  // ── View dispatcher ──────────────────────────────────────────────
  renderView(view) {
    const container = el('view-container');
    if (!container) return;
    container.innerHTML = this._skeletonHtml();

    const child = this.selectedChild;

    switch (view) {
      case 'dashboard':       return this.renderDashboard(container);
      case 'grades':          return this.renderGrades(container, child);
      case 'attendance':      return this.renderAttendance(container, child);
      case 'timetable':       return this.renderTimetable(container, child);
      case 'homework':        return this.renderHomework(container, child);
      case 'behaviour':       return this.renderBehaviour(container, child);
      case 'messages':        return this.renderMessages(container, child);
      case 'parents-evening': return this.renderParentsEvening(container);
      case 'notifications':   return this.renderNotifications(container);
      case 'settings':        return this.renderSettings(container);
      default:                container.innerHTML = this._emptyState('Unknown view', 'Navigate using the menu below.');
    }
  },

  _skeletonHtml() {
    return `
      <div style="display:flex;flex-direction:column;gap:16px">
        <div class="skeleton skeleton--h2 skeleton--short"></div>
        <div class="card"><div class="card__body"><div class="skeleton"></div><div class="skeleton skeleton--short mt-sm"></div></div></div>
        <div class="card"><div class="card__body"><div class="skeleton"></div><div class="skeleton skeleton--xshort mt-sm"></div></div></div>
        <div class="card"><div class="card__body"><div class="skeleton"></div></div></div>
      </div>`;
  },

  _emptyState(title, body, icon = '📭') {
    return `<div class="empty-state">
      <div class="empty-state__icon">${icon}</div>
      <div class="empty-state__title">${_esc(title)}</div>
      <p class="empty-state__body">${_esc(body)}</p>
    </div>`;
  },

  async refreshCurrentView() {
    this._viewCache = {};
    this.renderView(this.currentView);
  },

  // ── Dashboard ────────────────────────────────────────────────────
  async renderDashboard(container) {
    const children = this.children;
    if (children.length === 0) {
      container.innerHTML = this._emptyState(
        'No children linked',
        'Contact your school administrator to link your children to this account.',
        '👨‍👩‍👧'
      );
      return;
    }

    // Render overview cards for each child
    let html = `<h1 class="section-title">Dashboard</h1>`;

    for (const child of children) {
      html += await this._renderChildOverviewCard(child);
    }

    // Quick actions
    html += `
      <div class="card mt-md">
        <div class="card__header"><span class="card__title">Quick Actions</span></div>
        <div class="card__body" style="display:flex;flex-wrap:wrap;gap:8px">
          <button class="btn btn--outline btn--sm" onclick="ParentApp.navigate('messages')">Message School</button>
          <button class="btn btn--outline btn--sm" onclick="ParentApp.navigate('parents-evening')">Book Parents' Evening</button>
          <button class="btn btn--outline btn--sm" onclick="ParentApp.navigate('homework')">View Homework</button>
        </div>
      </div>`;

    container.innerHTML = html;
  },

  async _renderChildOverviewCard(child) {
    const name = child.name || child.child_student_id;
    let attHtml = '', gradeHtml = '';

    try {
      const attData = await apiFetch(`/children/${child.child_student_id}/attendance`);
      const s = attData.data?.summary || {};
      const pctVal = s.attendance_pct || 0;
      const pctColor = pctVal >= 95 ? 'accent' : pctVal >= 85 ? 'warn' : 'danger';
      attHtml = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <span style="font-size:.8rem;color:var(--color-text-2)">Attendance</span>
          <span style="font-weight:700;color:var(--color-${pctColor})">${pctVal}%</span>
        </div>
        <div class="progress-bar"><div class="progress-bar__fill progress-bar__fill--${pctColor}" style="width:${pctVal}%"></div></div>`;
    } catch {}

    try {
      const gradesData = await apiFetch(`/children/${child.child_student_id}/grades`);
      const grades = (gradesData.data || []).slice(0, 3);
      gradeHtml = grades.map(g =>
        `<div style="display:flex;justify-content:space-between;font-size:.85rem;padding:4px 0;border-bottom:1px solid var(--color-border)">
          <span class="truncate" style="max-width:60%">${_esc(g.subject_name || g.subject_id || '')}</span>
          <strong>${_esc(g.grade || g.percentage || '')}</strong>
        </div>`
      ).join('');
    } catch {}

    return `
      <div class="card card--primary">
        <div class="card__header">
          <div style="display:flex;align-items:center;gap:12px">
            <div class="child-avatar" style="width:36px;height:36px;font-size:.9rem">${initials(name)}</div>
            <div>
              <div class="card__title">${_esc(name)}</div>
              <div class="card__subtitle">${_esc(child.year_group || '')} ${child.form_group ? '• ' + _esc(child.form_group) : ''}</div>
            </div>
          </div>
          <button class="btn btn--ghost btn--sm" onclick="ParentApp.navigate('attendance')">Details</button>
        </div>
        <div class="card__body">
          ${attHtml}
          ${gradeHtml ? `<div style="margin-top:12px"><div style="font-size:.8rem;font-weight:600;color:var(--color-text-2);margin-bottom:4px">RECENT GRADES</div>${gradeHtml}</div>` : ''}
        </div>
      </div>`;
  },

  // ── Grades ───────────────────────────────────────────────────────
  async renderGrades(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', 'Select a child from the top menu.'); return; }

    container.innerHTML = '<div class="section-title">Grades</div>' + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/grades`);
      const grades = data.data || [];

      if (grades.length === 0) {
        container.innerHTML = `<h1 class="section-title">Grades</h1>` +
          this._emptyState('No grades recorded', 'Grades will appear here once teachers submit them.', '📊');
        return;
      }

      // Group by subject
      const bySubject = {};
      for (const g of grades) {
        const subj = g.subject_name || g.subject_id || 'Unknown';
        if (!bySubject[subj]) bySubject[subj] = [];
        bySubject[subj].push(g);
      }

      let html = `<h1 class="section-title">Grades — ${_esc(child.name || child.child_student_id)}</h1>`;

      for (const [subj, items] of Object.entries(bySubject)) {
        const latest = items[0];
        const grade = latest.grade || (latest.percentage != null ? `${latest.percentage}%` : '–');
        const gpill = this._gradePill(String(latest.grade || ''));

        html += `
          <div class="card">
            <div class="card__header">
              <div>
                <div class="card__title">${_esc(subj)}</div>
                ${latest.grade_type ? `<div class="card__subtitle">${_esc(latest.grade_type)}</div>` : ''}
              </div>
              <div class="grade-pill grade-pill--${_esc(String(latest.grade || ''))}">${_esc(grade)}</div>
            </div>
            <div class="card__body" style="display:flex;flex-direction:column;gap:4px">
              ${items.slice(0,5).map(g => `
                <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--color-border)">
                  <div>
                    <div style="font-size:.875rem;font-weight:500">${_esc(g.grade_type || 'Grade')}</div>
                    <div style="font-size:.75rem;color:var(--color-text-2)">${formatDate(g.date_recorded)}</div>
                  </div>
                  <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
                    <strong>${_esc(g.grade || '')}</strong>
                    ${g.percentage != null ? `<span style="font-size:.75rem;color:var(--color-text-2)">${g.percentage}%</span>` : ''}
                  </div>
                </div>`).join('')}
              ${latest.comments ? `<p style="font-size:.8rem;color:var(--color-text-2);margin-top:8px;font-style:italic">"${_esc(latest.comments)}"</p>` : ''}
            </div>
          </div>`;
      }

      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Grades</h1>` +
        this._emptyState('Could not load grades', err.message, '⚠️');
    }
  },

  _gradePill(g) {
    const cls = ['9','8','A*','A'].includes(g) ? 'accent' :
                ['7','6','B'].includes(g) ? 'info' :
                ['5','4','C'].includes(g) ? 'warn' : 'danger';
    return `<span class="chip chip--${cls}">${_esc(g)}</span>`;
  },

  // ── Attendance ───────────────────────────────────────────────────
  async renderAttendance(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', ''); return; }

    container.innerHTML = `<h1 class="section-title">Attendance</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/attendance?limit=90`);
      const { summary = {}, records = [] } = data.data || {};

      const pct  = summary.attendance_pct || 0;
      const clr  = pct >= 95 ? 'accent' : pct >= 85 ? 'warn' : 'danger';

      const statGrid = `
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-card__value" style="color:var(--color-${clr})">${pct}%</div><div class="stat-card__label">Overall</div></div>
          <div class="stat-card"><div class="stat-card__value" style="color:var(--color-accent)">${summary.present || 0}</div><div class="stat-card__label">Present</div></div>
          <div class="stat-card"><div class="stat-card__value" style="color:var(--color-danger)">${summary.absent || 0}</div><div class="stat-card__label">Absent</div></div>
          <div class="stat-card"><div class="stat-card__value" style="color:var(--color-warn)">${summary.late || 0}</div><div class="stat-card__label">Late</div></div>
        </div>`;

      // Calendar-style grid
      const calHtml = this._renderAttendanceCalendar(records);

      // Recent records list
      const listHtml = records.slice(0, 30).map(r => {
        const s = (r.status || 'unknown').toLowerCase();
        const chipCls = s === 'present' ? 'present' : s === 'absent' ? 'absent' : s === 'late' ? 'late' : 'auth';
        return `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--color-border)">
            <div>
              <div style="font-size:.875rem;font-weight:500">${formatDate(r.date)}</div>
              ${r.subject_id ? `<div style="font-size:.75rem;color:var(--color-text-2)">${_esc(r.subject_id)}</div>` : ''}
            </div>
            <span class="chip chip--${chipCls}">${_esc(r.status || 'Unknown')}</span>
          </div>`;
      }).join('');

      container.innerHTML = `
        <h1 class="section-title">Attendance — ${_esc(child.name || child.child_student_id)}</h1>
        ${statGrid}
        <div class="card"><div class="card__header"><span class="card__title">Last 90 Days</span></div><div class="card__body">${calHtml}</div></div>
        <div class="card"><div class="card__header"><span class="card__title">Recent Records</span></div><div class="card__body" style="padding:0 16px">${listHtml}</div></div>`;
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Attendance</h1>` +
        this._emptyState('Could not load attendance', err.message, '⚠️');
    }
  },

  _renderAttendanceCalendar(records) {
    const byDate = {};
    records.forEach(r => { if (r.date) byDate[r.date.slice(0, 10)] = r.status; });

    // Build last 70 days
    const cells = [];
    const today = new Date();
    for (let i = 69; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      const dow = d.getDay(); // 0=Sun
      if (dow === 0 || dow === 6) continue; // skip weekends
      const status = byDate[key];
      const cls = !status ? 'empty' :
                  status.toLowerCase() === 'present' ? 'present' :
                  status.toLowerCase() === 'absent'  ? 'absent'  :
                  status.toLowerCase() === 'late'    ? 'late'    : 'auth';
      cells.push(`<div class="cal-cell cal-cell--${cls}" title="${key}: ${status || 'No data'}">${d.getDate()}</div>`);
    }

    return `<div class="attendance-calendar">${cells.join('')}</div>
      <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:.75rem">
        <span><span class="cal-cell cal-cell--present" style="display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:middle"></span>Present</span>
        <span><span class="cal-cell cal-cell--absent" style="display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:middle"></span>Absent</span>
        <span><span class="cal-cell cal-cell--late" style="display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:middle"></span>Late</span>
        <span><span class="cal-cell cal-cell--auth" style="display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:4px;vertical-align:middle"></span>Authorised</span>
      </div>`;
  },

  // ── Timetable ────────────────────────────────────────────────────
  async renderTimetable(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', ''); return; }

    container.innerHTML = `<h1 class="section-title">Timetable</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/timetable`);
      const slots = data.data || [];

      if (slots.length === 0) {
        container.innerHTML = `<h1 class="section-title">Timetable</h1>` +
          this._emptyState('No timetable found', 'The timetable has not been set yet.', '🗓️');
        return;
      }

      // Group by day
      const byDay = {};
      DAYS.forEach(d => { byDay[d] = []; });
      slots.forEach(s => {
        const day = s.day_of_week;
        if (!byDay[day]) byDay[day] = [];
        byDay[day].push(s);
      });

      // Find today's day name
      const todayName = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][new Date().getDay()];
      const dayOrder = DAYS.includes(todayName) ? [todayName, ...DAYS.filter(d => d !== todayName)] : DAYS;

      let html = `<h1 class="section-title">Timetable — ${_esc(child.name || child.child_student_id)}</h1>`;
      html += `<div class="tab-bar" id="tt-tab-bar">
        ${dayOrder.map((d,i) => `<button class="tab-btn${i===0?' active':''}" data-day="${_esc(d)}">${d.slice(0,3)}</button>`).join('')}
      </div>`;

      html += `<div id="tt-day-view">`;
      dayOrder.forEach((day, i) => {
        const daySlots = byDay[day] || [];
        html += `<div class="timetable-day${i!==0?' hidden':''}" data-day-panel="${_esc(day)}">
          <div class="timetable-day__header">${day}</div>
          ${daySlots.length === 0
            ? `<div style="padding:20px;text-align:center;color:var(--color-text-2);font-size:.875rem">No lessons</div>`
            : daySlots.map(s => `
            <div class="timetable-slot">
              <div class="timetable-slot__time">${_esc(s.start_time || `P${s.period}`)}<br><span style="color:var(--color-text-2)">${_esc(s.end_time || '')}</span></div>
              <div class="timetable-slot__subject">${_esc(s.subject_name || 'Unknown')}<br>
                <span style="font-size:.75rem;font-weight:400;color:var(--color-text-2)">${_esc(s.teacher_name || '')}</span>
              </div>
              ${s.room ? `<div class="timetable-slot__room">${_esc(s.room)}</div>` : ''}
            </div>`).join('')}
        </div>`;
      });
      html += `</div>`;

      container.innerHTML = html;

      // Tab switching
      container.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          container.querySelectorAll('[data-day-panel]').forEach(p => {
            p.classList.toggle('hidden', p.dataset.dayPanel !== btn.dataset.day);
          });
        });
      });
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Timetable</h1>` +
        this._emptyState('Could not load timetable', err.message, '⚠️');
    }
  },

  // ── Homework ─────────────────────────────────────────────────────
  async renderHomework(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', ''); return; }

    container.innerHTML = `<h1 class="section-title">Homework</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/homework`);
      const { pending = [], completed = [] } = data.data || {};

      let html = `<h1 class="section-title">Homework — ${_esc(child.name || child.child_student_id)}</h1>`;
      html += `<div class="tab-bar">
        <button class="tab-btn active" data-tab="pending">Pending (${pending.length})</button>
        <button class="tab-btn" data-tab="completed">Completed (${completed.length})</button>
      </div>`;

      const renderList = (items, emptyMsg) => {
        if (items.length === 0) return this._emptyState('All done!', emptyMsg, '✅');
        return items.map(h => {
          const overdue = h.due_date && new Date(h.due_date) < new Date() && !h.submitted_at;
          return `
            <div class="card card--${overdue ? 'danger' : 'flat'}" style="margin-bottom:8px">
              <div class="card__body">
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
                  <div style="flex:1;min-width:0">
                    <div style="font-weight:600;font-size:.9rem">${_esc(h.title || 'Homework')}</div>
                    <div style="font-size:.8rem;color:var(--color-text-2);margin-top:2px">${_esc(h.subject_name || '')}</div>
                    ${h.description ? `<p style="font-size:.8rem;margin-top:6px;color:var(--color-text-2)">${_esc(h.description)}</p>` : ''}
                  </div>
                  <span class="chip chip--${overdue ? 'absent' : h.submitted_at ? 'done' : 'pending'}">${overdue ? 'Overdue' : h.submitted_at ? 'Done' : 'Pending'}</span>
                </div>
                <div style="display:flex;gap:12px;margin-top:8px;font-size:.75rem;color:var(--color-text-2)">
                  ${h.set_date ? `<span>Set: ${formatDate(h.set_date)}</span>` : ''}
                  ${h.due_date ? `<span>Due: ${formatDate(h.due_date)}</span>` : ''}
                  ${h.marks_awarded != null ? `<span>Marks: ${h.marks_awarded}/${h.max_marks || '?'}</span>` : ''}
                </div>
              </div>
            </div>`;
        }).join('');
      };

      html += `<div id="tab-pending">${renderList(pending, 'No pending homework.')}</div>`;
      html += `<div id="tab-completed" class="hidden">${renderList(completed, 'No completed homework yet.')}</div>`;

      container.innerHTML = html;

      container.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          container.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          el('tab-pending').classList.toggle('hidden', btn.dataset.tab !== 'pending');
          el('tab-completed').classList.toggle('hidden', btn.dataset.tab !== 'completed');
        });
      });
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Homework</h1>` +
        this._emptyState('Could not load homework', err.message, '⚠️');
    }
  },

  // ── Behaviour ────────────────────────────────────────────────────
  async renderBehaviour(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', ''); return; }

    container.innerHTML = `<h1 class="section-title">Behaviour</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/behaviour`);
      const records = data.data || [];

      let html = `<h1 class="section-title">Behaviour — ${_esc(child.name || child.child_student_id)}</h1>`;

      if (records.length === 0) {
        html += this._emptyState('No records', 'No behaviour or reward records to show.', '⭐');
        container.innerHTML = html;
        return;
      }

      html += `<div class="timeline">`;
      records.forEach(r => {
        const isReward = r.record_type === 'reward';
        html += `
          <div class="timeline-item timeline-item--${isReward ? 'reward' : 'danger'}">
            <div class="card card--flat" style="margin-bottom:0">
              <div class="card__body">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
                  <div style="flex:1;min-width:0">
                    <div style="font-size:.8rem;font-weight:600;color:var(--color-text-2);text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px">
                      ${isReward ? '⭐ Reward' : '⚠️ Behaviour'}
                    </div>
                    <div style="font-weight:600;font-size:.9rem">${_esc(r.category || r.description || 'Record')}</div>
                    ${r.description && r.category ? `<p style="font-size:.8rem;color:var(--color-text-2);margin-top:4px">${_esc(r.description)}</p>` : ''}
                    <div style="font-size:.75rem;color:var(--color-text-2);margin-top:6px">
                      ${formatDate(r.date)}
                      ${r.severity ? ` • Severity: ${_esc(r.severity)}` : ''}
                      ${r.points ? ` • +${r.points} pts` : ''}
                    </div>
                  </div>
                  <span class="chip chip--${isReward ? 'reward' : 'behaviour'}">${isReward ? 'Reward' : 'Incident'}</span>
                </div>
                ${r.action_taken ? `<div style="margin-top:8px;font-size:.8rem;background:var(--color-surface-2);padding:6px 10px;border-radius:6px">Action: ${_esc(r.action_taken)}</div>` : ''}
              </div>
            </div>
          </div>`;
      });
      html += `</div>`;
      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Behaviour</h1>` +
        this._emptyState('Could not load behaviour records', err.message, '⚠️');
    }
  },

  // ── Messages ─────────────────────────────────────────────────────
  async renderMessages(container, child) {
    if (!child) { container.innerHTML = this._emptyState('No child selected', ''); return; }

    container.innerHTML = `<h1 class="section-title">Messages</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch(`/children/${child.child_student_id}/messages`);
      const messages = data.data || [];

      let html = `<h1 class="section-title">Messages — ${_esc(child.name || child.child_student_id)}</h1>`;

      if (messages.length === 0) {
        html += this._emptyState('No messages', 'Your school communications will appear here.', '💬');
      } else {
        html += `<div class="card">`;
        messages.forEach(m => {
          const unread = !m.is_read && !m.read_at;
          html += `
            <div class="list-item" style="${unread ? 'background:var(--color-primary-lt)' : ''}">
              <div class="list-item__icon">${m.sender_name ? initials(m.sender_name) : '✉️'}</div>
              <div class="list-item__content">
                <div class="list-item__title">${_esc(m.subject || '(No subject)')}</div>
                <div class="list-item__meta">${_esc(m.sender_name || 'School')} · ${formatDate(m.sent_at)}</div>
              </div>
              ${unread ? '<span class="chip chip--primary" style="font-size:.7rem">New</span>' : ''}
            </div>`;
        });
        html += `</div>`;
      }

      // Compose area
      html += `
        <div class="card mt-md">
          <div class="card__header"><span class="card__title">Send a Message</span></div>
          <div class="card__body">
            <form id="compose-form">
              <div class="form-group">
                <label class="form-label" for="msg-subject">Subject</label>
                <input class="form-input" id="msg-subject" placeholder="e.g. Absence on Friday" required>
              </div>
              <div class="form-group">
                <label class="form-label" for="msg-body">Message</label>
                <textarea class="form-textarea" id="msg-body" placeholder="Write your message here…" required></textarea>
              </div>
              <button class="btn btn--primary" type="submit">Send Message</button>
            </form>
          </div>
        </div>`;

      container.innerHTML = html;

      el('compose-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = e.target.querySelector('button[type=submit]');
        btn.disabled = true;
        btn.textContent = 'Sending…';
        try {
          await apiFetch(`/children/${child.child_student_id}/messages`, {
            method: 'POST',
            body: JSON.stringify({
              subject: el('msg-subject').value,
              body: el('msg-body').value,
            }),
          });
          Toast.success('Message sent successfully');
          el('msg-subject').value = '';
          el('msg-body').value = '';
        } catch (err) {
          Toast.error(err.message);
        } finally {
          btn.disabled = false;
          btn.textContent = 'Send Message';
        }
      });
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Messages</h1>` +
        this._emptyState('Could not load messages', err.message, '⚠️');
    }
  },

  // ── Parents' Evening ─────────────────────────────────────────────
  async renderParentsEvening(container) {
    container.innerHTML = `<h1 class="section-title">Parents' Evening</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch('/parents-evening');
      const slots = data.data || [];

      let html = `<h1 class="section-title">Parents' Evening</h1>`;

      if (slots.length === 0) {
        html += this._emptyState('No upcoming events', 'Parents\' Evening slots will appear here when available.', '📅');
        container.innerHTML = html;
        return;
      }

      // Group by event
      const byEvent = {};
      slots.forEach(s => {
        const key = s.event_name || s.event_id || 'Event';
        if (!byEvent[key]) byEvent[key] = [];
        byEvent[key].push(s);
      });

      for (const [event, eventSlots] of Object.entries(byEvent)) {
        html += `
          <div class="card">
            <div class="card__header">
              <div>
                <div class="card__title">${_esc(event)}</div>
                ${eventSlots[0]?.event_date ? `<div class="card__subtitle">${formatDate(eventSlots[0].event_date)}</div>` : ''}
              </div>
            </div>
            <div class="card__body" style="display:flex;flex-direction:column;gap:8px">`;

        eventSlots.forEach(s => {
          const booked = s.is_booked && s.booked_by_parent_id;
          html += `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px;border-radius:8px;border:1px solid var(--color-border);${booked ? 'background:var(--color-primary-lt)' : ''}">
                <div>
                  <div style="font-weight:600;font-size:.875rem">${_esc(s.start_time || '')} – ${_esc(s.end_time || '')}</div>
                  <div style="font-size:.75rem;color:var(--color-text-2)">${_esc(s.teacher_id || 'Teacher')}</div>
                </div>
                ${booked
                  ? `<span class="chip chip--done">Booked</span>`
                  : `<button class="btn btn--primary btn--sm book-slot-btn"
                       data-slot-id="${_esc(String(s.slot_id))}"
                       data-child-id="${_esc(s.child_student_id || '')}"
                       data-system="${_esc(s.system_key || 'school')}">
                       Book
                     </button>`
                }
              </div>`;
        });

        html += `</div></div>`;
      }

      container.innerHTML = html;

      container.querySelectorAll('.book-slot-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          btn.disabled = true;
          btn.textContent = 'Booking…';
          try {
            await apiFetch('/parents-evening/book', {
              method: 'POST',
              body: JSON.stringify({
                slot_id: btn.dataset.slotId,
                child_id: btn.dataset.childId,
                system_key: btn.dataset.system,
              }),
            });
            Toast.success('Slot booked!');
            this.renderParentsEvening(container);
          } catch (err) {
            Toast.error(err.message);
            btn.disabled = false;
            btn.textContent = 'Book';
          }
        });
      });
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Parents' Evening</h1>` +
        this._emptyState('Could not load events', err.message, '⚠️');
    }
  },

  // ── Notifications ────────────────────────────────────────────────
  async renderNotifications(container) {
    container.innerHTML = `<h1 class="section-title">Notifications</h1>` + this._skeletonHtml();
    try {
      const data = await apiFetch('/notifications');
      const notifs = data.data || [];

      let html = `<h1 class="section-title">Notifications</h1>`;
      if (notifs.length === 0) {
        html += this._emptyState('No notifications', 'You\'re all caught up!', '🎉');
      } else {
        html += `<div class="card">`;
        notifs.forEach(n => {
          html += `
            <div class="list-item" style="${!n.is_read ? 'background:var(--color-primary-lt)' : ''}">
              <div class="list-item__icon" style="font-size:1.2rem">🔔</div>
              <div class="list-item__content">
                <div class="list-item__title">${_esc(n.title || 'Notification')}</div>
                <div class="list-item__meta">${_esc(n.message || '')} · ${formatDate(n.created_at)}</div>
              </div>
              ${!n.is_read ? '<span class="badge" style="position:static;min-width:8px;height:8px;padding:0;border-radius:50%"></span>' : ''}
            </div>`;
        });
        html += `</div>`;
      }
      container.innerHTML = html;
    } catch (err) {
      container.innerHTML = `<h1 class="section-title">Notifications</h1>` +
        this._emptyState('Could not load notifications', err.message, '⚠️');
    }
  },

  // ── Settings ─────────────────────────────────────────────────────
  renderSettings(container) {
    const token = Store.get(TOKEN_KEY);
    let user = {};
    try {
      const parts = token.split('.');
      user = JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));
    } catch {}

    container.innerHTML = `
      <h1 class="section-title">Settings</h1>
      <div class="card">
        <div class="card__header"><span class="card__title">Account</span></div>
        <div class="card__body">
          <div class="list-item" style="padding:0 0 12px">
            <div class="child-avatar" style="width:48px;height:48px;font-size:1.1rem">${initials(user.username || 'U')}</div>
            <div>
              <div style="font-weight:700">${_esc(user.username || 'Parent')}</div>
              <div style="font-size:.8rem;color:var(--color-text-2)">Parent account</div>
            </div>
          </div>
          <button class="btn btn--outline btn--full" onclick="ParentApp.logout()" style="margin-top:8px">
            Sign Out
          </button>
        </div>
      </div>

      <div class="card">
        <div class="card__header"><span class="card__title">Linked Children</span></div>
        <div class="card__body" style="padding:0">
          ${this.children.length === 0
            ? `<div style="padding:16px;text-align:center;color:var(--color-text-2);font-size:.875rem">No children linked</div>`
            : this.children.map(c => `
              <div class="list-item">
                <div class="child-avatar">${initials(c.name || c.child_student_id)}</div>
                <div class="list-item__content">
                  <div class="list-item__title">${_esc(c.name || c.child_student_id)}</div>
                  <div class="list-item__meta">${_esc(c.child_system_key)} · ${_esc(c.relationship || 'parent')}</div>
                </div>
              </div>`).join('')}
        </div>
      </div>

      <div class="card">
        <div class="card__header"><span class="card__title">Notifications</span></div>
        <div class="card__body">
          <label style="display:flex;align-items:center;justify-content:space-between;min-height:44px;cursor:pointer">
            <span>Push Notifications</span>
            <input type="checkbox" id="push-toggle" style="width:20px;height:20px;cursor:pointer" ${Notification.permission === 'granted' ? 'checked' : ''}>
          </label>
        </div>
      </div>

      <div class="card">
        <div class="card__header"><span class="card__title">App</span></div>
        <div class="card__body" style="display:flex;flex-direction:column;gap:4px">
          <div style="font-size:.875rem;color:var(--color-text-2)">Version 1.0.0</div>
          <div style="font-size:.875rem;color:var(--color-text-2)">Parent Portal — Education System</div>
        </div>
      </div>`;

    // Push toggle
    const pushToggle = el('push-toggle');
    if (pushToggle) {
      pushToggle.addEventListener('change', async (e) => {
        if (e.target.checked) {
          const perm = await Notification.requestPermission();
          if (perm !== 'granted') {
            e.target.checked = false;
            Toast.warn('Notifications permission denied');
          } else {
            Toast.success('Push notifications enabled');
          }
        }
      });
    }
  },

  // ── Service worker registration ──────────────────────────────────
  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/parent/static/sw.js', { scope: '/parent/' })
        .then(() => console.log('[ParentPortal] Service worker registered'))
        .catch(err => console.warn('[ParentPortal] SW registration failed:', err));
    }

    // Listen for offline sync messages
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data?.type === 'SYNC_MESSAGES') {
          Toast.warn('Syncing queued messages…');
        }
      });
    }
  },
};

// ── Boot ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => ParentApp.init());
