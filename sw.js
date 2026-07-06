const CACHE = 'linklynk-v3';  // 버전 올림 → 옛 캐시 폐기
const ASSETS = ['/', '/app.js', '/manifest.json', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) return;  // API는 캐시 안 함
  // HTML/JS는 네트워크 우선 (항상 최신), 실패 시 캐시
  if (url.pathname === '/' || url.pathname.endsWith('.js') || url.pathname.endsWith('.json')) {
    e.respondWith(
      fetch(e.request).then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return resp;
      }).catch(() => caches.match(e.request).then(r => r || caches.match('/')))
    );
    return;
  }
  // 이미지 등은 캐시 우선
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
