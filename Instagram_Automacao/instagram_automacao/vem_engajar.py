from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class AccountStatus:
    username: str
    complete: bool
    missing_biography: bool = False
    missing_avatar: bool = False
    current_posts: int | None = None


def inspect_window() -> list[AccountStatus]:
    """Read visible UI Automation text only; performs no task/interactions."""
    if platform.system() != "Windows":
        raise RuntimeError("A inspeção do VEM ENGAJAR BOT requer execução local no Windows")
    from pywinauto import Desktop

    matches = Desktop(backend="uia").windows(title_re=".*VEM ENGAJAR BOT.*")
    if not matches:
        raise RuntimeError("Janela do VEM ENGAJAR BOT não encontrada")
    texts = "\n".join(matches[0].texts())
    # The application exposes no documented API in the supplied material. Keep
    # discovery read-only until its actual UIA tree can be calibrated locally.
    if not texts.strip():
        raise RuntimeError("A janela não expôs texto via UI Automation; use a exportação/manual assistida")
    return []
