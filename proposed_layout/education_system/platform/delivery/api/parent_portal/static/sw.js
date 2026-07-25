/**
 * Parent Portal — Service Worker
 *
 * Strategy:
 *   - Static assets (JS/CSS/HTML/fonts): Cache-first with cache update in background.
 *   - API requests (/parent/api/*): Network-first; fall back to cached response on failure.
 *   - Push notifications: Displayed with action buttons.
 */

const CACHE_NAME   = 'parent-portal-v1';
const API_CACHE    = 'parent-portal-api-v1';
const OFFLINE_URL  = '/parent/';

const STATIC_ASSETS = [
  '/parent/',
  '/parent/static/css/parent.css',
  '/parent/static/js/parent_app.js',
  '/parent/static/manifest.json',
];

// ── Install ────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate ───────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests
  if (request.method !== 'GET') return;
  if (url.origin !== location.origin) return;

  if (url.pathname.startsWith('/parent/api/')) {
    // Network-first for API calls
    event.respondWith(networkFirstApi(request));
  } else if (
    url.pathname.startsWith('/parent/static/') ||
    url.pathname === '/parent/' ||
    url.pathname.startsWith('/parent/')
  ) {
    // Cache-first for static assets and SPA routes
    event.respondWith(cacheFirstStatic(request));
  }
});

// ── Cache strategies ───────────────────────────────────────────────────

async function cacheFirstStatic(request) {
  const cached = await caches.match(request);
  if (cached) {
    // Update in background (stale-while-revalidate)
    event_revalidate(request);
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Offline fallback: serve the SPA shell for navigation requests
    if (request.mode === 'navigate') {
      const fallback = await caches.match(OFFLINE_URL);
      if (fallback) return fallback;
    }
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

function event_revalidate(request) {
  fetch(request).then((response) => {
    if (response.ok) {
      caches.open(CACHE_NAME).then((cache) => cache.put(request, response));
    }
  }).catch(() => {});
}

async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request, { cacheName: API_CACHE });
    if (cached) {
      // Add a header so the app knows it's stale data
      const headers = new Headers(cached.headers);
      headers.set('X-Served-From-Cache', 'true');
      return new Response(cached.body, {
        status: cached.status,
        statusText: cached.statusText,
        headers,
      });
    }
    return new Response(
      JSON.stringify({ error: 'Offline — no cached data available', offline: true }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

// ── Push notifications ─────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  let data = { title: 'Parent Portal', body: 'You have a new notification.' };
  try {
    if (event.data) data = event.data.json();
  } catch {}

  const options = {
    body:    data.body || '',
    icon:    '/parent/static/icons/icon-192.png',
    badge:   '/parent/static/icons/icon-96.png',
    tag:     data.tag || 'parent-portal',
    data:    { url: data.url || '/parent/' },
    actions: [
      { action: 'view',    title: 'View' },
      { action: 'dismiss', title: 'Dismiss' },
    ],
    vibrate: [200, 100, 200],
    renotify: true,
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'Parent Portal', options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'dismiss') return;

  const targetUrl = (event.notification.data && event.notification.data.url)
    ? event.notification.data.url
    : '/parent/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes('/parent/') && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(targetUrl);
    })
  );
});

// ── Background sync (for queued messages) ─────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'send-message') {
    event.waitUntil(flushMessageQueue());
  }
});

async function flushMessageQueue() {
  // Opens IndexedDB outbox and retries failed POSTs
  // Implementation relies on the app storing failed requests in IDB
  const allClients = await clients.matchAll();
  for (const client of allClients) {
    client.postMessage({ type: 'SYNC_MESSAGES' });
  }
}
