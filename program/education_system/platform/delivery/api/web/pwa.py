"""Progressive Web App (PWA) support for the education system web interface.

Provides the service worker, manifest, and offline fallback page
so the web UI can work as an installable mobile-friendly app.
"""

import json
import logging
from flask import Blueprint, Response, render_template_string

logger = logging.getLogger(__name__)

pwa_bp = Blueprint("pwa", __name__)

_MANIFEST = {
    "name": "Education System",
    "short_name": "EduSys",
    "description": "Comprehensive Education Management System",
    "start_url": "/web/login",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#1a73e8",
    "orientation": "any",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
    "categories": ["education", "productivity"],
}

_SERVICE_WORKER = """\
const CACHE_NAME = 'edusys-v1';
const OFFLINE_URL = '/offline';
const PRECACHE_URLS = [
    '/web/login',
    '/offline',
    '/static/css/style.css',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => caches.match(OFFLINE_URL))
        );
        return;
    }
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
});
"""

_OFFLINE_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Offline - Education System</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center; min-height: 100vh;
               margin: 0; background: #f5f5f5; color: #333; }
        .container { text-align: center; padding: 2rem; max-width: 400px; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        p { color: #666; line-height: 1.6; }
        .icon { font-size: 3rem; margin-bottom: 1rem; }
        button { background: #1a73e8; color: white; border: none; padding: 0.75rem 1.5rem;
                 border-radius: 4px; cursor: pointer; font-size: 1rem; margin-top: 1rem; }
        button:hover { background: #1557b0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">&#x1F4F6;</div>
        <h1>You're Offline</h1>
        <p>The Education System requires an internet connection. Any changes you made while offline will be synced when connectivity returns.</p>
        <button onclick="window.location.reload()">Try Again</button>
    </div>
</body>
</html>
"""


@pwa_bp.route("/manifest.json")
def manifest():
    return Response(json.dumps(_MANIFEST, indent=2), mimetype="application/manifest+json")


@pwa_bp.route("/sw.js")
def service_worker():
    return Response(_SERVICE_WORKER, mimetype="application/javascript",
                    headers={"Service-Worker-Allowed": "/"})


@pwa_bp.route("/offline")
def offline():
    return _OFFLINE_PAGE
