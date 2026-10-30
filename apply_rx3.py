#!/usr/bin/env python3
# -*- coding: ascii -*-
# apply_rx3.py -- KO OG card: add the RX row. Pure ASCII, idempotent.
import os, sys, py_compile, shutil, time, collections

EDITS = [
    ('next_v1.py',
     '    names = (d["pro"] + d["per"] + d["dec"])[:7]',
     '    # \u2605rx \ub97c \ube7c\uba74 \ud55c\uae00 OG \uce74\ub4dc\uc5d0\uc11c \uc601\uad6d\xb7\ub3c5\uc77c\uc774 \ud1b5\uc9f8\ub85c \uc0ac\ub77c\uc9c4\ub2e4(2026-10-09 \uc2e4\uce21).\n    #   .get \uc744 \uc4f0\ub294 \uc774\uc720: \ubc30\ud3ec \uc804 \ucaa8\uc2dc dict \uc5d0\ub294 rx \ud0a4\uac00 \uc5c6\ub2e4.\n    names = (d["pro"] + d["per"] + d.get("rx", []) + d["dec"])[:7]'),
    ('next_v1.py',
     '    lab = [("\ubc18\uc785 \ubd88\uac00", d["pro"], (255, 92, 80)),\n           ("\uc0ac\uc804 \ud5c8\uac00", d["per"], (240, 176, 76)),\n           ("\uc2e0\uace0 \ub300\uc0c1", d["dec"], (127, 182, 232))]',
     '    lab = [("\ubc18\uc785 \ubd88\uac00", d["pro"], (255, 92, 80)),\n           ("\uc0ac\uc804 \ud5c8\uac00", d["per"], (240, 176, 76)),\n           # \u2605\ub9c8\uc820\ud0c0 = COL["RX"] #e79ac9. \ub4f1\uae09 \uc21c\uc11c\ub300\ub85c \ud5c8\uac00 \ub2e4\uc74c, \uc2e0\uace0 \uc55e\uc774\ub2e4.\n           ("\ud604\uc9c0 \ucc98\ubc29", d.get("rx", []), (231, 154, 201)),\n           ("\uc2e0\uace0 \ub300\uc0c1", d["dec"], (127, 182, 232))]'),
]

MARKERS = ['d.get("rx", []) + d["dec"]']

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
tmp = os.path.join(tgt, ".rx3_tmp_" + stamp)
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
