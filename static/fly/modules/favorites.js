/* favorites.js — 즐겨찾기 & 히스토리 모듈
 * 목적: 현재 카메라 위치 저장/불러오기, 최근 방문 자동 기록
 * 의존성: window.Cesium, window.SWEFM.waitViewer
 * 저장키: swefm_favs, swefm_history
 */
(function () {
  "use strict";

  const LS_FAVS = "swefm_favs";
  const LS_HIST = "swefm_history";
  const MAX_HISTORY = 20;
  const MAX_FAVS = 100;

  /* ── 유틸 ── */
  function loadJSON(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
  }
  function saveJSON(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { console.warn("[swefm/favs] save failed", e); }
  }
  function rad2deg(r) { return r * 180 / Math.PI; }

  function getCameraPos(viewer) {
    try {
      const C = window.Cesium;
      let carto;
      if (viewer.camera.positionCartographic) {
        carto = viewer.camera.positionCartographic;
      } else if (C && C.Cartographic && C.Cartesian3) {
        carto = C.Cartographic.fromCartesian(viewer.camera.position);
      } else return null;
      return {
        lat: rad2deg(carto.latitude),
        lon: rad2deg(carto.longitude),
        alt: carto.height,
        heading: viewer.camera.heading || 0,
        pitch: viewer.camera.pitch || 0,
        roll: viewer.camera.roll || 0
      };
    } catch (e) { return null; }
  }

  function makeName(pos) {
    return pos.lat.toFixed(4) + "," + pos.lon.toFixed(4) + " @" + Math.round(pos.alt) + "m";
  }

  function flyToPos(viewer, pos) {
    try {
      if (typeof viewer.camera.flyTo === "function") {
        const C = window.Cesium;
        if (C && C.Math && C.Cartesian3) {
          viewer.camera.flyTo({
            destination: C.Cartesian3.fromDegrees(pos.lon, pos.lat, pos.alt),
            orientation: { heading: pos.heading, pitch: pos.pitch, roll: pos.roll }
          });
        }
      } else if (window.SWEF && typeof window.SWEF.flyToDest === "function") {
        window.SWEF.flyToDest(pos.lat, pos.lon, pos.alt);
      }
    } catch (e) { console.warn("[swefm/favs] flyTo failed", e); }
  }

  /* ── 히스토리 ── */
  function addHistory(pos, label) {
    const hist = loadJSON(LS_HIST, []);
    const entry = { lat: pos.lat, lon: pos.lon, alt: pos.alt, heading: pos.heading, pitch: pos.pitch, roll: pos.roll, label, ts: Date.now() };
    const filtered = hist.filter(h => !(Math.abs(h.lat - pos.lat) < 0.001 && Math.abs(h.lon - pos.lon) < 0.001));
    filtered.unshift(entry);
    saveJSON(LS_HIST, filtered.slice(0, MAX_HISTORY));
  }

  /* ── UI 빌더 ── */
  function buildUI(viewer) {
    const panel = document.createElement("div");
    panel.id = "swefm-favs-panel";
    Object.assign(panel.style, {
      position: "fixed", top: "60px", left: "10px", zIndex: "9999",
      background: "rgba(20,20,30,0.92)", color: "#eee", borderRadius: "8px",
      padding: "8px", width: "260px", maxHeight: "70vh", overflowY: "auto",
      fontFamily: "sans-serif", fontSize: "13px", display: "none",
      boxShadow: "0 2px 12px rgba(0,0,0,0.6)"
    });

    /* 헤더 */
    const header = document.createElement("div");
    Object.assign(header.style, { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" });
    const title = document.createElement("span");
    title.textContent = "⭐ 즐겨찾기";
    Object.assign(title.style, { fontWeight: "bold" });

    const btnSave = makeBtn("📍 저장", () => {
      const pos = getCameraPos(viewer);
      if (!pos) return console.warn("[swefm/favs] 카메라 위치 없음");
      const name = prompt("이름 (비워두면 자동생성):", "") || makeName(pos);
      const favs = loadJSON(LS_FAVS, []);
      favs.unshift({ name, ...pos, id: Date.now() });
      saveJSON(LS_FAVS, favs.slice(0, MAX_FAVS));
      addHistory(pos, name);
      renderLists();
    });

    const btnExport = makeBtn("⬇ 내보내기", exportFavs);
    const btnImport = makeBtn("⬆ 가져오기", importFavs);

    header.append(title, btnSave, btnExport, btnImport);
    panel.appendChild(header);

    /* 탭 */
    const tabs = document.createElement("div");
    Object.assign(tabs.style, { display: "flex", gap: "4px", marginBottom: "6px" });
    const tabFav = makeTabBtn("즐겨찾기", true);
    const tabHist = makeTabBtn("히스토리", false);
    tabs.append(tabFav, tabHist);
    panel.appendChild(tabs);

    const listEl = document.createElement("div");
    panel.appendChild(listEl);

    let currentTab = "favs";
    function switchTab(t) {
      currentTab = t;
      tabFav.style.fontWeight = t === "favs" ? "bold" : "normal";
      tabHist.style.fontWeight = t === "hist" ? "bold" : "normal";
      renderLists();
    }
    tabFav.addEventListener("click", () => switchTab("favs"), { passive: false });
    tabHist.addEventListener("click", () => switchTab("hist"), { passive: false });

    function renderLists() {
      listEl.innerHTML = "";
      const items = currentTab === "favs" ? loadJSON(LS_FAVS, []) : loadJSON(LS_HIST, []);
      if (!items.length) { listEl.textContent = "없음"; return; }
      items.forEach((item, idx) => {
        const row = document.createElement("div");
        Object.assign(row.style, { display: "flex", alignItems: "center", gap: "4px", padding: "4px 2px", borderBottom: "1px solid #333" });

        const btnGo = makeBtn(item.name || item.label || makeName(item), () => {
          flyToPos(viewer, item);
          addHistory(item, item.name || item.label);
        });
        Object.assign(btnGo.style, { flex: "1", textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });

        if (currentTab === "hist") {
          const btnPromote = makeBtn("⭐", () => {
            const favs = loadJSON(LS_FAVS, []);
            favs.unshift({ ...item, name: item.label || makeName(item), id: Date.now() });
            saveJSON(LS_FAVS, favs.slice(0, MAX_FAVS));
            renderLists();
          });
          btnPromote.title = "즐겨찾기로 승격";
          Object.assign(btnPromote.style, { minWidth: "30px" });
          row.append(btnGo, btnPromote);
        } else {
          const btnDel = makeBtn("🗑", () => {
            const favs = loadJSON(LS_FAVS, []);
            favs.splice(idx, 1);
            saveJSON(LS_FAVS, favs);
            renderLists();
          });
          btnDel.title = "삭제";
          Object.assign(btnDel.style, { minWidth: "30px" });
          row.append(btnGo, btnDel);
        }
        listEl.appendChild(row);
      });
    }

    panel.renderLists = renderLists;

    /* 내보내기/가져오기 */
    function exportFavs() {
      try {
        const data = { favs: loadJSON(LS_FAVS, []), history: loadJSON(LS_HIST, []) };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "swefm_favs.json"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (e) { console.warn("[swefm/favs] export failed", e); }
    }

    function importFavs() {
      try {
        const input = document.createElement("input");
        input.type = "file"; input.accept = ".json";
        input.addEventListener("change", () => {
          const file = input.files[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = (ev) => {
            try {
              const data = JSON.parse(ev.target.result);
              if (data.favs) {
                const cur = loadJSON(LS_FAVS, []);
                const merged = [...data.favs, ...cur].slice(0, MAX_FAVS);
                saveJSON(LS_FAVS, merged);
              }
              if (data.history) {
                const cur = loadJSON(LS_HIST, []);
                const merged = [...data.history, ...cur].slice(0, MAX_HISTORY);
                saveJSON(LS_HIST, merged);
              }
              renderLists();
            } catch (e) { console.warn("[swefm/favs] import parse failed", e); }
          };
          reader.readAsText(file);
        }, { passive: false });
        input.click();
      } catch (e) { console.warn("[swefm/favs] import failed", e); }
    }

    document.body.appendChild(panel);
    renderLists();

    /* 토글 버튼 */
    const toggle = makeBtn("⭐", () => {
      const vis = panel.style.display === "none";
      panel.style.display = vis ? "block" : "none";
      if (vis) renderLists();
    });
    toggle.id = "swefm-favs-toggle";
    Object.assign(toggle.style, {
      position: "fixed", top: "10px", left: "10px", zIndex: "10000",
      minWidth: "44px", minHeight: "44px", fontSize: "18px"
    });
    document.body.appendChild(toggle);
  }

  function makeBtn(text, onClick) {
    const b = document.createElement("button");
    b.textContent = text;
    Object.assign(b.style, {
      background: "rgba(60,60,80,0.9)", color: "#eee", border: "1px solid #555",
      borderRadius: "5px", padding: "4px 7px", cursor: "pointer",
      minHeight: "44px", fontSize: "13px"
    });
    b.addEventListener("click", onClick, { passive: false });
    return b;
  }

  function makeTabBtn(text, active) {
    const b = makeBtn(text, null);
    b.style.flex = "1";
    b.style.fontWeight = active ? "bold" : "normal";
    b.removeEventListener("click", null);
    return b;
  }

  /* ── 초기화 ── */
  try {
    window.SWEFM.waitViewer(function (viewer) {
      try { buildUI(viewer); console.log("[swefm/favs] ready"); }
      catch (e) { console.warn("[swefm/favs] buildUI failed", e); }
    });
  } catch (e) { console.warn("[swefm/favs] init failed", e); }

  /* 공개 API */
  window.SWEFM.favorites = { addHistory, loadJSON, saveJSON, makeName };
})();
