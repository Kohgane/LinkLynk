# -*- coding: utf-8 -*-
"""IndexNow 키 파일을 새 도메인에서도 200 으로 내보낸다. ★앵커 1회 매치만."""
import io, sys
src = io.open("app.py", encoding="utf-8").read()
if "_KEEP" in src:
    print("이미 붙어 있다"); sys.exit(1)

A1 = '_BOTH = {"/robots.txt"}       # 호스트마다 제 내용을 낸다. 절대 안 넘긴다'
N1 = (A1 + '\n\n'
      '# ★IndexNow 키 파일은 양쪽 호스트가 각자 200 으로 내야 한다.\n'
      '#   제출한 URL 과 같은 호스트에서 키가 안 나오면 소유 증명 실패다.\n'
      '#   301 은 실패로 친다 — 도메인 옮기면서 조용히 끊겨 있었다.\n'
      'from canibring_v1 import INDEXNOW_KEY as _INKEY\n'
      '_KEEP = ("/%s.txt" % _INKEY,)')

A2 = ('        if p == "/":\n'
      '            return _cb_home()         # ★앱 UI 가 아니라 BorderRx 홈\n'
      '        if not _is_cb(p):')
N2 = ('        if p == "/":\n'
      '            return _cb_home()         # ★앱 UI 가 아니라 BorderRx 홈\n'
      '        if p in _KEEP:\n'
      '            return None               # 이 호스트가 직접 낸다\n'
      '        if not _is_cb(p):')

for tag, old, new in (("_KEEP 정의", A1, N1), ("CB 분기", A2, N2)):
    if src.count(old) != 1:
        print("실패: %s — %d회 매치" % (tag, src.count(old))); sys.exit(1)
    src = src.replace(old, new, 1); print("  OK %s" % tag)

io.open("app.py", "w", encoding="utf-8").write(src)
print("기록 완료")
