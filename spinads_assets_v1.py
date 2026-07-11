# spinads_assets_v1.py — 퍼블리셔 온보딩 페이지 + 설치 스크립트 원문
# 클라이언트/인스톨러는 ASCII 전용(PS 5.1 인코딩 지뢰 회피), 기본 mode=append(타인 설정 존중)

CLIENT_PS1 = r'''# spinads_client.ps1 - updates Claude Code spinner verbs (Windows, PS 5.1 compatible)
$ErrorActionPreference = "SilentlyContinue"
$settings = Join-Path $env:USERPROFILE ".claude\settings.json"
$cache    = Join-Path $env:USERPROFILE ".spinads\last_verbs.json"
$keyfile  = Join-Path $env:USERPROFILE ".spinads\key"
$api      = "https://linklynk.onrender.com/api/spinads/verbs"

$key = $env:SPINADS_KEY
if (-not $key -and (Test-Path $keyfile)) { $key = (Get-Content $keyfile -Raw -Encoding UTF8).Trim() }
if (-not $key) { exit 0 }

try { $resp = Invoke-RestMethod -Uri $api -Headers @{ "X-API-Key" = $key } -TimeoutSec 5 } catch { exit 0 }
$new = @($resp.verbs)
if ($new.Count -eq 0) { exit 0 }

$cfg = New-Object PSCustomObject
if (Test-Path $settings) { $cfg = Get-Content $settings -Raw -Encoding UTF8 | ConvertFrom-Json }
$prev = @()
if (Test-Path $cache) { $prev = @(Get-Content $cache -Raw -Encoding UTF8 | ConvertFrom-Json) }

if (-not ($cfg.PSObject.Properties.Name -contains "spinnerVerbs")) {
  $cfg | Add-Member -NotePropertyName spinnerVerbs -NotePropertyValue ([PSCustomObject]@{ mode = "append"; verbs = @() })
}
if (-not ($cfg.spinnerVerbs.PSObject.Properties.Name -contains "verbs")) {
  $cfg.spinnerVerbs | Add-Member -NotePropertyName verbs -NotePropertyValue @()
}
$kept = @($cfg.spinnerVerbs.verbs | Where-Object { $prev -notcontains $_ })
$cfg.spinnerVerbs.verbs = @($kept + $new)
if (-not ($cfg.spinnerVerbs.PSObject.Properties.Name -contains "mode")) {
  $cfg.spinnerVerbs | Add-Member -NotePropertyName mode -NotePropertyValue "append"
}

$noBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($settings, ($cfg | ConvertTo-Json -Depth 20), $noBom)
[IO.File]::WriteAllText($cache, ($new | ConvertTo-Json), $noBom)
'''

CLIENT_PY = r'''#!/usr/bin/env python3
# spinads_client.py - updates Claude Code spinner verbs (macOS/Linux)
import json, os, urllib.request

HOME = os.path.expanduser("~")
SETTINGS = os.path.join(HOME, ".claude", "settings.json")
CACHE = os.path.join(HOME, ".spinads", "last_verbs.json")
KEYFILE = os.path.join(HOME, ".spinads", "key")
API = "https://linklynk.onrender.com/api/spinads/verbs"

def get_key():
    k = os.environ.get("SPINADS_KEY", "")
    if not k and os.path.exists(KEYFILE):
        with open(KEYFILE, encoding="utf-8") as f:
            k = f.read().strip()
    return k

def main():
    key = get_key()
    if not key:
        return
    req = urllib.request.Request(API, headers={"X-API-Key": key})
    new = json.load(urllib.request.urlopen(req, timeout=5)).get("verbs", [])
    if not new:
        return
    settings = {}
    if os.path.exists(SETTINGS):
        with open(SETTINGS, encoding="utf-8") as f:
            settings = json.load(f)
    prev = []
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            prev = json.load(f)
    sv = settings.get("spinnerVerbs") or {"mode": "append", "verbs": []}
    kept = [v for v in sv.get("verbs", []) if v not in prev]
    sv["verbs"] = kept + new
    sv.setdefault("mode", "append")
    settings["spinnerVerbs"] = sv
    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SETTINGS)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
'''

