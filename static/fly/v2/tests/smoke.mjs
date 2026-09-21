#!/usr/bin/env node
// smoke.mjs — SWEF v2 contract smoke test
// Run: node static/fly/v2/tests/smoke.mjs
// No external dependencies, no browser required.

import { readFileSync } from "fs";
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

// ─── Summary ─────────────────────────────────────────────────────────────────
console.log("");
if (allPassed) {
  console.log("✅ 모든 검사 통과");
  process.exit(0);
} else {
  console.log("❌ 일부 검사 실패");
  process.exit(1);
}
