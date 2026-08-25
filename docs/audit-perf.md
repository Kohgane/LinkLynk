# 성능 감사 리포트

## 요약

`static/fly/index.html`과 `static/fly/modules/*.js`를 정적 분석하여 런타임 성능 병목 가능성을 검토한 결과입니다.  
코드 수정 없이 읽기 전용으로 분석하였습니다.

| # | 항목 | 우선순위 | 파일 |
|---|------|----------|------|
| PERF-001 | 매 프레임 `raceHud.innerHTML` 갱신 | 상 | index.html |
| PERF-002 | 매 프레임 `vehHud.textContent` 갱신 | 중 | index.html |
| PERF-003 | 매 프레임 `new Cesium.HeadingPitchRange` 할당 | 상 | index.html |
| PERF-004 | 매 프레임 `camera.position.clone()` 호출 | 중 | index.html |
| PERF-005 | `querySelectorAll(".dcard")` 반복 호출 | 중 | index.html |
| PERF-006 | replay.js 전역 `keydown` 리스너 미제거 | 중 | modules/replay.js |
| PERF-007 | hud.js `setInterval` 미정리 | 하 | modules/hud.js |
| PERF-008 | replay.js `setInterval` 기반 재생 루프 | 중 | modules/replay.js |

---

## 발견 항목

### PERF-001: 매 프레임 루프 내 `raceHud.innerHTML` 갱신

- **우선순위**: 상
- **위치**: `static/fly/index.html:L1011, L1026` (`raceTick` 함수)
- **문제**:
```javascript
// L1011 — 카운트다운 중 매 프레임
raceHud.innerHTML = race.countdown > 1 ? ("🏁 " + Math.floor(race.countdown)) : "GO!";
// L1026 — 레이스 중 매 프레임
raceHud.innerHTML = "⏱ " + el.toFixed(1) + "s<br><small>..." + "</small>";
```
`innerHTML` 할당은 HTML 파싱과 DOM 트리 재구성을 유발합니다. Cesium `onTick`은 `viewer.clock.onTick.addEventListener(tick)`(L476)로 등록되어 렌더 프레임마다 호출됩니다. 즉, 60fps 기준 초당 60회 innerHTML 갱신이 발생합니다.
- **근거**: `innerHTML` 할당은 문자열 파싱 → 기존 자식 노드 제거 → 새 노드 삽입의 3단계를 매 프레임 수행합니다. `textContent`나 사전 생성 노드의 `data` 갱신보다 ~5–10배 비용이 큽니다.
- **제안**:
```javascript
// 초기화 시 한 번 자식 노드 생성
const hudMain = document.createElement("span");
const hudSub  = document.createElement("small");
raceHud.appendChild(hudMain);
raceHud.appendChild(document.createElement("br"));
raceHud.appendChild(hudSub);

// raceTick 내에서 textContent만 갱신
hudMain.textContent = "⏱ " + el.toFixed(1) + "s";
hudSub.textContent  = (KO ? "게이트 " : "Gate ") + race.gi + "/" + T.gates.length + ...;
```

---

### PERF-002: 매 프레임 루프 내 `vehHud.textContent` 갱신

- **우선순위**: 중
- **위치**: `static/fly/index.html:L836` (`tick` 함수 내 `mode === "free"` 분기)
- **문제**:
```javascript
vehHud.textContent = (driftSt.on ? "⚡ " : driftSt.boostT > 0 ? "🔥 " : "")
  + `${veh.e} ${dn(veh)} · ${Math.round(curSpeed() * 3.6).toLocaleString()} km/h`;
```
`textContent` 할당 자체는 가벼우나, 매 프레임 템플릿 리터럴과 `toLocaleString()`를 실행합니다. `toLocaleString()`은 `Intl` 포매터를 사용하므로 비용이 예상보다 클 수 있습니다.
- **근거**: 속도 변화가 없는 프레임에서도 동일 문자열을 새로 생성해 DOM에 씁니다. 이전 값과 비교해 변화가 없으면 생략하는 방식으로 개선 가능합니다.
- **제안**:
```javascript
// tick() 바깥에서 캐시 변수 선언
let _lastVehTxt = "";

// tick() 내부
const newTxt = (driftSt.on ? "⚡ " : driftSt.boostT > 0 ? "🔥 " : "")
  + `${veh.e} ${dn(veh)} · ${Math.round(curSpeed() * 3.6).toLocaleString()} km/h`;
if (newTxt !== _lastVehTxt) {
  vehHud.textContent = newTxt;
  _lastVehTxt = newTxt;
}
```

