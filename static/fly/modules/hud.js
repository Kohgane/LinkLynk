/* hud.js — 좌표 HUD & 나침반 모듈
 * 목적: 우상단 실시간 위도/경도/고도/속도/방위 표시 및 SVG 나침반
 * 의존성: window.Cesium, window.SWEFM.waitViewer
 * 저장키: swefm_hud_visible
 */
(function () {
  "use strict";

  const LS_VISIBLE = "swefm_hud_visible";

  function loadBool(key, fallback) {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    return v === "true";
  }

  function rad2deg(r) { return r * 180 / Math.PI; }

  function getCameraInfo(viewer) {
    try {
      const C = window.Cesium;
      let carto;
      if (viewer.camera.positionCartographic) {
        carto = viewer.camera.positionCartographic;
      } else if (C && C.Cartographic && C.Cartesian3) {
        carto = C.Cartographic.fromCartesian(viewer.camera.position);
      } else return null;

      const lat = rad2deg(carto.latitude);
      const lon = rad2deg(carto.longitude);
      const alt = carto.height;
      const heading = typeof viewer.camera.heading === "number" ? rad2deg(viewer.camera.heading) : 0;
      const pitch = typeof viewer.camera.pitch === "number" ? rad2deg(viewer.camera.pitch) : 0;

      /* 속도: 이전 위치와 비교 */
      return { lat, lon, alt, heading, pitch };
    } catch (e) { return null; }
  }

  function compassSVG(heading) {
    /* 0°=북, 시계방향 */
    const rot = heading.toFixed(1);
    return `<svg width="60" height="60" viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg">
  <circle cx="30" cy="30" r="28" fill="rgba(0,0,0,0.5)" stroke="#555" stroke-width="1.5"/>
  <g transform="rotate(${rot}, 30, 30)">
    <polygon points="30,6 34,30 30,26 26,30" fill="#f44"/>
    <polygon points="30,54 34,30 30,34 26,30" fill="#aaa"/>
  </g>
  <text x="30" y="14" text-anchor="middle" fill="#f44" font-size="8" font-family="sans-serif">N</text>
  <text x="30" y="52" text-anchor="middle" fill="#aaa" font-size="8" font-family="sans-serif">S</text>
  <text x="10" y="33" text-anchor="middle" fill="#aaa" font-size="8" font-family="sans-serif">W</text>
  <text x="50" y="33" text-anchor="middle" fill="#aaa" font-size="8" font-family="sans-serif">E</text>
</svg>`;
  }

  function buildUI(viewer) {
    let visible = loadBool(LS_VISIBLE, true);
    let prevPos = null;
    let prevTime = null;
    let speedMs = 0;
    let animFrame = null;

    /* 컨테이너 */
    const container = document.createElement("div");
    container.id = "swefm-hud";
    Object.assign(container.style, {
      position: "fixed", top: "10px", right: "10px", zIndex: "9997",
      background: "rgba(10,10,20,0.75)", color: "#ddd", borderRadius: "8px",
      padding: "8px 10px", fontFamily: "monospace", fontSize: "12px",
      lineHeight: "1.6", minWidth: "180px",
      boxShadow: "0 2px 8px rgba(0,0,0,0.5)",
      display: visible ? "flex" : "none",
      flexDirection: "column", alignItems: "flex-end", gap: "4px",
      cursor: "pointer"
    });
    container.title = "클릭하면 좌표를 클립보드에 복사";

    const coordDiv = document.createElement("div");
    coordDiv.id = "swefm-hud-coords";

    const compassDiv = document.createElement("div");
    compassDiv.id = "swefm-hud-compass";

    container.append(coordDiv, compassDiv);
    document.body.appendChild(container);

    /* 클립보드 복사 */
    container.addEventListener("click", () => {
      const info = getCameraInfo(viewer);
      if (!info) return;
      const txt = info.lat.toFixed(6) + ", " + info.lon.toFixed(6) + " @" + Math.round(info.alt) + "m";
      if (typeof navigator.clipboard !== "undefined") {
        navigator.clipboard.writeText(txt).catch(() => fallbackCopy(txt));
      } else { fallbackCopy(txt); }
    }, { passive: false });

    function fallbackCopy(txt) {
      try {
        const ta = document.createElement("textarea");
        ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); ta.remove();
      } catch (e) { console.warn("[swefm/hud] copy failed", e); }
    }

    /* 업데이트 루프 */
    function update() {
      if (!visible) { animFrame = requestAnimationFrame(update); return; }
      const info = getCameraInfo(viewer);
      if (info) {
        /* 속도 계산 */
        const now = Date.now();
        const C = window.Cesium;
        if (prevPos && prevTime && C && C.Cartesian3 && C.Cartographic) {
          try {
            const p1 = C.Cartesian3.fromDegrees(prevPos.lon, prevPos.lat, prevPos.alt);
            const p2 = C.Cartesian3.fromDegrees(info.lon, info.lat, info.alt);
            const dist = C.Cartesian3.distance(p1, p2);
            const dt = (now - prevTime) / 1000;
            if (dt > 0) speedMs = dist / dt;
          } catch (e) { /* 무시 */ }
        }
        prevPos = info; prevTime = now;

        const lat = info.lat >= 0 ? info.lat.toFixed(5) + "°N" : (-info.lat).toFixed(5) + "°S";
        const lon = info.lon >= 0 ? info.lon.toFixed(5) + "°E" : (-info.lon).toFixed(5) + "°W";
        const alt = info.alt >= 1000 ? (info.alt / 1000).toFixed(1) + "km" : Math.round(info.alt) + "m";
        const spd = speedMs >= 1000 ? (speedMs / 1000).toFixed(1) + "km/s" : Math.round(speedMs) + "m/s";
        const hdg = ((info.heading % 360) + 360) % 360;
        const hdgStr = hdg.toFixed(1) + "°";

        coordDiv.innerHTML =
          "<div>📍 " + lat + " " + lon + "</div>" +
          "<div>⬆ " + alt + "  💨 " + spd + "  🧭 " + hdgStr + "</div>" +
          "<div>pitch " + info.pitch.toFixed(1) + "°</div>";

        compassDiv.innerHTML = compassSVG(hdg);
      }
      animFrame = requestAnimationFrame(update);
    }
    animFrame = requestAnimationFrame(update);

    /* 토글 버튼 */
    const toggle = document.createElement("button");
    toggle.id = "swefm-hud-toggle";
    toggle.textContent = "🌐";
    Object.assign(toggle.style, {
      position: "fixed", top: "10px", right: "80px", zIndex: "10000",
      minWidth: "44px", minHeight: "44px", fontSize: "18px",
      background: "rgba(60,60,80,0.9)", color: "#eee", border: "1px solid #555",
      borderRadius: "5px", cursor: "pointer"
    });
    toggle.addEventListener("click", () => {
      visible = !visible;
      container.style.display = visible ? "flex" : "none";
      try { localStorage.setItem(LS_VISIBLE, String(visible)); } catch (e) { /* 무시 */ }
    }, { passive: false });
    document.body.appendChild(toggle);
  }

  /* ── 초기화 ── */
  try {
    window.SWEFM.waitViewer(function (viewer) {
      try { buildUI(viewer); console.log("[swefm/hud] ready"); }
      catch (e) { console.warn("[swefm/hud] buildUI failed", e); }
    });
  } catch (e) { console.warn("[swefm/hud] init failed", e); }

  window.SWEFM.hud = {};
})();
