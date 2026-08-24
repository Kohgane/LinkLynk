/* hud.js — 좌표 HUD & SVG 나침반
 * 목적: 우상단에 위도/경도/고도/속도/방위 실시간 표시, 클립보드 복사, SVG 나침반 회전, 토글
 * 의존성: window.SWEFM.waitViewer, window.Cesium (선택)
 * 저장키: swefm_hud_visible
 */
(function () {
  "use strict";

  const KEY_VISIBLE = "swefm_hud_visible";
  const UPDATE_INTERVAL = 300; // ms

  function load(key, def) {
    try {
      const v = localStorage.getItem(key);
      return v !== null ? JSON.parse(v) : def;
    } catch { return def; }
  }
  function save(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { console.warn("[swefm/hud] 저장 실패"); }
  }

  /* ── 카메라 데이터 추출 ── */
  function getCamData(viewer, prevPos, prevTs) {
    try {
      const cam = viewer.camera;
      let lat, lon, alt;
      if (cam.positionCartographic) {
        const c = cam.positionCartographic;
        const toDeg = window.Cesium ? Cesium.Math.toDegrees : (r => r * 180 / Math.PI);
        lat = toDeg(c.latitude); lon = toDeg(c.longitude); alt = c.height;
      } else if (window.Cesium && Cesium.Cartographic && cam.position) {
        const c = Cesium.Cartographic.fromCartesian(cam.position);
        lat = Cesium.Math.toDegrees(c.latitude);
        lon = Cesium.Math.toDegrees(c.longitude);
        alt = c.height;
      } else return null;

      const headingDeg = cam.heading * 180 / Math.PI;

      // 속도 추정 (m/s)
      let speed = 0;
      if (prevPos && prevTs) {
        const dt = (Date.now() - prevTs) / 1000;
        if (dt > 0 && window.Cesium && Cesium.Cartesian3 && cam.position) {
          try {
            const d = Cesium.Cartesian3.distance(prevPos, cam.position);
            speed = d / dt;
          } catch { /* 무시 */ }
        }
      }

      const pos3d = (window.Cesium && cam.position) ? cam.position.clone() : null;
      return { lat, lon, alt, heading: headingDeg, speed, pos3d, ts: Date.now() };
    } catch { return null; }
  }

  /* ── SVG 나침반 ── */
  function compassSVG(headingDeg) {
    const r = headingDeg.toFixed(1);
    return `<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 52 52">
      <circle cx="26" cy="26" r="24" fill="rgba(0,0,0,.5)" stroke="rgba(255,255,255,.25)" stroke-width="1"/>
      <g transform="rotate(${r},26,26)">
        <polygon points="26,6 22,26 26,22 30,26" fill="#FF4444"/>
        <polygon points="26,46 22,26 26,30 30,26" fill="#aaa"/>
      </g>
      <text x="26" y="13" text-anchor="middle" fill="#FF4444" font-size="8" font-family="sans-serif" font-weight="bold">N</text>
    </svg>`;
  }

  /* ── UI ── */
  function buildUI(viewer) {
    let visible = load(KEY_VISIBLE, true);
    let prevPos = null, prevTs = null;

    // 컨테이너
    const container = document.createElement("div");
    container.id = "swefm-hud-container";
    container.style.cssText = `position:fixed;top:60px;right:12px;z-index:8800;
      display:flex;flex-direction:column;align-items:flex-end;gap:6px;pointer-events:none;`;
    document.body.appendChild(container);

    // HUD 정보 박스
    const hud = document.createElement("div");
    hud.id = "swefm-hud-box";
    hud.title = "클릭하여 좌표 복사";
    hud.style.cssText = `background:rgba(0,0,0,.65);color:#eee;border-radius:8px;padding:6px 10px;
      font-size:11px;line-height:1.6;pointer-events:auto;cursor:pointer;
      font-family:monospace;min-width:160px;text-align:right;`;
    hud.innerHTML = `<span style="color:#888">위치 초기화 중...</span>`;
    container.appendChild(hud);

    // 나침반
    const compass = document.createElement("div");
    compass.id = "swefm-hud-compass";
    compass.style.cssText = `pointer-events:none;`;
    compass.innerHTML = compassSVG(0);
    container.appendChild(compass);

    function setVisible(v) {
      visible = v;
      container.style.display = visible ? "flex" : "none";
      save(KEY_VISIBLE, visible);
    }
    setVisible(visible);

    // 런처 등록
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-hud",
        icon: "📍",
        label: "좌표",
        onClick: function () { setVisible(!visible); }
      });
    } else {
      console.warn("[swefm/hud] registerButton 없음 — 런처 미로드");
    }

    /* 클립보드 복사 */
    hud.onclick = () => {
      try {
        const data = getCamData(viewer, prevPos, prevTs);
        if (!data) return;
        const text = `${data.lat.toFixed(6)}, ${data.lon.toFixed(6)}, ${data.alt.toFixed(0)}m`;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(() => {
            const orig = hud.style.background;
            hud.style.background = "rgba(0,100,0,.8)";
            setTimeout(() => { hud.style.background = orig; }, 600);
          }).catch(() => fallbackCopy(text));
        } else fallbackCopy(text);
      } catch (e) { console.warn("[swefm/hud] 복사 실패", e); }
    };

    function fallbackCopy(text) {
      try {
        const ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select(); document.execCommand("copy");
        document.body.removeChild(ta);
      } catch { /* 무시 */ }
    }

    /* 업데이트 루프 */
    setInterval(() => {
      if (!visible) return;
      try {
        const data = getCamData(viewer, prevPos, prevTs);
        if (!data) return;

        const latDir = data.lat >= 0 ? "N" : "S";
        const lonDir = data.lon >= 0 ? "E" : "W";
        const altKm = data.alt >= 10000 ? `${(data.alt / 1000).toFixed(1)}km` : `${Math.round(data.alt)}m`;
        const speedStr = data.speed < 1 ? "" : `<br>속도: ${data.speed >= 1000 ? (data.speed / 1000).toFixed(1) + "km/s" : Math.round(data.speed) + "m/s"}`;
        const hdg = ((data.heading % 360) + 360) % 360;

        hud.innerHTML = `
          <span style="color:#88CCFF">${Math.abs(data.lat).toFixed(5)}°${latDir}</span><br>
          <span style="color:#88CCFF">${Math.abs(data.lon).toFixed(5)}°${lonDir}</span><br>
          <span style="color:#AAFFAA">고도: ${altKm}</span><br>
          <span style="color:#FFCC66">방위: ${hdg.toFixed(1)}°</span>${speedStr}
        `;

        compass.innerHTML = compassSVG(hdg);

        prevPos = data.pos3d;
        prevTs = data.ts;
      } catch (e) { console.warn("[swefm/hud] 업데이트 오류", e); }
    }, UPDATE_INTERVAL);
  }

  /* ── 초기화 ── */
  function init() {
    try {
      window.SWEFM.waitViewer(viewer => {
        try { buildUI(viewer); } catch (e) { console.warn("[swefm/hud] UI 초기화 실패", e); }
      });
    } catch (e) {
      console.warn("[swefm/hud] 초기화 실패", e);
    }
  }

  init();
})();
