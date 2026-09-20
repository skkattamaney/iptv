"""Test whether a stream address actually plays.

Each request runs through curl with a hard time limit, so a stream that trickles
data or never answers cannot hold the check up. A stream counts as working when
its address answers and, for HLS, when its playlist leads to a downloadable
video segment.
"""
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

PLAYER_UA = "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0 Safari/537.36"
MAX_TIME = 8  # seconds per request, enforced by curl
MARK = "\n@@CURL@@"


def get(url, headers, limit=65536):
    """Return (final_url, http_code, content_type, body). Never blocks past MAX_TIME."""
    cmd = ["curl", "-sSLk", "--max-time", str(MAX_TIME), "--connect-timeout", "5",
           "--max-redirs", "5", "-w", MARK + "%{url_effective}|%{http_code}|%{content_type}"]
    for key, value in headers.items():
        cmd += ["-H", f"{key}: {value}"]
    cmd.append(url)
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=MAX_TIME + 4).stdout
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or b""
    body, _, info = raw.rpartition(MARK.encode())
    parts = info.decode("utf-8", "ignore").split("|")
    if len(parts) < 3:
        # curl was cut off mid-stream: whatever arrived is the body
        return url, 200 if raw else 0, "", raw[:limit]
    code = int(parts[1]) if parts[1].isdigit() else 0
    return parts[0] or url, code, parts[2], body[:limit]


def first_uri(text):
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def probe(url, headers):
    """Return None when the stream works, otherwise a short reason."""
    final, code, ctype, body = get(url, headers)
    for _ in range(3):
        if code == 0 and not body:
            return "no answer"
        if code >= 400:
            return f"http {code}"
        text = body.decode("utf-8", "ignore").lstrip()
        if not text.startswith("#EXTM3U"):
            if "text/html" in ctype.lower() or text[:15].lower().startswith(("<!doctype", "<html")):
                return "web page, not a stream"
            return None if body else "no data"
        uri = first_uri(text)
        if uri is None:
            return "empty playlist"
        final, code, ctype, body = get(urljoin(final, uri), headers)
        if "#EXT-X-STREAM-INF" not in text and not re.search(r"\.m3u8?(\?|$)", uri):
            if code >= 400:
                return f"segment http {code}"
            return None if body else "segment unreachable"
    return "playlist loop"


def entry_headers(meta):
    headers = {}
    for line in meta:
        m = re.match(r"#EXTVLCOPT:http-user-agent=(.+)", line)
        if m:
            headers["User-Agent"] = m.group(1).strip()
        m = re.match(r"#EXTVLCOPT:http-referrer=(.+)", line)
        if m:
            headers["Referer"] = m.group(1).strip()
    return headers


def check_entry(entry):
    """Return (status, reason): 'ok', 'needs-headers' or 'dead'."""
    meta, url = entry
    plain = {"User-Agent": PLAYER_UA}
    reason = probe(url, plain)
    if reason is None:
        return "ok", ""
    special = entry_headers(meta)
    if special and probe(url, dict(plain, **special)) is None:
        return "needs-headers", reason
    return "dead", reason


def check_all(entries, workers=64):
    results = [None] * len(entries)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(check_entry, e): i for i, e in enumerate(entries)}
        for done, fut in enumerate(as_completed(futures), 1):
            results[futures[fut]] = fut.result()
            if done % 250 == 0 or done == len(entries):
                print(f"  checked {done}/{len(entries)}", file=sys.stderr, flush=True)
    return results
