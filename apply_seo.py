#!/usr/bin/env python3
# -*- coding: ascii -*-
# apply_seo.py -- self-contained, pure ASCII, multi-file, idempotent.
# Korean comment text is \uXXXX escaped so no terminal can mangle it.
import os, sys, py_compile, shutil, time, collections

MARKER = "_SLASH_CB"

EDITS = [
    ('app.py',
     '_STAY = ("/next/card", "/next/og")',
     '_STAY = ("/next/card", "/next/og")\n\n# \u2605\uc2ac\ub798\uc2dc \uc30d\ub465\uc774. \ub450 \uc8fc\uc18c\uac00 \uac19\uc740 \ubc14\uc774\ud2b8\ub97c \ub0b4\ub294\ub370 canonical \uc774 \uc5c6\uc5b4\n#   \uad6c\uae00\uc774 "\ud45c\uc900 \uc5c6\ub294 \uc911\ubcf5"\uc73c\ub85c \ubc84\ub838\ub2e4(2026-10-07 GSC \uc54c\ub9bc).\n#   canonical \ud0dc\uadf8\ubcf4\ub2e4 301 \uc774 \uac15\ud55c \uc2e0\ud638\ub2e4. \ud638\uc2a4\ud2b8\ubcc4\ub85c \ub098\ub220 \ub450 \ubc88 \ud280\uae30\ub294 \uac78 \ub9c9\ub294\ub2e4.\n#   \u2605\uc804\uc5ed \uaddc\uce59\uc73c\ub85c \uc548 \ud558\ub294 \uc774\uc720: Flask \uac00 \'/foo/\' \ub85c \ub4f1\ub85d\ud55c \ub77c\uc6b0\ud2b8\ub294\n#   \'/foo\' \ub97c \'/foo/\' \ub85c 308 \ubcf4\ub0b8\ub2e4. \uac70\uae30\uc5d0 \ubc18\ub300 301 \uc744 \uac78\uba74 \ubb34\ud55c \ub8e8\ud504\ub2e4.\n#   \uc544\ub798\ub294 \uc2e4\uce21\uc73c\ub85c \uc591\ucabd \ub2e4 200 \uc778 \uac83\ub9cc \uba85\uc2dc\ud55c\ub2e4.\n_SLASH_CB  = {"/next/": "/next", "/next/en/": "/next/en"}\n_SLASH_APP = {"/gottago/": "/gottago", "/eats/": "/eats",\n              "/majak/": "/majak", "/hwatu/": "/hwatu"}'),
    ('app.py',
     '        if p == "/":\n            return _cb_home()         # \u2605\uc571 UI \uac00 \uc544\ub2c8\ub77c BorderRx \ud648',
     '        if p == "/":\n            return _cb_home()         # \u2605\uc571 UI \uac00 \uc544\ub2c8\ub77c BorderRx \ud648\n        if p in _SLASH_CB:\n            return _rd(_to(CB_HOST, _SLASH_CB[p]), 301)'),
    ('app.py',
     '        if p in _BOTH or p == "/" or p.startswith(_STAY):\n            return None',
     '        if p in _BOTH or p == "/" or p.startswith(_STAY):\n            return None\n        if p in _SLASH_APP:\n            return _rd(_to(APP_HOST, _SLASH_APP[p]), 301)'),
    ('app.py',
     '    urls = ["https://linklynk.onrender.com/boim",\n            "https://linklynk.onrender.com/boim/guide"]',
     '    # \u2605\uc571 \ub79c\ub529 4\uc7a5\uc744 \ub123\ub294\ub2e4. \uc9c0\uae08\uae4c\uc9c0 \uc5b4\ub290 \uc0ac\uc774\ud2b8\ub9f5\uc5d0\ub3c4 \uc5c6\uc5c8\ub2e4.\n    #   gottago/eats \ub294 canibringmeds \uc5ec\ud589 \uc0ac\uc774\ud2b8\ub9f5\uc5d0 \uc788\uc5c8\uc9c0\ub9cc \uac70\uae30\uc120 301 \ub41c\ub2e4.\n    #   TWA assetlinks \uac00 \uc774 \ud638\uc2a4\ud2b8\uc5d0\ub9cc \uc788\uc73c\ubbc0\ub85c \ud398\uc774\uc9c0\ub294 \uc5ec\uae30 \ub0a8\uae34\ub2e4.\n    urls = ["https://linklynk.onrender.com/boim",\n            "https://linklynk.onrender.com/boim/guide",\n            "https://linklynk.onrender.com/gottago",\n            "https://linklynk.onrender.com/eats",\n            "https://linklynk.onrender.com/majak",\n            "https://linklynk.onrender.com/hwatu"]'),
    ('canibring_v1.py',
     '    urls = ["%s/next/en" % BASE, "%s/can-i-bring" % BASE,\n            "%s/gottago/" % BASE, "%s/eats/" % BASE]',
     '    # \u2605gottago/eats \ub97c \ube80\ub2e4. \uc774 \ud638\uc2a4\ud2b8\uc5d0\uc120 linklynk \ub85c 301 \ub418\ubbc0\ub85c\n    #   \uc0ac\uc774\ud2b8\ub9f5\uc774 \ud295\uae30\ub294 \uc8fc\uc18c\ub97c \uad11\uace0\ud558\ub294 \uaf34\uc774\uc5c8\ub2e4. \uc800\ucabd \uc0ac\uc774\ud2b8\ub9f5\uc73c\ub85c \uc62e\uacbc\ub2e4.\n    urls = ["%s/next/en" % BASE, "%s/can-i-bring" % BASE]'),
]

def die(m):
    sys.stdout.write("REFUSED: %s\n" % m); sys.exit(1)

tgt = os.getcwd()
by = collections.OrderedDict()
for path, old, new in EDITS:
    by.setdefault(path, []).append((old, new))

src = {}
for path in by:
    f = os.path.join(tgt, path)
    if not os.path.exists(f):
        die("%s not found in %s -- cd to the project dir first" % (path, tgt))
    src[path] = open(f, encoding="utf-8").read()

if any(MARKER in s for s in src.values()):
    die("already applied (marker present). nothing done.")

n = 0
for path, pairs in by.items():
    for old, new in pairs:
        c = src[path].count(old)
        if c != 1:
            die("anchor count %d (expected 1) in %s for:\n---\n%s\n---"
                % (c, path, old[:160]))
        n += 1
sys.stdout.write("all %d anchors unique across %d files\n" % (n, len(by)))

out = {}
for path, pairs in by.items():
    t = src[path]
    for old, new in pairs:
        t = t.replace(old, new, 1)
    out[path] = t

stamp = time.strftime("%Y%m%d-%H%M%S")
tmp = os.path.join(tgt, ".seo_tmp_" + stamp)
os.mkdir(tmp)
try:
    for path, text in out.items():
        t = os.path.join(tmp, os.path.basename(path))
        open(t, "w", encoding="utf-8").write(text)
        py_compile.compile(t, cfile=t + "c", doraise=True)
    sys.stdout.write("compile ok (%d files)\n" % len(out))
except Exception as e:
    shutil.rmtree(tmp, ignore_errors=True)
    die("compile failed, disk untouched: %s" % e)

try:
    for path, text in out.items():
        f = os.path.join(tgt, path)
        shutil.copy2(f, f + ".bak-" + stamp)
        open(f, "w", encoding="utf-8").write(text)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.stdout.write("WROTE ok\n")
for path in out:
    sys.stdout.write("  ~ %s (backup %s.bak-%s)\n" % (path, path, stamp))
