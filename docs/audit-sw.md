# static/fly/sw.js 캐시 전략 감사

## 현재(수정 전) 전략

### 캐시 이름/버전 관리
- 캐시 이름 상수, 버전 상수, 캐시 정리 로직이 없었습니다.

### 이벤트 동작
- `install`: `self.skipWaiting()`만 수행.
- `activate`: `self.clients.claim()`만 수행.
- `fetch`: 모든 요청을 `fetch(request)`로 처리하고, 네트워크 실패 시 오프라인 HTML 문자열을 응답.

### precache / runtime cache
- precache 목록 없음.
- runtime cache 저장 로직 없음.

## 문제점
- `/fly/modules/*.js`가 캐시되지 않아 오프라인/느린 네트워크에서 모듈 로드 실패 가능성이 있었습니다.
- 네트워크 실패 시 JS/CSS/API 요청에도 HTML fallback이 내려갈 수 있어 리소스 타입 불일치 위험이 있습니다.

## Cesium CDN·타일 요청을 캐싱하지 않아야 하는 이유
- Cesium CDN 및 imagery/terrain/tile 요청은 데이터 크기와 요청 수가 매우 커질 수 있습니다.
- 서비스워커 캐시에 저장 시 캐시 용량 급증(폭발)과 eviction(축출)로 핵심 앱 자원이 밀려날 위험이 큽니다.
- 외부/대용량 타일은 네트워크 경로로만 처리하고 앱 핵심 정적 자원만 캐싱하는 것이 안전합니다.

## 이번 변경 후 의도한 전략

### 캐시 버전/정리
- `CACHE_VERSION = 'v2'`, `APP_CACHE = fly-app-v2` 도입.
- `activate`에서 현재 캐시 외 나머지 캐시 삭제로 버전 무효화 보장.

### precache
- `install`에서 모듈 JS를 precache:
  - `/fly/modules/index.js`
  - `/fly/modules/launcher.js`
  - `/fly/modules/favorites.js`
  - `/fly/modules/replay.js`
  - `/fly/modules/hud.js`
  - `/fly/modules/share.js`
  - `/fly/modules/compare.js`

### fetch 전략
- 모듈 JS 요청: **stale-while-revalidate**
  - 캐시 hit 시 즉시 반환
  - 백그라운드 네트워크 갱신 후 캐시 업데이트
  - 캐시 miss 시 네트워크 응답 사용 + 성공 응답 캐시 저장
  - 네트워크 실패 시 캐시가 있으면 캐시 사용, 없으면 503 응답
- Cesium CDN/imagery/terrain/tile 패턴은 캐싱 처리에서 제외.
- 그 외 same-origin GET 요청은 기존과 유사하게 네트워크 우선 + 실패 시 오프라인 HTML fallback.
