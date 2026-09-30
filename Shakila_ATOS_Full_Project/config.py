"""Central config loader. All YAML files live in configs/, camera JSON in configs/cameras/."""
import json
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def path(*parts) -> Path:
    return ROOT.joinpath(*parts)


@lru_cache(maxsize=None)
def cfg(name: str) -> dict:
    """cfg('detector') -> dict from configs/detector.yaml"""
    with open(path("configs", f"{name}.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=None)
def camera(cam_id: str) -> dict:
    with open(path("configs", "cameras", f"{cam_id}.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def all_cameras() -> list:
    return [camera(p.stem) for p in sorted(path("configs", "cameras").glob("CAM*.json"))]


def env(name: str, default=None):
    return os.environ.get(name, default)


def database_url() -> str:
    url = env("DATABASE_URL")
    if url:
        return url
    return "sqlite:///" + str(path("storage", "atos.db"))
