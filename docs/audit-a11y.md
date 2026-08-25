# 접근성 감사 리포트

## 요약

`static/fly/index.html`과 `static/fly/modules/*.js`를 정적 분석하여 WCAG 2.1 AA 기준으로 검토한 결과입니다.  
코드 수정 없이 읽기 전용으로 분석하였으며, 실제 브라우저 렌더링 결과와 차이가 있을 수 있습니다.

| # | 항목 | 심각도 | 파일 |
|---|------|--------|------|
| A11Y-001 | 버튼 `aria-label` 누락 (아이콘 전용) | 높음 | index.html, 모듈 전반 |
| A11Y-002 | 터치 타겟 44px 미만 | 중간 | index.html |
| A11Y-003 | 색 대비 — 정적 계산 불가 요소 | 확인 필요 | index.html |
| A11Y-004 | `div`/`span`을 버튼처럼 사용 (키보드 접근 불가) | 높음 | index.html, 모듈 전반 |

---

## 발견 항목

### A11Y-001: 버튼 `aria-label` 누락

#### A11Y-001-1: `#btnGo` 검색 버튼 (emoji만 표시)

- **위치**: `static/fly/index.html:L125`
- **문제**: `🔍` 텍스트만 있고 `aria-label`이 없어 스크린리더가 "🔍" 또는 "검색"임을 알 수 없습니다.
- **영향**: 스크린리더 사용자가 버튼 기능을 파악하지 못합니다.
- **제안**:
```html
<button class="btn" id="btnGo" aria-label="장소 검색">🔍</button>
```

#### A11Y-001-2: `#btnHov` 정지 버튼 (특수문자)

- **위치**: `static/fly/index.html:L107`
- **문제**: `&#9208;` (⏸ 유니코드 특수기호)만 있고 `aria-label`이 없습니다.
- **영향**: 스크린리더가 "일시정지" 의미를 전달하지 못합니다.
- **제안**:
```html
<button class="tbtn" id="btnHov" aria-label="호버(일시정지)">&#9208;</button>
```

#### A11Y-001-3: `#btnDrift`, `#btnBoost` (조작 버튼)

- **위치**: `static/fly/index.html:L108-L109`
- **문제**: "DRIFT", "BOOST" 텍스트가 영어 약어로 한국어 사용자에게 맥락 없이 제공됩니다.
- **영향**: 스크린리더/고대비 모드 사용자가 기능을 알기 어렵습니다.
- **제안**:
```html
<button class="tbtn big" id="btnDrift" aria-label="드리프트">DRIFT</button>
<button class="tbtn" id="btnBoost" aria-label="부스터">BOOST</button>
```

#### A11Y-001-4: 탭 버튼 (`#tabX`, `#tabV`, `#tabR`, `#tabS`)

- **위치**: `static/fly/index.html:L154-L157`
- **문제**: emoji + 텍스트 조합이지만 `role="tab"` 및 `aria-selected` 속성이 없습니다.
- **영향**: 스크린리더가 탭 구성 요소임을 인식하지 못합니다.
- **제안**:
```html
<div id="tabbar" role="tablist">
  <button class="tabb on" id="tabX" role="tab" aria-selected="true" aria-controls="px">🌍 탐험</button>
  <button class="tabb" id="tabV" role="tab" aria-selected="false" aria-controls="pv">🐉 탈것</button>
  <button class="tabb" id="tabR" role="tab" aria-selected="false" aria-controls="pr">🏁 레이스</button>
  <button class="tabb" id="tabS" role="tab" aria-selected="false" aria-controls="ps">🎬 연출</button>
</div>
```

#### A11Y-001-5: `#btnPhoto`, `#btnStats`, `#btnCity`, `#btnLayer`, `#btnRec`, `#btnHQ`, `#btnCine`

- **위치**: `static/fly/index.html:L146-L164`
- **문제**: emoji + `<span>` 텍스트 조합으로 버튼 레이블이 동적으로 변경되지만 `aria-label` 또는 `aria-live` 없음.
- **영향**: 상태 변경 시 스크린리더가 업데이트를 알리지 않습니다.
- **제안**:
```html
<button class="btn" id="btnRec" aria-label="화면 녹화 시작">
  📹 <span id="recLbl" aria-live="polite">녹화</span>
</button>
```

#### A11Y-001-6: launcher.js 런처 버튼