---

### PERF-003: 매 프레임 루프 내 `new Cesium.HeadingPitchRange` 할당

- **우선순위**: 상
- **위치**: `static/fly/index.html:L764` (`tick` 함수 내 `mode === "tour"` 분기)
- **문제**:
```javascript
if (mode === "tour" && orbiting && orbitCenter) {
  orbitHeading += 0.1 * dt;
  viewer.camera.lookAt(orbitCenter, new Cesium.HeadingPitchRange(orbitHeading, orbitP, orbitR));
}
```
`mode === "tour"` 상태에서 매 렌더 프레임마다 `new Cesium.HeadingPitchRange(...)` 객체가 힙에 할당됩니다.
- **근거**: 자바스크립트 GC는 단명 객체가 누적될 때 짧은 중단(minor GC)을 유발합니다. 60fps에서 초당 60개의 임시 객체가 생성되며, Cesium의 `HeadingPitchRange`는 내부적으로 세 개의 `Number` 필드를 갖는 경량 객체이지만 축적 시 GC 압력을 높입니다.
- **제안**:
```javascript
// tick() 바깥에서 재사용 가능한 객체 선언
const _orbitHPR = new Cesium.HeadingPitchRange(0, 0, 0);

// tick() 내부
if (mode === "tour" && orbiting && orbitCenter) {
  orbitHeading += 0.1 * dt;
  _orbitHPR.heading = orbitHeading;
  _orbitHPR.pitch   = orbitP;
  _orbitHPR.range   = orbitR;
  viewer.camera.lookAt(orbitCenter, _orbitHPR);
}
```

추가로 L787에서도 동일 패턴이 있습니다:
```javascript
// L787 — 드리프트 이동 시 매 프레임
const mv = Cesium.Cartesian3.multiplyByScalar(driftSt.vec, sp, new Cesium.Cartesian3());
```
`new Cesium.Cartesian3()`를 미리 할당한 스크래치 객체로 교체:
```javascript
const _scratchC3 = new Cesium.Cartesian3();
// tick() 내 드리프트 분기:
Cesium.Cartesian3.multiplyByScalar(driftSt.vec, sp, _scratchC3);
Cesium.Cartesian3.add(c.position, _scratchC3, c.position);
```

---

### PERF-004: 매 프레임 `camera.position.clone()` 호출

- **우선순위**: 중
- **위치**: `static/fly/index.html:L767-L771, L795` (`tick` 함수 내)
- **문제**:
```javascript
// L767-L771
if (!tick._pp) tick._pp = viewer.camera.position.clone();
const _mv = Cesium.Cartesian3.distance(tick._pp, viewer.camera.position);
...
tick._pp = viewer.camera.position.clone();  // 매 프레임 clone
// L795 (드리프트 활성 시)
trail.push(Cesium.Cartesian3.clone(c.position));  // 매 프레임 clone + 배열 push
```
`clone()`은 새 `Cartesian3` 객체를 힙에 할당합니다. `tick._pp`는 매 프레임 새 객체로 교체됩니다.
- **근거**: PERF-003과 동일. 재사용 가능한 사전 할당 객체로 교체하면 GC 압력 감소.
- **제안**:
```javascript
// tick() 바깥
const _prevPos = new Cesium.Cartesian3();
let   _prevPosSet = false;

// tick() 내
if (!_prevPosSet) { Cesium.Cartesian3.clone(viewer.camera.position, _prevPos); _prevPosSet = true; }
const _mv = Cesium.Cartesian3.distance(_prevPos, viewer.camera.position);
...
Cesium.Cartesian3.clone(viewer.camera.position, _prevPos);  // 재사용 (새 객체 미생성)
```

