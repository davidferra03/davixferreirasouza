from __future__ import annotations

import platform
import re
from datetime import datetime, timezone

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def redact(text: str) -> str:
    return EMAIL.sub("[email ocultado]", text)


def parse_accounts(diagnostic: dict) -> list[dict]:
    """Associate accessible descendants with their enclosing account card."""
    controls = diagnostic.get("controls", [])
    accounts = []
    for item in controls:
        match = re.fullmatch(r"Conta @([A-Za-z0-9._]+)", item.get("name", "").strip())
        if not match or item.get("control_type") != "ListItem":
            continue
        bounds = item["rectangle"]
        children = [
            control for control in controls
            if control is not item
            and bounds["top"] <= control.get("rectangle", {}).get("top", -1) < bounds["bottom"]
            and bounds["left"] <= control.get("rectangle", {}).get("left", -1) <= bounds["right"]
        ]
        names = [control.get("name", "") for control in children]
        username = match.group(1)
        blocked = any("bloqueada nas tarefas do bot" in name.casefold() for name in names)
        avatar = any(
            control.get("control_type") == "Image" and f"@{username}" in control.get("name", "")
            for control in children
        )
        accounts.append({
            "username": username,
            "complete": not blocked,
            "blocked": blocked,
            "avatar_complete": avatar,
            "can_verify": any("verificar o perfil" in name.casefold() for name in names),
            "can_open_browser": any("abrir navegador" in name.casefold() for name in names),
            "can_close_browser": any("fechar navegador" in name.casefold() for name in names),
        })
    return accounts


def inspect_window() -> dict:
    """Export the visible UI Automation tree without clicking or typing."""
    if platform.system() != "Windows":
        raise RuntimeError("A inspeção do VEM ENGAJAR BOT requer execução local no Windows")
    from pywinauto import Desktop

    matches = Desktop(backend="uia").windows(title_re=".*VEM ENGAJAR BOT.*")
    if not matches:
        raise RuntimeError("Janela do VEM ENGAJAR BOT não encontrada")
    window = matches[0]
    controls = []
    seen = set()
    for control in [window, *window.descendants()]:
        try:
            name = redact(control.window_text().strip())
            info = control.element_info
            control_type = str(info.control_type or "")
            automation_id = str(info.automation_id or "")
            rectangle = control.rectangle()
        except Exception:
            continue
        if not name and not automation_id:
            continue
        key = (name, control_type, automation_id, rectangle.left, rectangle.top)
        if key in seen:
            continue
        seen.add(key)
        controls.append({
            "name": name[:500],
            "control_type": control_type,
            "automation_id": automation_id,
            "rectangle": {
                "left": rectangle.left,
                "top": rectangle.top,
                "right": rectangle.right,
                "bottom": rectangle.bottom,
            },
        })
        if len(controls) >= 1000:
            break
    if not controls:
        raise RuntimeError("A janela não expôs texto via UI Automation; use a exportação/manual assistida")
    diagnostic = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window_title": redact(window.window_text()),
        "read_only": True,
        "control_count": len(controls),
        "controls": controls,
    }
    diagnostic["accounts"] = parse_accounts(diagnostic)
    return diagnostic
