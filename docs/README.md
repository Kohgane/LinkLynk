# docs — 감사 문서 목차

이 디렉터리에는 `Kohgane/LinkLynk` 저장소의 프론트엔드 감사 리포트가 포함되어 있습니다.

---

## 문서 목록

### [audit-a11y.md](./audit-a11y.md) — 접근성(A11Y) 감사 리포트

`static/fly/index.html` 및 `static/fly/modules/*.js`를 대상으로 WCAG 2.1 AA 기준으로 분석한 접근성 감사 리포트입니다.

주요 발견 항목:
- 버튼 `aria-label` 누락 (아이콘 전용 버튼, 탭, 모달 버튼 등)
- 터치 타겟 44px 미만 요소 (`.ccard`, `.btn`, `.tabb`, `.dcard` 등)
- 색 대비 정적 계산 불가 요소 (Cesium 3D 장면 위 HUD 텍스트)
- `div`를 버튼처럼 사용하는 키보드 접근 불가 요소 (`.vcard`, `.dcard`, `.ccard` 등)

---

### [audit-perf.md](./audit-perf.md) — 성능 감사 리포트

`static/fly/index.html` 및 `static/fly/modules/*.js`를 대상으로 런타임 성능 병목을 분석한 감사 리포트입니다.

주요 발견 항목:
- 매 렌더 프레임 `innerHTML` 갱신 (raceTick)
- 매 프레임 Cesium 객체 할당 (`new HeadingPitchRange`, `position.clone()`)
- 전역 `keydown` 이벤트 리스너 미제거 (replay.js)
- `querySelectorAll` 반복 순회 (90+ 목적지 카드)
- `setInterval` 기반 재생 루프 (렌더 프레임 비동기, hud.js)

---

### [audit-sw.md](./audit-sw.md) — 서비스워커(PWA) 감사 리포트

`static/fly/sw.js`의 캐시 전략을 분석하고, 모듈 파일 캐싱 추가 및 `stale-while-revalidate` 전략 적용을 다룬 리포트입니다.

---

## 분석 대상 파일

| 파일 | 분석 유형 |
|------|-----------|
| `static/fly/index.html` | 읽기 전용 분석 |
| `static/fly/modules/index.js` | 읽기 전용 분석 |
| `static/fly/modules/launcher.js` | 읽기 전용 분석 |
| `static/fly/modules/hud.js` | 읽기 전용 분석 |
| `static/fly/modules/favorites.js` | 읽기 전용 분석 |
| `static/fly/modules/replay.js` | 읽기 전용 분석 |
| `static/fly/modules/share.js` | 읽기 전용 분석 |
| `static/fly/modules/compare.js` | 읽기 전용 분석 |

> 분석 대상 파일은 읽기 전용으로만 참조하였으며, 어떠한 코드 수정도 수행하지 않았습니다.
