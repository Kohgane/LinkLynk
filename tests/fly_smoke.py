#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_URL = "https://linklynk.onrender.com/fly/"
TIMEOUT = 20
MARKERS = [
    "requestWaterMask",
    "requestVertexNormals",
    "showGroundAtmosphere",
    "createLensFlareStage",
    "toggleHQ",
    "cinebars",
    "coachCard",
    "searchPlace",
    "MOMENTS",
    "MediaRecorder",
    "tabbar",
    "createGooglePhotorealistic3DTileset",
    "swef:ready",
    "SWEF_MODULES",
]
STATIC_PATHS = [
    "/fly/manifest.json",
    "/fly/icon-512.png",
    "/fly/privacy.html",
    "/fly/modules/index.js",
    "/fly/modules/launcher.js",
    "/fly/modules/favorites.js",
    "/fly/modules/replay.js",
    "/fly/modules/hud.js",
    "/fly/modules/share.js",
    "/fly/modules/compare.js",
    "/.well-known/assetlinks.json",
]
ARRAY_MINIMUMS = {
    "DESTS": 125,
    "TRACKS": 8,
    "FILMS": 11,
}
SCRIPT_OPEN_RE = re.compile(r"<script\b(?P<attrs>[^>]*)>", re.IGNORECASE)
SCRIPT_SRC_RE = re.compile(r"\bsrc\s*=", re.IGNORECASE)
GOOGLE_KEY_RE = re.compile(r"\bconst\s+GOOGLE_KEY\s*=\s*(['\"])(?P<value>.*?)\1", re.DOTALL)
LOCALSTORAGE_LITERAL_RE = re.compile(
    r"\blocalStorage\.(?:getItem|setItem|removeItem)\(\s*(['\"])(?P<key>.*?)\1",
    re.DOTALL,
)
MODULE_STRING_RE = re.compile(r"(['\"])(?P<name>[^'\"]+?\.js)\1")
PANEL_SELECTOR_PATTERNS = [
    'document.getElementById("panel")',
    "document.getElementById('panel')",
    'document.querySelector("#panel")',
    "document.querySelector('#panel')",
]


class ResultRow:
    def __init__(self, check: str, status: str, details: str) -> None:
        self.check = check
        self.status = status
        self.details = details


class CheckFailure(Exception):
    pass


class HtmlExtractionError(CheckFailure):
    pass


class JsParsingError(CheckFailure):
    pass


class AssetCheckError(CheckFailure):
    pass


class JsonSearchError(CheckFailure):
    pass


class JsScanner:
    def __init__(self, text: str, start: int = 0) -> None:
        self.text = text
        self.i = start
        self.length = len(text)
        self.in_string: Optional[str] = None
        self.in_line_comment = False
        self.in_block_comment = False
        self.escape = False

    def at_end(self) -> bool:
        return self.i >= self.length

    def current(self) -> str:
        return self.text[self.i]

    def advance(self) -> None:
        ch = self.text[self.i]
        nxt = self.text[self.i + 1] if self.i + 1 < self.length else ""

        if self.in_line_comment:
            self.i += 1
            if ch == "\n":
                self.in_line_comment = False
            return

        if self.in_block_comment:
            if ch == "*" and nxt == "/":
                self.i += 2
                self.in_block_comment = False
            else:
                self.i += 1
            return

        if self.in_string is not None:
            self.i += 1
            if self.escape:
                self.escape = False
            elif ch == "\\":
                self.escape = True
            elif ch == self.in_string:
                self.in_string = None
            return

        if ch == "/" and nxt == "/":
            self.i += 2
            self.in_line_comment = True
            return

        if ch == "/" and nxt == "*":
            self.i += 2
            self.in_block_comment = True
            return

        if ch in ('"', "'", "`"):
            self.i += 1
            self.in_string = ch
            self.escape = False
            return

        self.i += 1

    def significant_char(self) -> Optional[str]:
        while not self.at_end():
            if self.in_line_comment or self.in_block_comment or self.in_string is not None:
                self.advance()
                continue

            ch = self.current()
            nxt = self.text[self.i + 1] if self.i + 1 < self.length else ""
            if ch == "/" and nxt in ("/", "*"):
                self.advance()
                continue
            if ch in ('"', "'", "`"):
                self.advance()
                continue
            if ch.isspace():
                self.i += 1
                continue
            return ch
        return None


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def add_row(rows: List[ResultRow], check: str, status: str, details: str) -> None:
    rows.append(ResultRow(check, status, details))


def add_section(rows: List[ResultRow], title: str) -> None:
    rows.append(ResultRow(f"=== {title} ===", "", ""))


