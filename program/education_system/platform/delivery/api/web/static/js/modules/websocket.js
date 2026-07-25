/**
 * WebSocketManager – Socket.IO client for the Education System.
 *
 * Provides:
 *   - JWT-authenticated connections to /notifications, /chat, /presence
 *   - Auto-reconnect with exponential backoff
 *   - Notification toast renderer
 *   - Chat panel UI (room list, message area, input, typing indicator)
 *   - Presence indicators (green dot for online users)
 *
 * Usage:
 *   import { WebSocketManager } from './modules/websocket.js';
 *   const ws = new WebSocketManager({ token: 'your.jwt.token' });
 *   ws.connect();
 */

/* global io */  // Socket.IO client loaded via CDN

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const RECONNECT_BASE_MS   = 1000;
const RECONNECT_MAX_MS    = 30000;
const RECONNECT_FACTOR    = 2;
const TOAST_DURATION_MS   = 5000;
const TYPING_DEBOUNCE_MS  = 1500;

// ---------------------------------------------------------------------------
// Helper – build Socket.IO options with JWT auth
// ---------------------------------------------------------------------------
function _socketOpts(token, extraOpts = {}) {
  return {
    auth: { token },
    query: { token },
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: RECONNECT_BASE_MS,
    reconnectionDelayMax: RECONNECT_MAX_MS,
    randomizationFactor: 0.3,
    ...extraOpts,
  };
}

// ---------------------------------------------------------------------------
// Toast notification renderer
// ---------------------------------------------------------------------------
class ToastRenderer {
  constructor() {
    this._container = null;
  }

  _ensureContainer() {
    if (this._container) return this._container;
    let el = document.getElementById('ws-toast-container');
    if (!el) {
      el = document.createElement('div');
      el.id = 'ws-toast-container';
      el.style.cssText = [
        'position:fixed', 'top:1rem', 'right:1rem', 'z-index:9999',
        'display:flex', 'flex-direction:column', 'gap:0.5rem',
        'max-width:360px', 'pointer-events:none',
      ].join(';');
      document.body.appendChild(el);
    }
    this._container = el;
    return el;
  }

  show(title, body = '', type = 'info') {
    const container = this._ensureContainer();
    const colours = {
      info:    '#3b82f6',
      success: '#22c55e',
      warning: '#f59e0b',
      error:   '#ef4444',
    };
    const accent = colours[type] || colours.info;

    const toast = document.createElement('div');
    toast.style.cssText = [
      'background:#1e293b', 'color:#f1f5f9', 'border-radius:0.5rem',
      'padding:0.75rem 1rem', 'box-shadow:0 4px 12px rgba(0,0,0,0.4)',
      `border-left:4px solid ${accent}`, 'pointer-events:auto',
      'opacity:0', 'transform:translateX(100%)',
      'transition:opacity 0.25s,transform 0.25s',
    ].join(';');
    toast.innerHTML = `
      <div style="font-weight:600;font-size:0.875rem;margin-bottom:0.25rem">${_esc(title)}</div>
      ${body ? `<div style="font-size:0.8rem;opacity:0.8">${_esc(body)}</div>` : ''}
    `;
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateX(0)';
    });

    // Auto-remove
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, TOAST_DURATION_MS);
  }
}

function _esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Chat panel UI
// ---------------------------------------------------------------------------
class ChatPanel {
  constructor(manager) {
    this._mgr = manager;
    this._panel = null;
    this._activeRoom = null;
    this._typingTimer = null;
    this._rooms = [];
    this._messages = {};  // roomId → [message, ...]
  }

