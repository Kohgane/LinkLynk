/* share.js — 현재 장면 공유 링크 생성 */
(function () {
  "use strict";

  var KEY_LINKS = "swefm_links";
  var MAX_LINKS = 5;

  function safeLoadLinks() {
    try {
      var arr = JSON.parse(localStorage.getItem(KEY_LINKS));
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      console.warn("[swefm/share] load 실패", e);
      return [];
    }
  }

  function safeSaveLinks(list) {
    try {
      localStorage.setItem(KEY_LINKS, JSON.stringify(list));
    } catch (e) {
      console.warn("[swefm/share] save 실패", e);
    }
  }

  function toDegrees(rad) {
    try {
      if (window.Cesium && window.Cesium.Math && typeof window.Cesium.Math.toDegrees === "function") {
        return window.Cesium.Math.toDegrees(rad);
      }
    } catch (e) {
      console.warn("[swefm/share] toDegrees 실패", e);
    }
    return rad * (180 / Math.PI);
  }

  function roundNumber(n, digits) {
    if (!Number.isFinite(n)) return 0;
    return Number(n.toFixed(digits));
  }

  function getCameraData() {
    try {
      var viewer = window.SWEF && window.SWEF.viewer;
      if (!viewer || !viewer.camera || !viewer.camera.positionCartographic) return null;
      var camera = viewer.camera;
      var c = camera.positionCartographic;
      var lat = roundNumber(toDegrees(c.latitude), 5);
      var lon = roundNumber(toDegrees(c.longitude), 5);
      var h = Math.round(Number(c.height) || 0);
      var hd = roundNumber(Number(camera.heading) || 0, 3);
      var pt = roundNumber(Number(camera.pitch) || 0, 3);
      var tRaw = document.getElementById("timeSlider") && document.getElementById("timeSlider").value;
      var tNum = Number.parseFloat(tRaw);
      var t = Number.isFinite(tNum) ? Math.max(0, Math.min(24, tNum)) : 12;
      return { lat: lat, lon: lon, h: h, hd: hd, pt: pt, t: roundNumber(t, 3) };
    } catch (e) {
      console.warn("[swefm/share] 카메라 정보 추출 실패", e);
      return null;
    }
  }

  function makeDeepLink(data) {
    var base = window.location.origin + "/fly/";
    var params = new URLSearchParams({
      lon: data.lon.toFixed(5),
      lat: data.lat.toFixed(5),
      h: String(data.h),
      hd: data.hd.toFixed(3),
      pt: data.pt.toFixed(3),
      t: data.t.toFixed(3)
    });
    return base + "?" + params.toString();
  }

  function copyText(text) {
    if (!text) return Promise.resolve(false);
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function (e) {
          console.warn("[swefm/share] clipboard 실패", e);
          return fallbackCopy(text);
        });
      }
    } catch (e) {
      console.warn("[swefm/share] clipboard 접근 실패", e);
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function fallbackCopy(text) {
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "readonly");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return !!ok;
    } catch (e) {
      console.warn("[swefm/share] fallback copy 실패", e);
      return false;
    }
  }

  function addRecent(url, label) {
    var list = safeLoadLinks().filter(function (item) { return item && item.url && item.url !== url; });
    list.unshift({ url: url, label: label, ts: Date.now() });
    if (list.length > MAX_LINKS) list = list.slice(0, MAX_LINKS);
    safeSaveLinks(list);
    return list;
  }

  function removeRecent(url) {
    var list = safeLoadLinks().filter(function (item) { return item && item.url && item.url !== url; });
    safeSaveLinks(list);
    return list;
  }

  function buildUI() {
    try {
      if (document.getElementById("swefm-share-panel")) return;

      var panel = document.createElement("div");
      panel.id = "swefm-share-panel";
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-label", "공유 링크");
      panel.style.cssText = [
        "display:none",
        "position:fixed",
        "top:50%",
        "left:12px",
        "transform:translateY(-50%)",
        "z-index:9000",
        "width:320px",
        "max-height:65vh",
        "overflow-y:auto",
        "background:rgba(15,15,25,.92)",
        "color:#eee",
        "border-radius:10px",
        "padding:10px",
        "font-size:13px",
        "box-shadow:0 4px 20px rgba(0,0,0,.6)"
      ].join(";");
      document.body.appendChild(panel);

      function renderRecent() {
        var recent = safeLoadLinks();
        var listEl = document.getElementById("swefm-share-recent");
        if (!listEl) return;
        if (!recent.length) {
          listEl.innerHTML = '<div style="color:#bbb">최근 링크 없음</div>';
          return;
        }
        listEl.innerHTML = recent.map(function (item) {
          var safeUrl = String(item.url || "").replace(/"/g, "&quot;");
          var safeLabel = String(item.label || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
          return '<div style="display:flex;gap:4px;align-items:center;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.07)">' +
            '<button class="swefm-share-copy-recent" type="button" aria-label="최근 링크 복사" data-url="' + safeUrl + '" style="flex:1;text-align:left;background:none;border:none;color:#ddd;cursor:pointer;font-size:12px;padding:8px 0;min-height:44px">' + safeLabel + "</button>" +
            '<button class="swefm-share-del-recent" type="button" aria-label="최근 링크 삭제" data-url="' + safeUrl + '" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#f66;cursor:pointer;padding:0;min-width:44px;min-height:44px">✕</button>' +
            "</div>";
        }).join("");
        listEl.querySelectorAll(".swefm-share-copy-recent").forEach(function (btn) {
          btn.onclick = function () { copyText(btn.dataset.url || ""); };
        });
        listEl.querySelectorAll(".swefm-share-del-recent").forEach(function (btn) {
          btn.onclick = function () {
            removeRecent(btn.dataset.url || "");
            renderRecent();
          };
        });
      }

      function refreshLink() {
        var data = getCameraData();
        if (!data) return null;
        var url = makeDeepLink(data);
        var label = data.lat.toFixed(5) + "," + data.lon.toFixed(5) + " @" + data.h + "m";
        addRecent(url, label);
        var input = document.getElementById("swefm-share-link");
        if (input) input.value = url;
        renderRecent();
        return url;
      }

      panel.innerHTML = [
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">',
        "<b>공유 링크</b>",
        '<button id="swefm-share-close" type="button" aria-label="닫기" style="display:inline-flex;align-items:center;justify-content:center;background:none;border:none;color:#aaa;font-size:16px;cursor:pointer;padding:0;min-width:44px;min-height:44px">✕</button>',
        "</div>",
        '<input id="swefm-share-link" type="text" readonly style="width:100%;box-sizing:border-box;border:1px solid #444;border-radius:6px;background:#111;color:#eee;padding:8px;font-size:12px">',
        '<div style="display:flex;gap:6px;margin-top:8px">',
        '<button id="swefm-share-copy" type="button" aria-label="링크 복사" style="background:#2a6;color:#fff;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;min-height:44px">복사</button>',
        '<button id="swefm-share-share" type="button" aria-label="링크 공유" style="display:none;background:#246;color:#fff;border:none;border-radius:6px;padding:8px 12px;cursor:pointer;min-height:44px">공유</button>',
        "</div>",
        '<div style="font-weight:600;margin:10px 0 4px;color:#88BBFF">최근 링크</div>',
        '<div id="swefm-share-recent"></div>'
      ].join("");

      var inputEl = panel.querySelector("#swefm-share-link");
      var closeEl = panel.querySelector("#swefm-share-close");
      var copyEl = panel.querySelector("#swefm-share-copy");
      var shareEl = panel.querySelector("#swefm-share-share");

      inputEl.onclick = function () { inputEl.select(); };
      inputEl.onfocus = function () { inputEl.select(); };
      closeEl.onclick = function () { panel.style.display = "none"; };
      copyEl.onclick = function () { copyText(inputEl.value || ""); };

      if (navigator.share && typeof navigator.share === "function") {
        shareEl.style.display = "inline-block";
        shareEl.onclick = function () {
          try {
            navigator.share({ title: "LinkLynk 공유 링크", url: inputEl.value || "" }).catch(function (e) {
              console.warn("[swefm/share] share 실패", e);
            });
          } catch (e) {
            console.warn("[swefm/share] share 호출 실패", e);
          }
        };
      }

      if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
        window.SWEFM.registerButton({
          id: "swefm-share",
          icon: "🔗",
          label: "공유",
          onClick: function () {
            if (panel.style.display === "none") {
              panel.style.display = "block";
              refreshLink();
            } else {
              panel.style.display = "none";
            }
          }
        });
      } else {
        console.warn("[swefm/share] registerButton 없음");
      }

      renderRecent();
    } catch (e) {
      console.warn("[swefm/share] UI 생성 실패", e);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildUI);
  } else {
    buildUI();
  }
})();
