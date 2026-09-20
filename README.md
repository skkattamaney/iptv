# iptv

An English-only playlist built from the public [iptv-org](https://github.com/iptv-org/iptv) lists.

Playlist address: https://skkattamaney.github.io/iptv/english-channels.m3u

Ghana, UK and US channels come first, grouped by country and category ("UK: News", "US: Sports"). English-language channels from every other country follow under "World".

A GitHub Actions job runs `build.py` once a day. It rebuilds the list from iptv-org, then `check.py` tests every stream and drops the ones that do not answer, so dead channels disappear and new ones appear without any manual work. Streams that only answer when the player sends a special Referer or User-Agent go into a group called "Test on TV (needs special headers)". The repository holds links to streams that are already public. It hosts no video.

## Matching the list to the home network

GitHub runs the daily check from US data centres, which see a slightly different internet from a home connection: some streams are locked to one country, and some refuse data-centre addresses. `home-status.json` records what the home network could reach, and the daily build uses it to correct its own results. Refresh it from a computer on the same network as the TV:

```sh
python3 home_check.py && git add home-status.json && git commit -m "Refresh home record" && git push
```

The record is ignored once it is more than 45 days old.
