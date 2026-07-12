"""LinkLynk 저장소 (Supabase/PostgreSQL). 연결: DATABASE_URL 환경변수."""
import os, time, secrets, hashlib
from cryptography.fernet import Fernet
import psycopg2, psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL")

def _load_fernet():
    k = os.environ.get("LINKLYNK_ENC_KEY")
    if k: return Fernet(k.encode() if isinstance(k, str) else k)
    kf = ".enc_key"
    if os.path.exists(kf): return Fernet(open(kf, "rb").read())
    key = Fernet.generate_key()
    open(kf, "wb").write(key); os.chmod(kf, 0o600)
    return Fernet(key)
_fernet = _load_fernet()

def _q(query, params=None, fetch=None):
    c = psycopg2.connect(DATABASE_URL)
    try:
        cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params or ())
        r = cur.fetchone() if fetch=="one" else cur.fetchall() if fetch=="all" else None
        c.commit(); return r
    finally: c.close()

def init_db():
    _q("""CREATE TABLE IF NOT EXISTS linklynk_users(
        id BIGSERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL,
        handle TEXT UNIQUE, display_name TEXT, plan TEXT DEFAULT 'free',
        pt_access_enc TEXT, pt_secret_enc TEXT, zernio_key_enc TEXT, created_at BIGINT);""")
    # 기존 테이블 마이그레이션 (컬럼 없으면 추가)
    try: _q("ALTER TABLE linklynk_users ADD COLUMN IF NOT EXISTS zernio_key_enc TEXT")
    except Exception: pass
    try: _q("ALTER TABLE linklynk_users ADD COLUMN IF NOT EXISTS anthropic_key_enc TEXT")
    except Exception: pass
    try: _q("ALTER TABLE linklynk_users ADD COLUMN IF NOT EXISTS linked_emails TEXT")
    except Exception: pass
    try: _q("ALTER TABLE linklynk_users ADD COLUMN IF NOT EXISTS gemini_key_enc TEXT")
    except Exception: pass
    try: _q("ALTER TABLE linklynk_users ADD COLUMN IF NOT EXISTS openrouter_key_enc TEXT")
    except Exception: pass
    _q("""CREATE TABLE IF NOT EXISTS linklynk_usage(
        user_id BIGINT, month TEXT, link_count INTEGER DEFAULT 0, draft_count INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, month));""")
    _q("""CREATE TABLE IF NOT EXISTS linklynk_links(
        id BIGSERIAL PRIMARY KEY, user_id BIGINT, original_url TEXT, deeplink TEXT,
        product_name TEXT, channel TEXT, clicks INTEGER DEFAULT 0, position INTEGER DEFAULT 0,
        on_profile INTEGER DEFAULT 1, created_at BIGINT);""")

    # 게시물: 임시저장(draft) → 게시(published), 게시물 URL 저장
    _q("""CREATE TABLE IF NOT EXISTS linklynk_posts(
        id BIGSERIAL PRIMARY KEY, user_id BIGINT, channel TEXT, product_name TEXT,
        content TEXT, deeplink TEXT, image TEXT,
        status TEXT DEFAULT 'draft', post_url TEXT, post_id TEXT,
        created_at BIGINT, published_at BIGINT);""")

    # 검색 캐시: 키워드→상품 (API 호출 최소화, 시간당 10회 제한 보호)
    _q("""CREATE TABLE IF NOT EXISTS linklynk_search_cache(
        keyword TEXT PRIMARY KEY, product_name TEXT, deeplink TEXT,
        image TEXT, price BIGINT, cached_at BIGINT);""")

def _hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()
    return f"{salt}${h}"
def _verify_pw(pw, stored):
    salt, _ = stored.split("$", 1); return _hash_pw(pw, salt) == stored

def create_user(email, password, handle=None, display_name=None):
    try:
        row = _q("INSERT INTO linklynk_users(email,pw_hash,handle,display_name,created_at) "
                 "VALUES(%s,%s,%s,%s,%s) RETURNING id",
                 (email,_hash_pw(password),handle,display_name or email.split("@")[0],int(time.time())),
                 fetch="one")
        return {"ok": True, "user_id": row["id"]}
    except psycopg2.errors.UniqueViolation:
        return {"ok": False, "error": "이미 가입된 이메일 또는 사용 중인 프로필 주소입니다"}
    except Exception:
        return {"ok": False, "error": "가입 처리 중 오류가 발생했습니다"}

