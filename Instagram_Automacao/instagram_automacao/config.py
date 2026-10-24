from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path
    profiles: int = 9
    target_posts: int = 7
    min_delay_seconds: int = 30
    max_delay_seconds: int = 60
    flow_url: str = "https://labs.google/fx/tools/flow"
    flow_selectors: dict[str, str] = field(default_factory=dict)
    instagram_api_version: str = "v24.0"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        root = Path(os.environ.get("INSTAGRAM_AUTOMACAO_HOME", Path.cwd())).resolve()
        path = config_path or root / "config.toml"
        raw: dict = {}
        if path.exists():
            with path.open("rb") as fh:
                raw = tomllib.load(fh)
        app = raw.get("app", {})
        flow = raw.get("google_flow", {})
        meta = raw.get("meta", {})
        return cls(
            root=root,
            profiles=int(app.get("profiles", 9)),
            target_posts=int(app.get("target_posts", 7)),
            min_delay_seconds=int(app.get("min_delay_seconds", 30)),
            max_delay_seconds=int(app.get("max_delay_seconds", 60)),
            flow_url=str(flow.get("url", cls.flow_url)),
            flow_selectors=dict(flow.get("selectors", {})),
            instagram_api_version=str(meta.get("api_version", "v24.0")),
        )
