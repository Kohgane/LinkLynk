/* SWEF v2 Service Worker — scope: /fly/v2/ only */
const SW_V = "swef-v2-1";
const CACHE = SW_V;

const APP_SHELL = [
  "/fly/v2/",
  "/fly/v2/index.html",
  "/fly/v2/js/data.js",
  "/fly/v2/js/engine.js",
  "/fly/v2/js/input.js",
  "/fly/v2/js/features.js",
  "/fly/v2/js/ui.js",
  "/fly/v2/manifest.webmanifest",
  "/fly/v2/icons/icon-192.png",
  "/fly/v2/icons/icon-512.png",
];

// Returns true if this request must NEVER be cached.
function isNoCacheRequest(request) {
  const url = new URL(request.url);

  // Cross-origin: always network-direct
  if (url.origin !== self.location.origin) return true;

  // Same-origin blocked paths
  const path = url.pathname;
  if (path.startsWith("/fly/av/")) return true;
  if (path.startsWith("/fly/sky/")) return true;

  return false;
}

// Returns true if this request is outside our scope — never intercept v1
function isOutOfScope(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false; // handled by isNoCacheRequest
  const path = url.pathname;
  // Only serve /fly/v2/ paths from cache; everything else passes through
  if (!path.startsWith("/fly/v2/")) return true;
  return false;
}

// Install: pre-cache the app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting())
  );
});

// Activate: delete old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: stale-while-revalidate for app shell; network-direct for everything else
self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only handle GET
  if (request.method !== "GET") return;

  // Never intercept v1 or out-of-scope same-origin paths
  if (isOutOfScope(request)) return;

  // Network-direct for no-cache resources
  if (isNoCacheRequest(request)) {
    event.respondWith(fetch(request));
    return;
  }

  // Stale-while-revalidate for app shell
  event.respondWith(
    caches.open(CACHE).then((cache) =>
      cache.match(request).then((cached) => {
        const networkFetch = fetch(request).then((response) => {
          if (response && response.status === 200) {
            cache.put(request, response.clone());
          }
          return response;
        });
        return cached || networkFetch;
      })
    )
  );
});