def get_or_create_oauth_user(email, provider, display_name=None):
    """소셜 로그인: 기존 유저(본 이메일 또는 연결된 이메일)를 찾거나 새로 만듦.
    ★같은 사람이 여러 소셜로 로그인해도 하나의 계정으로 통합."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return None
    # 1) 본 이메일로 찾기
    row = _q("SELECT * FROM linklynk_users WHERE email=%s", (email,), fetch="one")
    if row:
        return dict(row)
    # 2) 연결된 이메일(linked_emails)로 찾기 → 통합 계정
    row = _q("SELECT * FROM linklynk_users WHERE linked_emails LIKE %s", (f"%{email}%",), fetch="one")
    if row:
        return dict(row)
    # 3) 새 유저
    try:
        r = _q("INSERT INTO linklynk_users(email,pw_hash,handle,display_name,created_at) "
               "VALUES(%s,%s,%s,%s,%s) RETURNING id",
               (email, f"oauth:{provider}", None, display_name or email.split("@")[0], int(time.time())),
               fetch="one")
        return get_user(r["id"])
    except Exception:
        row = _q("SELECT * FROM linklynk_users WHERE email=%s", (email,), fetch="one")
        return dict(row) if row else None

def link_email(uid, email):
    """현재 계정에 다른 이메일(소셜) 연결 → 그 소셜로 로그인해도 이 계정으로."""
    email = (email or "").strip().lower()
    row = _q("SELECT linked_emails FROM linklynk_users WHERE id=%s", (uid,), fetch="one")
    cur = (row or {}).get("linked_emails") or ""
    emails = [e for e in cur.split(",") if e.strip()]
    if email not in emails:
        emails.append(email)
    _q("UPDATE linklynk_users SET linked_emails=%s WHERE id=%s", (",".join(emails), uid))
    return {"ok": True, "linked": emails}

def auth_user(email, password):
    row = _q("SELECT * FROM linklynk_users WHERE email=%s", (email,), fetch="one")
    if not row or not _verify_pw(password, row["pw_hash"]): return None
    return dict(row)
def get_user(uid):
    row = _q("SELECT * FROM linklynk_users WHERE id=%s", (uid,), fetch="one")
    return dict(row) if row else None
def get_user_by_handle(h):
    row = _q("SELECT * FROM linklynk_users WHERE handle=%s", (h,), fetch="one")
    return dict(row) if row else None

def set_handle(uid, handle):
    """핸들(프로필 주소) 설정/변경. 중복이면 실패."""
    handle = (handle or "").strip().lower()
    # 소문자/숫자/언더스코어만, 3~20자
    import re as _re
    if not _re.match(r'^[a-z0-9_]{3,20}$', handle):
        return {"ok": False, "error": "3~20자의 영문 소문자, 숫자, _만 사용할 수 있어요"}
    exists = _q("SELECT id FROM linklynk_users WHERE handle=%s AND id!=%s", (handle, uid), fetch="one")
    if exists:
        return {"ok": False, "error": "이미 사용 중인 주소예요"}
    _q("UPDATE linklynk_users SET handle=%s WHERE id=%s", (handle, uid))
    return {"ok": True, "handle": handle}

def save_partners_key(uid, access, secret):
    ea=_fernet.encrypt(access.encode()).decode(); es=_fernet.encrypt(secret.encode()).decode()
    _q("UPDATE linklynk_users SET pt_access_enc=%s, pt_secret_enc=%s WHERE id=%s",(ea,es,uid))
    return {"ok": True}
def get_partners_key(uid):
    row=_q("SELECT pt_access_enc,pt_secret_enc FROM linklynk_users WHERE id=%s",(uid,),fetch="one")
    if not row or not row["pt_access_enc"]: return None
    return {"access":_fernet.decrypt(row["pt_access_enc"].encode()).decode(),
            "secret":_fernet.decrypt(row["pt_secret_enc"].encode()).decode()}

def save_zernio_key(uid, key):
    ek = _fernet.encrypt(key.encode()).decode()
    _q("UPDATE linklynk_users SET zernio_key_enc=%s WHERE id=%s", (ek, uid))
    return {"ok": True}

# ── 게시물(posts): 임시저장 → 게시 ──
def save_post(uid, channel, product_name, content, deeplink, image=None, status="draft"):
    row = _q("""INSERT INTO linklynk_posts(user_id,channel,product_name,content,deeplink,image,status,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
             (uid, channel, product_name, content, deeplink, image, status, int(time.time())), fetch="one")
    return row["id"] if row else None

