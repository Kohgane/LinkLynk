/* compare.js — 시간 비교 캡처 모듈
 * 목적: 현재 위치를 고정하고 06/12/18/00시 4장을 순차 캡처해 2x2 JPEG로 다운로드
 * 의존성: window.SWEFM.waitViewer, window.Cesium (선택), window.SWEFM.registerButton
 * 저장키: 없음 (다운로드 파일만)
 */
(function () {
  "use strict";

  const CAPTURE_DELAY_MS = 1500; // 캡처 전 타일 로딩 대기
  const TIME_SLOTS = [6, 12, 18, 0]; // 24h 실수

  /* ── #timeSlider 감지 ── */
  function getSlider() {
    return document.getElementById("timeSlider");
  }

  /* ── 슬라이더 값 설정 ── */
  function setSliderTime(t) {
    const sl = getSlider();
    if (!sl) return false;
    sl.value = String(t);
    try { sl.dispatchEvent(new Event("input", { bubbles: true })); } catch { /* 무시 */ }
    return true;
  }

  /* ── 지연 헬퍼 ── */
  function delay(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  /* ── 캔버스 캡처 ── */
  function captureFrame(viewer) {
    return new Promise(function (resolve, reject) {
      try {
        viewer.scene.render();
        const dataUrl = viewer.canvas.toDataURL("image/jpeg", 0.9);
        resolve(dataUrl);
      } catch (e) {
        reject(e);
      }
    });
  }

  /* ── 이미지 로드 헬퍼 ── */
  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      const img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = reject;
      img.src = src;
    });
  }

  /* ── 2x2 합성 ── */
  async function compose2x2(frames) {
    const w = frames[0].width, h = frames[0].height;
    const canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    const ctx = canvas.getContext("2d");
    const positions = [[0, 0], [w, 0], [0, h], [w, h]];
    for (let i = 0; i < 4; i++) {
      const [x, y] = positions[i];
      ctx.drawImage(frames[i], x, y, w, h);
      /* 시각 레이블 */
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(x + 4, y + 4, 52, 22);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 14px sans-serif";
      const label = TIME_SLOTS[i] === 0 ? "00:00" : TIME_SLOTS[i] + ":00";
      ctx.fillText(label, x + 8, y + 20);
    }
    return canvas.toDataURL("image/jpeg", 0.9);
  }

  /* ── 다운로드 ── */
  function download(dataUrl, filename) {
    try {
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () { document.body.removeChild(a); }, 300);
    } catch (e) {
      console.warn("[swefm/compare] download 실패", e);
    }
  }

  /* ── UI 상태 업데이트 ── */
  let panelEl = null;

  function showProgress(msg) {
    try {
      if (panelEl) {
        const el = panelEl.querySelector("#swefm-compare-progress");
        if (el) el.textContent = msg;
      }
    } catch { /* 무시 */ }
  }

  /* ── 캡처 프로세스 ── */
  let abortFlag = false;

  async function runCapture(viewer, origSliderVal) {
    abortFlag = false;
    const frames = [];
    try {
      for (let i = 0; i < TIME_SLOTS.length; i++) {
        if (abortFlag) throw new Error("사용자 중단");
        const t = TIME_SLOTS[i];
        setSliderTime(t);
        showProgress((i + 1) + "/" + TIME_SLOTS.length + " 준비 중...");
        await delay(CAPTURE_DELAY_MS);
        if (abortFlag) throw new Error("사용자 중단");
        showProgress((i + 1) + "/" + TIME_SLOTS.length + " 캡처 중...");
        const dataUrl = await captureFrame(viewer);
        const img = await loadImage(dataUrl);
        frames.push(img);
      }
      showProgress("합성 중...");
      const result = await compose2x2(frames);
      const ts = Date.now();
      download(result, "swef_compare_" + ts + ".jpg");
      showProgress("완료! 다운로드됨");
    } catch (e) {
      if (e.message && e.message.includes("중단")) {
        showProgress("중단됨");
      } else {
        console.warn("[swefm/compare] 캡처 실패", e);
        /* toast 알림 시도 */
        try {
          if (window.SWEF && typeof window.SWEF.toast === "function") {
            window.SWEF.toast("캡처 오류: " + (e.message || "알 수 없음"));
          }
        } catch { /* 무시 */ }
        showProgress("오류: " + (e.message || "실패"));
      }
    } finally {
      /* 슬라이더 복구 */
      try {
        if (origSliderVal !== null) setSliderTime(origSliderVal);
      } catch { /* 무시 */ }
      /* 버튼 복구 */
      try {
        if (panelEl) {
          const startBtn = panelEl.querySelector("#swefm-compare-start");
          const stopBtn = panelEl.querySelector("#swefm-compare-stop");
          if (startBtn) startBtn.disabled = false;
          if (stopBtn) stopBtn.style.display = "none";
        }
      } catch { /* 무시 */ }
    }
  }

  /* ── 패널 UI 구축 ── */
  function buildUI(viewer) {
    try {
      if (document.getElementById("swefm-compare-panel")) return;

      const panel = document.createElement("div");
      panel.id = "swefm-compare-panel";
      panel.style.cssText = [
        "display:none",
        "position:fixed",
        "right:80px",
        "top:50%",
        "transform:translateY(-50%)",
        "width:240px",
        "background:rgba(15,15,30,0.95)",
        "color:#eee",
        "border-radius:10px",
        "padding:14px",
        "z-index:42",
        "box-shadow:0 4px 20px rgba(0,0,0,.6)",
        "font-size:13px"
      ].join(";");

      panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-weight:600;font-size:14px">🕐 시간 비교</span>
          <button id="swefm-compare-close" style="background:none;border:none;color:#aaa;font-size:16px;cursor:pointer">✕</button>
        </div>
        <div style="color:#aaa;font-size:12px;margin-bottom:10px">06:00 / 12:00 / 18:00 / 00:00 4장을 현재 위치에서 캡처해 2×2 JPEG로 저장합니다.</div>
        <button id="swefm-compare-start" style="width:100%;padding:8px;background:#135;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:6px">📷 캡처 시작</button>
        <button id="swefm-compare-stop" style="display:none;width:100%;padding:8px;background:#622;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:6px">⏹ 중단</button>
        <div id="swefm-compare-progress" style="text-align:center;font-size:12px;color:#aaa;min-height:18px"></div>
      `;

      document.body.appendChild(panel);
      panelEl = panel;

      panel.querySelector("#swefm-compare-close").onclick = function () {
        panel.style.display = "none";
      };

      panel.querySelector("#swefm-compare-start").onclick = function () {
        try {
          const sl = getSlider();
          const origVal = sl ? parseFloat(sl.value) : null;
          const startBtn = panel.querySelector("#swefm-compare-start");
          const stopBtn = panel.querySelector("#swefm-compare-stop");
          startBtn.disabled = true;
          stopBtn.style.display = "block";
          runCapture(viewer, origVal);
        } catch (e) {
          console.warn("[swefm/compare] start 실패", e);
          showProgress("시작 오류");
        }
      };

      panel.querySelector("#swefm-compare-stop").onclick = function () {
        abortFlag = true;
        showProgress("중단 요청 중...");
      };

      /* 런처 버튼 등록 */
      function openPanel() {
        if (panel.style.display === "none" || !panel.style.display) {
          panel.style.display = "block";
        } else {
          panel.style.display = "none";
        }
      }

      /* #timeSlider 없으면 등록하지 않음 */
      if (!getSlider()) {
        /* MutationObserver로 나중에 추가될 때 등록 */
        try {
          const obs = new MutationObserver(function () {
            if (getSlider()) {
              obs.disconnect();
              registerLauncherBtn(openPanel);
            }
          });
          obs.observe(document.body, { childList: true, subtree: true });
        } catch (e) {
          console.warn("[swefm/compare] slider 감시 실패", e);
        }
      } else {
        registerLauncherBtn(openPanel);
      }

    } catch (e) {
      console.warn("[swefm/compare] buildUI 실패", e);
    }
  }

  function registerLauncherBtn(onClick) {
    const cfg = { id: "swefm-compare-btn", icon: "🕐", label: "시간비교", onClick: onClick };
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton(cfg);
    } else if (window.SWEFM) {
      if (!Array.isArray(window.SWEFM._btnQueue)) window.SWEFM._btnQueue = [];
      window.SWEFM._btnQueue.push(cfg);
    }
  }

  /* ── 초기화 ── */
  let _inited = false;
  function init() {
    if (_inited) return;
    _inited = true;
    try {
      if (window.SWEFM && window.SWEFM.waitViewer) {
        window.SWEFM.waitViewer(function (viewer) {
          try { buildUI(viewer); } catch (e) { console.warn("[swefm/compare] UI 실패", e); }
        });
      } else {
        console.warn("[swefm/compare] SWEFM 없음");
      }
    } catch (e) {
      console.warn("[swefm/compare] init 실패", e);
    }
  }

  window.addEventListener("swef:ready", function () { init(); });
  if (window.SWEF && window.SWEF.viewer) { init(); }
  setTimeout(init, 300);
})();
