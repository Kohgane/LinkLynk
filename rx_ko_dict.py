# -*- coding: utf-8 -*-
"""한국 상비약·처방약 한글명 → 영문 성분 매핑.
   RxNav 는 영문 DB라 한글을 못 읽고, 폴백이 입력을 그대로 성분으로 써서
   오판정을 만든다(애더럴 -> citrate 실측). 이 표가 그 구멍을 막는다.
   ※ 성분은 대표 성분 위주. 제품마다 함량·복합 구성이 다르므로 참고용이다.
"""
KO_DRUG = {
    # 해열·진통
    "타이레놀": ["acetaminophen"],
    "타이레놀이알": ["acetaminophen"],
    "게보린": ["acetaminophen", "isopropylantipyrine", "caffeine"],
    "펜잘": ["acetaminophen", "ethenzamide", "caffeine"],
    "사리돈": ["acetaminophen", "isopropylantipyrine", "caffeine"],
    "이지엔6": ["ibuprofen"],
    "부루펜": ["ibuprofen"],
    "탁센": ["naproxen"],
    "낙센": ["naproxen"],
    "아스피린": ["aspirin"],
    "울트라셋": ["tramadol", "acetaminophen"],
    "트리돌": ["tramadol"],
    "타진": ["oxycodone", "naloxone"],
    "옥시콘틴": ["oxycodone"],
    "듀로제식": ["fentanyl"],
    "코데원": ["codeine"],
    # 감기·기침·콧물
    "판콜": ["acetaminophen", "chlorpheniramine", "dl-methylephedrine"],
    "판피린": ["acetaminophen", "chlorpheniramine", "dl-methylephedrine"],
    "콜대원": ["acetaminophen", "dextromethorphan", "pseudoephedrine"],
    "테라플루": ["acetaminophen", "pheniramine", "phenylephrine"],
    "화이투벤": ["acetaminophen", "chlorpheniramine", "pseudoephedrine"],
    "코푸시럽": ["dihydrocodeine", "chlorpheniramine", "dl-methylephedrine"],
    "러미라": ["dextromethorphan"],
    "슈다페드": ["pseudoephedrine"],
    "액티피드": ["pseudoephedrine", "triprolidine"],
    "지르텍": ["cetirizine"],
    "클라리틴": ["loratadine"],
    "알레그라": ["fexofenadine"],
    "베나드릴": ["diphenhydramine"],
    # 수면·신경
    "졸피뎀": ["zolpidem"],
    "스틸녹스": ["zolpidem"],
    "졸피드": ["zolpidem"],
    "자낙스": ["alprazolam"],
    "알프람": ["alprazolam"],
    "바리움": ["diazepam"],
    "디아제팜": ["diazepam"],
    "아티반": ["lorazepam"],
    "리보트릴": ["clonazepam"],
    "할시온": ["triazolam"],
    "멜라토닌": ["melatonin"],
    "서카딘": ["melatonin"],
    # ADHD·각성
    "애더럴": ["dextroamphetamine", "amfetamine"],
    "아데랄": ["dextroamphetamine", "amfetamine"],
    "콘서타": ["methylphenidate"],
    "메디키넷": ["methylphenidate"],
    "페니드": ["methylphenidate"],
    "스트라테라": ["atomoxetine"],
    "모다피닐": ["modafinil"],
    "프로비질": ["modafinil"],
    # 소화기
    "겔포스": ["aluminum hydroxide", "magnesium hydroxide"],
    "베아제": ["pancreatin"],
    "훼스탈": ["pancreatin"],
    "가스활명수": ["ursodeoxycholic acid"],
    "부스코판": ["scopolamine butylbromide"],
    "로페라미드": ["loperamide"],
    "스멕타": ["diosmectite"],
    "넥시움": ["esomeprazole"],
    "란스톤": ["lansoprazole"],
    # 근이완·기타
    "에페리손": ["eperisone"],
    "무코스타": ["rebamipide"],
    "트라스트": ["piroxicam"],
    "케토톱": ["ketoprofen"],
    "제일쿨파스": ["methyl salicylate"],
    "안티푸라민": ["methyl salicylate", "menthol"],
    # 대마·기타 통제
    "cbd오일": ["cannabidiol"],
    "씨비디": ["cannabidiol"],
    "대마오일": ["cannabidiol"],
    # 여행자 다빈도
    "인사돌": ["hydroxyapatite"],
    "이가탄": ["lysozyme"],
    "우루사": ["ursodeoxycholic acid"],
    "아로나민": ["fursultiamine"],
    "센트룸": ["multivitamin"],
    "컨디션": ["taurine"],
    "박카스": ["taurine"],
}


def norm_ko(s):
    return "".join((s or "").split()).lower().replace("-", "").replace("·", "")


_IDX = {norm_ko(k): v for k, v in KO_DRUG.items()}


def lookup_ko(name):
    """한글 약명 -> 영문 성분 리스트. 없으면 빈 리스트."""
    q = norm_ko(name)
    if not q:
        return []
    if q in _IDX:
        return list(_IDX[q])
    # 부분 일치: '타이레놀500' '게보린정' 같은 변형 흡수
    for k, v in _IDX.items():
        if len(k) >= 3 and (k in q or q in k):
            return list(v)
    return []
