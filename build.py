"""Build english-channels.m3u from the iptv-org playlists.

Ghana, UK and US English-language channels come first, grouped by country and
category. English-language channels from every other country follow under "World".
Every stream is then tested, and only the ones that answer are kept.
"""
import collections
import datetime
import json
import os
import re
import urllib.request

from check import check_all

BASE = "https://iptv-org.github.io/iptv/"
COUNTRIES = (("gh", "Ghana"), ("uk", "UK"), ("us", "US"))
OUTPUT = "english-channels.m3u"
MIN_CHANNELS = 1000  # refuse to overwrite the playlist after a broken download or check
RETEST_GROUP = "Test on TV (needs special headers)"
HOME_STATUS = "home-status.json"  # written by home_check.py
HOME_STATUS_MAX_AGE = 45  # days before the home record is ignored as stale


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "playlist-builder"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8")


def parse(text):
    entries, cur = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            cur = [line]
        elif line.startswith("#"):
            cur.append(line)
        elif cur:
            entries.append((cur, line))
            cur = []
    return entries


def regroup(meta, label):
    m = re.search(r'group-title="([^"]*)"', meta[0])
    cat = (m.group(1) if m else "Undefined").split(";")[0] or "Undefined"
    if cat == "Undefined":
        cat = "General"
    group = f'group-title="{label}: {cat}"'
    if m:
        meta[0] = meta[0].replace(m.group(0), group, 1)
    else:
        head, _, name = meta[0].rpartition(",")
        meta[0] = f"{head} {group},{name}"
    return meta


def collect():
    english = parse(fetch("languages/eng.m3u"))
    english_urls = {url for _, url in english}
    entries, seen = [], set()
    for code, label in COUNTRIES:
        for meta, url in parse(fetch(f"countries/{code}.m3u")):
            if url in english_urls and url not in seen:
                seen.add(url)
                entries.append((regroup(meta, label), url))
    for meta, url in english:
        if url not in seen:
            seen.add(url)
            entries.append((regroup(meta, "World"), url))
    return entries


def load_home_status():
    """Return {url: status} from the last home-network check, or {} when missing or stale."""
    try:
        with open(HOME_STATUS, encoding="utf-8") as f:
            data = json.load(f)
        age = (datetime.date.today() - datetime.date.fromisoformat(data["checked"])).days
    except (OSError, ValueError, KeyError):
        return {}
    if age > HOME_STATUS_MAX_AGE:
        print(f"home record is {age} days old; ignoring it")
        return {}
    return data["streams"]


def main():
    entries = collect()
    print("found", len(entries), "English channels")

    if os.environ.get("SKIP_CHECK"):
        kept = entries
    else:
        results = check_all(entries)
        print(collections.Counter(status for status, _ in results))
        home = load_home_status()
        if home:
            # A stream blocked at home is dropped even when GitHub can reach it. A stream
            # that worked at home is kept when GitHub is merely refused (data-centre
            # blocks), but not when the address has gone (404/410), which means it died
            # after the home check.
            merged = []
            for (_, url), (status, why) in zip(entries, results):
                seen_at_home = home.get(url)
                gone = "404" in why or "410" in why
                if seen_at_home == "dead":
                    status = "dead"
                elif seen_at_home and not gone:
                    status = seen_at_home
                merged.append((status, why))
            changed = sum(a[0] != b[0] for a, b in zip(merged, results))
            print(f"home record changed {changed} results")
            results = merged
        kept, retest = [], []
        for (meta, url), (status, _) in zip(entries, results):
            if status == "ok":
                kept.append((meta, url))
            elif status == "needs-headers":
                # Alive, but only for players that send the Referer/User-Agent
                # given in the #EXTVLCOPT lines. Grouped apart so they are easy to try.
                meta[0] = re.sub(r'group-title="[^"]*"', f'group-title="{RETEST_GROUP}"', meta[0])
                retest.append((meta, url))
        kept += retest

    print("keeping", len(kept), "working channels")
    if len(kept) < MIN_CHANNELS:
        raise SystemExit(f"Only {len(kept)} channels passed; keeping the previous playlist.")
    out = ["#EXTM3U"]
    for meta, url in kept:
        out += meta + [url]
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
