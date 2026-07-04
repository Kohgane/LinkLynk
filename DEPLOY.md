# LinkLynk 배포 가이드

MVP를 실제 인터넷에 올려 폰으로 접속하게 만드는 절차.

## 파일 구성 (배포 대상)
```
linklynk/
├── app.py            # 백엔드 API (멀티테넌트)
├── core.py           # 쿠팡 딥링크 엔진 + 블로그초안 + 고지문구
├── store.py          # DB(SQLite) + 키 암호화 + 사용량
├── index.html        # 모바일 프론트엔드
├── requirements.txt  # 의존성
├── Procfile          # 실행 명령 (gunicorn)
├── runtime.txt       # 파이썬 버전
└── .gitignore
```

## 필수 환경변수 (배포 시 반드시 설정)

| 변수 | 설명 | 예시 |
|------|------|------|
| `LINKLYNK_SESSION_SECRET` | 세션 암호화용 (아무 긴 랜덤 문자열) | `openssl rand -hex 32` 결과 |
| `LINKLYNK_ENC_KEY` | 파트너스 키 암호화용 Fernet 키 | 아래 명령으로 생성 |
| `COUPANG_PT_ACCESS` | 폴백 파트너스 access (체험용, 선택) | 39659f61-... |
| `COUPANG_PT_SECRET` | 폴백 파트너스 secret (체험용, 선택) | cc9a76dd... |

**Fernet 키 생성:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
> ⚠️ `LINKLYNK_ENC_KEY`는 한번 정하면 **절대 바꾸면 안 됨**. 바꾸면 저장된 유저 키를 복호화 못 함.
> ⚠️ 배포 환경엔 `.enc_key` 파일이 없어야 함(환경변수로 관리). .gitignore에 이미 포함.

---

## 옵션 A) Render 배포 (추천 — 가장 쉬움)

1. GitHub에 코드 푸시 (새 레포, 예: `linklynk`)
2. Render 대시보드 → New → Web Service → 레포 연결
3. 설정:
   - Environment: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
4. Environment Variables에 위 표의 변수 등록
5. Deploy → `https://linklynk.onrender.com` 같은 주소 발급

**주의 — SQLite 한계:** Render 무료 플랜은 디스크가 재배포마다 초기화됨.
- MVP 테스트: SQLite 그대로 OK
- 실서비스: **PostgreSQL로 이전** 필요 (Render Postgres 무료 제공). store.py의 sqlite3 → psycopg2로 교체.

---

## 옵션 B) Bluehost 배포 (기존 서버 활용)

Bluehost는 기본이 PHP 호스팅이라 Python 앱은 제약이 있음. 두 방법:

**B-1. Passenger(cPanel Python App)** — Bluehost가 지원하면:
1. cPanel → Setup Python App
2. 앱 루트에 파일 업로드, `app.py`의 `app` 객체를 WSGI 진입점으로
3. requirements 설치, 환경변수 등록

**B-2. 별도 포트 + gunicorn** (SSH 접근되니 가능):
```bash
cd ~/linklynk
pip install --user -r requirements.txt
export LINKLYNK_SESSION_SECRET="..." LINKLYNK_ENC_KEY="..."
gunicorn app:app --bind 127.0.0.1:8080 --workers 2 --daemon
# 그담 .htaccess나 리버스 프록시로 서브도메인 연결
```
> Bluehost 공유호스팅은 백그라운드 프로세스·포트에 제약이 많음.
> **결론: MVP는 Render가 훨씬 매끄러움.** Bluehost는 이미 WooCommerce로 쓰는 중이라 얽히지 않는 게 나음.

---

## 배포 후 체크리스트

- [ ] `https://주소/` 접속 → 프론트 화면 뜨는지
- [ ] `https://주소/api/health` → `{"ok":true}` 뜨는지
- [ ] 회원가입 → 로그인 → 키 등록 → 링크 생성 흐름 테스트
- [ ] `https://주소/u/{handle}` → 공개 프로필 뜨는지
- [ ] HTTPS 적용됐는지 (Render는 자동, Bluehost는 SSL 설정)

---

## 다음 단계 (배포 후)

1. **PostgreSQL 이전** (실서비스 필수 — SQLite는 동시성·영속성 한계)
2. **결제 연동** (토스페이먼츠/아임포트 → Pro 구독)
3. **네이버커넥트 API** 연동
4. **클릭 트래킹** 실측 (링크 리다이렉트 경유)
5. **PWA 매니페스트** (홈화면 추가, 앱처럼)
6. **커스텀 도메인** 연결
