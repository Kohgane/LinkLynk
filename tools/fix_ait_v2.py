# -*- coding: utf-8 -*-
"""AITBUNDL deploymentId 동기화 수술 v2
   ─ 무엇을 고치나
     .ait = [AITBUNDL 헤더(protobuf)] + [zip]
     헤더에 deploymentId(UUID v7)가 있고, granite 런타임 번들 4개 안에도
     global.__appsInToss = { deploymentId: "..." } 로 같은 값이 박혀 있어야 한다.
     도너 셸을 재사용하면 번들 내부에 옛 배포 ID가 남아 둘이 어긋나고,
     엣지가 배포를 식별하지 못해 CloudFront 503이 난다.

   ─ 어떻게 고치나
     새 UUID v7을 발급해 헤더와 번들 4개에 동시에 심고,
     바뀐 파일의 SHA-256을 헤더에 다시 써넣는다.
     UUID 36자·해시 64자로 길이가 같아 protobuf 길이 필드를 건드리지 않는다.
     zip은 재압축하지 않고 엔트리 단위로 교체해 순서·압축방식·타임스탬프를 보존한다.

   ─ 사용법
     python3 fix_ait_v2.py <입력.ait> <출력.ait>              # 새 ID 자동 발급(권장)
     python3 fix_ait_v2.py <입력.ait> <출력.ait> --check      # 진단만, 파일 안 만듦
     python3 fix_ait_v2.py <입력.ait> <출력.ait> --id <UUID>  # ID 직접 지정
"""
import re, os, sys, io, time, zipfile, hashlib, secrets

U      = re.compile(rb'deploymentId:\s*"([0-9a-f-]{36})"')
HDRID  = re.compile(rb'\x12\$([0-9a-f-]{36})')
PATHS  = re.compile(rb'(?:web/)?[\w./-]+\.(?:js|map|png|html|css)')
HEX    = re.compile(rb'[0-9a-f]{64}')

def uuid7():
    """UUID v7 — 앞 48비트가 유닉스 밀리초. 토스 CLI와 같은 형식."""
    ms = int(time.time() * 1000)
    b = bytearray(ms.to_bytes(6, "big") + secrets.token_bytes(10))
    b[6] = (b[6] & 0x0F) | 0x70          # version 7
    b[8] = (b[8] & 0x3F) | 0x80          # variant 10
    h = b.hex()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])

def split(path):
    raw = open(path, "rb").read()
    i = raw.find(b"PK\x03\x04")
    if i < 0 or raw[:8] != b"AITBUNDL":
        raise SystemExit("[!] AITBUNDL 형식이 아니다: %s" % path)
    return raw[:i], raw[i:]

def report(path):
    pre, zb = split(path)
    hdr = HDRID.search(pre).group(1).decode()
    z = zipfile.ZipFile(io.BytesIO(zb))
    print("  파일        : %s (%d bytes)" % (os.path.basename(path), os.path.getsize(path)))
    print("  헤더 ID     : %s" % hdr)
    bad = 0
    for n in z.namelist():
        if n.endswith(".js"):
            for m in U.finditer(z.read(n)):
                mark = "OK" if m.group(1).decode() == hdr else "★불일치"
                if mark != "OK":
                    bad += 1
                print("  %-30s %s  %s" % (n, m.group(1).decode(), mark))
    ok = ng = 0
    tail = pre[pre.rfind(b"always"):]
    hexes = list(HEX.finditer(tail))
    for pm in PATHS.finditer(tail):
        n = pm.group().decode()
        if n not in z.namelist():
            continue
        h = [m for m in hexes if pm.end() < m.start() < pm.end() + 12]
        if not h:
            continue
        if hashlib.sha256(z.read(n)).hexdigest() == h[0].group().decode():
            ok += 1
        else:
            ng += 1
            print("  ★ SHA 불일치: %s" % n)
    print("  SHA-256     : 일치 %d / 불일치 %d" % (ok, ng))
    print("  판정        : %s" % ("정상" if bad == 0 and ng == 0 else "★수술 필요 (ID 불일치 %d)" % bad))
    return bad, ng

def fix(src, dst, newid):
    pre, zb = split(src)
    old_hdr = HDRID.search(pre).group(1)
    nid = newid.encode()
    if len(nid) != 36:
        raise SystemExit("[!] UUID는 36자여야 한다")
    print("  기존 헤더 ID : %s" % old_hdr.decode())
    print("  새 배포 ID   : %s" % newid)

    zin = zipfile.ZipFile(io.BytesIO(zb))
    buf = io.BytesIO()
    zout = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    newhash, changed = {}, 0
    for it in zin.infolist():
        data = zin.read(it.filename)
        found = set(m.group(1) for m in U.finditer(data))
        if found:
            for old in found:
                data = data.replace(old, nid)
            changed += 1
            print("    번들 %-28s %s -> 새 ID" % (it.filename, list(found)[0].decode()[:13] + "…"))
        newhash[it.filename] = hashlib.sha256(data).hexdigest().encode()
        zi = zipfile.ZipInfo(it.filename, date_time=it.date_time)
        zi.compress_type = it.compress_type
        zi.external_attr = it.external_attr
        zi.create_system = it.create_system
        zout.writestr(zi, data)
    zout.close()
    print("  번들 %d개 갱신" % changed)

    pre = pre.replace(old_hdr, nid)          # 헤더 ID 교체 (길이 동일)
    at = pre.rfind(b"always")
    head, tail = pre[:at], bytearray(pre[at:])
    hexes = list(HEX.finditer(bytes(tail)))
    n_fix = 0
    for pm in PATHS.finditer(bytes(tail)):
        name = pm.group().decode()
        if name not in newhash:
            continue
        for hm in hexes:
            if pm.end() < hm.start() < pm.end() + 12:
                if bytes(tail[hm.start():hm.end()]) != newhash[name]:
                    tail[hm.start():hm.end()] = newhash[name]
                    n_fix += 1
                break
    print("  헤더 SHA-256 %d개 갱신" % n_fix)
    open(dst, "wb").write(head + bytes(tail) + buf.getvalue())
    print("  저장 -> %s (%d bytes)" % (dst, os.path.getsize(dst)))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); raise SystemExit(1)
    src, dst = sys.argv[1], sys.argv[2]
    print("=== 진단: %s" % src)
    report(src)
    if "--check" in sys.argv:
        raise SystemExit(0)
    nid = sys.argv[sys.argv.index("--id") + 1] if "--id" in sys.argv else uuid7()
    print("=== 수술")
    fix(src, dst, nid)
    print("=== 검증: %s" % dst)
    report(dst)
