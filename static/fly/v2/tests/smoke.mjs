#!/usr/bin/env node
// smoke.mjs — SWEF v2 contract smoke test
// Run: node static/fly/v2/tests/smoke.mjs
// No external dependencies, no browser required.

import { execFileSync } from "child_process";
import { readFileSync, readdirSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "../js");

function readFile(name) {
  return readFileSync(resolve(ROOT, name), "utf8");
}

let allPassed = true;
function result(label, ok, detail) {
  const mark = ok ? "✅" : "❌";
  console.log(`  ${mark} ${label}${detail ? " — " + detail : ""}`);
  if (!ok) allPassed = false;
}

// ─── Check 1: Syntax ─────────────────────────────────────────────────────────
console.log("\n[1] 문법 검사 (new Function 로드 가능)");
const FILES = ["data.js", "engine.js", "input.js", "features.js", "ui.js"];
const sources = {};
for (const f of FILES) {
  let ok = false;
  let err = "";
  try {
    const src = readFile(f);
    sources[f] = src;
    new Function(src); // eslint-disable-line no-new-func
    ok = true;
  } catch (e) {
    err = String(e).split("\n")[0];
  }
  result(f, ok, ok ? "" : err);
}

// ─── Check 2: Data contract ──────────────────────────────────────────────────
console.log("\n[2] 데이터 계약 (data.js)");
const dataSource = sources["data.js"] || readFile("data.js");

function countArrayItems(src, varName) {
  // Match: const/let/var NAME = [ ... ] or NAME = [ ... ] spanning lines
  // Strategy: find the start of the array literal after the variable name,
  // then count balanced brackets.
  const startRe = new RegExp(`(?:const|let|var)\\s+${varName}\\s*=\\s*\\[`);
  const m = startRe.exec(src);
  if (!m) return -1;
  let depth = 0;
  let inStr = false;
  let strChar = "";
  let escaped = false;
  let count = 0;
  let i = m.index + m[0].length - 1; // position of opening [
  for (; i < src.length; i++) {
    const ch = src[i];
    if (inStr) {
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === strChar) {
        inStr = false;
      }
    } else if (ch === '"' || ch === "'" || ch === "`") {
      inStr = true;
      strChar = ch;
      escaped = false;
    } else if (ch === "[" || ch === "{") {
      depth++;
    } else if (ch === "]" || ch === "}") {
      depth--;
      if (depth === 0) break;
    } else if (ch === "," && depth === 1) {
      count++;
    }
  }
  // count commas at depth 1 → items = commas + 1 (if non-empty)
  // But we need to check if array is non-empty
  const arrayContent = src.slice(m.index + m[0].length, i).trim();
  if (!arrayContent) return 0;
  // Handle trailing comma: if the content right before the closing bracket
  // (ignoring whitespace) ends with a comma, it's a trailing comma.
  // In that case items == count (not count+1).
  const trailing = /,\s*$/.test(arrayContent);
  return trailing ? count : count + 1;
}

const contracts = [
  { name: "VEHICLES", expected: 74, op: "eq" },
  { name: "DESTS", expected: 130, op: "gte" },
  { name: "PORTALS", expected: 18, op: "eq" },
  { name: "TRIALS", expected: 2, op: "eq" },
  { name: "DREAM_SKIES", expected: 14, op: "eq" },
  { name: "FILMS", expected: 12, op: "eq" },
];

for (const { name, expected, op } of contracts) {
  const count = countArrayItems(dataSource, name);
  const ok =
    count >= 0 && (op === "eq" ? count === expected : count >= expected);
  const detail =
    count < 0
      ? "not found"
      : `found ${count}, expected ${op === "gte" ? ">=" : ""}${expected}`;
  result(`${name} ${op === "gte" ? ">=" : "="}${expected}`, ok, ok ? `found ${count}` : detail);
}

// ─── Check 3: Iron law markers (engine.js) ───────────────────────────────────
console.log("\n[3] 철칙 마커 (engine.js)");
const engineSrc = sources["engine.js"] || readFile("engine.js");
const markers = [
  { label: "globe.show = false", pattern: "globe.show = false" },
  { label: "msaaSamples = 1", pattern: "msaaSamples = 1" },
  { label: "highDynamicRange = false", pattern: "highDynamicRange = false" },
  { label: "시간기반 거버너 (1500)", pattern: "1500" },
  { label: "계단하강 (skip)", pattern: "skip" },
];
for (const { label, pattern } of markers) {
  result(label, engineSrc.includes(pattern));
}

