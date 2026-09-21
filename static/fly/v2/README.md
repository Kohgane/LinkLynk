`/fly/v2/`는 v1을 건드리지 않고 신규 렌더 코어로 접속하는 경로이며, 브라우저에서 `/fly/v2/`로 열면 됩니다. 진단은 쿼리 파라미터로 켜며 `?fps=1`은 FPS/최악 ms/처리 타일/해상도/SSE/거버너 티어/최근 오류 계기판을, `?probe=1`은 8초 간격 자동 순회 성능 표를, `?bare=1`은 `features.js`와 후처리/모듈 로더를 생략한 최소 코어 부팅을 뜻합니다.

---

## v1 영구 접근로

`/fly/legacy/` — 서버에서 `static/fly/index.html`(v1)을 서빙합니다.

---

## PWA 연결 스니펫 (제안)

이번 PR에서는 `static/fly/v2/index.html`을 수정하지 않았습니다.
`<head>` 안에 아래 3줄을 추가하면 설치형 앱(홈 화면 추가)이 활성화됩니다:

```html
<link rel="manifest" href="/fly/v2/manifest.webmanifest">
<meta name="theme-color" content="#05070d">
<script>if('serviceWorker' in navigator) navigator.serviceWorker.register('/fly/v2/sw.js', {scope:'/fly/v2/'});</script>
```

## 서비스 워커 scope

`sw.js`의 scope는 `/fly/v2/`로 한정됩니다. fetch handler에서 `/fly/v2/` 외 경로와
cross-origin 요청은 캐시하지 않고 네트워크로 직결합니다. `/fly/`(v1)는 절대 가로채지 않습니다.