---

### PERF-005: `document.querySelectorAll(".dcard")` 다중 호출

- **우선순위**: 중
- **위치**: `static/fly/index.html:L703, L716, L731, L1053, L1098` (다수 함수)
- **문제**:
```javascript
// L703 — flyToDest()
document.querySelectorAll(".dcard").forEach(c => c.classList.toggle("on", c.textContent === dn(d)));
// L716 — goFree()
document.querySelectorAll(".dcard").forEach(c => c.classList.remove("on"));
// L731 — goSpace()
document.querySelectorAll(".dcard").forEach(c => c.classList.remove("on"));
// L1053 — pickVeh()
document.querySelectorAll(".vcard").forEach((c, j) => c.classList.toggle("on", j === i));
// L1098 — renderDests() 내 카테고리 클릭
document.querySelectorAll(".ccard").forEach((c, j) => c.classList.toggle("on", j === ci));
```
`DESTS` 배열은 약 90여 개 항목을 가지므로 `.dcard` 노드도 그만큼 생성됩니다. `querySelectorAll`은 매 호출 시 전체 DOM을 순회하는 라이브가 아닌 정적 NodeList를 반환하며, 이를 100+ 노드에 대해 반복 적용합니다.
- **근거**: `flyToDest` 호출 시 L703, 그리고 목적지 fly 과정에서 `goFree` → L716, `goSpace` → L731가 연쇄 호출될 경우 같은 프레임에 세 번의 `querySelectorAll(".dcard")` 순회가 발생합니다. 목적지 카드를 배열로 캐시하면 재조회 비용을 제거할 수 있습니다.
- **제안**:
```javascript
// buildUI() 내 dcard 생성 시 배열에 함께 저장
const dcardEls = [];
DESTS.forEach((d, i) => {
  const el = document.createElement("div");
  el.className = "dcard"; el.textContent = dn(d);
  el.onclick = () => flyToDest(i);
  dcardEls.push(el);
  wrap.appendChild(el);
});

// flyToDest() 내
dcardEls.forEach((c, i) => c.classList.toggle("on", i === idx));
// goFree() / goSpace()
dcardEls.forEach(c => c.classList.remove("on"));
```

---

### PERF-006: replay.js 전역 `keydown` 리스너 미제거 (이벤트 리스너 누수)

- **우선순위**: 중
- **위치**: `static/fly/modules/replay.js:L141-L146`
- **문제**:
```javascript
document.addEventListener("keydown", e => {
  if ((e.key === "Escape" || e.key === "Tab") && playing) {
    e.preventDefault();
    stopPlayback();
  }
});
```
`document`에 전역 `keydown` 리스너를 등록하지만 모듈이 언로드되거나 리플레이가 종료되어도 **리스너가 제거되지 않습니다.** IIFE 구조라 외부에서 제거할 방법도 없습니다.
- **근거**: SPA 수명 동안 해당 모듈이 여러 번 초기화(예: HMR, 수동 재로드)되면 리스너가 누적됩니다. 또한 재생이 끊긴 상태에서도 매 키 입력마다 핸들러가 실행됩니다.
- **제안**:
```javascript
// 재생 중에만 리스너 등록, 재생 종료 시 제거
function onKeyDown(e) {
  if (e.key === "Escape" || e.key === "Tab") {
    e.preventDefault();
    stopPlayback();
  }
}

function startPlayback(path, speed) {
  // ...
  document.addEventListener("keydown", onKeyDown);
}

function stopPlayback() {
  document.removeEventListener("keydown", onKeyDown);
  // ...
}
```

---

### PERF-007: hud.js `setInterval` 미정리 (잠재적 리스너 누수)

