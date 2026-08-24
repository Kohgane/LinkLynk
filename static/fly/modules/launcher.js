/* launcher.js — 통합 모듈 런처
 * 목적: 우측 중앙에 접이식 원형 버튼을 제공해 모든 SWEF 모듈 버튼을 한 곳에 통합
 * 의존성: window.SWEFM (index.js 선행 로드 필요)
 * 저장키: swefm_launcher_open
 * DOM id: swefm-launcher, swefm-launcher-items
 */
(function () {
  "use strict";

  const KEY_OPEN = "swefm_launcher_open";

  /* ── 저장/불러오기 ── */
  function loadOpen() {
    try { return localStorage.getItem(KEY_OPEN) === "1"; } catch { return false; }
  }
  function saveOpen(v) {
    try { localStorage.setItem(KEY_OPEN, v ? "1" : "0"); } catch { /* 무시 */ }
  }

  /* ── 런처 UI 구축 ── */
  function buildLauncher() {
    try {
      if (document.getElementById("swefm-launcher")) return; // 중복 방지

      /* 메인 토글 버튼 */
      const toggle = document.createElement("button");
      toggle.id = "swefm-launcher";
      toggle.title = "모듈 메뉴";
      toggle.textContent = "☰";
      toggle.style.cssText = [
        "position:fixed",
        "right:12px",
        "top:50%",
        "transform:translateY(-50%)",
        "width:56px",
        "height:56px",
        "border-radius:50%",
        "border:none",
        "background:rgba(20,20,40,0.88)",
        "color:#fff",
        "font-size:22px",
        "cursor:pointer",
        "z-index:40",
        "box-shadow:0 2px 10px rgba(0,0,0,.5)",
        "touch-action:manipulation",
        "display:flex",
        "align-items:center",
        "justify-content:center",
        "padding:0",
        "line-height:1"
      ].join(";");

      /* 버튼 목록 컨테이너 */
      const items = document.createElement("div");
      items.id = "swefm-launcher-items";
      items.style.cssText = [
        "position:fixed",
        "right:12px",
        "top:50%",
        "transform:translateY(-50%)",
        "display:flex",
        "flex-direction:column",
        "align-items:flex-end",
        "gap:8px",
        "z-index:39",
        "pointer-events:none",
        "opacity:0",
        "transition:opacity .2s ease"
      ].join(";");

      document.body.appendChild(items);
      document.body.appendChild(toggle);

      /* 열림 상태 복원 */
      let isOpen = loadOpen();
      applyOpen(isOpen, items, toggle);

      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        isOpen = !isOpen;
        saveOpen(isOpen);
        applyOpen(isOpen, items, toggle);
      }, { passive: true });

      /* 외부 클릭 시 닫기 */
      document.addEventListener("click", function (e) {
        if (isOpen && !toggle.contains(e.target) && !items.contains(e.target)) {
          isOpen = false;
          saveOpen(false);
          applyOpen(false, items, toggle);
        }
      }, { passive: true });

      /* 큐에 쌓인 버튼들 처리 */
      if (window.SWEFM && Array.isArray(window.SWEFM._btnQueue)) {
        window.SWEFM._btnQueue.forEach(function (cfg) {
          addButtonEl(items, cfg);
        });
        window.SWEFM._btnQueue = [];
      }

      /* 이후 호출을 위한 실제 등록 함수 교체 */
      if (window.SWEFM) {
        window.SWEFM._launcherItems = items;
        window.SWEFM.registerButton = function (cfg) {
          try { addButtonEl(items, cfg); } catch (e) { console.warn("[swefm/launcher] registerButton 실패", e); }
        };
      }

      console.log("[swefm/launcher] 런처 초기화 완료");
    } catch (e) {
      console.warn("[swefm/launcher] buildLauncher 실패", e);
    }
  }

  function applyOpen(open, items, toggle) {
    if (open) {
      items.style.opacity = "1";
      items.style.pointerEvents = "auto";
      toggle.textContent = "✕";
      toggle.style.background = "rgba(40,20,60,0.92)";
    } else {
      items.style.opacity = "0";
      items.style.pointerEvents = "none";
      toggle.textContent = "☰";
      toggle.style.background = "rgba(20,20,40,0.88)";
    }
  }

  /* 개별 버튼 DOM 생성 */
  function addButtonEl(container, cfg) {
    try {
      if (!cfg || !cfg.label) return;
      /* 중복 체크 */
      if (cfg.id && container.querySelector("#" + cfg.id)) return;

      const btn = document.createElement("button");
      if (cfg.id) btn.id = cfg.id;
      btn.title = cfg.label;
      btn.textContent = (cfg.icon || "") + " " + cfg.label;
      btn.style.cssText = [
        "background:rgba(20,20,40,0.88)",
        "color:#fff",
        "border:none",
        "border-radius:20px",
        "padding:8px 14px",
        "font-size:13px",
        "cursor:pointer",
        "white-space:nowrap",
        "box-shadow:0 2px 8px rgba(0,0,0,.4)",
        "touch-action:manipulation",
        "min-height:36px"
      ].join(";");

      if (typeof cfg.onClick === "function") {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          try { cfg.onClick(e); } catch (err) { console.warn("[swefm/launcher] onClick 실패", err); }
        }, { passive: true });
      }

      container.appendChild(btn);
    } catch (e) {
      console.warn("[swefm/launcher] addButtonEl 실패", e);
    }
  }

  /* ── 초기화 ── */
  function init() {
    try {
      /* DOMContentLoaded 보장 */
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", buildLauncher);
      } else {
        buildLauncher();
      }
    } catch (e) {
      console.warn("[swefm/launcher] init 실패", e);
    }
  }

  init();
})();
