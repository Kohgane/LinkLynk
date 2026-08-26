/* favorites.js — 즐겨찾기 & 최근 방문 히스토리
 * 목적: 카메라 위치 저장/불러오기, 최근 20곳 자동 기록, JSON 내보내기/가져오기
 * 의존성: window.SWEFM.waitViewer, window.Cesium (선택)
 * 저장키: swefm_favs, swefm_history
 */
(function () {
  "use strict";

  /* ── 상수 ── */
  const KEY_FAVS = "swefm_favs";
  const KEY_HIST = "swefm_history";
  const MAX_HIST = 20;
  const MAX_FAVS = 100;

  /* ── 스토리지 헬퍼 ── */
  function load(key, def) {
    try { return JSON.parse(localStorage.getItem(key)) || def; } catch { return def; }
  }
  function save(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { console.warn("[swefm/favs] 저장 실패", key); }
  }

  /* ── 카메라 위치 추출 ── */
  function getCamPos(viewer) {
    try {
      const cam = viewer.camera;
      let lat, lon, alt;
      if (cam.positionCartographic) {
        const c = cam.positionCartographic;
        lat = window.Cesium ? window.Cesium.Math.toDegrees(c.latitude) : c.latitude * (180 / Math.PI);
        lon = window.Cesium ? window.Cesium.Math.toDegrees(c.longitude) : c.longitude * (180 / Math.PI);
        alt = c.height;
      } else if (window.Cesium && Cesium.Cartographic && cam.position) {
        const c = Cesium.Cartographic.fromCartesian(cam.position);
        lat = Cesium.Math.toDegrees(c.latitude);
        lon = Cesium.Math.toDegrees(c.longitude);
        alt = c.height;
      } else {
        return null;
      }
      return {
        lat: +lat.toFixed(6), lon: +lon.toFixed(6), alt: +alt.toFixed(1),
        heading: +(cam.heading * 180 / Math.PI).toFixed(2),
        pitch: +(cam.pitch * 180 / Math.PI).toFixed(2)
      };
    } catch (e) {
      console.warn("[swefm/favs] getCamPos 실패", e);
      return null;
    }
  }

  /* ── flyTo 헬퍼 ── */
  function flyToPos(viewer, pos) {
    try {
      if (!window.Cesium) return;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(pos.lon, pos.lat, pos.alt),
        orientation: {
          heading: Cesium.Math.toRadians(pos.heading || 0),
          pitch: Cesium.Math.toRadians(pos.pitch || -30),
          roll: 0
        },
        duration: 2
      });
    } catch (e) {
      console.warn("[swefm/favs] flyTo 실패", e);
    }
  }

  /* ── 데이터 관리 ── */
  function addHistory(pos) {
    if (!pos) return;
    let hist = load(KEY_HIST, []);
    // 중복 제거 (1도 이내)
    hist = hist.filter(h => Math.abs(h.lat - pos.lat) > 0.001 || Math.abs(h.lon - pos.lon) > 0.001);
    hist.unshift({ ...pos, ts: Date.now(), label: makeLabel(pos) });
    if (hist.length > MAX_HIST) hist = hist.slice(0, MAX_HIST);
    save(KEY_HIST, hist);
    return hist;
  }

  function addFav(pos, name) {
    const favs = load(KEY_FAVS, []);
    if (favs.length >= MAX_FAVS) { console.warn("[swefm/favs] 즐겨찾기 최대치"); return favs; }
    favs.unshift({ ...pos, ts: Date.now(), id: Date.now(), label: name || makeLabel(pos) });
    save(KEY_FAVS, favs);
    return favs;
  }

  function removeFav(id) {
    const favs = load(KEY_FAVS, []).filter(f => f.id !== id);
    save(KEY_FAVS, favs);
    return favs;
  }

  function promoteHistory(hist_item) {
    return addFav(hist_item, hist_item.label);
  }

  function makeLabel(pos) {
    return `${pos.lat.toFixed(4)},${pos.lon.toFixed(4)} @${Math.round(pos.alt)}m`;
  }

  /* ── UI 생성 ── */
  function buildUI(viewer) {
    // 패널
    const panel = document.createElement("div");
    panel.id = "swefm-favs-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "즐겨찾기 및 히스토리");
    panel.style.cssText = `display:none;position:fixed;top:50%;left:12px;transform:translateY(-50%);z-index:9000;
      width:280px;max-height:60vh;overflow-y:auto;background:rgba(15,15,25,.92);
      color:#eee;border-radius:10px;padding:10px;font-size:13px;
      box-shadow:0 4px 20px rgba(0,0,0,.6);`;
    document.body.appendChild(panel);

    function renderPanel() {
      const favs = load(KEY_FAVS, []);
      const hist = load(KEY_HIST, []);

      panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <b>즐겨찾기 & 히스토리</b>
          <button id="swefm-favs-close" type="button" aria-label="닫기" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#aaa;font-size:16px;cursor:pointer;padding:0;min-width:44px;min-height:44px">✕</button>
        </div>
        <div style="display:flex;gap:6px;margin-bottom:8px">
          <button id="swefm-favs-save" type="button" aria-label="현재 위치 저장" style="${btnStyle('#2a6','#fff')}">📍 현재 위치 저장</button>
          <button id="swefm-favs-export" type="button" aria-label="즐겨찾기 내보내기" style="${btnStyle('#336','#ccc')}">⬇ 내보내기</button>
          <button id="swefm-favs-import-btn" type="button" aria-label="즐겨찾기 가져오기" style="${btnStyle('#336','#ccc')}">⬆ 가져오기</button>
        </div>
        <input id="swefm-favs-import-file" type="file" accept=".json" style="display:none">
        <div style="font-weight:600;margin:6px 0 4px;color:#FFD700">즐겨찾기 (${favs.length})</div>
        <div id="swefm-favs-list">${favs.length ? favs.map(f => favRow(f, true)).join("") : '<div style="color:#bbb">없음</div>'}</div>
        <div style="font-weight:600;margin:10px 0 4px;color:#88BBFF">최근 방문 (${hist.length})</div>
        <div id="swefm-hist-list">${hist.length ? hist.map(h => favRow(h, false)).join("") : '<div style="color:#bbb">없음</div>'}</div>
      `;

      // 이벤트
      panel.querySelector("#swefm-favs-close").onclick = () => { panel.style.display = "none"; };
      panel.querySelector("#swefm-favs-save").onclick = () => {
        const pos = getCamPos(viewer);
        if (!pos) { console.warn("[swefm/favs] 위치 없음"); return; }
        const name = prompt("즐겨찾기 이름 (빈칸=자동)", makeLabel(pos));
        if (name === null) return;
        addFav(pos, name.trim() || makeLabel(pos));
        renderPanel();
      };
      panel.querySelector("#swefm-favs-export").onclick = exportJSON;
      panel.querySelector("#swefm-favs-import-btn").onclick = () => panel.querySelector("#swefm-favs-import-file").click();
      panel.querySelector("#swefm-favs-import-file").onchange = importJSON;

      panel.querySelectorAll(".swefm-fav-fly").forEach(el => {
        el.onclick = () => {
          const pos = JSON.parse(el.dataset.pos);
          flyToPos(viewer, pos);
          addHistory(pos);
        };
      });
      panel.querySelectorAll(".swefm-fav-del").forEach(el => {
        el.onclick = () => { removeFav(+el.dataset.id); renderPanel(); };
      });
      panel.querySelectorAll(".swefm-hist-promote").forEach(el => {
        el.onclick = () => { promoteHistory(JSON.parse(el.dataset.pos)); renderPanel(); };
      });
    }

    function btnStyle(bg, fg) {
      return `background:${bg};color:${fg};border:none;border-radius:6px;padding:8px 10px;cursor:pointer;font-size:11px;touch-action:manipulation;min-height:44px`;
    }

    function favRow(item, isFav) {
      const posStr = JSON.stringify(item).replace(/"/g, "&quot;");
      const del = isFav ? `<button class="swefm-fav-del" type="button" aria-label="즐겨찾기 삭제" data-id="${item.id}" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#f66;cursor:pointer;padding:0;min-width:44px;min-height:44px">✕</button>` : "";
      const promote = !isFav ? `<button class="swefm-hist-promote" type="button" aria-label="최근 위치를 즐겨찾기로 저장" data-pos="${posStr}" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#FFD700;cursor:pointer;padding:0;min-width:44px;min-height:44px">★</button>` : "";
      return `<div style="display:flex;align-items:center;gap:4px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.07)">
        <button class="swefm-fav-fly" type="button" aria-label="${isFav ? "즐겨찾기 위치로 이동" : "최근 위치로 이동"}" data-pos="${posStr}" style="flex:1;text-align:left;background:none;border:none;color:#eee;cursor:pointer;font-size:12px;padding:8px 0;touch-action:manipulation;min-height:44px">${item.label || makeLabel(item)}</button>
        ${promote}${del}
      </div>`;
    }

    function exportJSON() {
      const data = { favs: load(KEY_FAVS, []), history: load(KEY_HIST, []) };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "swefm_favorites.json"; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
    }

    function importJSON(e) {
      const file = e.target.files[0]; if (!file) return;
      const reader = new FileReader();
      reader.onload = ev => {
        try {
          const data = JSON.parse(ev.target.result);
          if (data.favs) {
            const existing = load(KEY_FAVS, []);
            const ids = new Set(existing.map(f => f.id));
            const merged = [...existing, ...data.favs.filter(f => !ids.has(f.id))].slice(0, MAX_FAVS);
            save(KEY_FAVS, merged);
          }
          if (data.history) {
            const existing = load(KEY_HIST, []);
            const merged = [...data.history, ...existing].slice(0, MAX_HIST);
            save(KEY_HIST, merged);
          }
          renderPanel();
        } catch (err) { console.warn("[swefm/favs] import 실패", err); }
      };
      reader.readAsText(file);
      e.target.value = "";
    }

    // 런처 등록
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-favs",
        icon: "★",
        label: "즐겨찾기",
        onClick: function () {
          if (panel.style.display === "none") { renderPanel(); panel.style.display = "block"; }
          else panel.style.display = "none";
        }
      });
    } else {
      console.warn("[swefm/favs] registerButton 없음 — 런처 미로드");
    }

    // 자동 히스토리: 30초마다 기록
    setInterval(() => {
      try {
        const pos = getCamPos(viewer);
        if (pos) addHistory(pos);
      } catch { /* 무시 */ }
    }, 30000);
  }

  /* ── 초기화 ── */
  function init() {
    try {
      window.SWEFM.waitViewer(viewer => {
        try { buildUI(viewer); } catch (e) { console.warn("[swefm/favs] UI 초기화 실패", e); }
      });
    } catch (e) {
      console.warn("[swefm/favs] 초기화 실패", e);
    }
  }

  init();
})();
