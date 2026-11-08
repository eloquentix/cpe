#!/usr/bin/env python3
"""Continuously records WCPE internet radio into hourly segment files."""

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"
CHECK_INTERVAL = 30


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def last_write(storage):
    """Newest mtime among segment files, 0 if there are none."""
    newest = 0
    for p in storage.glob("wcpe_*.mp3"):
        try:
            newest = max(newest, p.stat().st_mtime)
        except FileNotFoundError:
            pass
    return newest


def stop(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run(config):
    storage = Path(config["storage_dir"])
    storage.mkdir(parents=True, exist_ok=True)

    pattern = str(storage / "wcpe_%Y%m%d_%H%M%S.mp3")
    stall = config.get("stall_seconds", 300)

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "30",
        "-rw_timeout", "30000000",
        "-i", config["stream_url"],
        "-c:a", "libmp3lame", "-b:a", f"{config.get('stream_bitrate_kbps', 128)}k",
        "-f", "segment",
        "-segment_time", str(config.get("segment_seconds", 3600)),
        "-segment_atclocktime", "1",
        "-reset_timestamps", "1",
        "-strftime", "1",
        pattern,
    ]

    # ffmpeg's -strftime uses local time; server.py parses segment names as UTC.
    env = {**os.environ, "TZ": "UTC"}

    while True:
        log(f"Recording {config['stream_url']} -> {storage}/")
        started = time.time()
        proc = subprocess.Popen(cmd, env=env)

        # ffmpeg can hang in its reconnect loop without exiting, so watch the
        # segment files rather than trusting the process to die on its own.
        while proc.poll() is None:
            try:
                proc.wait(timeout=CHECK_INTERVAL)
            except subprocess.TimeoutExpired:
                idle = time.time() - max(last_write(storage), started)
                if idle > stall:
                    log(f"No segment writes for {idle:.0f}s, killing stalled ffmpeg")
                    stop(proc)

        log(f"ffmpeg exited ({proc.returncode}), restarting in 10s...")
        time.sleep(10)


if __name__ == "__main__":
    run(load_config())
