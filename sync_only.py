import io
p = "borderrx_v1.py"
s = io.open(p, encoding="utf-8").read()
if "_SYNC_ONLY" in s:
    print("STOP: already applied"); raise SystemExit(1)
if "_JP_FIX" not in s or "_AE_FIX" not in s:
    print("STOP: prior patches missing"); raise SystemExit(1)
blk = '''

# national_rules() merges NATIONAL_ONLY after NATIONAL, so NATIONAL_ONLY wins.
# Mirror the corrections into it so the two tables cannot disagree.
_SYNC_ONLY = (("JP", _JP_FIX), ("AE", _AE_FIX))
for _cc, _fx in _SYNC_ONLY:
    for _k, _v in _fx.items():
        if _k in NATIONAL_ONLY and _cc in NATIONAL_ONLY[_k]:
            NATIONAL_ONLY[_k][_cc] = _v
'''
s = s.rstrip("\n") + "\n" + blk
compile(s, p, "exec")
io.open(p, "w", encoding="utf-8").write(s)
print("WROTE ok")
