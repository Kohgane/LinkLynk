const CACHE = 'linklynk-v1783593954';
// HTML/JS는 절대 캐시 안 함 (항상 최신). 이미지/아이콘만 캐시.
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) return;               // API: 네트워크
  if (url.pathname === '/' || url.pathname.includes('app.js')) return; // HTML/JS: 무조건 네트워크(캐시 안 함)
  // 이미지/아이콘만 캐시 우선
  if (/\.(png|jpg|jpeg|svg|ico|webp)$/.test(url.pathname)) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
      const c = resp.clone(); caches.open(CACHE).then(ch => ch.put(e.request, c)); return resp;
    })));
  }
});