// ─── Check 4: Forbidden strings (all 5 files) ────────────────────────────────
console.log("\n[4] 금지어 부재 (5개 파일 전체)");
const allSource = FILES.map((f) => sources[f] || readFile(f)).join("\n");
const forbidden = [
  "preserveDrawingBuffer:true",
  "msaaSamples = 4",
  "highDynamicRange = true",
];
for (const term of forbidden) {
  result(`"${term}" 없음`, !allSource.includes(term));
}

// ─── Check 5: Storage key contract ──────────────────────────────────────────
console.log("\n[5] 저장키 계약 (5개 파일 전체)");
const storageKeys = [
  "swef_gate1",
  "swef_gate2",
  "swef_gate3",
  "swef_gate4",
  "swef_visits",
  "swef_stars",
  "ef_av_size",
  "swef_tune_",
];
for (const key of storageKeys) {
  result(`"${key}" 존재`, allSource.includes(key));
}

// ─── Check 6: v2 추가 불변식 ───────────────────────────────────────────────────
console.log("\n[6] v2 추가 불변식");
const featuresSrc = sources["features.js"] || readFile("features.js");
const uiSrc = sources["ui.js"] || readFile("ui.js");

const patchTags = ["P0-0921a", "P2-1001", "P3-1002", "P5-1007", "P6-1008", "P7-1008", "P8-1008", "P9-1008"];
for (const tag of patchTags) {
  result(`engine.js patch tag "${tag}"`, engineSrc.includes(tag));
}
result("engine.js SPACE_ON = 320000", engineSrc.includes("SPACE_ON = 320000"));
result("engine.js SPACE_OFF = 240000", engineSrc.includes("SPACE_OFF = 240000"));
result(
  "engine.js globe.show = want || !!state.underwater",
  engineSrc.includes("globe.show = want || !!state.underwater")
);

const preRenderMatch = engineSrc.match(
  /scene\.preRender\.addEventListener\(\(\)=>safeRun\("preRender", \(\)=>\{[\s\S]*?\}\)\);/
);
if (!preRenderMatch) {
  result("preRender 핸들러 내 updateSpaceView()/updateWarpBudget() 순서", false, "preRender block not found");
} else {
  const preRenderBlock = preRenderMatch[0];
  const iSpace = preRenderBlock.indexOf("updateSpaceView()");
  const iWarp = preRenderBlock.indexOf("updateWarpBudget()");
  result(
    "preRender: updateSpaceView() before updateWarpBudget()",
    iSpace >= 0 && iWarp >= 0 && iSpace < iWarp,
    iSpace >= 0 && iWarp >= 0 ? `space=${iSpace}, warp=${iWarp}` : "one or both calls missing"
  );
}

result('features.js contains "u_camH<80000.0"', featuresSrc.includes("u_camH<80000.0"));
result('features.js contains "uniform float u_gold"', featuresSrc.includes("uniform float u_gold"));
result('features.js contains "data-fallback"', featuresSrc.includes("data-fallback"));
result('ui.js avSizeR2 max 220', /id="avSizeR2"[^>]*max="220"/.test(uiSrc));

// ─── Check 7: node --check ────────────────────────────────────────────────────
console.log("\n[7] node --check (static/fly/v2/js/*.js)");
const jsFiles = readdirSync(ROOT).filter((name) => name.endsWith(".js")).sort();
for (const f of jsFiles) {
  const filePath = resolve(ROOT, f);
  let ok = false;
  let err = "";
  try {
    execFileSync(process.execPath, ["--check", filePath], { stdio: "pipe" });
    ok = true;
  } catch (e) {
    err = String((e && (e.stderr || e.stdout)) || e).split("\n")[0];
  }
  result(`node --check ${f}`, ok, ok ? "" : err);
}

// ─── Summary ─────────────────────────────────────────────────────────────────
console.log("");
if (allPassed) {
  console.log("✅ 모든 검사 통과");
  process.exit(0);
} else {
  console.log("❌ 일부 검사 실패");
  process.exit(1);
}
