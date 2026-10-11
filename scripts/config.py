"""Loads profile.json (repo root). Every script reads its text from here."""
import datetime as dt
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load():
    path = os.environ.get("PROFILE_JSON") or os.path.join(ROOT, "profile.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    hm = cfg.setdefault("heatmap", {})
    hm.setdefault("total", 1000)
    hm.setdefault("seed", 29)
    end = hm.get("end_date") or ""
    hm["end"] = dt.date.fromisoformat(end) if end else dt.date.today()
    cfg.setdefault("portrait", {}).setdefault("crop", "")
    cfg["handle"] = (cfg.get("handle") or cfg["github_username"]).lower()
    return cfg
