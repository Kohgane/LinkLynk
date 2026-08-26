/* SWEFM Settings Module — 모듈 설정 패널
 * 규칙: IIFE, swefm- DOM 접두, swefm_ 저장키, ef_ 키 접근 금지, 외부 라이브러리·네트워크 금지
 */
(function () {
  "use strict";

  var PANEL_ID = "swefm-settings-panel";
  var TOAST_ID = "swefm-settings-toast";
  var DISABLED_KEY = "swefm_disabled";

  /* ── 비활성화 목록 헬퍼 ─────────────────────────────────────────── */
  function getDisabled() {
    try {
      return JSON.parse(localStorage.getItem(DISABLED_KEY) || "[]");
    } catch (e) {
      return [];
    }
  }
  function setDisabled(arr) {
    localStorage.setItem(DISABLED_KEY, JSON.stringify(arr));
  }
  function isDisabled(mod) {
    return getDisabled().indexOf(mod) !== -1;
  }

  /* ── 토스트 ─────────────────────────────────────────────────────── */
  function showToast(msg, duration) {
    try {
      var el = document.getElementById(TOAST_ID);
      if (!el) {
        el = document.createElement("div");
        el.id = TOAST_ID;
        el.style.cssText =
          "position:fixed;bottom:70px;left:12px;background:#333;color:#fff;" +
          "padding:8px 14px;border-radius:6px;font-size:13px;z-index:99999;" +
          "pointer-events:none;transition:opacity .3s;opacity:0;max-width:260px;";
        document.body.appendChild(el);
      }
      el.textContent = msg;
      el.style.opacity = "1";
      clearTimeout(el._t);
      el._t = setTimeout(function () {
        el.style.opacity = "0";
      }, duration || 3000);
    } catch (e) {
      console.warn("[swefm-settings] toast error", e);
    }
  }

  /* ── swefm_* 키 목록 ──────────────────────────────────────────── */
  function getSwefmKeys() {
    var keys = [];
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (k && k.indexOf("swefm_") === 0) keys.push(k);
    }
    return keys;
  }

  /* ── 패널 HTML 빌더 ──────────────────────────────────────────── */
  function buildPanel() {
    var el = document.getElementById(PANEL_ID);
    if (!el) {
      el = document.createElement("div");
      el.id = PANEL_ID;
      el.setAttribute("role", "dialog");
      el.setAttribute("aria-label", "모듈 설정");
      el.style.cssText =
        "display:none;position:fixed;top:60px;left:12px;width:320px;" +
        "background:#1a1a2e;color:#eee;border:1px solid #444;border-radius:10px;" +
        "padding:14px;z-index:99998;font-size:13px;max-height:80vh;overflow-y:auto;" +
        "box-shadow:0 4px 20px rgba(0,0,0,.6);";
      document.body.appendChild(el);
    }
    el.innerHTML = "";

    /* 제목 */
    var title = document.createElement("h3");
    title.textContent = "⚙ 모듈 설정";
    title.style.cssText = "margin:0 0 10px;font-size:15px;color:#7ec8e3;";
    el.appendChild(title);

    /* 닫기 버튼 */
    var closeBtn = document.createElement("button");
    closeBtn.id = "swefm-settings-close";
    closeBtn.type = "button";
    closeBtn.textContent = "✕";
    closeBtn.setAttribute("aria-label", "닫기");
    closeBtn.style.cssText =
      "position:absolute;top:10px;right:10px;display:inline-flex;align-items:center;justify-content:center;background:none;border:none;" +
      "color:#aaa;font-size:16px;cursor:pointer;padding:0;min-width:44px;min-height:44px;";
    closeBtn.onclick = function () { togglePanel(false); };
    el.appendChild(closeBtn);

    el.appendChild(buildSection1());
    el.appendChild(buildSection2());
    el.appendChild(buildSection3());
    el.appendChild(buildSection4());
  }

  /* ── 섹션 1: 모듈 on/off ────────────────────────────────────── */
  function buildSection1() {
    var wrap = document.createElement("div");
    wrap.id = "swefm-settings-s1";

    var h = document.createElement("h4");
    h.textContent = "모듈 활성/비활성";
    h.style.cssText = "margin:12px 0 6px;color:#aad;font-size:13px;";
    wrap.appendChild(h);

    var allMods = [];
    try {
      /* launcher.js에 등록된 버튼 목록에서 모듈명 유추 */
      var scripts = document.querySelectorAll("script[src*='modules/']");
      scripts.forEach(function (s) {
        var m = s.src.match(/modules\/([^/?#]+\.js)/);
        if (m && m[1]) allMods.push(m[1]);
      });
    } catch (e) { /* 무시 */ }

    /* MODULES 배열을 launcher에서 노출하지 않으면 알려진 목록을 하드코딩 */
    var known = ["launcher.js", "favorites.js", "replay.js", "hud.js", "share.js", "compare.js", "settings.js"];
    known.forEach(function (m) {
      if (allMods.indexOf(m) === -1) allMods.push(m);
    });

    allMods.forEach(function (mod) {
      var isSelf = (mod === "settings.js");
      var row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:4px 0;border-bottom:1px solid #333;";

      var label = document.createElement("span");
      label.textContent = mod + (isSelf ? " (이 모듈)" : "");
      label.style.cssText = "flex:1;";

      var toggle = document.createElement("button");
      toggle.id = "swefm-toggle-" + mod.replace(/\./g, "-");
      toggle.type = "button";
      var dis = isDisabled(mod);
      toggle.textContent = dis ? "꺼짐" : "켜짐";
      toggle.setAttribute("aria-label", mod + " " + (dis ? "비활성화됨" : "활성화됨"));
      toggle.style.cssText =
        "width:54px;border:none;border-radius:4px;cursor:" + (isSelf ? "not-allowed" : "pointer") +
        ";padding:8px 6px;font-size:12px;background:" + (dis ? "#555" : "#2a7") + ";color:#fff;min-height:44px;";

      if (isSelf) {
        toggle.disabled = true;
        toggle.title = "설정 모듈은 비활성화할 수 없습니다.";
      } else {
        toggle.onclick = (function (m, btn) {
          return function () {
            var list = getDisabled();
            var idx = list.indexOf(m);
            if (idx === -1) {
              /* 끄기 */
              list.push(m);
              setDisabled(list);
              btn.textContent = "꺼짐";
              btn.setAttribute("aria-label", m + " 비활성화됨");
              btn.style.background = "#555";
              /* 런처 버튼 숨기기 */
              try {
                var modId = m.replace(/\.js$/, "");
                var btnEl = document.getElementById("swefm-" + modId + "-btn") ||
                  document.querySelector("[id^='swefm-'][id*='" + modId + "']");
                if (btnEl) btnEl.style.display = "none";
              } catch (e2) {
                console.warn("[swefm-settings] 런처 버튼 숨기기 실패", e2);
              }
              showToast("'" + m + "' 비활성화됨. 다음 로드부터 제외됩니다.");
            } else {
              /* 켜기 */
              list.splice(idx, 1);
              setDisabled(list);
              btn.textContent = "켜짐";
              btn.setAttribute("aria-label", m + " 활성화됨");
              btn.style.background = "#2a7";
              showToast("'" + m + "' 활성화됨. 새로고침 후 적용됩니다.", 4000);
            }
          };
        })(mod, toggle);
      }

      row.appendChild(label);
      row.appendChild(toggle);
      wrap.appendChild(row);
    });

    return wrap;
  }

  /* ── 섹션 2: 저장 데이터 관리 ──────────────────────────────── */
  function buildSection2() {
    var wrap = document.createElement("div");
    wrap.id = "swefm-settings-s2";

    var h = document.createElement("h4");
    h.textContent = "저장 데이터 관리 (swefm_*)";
    h.style.cssText = "margin:14px 0 6px;color:#aad;font-size:13px;";
    wrap.appendChild(h);

    function renderKeys() {
      var list = wrap.querySelector("#swefm-key-list");
      if (!list) {
        list = document.createElement("div");
        list.id = "swefm-key-list";
        wrap.appendChild(list);
      }
      list.innerHTML = "";
      var keys = getSwefmKeys();
      if (keys.length === 0) {
        var empty = document.createElement("p");
        empty.textContent = "(저장된 swefm_* 키 없음)";
        empty.style.cssText = "color:#bbb;font-size:12px;";
        list.appendChild(empty);
      }
      keys.forEach(function (k) {
        var val = "";
        try { val = localStorage.getItem(k) || ""; } catch (e) { /* 무시 */ }
        var row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid #2a2a3e;";
        var info = document.createElement("span");
        info.style.cssText = "flex:1;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
        info.title = k;
        info.textContent = k + " (" + val.length + "자)";
        var del = document.createElement("button");
        del.type = "button";
        del.textContent = "삭제";
        del.setAttribute("aria-label", k + " 삭제");
        del.style.cssText = "background:#933;border:none;color:#fff;border-radius:4px;cursor:pointer;padding:8px 8px;font-size:11px;min-height:44px;";
        del.onclick = (function (key) {
          return function () {
            localStorage.removeItem(key);
            renderKeys();
            showToast("'" + key + "' 삭제됨.");
          };
        })(k);
        row.appendChild(info);
        row.appendChild(del);
        list.appendChild(row);
      });
    }

    renderKeys();

    /* 전체 초기화 */
    var resetBtn = document.createElement("button");
    resetBtn.id = "swefm-settings-reset";
    resetBtn.type = "button";
    resetBtn.textContent = "전체 초기화";
    resetBtn.setAttribute("aria-label", "모든 모듈 저장 데이터 초기화");
    resetBtn.style.cssText =
      "margin-top:8px;background:#933;border:none;color:#fff;border-radius:5px;" +
      "cursor:pointer;padding:8px 10px;font-size:12px;min-height:44px;";
    resetBtn.onclick = function () {
      if (!confirm("모든 swefm_* 저장 데이터를 삭제합니다. 계속하시겠습니까?")) return;
      var keys = getSwefmKeys();
      keys.forEach(function (k) { localStorage.removeItem(k); });
      renderKeys();
      showToast("전체 초기화 완료.");
    };
    wrap.appendChild(resetBtn);

    return wrap;
  }

  /* ── 섹션 3: 내보내기/가져오기 ─────────────────────────────── */
  function buildSection3() {
    var wrap = document.createElement("div");
    wrap.id = "swefm-settings-s3";

    var h = document.createElement("h4");
    h.textContent = "내보내기 / 가져오기";
    h.style.cssText = "margin:14px 0 6px;color:#aad;font-size:13px;";
    wrap.appendChild(h);

    /* 내보내기 */
    var exportBtn = document.createElement("button");
    exportBtn.id = "swefm-settings-export";
    exportBtn.type = "button";
    exportBtn.textContent = "⬇ JSON 내보내기";
    exportBtn.setAttribute("aria-label", "모듈 설정 JSON 내보내기");
    exportBtn.style.cssText =
      "background:#246;border:none;color:#fff;border-radius:5px;cursor:pointer;" +
      "padding:8px 10px;font-size:12px;margin-right:6px;min-height:44px;";
    exportBtn.onclick = function () {
      try {
        var data = {};
        getSwefmKeys().forEach(function (k) {
          data[k] = localStorage.getItem(k);
        });
        var json = JSON.stringify(data, null, 2);
        var ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        var blob = new Blob([json], { type: "application/json" });
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "swefm_settings_" + ts + ".json";
        a.click();
        URL.revokeObjectURL(url);
        showToast("내보내기 완료.");
      } catch (e) {
        console.warn("[swefm-settings] export error", e);
        showToast("내보내기 실패: " + e.message);
      }
    };
    wrap.appendChild(exportBtn);

    /* 가져오기 */
    var importLabel = document.createElement("label");
    importLabel.id = "swefm-settings-import-label";
    importLabel.textContent = "⬆ JSON 가져오기";
    importLabel.setAttribute("role", "button");
    importLabel.setAttribute("tabindex", "0");
    importLabel.setAttribute("aria-label", "모듈 설정 JSON 가져오기");
    importLabel.style.cssText =
      "background:#264;border:none;color:#fff;border-radius:5px;cursor:pointer;" +
      "padding:8px 10px;font-size:12px;display:inline-flex;align-items:center;min-height:44px;";
    var importInput = document.createElement("input");
    importInput.type = "file";
    importInput.accept = ".json,application/json";
    importInput.style.display = "none";
    importInput.id = "swefm-settings-import-input";
    importLabel.onkeydown = function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        importInput.click();
      }
    };
    importInput.onchange = function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function (ev) {
        var statusEl = document.getElementById("swefm-import-status");
        try {
          var parsed = JSON.parse(ev.target.result);
          var imported = 0, skipped = 0;
          Object.keys(parsed).forEach(function (k) {
            if (k.indexOf("swefm_") !== 0) {
              console.warn("[swefm-settings] import: 비허용 키 무시됨:", k);
              skipped++;
              return;
            }
            localStorage.setItem(k, parsed[k]);
            imported++;
          });
          var msg = "가져오기 완료: " + imported + "개 복원.";
          if (skipped > 0) msg += " " + skipped + "개 키 무시됨(swefm_* 아님).";
          showToast(msg, 5000);
          if (statusEl) statusEl.textContent = msg;
          /* 키 목록 갱신 */
          buildPanel();
          togglePanel(true);
        } catch (err) {
          console.warn("[swefm-settings] import parse error", err);
          var msg2 = "JSON 파싱 오류: " + err.message;
          showToast(msg2);
          if (statusEl) statusEl.textContent = msg2;
        }
        importInput.value = "";
      };
      reader.readAsText(file);
    };
    importLabel.appendChild(importInput);
    wrap.appendChild(importLabel);

    var statusEl = document.createElement("p");
    statusEl.id = "swefm-import-status";
    statusEl.style.cssText = "font-size:11px;color:#aaa;margin:4px 0 0;min-height:14px;";
    wrap.appendChild(statusEl);

    return wrap;
  }

  /* ── 섹션 4: SWEFM.debug() 결과 ────────────────────────────── */
  function buildSection4() {
    var wrap = document.createElement("div");
    wrap.id = "swefm-settings-s4";

    var h = document.createElement("h4");
    h.textContent = "진단 정보 (SWEFM.debug)";
    h.style.cssText = "margin:14px 0 6px;color:#aad;font-size:13px;";
    wrap.appendChild(h);

    var resultEl = document.createElement("div");
    resultEl.id = "swefm-debug-result";
    resultEl.style.cssText =
      "background:#111;border-radius:5px;padding:8px;font-size:11px;" +
      "color:#ccc;max-height:180px;overflow-y:auto;";
    wrap.appendChild(resultEl);

    function runDebug() {
      resultEl.innerHTML = "";
      try {
        if (typeof window.SWEFM.debug !== "function") {
          resultEl.textContent = "SWEFM.debug 함수가 없습니다.";
          return;
        }
        /* debug()가 console.table을 사용하므로 결과를 직접 구성 */
        var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
        var info = {
          "로드된 모듈": (window.SWEFM._loadedMods || []).join(", ") || "(없음)",
          "window.SWEF": !!(window.SWEF),
          "viewer": !!(viewer),
          "swefm- DOM 수": document.querySelectorAll("[id^=swefm-]").length,
          "비활성 모듈": getDisabled().join(", ") || "(없음)"
        };
        var tbl = document.createElement("table");
        tbl.style.cssText = "border-collapse:collapse;width:100%;font-size:11px;";
        Object.keys(info).forEach(function (key) {
          var val;
          try {
            val = typeof info[key] === "object" ? JSON.stringify(info[key]) : String(info[key]);
          } catch (e) {
            val = "(직렬화 오류)";
          }
          var tr = document.createElement("tr");
          var td1 = document.createElement("td");
          td1.textContent = key;
          td1.style.cssText = "padding:2px 6px;border:1px solid #333;color:#9cf;white-space:nowrap;";
          var td2 = document.createElement("td");
          td2.textContent = val;
          td2.style.cssText = "padding:2px 6px;border:1px solid #333;word-break:break-all;";
          tr.appendChild(td1);
          tr.appendChild(td2);
          tbl.appendChild(tr);
        });
        resultEl.appendChild(tbl);
        /* 실제 debug()도 호출해서 콘솔에도 출력 */
        try { window.SWEFM.debug(); } catch (e2) { /* 무시 */ }
      } catch (e) {
        console.warn("[swefm-settings] debug error", e);
        resultEl.textContent = "오류: " + e.message;
      }
    }

    var refreshBtn = document.createElement("button");
    refreshBtn.id = "swefm-debug-refresh";
    refreshBtn.type = "button";
    refreshBtn.textContent = "↻ 새로고침";
    refreshBtn.setAttribute("aria-label", "진단 정보 새로고침");
    refreshBtn.style.cssText =
      "margin-top:6px;background:#334;border:none;color:#ccc;border-radius:4px;" +
      "cursor:pointer;padding:8px 8px;font-size:11px;min-height:44px;";
    refreshBtn.onclick = runDebug;
    wrap.appendChild(refreshBtn);

    runDebug();
    return wrap;
  }

  /* ── 패널 토글 ──────────────────────────────────────────────── */
  function togglePanel(forceOpen) {
    var el = document.getElementById(PANEL_ID);
    if (!el) {
      buildPanel();
      el = document.getElementById(PANEL_ID);
    } else {
      buildPanel(); /* 내용 갱신 */
      el = document.getElementById(PANEL_ID);
    }
    if (el) {
      var open = (forceOpen === true) ? true : (el.style.display === "none" || el.style.display === "");
      el.style.display = open ? "block" : "none";
    }
  }

  /* ── 런처 등록 ──────────────────────────────────────────────── */
  function registerLauncher() {
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-settings",
        icon: "⚙",
        label: "모듈설정",
        onClick: function () { togglePanel(); }
      });
    } else {
      console.warn("[swefm-settings] SWEFM.registerButton 없음 — 런처 등록 건너뜀");
    }
  }

  /* ── 초기화 ────────────────────────────────────────────────── */
  function init() {
    registerLauncher();
    buildPanel();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
