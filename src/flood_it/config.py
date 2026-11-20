"""Load config/config.yaml and resolve project-relative paths."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]

    @property
    def bq(self) -> dict[str, Any]:
        return self.raw["bigquery"]

    @property
    def analysis(self) -> dict[str, Any]:
        return self.raw["analysis"]

    def path(self, key: str) -> Path:
        p = ROOT / self.raw["paths"][key]
        if p.suffix == "":  # directory
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def default_params(self) -> dict[str, Any]:
        """Default query parameters shared by all SQL files."""
        a = self.analysis
        return {"start_suffix": a["start_suffix"], "end_suffix": a["end_suffix"]}


@lru_cache(maxsize=1)
def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else ROOT / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return Config(yaml.safe_load(f))
