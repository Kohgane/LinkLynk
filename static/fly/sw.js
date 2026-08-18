self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());
self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() =>
    new Response('<h1 style="color:#fff;background:#000;height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif">오프라인 — 하늘은 인터넷이 필요해요</h1>',
    {headers:{'Content-Type':'text/html; charset=utf-8'}})));
});
