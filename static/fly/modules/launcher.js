/* SWEF modules — launcher.js
 * 우측 중앙 접이식 런처: 모듈 버튼들을 한 곳에 모읍니다.
 */
(function () {
  "use strict";

  var LAUNCHER_ID = "swefm-launcher";
  var TRAY_ID = "swefm-launcher-tray";
  var STORAGE_KEY = "swefm_launcher_open";

  var buttons = []; // { id, icon, label, onClick, el, chipEl }
  var open = false;
  var launcherEl = null;
  var trayEl = null;

  function safeGet(key, fallback) {
    try { return localStorage.getItem(key); } catch (e) { return fallback; }
  }
  function safeSet(key, val) {
    try { localStorage.setItem(key, val); } catch (e) { /* ignore */ }
  }

  function applyOpenState() {
    if (!trayEl) return;
    if (open) {
      trayEl.style.opacity = "1";
      trayEl.style.pointerEvents = "auto";
      trayEl.style.transform = "scaleY(1)";
      launcherEl.title = "닫기";
    } else {
      trayEl.style.opacity = "0";
      trayEl.style.pointerEvents = "none";
      trayEl.style.transform = "scaleY(0)";
      launcherEl.title = "모듈 열기";
    }
    buttons.forEach(function (btn) {
      if (btn.chipEl) {
        btn.chipEl.style.display = open ? "inline-block" : "none";
      }
    });
  }

  function toggle() {
    open = !open;
    safeSet(STORAGE_KEY, open ? "1" : "0");
    applyOpenState();
  }

  function renderButton(btn) {
    if (!trayEl) return;
    if (document.getElementById(btn.id)) return; // 중복 방지

    var row = document.createElement("div");
    row.style.cssText = [
      "display:flex",
      "align-items:center",
      "justify-content:flex-end",
      "margin-bottom:8px",
      "position:relative",
    ].join(";");

    // 라벨 칩
    var chip = document.createElement("span");
    chip.textContent = btn.label || "";
    chip.style.cssText = [
      "background:rgba(0,0,0,0.72)",
      "color:#fff",
      "font-size:12px",
      "padding:3px 8px",
      "border-radius:12px",
      "margin-right:8px",
      "white-space:nowrap",
      "display:" + (open ? "inline-block" : "none"),
    ].join(";");
    btn.chipEl = chip;

    // 원형 버튼
    var b = document.createElement("button");
    b.id = btn.id;
    b.textContent = btn.icon || "●";
    b.style.cssText = [
      "width:44px",
      "height:44px",
      "border-radius:50%",
      "border:none",
      "background:rgba(0,0,0,0.65)",
      "color:#fff",
      "font-size:20px",
      "cursor:pointer",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "box-shadow:0 2px 8px rgba(0,0,0,0.4)",
      "flex-shrink:0",
    ].join(";");
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      try { btn.onClick && btn.onClick(); } catch (err) { console.warn("[swefm] launcher btn error", err); }
    });
    btn.el = b;

    row.appendChild(chip);
    row.appendChild(b);
    trayEl.appendChild(row);
  }

  function registerButton(cfg) {
    try {
      if (!cfg || !cfg.id) { console.warn("[swefm] registerButton: id 필요"); return; }
      var exists = buttons.some(function (b) { return b.id === cfg.id; });
      if (exists) return;
      var btn = { id: cfg.id, icon: cfg.icon || "●", label: cfg.label || "", onClick: cfg.onClick || null, el: null, chipEl: null };
      buttons.push(btn);
      renderButton(btn);
    } catch (e) {
      console.warn("[swefm] registerButton error", e);
    }
  }

  function buildLauncher() {
    try {
      if (document.getElementById(LAUNCHER_ID)) return;

      // 트레이 (버튼 목록, 런처 위쪽)
      trayEl = document.createElement("div");
      trayEl.id = TRAY_ID;
      trayEl.style.cssText = [
        "position:fixed",
        "right:12px",
        "display:flex",
        "flex-direction:column",
        "align-items:flex-end",
        "padding-bottom:8px",
        "transition:opacity 0.25s ease, transform 0.25s ease",
        "transform-origin:bottom center",
        "z-index:9499",
      ].join(";");

      // 런처 버튼
      launcherEl = document.createElement("button");
      launcherEl.id = LAUNCHER_ID;
      launcherEl.textContent = "☰";
      launcherEl.title = "모듈 열기";
      launcherEl.style.cssText = [
        "position:fixed",
        "right:12px",
        "top:50%",
        "transform:translateY(-50%)",
        "width:56px",
        "height:56px",
        "border-radius:50%",
        "border:none",
        "background:rgba(0,0,0,0.65)",
        "color:#fff",
        "font-size:24px",
        "cursor:pointer",
        "z-index:9500",
        "display:flex",
        "align-items:center",
        "justify-content:center",
        "box-shadow:0 2px 10px rgba(0,0,0,0.5)",
      ].join(";");
      launcherEl.addEventListener("click", function (e) {
        e.stopPropagation();
        toggle();
      });

      document.body.appendChild(trayEl);
      document.body.appendChild(launcherEl);

      // 런처 위치를 기반으로 트레이 위치 동기
      function positionTray() {
        var rect = launcherEl.getBoundingClientRect();
        trayEl.style.top = "";
        trayEl.style.bottom = (window.innerHeight - rect.top) + "px";
      }
      positionTray();
      window.addEventListener("resize", positionTray);

      // 저장된 열림 상태 복원
      open = safeGet(STORAGE_KEY) === "1";
      applyOpenState();

      // 큐에 쌓인 버튼 일괄 등록
      var q = (window.SWEFM && window.SWEFM._btnQueue) || [];
      q.forEach(function (cfg) { registerButton(cfg); });
      if (window.SWEFM) {
        window.SWEFM._btnQueue = [];
        window.SWEFM._registerButtonImpl = registerButton;
      }

      console.log("[swefm] launcher ready");
    } catch (e) {
      console.warn("[swefm] launcher build error", e);
    }
  }

  // DOM 준비 후 런처 구성
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildLauncher);
  } else {
    buildLauncher();
  }

})();
