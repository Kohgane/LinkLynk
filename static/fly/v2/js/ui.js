(function(){
  "use strict";

  const app = window.SWEF_V2;
  if (!app) return;

  const { DESTS, VEHICLES, FILMS } = app.data;
  let currentCategory = "all";

  function dn(item){ return item.n; }
  function $(id){ return document.getElementById(id); }

  function makeScroller(el){
    if (!el) return;
    let dragX = null;
    el.addEventListener("wheel", (event)=>{
      if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
        // §조작 명소/탈것 행은 휠을 가로 스크롤로 변환한다.
        el.scrollLeft += event.deltaY;
        event.preventDefault();
      }
    }, { passive: false });
    el.addEventListener("mousedown", (event)=>{ dragX = event.clientX + el.scrollLeft; });
    window.addEventListener("mousemove", (event)=>{ if (dragX !== null) el.scrollLeft = dragX - event.clientX; });
    window.addEventListener("mouseup", ()=>{ dragX = null; });
  }

  function buildShell(){
    const panel = $("panel");
    if (!panel) return;
    panel.innerHTML = [
      '<div id="tabbar">',
      '  <button class="tabb on" id="tabExplore">🌍 탐험</button>',
      '  <button class="tabb" id="tabRides">🐉 탈것</button>',
      '  <button class="tabb" id="tabUser">🧭 유저</button>',
      '  <button class="tabb" id="tabStudio">🎬 연출</button>',
      '</div>',
      '<div class="panel show" id="panelExplore">',
      '  <div class="chips" id="destCats"></div>',
      '  <div class="cards" id="destCards"></div>',
      '</div>',
      '<div class="panel" id="panelRides">',
      '  <div class="cards" id="vehCards"></div>',
      '  <div class="stack">',
      '    <div class="control"><span>⚙️ 속도</span><input type="range" id="custSp" min="0.1" max="8" step="0.1" value="1"><output id="custSpv">1.0×</output></div>',
      '    <div class="control"><span>🌀 민첩</span><input type="range" id="custAg" min="0.3" max="3" step="0.1" value="1"><output id="custAgv">1.0×</output></div>',
      '    <div class="control"><span>🛩 크기</span><input type="range" id="avSizeR2" min="24" max="140" step="2" value="44"><button class="btn" id="btnAvHide">👻</button></div>',
      '  </div>',
      '</div>',
      '<div class="panel" id="panelUser">',
      '  <div class="row">',
      '    <button class="btn" id="btnTrackHere">📍 지금 위치 기록</button>',
      '    <button class="btn" id="btnImportStars">⭐ Takeout 가져오기</button>',
      '    <button class="btn" id="btnJourneyRefresh">↻ 새로고침</button>',
      '  </div>',
      '  <div class="meta">시그니처는 부팅 12초 후 이 유저 탭에서만 자동 적용됩니다. 진행도와 튜닝은 v1과 같은 localStorage 키를 그대로 사용합니다.</div>',
      '  <div id="journeyList"></div>',
      '  <input type="file" id="vjFile" accept=".json,application/json" class="hidden">',
      '</div>',
      '<div class="panel" id="panelStudio">',
      '  <div class="cards" id="filmCards"></div>',
      '  <div class="row">',
      '    <button class="btn" id="btnCloud">☁️ <span id="cloudLbl">구름 OFF</span></button>',
      '    <button class="btn" id="btnDream">🌌 드림스카이</button>',
      '    <button class="btn" id="btnMb">💫 <span id="mbLbl">블러 OFF</span></button>',
      '    <button class="btn" id="btnAtmo">🌫 대기</button>',
      '  </div>',
      '</div>',
      '<div id="footerRow">',
      '  <button class="btn on" id="btnTour">투어</button>',
      '  <button class="btn" id="btnFree">자유비행</button>',
      '  <button class="btn" id="btnSpace">우주</button>',
      '  <button class="btn" id="btnPhoto">📷 사진</button>',
      '  <button class="btn" id="btnStats">📊 진행</button>',
      '  <div id="timeWrap"><span>☀️</span><input type="range" id="timeSlider" min="0" max="24" step="0.1" value="17.5"><span id="timeLabel">17:30</span></div>',
      '</div>'
    ].join("");
    ["destCats","destCards","vehCards","filmCards","moduleRail"].forEach((id)=>makeScroller($(id)));
  }

  function syncTabs(){
    const map = {
      explore: ["tabExplore", "panelExplore"],
      rides: ["tabRides", "panelRides"],
      user: ["tabUser", "panelUser"],
      studio: ["tabStudio", "panelStudio"]
    };
    Object.keys(map).forEach((name)=>{
      const [tabId, panelId] = map[name];
      $(tabId).classList.toggle("on", app.state.currentTab === name);
      $(panelId).classList.toggle("show", app.state.currentTab === name);
    });
  }

  function renderDestCats(){
    const wrap = $("destCats");
    if (!wrap) return;
    const cats = [["all","전체"],["s","절경"],["w","유적"],["c","도시"],["h","비경"],["x","극한"]];
    wrap.innerHTML = "";
    cats.forEach(([id, label], idx)=>{
      const el = document.createElement("button");
      el.className = "chip" + ((idx === 0 && currentCategory === "all") || currentCategory === id ? " on" : "");
      el.textContent = label;
      el.onclick = ()=>{ currentCategory = id; renderDestCats(); renderDests(); };
      wrap.appendChild(el);
    });
    const rnd = document.createElement("button");
    rnd.className = "chip";
    rnd.textContent = "🎲 랜덤";
    rnd.onclick = ()=>app.flyToDest(Math.floor(Math.random() * DESTS.length));
    wrap.appendChild(rnd);
  }

  function renderDests(){
    const wrap = $("destCards");
    if (!wrap) return;
    wrap.innerHTML = "";
    const today = new Date();
    const seed = today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
    const featureIndex = ((seed * 9301 + 49297) % 233280) % DESTS.length;
    const feature = document.createElement("button");
    feature.className = "card accent";
    feature.textContent = "⭐ 오늘의 명소: " + dn(DESTS[featureIndex]);
    feature.onclick = ()=>{ $("timeSlider").value = "18.2"; app.flyToDest(featureIndex); };
    wrap.appendChild(feature);
    DESTS.forEach((dest, index)=>{
      if (currentCategory !== "all" && dest.c !== currentCategory) return;
      const el = document.createElement("button");
      el.className = "card";
      el.textContent = dn(dest);
      el.onclick = ()=>app.flyToDest(index);
      wrap.appendChild(el);
    });
  }

  function syncTuneInputs(){
    const veh = app.state.vehicle || VEHICLES[0];
    const sp = +(veh.sp || 1).toFixed(1);
    const ag = +(veh.ag || 1).toFixed(1);
    $("custSp").value = sp;
    $("custAg").value = ag;
    $("custSpv").textContent = sp.toFixed(1) + "×";
    $("custAgv").textContent = ag.toFixed(1) + "×";
    document.querySelectorAll("#vehCards .card").forEach((el, idx)=>el.classList.toggle("on", idx === app.state.vehicleIndex));
  }

  function renderVehicles(){
    const wrap = $("vehCards");
    if (!wrap) return;
    wrap.innerHTML = "";
    VEHICLES.forEach((veh, index)=>{
      const locked = veh.lock && !localStorage.getItem(veh.lock);
      const el = document.createElement("button");
      el.className = "card";
      if (locked) {
        el.textContent = "🔒 ???";
        el.style.opacity = "0.5";
      } else if (veh.e.indexOf("img:") === 0) {
        el.innerHTML = '<img loading="lazy" decoding="async" src="' + veh.e.slice(4) + '" alt=""> ' + dn(veh);
      } else {
        el.textContent = veh.e + " " + dn(veh);
      }
      el.onclick = ()=>{ app.pickVehicle(index); syncTuneInputs(); };
      wrap.appendChild(el);
    });
  }

  function renderFilms(){
    const wrap = $("filmCards");
    if (!wrap) return;
    wrap.innerHTML = "";
    FILMS.forEach((film, index)=>{
      const el = document.createElement("button");
      el.className = "card filmc" + (index === 0 ? " on" : "");
      el.textContent = film[0];
      el.onclick = ()=>app.setFilm(index);
      wrap.appendChild(el);
    });
  }

  function syncModeButtons(){
    [["btnTour","tour"],["btnFree","free"],["btnSpace","space"]].forEach(([id, mode])=>$(id).classList.toggle("on", app.state.mode === mode));
  }

  function showProgress(){
    const portals = (()=>{ try { return JSON.parse(localStorage.getItem("swef_portals") || "[]").length; } catch (_) { return 0; } })();
    const gods = (()=>{ try { return JSON.parse(localStorage.getItem("swef_gods") || "[]").length; } catch (_) { return 0; } })();
    const kr = (()=>{ try { return JSON.parse(localStorage.getItem("swef_kr") || "[]").length; } catch (_) { return 0; } })();
    const visits = (()=>{ try { return JSON.parse(localStorage.getItem("swef_visits") || "[]").length; } catch (_) { return 0; } })();
    const stars = (()=>{ try { return JSON.parse(localStorage.getItem("swef_stars") || "[]").length; } catch (_) { return 0; } })();
    app.toast("🐲 " + gods + "/4 · 🏯 " + kr + "/4 · 🌀 " + portals + "/" + app.PORTALS.length + " · 📍 " + visits + " · ⭐ " + stars, 3600);
  }

  function updateGauge(){
    const gauge = $("gauge");
    if (!gauge) return;
    if (app.state.mode !== "free") { gauge.classList.add("hidden"); return; }
    gauge.classList.remove("hidden");
    const kmh = app.state.speedKmh || 0;
    const pct = Math.min(100, Math.round(kmh / 8000 * 100));
    gauge.style.background = "conic-gradient(rgba(90,180,255,.92) " + pct + "%, rgba(255,255,255,.12) 0)";
    $("gKv").textContent = kmh >= 10000 ? (kmh / 10000).toFixed(1) + "만" : Math.round(kmh).toLocaleString();
  }

  function addModuleButton(cfg){
    const rail = $("moduleRail");
    if (!rail || !cfg || !cfg.id) return;
    if (document.getElementById(cfg.id)) return;
    const el = document.createElement("button");
    el.className = "module-btn";
    el.id = cfg.id;
    el.innerHTML = (cfg.icon || "✨") + ' <small>' + (cfg.label || cfg.id) + '</small>';
    el.onclick = ()=>{ try { cfg.onClick && cfg.onClick(); } catch (error) { console.warn("[swef-v2] module button", error); } };
    rail.appendChild(el);
  }

  function syncModuleHook(){
    if (!window.SWEFM) return;
    window.SWEFM._registerButtonImpl = addModuleButton;
    (window.SWEFM._btnQueue || []).splice(0).forEach(addModuleButton);
  }

  function bindControls(){
    $("tabExplore").onclick = ()=>app.setTab("explore");
    $("tabRides").onclick = ()=>app.setTab("rides");
    $("tabUser").onclick = ()=>app.setTab("user");
    $("tabStudio").onclick = ()=>app.setTab("studio");
    $("btnTour").onclick = ()=>app.flyToDest(Math.max(0, app.state.currentDest ? DESTS.indexOf(app.state.currentDest) : 0));
    $("btnFree").onclick = ()=>app.goFree();
    $("btnSpace").onclick = ()=>app.goSpace(false);
    $("btnPhoto").onclick = ()=>app.capturePhoto();
    $("btnStats").onclick = showProgress;
    $("timeSlider").oninput = ()=>app.setLocalTime(parseFloat($("timeSlider").value));
    $("btnCloud").onclick = ()=>app.cycleCloudMode();
    $("btnDream").onclick = ()=>app.toggleDream();
    $("btnMb").onclick = ()=>{
      const next = ((parseInt(localStorage.getItem("swef_mb") || "0", 10) + 1) % 3);
      app.setMotionBlurLevel(next);
      $("mbLbl").textContent = ["블러 OFF", "블러 180°", "블러 360°"][next];
      $("btnMb").classList.toggle("on", next > 0);
      app.toast("💫 " + $("mbLbl").textContent);
    };
    $("btnAtmo").onclick = ()=>{
      const on = localStorage.getItem("swef_atmo") !== "0";
      app.setAtmosphereEnabled(!on);
      $("btnAtmo").classList.toggle("on", !on);
      app.toast(!on ? "🌫 대기 ON" : "🌫 대기 OFF");
    };
    $("btnTrackHere").onclick = ()=>app.vjTrack(false);
    $("btnJourneyRefresh").onclick = ()=>app.vjRender();
    $("btnImportStars").onclick = ()=>$("vjFile").click();
    $("vjFile").onchange = ()=>{ if ($("vjFile").files[0]) app.vjImportFile($("vjFile").files[0]); $("vjFile").value = ""; };
    $("custSp").oninput = ()=>{ $("custSpv").textContent = (+$("custSp").value).toFixed(1) + "×"; app.tuneVehicle(parseFloat($("custSp").value), parseFloat($("custAg").value)); };
    $("custAg").oninput = ()=>{ $("custAgv").textContent = (+$("custAg").value).toFixed(1) + "×"; app.tuneVehicle(parseFloat($("custSp").value), parseFloat($("custAg").value)); };
    $("avSizeR2").value = localStorage.getItem("ef_av_size") || (app.IS_TOUCH ? "42" : "68");
    $("avSizeR2").oninput = ()=>{ localStorage.setItem("ef_av_size", $("avSizeR2").value); };
    const paintHide = ()=>{
      const hidden = localStorage.getItem("swef_avhide") === "1";
      $("btnAvHide").classList.toggle("on", hidden);
      $("btnAvHide").textContent = hidden ? "👻 숨김중" : "👻";
    };
    $("btnAvHide").onclick = ()=>{
      const hidden = localStorage.getItem("swef_avhide") === "1";
      localStorage.setItem("swef_avhide", hidden ? "0" : "1");
      paintHide();
      app.toast(hidden ? "👻 기체 표시" : "👻 기체 숨김");
    };
    paintHide();
  }

  app.on("ready", ()=>{
    buildShell();
    renderDestCats();
    renderDests();
    renderVehicles();
    renderFilms();
    bindControls();
    syncTabs();
    syncModeButtons();
    syncTuneInputs();
    app.vjRender && app.vjRender();
    if (localStorage.getItem("swef_vj_auto") === "1") setTimeout(()=>app.vjTrack(true), 2400);
    setInterval(syncModuleHook, 1200);
    syncModuleHook();
    $("btnAtmo").classList.toggle("on", localStorage.getItem("swef_atmo") !== "0");
    const blur = parseInt(localStorage.getItem("swef_mb") || "0", 10);
    $("mbLbl").textContent = ["블러 OFF", "블러 180°", "블러 360°"][blur];
    $("btnMb").classList.toggle("on", blur > 0);
  });

  app.on("tab", ()=>syncTabs());
  app.on("mode", ()=>syncModeButtons());
  app.on("vehicle", ()=>syncTuneInputs());
  app.on("frame", ()=>updateGauge());
})();
