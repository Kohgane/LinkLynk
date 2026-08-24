/* share.js — 공유 모듈
 * 목적: 현재 카메라 위치를 딥링크로 변환해 클립보드 복사 / 공유시트 / 최근 목록 제공
 * 의존성: window.SWEFM.waitViewer, window.Cesium (선택), window.SWEFM.registerButton
 * 저장키: swefm_links
 */
(function () {
  "use strict";

  const KEY_LINKS = "swefm_links";
  const MAX_LINKS = 5;

  /* ── 스토리지 헬퍼 ── */
  function loadLinks() {
    try { return JSON.parse(localStorage.getItem(KEY_LINKS)) || []; } catch { return []; }
  }
  function saveLinks(arr) {
    try { localStorage.setItem(KEY_LINKS, JSON.stringify(arr.slice(0, MAX_LINKS))); } catch { console.warn("[swefm/share] 저장 실패"); }
  }

  /* ── 카메라 상태 추출 ── */
  function getCamState(viewer) {
    try {
      const cam = viewer.camera;
      if (!cam) return null;
      let lat, lon, h, hd, pt;
      const C = window.Cesium;
      if (cam.positionCartographic) {
        const c = cam.positionCartographic;
        lat = C ? C.Math.toDegrees(c.latitude) : c.latitude * (180 / Math.PI);
        lon = C ? C.Math.toDegrees(c.longitude) : c.longitude * (180 / Math.PI);
        h = c.height;
      } else if (C && cam.position) {
        const c = C.Cartographic.fromCartesian(cam.position);
        lat = C.Math.toDegrees(c.latitude);
        lon = C.Math.toDegrees(c.longitude);
        h = c.height;
      } else {
        return null;
      }
      hd = cam.heading != null ? cam.heading : 0;
      pt = cam.pitch != null ? cam.pitch : 0;

      /* 시각: #timeSlider 값, 없으면 12 */
      let t = 12;
      try {
        const sl = document.getElementById("timeSlider");
        if (sl) { const v = parseFloat(sl.value); if (!isNaN(v)) t = v; }
      } catch { /* 무시 */ }

      return {
        lon: +lon.toFixed(6),
        lat: +lat.toFixed(6),
        h: +h.toFixed(1),
        hd: +hd.toFixed(6),
        pt: +pt.toFixed(6),
        t: +t.toFixed(2)
      };
    } catch (e) {
      console.warn("[swefm/share] getCamState 실패", e);
      return null;
    }
  }

  /* ── 딥링크 생성 ── */
  function buildUrl(state) {
    try {
      const p = new URLSearchParams();
      p.set("lon", state.lon);
      p.set("lat", state.lat);
      p.set("h", state.h);
      p.set("hd", state.hd);
      p.set("pt", state.pt);
      p.set("t", state.t);
      return location.origin + location.pathname + "?" + p.toString();
    } catch (e) {
      console.warn("[swefm/share] buildUrl 실패", e);
      return null;
    }
  }

  /* ── 클립보드 복사 ── */
  function copyText(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(function (e) {
          console.warn("[swefm/share] clipboard 실패, fallback 시도", e);
          fallbackCopy(text);
        });
      }
    } catch { /* 무시 */ }
    fallbackCopy(text);
  }
  function fallbackCopy(text) {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.cssText = "position:fixed;opacity:0;top:0;left:0;";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch (e) {
      console.warn("[swefm/share] fallbackCopy 실패", e);
    }
  }

  /* ── 패널 UI ── */
  function buildUI(viewer) {
    try {
      if (document.getElementById("swefm-share-panel")) return;

      /* 패널 */
      const panel = document.createElement("div");
      panel.id = "swefm-share-panel";
      panel.style.cssText = [
        "display:none",
        "position:fixed",
        "right:80px",
        "top:50%",
        "transform:translateY(-50%)",
        "width:300px",
        "max-height:70vh",
        "overflow-y:auto",
        "background:rgba(15,15,30,0.95)",
        "color:#eee",
        "border-radius:10px",
        "padding:14px",
        "z-index:42",
        "box-shadow:0 4px 20px rgba(0,0,0,.6)",
        "font-size:13px"
      ].join(";");
      document.body.appendChild(panel);

      function render() {
        const links = loadLinks();
        panel.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <span style="font-weight:600;font-size:14px">🔗 공유</span>
            <button id="swefm-share-close" style="background:none;border:none;color:#aaa;font-size:16px;cursor:pointer">✕</button>
          </div>
          <button id="swefm-share-copy" style="width:100%;padding:8px;background:#1a6;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:6px">📋 현재 위치 링크 복사</button>
          <button id="swefm-share-native" style="width:100%;padding:8px;background:#226;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:10px;${navigator.share ? "" : "display:none"}">📤 공유하기</button>
          <div id="swefm-share-status" style="text-align:center;font-size:12px;color:#aaa;min-height:18px;margin-bottom:8px"></div>
          <div style="font-weight:600;margin-bottom:6px;color:#FFD700">최근 링크 (${links.length})</div>
          <div id="swefm-share-list">
            ${links.length === 0 ? '<div style="color:#666">없음</div>' :
            links.map((lnk, i) =>
              `<div style="display:flex;align-items:center;gap:4px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.07)">
                <span style="flex:1;color:#88AAFF;font-size:11px;word-break:break-all;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${lnk}</span>
                <button data-idx="${i}" class="swefm-share-recopy" style="background:none;border:none;color:#aaa;cursor:pointer;font-size:12px;padding:0 3px" title="재복사">📋</button>
                <button data-idx="${i}" class="swefm-share-del" style="background:none;border:none;color:#f66;cursor:pointer;font-size:12px;padding:0 3px" title="삭제">✕</button>
              </div>`
            ).join("")}
          </div>
        `;

        panel.querySelector("#swefm-share-close").onclick = () => { panel.style.display = "none"; };

        panel.querySelector("#swefm-share-copy").onclick = function () {
          try {
            const state = getCamState(viewer);
            if (!state) { showStatus("카메라 정보 없음", "#f66"); return; }
            const url = buildUrl(state);
            if (!url) { showStatus("URL 생성 실패", "#f66"); return; }
            copyText(url);
            const links = loadLinks();
            if (!links.includes(url)) { links.unshift(url); saveLinks(links); }
            showStatus("링크 복사됨 ✓", "#4f4");
            setTimeout(render, 300);
          } catch (e) { console.warn("[swefm/share] 복사 실패", e); showStatus("오류 발생", "#f66"); }
        };

        const nativeBtn = panel.querySelector("#swefm-share-native");
        if (nativeBtn) {
          nativeBtn.onclick = function () {
            try {
              const state = getCamState(viewer);
              if (!state) { showStatus("카메라 정보 없음", "#f66"); return; }
              const url = buildUrl(state);
              if (!url) return;
              navigator.share({ title: "LinkLynk 위치 공유", url: url }).catch(function (e) {
                console.warn("[swefm/share] share 실패", e);
              });
            } catch (e) { console.warn("[swefm/share] nativeShare 실패", e); }
          };
        }

        panel.querySelectorAll(".swefm-share-recopy").forEach(function (btn) {
          btn.onclick = function () {
            try {
              const idx = parseInt(btn.dataset.idx);
              const links = loadLinks();
              if (links[idx]) { copyText(links[idx]); showStatus("재복사됨 ✓", "#4f4"); }
            } catch (e) { console.warn("[swefm/share] 재복사 실패", e); }
          };
        });

        panel.querySelectorAll(".swefm-share-del").forEach(function (btn) {
          btn.onclick = function () {
            try {
              const idx = parseInt(btn.dataset.idx);
              const links = loadLinks();
              links.splice(idx, 1);
              saveLinks(links);
              render();
            } catch (e) { console.warn("[swefm/share] 삭제 실패", e); }
          };
        });
      }

      function showStatus(msg, color) {
        try {
          const el = panel.querySelector("#swefm-share-status");
          if (el) { el.textContent = msg; el.style.color = color || "#aaa"; }
        } catch { /* 무시 */ }
      }

      /* 런처에 버튼 등록 */
      function openPanel() {
        if (panel.style.display === "none" || !panel.style.display) {
          render();
          panel.style.display = "block";
        } else {
          panel.style.display = "none";
        }
      }

      if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
        window.SWEFM.registerButton({ id: "swefm-share-btn", icon: "🔗", label: "공유", onClick: openPanel });
      } else if (window.SWEFM) {
        /* 큐잉 */
        if (!Array.isArray(window.SWEFM._btnQueue)) window.SWEFM._btnQueue = [];
        window.SWEFM._btnQueue.push({ id: "swefm-share-btn", icon: "🔗", label: "공유", onClick: openPanel });
      }

    } catch (e) {
      console.warn("[swefm/share] buildUI 실패", e);
    }
  }

  /* ── 초기화 ── */
  function init() {
    try {
      if (window.SWEFM && window.SWEFM.waitViewer) {
        window.SWEFM.waitViewer(function (viewer) {
          try { buildUI(viewer); } catch (e) { console.warn("[swefm/share] UI 실패", e); }
        });
      } else {
        console.warn("[swefm/share] SWEFM 없음");
      }
    } catch (e) {
      console.warn("[swefm/share] init 실패", e);
    }
  }

  window.addEventListener("swef:ready", function () { init(); });
  if (window.SWEF && window.SWEF.viewer) { init(); }
  setTimeout(init, 300);
})();