INSTALL_PS1 = r'''# SpinAds installer (Windows)
$ErrorActionPreference = "Stop"
$base = "https://linklynk.onrender.com"
$dir = Join-Path $env:USERPROFILE ".spinads"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$client = Join-Path $dir "spinads_client.ps1"
$u8 = New-Object System.Text.UTF8Encoding($false)
$code = Invoke-RestMethod -Uri "$base/spinads/client.ps1"
[IO.File]::WriteAllText($client, $code, $u8)

$key = $env:SPINADS_KEY
if (-not $key) { $key = Read-Host "SpinAds publisher key" }
[IO.File]::WriteAllText((Join-Path $dir "key"), $key.Trim(), $u8)

$claudeDir = Join-Path $env:USERPROFILE ".claude"
New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
$settings = Join-Path $claudeDir "settings.json"
$cfg = New-Object PSCustomObject
if (Test-Path $settings) { $cfg = [IO.File]::ReadAllText($settings, $u8) | ConvertFrom-Json }
if (-not ($cfg.PSObject.Properties.Name -contains "hooks")) {
  $cfg | Add-Member -NotePropertyName hooks -NotePropertyValue ([PSCustomObject]@{})
}
if (-not ($cfg.hooks.PSObject.Properties.Name -contains "SessionStart")) {
  $cfg.hooks | Add-Member -NotePropertyName SessionStart -NotePropertyValue @()
}
$cmd = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $client + '"'
$exists = $false
foreach ($m in @($cfg.hooks.SessionStart)) {
  foreach ($h in @($m.hooks)) { if ("$($h.command)" -like "*spinads*") { $exists = $true } }
}
if (-not $exists) {
  $entry = [PSCustomObject]@{ hooks = @([PSCustomObject]@{ type = "command"; command = $cmd }) }
  $cfg.hooks.SessionStart = @($cfg.hooks.SessionStart) + $entry
}
[IO.File]::WriteAllText($settings, ($cfg | ConvertTo-Json -Depth 20), $u8)

& powershell -NoProfile -ExecutionPolicy Bypass -File $client
Write-Host ""
Write-Host "SpinAds installed. Restart Claude Code (terminal) and sponsored verbs will rotate in the spinner."
'''

INSTALL_SH = r'''#!/usr/bin/env bash
# SpinAds installer (macOS/Linux)
set -e
BASE="https://linklynk.onrender.com"
mkdir -p "$HOME/.spinads"
curl -fsSL "$BASE/spinads/client.py" -o "$HOME/.spinads/spinads_client.py"

if [ -z "$SPINADS_KEY" ]; then
  read -r -p "SpinAds publisher key: " SPINADS_KEY < /dev/tty
fi
printf '%s' "$SPINADS_KEY" > "$HOME/.spinads/key"

python3 - <<'PYEOF'
import json, os
home = os.path.expanduser("~")
sdir = os.path.join(home, ".claude")
os.makedirs(sdir, exist_ok=True)
sp = os.path.join(sdir, "settings.json")
cfg = {}
if os.path.exists(sp):
    with open(sp, encoding="utf-8") as f:
        cfg = json.load(f)
cmd = 'python3 "' + os.path.join(home, ".spinads", "spinads_client.py") + '"'
hooks = cfg.setdefault("hooks", {}).setdefault("SessionStart", [])
if "spinads" not in json.dumps(hooks):
    hooks.append({"hooks": [{"type": "command", "command": cmd}]})
with open(sp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
PYEOF

python3 "$HOME/.spinads/spinads_client.py" || true
echo ""
echo "SpinAds installed. Restart Claude Code (terminal) and sponsored verbs will rotate in the spinner."
'''