def get_posts(uid, status=None):
    if status:
        rows = _q("SELECT * FROM linklynk_posts WHERE user_id=%s AND status=%s AND channel!='__search__' ORDER BY created_at DESC",
                  (uid, status), fetch="all")
    else:
        rows = _q("SELECT * FROM linklynk_posts WHERE user_id=%s AND channel!='__search__' ORDER BY created_at DESC",
                  (uid,), fetch="all")
    return [dict(r) for r in rows] if rows else []

def get_post(post_id):
    row = _q("SELECT * FROM linklynk_posts WHERE id=%s", (post_id,), fetch="one")
    return dict(row) if row else None

def mark_published(post_id, post_url=None, post_id_ext=None):
    _q("""UPDATE linklynk_posts SET status='published', post_url=%s, post_id=%s, published_at=%s
          WHERE id=%s""", (post_url, post_id_ext, int(time.time()), post_id))
    return {"ok": True}

def update_post_content(uid, post_id, content):
    """임시저장 글 내용 편집 (본인 것만)."""
    _q("UPDATE linklynk_posts SET content=%s WHERE id=%s AND user_id=%s AND status IN ('draft','autodraft')",
       (content, post_id, uid))
    return {"ok": True}

def delete_auto_drafts(uid):
    """이전 자동저장 초안 삭제 (최신 1개만 유지하려고)."""
    _q("DELETE FROM linklynk_posts WHERE user_id=%s AND status='autodraft'", (uid,))
    return {"ok": True}

def delete_post(uid, post_id):
    _q("DELETE FROM linklynk_posts WHERE id=%s AND user_id=%s", (post_id, uid))
    return {"ok": True}

# ── 검색 캐시 (파트너스 검색 API 시간당 10회 제한 보호) ──
def get_search_cache(keyword):
    row = _q("SELECT * FROM linklynk_search_cache WHERE keyword=%s", (keyword.strip().lower(),), fetch="one")
    if not row: return None
    # 7일 지나면 만료 (가격 변동 반영)
    if int(time.time()) - (row["cached_at"] or 0) > 7*86400:
        return None
    return dict(row)

def set_search_cache(keyword, product_name, deeplink, image, price):
    kw = keyword.strip().lower()
    _q("""INSERT INTO linklynk_search_cache(keyword,product_name,deeplink,image,price,cached_at)
          VALUES(%s,%s,%s,%s,%s,%s)
          ON CONFLICT(keyword) DO UPDATE SET product_name=EXCLUDED.product_name,
          deeplink=EXCLUDED.deeplink, image=EXCLUDED.image, price=EXCLUDED.price, cached_at=EXCLUDED.cached_at""",
       (kw, product_name, deeplink, image, price or 0, int(time.time())))
    return {"ok": True}

def count_recent_searches(uid, within_seconds=3600):
    """유저의 최근 검색 API 호출 횟수 (시간당 제한 확인용). usage 테이블 재사용."""
    since = int(time.time()) - within_seconds
    row = _q("SELECT COUNT(*) AS c FROM linklynk_posts WHERE user_id=%s AND channel='__search__' AND created_at>=%s",
             (uid, since), fetch="one")
    return row["c"] if row else 0

def log_search(uid):
    """검색 API 호출 기록 (rate limit 추적용, posts 테이블 재사용)."""
    _q("""INSERT INTO linklynk_posts(user_id,channel,status,created_at)
          VALUES(%s,'__search__','log',%s)""", (uid, int(time.time())))

def get_zernio_key(uid):
    row=_q("SELECT zernio_key_enc FROM linklynk_users WHERE id=%s",(uid,),fetch="one")
    if not row or not row.get("zernio_key_enc"): return None
    return _fernet.decrypt(row["zernio_key_enc"].encode()).decode()

def save_anthropic_key(uid, key):
    ek = _fernet.encrypt(key.encode()).decode()
    _q("UPDATE linklynk_users SET anthropic_key_enc=%s WHERE id=%s", (ek, uid))
    return {"ok": True}

def get_anthropic_key(uid):
    row=_q("SELECT anthropic_key_enc FROM linklynk_users WHERE id=%s",(uid,),fetch="one")
    if not row or not row.get("anthropic_key_enc"): return None
    return _fernet.decrypt(row["anthropic_key_enc"].encode()).decode()

FREE_LIMITS = {"link": 500, "draft": 500}
def _month(): return time.strftime("%Y-%m", time.gmtime())
def get_usage(uid):
    row=_q("SELECT * FROM linklynk_usage WHERE user_id=%s AND month=%s",(uid,_month()),fetch="one")
    return {"link_count":row["link_count"],"draft_count":row["draft_count"]} if row else {"link_count":0,"draft_count":0}
