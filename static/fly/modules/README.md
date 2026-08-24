# SWEF Modules — 아키텍처 가이드

## 개요
`static/fly/modules/` 는 CesiumJS 기반 지구 비행 앱(`/fly/`)의 **확장 기능 작업 영역**입니다.
`index.html`을 수정하지 않고, `index.js` 단일 진입점에서 서브모듈을 동적으로 로드합니다.

## 디렉터리 구조
```
modules/
├── index.js        # 진입점. window.SWEFM 초기화, 서브모듈 동적 로드
├── favorites.js    # 즐겨찾기 & 히스토리
├── replay.js       # 비행 리플레이
├── hud.js          # 좌표 HUD & 나침반
└── README.md       # 본 문서
```

## 아키텍처 규칙

| 규칙 | 내용 |
|------|------|
| **진입점** | `index.js` 하나. 추가 `<script>` 태그 삽입 금지 |
| **DOM** | 기존 DOM 수정 금지. 자체 컨테이너 생성 후 `document.body.appendChild` |
| **ID 접두** | 모든 요소 id는 `swefm-` 접두 |
| **localStorage** | 키 접두 `swefm_`. 기존 `ef_*` 키 읽기/쓰기 금지 |
| **전역** | IIFE 또는 모듈 스코프. `window.SWEFM`에만 최소 API 추가 |
| **에러 처리** | 모든 초기화 `try/catch`, 실패 시 `console.warn`만 |
| **외부 라이브러리** | Cesium 외 금지. 순수 JS + 브라우저 API |
| **네트워크** | Cesium 타일 외 추가 요청 금지 |
| **모바일** | 터치 이벤트 `{ passive:false }`, 버튼 최소 44px |
| **Cesium API** | 사용 전 `typeof` / 존재 여부 체크 필수 |

## viewer 접근 방법
```js
window.SWEFM.waitViewer(function(viewer) {
  // viewer는 CesiumJS Viewer 인스턴스
});
```
- 최대 20회, 500ms 간격 재시도 후 자동 포기
- `window.SWEF.viewer || window.viewer` 순으로 탐색

## 각 모듈 설명

### favorites.js
- **목적**: 현재 카메라 위치 저장 및 즐겨찾기 관리, 최근 방문 20곳 자동 기록
- **의존성**: `window.SWEFM.waitViewer`, `window.Cesium`
- **저장키**: `swefm_favs` (즐겨찾기 목록), `swefm_history` (방문 기록)
- **공개 API**: `window.SWEFM.favorites`
- **UI**: 화면 좌상단 ⭐ 토글 버튼 + 패널

### replay.js
- **목적**: 자유비행 카메라 경로 0.2초 간격 샘플링 및 재생(보간)
- **의존성**: `window.SWEFM.waitViewer`, `window.Cesium`
- **저장키**: `swefm_replays` (최대 5개 슬롯)
- **공개 API**: `window.SWEFM.replay`
- **UI**: 화면 좌상단 🎬 토글 버튼 + 패널, 재생 중 진행바

### hud.js
- **목적**: 실시간 위도/경도/고도/속도/방위 표시, SVG 나침반
- **의존성**: `window.SWEFM.waitViewer`, `window.Cesium`
- **저장키**: `swefm_hud_visible` (토글 상태)
- **공개 API**: `window.SWEFM.hud`
- **UI**: 화면 우상단 HUD + 🌐 토글 버튼

## 새 모듈 추가 방법

1. `static/fly/modules/myfeature.js` 파일 생성
2. IIFE로 감싸고 상단 주석 작성:
   ```js
   /* myfeature.js — 모듈 설명
    * 목적: ...
    * 의존성: window.SWEFM.waitViewer
    * 저장키: swefm_myfeature_*
    */
   (function() {
     "use strict";
     // ...
     window.SWEFM.myfeature = { /* public API */ };
   })();
   ```
3. `index.js`의 모듈 배열에 파일명 추가:
   ```js
   ["favorites.js","replay.js","hud.js","myfeature.js"].forEach(...)
   ```

## 로컬스토리지 키 목록

| 키 | 모듈 | 내용 |
|----|------|------|
| `swefm_favs` | favorites | 즐겨찾기 배열 (JSON) |
| `swefm_history` | favorites | 최근 방문 기록 (JSON) |
| `swefm_replays` | replay | 리플레이 슬롯 배열 (JSON) |
| `swefm_hud_visible` | hud | HUD 표시 여부 (boolean) |
