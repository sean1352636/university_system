// Shared auth helper for the University System web UI.
//
// Talks to the unified Flask API (python run.py --api) — single source of
// truth for user accounts is the shared auth.db. No hardcoded users here.
//
// Endpoints used:
//   POST  /api/v1/auth/login         → { token, refresh_token, user } or { mfa_required, mfa_token, ... }
//   POST  /api/v1/auth/mfa/verify    → { token, refresh_token, user }
//   GET   /api/v1/auth/me            → { user }

(function (global) {
    'use strict';

    // API base URL. Override via localStorage.setItem('api_base_url', 'http://host:port')
    // for alternative deployments.
    const DEFAULT_API = 'http://localhost:5000';
    const API_BASE = (localStorage.getItem('api_base_url') || DEFAULT_API).replace(/\/$/, '');
    const API_PREFIX = '/api/v1';

    const SESSION_KEY = 'uni_session';

    function apiUrl(path) {
        return API_BASE + API_PREFIX + path;
    }

    async function parseError(response) {
        let msg = `Request failed (${response.status})`;
        try {
            const data = await response.json();
            if (data && (data.error || data.message)) {
                msg = data.error || data.message;
            }
        } catch (_) { /* ignore */ }
        return new Error(msg);
    }

    async function postJson(path, body, headers) {
        let response;
        try {
            response = await fetch(apiUrl(path), {
                method: 'POST',
                headers: Object.assign(
                    { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                    headers || {},
                ),
                body: JSON.stringify(body || {}),
            });
        } catch (netErr) {
            throw new Error(
                `Cannot reach API at ${API_BASE}. Start it with:\n  python run.py --api`
            );
        }
        if (!response.ok) throw await parseError(response);
        return response.json();
    }

    async function getJson(path, token) {
        let response;
        try {
            response = await fetch(apiUrl(path), {
                headers: {
                    'Accept': 'application/json',
                    'Authorization': 'Bearer ' + token,
                },
            });
        } catch (netErr) {
            throw new Error(`Cannot reach API at ${API_BASE}.`);
        }
        if (!response.ok) throw await parseError(response);
        return response.json();
    }

    // ── Role resolution ────────────────────────────────────────────────
    //
    // The API returns the user's access list across all four systems:
    //     systems: [{ system_key, role }, ...]
    //
    // For the University web UI we need one role. Resolution rules:
    //   • If the user is admin of all 4 systems → 'superadmin'
    //   • Else the role on the 'university' system
    //   • Else null (no university access → login refused in the UI)

    function resolveRole(systems) {
        if (!Array.isArray(systems) || systems.length === 0) return null;

        const adminSystems = new Set(
            systems.filter(s => s.role === 'admin').map(s => s.system_key)
        );
        const ALL = ['university', 'college', 'school', 'primary'];
        if (ALL.every(k => adminSystems.has(k))) return 'superadmin';

        const uni = systems.find(s => s.system_key === 'university');
        return uni ? uni.role : null;
    }

    // Build the session object stored in sessionStorage. All dashboards read
    // from this shape.
    function buildSession(apiResult) {
        const user = apiResult.user || {};
        const role = resolveRole(user.systems || []);
        return {
            user_id: user.user_id,
            username: user.username,
            name: user.display_name || user.username,
            display_name: user.display_name || user.username,
            email: user.email || null,
            role: role,
            systems: user.systems || [],
            token: apiResult.token || null,
            refresh_token: apiResult.refresh_token || null,
            login_time: new Date().toISOString(),
        };
    }

    // ── Session storage helpers ────────────────────────────────────────

    function saveSession(session) {
        sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    }
    function getSession() {
        const raw = sessionStorage.getItem(SESSION_KEY);
        if (!raw) return null;
        try { return JSON.parse(raw); } catch (_) { return null; }
    }
    function clearSession() {
        sessionStorage.removeItem(SESSION_KEY);
    }

    // ── API calls ──────────────────────────────────────────────────────

    async function login(username, password) {
        return postJson('/auth/login', { username, password });
    }

    async function verifyMfa(mfaToken, code) {
        return postJson('/auth/mfa/verify', { code }, {
            'Authorization': 'Bearer ' + mfaToken,
        });
    }

    async function getMe() {
        const sess = getSession();
        if (!sess || !sess.token) throw new Error('Not logged in');
        return getJson('/auth/me', sess.token);
    }

    // Expose
    global.AuthClient = {
        API_BASE,
        API_PREFIX,
        login,
        verifyMfa,
        getMe,
        resolveRole,
        buildSession,
        saveSession,
        getSession,
        clearSession,
    };
})(window);
