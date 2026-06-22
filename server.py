#!/usr/bin/env python3
"""HTTP server that streams WCPE audio delayed to match the listener's local time.

    Listen: http://<host>:<port>/
    Stream: http://<host>:<port>/stream?tz=Europe/Bucharest
    Status: http://<host>:<port>/status
"""

import http.server
import json
import re
import subprocess
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"
SEGMENT_RE = re.compile(r"wcpe_(\d{8}_\d{6})\.mp3$")
WCPE_TZ = ZoneInfo("America/New_York")


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def calculate_delay(user_tz_name):
    try:
        user_tz = ZoneInfo(user_tz_name)
    except (KeyError, Exception):
        return None

    now = datetime.now(timezone.utc)
    wcpe_offset = now.astimezone(WCPE_TZ).utcoffset().total_seconds() / 3600
    user_offset = now.astimezone(user_tz).utcoffset().total_seconds() / 3600

    return (24 - (user_offset - wcpe_offset)) % 24


def parse_segment_time(name):
    m = SEGMENT_RE.search(name)
    if m:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    return None


def available_segments(storage_dir):
    segments = []
    for p in Path(storage_dir).glob("wcpe_*.mp3"):
        t = parse_segment_time(p.name)
        if t and p.stat().st_size > 0:
            segments.append((t, p))
    segments.sort()
    return segments


def find_segment(segments, target):
    hit = None
    for start, path in segments:
        if start <= target:
            hit = (start, path)
        else:
            break
    return hit


LANDING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WCPE Time-Shifted</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 20px; color: #222; }
  h1 { font-size: 1.4em; }
  .info { color: #555; margin: 12px 0; }
  audio { width: 100%; margin: 20px 0; }
  .btn { display: inline-block; padding: 12px 24px; background: #1a5276; color: #fff;
         text-decoration: none; border-radius: 6px; font-size: 1em; margin: 8px 4px 8px 0; }
  .btn:active { background: #154360; }
  .note { font-size: 0.85em; color: #888; margin-top: 20px; }
</style>
</head>
<body>
<h1>WCPE Time-Shifted</h1>
<p class="info">Your timezone: <strong id="tz">detecting...</strong></p>
<p class="info">Delay: <strong id="delay">--</strong> hours</p>
<a id="vlc-link" class="btn" href="/listen.m3u">Open in VLC</a>
<p class="note">Tap the button to open the stream in VLC (or any audio app).<br>
This keeps playing when you lock your phone or switch apps.</p>
<hr style="margin: 24px 0; border: none; border-top: 1px solid #ddd;">
<p class="info" style="font-size: 0.9em;">Quick preview (stops when you leave the browser):</p>
<audio id="player" controls preload="none"></audio>
<script>
const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
document.getElementById('tz').textContent = tz;
const tzParam = encodeURIComponent(tz);
document.getElementById('player').src = '/stream?tz=' + tzParam;
document.getElementById('vlc-link').href = '/listen.m3u?tz=' + tzParam;
fetch('/status?tz=' + tzParam)
  .then(r => r.json())
  .then(d => {
    document.getElementById('delay').textContent = d.delay_hours;
    if (!d.ready) document.getElementById('delay').textContent += ' (buffering, not ready yet)';
  });

if ('mediaSession' in navigator) {
  const player = document.getElementById('player');
  player.addEventListener('play', () => {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: 'WCPE Time-Shifted',
      artist: 'The Classical Station',
      album: tz
    });
    navigator.mediaSession.setActionHandler('play', () => player.play());
    navigator.mediaSession.setActionHandler('pause', () => player.pause());
  });
}
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {self.client_address[0]} {fmt % args}")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_landing()
        elif path in ("/stream", "/stream.mp3"):
            self._serve_stream(parsed.query)
        elif path == "/listen.m3u":
            self._serve_playlist(parsed.query)
        elif path == "/status":
            self._serve_status(parsed.query)
        else:
            self.send_error(404)

    def _resolve_delay(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        tz_name = params.get("tz", [None])[0]

        if tz_name:
            delay = calculate_delay(tz_name)
            if delay is not None:
                return delay

        return self.server.config["delay_hours"]

    def _serve_landing(self):
        body = LANDING_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_playlist(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        tz_name = params.get("tz", [None])[0]
        host = self.headers.get("Host", "localhost:8234")

        tz_param = f"?tz={urllib.parse.quote(tz_name)}" if tz_name else ""
        stream_url = f"http://{host}/stream{tz_param}"

        body = f"#EXTM3U\n#EXTINF:-1,WCPE Time-Shifted\n{stream_url}\n".encode()

        self.send_response(200)
        self.send_header("Content-Type", "audio/x-mpegurl")
        self.send_header("Content-Disposition", 'attachment; filename="wcpe-shifted.m3u"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self, query_string):
        cfg = self.server.config
        delay_hours = self._resolve_delay(query_string)
        segs = available_segments(cfg["storage_dir"])
        now = datetime.now(timezone.utc)

        oldest = segs[0][0] if segs else None
        buffered = ((now - oldest).total_seconds() / 3600) if oldest else 0

        body = json.dumps({
            "delay_hours": round(delay_hours, 1),
            "segments": len(segs),
            "oldest": oldest.isoformat() if oldest else None,
            "newest": segs[-1][0].isoformat() if segs else None,
            "buffered_hours": round(buffered, 1),
            "ready": buffered >= delay_hours,
        }, indent=2).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_stream(self, query_string):
        cfg = self.server.config
        delay_hours = self._resolve_delay(query_string)

        if delay_hours == 0:
            self.send_response(302)
            self.send_header("Location", cfg["stream_url"])
            self.end_headers()
            return

        delay = timedelta(hours=delay_hours)

        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("icy-name", "WCPE Time-Shifted")
        self.send_header("icy-br", str(cfg.get("stream_bitrate_kbps", 128)))
        self.end_headers()

        self.log_message("stream started (delay=%.1fh)", delay_hours)

        try:
            self._stream_loop(cfg, delay)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

        self.log_message("stream ended")

    def _stream_loop(self, cfg, delay):
        while True:
            target = datetime.now(timezone.utc) - delay
            segs = available_segments(cfg["storage_dir"])
            seg = find_segment(segs, target)

            if seg is None:
                time.sleep(5)
                continue

            start_time, path = seg
            offset = max(0, (target - start_time).total_seconds())

            proc = subprocess.Popen(
                [
                    "ffmpeg", "-v", "quiet",
                    "-ss", f"{offset:.1f}",
                    "-i", str(path),
                    "-c", "copy", "-f", "mp3", "-re",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            try:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


def main():
    cfg = load_config()
    port = cfg.get("server_port", 8234)

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    srv.config = cfg

    print(f"WCPE delayed stream | port {port}")
    print(f"  Listen:  http://0.0.0.0:{port}/")
    print(f"  Stream:  http://0.0.0.0:{port}/stream?tz=Europe/Bucharest")
    print(f"  Status:  http://0.0.0.0:{port}/status")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
