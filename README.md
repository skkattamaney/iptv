# iptv

An English-only playlist built from the public [iptv-org](https://github.com/iptv-org/iptv) lists.

Playlist address: https://skkattamaney.github.io/iptv/english-channels.m3u

Ghana, UK and US channels come first, grouped by country and category ("UK: News", "US: Sports"). English-language channels from every other country follow under "World".

A GitHub Actions job runs `build.py` once a day, so dead streams drop out and new ones appear without any manual work. The repository holds links to streams that are already public. It hosts no video.
