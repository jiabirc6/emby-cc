#!/usr/bin/env python3
"""Generate config.toml for keepalive deployment"""
import os

config = """[general]
version = "1.0.0"
log_level = "info"

[notifications]
enabled = false

[[accounts]]
name = "lite"
emby_url = "https://lite.cn2gias.uk:443"
username = "jiabir"
password = "cjb123456"
api_key = ""
telegram_bot_token = ""

[accounts.keepalive]
enabled = true
interval_hours = 6
min_minutes = 30
max_minutes = 120

[accounts.checkin]
telegram_bots = []
"""

config_path = os.path.join(os.path.dirname(__file__), "config.toml")
with open(config_path, "w", encoding="utf-8") as f:
    f.write(config)
print(f"Written {len(config)} bytes to {config_path}")
