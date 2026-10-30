# -*- coding: utf-8 -*-
import re, sys, io, json, base64

def run(payload_b64, cb_path, brx_path):
    D = json.loads(__import__("gzip").decompress(base64.b64decode(payload_b64)).decode("utf-8"))
    cb  = io.open(cb_path,  encoding="utf-8").read()
    brx = io.open(brx_path, encoding="utf-8").read()
    if "_AE_FIX" in brx:
        print("STOP: already applied"); return 1
    if "_JP_FIX" not in brx:
        print("STOP: JP patch missing - wrong file state"); return 1

    split = "\nKO_WHY = {"
    if cb.count(split) != 1:
        print("STOP: KO_WHY anchor %d" % cb.count(split)); return 1
    head, tail = cb.split(split, 1); tail = split + tail

    def repl(block, ing, newtxt, label):
        pat = re.compile(r'\("' + ing + r'",\s*"AE"\):\s*"(?:[^"\\]|\\.)*"')
        n = len(pat.findall(block))
        if n != 1:
            print("STOP: %s/%s match=%d" % (label, ing, n)); return None
        return pat.sub(lambda m: '("%s", "AE"): %s' % (ing, json.dumps(newtxt, ensure_ascii=False)),
                       block, count=1)

    for ing, txt in D["EN_FIX"].items():
        head = repl(head, ing, txt, "WHY")
        if head is None: return 1
    for ing, txt in D["KO_FIX"].items():
        tail = repl(tail, ing, txt, "KO_WHY")
        if tail is None: return 1
    cb = head + tail

    blk = ["", "", "# AE verdicts corrected against the Emirates Drug Establishment list of",
           "#   controlled and semi-controlled medicines, published 2025-12-29 (content dated 2022-09-15).",
           "#   Only cannabis-class and a small prohibited set are barred; the rest are admissible",
           "#   with a prescription or an attested medical report, capped at the stay or three months.",
           "_AE_FIX = {"]
    for k, v in D["AE_FIX"].items():
        blk.append('    %s: (%s, %s, True),' % (json.dumps(k), json.dumps(v[0]),
                                                json.dumps(v[1], ensure_ascii=False)))
    blk += ["}", "for _k, _v in _AE_FIX.items():",
            '    NATIONAL.setdefault(_k, {})["AE"] = _v', ""]
    brx = brx.rstrip("\n") + "\n".join(blk) + "\n"

    compile(cb, "canibring_v1.py", "exec")
    compile(brx, "borderrx_v1.py", "exec")
    io.open(cb_path, "w", encoding="utf-8").write(cb)
    io.open(brx_path, "w", encoding="utf-8").write(brx)
    print("WROTE ok"); return 0

if __name__ == "__main__":
    sys.exit(run(sys.argv[1], "canibring_v1.py", "borderrx_v1.py"))