- **위치**: `static/fly/modules/launcher.js:L140-L162`
- **문제**: `launcherEl.textContent = "☰"` 에 `title`만 있고 `aria-label`이 없습니다. `title`은 마우스 호버에서만 표시되며 스크린리더 지원이 일관되지 않습니다.
- **영향**: 모바일 스크린리더에서 기능 파악 불가.
- **제안**:
```javascript
launcherEl.setAttribute("aria-label", "모듈 열기");
launcherEl.setAttribute("aria-expanded", "false");
// toggle() 시:
launcherEl.setAttribute("aria-expanded", open ? "true" : "false");
```

#### A11Y-001-7: launcher.js 모듈 버튼 (tray 버튼들)

- **위치**: `static/fly/modules/launcher.js:L78-L95`
- **문제**: `b.textContent = btn.icon` (emoji만) — `aria-label`이 없습니다.
- **영향**: 스크린리더가 emoji 이름을 읽거나 기능을 파악하지 못합니다.
- **제안**:
```javascript
b.setAttribute("aria-label", btn.label || btn.icon);
```

#### A11Y-001-8: share.js 패널 버튼

- **위치**: `static/fly/modules/share.js:L191-L196`
- **문제**: 닫기(`✕`), 복사, 공유 버튼에 `aria-label` 없음.
- **영향**: 스크린리더에서 각 버튼 기능을 알 수 없습니다.
- **제안**:
```html
<button id="swefm-share-close" aria-label="닫기" ...>✕</button>
<button id="swefm-share-copy" aria-label="링크 복사" ...>복사</button>
<button id="swefm-share-share" aria-label="링크 공유" ...>공유</button>
```

#### A11Y-001-9: compare.js 패널 버튼

- **위치**: `static/fly/modules/compare.js:L56-L62`
- **문제**: 닫기(`✕`), 시작, 중단 버튼에 `aria-label` 없음.
- **제안**:
```html
<button id="swefm-compare-close" aria-label="닫기" ...>✕</button>
<button id="swefm-compare-start" aria-label="캡처 시작" ...>시작</button>
<button id="swefm-compare-cancel" aria-label="캡처 중단" ...>중단</button>
```

---

### A11Y-002: 터치 타겟 44px 미만

WCAG 2.5.5 (Target Size, AAA) 및 WCAG 2.5.8 (Target Size Minimum, AA, 24px) 기준.  
Google/Apple HIG 권장 최소값은 44×44px.

#### A11Y-002-1: `.ccard` (카테고리 선택 칩)

- **위치**: `static/fly/index.html:L27` (CSS), L1094-L1099 (생성)
- **문제**: `padding:6px 12px; font-size:12px` — 실제 높이 ≈ `12px × 1.2 + 12px = 26.4px`. 44px 미만.
- **영향**: 손가락으로 탭 시 오작동, 운동 장애 사용자에게 어려움.
- **제안**:
```css
.ccard {
  padding: 10px 12px;   /* 높이 ≈ 12×1.2 + 20 = 34.4px → min-height로 보완 */
  min-height: 44px;
  display: flex;
  align-items: center;
}
```

#### A11Y-002-2: `.btn` (일반 버튼)

- **위치**: `static/fly/index.html:L36-L38` (CSS), L160-L164 (사용)
- **문제**: `padding:8px 14px; font-size:13px` — 실제 높이 ≈ `13px × 1.2 + 16px ≈ 31.6px`. 44px 미만.
- **영향**: 투어/자유비행/우주 등 핵심 기능 버튼이 소형 타겟임.
- **제안**:
```css
.btn {
  padding: 10px 14px;
  min-height: 44px;
}
```

#### A11Y-002-3: `.tabb` (탭 버튼)

- **위치**: `static/fly/index.html:L73-L74` (CSS), L154-L157 (사용)
- **문제**: `padding:9px 0; font-size:13px` — 실제 높이 ≈ `13px × 1.2 + 18px ≈ 33.6px`. 44px 미만.
- **제안**:
```css
.tabb {
  padding: 12px 0;
  min-height: 44px;
}
```

#### A11Y-002-4: `.dcard`, `.vcard`, `.tcard`, `.filmc`, `.momc` (목록 카드)

- **위치**: `static/fly/index.html:L29-L31, L53, L81-L84` (CSS)
- **문제**: `padding:8px 14px; font-size:13px` — 실제 높이 ≈ 32px. 44px 미만.
- **영향**: 목적지/탈것/레이스 트랙/필름/모멘트 선택 요소가 소형 타겟.
- **제안**:
```css
.dcard, .vcard, .tcard, .filmc, .momc {
  min-height: 44px;
  display: flex;
  align-items: center;
}
```

