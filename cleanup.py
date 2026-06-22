#!/usr/bin/env python3
"""Removes segment files older than the configured retention period."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def cleanup(config):
    storage = Path(config["storage_dir"])
    if not storage.exists():
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=config.get("retention_hours", 48))).timestamp()

    removed = 0
    for f in storage.glob("wcpe_*.mp3"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1

    if removed:
        print(f"Removed {removed} segment(s) older than {config.get('retention_hours', 48)}h")


if __name__ == "__main__":
    cleanup(load_config())
