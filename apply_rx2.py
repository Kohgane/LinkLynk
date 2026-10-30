#!/usr/bin/env python3
# -*- coding: ascii -*-
# apply_rx2.py -- RX polish: KO wording + OG card row. Pure ASCII, idempotent.
import os, sys, py_compile, shutil, time, collections


EDITS = [
    ('canibring_v1.py',
     'KO_LV["RX"] = "\ud604\uc9c0\uc5d0\uc11c \ucc98\ubc29 \ub300\uc0c1\uc785\ub2c8\ub2e4"',
     '# \u2605"%s\uc5d0\uc11c %s" \ud15c\ud50c\ub9bf\uc5d0 \ub4e4\uc5b4\uac00\ubbc0\ub85c \uc5ec\uae30\uc11c \'\uc5d0\uc11c\'\ub85c \uc2dc\uc791\ud558\uba74 \uc870\uc0ac\uac00 \uacb9\uce5c\ub2e4.\n#   \uc2e4\uce21: "\uc601\uad6d\uc5d0\uc11c \ud604\uc9c0\uc5d0\uc11c \ucc98\ubc29 \ub300\uc0c1\uc785\ub2c8\ub2e4". \ub098\uba38\uc9c0 5\ub4f1\uae09\uacfc \uc5b4\ubbf8\ub97c \ub9de\ucd98\ub2e4.\nKO_LV["RX"] = "\ucc98\ubc29 \ub300\uc0c1 \uc758\uc57d\ud488\uc785\ub2c8\ub2e4"'),
    ('next_v1.py',
     '    for lab, arr, c in (("Banned / restricted", d.get("pro_en"), (255, 92, 80)),\n                        ("Permit required", d.get("per_en"), (240, 176, 76)),\n                        ("Must declare", d.get("dec_en"), (127, 182, 232))):',
     '    for lab, arr, c in (("Banned / restricted", d.get("pro_en"), (255, 92, 80)),\n                        ("Permit required", d.get("per_en"), (240, 176, 76)),\n                        # \u2605RX \uc904\uc774 \uc5c6\uc73c\uba74 \uc601\uad6d\xb7\ub3c5\uc77c\uc774 \uce74\ub4dc\uc5d0\uc11c \ud1b5\uc9f8\ub85c \uc0ac\ub77c\uc9c4\ub2e4.\n                        ("Prescription only", d.get("rx_en"), (231, 154, 201)),\n                        ("Must declare", d.get("dec_en"), (127, 182, 232))):'),
]

MARKERS = ['rx_en"), (231, 154, 201)']

def die(m):
    sys.stdout.write("REFUSED: %s\n" % m); sys.exit(1)

tgt = os.getcwd()
by = collections.OrderedDict()
for p, o, n in EDITS:
    by.setdefault(p, []).append((o, n))
src = {}
for p in by:
    f = os.path.join(tgt, p)
    if not os.path.exists(f):
        die("%s not found in %s -- cd to the project dir first" % (p, tgt))
    src[p] = open(f, encoding="utf-8").read()
for mk in MARKERS:
    for p, s in src.items():
        if mk in s:
            die("already applied (marker in %s). nothing done." % p)
cnt = 0
for p, pairs in by.items():
    for o, n in pairs:
        c = src[p].count(o)
        if c != 1:
            die("anchor count %d (expected 1) in %s for:\n---\n%s\n---" % (c, p, o[:200]))
        cnt += 1
sys.stdout.write("all %d anchors unique\n" % cnt)
out = {}
for p, pairs in by.items():
    t = src[p]
    for o, n in pairs:
        t = t.replace(o, n, 1)
    out[p] = t
stamp = time.strftime("%Y%m%d-%H%M%S")
tmp = os.path.join(tgt, ".rx2_tmp_" + stamp)
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
