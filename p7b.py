# -*- coding: utf-8 -*-
import io,shutil,sys
APPLY="--apply" in sys.argv
p="core.py"; s=io.open(p,encoding="utf-8").read()
if APPLY: shutil.copy(p,p+".bak7b")
R=[
('    # 답글4: 링크 + 고지문구 (모델이 쓴 한 줄 안내는 살린다)',
 '    # 답글5: 링크 + 고지문구 (모델이 쓴 한 줄 안내는 살린다)'),
('    r4 = f"{lead}\\n{deeplink}\\n\\n{DISCLOSURE}"',
 '    r5 = f"{lead}\\n{deeplink}\\n\\n{DISCLOSURE}"'),
('    # 답글5: 마무리 + 링크 + 해시태그 3개',
 '    # 답글6: 마무리 + 링크 + 해시태그 3개'),
('        # 답글4와 답글5가 같은 말이면 안 된다',
 '        # 답글5와 답글6이 같은 말이면 안 된다'),
('    r5 = f"{tail}\\n{deeplink}\\n\\n{hashtags}"\n\n    return rest + [r4, r5]',
 '    r6 = f"{tail}\\n{deeplink}\\n\\n{hashtags}"\n\n    return rest[:5] + [r5, r6]'),
('    # 본글·답글1~3 = 링크 없는 글 4개',
 '    # 본글·답글1~4 = 링크 없는 글 5개'),
('    while len(rest) < 4:\n        # 모자라면 가장 긴 글을 두 문장으로 쪼개서 채운다 (억지 생성 금지)',
 '    while len(rest) < 5:\n        # 모자라면 가장 긴 글을 두 문장으로 쪼개서 채운다 (억지 생성 금지)'),
('        if len(parts) < 2:\n            rest.append(rest[idx])\n            break',
 '        if len(parts) < 2:\n            rest.append("…")\n            break'),
('    rest = rest[:4]','    rest = rest[:5]'),
('    PLACEHOLDER = {"본글", "답글1", "답글2", "답글3", "답글4", "답글5",',
 '    PLACEHOLDER = {"본글", "답글1", "답글2", "답글3", "답글4", "답글5", "답글6",'),
('답글4: 밑에 링크.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글5: 원인 알고 나니까 허무하더라. 진작 바꿀걸.',
 '답글4: 베개 하나 바꾼 걸로 이렇게 될 줄은 몰랐고.\n답글5: 밑에 링크.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글6: 원인 알고 나니까 허무하더라. 진작 바꿀걸.'),
('답글4: 혹시 저 같은 분 계실까 봐 남겨둘게요.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글5: 그 작은 불안들이 쌓이는 게 육아더라고요.',
 '답글4: 물론 안 보고 자는 날도 있어요. 그것도 괜찮더라고요.\n답글5: 혹시 저 같은 분 계실까 봐 남겨둘게요.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글6: 그 작은 불안들이 쌓이는 게 육아더라고요.'),
('답글4: 밑에.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글5: 싼 거 여러 번 사는 게 결국 더 비쌌음.',
 '답글4: 뭐 목에 거는 게 다 좋다는 건 아니고, 무게는 좀 있음.\n답글5: 밑에.\\\\n{링크}\\\\n\\\\n(광고) 쿠팡파트너스 활동으로 수수료를 받습니다.\n답글6: 싼 거 여러 번 사는 게 결국 더 비쌌음.'),
('- 답글3까지 링크가 없다. 감정이 연결된 뒤 답글4에서 링크.',
 '- 답글4까지 링크가 없다. 감정이 연결된 뒤 답글5에서 링크. 링크는 답글5·6 두 곳뿐이다.'),
]
tot=0
for a,b in R:
    n=s.count(a); tot+=n
    print("%2d회  %s"%(n,a.strip().split("\n")[0][:58]))
    if n and APPLY: s=s.replace(a,b,1)
print("\n총 %d곳"%tot)
if APPLY:
    io.open(p,"w",encoding="utf-8").write(s)
    import py_compile; py_compile.compile(p,doraise=True); print("적용 완료")
else: print("[드라이런]")