PUBLISH_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SpinAds — Claude Code 스피너 문구팩</title>
<style>body{font-family:system-ui,-apple-system,'Noto Sans KR',sans-serif;background:#111;color:#eee;
max-width:560px;margin:0 auto;padding:48px 20px;line-height:1.7}
h1{font-size:26px}h2{font-size:16px;margin-top:32px}p,li{color:#bbb;font-size:14px}
input,select{width:100%;box-sizing:border-box;background:#1c1c1c;border:1px solid #333;color:#eee;
border-radius:8px;padding:10px;margin:6px 0;font-size:14px}
button{background:#7aa2ff;color:#111;border:0;border-radius:8px;padding:12px 20px;font-weight:700;
font-size:14px;cursor:pointer;margin-top:10px}
code,pre{font-family:ui-monospace,monospace;background:#1c1c1c;border-radius:6px}
pre{padding:12px;overflow-x:auto;font-size:12px;white-space:pre-wrap;word-break:break-all}
#result{display:none}.warn{color:#fc6;font-size:13px}</style></head><body>
<h1>SpinAds 문구팩</h1>
<p>Claude Code가 생각하는 동안, 스피너가 좀 놀아도 됩니다.
<span class="mono">"레거시 코드에게 정중히 사과하는 중…"</span> 같은 문구들이 세션마다 새로 로테이션되고,
그 사이에 스폰서 한 줄이 섞입니다. 굴리다 보면 커피값이 쌓이는 구조 — 배분 60%, 토스·계좌·PayPal·Payoneer 정산.</p>
<style>.mono{font-family:ui-monospace,monospace;background:#1c1c1c;padding:2px 6px;border-radius:4px;font-size:13px}</style>
<div id="form-wrap">
<h2>1분 가입</h2>
<form id="f">
<input name="name" placeholder="닉네임 (필수)" required maxlength="40">
<input name="email" placeholder="이메일 (정산 안내용, 필수)" required maxlength="120" type="email">
<select name="lang">
<option value="ko">문구팩: 한국어</option><option value="en">Pack: English</option>
</select>
<select name="payout_method">
<option value="toss">정산: 토스</option><option value="bank_krw">정산: 계좌이체(KRW)</option>
<option value="paypal">정산: PayPal</option><option value="payoneer">정산: Payoneer</option>
</select>
<button>키 발급받기</button>
</form>
</div>
<div id="result">
<h2>발급 완료</h2>
<p class="warn">아래 키는 지금 한 번만 표시됩니다. 설치 명령에 이미 포함돼 있으니 그대로 복사해 실행하세요.</p>
<h2>Windows (PowerShell)</h2><pre id="cmd-win"></pre>
<h2>macOS / Linux</h2><pre id="cmd-nix"></pre>
<p>실행 후 Claude Code(터미널)를 재시작하면 다음 세션부터 문구팩이 돕니다.
기존 커스텀 verb는 보존되고, settings.json의 spinnerVerbs와 SessionStart 훅을 지우면 언제든 해제됩니다.</p>
</div>
<p style="font-size:12px;color:#666">수익은 세션 단위로 원장에 적립되며 월 단위 정산 안내를 이메일로 드립니다.
문의: ikymximy@kohganemultishop.org · <a style="color:#7aa2ff" href="/spinads">광고주이신가요?</a></p>
<script>
document.getElementById('f').onsubmit=async function(e){e.preventDefault();
const d=Object.fromEntries(new FormData(this));
const r=await fetch('/api/spinads/publishers/register',{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
if(!r.ok){alert('가입 실패 — 입력값을 확인해주세요');return}
const j=await r.json();
document.getElementById('cmd-win').textContent=
"$env:SPINADS_KEY='"+j.api_key+"'; irm https://linklynk.onrender.com/spinads/install.ps1 | iex";
document.getElementById('cmd-nix').textContent=
"SPINADS_KEY='"+j.api_key+"' bash -c \\"$(curl -fsSL https://linklynk.onrender.com/spinads/install.sh)\\"";
document.getElementById('form-wrap').style.display='none';
document.getElementById('result').style.display='block'};
</script></body></html>"""