def print_table(rows: Sequence[ResultRow]) -> None:
    print("| Check | Status | Details |")
    print("| --- | --- | --- |")
    for row in rows:
        print(
            f"| {markdown_escape(row.check)} | {markdown_escape(row.status)} | {markdown_escape(row.details)} |"
        )


def fetch_text(url: str) -> Tuple[int, str]:
    response = requests.get(url, timeout=TIMEOUT)
    return response.status_code, response.text


def fetch_binary_status(url: str) -> int:
    response = requests.get(url, timeout=TIMEOUT)
    return response.status_code


def extract_first_inline_script(html: str) -> Tuple[int, str]:
    lower_html = html.lower()
    script_count = 0
    for match in SCRIPT_OPEN_RE.finditer(html):
        script_count += 1
        attrs = match.group("attrs") or ""
        close_index = lower_html.find("</script>", match.end())
        if close_index == -1:
            raise HtmlExtractionError("`</script>` 닫힘 태그를 찾지 못했습니다.")
        if not SCRIPT_SRC_RE.search(attrs):
            return script_count, html[match.end() : close_index]
    raise HtmlExtractionError("첫 inline <script>를 찾지 못했습니다.")


def count_script_tags(html: str) -> int:
    return len(SCRIPT_OPEN_RE.findall(html))


def find_matching_bracket(text: str, start: int, opening: str = "[", closing: str = "]") -> int:
    if start >= len(text) or text[start] != opening:
        raise JsParsingError(f"'{opening}' 시작 위치를 찾지 못했습니다.")

    scanner = JsScanner(text, start)
    depth = 0
    while not scanner.at_end():
        if scanner.in_line_comment or scanner.in_block_comment or scanner.in_string is not None:
            scanner.advance()
            continue

        ch = scanner.current()
        nxt = text[scanner.i + 1] if scanner.i + 1 < len(text) else ""
        if ch == "/" and nxt in ("/", "*"):
            scanner.advance()
            continue
        if ch in ('"', "'", "`"):
            scanner.advance()
            continue

        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return scanner.i
        scanner.i += 1

    raise JsParsingError(f"'{opening}' 에 대응하는 '{closing}' 를 찾지 못했습니다.")


