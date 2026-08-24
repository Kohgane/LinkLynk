# Fly smoke test

`tests/fly_smoke.py`는 배포된 Earthflight 페이지를 직접 조회해, `static/fly/index.html` 교체 과정에서 기능 마커·API key·정적 자원이 조용히 사라지는 사고를 CI에서 바로 잡기 위한 smoke test입니다.

## 로컬 실행

```bash
python -m pip install requests
python tests/fly_smoke.py
```

## 다른 대상 URL 검사

```bash
python tests/fly_smoke.py --url https://example.com/fly/
```

`--url`을 바꾸면 HTML 본문은 해당 URL에서 가져오고, 정적 자원 검사는 그 URL의 origin 기준으로 `/fly/...`, `/.well-known/assetlinks.json` 절대 경로를 조합해 검사합니다.

## CI 동작

`.github/workflows/fly-smoke.yml`은 아래 경우에 `python tests/fly_smoke.py`를 실행합니다.

- 모든 `push`
- 매일 `00:00 UTC`
- 수동 실행(`workflow_dispatch`)

워크플로는 Python을 준비한 뒤 `requests`를 설치하고 smoke test를 실행합니다. 스크립트에서 하나라도 `FAIL`이 나오면 종료 코드 1로 끝나므로 GitHub Actions도 실패합니다.

## 어떤 사고를 막는가

- **메인 앱 script 추출 / 문법 검사**  
  첫 번째 inline `<script>`만 메인 앱 JS로 추출하고 `node --check`로 문법 오류를 확인해, 통파일 교체 중 깨진 JS가 배포되는 사고를 막습니다. `node`가 없는 환경에서는 이 검사는 `SKIP`으로 표시됩니다.
- **기능 마커 검사**  
  핵심 기능 이름과 SWEF 훅 마커(`requestWaterMask`, `toggleHQ`, `swef:ready`, `SWEF_MODULES` 등)가 남아 있는지 확인해, 기능 코드가 통째로 빠지는 사고를 잡습니다.
- **Google key 형식 검사**  
  `const GOOGLE_KEY`가 문자열이며 `AIza` prefix와 최소 길이를 만족하는지 확인해, 잘못된 placeholder나 잘린 값이 들어가는 사고를 막습니다. 로그에는 전체 키를 출력하지 않습니다.
- **DESTS / TRACKS / FILMS 개수 검사**  
  메인 앱 JS에서 배열 리터럴을 직접 찾아 최소 개수를 확인해, 대량 데이터가 일부만 남거나 통째로 누락되는 사고를 탐지합니다.
- **정적 자원 200 검사**  
  manifest, 아이콘, privacy 페이지, modules JS, `assetlinks.json`이 실제로 200 응답을 반환하는지 확인해, 배포 경로 누락이나 정적 파일 손실을 바로 잡습니다.
- **assetlinks package_name 검사**  
  `/.well-known/assetlinks.json` JSON 안에 `com.kohgane.earthflight`가 존재하는지 확인해, Android 앱 링크 연결에 필요한 패키지 식별자가 빠지는 사고를 막습니다.
