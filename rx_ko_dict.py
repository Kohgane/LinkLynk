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
    # 부분 일치 — '긴 키 우선'. 짧은 키가 긴 키를 가로채는 걸 막는다
    # ('코데인'이 '디히드로코데인'을, '에페드린'이 '슈도에페드린'을 먹던 버그)
    best = None
    for k, v in _IDX.items():
        if len(k) < 2:
            continue
        if k in q or q in k:
            if best is None or len(k) > len(best[0]):
                best = (k, v)
    return list(best[1]) if best else []

# ── 확장분 (상비약·처방약 다빈도)
KO_DRUG.update({
    "타이레놀콜드": ["acetaminophen", "chlorpheniramine", "dextromethorphan"],
    "챔프": ["acetaminophen"],
    "콜대원키즈": ["acetaminophen", "dextromethorphan"],
    "어린이부루펜": ["ibuprofen"],
    "맥시부펜": ["dexibuprofen"],
    "이부프로펜": ["ibuprofen"],
    "아세트아미노펜": ["acetaminophen"],
    "덱시부프로펜": ["dexibuprofen"],
    "쎄레브렉스": ["celecoxib"],
    "아렉스": ["acetaminophen", "chlorpheniramine"],
    "신신파스": ["methyl salicylate"],
    "제놀": ["ketoprofen"],
    "페인엔젤": ["naproxen"],
    "이지엔6프로": ["dexibuprofen"],
    "탁센이브": ["ibuprofen"],
    "비겐": ["dimenhydrinate"],
    "키미테": ["scopolamine"],
    "토스롱": ["dextromethorphan"],
    "미놀": ["dextromethorphan"],
    "브론": ["dihydrocodeine", "dl-methylephedrine"],
    "코데날": ["dihydrocodeine"],
    "지노콜": ["dihydrocodeine"],
    "뮤코펙트": ["ambroxol"],
    "리나치올": ["carbocisteine"],
    "스토가": ["famotidine"],
    "잔탁": ["ranitidine"],
    "개비스콘": ["sodium alginate"],
    "알마겔": ["almagate"],
    "포타겔": ["dioctahedral smectite"],
    "정로환": ["berberine"],
    "백초시럽": ["berberine"],
    "이모듐": ["loperamide"],
    "둘코락스": ["bisacodyl"],
    "마그밀": ["magnesium hydroxide"],
    "아락실": ["plantago ovata"],
    "타이록신": ["levothyroxine"],
    "씬지로이드": ["levothyroxine"],
    "쿠에타핀": ["quetiapine"],
    "쎄로켈": ["quetiapine"],
    "렉사프로": ["escitalopram"],
    "졸로푸트": ["sertraline"],
    "프로작": ["fluoxetine"],
    "자이프렉사": ["olanzapine"],
    "인데놀": ["propranolol"],
    "트라젠타": ["linagliptin"],
    "메트포르민": ["metformin"],
    "리피토": ["atorvastatin"],
    "크레스토": ["rosuvastatin"],
    "아모잘탄": ["amlodipine", "losartan"],
    "노바스크": ["amlodipine"],
    "비아그라": ["sildenafil"],
    "시알리스": ["tadalafil"],
    "프로페시아": ["finasteride"],
    "미녹시딜": ["minoxidil"],
    "타미플루": ["oseltamivir"],
    "조플루자": ["baloxavir"],
    "항생제아목시실린": ["amoxicillin"],
    "오구멘틴": ["amoxicillin", "clavulanate"],
    "지스로맥스": ["azithromycin"],
    "에피펜": ["epinephrine"],
    "벤토린": ["salbutamol"],
    "심비코트": ["budesonide", "formoterol"],
    "니코레트": ["nicotine"],
    "챔픽스": ["varenicline"],
    "보나링": ["dimenhydrinate"],
})
_IDX = {norm_ko(k): v for k, v in KO_DRUG.items()}

