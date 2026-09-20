"""Build english-channels.m3u from the iptv-org playlists.

Ghana, UK and US English-language channels come first, grouped by country and
category. English-language channels from every other country follow under "World".
"""
import re
import urllib.request

BASE = "https://iptv-org.github.io/iptv/"
COUNTRIES = (("gh", "Ghana"), ("uk", "UK"), ("us", "US"))
OUTPUT = "english-channels.m3u"
MIN_CHANNELS = 1000  # refuse to overwrite the playlist with a broken download


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


def main():
    english = parse(fetch("languages/eng.m3u"))
    english_urls = {url for _, url in english}
    out, seen, stats = ["#EXTM3U"], set(), {}

    for code, label in COUNTRIES:
        count = 0
        for meta, url in parse(fetch(f"countries/{code}.m3u")):
            if url not in english_urls or url in seen:
                continue
            seen.add(url)
            out += regroup(meta, label) + [url]
            count += 1
        stats[label] = count

    count = 0
    for meta, url in english:
        if url in seen:
            continue
        seen.add(url)
        out += regroup(meta, "World") + [url]
        count += 1
    stats["World"] = count

    total = sum(stats.values())
    print(stats, "total", total)
    if total < MIN_CHANNELS:
        raise SystemExit(f"Only {total} channels found; keeping the previous playlist.")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