---

### A11Y-003: 색 대비 이슈

WCAG 1.4.3 기준: 일반 텍스트 4.5:1, 대형 텍스트(18pt+ 또는 14pt+ bold) 3:1 이상.

#### A11Y-003-1: 정적 계산 가능한 요소

| 요소 | 전경색 | 실효 배경색 | 계산 대비 | 판정 |
|------|--------|-------------|-----------|------|
| `.ccard` | `#ccddff` | `rgb(18,24,38)` (알파 합성, body `#000`) | ≈ 13.7:1 | ✅ PASS |
| `.ccard.on` | `#001a33` | `rgb(102,153,217)` (알파 합성) | ≈ 6.3:1 | ✅ PASS |
| `.fcard` | `#331a00` | `rgb(230,158,63)` (그라디언트 중간값, 알파 합성) | ≈ 7.9:1 | ✅ PASS |
| `.btn` (기본) | `#ffffff` | `rgb(36,36,36)` (알파 합성) | ≈ 14.0:1 | ✅ PASS |
| `.btn.on` | `#00121f` | `rgb(96,160,204)` (알파 합성) | ≈ 6.8:1 | ✅ PASS |
| `hud.js` HUD 박스 | `#eeeeee` | `rgba(0,0,0,.65)` 아래 검정 가정 | ≈ 18.3:1 | ✅ PASS |

> 알파 합성 공식: `effective_rgb = alpha × fg_rgb + (1-alpha) × bg_rgb` (body background `#000` 기준)

#### A11Y-003-2: 정적 계산 불가 — Cesium 3D 장면 위 요소

아래 요소는 배경이 동적인 3D 지구/지형 렌더링이므로 정적 분석으로 대비값을 확정할 수 없습니다.

**`#title` ("EARTHFLIGHT" 로고)**
- **위치**: `static/fly/index.html:L18-L19` (CSS), `L94` (HTML)
- **문제**: `color:#fff; opacity:.85`. 배경은 Cesium 장면(눈/구름/밤 등 다양). `text-shadow:0 1px 6px #000`이 있으나 강도가 충분하지 않을 수 있음.
- **확인 필요**: 야간 비행 모드(배경 어두움) vs 밝은 구름/눈 장면에서 실제 대비 측정 필요.
- **제안**: `text-shadow`를 강화하거나 반투명 배경 패드를 추가.
```css
#title {
  text-shadow: 0 1px 8px #000, 0 0 16px rgba(0,0,0,.7);
  /* 또는 */
  background: rgba(0,0,0,.3);
  padding: 2px 6px;
  border-radius: 4px;
}
```

**`#hint` (우상단 안내 텍스트)**
- **위치**: `static/fly/index.html:L87` (CSS), `L103` (HTML), `L1044` (JS 동적 설정)
- **문제**: `opacity:.6` — 화이트 텍스트가 60% 불투명도로 렌더링됨. Cesium 장면 위에서 밝은 배경과 겹칠 경우 대비 부족 가능.
- **확인 필요**: 낮 시간대, 밝은 지형(설산·구름) 위에서 실제 대비 측정.

**`#tier` (등급 표시)**
- **위치**: `static/fly/index.html:L88-L89` (CSS), `L104` (HTML)
- **문제**: `opacity:.55; color:#ffd9a0; font-size:11px` — 55% 불투명도의 11px 텍스트. WCAG AA의 소형 텍스트 기준(4.5:1)을 충족하기 어려울 수 있음.
- **확인 필요**: 밝은 배경 장면에서 실제 대비 측정. `font-size:11px`는 WCAG "대형 텍스트" 기준 미충족.

---

### A11Y-004: 키보드 접근 불가 요소

#### A11Y-004-1: `.vcard`, `.dcard`, `.ccard`, `.fcard` — `div`를 버튼으로 사용

- **위치**: `static/fly/index.html:L1066-L1101` (`buildUI` 함수)
- **문제**: `div` 요소에 `.onclick`을 설정했으나 `tabindex`, `role="button"`, `keydown`/`keyup` 이벤트 없음.
```javascript
// L1068-L1070 (vcard 생성)
const el = document.createElement("div");
el.className = "vcard"; el.textContent = v.e+" "+dn(v);
el.onclick = ()=>pickVeh(i);
// L1089-L1091 (dcard 생성)
const el = document.createElement("div");
el.className = "dcard"; el.textContent = dn(d);
el.onclick = ()=>flyToDest(i);
```
- **영향**: 키보드 탭 이동 불가, 스크린리더에서 "클릭 가능"임을 인식하지 못함.
- **제안**:
```javascript
const el = document.createElement("button");
el.className = "vcard";
el.type = "button";
el.textContent = v.e + " " + dn(v);
el.onclick = () => pickVeh(i);
// 또는 div를 유지할 경우:
el.setAttribute("role", "button");
el.setAttribute("tabindex", "0");
el.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickVeh(i); }
});
```

