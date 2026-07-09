// 캐시 완전 비활성화 - 항상 네트워크에서 최신 파일
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// fetch 가로채지 않음 = 브라우저 기본 (네트워크)
