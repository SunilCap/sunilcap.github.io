// Scotcha service worker: makes games installable and playable offline.
// Bump VERSION whenever you want every player to refresh their cached copy.
const VERSION = 'scotcha-v7';

// Pages and files to save for offline play. Add the URL of every game here.
// A URL that doesn't exist is skipped, so it's safe to list games before they're live.
const PRECACHE = [
  '/',
  '/games/',
  '/404.html',
  '/games/rocket-dash/guide.html',
  '/games/stack-up/guide.html',
  '/games/volleyball-duel/guide.html',
  '/games/word-tower/guide.html',
  '/games/rocket-dash/',
  '/games/word-tower/',
  '/games/volleyball-duel/',
  '/about.html',
  '/manifest.webmanifest',
  '/games/rocket-dash/manifest.webmanifest',
  '/games/word-tower/manifest.webmanifest',
  '/icons/rocket-dash-192.png',
  '/icons/rocket-dash-512.png',
  '/icons/word-tower-192.png',
  '/icons/word-tower-512.png',
  '/games/volleyball-duel/manifest.webmanifest',
  '/icons/volleyball-duel-192.png',
  '/icons/volleyball-duel-512.png',
  '/games/stack-up/',
  '/games/stack-up/manifest.webmanifest',
  '/icons/stack-up-192.png',
  '/icons/stack-up-512.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
  '/icons/apple-touch-icon.png',
  '/icons/favicon-64.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(VERSION)
      .then(cache => Promise.allSettled(PRECACHE.map(url => cache.add(new Request(url, { cache: 'reload' })))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Only handle our own files. Ads, dictionary lookups and fonts always go straight to the network.
  if (url.origin !== location.origin) return;

  // Pages: try the network first so updates arrive, fall back to the saved copy offline.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(res => { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); return res; })
        .catch(() => caches.match(req).then(hit => hit || caches.match('/')))
    );
    return;
  }

  // Everything else: show the saved copy instantly, refresh it in the background.
  event.respondWith(
    caches.match(req).then(hit => {
      const refresh = fetch(req)
        .then(res => { if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); } return res; })
        .catch(() => hit);
      return hit || refresh;
    })
  );
});