def extract_const_array_literal(js: str, name: str) -> str:
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=\s*\[", js)
    if not match:
        raise JsParsingError(f"`const {name} = [...]` 패턴을 찾지 못했습니다.")

    start = match.end() - 1
    end = find_matching_bracket(js, start)
    return js[start : end + 1]


def count_top_level_items(array_literal: str) -> int:
    if len(array_literal) < 2 or array_literal[0] != "[" or array_literal[-1] != "]":
        raise JsParsingError("배열 리터럴 형식이 아닙니다.")

    content = array_literal[1:-1]
    scanner = JsScanner(content)
    brace_depth = 0
    bracket_depth = 0
    paren_depth = 0
    has_token = False
    count = 0

    while not scanner.at_end():
        if scanner.in_line_comment or scanner.in_block_comment or scanner.in_string is not None:
            if scanner.in_string is not None:
                has_token = True
            scanner.advance()
            continue

        ch = scanner.current()
        nxt = content[scanner.i + 1] if scanner.i + 1 < len(content) else ""
        if ch == "/" and nxt in ("/", "*"):
            scanner.advance()
            continue
        if ch in ('"', "'", "`"):
            has_token = True
            scanner.advance()
            continue

        if ch.isspace():
            scanner.i += 1
            continue

        if ch == "{":
            brace_depth += 1
            has_token = True
        elif ch == "}":
            brace_depth -= 1
            if brace_depth < 0:
                raise JsParsingError("객체 중괄호 깊이가 음수가 되었습니다.")
        elif ch == "[":
            bracket_depth += 1
            has_token = True
        elif ch == "]":
            bracket_depth -= 1
            if bracket_depth < 0:
                raise JsParsingError("배열 대괄호 깊이가 음수가 되었습니다.")
        elif ch == "(":
            paren_depth += 1
            has_token = True
        elif ch == ")":
            paren_depth -= 1
            if paren_depth < 0:
                raise JsParsingError("괄호 깊이가 음수가 되었습니다.")
        elif ch == "," and brace_depth == 0 and bracket_depth == 0 and paren_depth == 0:
            if has_token:
                count += 1
                has_token = False
        else:
            has_token = True

        scanner.i += 1

    if brace_depth or bracket_depth or paren_depth:
        raise JsParsingError("배열 내부 구문 깊이가 0으로 돌아오지 않았습니다.")
    if has_token:
        count += 1
    return count


def summarize_google_key(value: str) -> str:
    return f"prefix_AiZa={str(value.startswith('AIza')).lower()}, length={len(value)}"


def find_google_key(js: str) -> str:
    match = GOOGLE_KEY_RE.search(js)
    if not match:
        raise JsParsingError("`const GOOGLE_KEY = \"...\"` 패턴을 찾지 못했습니다.")
    return match.group("value")


def validate_node_syntax(js: str) -> Tuple[str, str]:
    node_path = shutil.which("node")
    if not node_path:
        return "SKIP", "node 실행 파일이 없어 `node --check` 문법 검사를 건너뜁니다."

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(js)
            tmp_path = tmp.name
        completed = subprocess.run(
            [node_path, "--check", tmp_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return "PASS", "`node --check` 문법 검사를 통과했습니다."
        output = completed.stderr or completed.stdout or ""
        return "FAIL", f"`node --check` 실패: {summarize_command_output(output)}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def collect_module_paths_from_static_list(paths: Sequence[str]) -> List[str]:
    modules = []
    for path in paths:
        if not path.startswith("/fly/modules/") or not path.endswith(".js"):
            continue
        if path.endswith("/index.js"):
            continue
        modules.append(path)
    return modules


def extract_modules_from_index_js(index_js: str) -> List[str]:
    array_literal = extract_const_array_literal(index_js, "MODULES")
    modules = []
    for match in MODULE_STRING_RE.finditer(array_literal):
        modules.append(match.group("name"))
    if not modules:
        raise JsParsingError("MODULES 배열에서 모듈 파일명을 추출하지 못했습니다.")
    return modules


def extract_localstorage_literal_keys(js: str) -> List[str]:
    return [m.group("key") for m in LOCALSTORAGE_LITERAL_RE.finditer(js)]


def summarize_command_output(output: str, limit: int = 300) -> str:
    compact = " ".join((output or "").split())
    return compact[:limit] if compact else "(출력 없음)"


def check_module_conventions(js: str) -> Tuple[str, str, str, str]:
    keys = extract_localstorage_literal_keys(js)
    ef_keys = sorted({k for k in keys if k.startswith("ef_")})
    non_swefm_keys = sorted({k for k in keys if not k.startswith("swefm_")})
    hardcoded = [pattern for pattern in PANEL_SELECTOR_PATTERNS if pattern in js]

    if ef_keys:
        storage_status = "FAIL"
        storage_details = f"ef_* localStorage 키 사용 금지 위반: {', '.join(ef_keys)}"
    elif non_swefm_keys:
        storage_status = "FAIL"
        storage_details = f"swefm_ 접두가 아닌 localStorage 키 발견: {', '.join(non_swefm_keys)}"
    elif keys:
        storage_status = "PASS"
        storage_details = f"localStorage 키 {len(set(keys))}개가 모두 swefm_ 접두입니다."
    else:
        storage_status = "PASS"
        storage_details = "localStorage 문자열 리터럴 키 사용을 찾지 못했습니다."

    if hardcoded:
        selector_status = "WARN"
        selector_details = f"앱 내부 selector 하드코딩 경고: {', '.join(hardcoded)}"
    else:
        selector_status = "PASS"
        selector_details = "panel selector 하드코딩 패턴이 없습니다."

    return storage_status, storage_details, selector_status, selector_details


def collect_missing_markers(text: str) -> List[str]:
    return [marker for marker in MARKERS if marker not in text]


def find_origin(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise CheckFailure(f"유효한 절대 URL이 아닙니다: {base_url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def json_contains_package_name(value: object, package_name: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "package_name" and item == package_name:
                return True
            if json_contains_package_name(item, package_name):
                return True
        return False
    if isinstance(value, list):
        return any(json_contains_package_name(item, package_name) for item in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Earthflight 배포 smoke test")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"검사 대상 URL (기본값: {DEFAULT_URL})")
    args = parser.parse_args()

    rows: List[ResultRow] = []
    html = ""
    main_js = ""
    add_section(rows, "Main app")

    try:
        status_code, html = fetch_text(args.url)
        if status_code == 200:
            add_row(rows, "HTML fetch", "PASS", f"{args.url} -> HTTP 200")
        else:
            add_row(rows, "HTML fetch", "FAIL", f"{args.url} -> HTTP {status_code}")
    except requests.RequestException as exc:
        add_row(rows, "HTML fetch", "FAIL", f"네트워크 오류: {exc}")

    if html:
        try:
            total_scripts = count_script_tags(html)
            inline_index, main_js = extract_first_inline_script(html)
            if total_scripts == 4:
                add_row(
                    rows,
                    "HTML script structure",
                    "PASS",
                    f"script 태그 {total_scripts}개, 첫 inline script는 #{inline_index}입니다.",
                )
            else:
                add_row(
                    rows,
                    "HTML script structure",
                    "FAIL",
                    f"script 태그 개수가 4가 아닙니다: {total_scripts}",
                )
        except HtmlExtractionError as exc:
            add_row(rows, "HTML script structure", "FAIL", str(exc))

    if main_js:
        syntax_status, syntax_details = validate_node_syntax(main_js)
        add_row(rows, "Main app JS syntax", syntax_status, syntax_details)

        marker_text = main_js + "\n" + html
        missing_markers = collect_missing_markers(marker_text)
        if missing_markers:
            add_row(
                rows,
                "Feature markers",
                "FAIL",
                f"누락된 마커: {', '.join(missing_markers)}",
            )
        else:
            add_row(rows, "Feature markers", "PASS", f"필수 마커 {len(MARKERS)}개가 모두 존재합니다.")

        try:
            google_key = find_google_key(main_js)
            if google_key.startswith("AIza") and len(google_key) >= 30:
                add_row(rows, "Google key format", "PASS", summarize_google_key(google_key))
            else:
                add_row(rows, "Google key format", "FAIL", summarize_google_key(google_key))
        except JsParsingError as exc:
            add_row(rows, "Google key format", "FAIL", str(exc))

        for array_name, minimum in ARRAY_MINIMUMS.items():
            check_name = f"{array_name} count"
            try:
                array_literal = extract_const_array_literal(main_js, array_name)
                count = count_top_level_items(array_literal)
                if count >= minimum:
                    add_row(rows, check_name, "PASS", f"{count}개 (요구치: {minimum}개 이상)")
                else:
                    add_row(rows, check_name, "FAIL", f"{count}개 (요구치: {minimum}개 이상)")
            except JsParsingError as exc:
                add_row(rows, check_name, "FAIL", str(exc))
    else:
        add_row(rows, "Main app JS syntax", "FAIL", "메인 앱 inline script를 추출하지 못했습니다.")
        add_row(rows, "Feature markers", "FAIL", "메인 앱 JS가 없어 마커를 검사할 수 없습니다.")
        add_row(rows, "Google key format", "FAIL", "메인 앱 JS가 없어 GOOGLE_KEY를 검사할 수 없습니다.")
        for array_name in ARRAY_MINIMUMS:
            add_row(rows, f"{array_name} count", "FAIL", "메인 앱 JS가 없어 배열 개수를 검사할 수 없습니다.")

    try:
        origin = find_origin(args.url)
        add_section(rows, "Static resources")
        for path in STATIC_PATHS:
            full_url = urljoin(origin, path)
            try:
                status_code = fetch_binary_status(full_url)
                if status_code == 200:
                    add_row(rows, f"Static asset {path}", "PASS", f"{full_url} -> HTTP 200")
                else:
                    add_row(rows, f"Static asset {path}", "FAIL", f"{full_url} -> HTTP {status_code}")
            except requests.RequestException as exc:
                add_row(rows, f"Static asset {path}", "FAIL", f"네트워크 오류: {exc}")

        assetlinks_url = urljoin(origin, "/.well-known/assetlinks.json")
        try:
            response = requests.get(assetlinks_url, timeout=TIMEOUT)
            if response.status_code != 200:
                raise AssetCheckError(f"HTTP {response.status_code}")
            try:
                payload = response.json()
            except json.JSONDecodeError as exc:
                raise JsonSearchError(f"JSON 파싱 실패: {exc}") from exc
            if json_contains_package_name(payload, "com.kohgane.earthflight"):
                add_row(rows, "assetlinks package_name", "PASS", "com.kohgane.earthflight 가 존재합니다.")
            else:
                add_row(rows, "assetlinks package_name", "FAIL", "com.kohgane.earthflight 가 없습니다.")
        except (requests.RequestException, AssetCheckError, JsonSearchError) as exc:
            add_row(rows, "assetlinks package_name", "FAIL", str(exc))

        module_paths = collect_module_paths_from_static_list(STATIC_PATHS)
        module_sources = {}
        add_section(rows, "Module syntax")
        for module_path in module_paths:
            module_url = urljoin(origin, module_path)
            module_name = module_path.rsplit("/", 1)[-1]
            try:
                status_code, module_js = fetch_text(module_url)
                if status_code != 200:
                    add_row(
                        rows,
                        f"Module syntax {module_name}",
                        "FAIL",
                        f"{module_url} -> HTTP {status_code}",
                    )
                    continue
                module_sources[module_name] = module_js
                syntax_status, syntax_details = validate_node_syntax(module_js)
                add_row(rows, f"Module syntax {module_name}", syntax_status, syntax_details)
            except requests.RequestException as exc:
                add_row(rows, f"Module syntax {module_name}", "FAIL", f"네트워크 오류: {exc}")

        add_section(rows, "Module conventions")
        for module_path in module_paths:
            module_name = module_path.rsplit("/", 1)[-1]
            module_js = module_sources.get(module_name)
            if module_js is None:
                module_url = urljoin(origin, module_path)
                try:
                    status_code, module_js = fetch_text(module_url)
                    if status_code != 200:
                        add_row(
                            rows,
                            f"Module conventions storage {module_name}",
                            "FAIL",
                            f"{module_url} -> HTTP {status_code}",
                        )
                        add_row(
                            rows,
                            f"Module conventions selector {module_name}",
                            "FAIL",
                            "소스 미확보로 selector 하드코딩 검사를 완료하지 못했습니다.",
                        )
                        continue
                    module_sources[module_name] = module_js
                except requests.RequestException as exc:
                    add_row(rows, f"Module conventions storage {module_name}", "FAIL", f"네트워크 오류: {exc}")
                    add_row(
                        rows,
                        f"Module conventions selector {module_name}",
                        "FAIL",
                        "네트워크 오류로 selector 하드코딩 검사를 완료하지 못했습니다.",
                    )
                    continue

            storage_status, storage_details, selector_status, selector_details = check_module_conventions(module_js)
            add_row(rows, f"Module conventions storage {module_name}", storage_status, storage_details)
            add_row(rows, f"Module conventions selector {module_name}", selector_status, selector_details)

        add_section(rows, "Module registration")
        index_url = urljoin(origin, "/fly/modules/index.js")
        try:
            status_code, index_js = fetch_text(index_url)
            if status_code != 200:
                add_row(rows, "Module registration parse", "FAIL", f"{index_url} -> HTTP {status_code}")
            else:
                try:
                    registered_modules = extract_modules_from_index_js(index_js)
                    add_row(
                        rows,
                        "Module registration parse",
                        "PASS",
                        f"MODULES 배열에서 {len(registered_modules)}개 모듈을 추출했습니다.",
                    )
                    for module_name in registered_modules:
                        module_url = urljoin(origin, f"/fly/modules/{module_name}")
                        try:
                            code = fetch_binary_status(module_url)
                            if code == 200:
                                add_row(
                                    rows,
                                    f"Module registration {module_name}",
                                    "PASS",
                                    f"{module_url} -> HTTP 200",
                                )
                            else:
                                add_row(
                                    rows,
                                    f"Module registration {module_name}",
                                    "FAIL",
                                    f"{module_url} -> HTTP {code}",
                                )
                        except requests.RequestException as exc:
                            add_row(
                                rows,
                                f"Module registration {module_name}",
                                "FAIL",
                                f"네트워크 오류: {exc}",
                            )
                except JsParsingError as exc:
                    add_row(rows, "Module registration parse", "FAIL", str(exc))
        except requests.RequestException as exc:
            add_row(rows, "Module registration parse", "FAIL", f"네트워크 오류: {exc}")
    except CheckFailure as exc:
        add_row(rows, "Static asset checks", "FAIL", str(exc))
        add_row(rows, "assetlinks package_name", "FAIL", "origin 계산 실패로 검사하지 못했습니다.")
        add_row(rows, "Module syntax", "FAIL", "origin 계산 실패로 검사하지 못했습니다.")
        add_row(rows, "Module conventions", "FAIL", "origin 계산 실패로 검사하지 못했습니다.")
        add_row(rows, "Module registration", "FAIL", "origin 계산 실패로 검사하지 못했습니다.")

    print_table(rows)

    fail_count = sum(1 for row in rows if row.status == "FAIL")
    pass_count = sum(1 for row in rows if row.status == "PASS")
    skip_count = sum(1 for row in rows if row.status == "SKIP")
    warn_count = sum(1 for row in rows if row.status == "WARN")
    total_count = sum(1 for row in rows if row.status in {"PASS", "FAIL", "SKIP", "WARN"})
    print()
    print(
        f"Summary: TOTAL {total_count} / PASS {pass_count} / FAIL {fail_count} / SKIP {skip_count} / WARN {warn_count}"
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