- **우선순위**: 하
- **위치**: `static/fly/modules/hud.js:L144-L168`
- **문제**:
```javascript
setInterval(() => {
  if (!visible) return;
  // DOM 갱신...
}, UPDATE_INTERVAL); // 300ms
```
`clearInterval`을 호출할 수 있는 핸들 참조가 없으며, HUD가 숨겨진 상태(`visible = false`)에서도 300ms마다 클로저가 실행됩니다. 핸들이 없으므로 정리할 수 없습니다.
- **근거**: `!visible`일 때 `return`으로 조기 종료하지만 클로저 호출 자체는 계속 발생합니다. 메모리 누수보다는 불필요한 타이머 큐 항목이 문제입니다. 향후 HUD 동적 마운트/언마운트 시 누수로 전환될 수 있습니다.
- **제안**:
```javascript
let hudTimer = null;

function setVisible(v) {
  visible = v;
  container.style.display = visible ? "flex" : "none";
  save(KEY_VISIBLE, visible);

  // 가시 상태에 따라 타이머 시작/중지
  if (visible && !hudTimer) {
    hudTimer = setInterval(updateHUD, UPDATE_INTERVAL);
  } else if (!visible && hudTimer) {
    clearInterval(hudTimer);
    hudTimer = null;
  }
}
```

---

### PERF-008: replay.js `setInterval` 기반 재생 루프

- **우선순위**: 중
- **위치**: `static/fly/modules/replay.js:L113-L127`
- **문제**:
```javascript
const interval = SAMPLE_INTERVAL / playSpeed;  // 200ms / speed
playTimer = setInterval(() => {
  if (playFrameIdx >= path.length - 1) { stopPlayback(); return; }
  const f0 = path[playFrameIdx], f1 = path[playFrameIdx + 1];
  const frame = lerpFrame(f0, f1, 0.5);
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(frame.lon, frame.lat, frame.alt),
    orientation: { heading: frame.heading, pitch: frame.pitch, roll: frame.roll }
  });
  playFrameIdx++;
  updateProgress(playFrameIdx / (path.length - 1));
}, interval);
```
`setInterval`은 자바스크립트 이벤트 루프 타이머로, 실제 렌더 프레임과 동기화되지 않습니다. Cesium 렌더 루프(`onTick`)와 별개로 카메라를 설정하므로 렌더 프레임 사이에 카메라가 여러 번 이동되거나, 반대로 한 프레임에 카메라 갱신이 빠질 수 있습니다.
- **근거**: `setInterval(fn, 200/speed)` 에서 `playSpeed=2`이면 100ms마다 프레임 전진. 디스플레이가 60fps(16.6ms)이면 약 6프레임마다 한 번씩 재생 단계가 진행되어 카메라 움직임이 버벅이게 느껴집니다. 또한 탭이 백그라운드로 이동하면 `setInterval`이 최소 1초로 제한되어 재생이 급격히 느려집니다.
- **제안**: `requestAnimationFrame` 또는 Cesium `onTick`과 통합하여 렌더 프레임 기반 보간으로 전환:
```javascript
let playLastTs = null;
let playElapsed = 0;

function playTick(nowMs) {
  if (!playing) return;
  if (playLastTs !== null) {
    playElapsed += (nowMs - playLastTs) * playSpeed / 1000;  // 초 단위
  }
  playLastTs = nowMs;

  // path는 SAMPLE_INTERVAL(0.2s) 간격이므로 현재 경과 시간으로 인덱스 결정
  const totalDur = (path.length - 1) * (SAMPLE_INTERVAL / 1000);
  const t = Math.min(playElapsed / totalDur, 1);
  const rawIdx = t * (path.length - 1);
  const idx0 = Math.floor(rawIdx);
  const idx1 = Math.min(idx0 + 1, path.length - 1);
  const alpha = rawIdx - idx0;
  const frame = lerpFrame(path[idx0], path[idx1], alpha);

  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(frame.lon, frame.lat, frame.alt),
    orientation: { heading: frame.heading, pitch: frame.pitch, roll: frame.roll }
  });
  updateProgress(t);

  if (t >= 1) { stopPlayback(); return; }
  requestAnimationFrame(playTick);
}

// startPlayback 내에서:
playLastTs = null;
playElapsed = 0;
requestAnimationFrame(playTick);
```
