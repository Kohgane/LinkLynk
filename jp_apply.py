# -*- coding: utf-8 -*-
import re, sys, io, json, base64

def run(payload_b64, cb_path, brx_path):
    D = json.loads(__import__("gzip").decompress(base64.b64decode(payload_b64)).decode("utf-8"))
    cb  = io.open(cb_path,  encoding="utf-8").read()
    brx = io.open(brx_path, encoding="utf-8").read()

    if "_JP_FIX" in brx or '("Concerta", "JP")' in cb:
        print("STOP: already applied"); return 1

    split = "\nKO_WHY = {"
    if cb.count(split) != 1:
        print("STOP: KO_WHY anchor %d" % cb.count(split)); return 1
    head, tail = cb.split(split, 1); tail = split + tail

    def repl(block, ing, newtxt, label):
        pat = re.compile(r'\("' + ing + r'",\s*"JP"\):\s*"(?:[^"\\]|\\.)*"')
        n = len(pat.findall(block))
        if n != 1:
            print("STOP: %s/%s match=%d" % (label, ing, n)); return None
        return pat.sub(lambda m: '("%s", "JP"): %s' % (ing, json.dumps(newtxt, ensure_ascii=False)),
                       block, count=1)

    for ing, txt in D["EN_FIX"].items():
        head = repl(head, ing, txt, "WHY")
        if head is None: return 1
    for ing, txt in D["KO_FIX"].items():
        tail = repl(tail, ing, txt, "KO_WHY")
        if tail is None: return 1

    a = "\nWHY = {\n"
    if head.count(a) != 1:
        print("STOP: WHY anchor %d" % head.count(a)); return 1
    ins = "".join('    ("%s", "JP"): %s,\n' % (k, json.dumps(v, ensure_ascii=False))
                  for k, v in D["EN_NEW"].items())
    head = head.replace(a, a + ins, 1)

    ap = '    ("melatonin", "GB"), ("melatonin", "DE"),\n]'
    if head.count(ap) != 1:
        print("STOP: PAIRS anchor %d" % head.count(ap)); return 1
    newp = "".join('    ("%s", "%s"),\n' % (d, c) for d, c in D["NEW_PAIRS"])
    head = head.replace(ap, '    ("melatonin", "GB"), ("melatonin", "DE"),\n' + newp + ']', 1)

    cb = head + tail

    blk = ["", "", "# JP verdicts corrected. Sources: MHLW personal-import notice,",
           "#   NCD Controlled Substances List 2024-12-12. N=narcotic SRM=stimulant raw material P=psychotropic.",
           "#   The import/export ban mark applies to amphetamine only.",
           "_JP_FIX = {"]
    for k, v in D["JP_FIX"].items():
        blk.append('    %s: (%s, %s, True),' % (json.dumps(k), json.dumps(v[0]),
                                                json.dumps(v[1], ensure_ascii=False)))
    blk += ["}", "for _k, _v in _JP_FIX.items():",
            '    NATIONAL.setdefault(_k, {})["JP"] = _v', ""]
    brx = brx.rstrip("\n") + "\n".join(blk) + "\n"

    compile(cb, "canibring_v1.py", "exec")
    compile(brx, "borderrx_v1.py", "exec")
    io.open(cb_path, "w", encoding="utf-8").write(cb)
    io.open(brx_path, "w", encoding="utf-8").write(brx)
    print("WROTE ok")
    return 0

if __name__ == "__main__":
    sys.exit(run(sys.argv[1], "canibring_v1.py", "borderrx_v1.py"))
