/* compare.js — 시간대별 화면 4컷 비교 캡처 */
(function () {
  "use strict";

  var WAIT_MS = 1500;
  var CAPTURES = [
    { label: "06:00", value: 6 },
    { label: "12:00", value: 12 },
    { label: "18:00", value: 18 },
    { label: "00:00", value: 0 }
  ];

  var running = false;
  var cancelRequested = false;

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function showToast(msg) {
    try {
      if (window.SWEF && typeof window.SWEF.toast === "function") {
        window.SWEF.toast(msg);
      }
    } catch (e) {
      console.warn("[swefm/compare] toast 실패", e);
    }
  }

  function setSliderValue(slider, value) {
    slider.value = String(value);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function buildPanel() {
    var panel = document.createElement("div");
    panel.id = "swefm-compare-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "시간 비교 캡처");
    panel.style.cssText = [
      "display:none",
      "position:fixed",
      "top:50%",
      "left:12px",
      "transform:translateY(-50%)",
      "z-index:9000",
      "background:rgba(15,15,25,.92)",
      "color:#eee",
      "border-radius:10px",
      "padding:10px",
      "font-size:13px",
      "box-shadow:0 4px 20px rgba(0,0,0,.6)",
      "min-width:220px"
    ].join(";");
    panel.innerHTML = [
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">',
      "<b>시간 비교 캡처</b>",
      '<button id="swefm-compare-close" type="button" aria-label="닫기" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#aaa;font-size:16px;cursor:pointer;padding:0;min-width:44px;min-height:44px">✕</button>',
      "</div>",
      '<div id="swefm-compare-status" style="margin-top:8px;color:#9fd">대기 중</div>',
      '<div style="display:flex;gap:6px;margin-top:10px">',
      '<button id="swefm-compare-start" type="button" aria-label="캡처 시작" style="background:#2a6;color:#fff;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;min-height:44px">시작</button>',
      '<button id="swefm-compare-cancel" type="button" aria-label="캡처 중단" style="background:#933;color:#fff;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;min-height:44px" disabled>중단</button>',
      "</div>"
    ].join("");
    document.body.appendChild(panel);
    return panel;
  }

  function composeAndDownload(items) {
    if (!items || items.length !== 4) {
      throw new Error("캡처 이미지 수가 4장이 아닙니다.");
    }
    var w = items[0].img.width;
    var h = items[0].img.height;
    var canvas = document.createElement("canvas");
    canvas.width = w * 2;
    canvas.height = h * 2;
    var ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas context를 생성할 수 없습니다.");

    items.forEach(function (it, idx) {
      var x = (idx % 2) * w;
      var y = Math.floor(idx / 2) * h;
      ctx.drawImage(it.img, x, y, w, h);
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(x + 10, y + 10, 76, 28);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 18px sans-serif";
      ctx.fillText(it.label, x + 18, y + 30);
    });

    var stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
    var link = document.createElement("a");
    link.href = canvas.toDataURL("image/jpeg", 0.9);
    link.download = "swef_compare_" + stamp + ".jpg";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function dataUrlToImage(url) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = reject;
      img.src = url;
    });
  }

  async function runCapture(slider, statusEl, startBtn, cancelBtn) {
    var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
    if (!viewer || !viewer.scene || !viewer.canvas) {
      console.warn("[swefm/compare] viewer를 찾을 수 없습니다.");
      statusEl.textContent = "viewer 없음";
      showToast("비교 캡처 실패(viewer 없음)");
      return;
    }

    var originalTime = slider.value;
    running = true;
    cancelRequested = false;
    startBtn.disabled = true;
    cancelBtn.disabled = false;
    var shots = [];

    try {
      for (var i = 0; i < CAPTURES.length; i++) {
        if (cancelRequested) throw new Error("사용자 중단");
        var item = CAPTURES[i];
        setSliderValue(slider, item.value);
        statusEl.textContent = (i + 1) + "/4 캡처 중 (" + item.label + ")";
        await sleep(WAIT_MS);
        if (cancelRequested) throw new Error("사용자 중단");
        viewer.scene.render();
        var url = viewer.canvas.toDataURL("image/jpeg", 0.9);
        var img = await dataUrlToImage(url);
        shots.push({ label: item.label, img: img });
      }
      composeAndDownload(shots);
      statusEl.textContent = "완료";
    } catch (e) {
      console.warn("[swefm/compare] 캡처 실패", e);
      statusEl.textContent = cancelRequested ? "중단됨" : "오류 발생";
      showToast(cancelRequested ? "비교 캡처 중단" : "비교 캡처 오류");
    } finally {
      try {
        setSliderValue(slider, originalTime);
      } catch (e2) {
        console.warn("[swefm/compare] 시각 복원 실패", e2);
      }
      running = false;
      cancelRequested = false;
      startBtn.disabled = false;
      cancelBtn.disabled = true;
    }
  }

  function init() {
    try {
      var slider = document.getElementById("timeSlider");
      if (!slider) return;

      var panel = document.getElementById("swefm-compare-panel") || buildPanel();
      var statusEl = panel.querySelector("#swefm-compare-status");
      var startBtn = panel.querySelector("#swefm-compare-start");
      var cancelBtn = panel.querySelector("#swefm-compare-cancel");
      var closeBtn = panel.querySelector("#swefm-compare-close");

      startBtn.onclick = function () {
        if (running) return;
        runCapture(slider, statusEl, startBtn, cancelBtn);
      };
      cancelBtn.onclick = function () {
        cancelRequested = true;
        statusEl.textContent = "중단 요청 중...";
      };
      closeBtn.onclick = function () {
        if (!running) panel.style.display = "none";
      };

      if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
        window.SWEFM.registerButton({
          id: "swefm-compare",
          icon: "🕐",
          label: "시간비교",
          onClick: function () {
            panel.style.display = panel.style.display === "none" ? "block" : "none";
          }
        });
      } else {
        console.warn("[swefm/compare] registerButton 없음");
      }
    } catch (e) {
      console.warn("[swefm/compare] 초기화 실패", e);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