def check_and_bump(uid, kind, plan):
    if plan=="pro": _bump(uid,kind); return True,None,None
    u=get_usage(uid); field="link_count" if kind=="link" else "draft_count"; limit=FREE_LIMITS[kind]
    if u[field]>=limit: return False,u[field],limit
    _bump(uid,kind); return True,u[field]+1,limit
def _bump(uid, kind):
    field="link_count" if kind=="link" else "draft_count"
    _q(f"INSERT INTO linklynk_usage(user_id,month,{field}) VALUES(%s,%s,1) "
       f"ON CONFLICT(user_id,month) DO UPDATE SET {field}=linklynk_usage.{field}+1",(uid,_month()))

def save_link(uid, url, deeplink, pname, channel):
    row=_q("INSERT INTO linklynk_links(user_id,original_url,deeplink,product_name,channel,created_at) "
           "VALUES(%s,%s,%s,%s,%s,%s) RETURNING id",(uid,url,deeplink,pname,channel,int(time.time())),fetch="one")
    return row["id"]
def get_user_links(uid, profile_only=False):
    q="SELECT * FROM linklynk_links WHERE user_id=%s"+(" AND on_profile=1" if profile_only else "")+" ORDER BY position ASC, created_at DESC"
    rows=_q(q,(uid,),fetch="all"); return [dict(r) for r in rows] if rows else []

def get_link(link_id):
    row=_q("SELECT * FROM linklynk_links WHERE id=%s",(link_id,),fetch="one")
    return dict(row) if row else None

def delete_link(uid, link_id):
    _q("DELETE FROM linklynk_links WHERE id=%s AND user_id=%s",(link_id,uid))
    return {"ok": True}

def toggle_link_profile(uid, link_id, on):
    _q("UPDATE linklynk_links SET on_profile=%s WHERE id=%s AND user_id=%s",(1 if on else 0, link_id, uid))
    return {"ok": True}

def reorder_links(uid, ordered_ids):
    """ordered_ids 순서대로 position 부여."""
    for pos, lid in enumerate(ordered_ids):
        _q("UPDATE linklynk_links SET position=%s WHERE id=%s AND user_id=%s",(pos, lid, uid))
    return {"ok": True}

def bump_click(link_id):
    _q("UPDATE linklynk_links SET clicks=COALESCE(clicks,0)+1 WHERE id=%s",(link_id,))

def get_click_stats(uid):
    """유저의 총 클릭 + 링크별 클릭 (상위)."""
    total=_q("SELECT COALESCE(SUM(clicks),0) AS t FROM linklynk_links WHERE user_id=%s",(uid,),fetch="one")
    top=_q("SELECT product_name, channel, COALESCE(clicks,0) AS clicks FROM linklynk_links "
           "WHERE user_id=%s ORDER BY clicks DESC, created_at DESC LIMIT 10",(uid,),fetch="all")
    return {"total_clicks": (total["t"] if total else 0),
            "top": [dict(r) for r in top] if top else []}

if __name__=="__main__":
    if not DATABASE_URL: print("DATABASE_URL 설정 필요")
    else: init_db(); print("테이블 초기화 완료")


# ── 제공자별 LLM 키 (Gemini/OpenRouter/Claude 각각 저장 → 비교 가능) ──
_KEY_COL = {"gemini": "gemini_key_enc", "openrouter": "openrouter_key_enc", "anthropic": "anthropic_key_enc"}

def save_llm_key(uid, provider, key):
    col = _KEY_COL.get(provider)
    if not col: return {"ok": False, "error": "unknown_provider"}
    ek = _fernet.encrypt(key.encode()).decode()
    _q(f"UPDATE linklynk_users SET {col}=%s WHERE id=%s", (ek, uid))
    return {"ok": True}

def get_llm_key(uid, provider):
    col = _KEY_COL.get(provider)
    if not col: return None
    row = _q(f"SELECT {col} FROM linklynk_users WHERE id=%s", (uid,), fetch="one")
    if not row or not row.get(col): return None
    try:
        return _fernet.decrypt(row[col].encode()).decode()
    except Exception:
        return None

def get_llm_keys(uid):
    """등록된 모든 LLM 키 → {provider: key}"""
    out = {}
    for p in _KEY_COL:
        k = get_llm_key(uid, p)
        if k: out[p] = k
    return out
