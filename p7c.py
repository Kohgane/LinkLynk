# -*- coding: utf-8 -*-
import io,shutil,sys
APPLY="--apply" in sys.argv
p="core.py"; s=io.open(p,encoding="utf-8").read()
if APPLY: shutil.copy(p,p+".bakg")
OLD='    # 개수·링크위치·고지문구는 repair_structure()가 코드로 보장한다 → 모델에게 시키지 않는다.'
NEW = '''    # ★최종 안전망 — repair_structure() 결과를 믿지 않고 한 번 더 검사한다.
    #  정보글 모드(링크·고지 둘 다 없음)는 링크 검사 전체를 건너뛴다.
    _L = "link.coupang.com"
    _all = "\\n".join(str(x) for x in posts)
    _INFO = (_L not in _all) and ("수수료" not in _all)
    if not _INFO:
        if len(posts) != 7:
            fails.append("블록이 %d개다. 본글+답글6 = 7개여야 한다." % len(posts))
        for _i, _t in enumerate(posts[:5]):
            if _L in str(_t):
                fails.append(("본글" if _i == 0 else "답글%d" % _i) + "에 링크가 있다. 링크는 답글5·6에만 넣어라.")
        _n = sum(1 for _t in posts if _L in str(_t))
        if _n > 2:
            fails.append("링크가 %d개다. 글당 최대 2개다." % _n)
        if _n == 0:
            fails.append("링크가 하나도 없다.")
        if len(posts) >= 6 and "수수료를 받습니다" not in str(posts[5]):
            fails.append("답글5에 공정위 고지문구가 없다.")

    # 개수·링크위치·고지문구는 repair_structure()가 코드로 보장한다 → 모델에게 시키지 않는다.'''
n=s.count(OLD); print("앵커 %d회"%n)
if n and APPLY:
    s=s.replace(OLD,NEW,1)
    io.open(p,"w",encoding="utf-8").write(s)
    import py_compile; py_compile.compile(p,doraise=True)
    print("적용 + 문법검사 통과")
elif not APPLY: print("[드라이런]")
