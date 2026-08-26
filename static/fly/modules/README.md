# SWEF Modules (`static/fly/modules`)

`static/fly/modules`는 `index.html`을 직접 수정하지 않고 기능을 확장하는 모듈 계층입니다.
핵심은 **로더(`index.js`) + 런처(`launcher.js`) + 기능 모듈** 구조입니다.

---

## 1) 모듈 아키텍처

### 구성
- `index.js`: 모듈 로더, `window.SWEFM` API 제공
- `launcher.js`: 공통 UI 진입점(런처), 모듈 버튼 렌더러
- 기능 모듈: `favorites.js`, `replay.js`, `hud.js`, `share.js`, `compare.js`, `settings.js`

### 로드 순서
1. `index.js` 실행
2. `MODULES` 배열 순서대로 `launcher.js` 먼저 로드
3. 이후 기능 모듈 로드

현재 `MODULES`:
```js
["launcher.js","favorites.js","replay.js","hud.js","share.js","compare.js","settings.js"]
```

### 이 순서가 필요한 이유
- 기능 모듈은 `window.SWEFM.registerButton(...)`으로 런처 버튼을 등록합니다.
- 런처 준비 전 호출은 `SWEFM._btnQueue`에 큐잉되고, `launcher.js` 준비 후 일괄 반영됩니다.
- 기능 모듈은 `SWEFM.waitViewer` / `SWEFM.debug` 같은 공통 API를 공유합니다.

> 모듈은 `static/fly/index.html`을 직접 수정하지 않고, `window.SWEF`/`window.SWEFM` 훅에 붙는 방식으로 동작합니다.

---

## 2) `window.SWEF` 훅 목록과 사용 패턴

`index.html`에서 `window.SWEF`에 다음 필드를 노출합니다.

- `viewer`: Cesium Viewer 인스턴스
- `DESTS`, `TRACKS`, `FILMS`, `MOMENTS`: 앱 데이터 배열
- `toast(msg)`, `goFree()`, `goSpace()`, `flyToDest(i)`, `setFilm(i)`, `playMoment(i)`
- getter: `camera`, `isTouch`, `lang`
- `version`

### 준비 상태 패턴
- 현재 코드에는 `window.SWEF.ready` 필드가 없습니다.
- 대신 아래 패턴을 사용합니다.
  - `window.SWEF.viewer` 존재 여부 확인
  - `swef:ready` 이벤트 수신

```js
function initFromSWEF(swef) {
  // swef.viewer 사용
}

window.addEventListener("swef:ready", function (e) {
  initFromSWEF(e.detail);
});

if (window.SWEF && window.SWEF.viewer) {
  initFromSWEF(window.SWEF);
}
```

---

## 3) `window.SWEFM` API

### `SWEFM.waitViewer(cb, tries?)`
- 콜백 기반 유틸리티입니다. (`Promise` 반환 없음)
- 내부적으로 `window.SWEF.viewer`(또는 `window.viewer`)가 준비될 때까지 재시도 후 콜백 실행

```js
window.SWEFM.waitViewer(function (viewer) {
  // viewer 준비 후 실행
});
```

### `SWEFM.registerButton({ id, icon, label, onClick })`
- 런처 버튼 등록 API
- 필드:
  - `id`: 버튼 DOM id
  - `icon`: 버튼 아이콘 텍스트/이모지
  - `label`: 런처 펼침 시 표시 라벨
  - `onClick`: 버튼 클릭 핸들러
- 런처 준비 전 호출 시 `_btnQueue`에 임시 저장, `launcher.js` 준비 후 등록

### `SWEFM.debug()`
- 모듈/환경 진단용 API
- 콘솔 `table`로 다음 상태를 확인
  - loadedModules
  - `window.SWEF` 존재 여부
  - viewer 존재 여부
  - `swefm-` 접두 DOM 개수
- `settings.js`는 이 진단 정보를 패널 표 형태로도 보여줍니다(콘솔 없이 확인 가능).

---

## 4) 새 모듈 추가 방법

1. `static/fly/modules/<name>.js` 파일 추가
2. IIFE 사용
3. `window.SWEFM.registerButton`으로 런처 버튼 등록
4. viewer 접근은 `window.SWEFM.waitViewer` 또는 `swef:ready` 패턴 사용
5. 필요한 경우 `index.js`의 `MODULES` 배열에 파일명 추가
6. DOM id는 `swefm-`, 저장키는 `swefm_` 접두 준수

최소 템플릿:

```javascript
(function(){
  "use strict";

  function warn(message, error){
    if (window.console && typeof console.warn === "function") {
      console.warn("[SWEFM:example] " + message, error || "");
    }
  }

  function init(){
    if (!window.SWEFM || typeof window.SWEFM.registerButton !== "function") {
      warn("launcher API is not available");
      return;
    }

    window.SWEFM.registerButton({
      id: "swefm-example",
      icon: "★",
      label: "예시",
      onClick: function(){
        // TODO: open panel or run module action
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
```

---

## 5) 모듈 개발 규칙

- `static/fly/index.html` 비침범: 모듈 추가/변경 시 가능한 한 수정 금지
- 저장키는 `swefm_` 접두 사용
- DOM id는 `swefm-` 접두 사용
- 앱 UI 점유 영역 피하기
  - 상단 110px
  - 하단 220px
  - 우측하단 120px
- 외부 라이브러리 금지
- 네트워크 요청 금지(앱 기본 동작 외 임의 API 호출 금지)
- 앱 본체 저장키(`ef_` 등) 침범 금지
- 실패 시 앱 전체를 중단하지 말고 `console.warn` 중심으로 방어

---

## 6) 모듈 목록 / 저장키 표

| 모듈 | 역할 | 런처 버튼 | 저장키 |
|---|---|---|---|
| `launcher.js` | 공통 런처 UI 생성, 버튼 큐 flush | 런처 본체(☰) | `swefm_launcher_open` |
| `favorites.js` | 즐겨찾기/최근 방문 저장, 이동, JSON 입출력 | `id=swefm-favs`, `★`, `즐겨찾기` | `swefm_favs`, `swefm_history` |
| `replay.js` | 카메라 경로 녹화/재생/슬롯 저장 | `id=swefm-replay`, `▶`, `리플레이` | `swefm_replays` |
| `hud.js` | 좌표 HUD/나침반 표시 및 토글 | `id=swefm-hud`, `📍`, `좌표` | `swefm_hud_visible` |
| `share.js` | 공유 딥링크 생성/복사, 최근 링크 관리 | `id=swefm-share`, `🔗`, `공유` | `swefm_links` |
| `compare.js` | 시간대 4컷 비교 캡처 생성 | `id=swefm-compare`, `🕐`, `시간비교` | 없음 |
| `settings.js` | 모듈 on/off, swefm_* 관리, 백업/복원, 진단 표 | `id=swefm-settings`, `⚙`, `모듈설정` | `swefm_disabled` (+ `swefm_*` 관리) |

---

## 7) 알려진 함정 / 사고 기록

- 과거에 `script src`에 쿼리스트링이 붙을 때 모듈 로더의 `BASE` 계산이 깨진 사고가 있었습니다.
- 현재 `index.js`는 `new URL(...).href.replace(/index\.js.*$/, "")` 방식으로 보완되어 해결된 상태입니다.
- 향후 로더 경로 계산 로직을 수정할 때, 쿼리스트링/해시가 붙은 URL 케이스가 다시 깨지지 않게 주의해야 합니다.
- 새 모듈 추가 시에는 코드만이 아니라 캐시/서비스워커/테스트 목록 영향도 함께 확인하세요.
