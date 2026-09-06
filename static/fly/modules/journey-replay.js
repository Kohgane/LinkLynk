/* journey-replay.js — 내 여정 자동 투어
 * 목적: localStorage("swef_visits") 방문 기록을 시간순으로 연결/순회
 * 규칙: 읽기 전용 파싱, 실패 시 console.warn 후 안전 종료
 */
(function () {
  "use strict";

  var MODULE = "[swefm/journey]";
  var STORAGE_KEY = "swef_visits";
  var ROUTE_ALT_M = 800;
  var HOLD_MS = 1500;

  var state = {
    viewer: null,
    routeEntity: null,
    routeVisible: false,
    touring: false,
    stepTimer: null,
    runToken: 0,
    abortBound: false,
    initialized: false,
    launcherRegistered: false
  };

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function showStatus(msg) {
    try {
      var id = "swefm-journey-toast";
      var el = document.getElementById(id);
      if (!el) {
        el = document.createElement("div");
        el.id = id;
        el.style.cssText = "position:fixed;bottom:70px;left:12px;z-index:99999;" +
          "background:rgba(0,0,0,.78);color:#fff;border-radius:6px;padding:8px 12px;" +
          "font-size:12px;line-height:1.4;pointer-events:none;opacity:0;transition:opacity .25s;";
        document.body.appendChild(el);
      }
      el.textContent = msg;
      el.style.opacity = "1";
      clearTimeout(el._hideTimer);
      el._hideTimer = setTimeout(function () { el.style.opacity = "0"; }, 1800);
    } catch (e) {
      console.warn(MODULE, msg);
    }
  }

  function normalizeVisit(raw) {
    if (!raw || typeof raw !== "object") return null;

    var lat = Number(raw.la);
    var lon = Number(raw.lo);
    if (!isFinite(lat) || !isFinite(lon)) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;

    var tsNum = Number(raw.ts);
    if (!isFinite(tsNum)) {
      var parsed = Date.parse(raw.ts);
      tsNum = isFinite(parsed) ? parsed : NaN;
    }
    if (!isFinite(tsNum)) return null;

    return { la: lat, lo: lon, ts: tsNum };
  }

  function readVisits() {
    var arr;
    try {
      arr = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch (e) {
      console.warn(MODULE, "swef_visits 파싱 실패", e);
      return [];
    }

    if (!Array.isArray(arr)) {
      console.warn(MODULE, "swef_visits 형식 오류(Array 아님)");
      return [];
    }

    return arr
      .map(normalizeVisit)
      .filter(function (p) { return !!p; })
      .sort(function (a, b) { return a.ts - b.ts; });
  }

  function ensureRouteEntity(points) {
    if (!state.viewer || !window.Cesium) return;
    if (!points || points.length < 2) {
      if (state.routeEntity) state.routeEntity.show = false;
      return;
    }

    var positions = points.map(function (p) {
      return Cesium.Cartesian3.fromDegrees(p.lo, p.la, ROUTE_ALT_M);
    });

    if (!state.routeEntity) {
      state.routeEntity = state.viewer.entities.add({
        polyline: {
          positions: positions,
          width: 2,
          material: Cesium.Color.CYAN.withAlpha(0.45),
          clampToGround: false
        },
        show: state.routeVisible
      });
      return;
    }

    state.routeEntity.polyline.positions = positions;
    state.routeEntity.show = state.routeVisible;
  }

  function toggleRoute(points) {
    state.routeVisible = !state.routeVisible;
    ensureRouteEntity(points);
    if (state.routeEntity) {
      state.routeEntity.show = state.routeVisible && points.length >= 2;
    }
  }

  function clearStepTimer() {
    if (!state.stepTimer) return;
    clearTimeout(state.stepTimer);
    state.stepTimer = null;
  }

  function onUserAbort() {
    if (!state.touring) return;
    stopTour(true);
  }

  function addAbortListeners() {
    if (state.abortBound) return;
    window.addEventListener("pointerdown", onUserAbort, true);
    window.addEventListener("mousedown", onUserAbort, true);
    window.addEventListener("touchstart", onUserAbort, true);
    state.abortBound = true;
  }

  function removeAbortListeners() {
    if (!state.abortBound) return;
    window.removeEventListener("pointerdown", onUserAbort, true);
    window.removeEventListener("mousedown", onUserAbort, true);
    window.removeEventListener("touchstart", onUserAbort, true);
    state.abortBound = false;
  }

  function distanceMeters(a, b) {
    if (!window.Cesium) return 0;
    var p0 = Cesium.Cartesian3.fromDegrees(a.lo, a.la, ROUTE_ALT_M);
    var p1 = Cesium.Cartesian3.fromDegrees(b.lo, b.la, ROUTE_ALT_M);
    return Cesium.Cartesian3.distance(p0, p1);
  }

  function distanceFromCameraMeters(p) {
    try {
      if (!state.viewer || !state.viewer.camera || !state.viewer.camera.position || !window.Cesium) return 0;
      var dst = Cesium.Cartesian3.fromDegrees(p.lo, p.la, ROUTE_ALT_M);
      return Cesium.Cartesian3.distance(state.viewer.camera.position, dst);
    } catch (e) {
      return 0;
    }
  }

  function segmentDurationSec(points, idx) {
    var dist = idx <= 0 ? distanceFromCameraMeters(points[0]) : distanceMeters(points[idx - 1], points[idx]);
    var sec = dist / 120000;
    return clamp(sec, 3, 8);
  }

  function stopTour(byUser) {
    state.runToken += 1;
    clearStepTimer();
    removeAbortListeners();

    if (state.touring && state.viewer && state.viewer.camera && typeof state.viewer.camera.cancelFlight === "function") {
      try { state.viewer.camera.cancelFlight(); } catch (e) { console.warn(MODULE, "cancelFlight 실패", e); }
    }

    state.touring = false;
    if (byUser) showStatus("여정 투어를 중단했어요.");
  }

  function runTourStep(points, idx, token) {
    if (!state.touring || token !== state.runToken) return;
    if (!state.viewer || !state.viewer.camera || !window.Cesium) {
      stopTour(false);
      return;
    }
    if (idx >= points.length) {
      stopTour(false);
      showStatus("여정 투어가 끝났어요.");
      return;
    }

    var point = points[idx];
    var duration = segmentDurationSec(points, idx);

    try {
      state.viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(point.lo, point.la, ROUTE_ALT_M),
        duration: duration,
        complete: function () {
          if (!state.touring || token !== state.runToken) return;
          clearStepTimer();
          state.stepTimer = setTimeout(function () {
            runTourStep(points, idx + 1, token);
          }, HOLD_MS);
        },
        cancel: function () {
          if (state.touring && token === state.runToken) {
            stopTour(false);
          }
        }
      });
    } catch (e) {
      console.warn(MODULE, "flyTo 실패", e);
      stopTour(false);
    }
  }

  function startTour(points) {
    if (!points || points.length < 2) {
      showStatus("방문 기록이 부족해요. 2개 이상 필요해요.");
      console.warn(MODULE, "유효 방문점 부족");
      return;
    }

    stopTour(false);
    state.touring = true;
    state.runToken += 1;
    addAbortListeners();
    runTourStep(points, 0, state.runToken);
  }

  function onLauncherClick() {
    try {
      if (!state.viewer || !window.Cesium) {
        showStatus("뷰어가 아직 준비되지 않았어요.");
        return;
      }

      if (state.touring) {
        stopTour(true);
        return;
      }

      var points = readVisits();
      if (points.length < 2) {
        showStatus("방문 기록이 없거나 부족해요.");
        console.warn(MODULE, "방문 기록 없음/부족");
        if (state.routeEntity) state.routeEntity.show = false;
        state.routeVisible = false;
        return;
      }

      toggleRoute(points);
      startTour(points);
    } catch (e) {
      console.warn(MODULE, "버튼 클릭 처리 실패", e);
    }
  }

  function registerLauncher() {
    if (state.launcherRegistered) return;
    if (window.SWEFM && typeof window.SWEFM.registerButton === "function") {
      window.SWEFM.registerButton({
        id: "swefm-journey",
        icon: "🧵",
        label: "여정 리플레이",
        onClick: onLauncherClick
      });
      state.launcherRegistered = true;
    } else {
      console.warn(MODULE, "SWEFM.registerButton 없음 — 런처 등록 건너뜀");
    }
  }

  function cleanup() {
    stopTour(false);
    if (state.routeEntity && state.viewer && state.viewer.entities) {
      try {
        state.viewer.entities.remove(state.routeEntity);
      } catch (e) {
        console.warn(MODULE, "route entity 제거 실패", e);
      }
    }
    state.routeEntity = null;
  }

  function initWithViewer(viewer) {
    if (!viewer || !window.Cesium) {
      console.warn(MODULE, "viewer 또는 Cesium 없음");
      return;
    }
    state.viewer = viewer;
    if (!state.initialized) {
      window.addEventListener("pagehide", cleanup);
      window.addEventListener("beforeunload", cleanup);
      document.addEventListener("visibilitychange", function () {
        if (document.hidden) stopTour(false);
      });
      state.initialized = true;
    }
  }

  function init() {
    registerLauncher();

    try {
      if (window.SWEFM && typeof window.SWEFM.waitViewer === "function") {
        window.SWEFM.waitViewer(function (viewer) {
          initWithViewer(viewer);
        });
      }
    } catch (e) {
      console.warn(MODULE, "SWEFM.waitViewer 실패", e);
    }

    window.addEventListener("swef:ready", function () {
      try {
        var viewer = (window.SWEF && window.SWEF.viewer) || window.viewer;
        initWithViewer(viewer);
      } catch (e) {
        console.warn(MODULE, "swef:ready 처리 실패", e);
      }
    });
  }

  try {
    init();
  } catch (e) {
    console.warn(MODULE, "초기화 실패", e);
  }
})();
