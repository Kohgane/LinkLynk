# -*- coding: utf-8 -*-
"""BorderRx 데이터 빌더 — INCB Yellow/Green List PDF → data/incb_db.json
   월 1회 크론 권장. 소스가 갱신되면 판정도 따라 갱신된다."""
import re, os, json, sys, requests, pdfplumber

UA = {"User-Agent": "BorderRx/1.0 (+https://linklynk.onrender.com/rx)"}
BASE = "https://www.incb.org"
IDX = {
    "narcotic": "/incb/en/narcotic-drugs/Yellowlist/yellow-list.html",
    "psychotropic": "/incb/en/psychotropics/green-list.html",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def find_pdf(kind):
    h = requests.get(BASE + IDX[kind], headers=UA, timeout=40).text
    cands = re.findall(r'href="(/[^"]+\.pdf)"', h)
    if kind == "psychotropic":
        for c in cands:
            if re.search(r'greenlist', c, re.I) and c.endswith("E.pdf"):
                return BASE + c
    for c in cands:
        if re.search(r'YL_|yellow', c, re.I):
            return BASE + c
    return BASE + cands[0] if cands else None

def parse(path, kind):
    rows = {}
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for ln in (pg.extract_text() or "").split("\n"):
                m = re.match(r'^([A-Z]{2}\s?\d{3})\s+(\d{2,7}-\d{2}-\d)\s+(.+)$', ln.strip())
                if not m:
                    continue
                ids, cas, rest = m.group(1).replace(" ", ""), m.group(2), m.group(3)
                toks = rest.split()
                name = []
                for w in toks:
                    if re.match(r"^[A-Z][A-Za-z\-\u2019(),0-9]*$", w) and not re.match(r"^\d", w):
                        name.append(w)
                    else:
                        break
                nm = " ".join(name).strip(" ,")
                if len(nm) < 3:
                    nm = toks[0]
                rows[cas] = {"ids": ids, "cas": cas, "name": nm,
                             "inn": nm.lower().strip(" ,"), "list": kind}
    return rows

def main():
    os.makedirs(OUT, exist_ok=True)
    db = {}
    for kind in IDX:
        url = find_pdf(kind)
        if not url:
            print("[!] %s pdf 링크 못 찾음" % kind); continue
        p = os.path.join(OUT, kind + ".pdf")
        db_bytes = requests.get(url, headers=UA, timeout=90).content
        open(p, "wb").write(db_bytes)
        got = parse(p, kind)
        print("%-13s %s -> %d종" % (kind, url.split("/")[-1], len(got)))
        db.update(got)
    recs = sorted(db.values(), key=lambda x: x["inn"])
    json.dump(recs, open(os.path.join(OUT, "incb_db.json"), "w"), ensure_ascii=False, indent=0)
    print("총 %d종 저장 -> data/incb_db.json" % len(recs))
    return 0 if len(recs) > 150 else 1

if __name__ == "__main__":
    sys.exit(main())
