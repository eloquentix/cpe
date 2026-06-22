#!/usr/bin/env python3
"""Continuously records WCPE internet radio into hourly segment files."""

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def run(config):
    storage = Path(config["storage_dir"])
    storage.mkdir(parents=True, exist_ok=True)

    pattern = str(storage / "wcpe_%Y%m%d_%H%M%S.mp3")

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "30",
        "-i", config["stream_url"],
        "-c:a", "libmp3lame", "-b:a", f"{config.get('stream_bitrate_kbps', 128)}k",
        "-f", "segment",
        "-segment_time", str(config.get("segment_seconds", 3600)),
        "-segment_atclocktime", "1",
        "-reset_timestamps", "1",
        "-strftime", "1",
        pattern,
    ]

    while True:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{ts}] Recording {config['stream_url']} -> {storage}/")
        proc = subprocess.run(cmd)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{ts}] ffmpeg exited ({proc.returncode}), restarting in 10s...")
        time.sleep(10)


if __name__ == "__main__":
    run(load_config())
