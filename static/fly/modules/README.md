# SWEF Modules — 아키텍처 & 개발 가이드

## 개요

`static/fly/modules/` 는 CesiumJS 기반 3D 지구 비행 앱(`/fly/`)의 기능 확장 모듈 디렉터리입니다.  
`index.html` 수정 없이 `index.js` 진입점과 동적 로드를 통해 기능을 추가합니다.

---

## 아키텍처 규칙

| 규칙 | 내용 |
|------|------|
| 수정 가능 경로 | `static/fly/modules/` 내부 **전용** |
| 수정 금지 | `static/fly/index.html`, `app.py`, `static/fly/` 최상위 파일 |
| 전역 오염 금지 | 모든 코드는 IIFE 또는 모듈 스코프 내부 |
| `<script>` 추가 금지 | 서브모듈은 `index.js`에서 동적 import로 로드 |
| UI 원칙 | `document.body`에 자체 컨테이너를 append. ID 접두사: `swefm-` |
| 기존 DOM 참조 금지 | `#panel`, `.tabb` 등 하드코딩 금지. 없으면 자체 UI 폴백 |
| 저장 키 | `swefm_` 접두사 사용. `ef_*` 키 읽기/쓰기 금지 |
| 외부 라이브러리 금지 | 순수 JS + 브라우저 API만 (Cesium 제외) |
| 네트워크 요청 금지 | Cesium 타일 외 추가 요청 금지 |
| 오류 처리 | 모든 초기화는 `try/catch`, 실패 시 `console.warn` |
| 모바일 우선 | 터치 이벤트 `{ passive:false }`, 버튼 최소 44px |

---

## 훅 / 전역 API

```javascript
// SWEF 훅 (index.html이 제공)
window.SWEF = {
  viewer,       // CesiumJS Viewer 인스턴스
  camera,       // viewer.camera 단축
  DESTS,        // 목적지 배열
  TRACKS,       // 트랙 배열
  FILMS,        // 영화 배열
  MOMENTS,      // 모먼트 배열
  isTouch,      // 터치 환경 여부
  lang,         // 언어 문자열
  toast(msg),   // 토스트 메시지
  goFree(),     // 자유비행 모드
  goSpace(),    // 우주 뷰
  flyToDest(i), // 목적지 인덱스로 이동
  setFilm(i),   // 필름 설정
  playMoment(i) // 모먼트 재생
};

// SWEFM 모듈 API (index.js가 제공)
window.SWEFM = {
  waitViewer(cb, tries), // viewer 준비 대기 후 콜백 실행
  version                // "0.2"
};
```

### 초기화 패턴

```javascript
window.addEventListener("swef:ready", e => init(e.detail));
if (window.SWEF && window.SWEF.viewer) init(window.SWEF);
```

### Viewer 접근

```javascript
window.SWEFM.waitViewer(viewer => {
  // viewer 준비 완료 후 실행
});
```

---

## 모듈 설명

### `index.js` — 진입점
- `window.SWEFM.waitViewer` 제공
- `favorites.js`, `replay.js`, `hud.js`를 동적 import로 로드
- `swef:ready` 이벤트 및 즉시 준비 상태 모두 처리
- 중복 초기화 방지

### `favorites.js` — 즐겨찾기 & 히스토리
- **저장키**: `swefm_favs`, `swefm_history`
- 현재 카메라 위치 즐겨찾기 저장 (이름 자동 생성 또는 직접 입력)
- 저장 목록 패널 → 탭하면 `viewer.camera.flyTo`로 이동
- 최근 방문 20곳 자동 기록 (중복 제거)
- 최근 방문 → 즐겨찾기로 승격
- JSON 내보내기 / 가져오기 (병합 방식)
- 30초마다 현재 위치를 히스토리에 자동 기록

### `replay.js` — 비행 리플레이
- **저장키**: `swefm_replays`
- 0.2초 간격 카메라 샘플링 (링버퍼, 최대 5분)
- 선형 보간으로 부드러운 재생
- 재생 속도 0.5× / 1× / 2× 선택
- ESC 또는 탭으로 재생 중단
- 최대 5개 슬롯에 저장/불러오기
- 재생 중 화면 하단에 진행바 표시

### `hud.js` — 좌표 HUD & 나침반
- **저장키**: `swefm_hud_visible`
- 우상단: 위도/경도/고도/속도/방위 실시간 표시
- 클릭 시 좌표를 클립보드에 복사
- SVG 나침반 — 카메라 방위에 따라 회전
- 🧭 버튼으로 HUD 토글 (상태 저장)

---

## 새 모듈 추가 방법

1. `static/fly/modules/새모듈.js` 생성
2. 파일 상단 주석:
   ```javascript
   /* 새모듈.js — [목적]
    * 목적: [설명]
    * 의존성: window.SWEFM.waitViewer, window.Cesium (선택)
    * 저장키: swefm_[키명]
    */
   ```
3. 전체 코드를 IIFE로 감싸기:
   ```javascript
   (function () {
     "use strict";
     // ...
     function init() {
       try {
         window.SWEFM.waitViewer(viewer => {
           try { buildUI(viewer); } catch (e) { console.warn("[swefm/새모듈] 초기화 실패", e); }
         });
       } catch (e) { console.warn("[swefm/새모듈] 초기화 실패", e); }
     }
     init();
   })();
   ```
4. `index.js`의 `MODULES` 배열에 `"새모듈.js"` 추가
5. 이 README에 모듈 설명 추가

---

## UI 가이드

- **컨테이너 ID**: `swefm-{모듈명}-{컴포넌트}` (예: `swefm-hud-box`)
- **버튼 최소 크기**: 44×44px (모바일 터치 대응)
- **배경**: `rgba(0,0,0,.65)` 내외
- **z-index 범위**: 8800~9100 (기존 앱 UI와 충돌 방지)
- **터치 이벤트**: `{ passive: false }` 명시

---

## 저장 키 목록

| 키 | 모듈 | 내용 |
|----|------|------|
| `swefm_favs` | favorites.js | 즐겨찾기 배열 |
| `swefm_history` | favorites.js | 최근 방문 배열 |
| `swefm_replays` | replay.js | 리플레이 슬롯 배열 |
| `swefm_hud_visible` | hud.js | HUD 표시 상태 |
