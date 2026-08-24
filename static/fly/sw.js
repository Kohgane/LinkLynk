const CACHE_VERSION = 'v2';
const APP_CACHE = `fly-app-${CACHE_VERSION}`;
const MODULE_PATHS = [
  '/fly/modules/index.js',
  '/fly/modules/launcher.js',
  '/fly/modules/favorites.js',
  '/fly/modules/replay.js',
  '/fly/modules/hud.js',
  '/fly/modules/share.js',
  '/fly/modules/compare.js'
];

const OFFLINE_HTML = '<h1 style="color:#fff;background:#000;height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif">오프라인 — 하늘은 인터넷이 필요해요</h1>';

const TILE_OR_CESIUM_RE = /(cesium\.com|cesium\.js|imagery|terrain|tile)/i;

async function putInCache(request, response) {
  try {
    if (!response || !response.ok || response.type === 'opaque') return;
    const cache = await caches.open(APP_CACHE);
    await cache.put(request, response.clone());
  } catch (_err) {}
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(APP_CACHE);
    await cache.addAll(MODULE_PATHS);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(key => (key !== APP_CACHE ? caches.delete(key) : Promise.resolve())));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  const isModuleRequest = MODULE_PATHS.includes(url.pathname);
  const isCesiumOrTile = TILE_OR_CESIUM_RE.test(req.url);
  if (isCesiumOrTile) return;

  if (isModuleRequest) {
    event.respondWith((async () => {
      const cache = await caches.open(APP_CACHE);
      const cached = await cache.match(req);
      const networkUpdate = fetch(req)
        .then(res => {
          putInCache(req, res);
          return res;
        })
        .catch(() => null);

      if (cached) {
        event.waitUntil(networkUpdate);
        return cached;
      }

      const fresh = await networkUpdate;
      if (fresh) return fresh;
      return new Response('', { status: 503, statusText: 'Service Unavailable' });
    })());
    return;
  }

  event.respondWith(
    fetch(req).catch(() => new Response(OFFLINE_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }))
  );
});
