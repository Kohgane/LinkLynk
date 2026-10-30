#!/usr/bin/env python3
# -*- coding: ascii -*-
# apply_rx.py -- self-contained, pure ASCII, idempotent.
# Adds the RX verdict level (prescription-only at destination, no import permit).
import os, sys, py_compile, shutil, time, collections

MARKERS = ["_RX_FIX", "_bridge_before_rx", 'r["level"] == "RX"']

EDITS = [
    ('next_v1.py',
     '    pro = [r for r in rows if r["level"] == "PROHIBITED"]\n    per = [r for r in rows if r["level"] == "PERMIT"]\n    dec = [r for r in rows if r["level"] == "DECLARE"]\n    lim = [r for r in rows if r["level"] == "LIMIT"]\n    total = len(rows)\n    hard = len(pro) + len(per)\n    soft = len(dec) + len(lim)',
     '    pro = [r for r in rows if r["level"] == "PROHIBITED"]\n    per = [r for r in rows if r["level"] == "PERMIT"]\n    dec = [r for r in rows if r["level"] == "DECLARE"]\n    lim = [r for r in rows if r["level"] == "LIMIT"]\n    # \u2605RX = \uc218\uc785 \ud5c8\uac00 \uc81c\ub3c4\ub294 \uc5c6\ub294\ub370 \ud604\uc9c0\uc5d0\uc11c \ucc98\ubc29 \ub300\uc0c1\uc778 \uacbd\uc6b0(\uc601\uad6d\xb7\ub3c5\uc77c \uba5c\ub77c\ud1a0\ub2cc).\n    #   PERMIT \uc73c\ub85c \uc4f0\uba74 "\uc5c6\ub294 \ucc3d\uad6c\uc5d0 \uc2e0\uccad\ud558\ub77c"\uac00 \ub418\uace0, \ubc84\ud0b7\uc5d0\uc11c \ube7c\uba74 soft=0 \uc774 \ub418\uc5b4\n    #   \'\uc81c\ud55c \uc815\ubcf4 \uc5c6\uc74c\' \ucd08\ub85d\uc73c\ub85c \ub5a8\uc5b4\uc9c4\ub2e4. \ub458 \ub2e4 \uac70\uc9d3 \uc2e0\ud638\ub2e4. \uadf8\ub798\uc11c \uc81c \ubc84\ud0b7\uc744 \uc900\ub2e4.\n    rx = [r for r in rows if r["level"] == "RX"]\n    total = len(rows)\n    hard = len(pro) + len(per)\n    soft = len(dec) + len(lim) + len(rx)'),
    ('next_v1.py',
     '    elif soft:\n        head, tone = "%d\uac1c\uad6d\uc5d0\uc11c \uc2e0\uace0 \ub300\uc0c1\uc785\ub2c8\ub2e4" % soft, "amber"\n        head_en = "Must be declared in %d countr%s" % (soft, "y" if soft == 1 else "ies")',
     '    elif rx:\n        head, tone = "%d\uac1c\uad6d\uc5d0\uc11c \ud604\uc9c0 \ucc98\ubc29\uc774 \ud544\uc694\ud569\ub2c8\ub2e4" % len(rx), "amber"\n        head_en = ("Needs a local prescription in %d countr%s"\n                   % (len(rx), "y" if len(rx) == 1 else "ies"))\n    elif soft:\n        head, tone = "%d\uac1c\uad6d\uc5d0\uc11c \uc2e0\uace0 \ub300\uc0c1\uc785\ub2c8\ub2e4" % soft, "amber"\n        head_en = "Must be declared in %d countr%s" % (soft, "y" if soft == 1 else "ies")'),
    ('next_v1.py',
     '        "dec_en": [r["en"] for r in dec][:8],\n        "rows": rows,',
     '        "dec_en": [r["en"] for r in dec][:8],\n        "rx": [r["ko"] for r in rx], "rx_en": [r["en"] for r in rx],\n        "rows": rows,'),
]
APPENDS = [
    ('borderrx_v1.py',
     '\n\n# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n# \u2605RX \ub4f1\uae09 (2026-10-09). "\uc218\uc785 \ud5c8\uac00 \uc81c\ub3c4\uac00 \uc5c6\ub294\ub370 \ud604\uc9c0\uc5d0\uc11c\ub294 \ucc98\ubc29 \ub300\uc0c1"\n#   \uc601\uad6d\xb7\ub3c5\uc77c \uba5c\ub77c\ud1a0\ub2cc\uc774 PERMIT \uc73c\ub85c \ucc0d\ud600 \uc788\uc5c8\uace0, \uadf8 \uacb0\uacfc \ud398\uc774\uc9c0\uac00\n#   "\ucd9c\uad6d \uc804 \ub3c4\ucc29\uad6d \ubcf4\uac74\ub2f9\uad6d\uc758 \uc2b9\uc778\uc744 \ubc1b\uc73c\uc138\uc694"\ub77c\uace0 \ud588\ub2e4. \uadf8\ub7f0 \ucc3d\uad6c\uac00 \uc5c6\ub2e4.\n#   \uc5c6\ub294 \uc808\ucc28\ub97c \ucc3e\uc544\uac00\ub77c\uace0 \ubcf4\ub0b4\ub294 \uac74 BorderRx \uac00 \ub9c9\uc73c\ub77c\uace0 \ub9cc\ub4e4\uc5b4\uc9c4 \uc624\ub2f5\uc774\ub2e4.\nRANK["RX"] = 2.5      # PERMIT(3) \ubcf4\ub2e4 \uc57d\ud558\uace0 DECLARE(2) \ubcf4\ub2e4 \ubb34\uac81\ub2e4\n\n_RX_FIX = {\n    "melatonin": {\n        "GB": ("RX", "\ucc98\ubc29 \uc758\uc57d\ud488. \uc218\uc785 \ud5c8\uac00 \uc81c\ub3c4\ub294 \uc5c6\uace0 \ud604\uc9c0\uc5d0\uc11c \uc0ac\ub824\uba74 \uc601\uad6d \ucc98\ubc29\uc774 \ud544\uc694", False),\n        "DE": ("RX", "\uc6a9\ub7c9\uc5d0 \ub530\ub77c \ucc98\ubc29 \ub300\uc0c1. \uc218\uc785 \ud5c8\uac00 \uc81c\ub3c4\ub294 \uc5c6\uc74c", False)},\n}\nfor _k, _v in _RX_FIX.items():\n    NATIONAL.setdefault(_k, {}).update(_v)\n\n# \u2605national_rules() \uac00 NATIONAL \ub2e4\uc74c\uc5d0 NATIONAL_ONLY \ub97c \ub36e\uc5b4\uc4f4\ub2e4.\n#   \uc9c0\ub09c\ubc88 tramadol/AE \uc5d0\uc11c \ud55c\ucabd\ub9cc \ubcf4\uace0 \ub2f9\ud588\ub2e4. \uc591\ucabd\uc744 \ub9de\ucdb0 \ub454\ub2e4.\nfor _k, _v in _RX_FIX.items():\n    if _k in NATIONAL_ONLY:\n        for _cc, _r in _v.items():\n            if _cc in NATIONAL_ONLY[_k]:\n                NATIONAL_ONLY[_k][_cc] = _r\n'),
    ('canibring_v1.py',
     '\n\n# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\n# \u2605RX \ub4f1\uae09 \ud45c\uc2dc (2026-10-09). borderrx_v1 \uc758 RANK["RX"] \uc640 \uc9dd\uc774\ub2e4.\n#   \u2605\ub515\uc154\ub108\ub9ac\ub97c \uc21c\ud68c\ud558\ub294 \ucf54\ub4dc\uac00 \ud55c \uacf3\ub3c4 \uc5c6\ub294 \uac78 \ud655\uc778\ud558\uace0 \ud0a4\ub9cc \ub354\ud55c\ub2e4.\n#   \uc0c9\uc740 \ub9c8\uc820\ud0c0\ub2e4. \ube68\uac15\xb7\ud638\ubc15\xb7\ud30c\ub791\xb7\ubcf4\ub77c\xb7\ucd08\ub85d\uc774 \uc774\ubbf8 \uc4f0\uc600\uace0, \uc2ec\uac01\ub3c4 \ucd95\uc758\n#   \uc911\uac04\uc0c9\uc744 \uc4f0\uba74 \ud638\ubc15(PERMIT)\uacfc \ud5f7\uac08\ub9b0\ub2e4. RX \ub294 \'\ub354 \uc57d\ud55c \ud5c8\uac00\'\uac00 \uc544\ub2c8\ub77c\n#   \uc885\ub958\uac00 \ub2e4\ub978 \uc7a5\uc560\ubb3c\uc774\ub77c \uacc4\uc5f4\uc744 \ub2ec\ub9ac\ud558\ub294 \uac8c \ub9de\ub2e4.\nLV["RX"] = "Prescription required there"\nCOL["RX"] = "#e79ac9"\nDO["RX"] = ("There is no import permit to apply for. Bring your own supply with the "\n            "prescription and the original labelled packaging. The catch is at the other "\n            "end: a pharmacy there will not sell you more without a prescription written "\n            "in that country, so take enough for the whole trip.")\nKO_LV["RX"] = "\ud604\uc9c0\uc5d0\uc11c \ucc98\ubc29 \ub300\uc0c1\uc785\ub2c8\ub2e4"\nKO_DO["RX"] = ("\uc2e0\uccad\ud560 \uc218\uc785 \ud5c8\uac00 \uc81c\ub3c4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4. \ubcf8\uc778 \ucc98\ubc29\ubd84\uc744 \ucc98\ubc29\uc804\uacfc \uc6d0\ub798 \ub77c\ubca8\uc774 "\n               "\ubd99\uc740 \ud3ec\uc7a5 \uadf8\ub300\ub85c \uac00\uc838\uac00\uba74 \ub429\ub2c8\ub2e4. \ubb38\uc81c\ub294 \ub3c4\ucc29\ud55c \ub2e4\uc74c\uc785\ub2c8\ub2e4 \u2014 \ud604\uc9c0 "\n               "\uc57d\uad6d\uc740 \uadf8 \ub098\ub77c \uc758\uc0ac\uc758 \ucc98\ubc29 \uc5c6\uc774\ub294 \ub354 \ud314\uc9c0 \uc54a\uc73c\ubbc0\ub85c, \uc5ec\ud589 \uae30\uac04 \uc804\uccb4\uc5d0 "\n               "\uc4f8 \ub9cc\ud07c\uc744 \ucc59\uaca8 \uac00\uc138\uc694.")\n\n# \u2605_bridge \ub97c \uac10\uc2fc\ub2e4. \ubaa8\ub4c8 \uc804\uc5ed \uc774\ub984\uc744 \ub2e4\uc2dc \ubb36\uc73c\ubbc0\ub85c \uc774\ud6c4 \ud638\ucd9c\uc740 \uc774\ucabd\uc744 \ud0c4\ub2e4.\n#   \uc6d0\ubcf8\uc740 PERMIT/PROHIBITED \uc138 \uac08\ub798\ubfd0\uc774\ub77c RX \ub294 \uc544\ubb34 \ubc15\uc2a4\ub3c4 \ubabb \ubc1b\ub294\ub2e4.\n_bridge_before_rx = _bridge\n\n\ndef _bridge(lvl, cc, lang):\n    if lvl == "RX":\n        lurl = "/can-i-bring/doctors-letter" if lang == "en" else "/ko/\uc18c\uacac\uc11c"\n        if lang == "en":\n            return _BOX % ("#6b3a55", "#e79ac9",\n                           "Nothing to apply for &mdash; but you cannot buy it there either",\n                           \'<p style="margin:0">No permit exists for this one, so there is no \'\n                           \'paperwork to file before you fly. It is prescription-only at your \'\n                           \'destination, which means a pharmacy there will turn you away without \'\n                           \'a local prescription. Carry enough for the whole trip in the original \'\n                           \'labelled packaging, with your prescription and a prescriber&rsquo;s \'\n                           \'letter naming the generic ingredient. \'\n                           \'<a href="%s">Letter template</a>.</p>\' % lurl)\n        return _BOX % ("#6b3a55", "#e79ac9",\n                       "\uc2e0\uccad\ud560 \uac83\uc740 \uc5c6\uc9c0\ub9cc, \ud604\uc9c0\uc5d0\uc11c \uc0b4 \uc218\ub3c4 \uc5c6\ub2e4",\n                       \'<p style="margin:0">\uc774 \uc131\ubd84\uc5d0\ub294 \ud5c8\uac00 \uc81c\ub3c4\uac00 \uc5c6\uc5b4\uc11c \ucd9c\uad6d \uc804\uc5d0 \ub0bc \uc11c\ub958\uac00 \'\n                       \'\uc5c6\uc2b5\ub2c8\ub2e4. \ub300\uc2e0 \ub3c4\ucc29\uc9c0\uc5d0\uc11c \ucc98\ubc29 \ub300\uc0c1\uc774\ub77c \ud604\uc9c0 \uc57d\uad6d\uc740 \uadf8 \ub098\ub77c \ucc98\ubc29\uc804 \uc5c6\uc774 \'\n                       \'\ud314\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4. \uc5ec\ud589 \uae30\uac04 \uc804\uccb4\uc5d0 \uc4f8 \ubd84\ub7c9\uc744 \uc6d0\ub798 \ub77c\ubca8\uc774 \ubd99\uc740 \ud3ec\uc7a5 \uadf8\ub300\ub85c, \'\n                       \'\ucc98\ubc29\uc804\uacfc \uc131\ubd84 \uc77c\ubc18\uba85\uc744 \uc801\uc740 \uc18c\uacac\uc11c\uc640 \ud568\uaed8 \uac00\uc838\uac00\uc138\uc694. \'\n                       \'<a href="%s">\uc18c\uacac\uc11c \uc591\uc2dd</a>.</p>\' % lurl)\n    return _bridge_before_rx(lvl, cc, lang)\n'),
]