# ── 한글 성분명 ──────────────────────────────────────────────────
# 상품명만 있어서 '코데인' '트라마돌' 같은 성분명 검색이 전부 빈손이었다.
# 여행객은 상품명과 성분명을 둘 다 검색한다.
KO_DRUG.update({
    # 마약성 진통
    "코데인": ["codeine"], "디히드로코데인": ["dihydrocodeine"],
    "하이드로코돈": ["hydrocodone"], "옥시코돈": ["oxycodone"],
    "모르핀": ["morphine"], "펜타닐": ["fentanyl"],
    "트라마돌": ["tramadol"], "부프레노르핀": ["buprenorphine"],
    "메타돈": ["methadone"], "메사돈": ["methadone"],
    "페티딘": ["pethidine"], "케타민": ["ketamine"],
    # 각성제·ADHD
    "암페타민": ["amphetamine"], "덱스트로암페타민": ["dextroamphetamine"],
    "리스덱스암페타민": ["lisdexamfetamine"], "메틸페니데이트": ["methylphenidate"],
    "모다피닐": ["modafinil"], "아르모다피닐": ["armodafinil"],
    "아토목세틴": ["atomoxetine"],
    # 수면·항불안
    "졸피뎀": ["zolpidem"], "조피클론": ["zopiclone"],
    "에스조피클론": ["eszopiclone"], "트리아졸람": ["triazolam"],
    "알프라졸람": ["alprazolam"], "디아제팜": ["diazepam"],
    "로라제팜": ["lorazepam"], "클로나제팜": ["clonazepam"],
    "에티졸람": ["etizolam"], "멜라토닌": ["melatonin"],
    # 항우울·정신
    "설트랄린": ["sertraline"], "에스시탈로프람": ["escitalopram"],
    "플루옥세틴": ["fluoxetine"], "파록세틴": ["paroxetine"],
    "부프로피온": ["bupropion"], "미르타자핀": ["mirtazapine"],
    "쿠에티아핀": ["quetiapine"], "올란자핀": ["olanzapine"],
    "아리피프라졸": ["aripiprazole"], "가바펜틴": ["gabapentin"],
    "프레가발린": ["pregabalin"],
    # 감기·기침·콧물
    "슈도에페드린": ["pseudoephedrine"], "에페드린": ["ephedrine"],
    "메틸에페드린": ["dl-methylephedrine"],
    "덱스트로메토르판": ["dextromethorphan"], "구아이페네신": ["guaifenesin"],
    "페닐에프린": ["phenylephrine"], "독실아민": ["doxylamine"],
    # 항히스타민
    "로라타딘": ["loratadine"], "세티리진": ["cetirizine"],
    "레보세티리진": ["levocetirizine"], "펙소페나딘": ["fexofenadine"],
    "클로르페니라민": ["chlorpheniramine"], "디펜히드라민": ["diphenhydramine"],
    "에바스틴": ["ebastine"],
    # 해열·진통·소염
    "아세트아미노펜": ["acetaminophen"], "아세타미노펜": ["acetaminophen"],
    "파라세타몰": ["acetaminophen"], "이부프로펜": ["ibuprofen"],
    "덱시부프로펜": ["dexibuprofen"], "나프록센": ["naproxen"],
    "디클로페낙": ["diclofenac"], "셀레콕시브": ["celecoxib"],
    "아세클로페낙": ["aceclofenac"],
    # 위장
    "오메프라졸": ["omeprazole"], "에스오메프라졸": ["esomeprazole"],
    "란소프라졸": ["lansoprazole"], "판토프라졸": ["pantoprazole"],
    "파모티딘": ["famotidine"], "로페라미드": ["loperamide"],
    "돔페리돈": ["domperidone"], "메토클로프라미드": ["metoclopramide"],
    # 멀미
    "스코폴라민": ["scopolamine"], "디멘히드리네이트": ["dimenhydrinate"],
    "메클리진": ["meclizine"],
    # 순환·대사
    "프로프라놀롤": ["propranolol"], "암로디핀": ["amlodipine"],
    "로사르탄": ["losartan"], "아토르바스타틴": ["atorvastatin"],
    "로수바스타틴": ["rosuvastatin"], "레보티록신": ["levothyroxine"],
    # 항생·항바이러스·항말라리아
    "아목시실린": ["amoxicillin"], "아지트로마이신": ["azithromycin"],
    "시프로플록사신": ["ciprofloxacin"], "레보플록사신": ["levofloxacin"],
    "독시사이클린": ["doxycycline"], "세프트리악손": ["ceftriaxone"],
    "오셀타미비르": ["oseltamivir"], "메플로퀸": ["mefloquine"],
    "하이드록시클로로퀸": ["hydroxychloroquine"], "아토바쿠온": ["atovaquone"],
    # 호르몬·기타
    "테스토스테론": ["testosterone"], "에스트라디올": ["estradiol"],
    "프레드니솔론": ["prednisolone"], "덱사메타손": ["dexamethasone"],
    "실데나필": ["sildenafil"], "타다라필": ["tadalafil"],
    "바르데나필": ["vardenafil"], "피나스테리드": ["finasteride"],
    "이소트레티노인": ["isotretinoin"], "니코틴": ["nicotine"],
    "카페인": ["caffeine"], "칸나비디올": ["cannabidiol"],
    "테트라하이드로칸나비놀": ["tetrahydrocannabinol"],
    # 해외 브랜드 한글 표기 — 여행객이 이 이름으로 검색한다
    "애드빌": ["ibuprofen"], "애드빌피엠": ["ibuprofen", "diphenhydramine"],
    "모트린": ["ibuprofen"], "알리브": ["naproxen"],
    "타이레놀피엠": ["acetaminophen", "diphenhydramine"],
    "니퀼": ["acetaminophen", "dextromethorphan", "doxylamine"],
    "데이퀼": ["acetaminophen", "dextromethorphan", "phenylephrine"],
    "베나드릴": ["diphenhydramine"], "클라리틴": ["loratadine"],
    "지르텍": ["cetirizine"], "알레그라": ["fexofenadine"],
    "수다페드": ["pseudoephedrine"], "슈다페드": ["pseudoephedrine"],
    "뮤시넥스": ["guaifenesin", "dextromethorphan"],
    "리탈린": ["methylphenidate"], "콘서타": ["methylphenidate"],
    "바이반스": ["lisdexamfetamine"], "자낙스": ["alprazolam"],
    "앰비엔": ["zolpidem"], "발륨": ["diazepam"], "아티반": ["lorazepam"],
    "퍼코셋": ["oxycodone", "acetaminophen"],
    "바이코딘": ["hydrocodone", "acetaminophen"],
    "울트람": ["tramadol"], "드라마민": ["dimenhydrinate"],
    "펩시드": ["famotidine"], "이모디움": ["loperamide"],
    "넥시움": ["esomeprazole"], "프릴로섹": ["omeprazole"],
})
_IDX = {norm_ko(k): v for k, v in KO_DRUG.items()}
