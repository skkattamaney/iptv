"""Build english-channels.m3u from the iptv-org playlists.

Ghana, UK and US English-language channels come first, grouped by country and
category. English-language channels from every other country follow under "World".
Every stream is then tested, and only the ones that answer are kept.
"""
import collections
import os
import re
import urllib.request

from check import check_all

BASE = "https://iptv-org.github.io/iptv/"
COUNTRIES = (("gh", "Ghana"), ("uk", "UK"), ("us", "US"))
OUTPUT = "english-channels.m3u"
MIN_CHANNELS = 1000  # refuse to overwrite the playlist after a broken download or check
RETEST_GROUP = "Test on TV (needs special headers)"


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


def main():
    entries = collect()
    print("found", len(entries), "English channels")

    if os.environ.get("SKIP_CHECK"):
        kept = entries
    else:
        results = check_all(entries)
        print(collections.Counter(status for status, _ in results))
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
