# WCPE Time-Shifted Radio

Record [WCPE "The Classical Station"](https://theclassicalstation.org/) and play it
back delayed so the programming lands at the *same local clock time* for a listener in
another timezone. A listener in Bucharest hears the 8 a.m. morning show at their 8 a.m.,
not at 3 p.m.

Built for a Raspberry Pi: a recorder captures the live stream into hourly segments, and
a small HTTP server streams those segments back with a per-listener delay computed from
the listener's timezone.

## How it works

```
recorder.py  →  segments/wcpe_YYYYMMDD_HHMMSS.mp3  →  server.py  →  /stream?tz=Europe/Bucharest
                          ↑                                    ↓
                   cleanup.py (retention)            ffmpeg seek + real-time pipe
```

- **recorder.py** — `ffmpeg` records the source stream into 1-hour segments, auto-reconnecting on drop.
- **server.py** — HTTP server. Computes the delay from the listener's timezone (or a fallback), finds the matching segment, and streams it from the right offset via `ffmpeg`.
- **cleanup.py** — deletes segments older than the retention window (run on a timer).
- **duckdns.sh** — optional dynamic-DNS updater so the Pi is reachable by name.

## Endpoints

| Path | Purpose |
|---|---|
| `/` | Landing page; auto-detects browser timezone, preview player + VLC link |
| `/stream?tz=<IANA tz>` | Delayed audio stream (e.g. `tz=Europe/Bucharest`) |
| `/listen.m3u?tz=<IANA tz>` | Playlist file for VLC / audio apps |
| `/status?tz=<IANA tz>` | JSON: delay, segment count, buffered hours, readiness |

## Setup (Raspberry Pi / Debian)

```sh
./setup.sh                       # installs ffmpeg, venv, systemd units
nano config.yaml                 # set stream_url, delay, retention, port
sudo systemctl enable --now wcpe-recorder wcpe-server wcpe-cleanup.timer
curl http://localhost:8234/status
```

The stream is usable once the buffer has filled past the configured delay
(`buffered_hours >= delay_hours` in `/status`).

### Optional: dynamic DNS

```sh
cp duckdns.env.example duckdns.env   # fill in DUCKDNS_DOMAIN + DUCKDNS_TOKEN
crontab -e                           # */5 * * * * /path/to/cpe/duckdns.sh
```

`duckdns.env` is gitignored — keep your token out of version control.

## Configuration

See `config.yaml`: source `stream_url`, `storage_dir`, `segment_seconds`,
`delay_hours` (fallback when no `tz` given), `retention_hours`, `server_port`,
`stream_bitrate_kbps`.

## Requirements

- Python 3.9+ (`zoneinfo`), `ffmpeg`, `pyyaml`

## Known limitations

- **No connection limiting.** Each `/stream` connection spawns its own `ffmpeg`
  process; many simultaneous listeners can exhaust a small device. Front with a
  reverse proxy (nginx) and/or a connection cap for any real exposure.
- **No TLS / auth.** Intended for personal, low-traffic use. Put it behind a
  reverse proxy if exposing it publicly.

## Legal

This tool records and time-shifts a third-party broadcast for personal,
private listening. WCPE's stream and programming are property of The Classical
Station. Respect their terms of use and your local copyright law; do not
redistribute recordings.

## License

MIT — see [LICENSE](LICENSE). © Eloquentix Inc.
