(function(){
  "use strict";

  const params = new URLSearchParams(location.search);
  const IS_TOUCH = ("ontouchstart" in window);
  const app = window.SWEF_V2 = window.SWEF_V2 || {};
  const state = app.state = app.state || {
    mode: "tour",
    currentTab: "explore",
    travel: null,
    governorTier: 0,
    governorToasted: false,
    frameWorst: 0,
    fpsFrames: 0,
    fpsStamp: 0,
    fpsValue: 0,
    diagText: "",
    targetSSE: 12,
    currentSSE: 12,
    warpHold: 0,
    warpStepTick: 0,
    cloudMode: 0,
    profile: null,
    postprocessSuspended: false,
    fogSuppressed: false,
    lastError: "",
    tileLoadProgress: 0,
    vehicle: null,
    speedKmh: 0,
    bootedAt: Date.now(),
    signatureReady: false,
    softRenderer: false,
    rendererName: ""
  };
  const hooks = app.hooks = app.hooks || { ready: [], frame: [], tab: [], mode: [], diag: [] };
  const D = window.SWEF_DATA || {};
  const diagEnabled = params.get("fps") === "1";
  const probeEnabled = params.get("probe") === "1";
  const bareMode = /[?&]bare=1/.test(location.search);

  Object.assign(app, { params, IS_TOUCH, bareMode, data: D, state });
  window.SWEF = window.SWEF || { viewer: null };

  function setLastErr(err){
    const text = String(err && err.message ? err.message : err || "?").slice(0, 180);
    window._lastErr = text;
    state.lastError = text;
  }

  // §9 전역 에러를 1건 유지하고 계기판에 노출한다.
  window.addEventListener("error", (event)=>{
    if (!window._lastErr) setLastErr(event.message || "window error");
  });
  window.addEventListener("unhandledrejection", (event)=>{
    if (!window._lastErr) setLastErr(event.reason || "promise rejection");
  });

  function safeRun(label, fn){
    try { return fn(); }
    catch (error) {
      setLastErr(label + ": " + (error && error.message ? error.message : error));
      console.warn("[swef-v2]", label, error);
      return null;
    }
  }

  function on(type, fn){
    (hooks[type] = hooks[type] || []).push(fn);
    return ()=>{ hooks[type] = (hooks[type] || []).filter((it)=>it !== fn); };
  }
  function emit(type, detail){
    (hooks[type] || []).forEach((fn, index)=>safeRun(type + "#" + index, ()=>fn(detail)));
  }

  function $(id){ return document.getElementById(id); }

  function toast(message, ms){
    const host = $("toastHost");
    if (!host) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = String(message);
    host.appendChild(el);
    setTimeout(()=>{ el.style.opacity = "0"; el.style.transform = "translateY(6px)"; }, Math.max(500, (ms || 2600) - 250));
    setTimeout(()=>{ el.remove(); }, Math.max(900, ms || 2600));
  }

  function setMode(nextMode){
    if (state.mode === nextMode) return;
    state.mode = nextMode;
    emit("mode", nextMode);
  }

  function setTab(nextTab){
    if (state.currentTab === nextTab) return;
    state.currentTab = nextTab;
    emit("tab", nextTab);
  }

  function getProfile(){
    return state.profile || {
      resolutionScale: IS_TOUCH ? 0.65 : 0.85,
      cacheBytes: IS_TOUCH ? 192 * 1024 * 1024 : 768 * 1024 * 1024,
      overflowBytes: IS_TOUCH ? 96 * 1024 * 1024 : 256 * 1024 * 1024,
      maxRequests: IS_TOUCH ? 6 : 12,
      globeSSE: IS_TOUCH ? 6 : 3
    };
  }

  function baseResolutionForTier(tier){
    const p = getProfile();
    const softPenalty = state.softRenderer ? Math.min(p.resolutionScale, 0.5) : p.resolutionScale;
    if (tier <= 0) return softPenalty;
    if (tier === 1) return Math.max(0.45, softPenalty - (IS_TOUCH ? 0.10 : 0.15));
    return Math.max(0.40, softPenalty - (IS_TOUCH ? 0.15 : 0.20));
  }

  function syncStageBudget(){
    state.postprocessSuspended = state.governorTier >= 1;
    state.fogSuppressed = state.governorTier >= 2;
    emit("diag", { reason: "governor" });
  }

  function applyGovernorTier(){
    if (!app.viewer) return;
    app.viewer.resolutionScale = baseResolutionForTier(state.governorTier);
    syncStageBudget();
    if (state.governorTier >= 2 && typeof app.setCloudMode === "function") app.setCloudMode(0, true);
  }

  function evaluateGovernor(){
    const acc = state.govAccum;
    if (!acc || acc.elapsed < 1500) return;
    const avg = acc.sum / Math.max(1, acc.count);
    state.govAvg = avg;
    state.govAccum = { elapsed: 0, sum: 0, count: 0 };
    // §4 벽시계 1.5초마다 평균 프레임타임을 평가해 티어를 올리고 되돌린다.
    if (avg > 26 && state.governorTier < 2) {
      state.governorTier += 1;
      if (!state.governorToasted) {
        state.governorToasted = true;
        toast("⚡ 최적화 모드", 2600);
      }
      applyGovernorTier();
    } else if (avg < 17 && state.governorTier > 0) {
      state.governorTier -= 1;
      applyGovernorTier();
    }
  }

  function detectRenderer(){
    try {
      const gl = app.viewer.canvas.getContext("webgl2") || app.viewer.canvas.getContext("webgl");
      const dbg = gl && gl.getExtension("WEBGL_debug_renderer_info");
      const name = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "") : "";
      state.rendererName = name;
      if (/swiftshader|llvmpipe/i.test(name)) {
        // §3 소프트웨어 렌더러 감지 시 해상도를 강등하고 경고 토스트를 띄운다.
        state.softRenderer = true;
        app.viewer.resolutionScale = 0.5;
        toast("⚠️ 소프트웨어 렌더러 감지 — 해상도 0.5로 강등", 4200);
      }
    } catch (error) {
      console.warn("[swef-v2] renderer detect", error);
    }
  }

  function updateTierLabel(){
    const el = $("tier");
    if (!el) return;
    const tiles = state.tileset ? "PHOTOREAL" : "BOOT";
    el.textContent = tiles + " · v2 · tier " + state.governorTier + (bareMode ? " · bare" : "");
  }

  function updateTravelCurtain(){
    const fade = $("fadeMask");
    const vignette = $("vignettePulse");
    if (!fade || !state.travel) return;
    if (state.travel.phase === "down") {
      fade.style.transition = "opacity .4s ease";
      fade.style.opacity = "0.88";
      state.travel.phase = "hold";
    } else if (state.travel.phase === "settling") {
      fade.style.opacity = "0.56";
      if (state.warpHold <= 0 && state.currentSSE <= state.targetSSE && state.tileLoadProgress <= 1) {
        state.travel.phase = "up";
        fade.style.transition = "opacity 1s ease";
        fade.style.opacity = "0";
        if (vignette) {
          vignette.style.opacity = "0.92";
          setTimeout(()=>{ vignette.style.opacity = "0"; }, 120);
        }
        setTimeout(()=>{ state.travel = null; }, 1000);
      }
    }
  }

  function beginTravel(){
    // §7 이동 시작 시 화면을 페이드 다운해 흐릿한 로딩 노출을 막는다.
    state.travel = { phase: "down" };
    const fade = $("fadeMask");
    if (fade) {
      fade.style.transition = "opacity .4s ease";
      fade.style.opacity = "0";
      requestAnimationFrame(()=>{ fade.style.opacity = "0.88"; state.travel.phase = "hold"; });
    }
  }

  function markTravelSettling(){
    if (!state.travel) return;
    state.travel.phase = "settling";
  }

  function updateWarpBudget(){
    const tileset = state.tileset;
    if (!tileset || !app.viewer) return;
    const camPos = app.viewer.camera.positionWC;
    if (!state.prevCamPos) {
      state.prevCamPos = Cesium.Cartesian3.clone(camPos, new Cesium.Cartesian3());
    }
    const moved = Cesium.Cartesian3.distance(camPos, state.prevCamPos);
    Cesium.Cartesian3.clone(camPos, state.prevCamPos);
    // §5 1프레임 1500m 이상 워프하면 타일 다이어트 모드로 진입한다.
    if (moved > 1500) state.warpHold = 30;
    else if (state.warpHold > 0) state.warpHold -= 1;
    const desired = state.warpHold > 0 ? 26 : state.targetSSE;
    if (state.currentSSE == null) state.currentSSE = desired;
    if (desired >= state.currentSSE) {
      state.currentSSE = desired;
      state.warpStepTick = 0;
    } else {
      state.warpStepTick += 1;
      if (state.warpStepTick >= 14) {
        state.warpStepTick = 0;
        state.currentSSE = Math.max(desired, state.currentSSE - 2);
      }
    }
    tileset.maximumScreenSpaceError = state.currentSSE;
    tileset.skipLevelOfDetail = state.warpHold > 0;
  }

  function updateDiag(now, dtMs){
    // §8 ?fps=1 계기판은 FPS/최악ms/처리타일/해상도/SSE/거버너티어/최근 오류를 즉시 노출한다.
    if (!diagEnabled || !app.viewer) return;
    state.fpsFrames += 1;
    state.frameWorst = Math.max(state.frameWorst || 0, dtMs);
    if (!state.fpsStamp) state.fpsStamp = now;
    if (now - state.fpsStamp < 500) return;
    state.fpsValue = Math.round(state.fpsFrames * 1000 / (now - state.fpsStamp));
    state.fpsStamp = now;
    state.fpsFrames = 0;
    const tiles = state.tileset && state.tileset._statistics ? state.tileset._statistics.numberOfTilesProcessing : 0;
    state.diagText = [
      "FPS " + state.fpsValue + " | 최악 " + Math.round(state.frameWorst || 0) + "ms",
      "타일 " + tiles + " | 해상도 " + app.viewer.resolutionScale.toFixed(2),
      "SSE " + state.currentSSE + " | 거버너 " + state.governorTier,
      window._lastErr ? ("⚠ " + window._lastErr) : "오류 없음"
    ].join("\n");
    const box = $("diag");
    if (box) {
      box.style.display = "block";
      box.textContent = state.diagText;
    }
    state.frameWorst = 0;
  }

  function runProbe(){
    // §8 ?probe=1 자동 순회는 8초 간격으로 기준/후처리/엔티티/대기/글로브/타일 단계를 비교한다.
    if (!probeEnabled || state.probeRunning || !app.viewer) return;
    state.probeRunning = true;
    const board = $("diag");
    const scene = app.viewer.scene;
    if (board) board.style.display = "block";
    const steps = [
      ["기준", ()=>{}, ()=>{}],
      ["후처리off", ()=>{ safeRun("probe-post-off", ()=>app.toggleAllPostprocess(false)); }, ()=>{ safeRun("probe-post-on", ()=>app.restoreAllPostprocess()); }],
      ["엔티티off", ()=>{ app.viewer.entities.show = false; }, ()=>{ app.viewer.entities.show = true; }],
      ["대기off", ()=>{ scene.skyAtmosphere.show = false; if (scene.sun) scene.sun.show = false; if (scene.moon) scene.moon.show = false; }, ()=>{ scene.skyAtmosphere.show = true; if (scene.sun) scene.sun.show = true; if (scene.moon) scene.moon.show = true; }],
      ["위성지구off", ()=>{ state._probeGlobe = scene.globe.show; scene.globe.show = false; }, ()=>{ scene.globe.show = state._probeGlobe; }],
      ["타일off", ()=>{ if (state.tileset) state.tileset.show = false; }, ()=>{ if (state.tileset) state.tileset.show = true; }]
    ];
    let index = -1;
    let mark = 0;
    let frames = 0;
    const results = [];
    function counter(){ if (state.probeRunning) { frames += 1; requestAnimationFrame(counter); } }
    requestAnimationFrame(counter);
    function step(){
      if (index >= 0) {
        const secs = Math.max(0.1, (performance.now() - mark) / 1000);
        results.push(steps[index][0] + ": " + Math.round(frames / secs) + " fps");
        safeRun("probe-restore", steps[index][2]);
      }
      index += 1;
      if (index >= steps.length) {
        state.probeRunning = false;
        if (board) board.textContent = "🧪 프로브 완료\n" + results.join("\n");
        return;
      }
      frames = 0;
      mark = performance.now();
      safeRun("probe-step", steps[index][1]);
      if (board) board.textContent = "🧪 프로브 " + (index + 1) + "/" + steps.length + " — " + steps[index][0] + "\n" + results.join("\n");
      setTimeout(step, 8000);
    }
    setTimeout(step, 3500);
  }

  function currentSpeed(){
    const viewer = app.viewer;
    const veh = state.vehicle || { sp: 1 };
    if (!viewer) return 0;
    const h = Math.max(viewer.camera.positionCartographic.height, 1);
    const base = Math.min(Math.max(h * 0.45, 60), 200000);
    const cap = Math.max(85, Math.min(8000, h * 0.6));
    return Math.min(base * (veh.sp || 1) * (app.keys && app.keys.shift ? 2.2 : 1), cap);
  }

  function capturePhoto(){
    if (!app.viewer) return;
    // §2 preserveDrawingBuffer 없이 scene.render() 직후 toDataURL로 저장한다.
    app.viewer.scene.render();
    const link = document.createElement("a");
    link.download = "earthflight-v2.png";
    link.href = app.viewer.canvas.toDataURL("image/png");
    link.click();
  }

  function refreshSWEFHook(){
    if (!app.viewer) return;
    Object.assign(window.SWEF, {
      viewer: app.viewer,
      DESTS: D.DESTS,
      FILMS: D.FILMS,
      toast,
      goFree: ()=>app.goFree(),
      goSpace: ()=>app.goSpace(),
      flyToDest: (index)=>app.flyToDest(index),
      setFilm: (index)=>app.setFilm && app.setFilm(index),
      get camera(){ return app.viewer.camera; },
      get isTouch(){ return IS_TOUCH; },
      get lang(){ return "ko"; },
      version: "2.0"
    });
    window.dispatchEvent(new CustomEvent("swef:ready", { detail: window.SWEF }));
  }

  function loadModuleLoader(){
    if (bareMode || document.getElementById("SWEF_MODULES")) return;
    const script = document.createElement("script");
    script.defer = true;
    script.id = "SWEF_MODULES";
    script.src = "/fly/modules/index.js";
    document.head.appendChild(script);
  }

  function flyToCartesian(destination, options){
    if (!app.viewer) return;
    beginTravel();
    state.warpHold = Math.max(state.warpHold || 0, 30);
    app.viewer.camera.flyTo(Object.assign({
      destination,
      duration: 4.8,
      complete: ()=>markTravelSettling()
    }, options || {}));
  }

  function flyToDest(index){
    const d = D.DESTS[index];
    if (!d || !app.viewer) return;
    state.currentDest = d;
    setMode("tour");
    app.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    state.orbit = {
      center: Cesium.Cartesian3.fromDegrees(d.lon, d.lat, d.h * 0.35),
      range: d.r,
      pitch: Cesium.Math.toRadians(d.p),
      heading: Cesium.Math.toRadians(20)
    };
    if (typeof app.applySig === "function") app.applySig(d);
    beginTravel();
    app.viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(state.orbit.center, d.r), {
      duration: 5,
      offset: new Cesium.HeadingPitchRange(state.orbit.heading, state.orbit.pitch, d.r),
      complete: ()=>{ state.orbiting = true; markTravelSettling(); }
    });
  }

  function goSpace(instant){
    setMode("space");
    state.orbiting = false;
    app.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    const dst = Cesium.Cartesian3.fromDegrees(127, 20, 22000000);
    if (instant) app.viewer.camera.setView({ destination: dst });
    else flyToCartesian(dst, { duration: 4.6 });
  }

  function goFree(){
    setMode("free");
    state.orbiting = false;
    app.viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }

  function setUnderwaterMode(on){
    if (!app.scene) return;
    // §1 globe는 수중 모드에서 반투명 수면용으로만 일시 허용한다.
    app.scene.globe.show = !!on;
    app.scene.globe.translucency.enabled = !!on;
    app.scene.globe.translucency.frontFaceAlpha = on ? 0.45 : 1.0;
  }

  function tickOrbit(dt){
    if (state.mode !== "tour" || !state.orbiting || !state.orbit) return;
    state.orbit.heading += 0.1 * dt;
    app.viewer.camera.lookAt(state.orbit.center, new Cesium.HeadingPitchRange(state.orbit.heading, state.orbit.pitch, state.orbit.range));
  }

  async function resolveGoogleKey(){
    if (state.googleKey !== undefined) return state.googleKey;
    try {
      const response = await fetch("/fly/", { credentials: "same-origin" });
      if (!response.ok) return state.googleKey = "";
      const html = await response.text();
      const match = html.match(/const\s+GOOGLE_KEY\s*=\s*"([^"]+)"/);
      return state.googleKey = (match && match[1]) || "";
    } catch (error) {
      console.warn("[swef-v2] key resolve", error);
      return state.googleKey = "";
    }
  }

  async function init(){
    const opts = {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      requestRenderMode: false,
      contextOptions: { webgl: { preserveDrawingBuffer: false } } // §2 preserveDrawingBuffer 금지
    };
    app.viewer = new Cesium.Viewer("cesiumContainer", opts);
    app.scene = app.viewer.scene;
    const scene = app.scene;
    scene.postProcessStages.fxaa.enabled = false; // §2 fxaa 기본 off
    scene.highDynamicRange = false; // §2 HDR 금지
    scene.msaaSamples = 1; // §2 msaaSamples > 1 금지
    scene.globe.enableLighting = true;
    scene.globe.depthTestAgainstTerrain = true;
    scene.globe.maximumScreenSpaceError = IS_TOUCH ? 6 : 3;
    scene.skyAtmosphere.show = true;
    scene.fog.enabled = true;
    scene.fog.density = 0.0004;
    scene.globe.show = false; // §1 이중 지구 금지
    app.viewer.clock.shouldAnimate = true;

    state.profile = getProfile();
    app.viewer.resolutionScale = state.profile.resolutionScale;
    Cesium.RequestScheduler.maximumRequestsPerServer = state.profile.maxRequests; // §3 기기 프로파일

    const googleKey = await resolveGoogleKey();
    if (googleKey) {
      try {
        Cesium.GoogleMaps.defaultApiKey = googleKey;
        const tileset = await Cesium.createGooglePhotorealistic3DTileset();
        tileset.cacheBytes = state.profile.cacheBytes;
        tileset.maximumCacheOverflowBytes = state.profile.overflowBytes;
        tileset.maximumScreenSpaceError = state.targetSSE;
        tileset.skipLevelOfDetail = false;
        tileset.cullRequestsWhileMoving = true; // §5
        tileset.preloadWhenHidden = false; // §5
        tileset.foveatedTimeDelay = 0.1;
        state.tileset = tileset;
        scene.primitives.add(tileset);
      } catch (error) {
        console.warn("[swef-v2] Google tiles", error);
        setLastErr(error);
      }
    }

    scene.globe.tileLoadProgressEvent.addEventListener((count)=>{ state.tileLoadProgress = count; });
    detectRenderer();
    applyGovernorTier();
    updateTierLabel();

    state.govAccum = { elapsed: 0, sum: 0, count: 0 };
    // §9 preRender 리스너는 반드시 try/catch 래퍼로 감싼다.
    scene.preRender.addEventListener(()=>safeRun("preRender", ()=>{
      const now = performance.now();
      const dtMs = state.lastFrameStamp ? Math.min(250, now - state.lastFrameStamp) : 16.6;
      const dt = dtMs / 1000;
      state.lastFrameStamp = now;
      state.govAccum.elapsed += dtMs;
      state.govAccum.sum += dtMs;
      state.govAccum.count += 1;
      evaluateGovernor();
      updateWarpBudget();
      tickOrbit(dt);
      updateTravelCurtain();
      state.speedKmh = currentSpeed() * 3.6;
      updateDiag(now, dtMs);
      emit("frame", { dt, dtMs, now });
    }));

    Object.assign(app, {
      on,
      emit,
      toast,
      setMode,
      setTab,
      getProfile,
      currentSpeed,
      capturePhoto,
      flyToDest,
      flyToCartesian,
      goFree,
      goSpace,
      beginTravel,
      markTravelSettling,
      setUnderwaterMode,
      safeRun,
      updateTierLabel,
      loadModuleLoader,
      refreshSWEFHook,
      toggleAllPostprocess(){},
      restoreAllPostprocess(){}
    });

    refreshSWEFHook();
    if (!bareMode) loadModuleLoader();
    emit("ready", app);
    setTimeout(()=>{ state.signatureReady = true; }, 12000);
    goSpace(true);
    setTimeout(()=>flyToDest(0), 1200);
    setTimeout(runProbe, 2000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", ()=>safeRun("init", init));
  else safeRun("init", init);
})();