  // Build and inject panel DOM
  init() {
    if (this._panel) return;
    const panel = document.createElement('div');
    panel.id = 'ws-chat-panel';
    panel.style.cssText = [
      'position:fixed', 'bottom:1rem', 'right:1rem',
      'width:340px', 'height:480px', 'background:#1e293b',
      'border-radius:0.75rem', 'box-shadow:0 8px 32px rgba(0,0,0,0.5)',
      'display:flex', 'flex-direction:column', 'overflow:hidden',
      'z-index:9998', 'font-family:Inter,sans-serif', 'color:#f1f5f9',
    ].join(';');
    panel.innerHTML = `
      <div id="ws-chat-header" style="padding:0.75rem 1rem;background:#0f172a;
           display:flex;align-items:center;justify-content:space-between;
           font-weight:600;font-size:0.9rem;cursor:pointer;user-select:none">
        <span>&#128172; Chat</span>
        <span id="ws-chat-unread" style="background:#ef4444;color:#fff;
              border-radius:9999px;padding:0 0.4rem;font-size:0.75rem;display:none">0</span>
        <button id="ws-chat-close" style="background:none;border:none;color:#94a3b8;
                font-size:1.1rem;cursor:pointer;padding:0 0.25rem">&#x2715;</button>
      </div>
      <div id="ws-chat-body" style="display:flex;flex:1;overflow:hidden">
        <div id="ws-chat-rooms" style="width:110px;background:#0f172a;overflow-y:auto;
             border-right:1px solid #334155;padding:0.5rem 0"></div>
        <div style="flex:1;display:flex;flex-direction:column">
          <div id="ws-chat-messages" style="flex:1;overflow-y:auto;padding:0.5rem;
               font-size:0.8rem;display:flex;flex-direction:column;gap:0.35rem"></div>
          <div id="ws-chat-typing" style="font-size:0.7rem;color:#64748b;
               padding:0 0.5rem;min-height:1rem"></div>
          <div style="display:flex;padding:0.5rem;gap:0.4rem">
            <input id="ws-chat-input" placeholder="Type a message…"
                   style="flex:1;background:#0f172a;border:1px solid #334155;
                          border-radius:0.375rem;padding:0.4rem 0.6rem;
                          color:#f1f5f9;font-size:0.8rem;outline:none" />
            <button id="ws-chat-send" style="background:#3b82f6;color:#fff;
                    border:none;border-radius:0.375rem;padding:0.4rem 0.75rem;
                    cursor:pointer;font-size:0.8rem">Send</button>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(panel);
    this._panel = panel;
    this._bindEvents();
  }

  _bindEvents() {
    const sendBtn  = document.getElementById('ws-chat-send');
    const input    = document.getElementById('ws-chat-input');
    const closeBtn = document.getElementById('ws-chat-close');

    sendBtn.addEventListener('click', () => this._send());
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._send(); }
      this._emitTyping();
    });
    closeBtn.addEventListener('click', () => { this._panel.style.display = 'none'; });
  }

  _emitTyping() {
    if (!this._activeRoom) return;
    this._mgr._chat && this._mgr._chat.emit('typing', {
      room_id: this._activeRoom, typing: true,
    });
    clearTimeout(this._typingTimer);
    this._typingTimer = setTimeout(() => {
      this._mgr._chat && this._mgr._chat.emit('typing', {
        room_id: this._activeRoom, typing: false,
      });
    }, TYPING_DEBOUNCE_MS);
  }

  _send() {
    if (!this._activeRoom) return;
    const input = document.getElementById('ws-chat-input');
    const text = (input.value || '').trim();
    if (!text) return;
    this._mgr._chat && this._mgr._chat.emit('chat_message', {
      room_id: this._activeRoom, message: text,
    });
    input.value = '';
  }

  updateRooms(rooms) {
    this._rooms = rooms;
    const container = document.getElementById('ws-chat-rooms');
    if (!container) return;
    container.innerHTML = '';
    rooms.forEach(room => {
      const div = document.createElement('div');
      div.style.cssText = [
        'padding:0.5rem;cursor:pointer;font-size:0.75rem;border-radius:0.25rem',
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis',
      ].join(';');
      div.textContent = room.name;
      div.title = room.name;
      div.dataset.roomId = room.id;
      div.addEventListener('click', () => this.selectRoom(room.id));
      if (room.id === this._activeRoom) {
        div.style.background = '#1e40af';
      }
      container.appendChild(div);
    });
  }

  selectRoom(roomId) {
    this._activeRoom = roomId;
    this._mgr._chat && this._mgr._chat.emit('join_room', { room_id: roomId });
    const msgs = this._messages[roomId] || [];
    this._renderMessages(msgs);
    // Re-render room list to update selection highlight
    this.updateRooms(this._rooms);
  }

  appendMessage(msg) {
    const roomId = msg.room_id;
    if (!this._messages[roomId]) this._messages[roomId] = [];
    this._messages[roomId].push(msg);
    if (roomId === this._activeRoom) {
      this._renderMessages(this._messages[roomId]);
    }
    // Update unread badge
    this._updateUnread();
  }

  _renderMessages(msgs) {
    const container = document.getElementById('ws-chat-messages');
    if (!container) return;
    container.innerHTML = '';
    msgs.forEach(m => {
      const div = document.createElement('div');
      div.style.cssText = 'background:#0f172a;border-radius:0.375rem;padding:0.35rem 0.5rem';
      div.innerHTML = `
        <span style="color:#60a5fa;font-weight:600;font-size:0.7rem">User ${m.sender_id}</span>
        <span style="margin-left:0.35rem">${_esc(m.message_text || m.message || '')}</span>
      `;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  }

  showTyping(userId, isTyping) {
    const el = document.getElementById('ws-chat-typing');
    if (!el) return;
    el.textContent = isTyping ? `User ${userId} is typing…` : '';
  }

  _updateUnread() {
    const badge = document.getElementById('ws-chat-unread');
    if (!badge) return;
    let total = 0;
    Object.entries(this._messages).forEach(([roomId, msgs]) => {
      if (parseInt(roomId) !== this._activeRoom) total += msgs.length;
    });
    if (total > 0) {
      badge.textContent = total > 99 ? '99+' : String(total);
      badge.style.display = 'inline';
    } else {
      badge.style.display = 'none';
    }
  }

  show() {
    if (this._panel) this._panel.style.display = 'flex';
  }
}

// ---------------------------------------------------------------------------
// Presence tracker
// ---------------------------------------------------------------------------
class PresenceTracker {
  constructor() {
    this._online = new Set();
  }

  setOnline(userId) {
    this._online.add(userId);
    this._updateDot(userId, true);
  }

  setOffline(userId) {
    this._online.delete(userId);
    this._updateDot(userId, false);
  }

  isOnline(userId) {
    return this._online.has(userId);
  }

  /** Find any element with data-user-id and add/remove an online dot. */
  _updateDot(userId, online) {
    document.querySelectorAll(`[data-user-id="${userId}"]`).forEach(el => {
      let dot = el.querySelector('.ws-presence-dot');
      if (!dot) {
        dot = document.createElement('span');
        dot.className = 'ws-presence-dot';
        dot.style.cssText = [
          'display:inline-block', 'width:8px', 'height:8px',
          'border-radius:50%', 'margin-left:4px', 'vertical-align:middle',
        ].join(';');
        el.appendChild(dot);
      }
      dot.style.background = online ? '#22c55e' : '#64748b';
      dot.title = online ? 'Online' : 'Offline';
    });
  }
}

// ---------------------------------------------------------------------------
// WebSocketManager – main export
// ---------------------------------------------------------------------------
export class WebSocketManager {
  /**
   * @param {object} opts
   * @param {string}  opts.token      - JWT access token
   * @param {string}  [opts.host]     - server host (default: window.location.origin)
   * @param {boolean} [opts.chat]     - enable chat panel (default: true)
   * @param {boolean} [opts.presence] - enable presence tracking (default: true)
   */
  constructor(opts = {}) {
    this._token    = opts.token || '';
    this._host     = opts.host  || window.location.origin;
    this._useChat  = opts.chat     !== false;
    this._usePres  = opts.presence !== false;

    this._notif    = null;  // /notifications socket
    this._chat     = null;  // /chat socket
    this._pres     = null;  // /presence socket

    this._toast    = new ToastRenderer();
    this._chatUI   = this._useChat ? new ChatPanel(this) : null;
    this._presence = this._usePres ? new PresenceTracker() : null;

    this._handlers = {};  // custom event → [callback, ...]
  }

  /** Set (or refresh) the JWT token used for auth. */
  setToken(token) {
    this._token = token;
  }

  /** Connect all namespaces. */
  connect() {
    if (typeof io === 'undefined') {
      console.warn('[WS] Socket.IO client not loaded – skipping WebSocket init');
      return;
    }
    this._connectNotifications();
    if (this._useChat)  this._connectChat();
    if (this._usePres)  this._connectPresence();
    if (this._chatUI)   this._chatUI.init();
  }

  /** Disconnect all sockets. */
  disconnect() {
    [this._notif, this._chat, this._pres].forEach(s => s && s.disconnect());
  }

  // ---- /notifications ----
  _connectNotifications() {
    this._notif = io(`${this._host}/notifications`, _socketOpts(this._token));

    this._notif.on('connect', () => {
      console.info('[WS] /notifications connected');
      this._emit('notifications:connect');
    });
    this._notif.on('disconnect', (reason) => {
      console.info('[WS] /notifications disconnected:', reason);
      this._emit('notifications:disconnect', reason);
    });
    this._notif.on('notification', (data) => {
      this._toast.show(data.title || 'Notification', data.body || '', data.notification_type || 'info');
      this._emit('notification', data);
    });
    this._notif.on('connect_error', (err) => {
      console.warn('[WS] /notifications error:', err.message);
    });
  }

  // ---- /chat ----
  _connectChat() {
    this._chat = io(`${this._host}/chat`, _socketOpts(this._token));

    this._chat.on('connect', () => {
      console.info('[WS] /chat connected');
    });
    this._chat.on('chat_message', (data) => {
      if (this._chatUI) this._chatUI.appendMessage(data);
      this._emit('chat:message', data);
    });
    this._chat.on('typing', (data) => {
      if (this._chatUI) this._chatUI.showTyping(data.user_id, data.typing);
      this._emit('chat:typing', data);
    });
    this._chat.on('connect_error', (err) => {
      console.warn('[WS] /chat error:', err.message);
    });
  }

  // ---- /presence ----
  _connectPresence() {
    this._pres = io(`${this._host}/presence`, _socketOpts(this._token));

    this._pres.on('connect', () => {
      console.info('[WS] /presence connected');
    });
    this._pres.on('presence_update', (data) => {
      if (this._presence) {
        if (data.status === 'online') this._presence.setOnline(data.user_id);
        else                          this._presence.setOffline(data.user_id);
      }
      this._emit('presence:update', data);
    });
    this._pres.on('connect_error', (err) => {
      console.warn('[WS] /presence error:', err.message);
    });
  }

  // ---- Public API ----

  /** Join a notification room (e.g. 'university:admin'). */
  joinRoom(room) {
    this._notif && this._notif.emit('join_room', { room });
  }

  /** Leave a notification room. */
  leaveRoom(room) {
    this._notif && this._notif.emit('leave_room', { room });
  }

  /** Open the chat panel and optionally select a room. */
  openChat(roomId) {
    if (this._chatUI) {
      this._chatUI.show();
      if (roomId !== undefined) this._chatUI.selectRoom(roomId);
    }
  }

  /** Update the room list displayed in the chat panel. */
  setChatRooms(rooms) {
    this._chatUI && this._chatUI.updateRooms(rooms);
  }

  /** Show a toast manually. */
  notify(title, body, type = 'info') {
    this._toast.show(title, body, type);
  }

  /** Check if a user is online (requires presence namespace). */
  isOnline(userId) {
    return this._presence ? this._presence.isOnline(userId) : false;
  }

  /** Register a custom event listener. */
  on(event, callback) {
    if (!this._handlers[event]) this._handlers[event] = [];
    this._handlers[event].push(callback);
    return this;
  }

  /** Remove a custom event listener. */
  off(event, callback) {
    if (this._handlers[event]) {
      this._handlers[event] = this._handlers[event].filter(cb => cb !== callback);
    }
    return this;
  }

  // Internal event bus
  _emit(event, data) {
    (this._handlers[event] || []).forEach(cb => {
      try { cb(data); } catch (e) { console.error('[WS] handler error', e); }
    });
  }
}

export default WebSocketManager;