#### A11Y-004-2: `.tcard` (레이스 트랙 카드) — `div`를 버튼으로 사용

- **위치**: `static/fly/index.html:L1152`
```javascript
el.textContent=tn(t); el.onclick=()=>startRace(i); tw.appendChild(el);
```
- **문제**: `tcard` 클래스 적용 후 onclick만 설정, `role="button"`, `tabindex` 없음.
- **제안**: 동일하게 `button` 태그로 교체 또는 `role`/`tabindex`/`keydown` 추가.

#### A11Y-004-3: `.filmc`, `.momc` (영화·모멘트 카드)

- **위치**: `static/fly/index.html:L1112, L1127`
```javascript
el.textContent=(KO?m.n:m.en); el.onclick=()=>playMoment(i); mw.appendChild(el);
el.textContent=(KO?f[0]:f[1]); el.onclick=()=>setFilm(i); fw.appendChild(el);
```
- **문제**: `div` 요소에만 onclick 설정, 키보드 이벤트 없음.

#### A11Y-004-4: `#statsBox` 닫기 — `div`에 onclick

- **위치**: `static/fly/index.html:L1179`
```javascript
b.onclick=()=>b.style.display="none";
```
- **문제**: `b`가 `div`로 생성되어 `display:none`으로 숨기는 클릭 핸들러를 가짐. 키보드로 닫을 수 없음.
- **제안**:
```javascript
const b = document.getElementById("statsBox");
// 닫기 버튼은 button 태그로 별도 생성
const closeBtn = document.createElement("button");
closeBtn.textContent = "✕";
closeBtn.setAttribute("aria-label", "닫기");
closeBtn.onclick = () => b.style.display = "none";
b.appendChild(closeBtn);
```

#### A11Y-004-5: favorites.js — innerHTML로 생성한 클릭 버튼들

- **위치**: `static/fly/modules/favorites.js:L119-L134`
- **문제**: `renderPanel()`에서 innerHTML로 생성한 `button` 요소들이 `aria-label` 없이 emoji/텍스트만 표시됨. `swefm-favs-close(✕)`, `swefm-favs-save`, `swefm-fav-del(✕)` 등.
- **제안**:
```javascript
'<button id="swefm-favs-close" aria-label="닫기" style="...">✕</button>'
'<button class="swefm-fav-del" aria-label="즐겨찾기 삭제" data-id="${item.id}" style="...">✕</button>'
```

#### A11Y-004-6: replay.js — `document.addEventListener("keydown")` (모달 트랩 미구현)

- **위치**: `static/fly/modules/replay.js:L141-L146`
```javascript
document.addEventListener("keydown", e => {
  if ((e.key === "Escape" || e.key === "Tab") && playing) {
    e.preventDefault();
    stopPlayback();
  }
});
```
- **문제**: 재생 중 Tab 키를 전역 차단하나, 재생 오버레이에 `aria-modal`, `role="dialog"`, `aria-label` 없음. 스크린리더가 배경 콘텐츠를 계속 탐색할 수 있음.
- **제안**:
```javascript
inputBlockOverlay.setAttribute("role", "dialog");
inputBlockOverlay.setAttribute("aria-modal", "true");
inputBlockOverlay.setAttribute("aria-label", "리플레이 재생 중");
```

#### A11Y-004-7: `#coach` (조종법 모달) — `role="dialog"` 없음

- **위치**: `static/fly/index.html:L111-L119`
- **문제**: 모달처럼 동작하는 `#coach` div에 `role="dialog"`, `aria-modal`, `aria-label`, `aria-labelledby` 없음. 포커스가 모달 내부로 이동하지 않음.
- **제안**:
```html
<div id="coach" role="dialog" aria-modal="true" aria-labelledby="coach-title">
  <div id="coachCard">
    <div id="coach-title" style="font-size:20px;font-weight:800;margin-bottom:14px">🛫 조종법</div>
    ...
  </div>
</div>
```
그리고 JS에서 모달 표시 시 `coachOk` 버튼으로 포커스 이동:
```javascript
document.getElementById("coachOk").focus();
```