def die(m):
    sys.stdout.write("REFUSED: %s\n" % m); sys.exit(1)

tgt = os.getcwd()
files = []
for p, o, n in EDITS:
    if p not in files: files.append(p)
for p, t in APPENDS:
    if p not in files: files.append(p)

src = {}
for p in files:
    f = os.path.join(tgt, p)
    if not os.path.exists(f):
        die("%s not found in %s -- cd to the project dir first" % (p, tgt))
    src[p] = open(f, encoding="utf-8").read()

for mk in MARKERS:
    for p, s in src.items():
        if mk in s:
            die("already applied (marker %r in %s). nothing done." % (mk, p))

by = collections.OrderedDict()
for p, o, n in EDITS:
    by.setdefault(p, []).append((o, n))
cnt = 0
for p, pairs in by.items():
    for o, n in pairs:
        c = src[p].count(o)
        if c != 1:
            die("anchor count %d (expected 1) in %s for:\n---\n%s\n---" % (c, p, o[:200]))
        cnt += 1
sys.stdout.write("all %d anchors unique\n" % cnt)

out = dict(src)
for p, pairs in by.items():
    t = out[p]
    for o, n in pairs:
        t = t.replace(o, n, 1)
    out[p] = t
for p, t in APPENDS:
    out[p] = out[p].rstrip("\n") + "\n" + t

stamp = time.strftime("%Y%m%d-%H%M%S")
tmp = os.path.join(tgt, ".rx_tmp_" + stamp)
os.mkdir(tmp)
try:
    for p, text in out.items():
        t = os.path.join(tmp, os.path.basename(p))
        open(t, "w", encoding="utf-8").write(text)
        py_compile.compile(t, cfile=t + "c", doraise=True)
    sys.stdout.write("compile ok (%d files)\n" % len(out))
except Exception as e:
    shutil.rmtree(tmp, ignore_errors=True)
    die("compile failed, disk untouched: %s" % e)

try:
    for p, text in out.items():
        f = os.path.join(tgt, p)
        shutil.copy2(f, f + ".bak-" + stamp)
        open(f, "w", encoding="utf-8").write(text)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.stdout.write("WROTE ok\n")
for p in out:
    sys.stdout.write("  ~ %s (backup %s.bak-%s)\n" % (p, p, stamp))
