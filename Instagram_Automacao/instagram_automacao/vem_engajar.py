from __future__ import annotations

import getpass
import os
import platform
import re
from datetime import datetime, timezone

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
ACCOUNT_COUNT = re.compile(r"\b(\d+)\s+contas?\b", re.IGNORECASE)
TAB_ACCOUNT_COUNT = re.compile(r"\btodas\s+as\s+contas\s*[:(\[]?\s*(\d+)\b", re.IGNORECASE)
POST_COUNT = re.compile(r"\btem\s+(\d+)\s*,\s*m[ií]nimo\s+(\d+)\b", re.IGNORECASE)


def redact(text: str) -> str:
    return EMAIL.sub("[email ocultado]", text)


def expected_account_count(diagnostic: dict) -> int | None:
    """Read one consistent explicit account counter from the VEM UI."""
    values = []
    for control in diagnostic.get("controls", []):
        name = control.get("name", "")
        for pattern in (ACCOUNT_COUNT, TAB_ACCOUNT_COUNT):
            for match in pattern.finditer(name):
                values.append(int(match.group(1)))
    unique = sorted(set(values))
    if len(unique) > 1:
        raise ValueError("contadores totais conflitantes: " + ", ".join(map(str, unique)))
    return unique[0] if unique else None


def parse_accounts(diagnostic: dict) -> list[dict]:
    """Associate accessible descendants with an account card conservatively.

    Missing UIA text, card geometry and the presence of an avatar are not
    evidence that a requirement is complete. Only the explicit ``Perfil
    completo`` badge may promote an observation to complete.
    """
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
        folded = [name.casefold() for name in names]
        blocked = any("bloqueada nas tarefas do bot" in name for name in folded)
        complete_badge = any("perfil completo" in name for name in folded)
        missing = [name.strip() for name in names if "falta:" in name.casefold()]
        has_missing = bool(missing)
        avatar_image = any(
            control.get("control_type") == "Image" and f"@{username}" in control.get("name", "")
            for control in children
        )
        can_verify = any("verificar o perfil" in name for name in folded)
        can_open_browser = any("abrir navegador" in name for name in folded)
        can_close_browser = any("fechar navegador" in name for name in folded)
        conflicting = complete_badge and (has_missing or blocked)
        if conflicting:
            status = "unknown"
            complete = None
            status_evidence = "conflicting_badges"
        elif complete_badge:
            status = "complete"
            complete = True
            status_evidence = "explicit_complete_badge"
        elif has_missing or blocked:
            status = "pending"
            complete = False
            status_evidence = "explicit_pending_warning"
        else:
            status = "unknown"
            complete = None
            status_evidence = "insufficient_evidence"
        missing_avatar = any(
            "falta:" in name and ("avatar" in name or "foto" in name)
            for name in folded
        )
        missing_biography = any("falta:" in name and "biografia" in name for name in folded)
        posts_existing = None
        posts_minimum = None
        for name in names:
            posts_match = POST_COUNT.search(name)
            if posts_match:
                posts_existing = int(posts_match.group(1))
                posts_minimum = int(posts_match.group(2))
                break

        if complete is True:
            avatar_complete = True
            biography_complete = True
        else:
            avatar_complete = True if avatar_image else (False if missing_avatar else None)
            biography_complete = False if missing_biography else None

        accounts.append({
            "username": username,
            "status": status,
            "status_evidence": status_evidence,
            "complete": complete,
            "blocked": blocked,
            "avatar_complete": avatar_complete,
            "biography_complete": biography_complete,
            "posts_existing": posts_existing,
            "posts_minimum": posts_minimum,
            "missing": missing,
            "can_verify": can_verify,
            "can_open_browser": can_open_browser,
            "can_close_browser": can_close_browser,
        })
    return accounts


def validate_diagnostic(
    diagnostic: dict, *, allowed_unknown_usernames: set[str] | None = None,
) -> dict:
    """Reject partial/ambiguous captures before they can alter local state.

    An unknown observation may pass only as a preservation exception for a
    username already confirmed complete in local state. It must still expose a
    profile image and no blocked warning; it is never promoted from UIA data.
    """
    accounts = diagnostic.get("accounts") or parse_accounts(diagnostic)
    allowed = {username.strip().lstrip("@").casefold() for username in (allowed_unknown_usernames or set())}
    try:
        expected = expected_account_count(diagnostic)
        count_error = None
    except ValueError as error:
        expected = None
        count_error = str(error)
    errors = []
    warnings = []
    usernames = [str(account.get("username", "")).strip().casefold() for account in accounts]
    if count_error:
        errors.append(count_error)
    elif expected is None:
        errors.append("contador total de contas não encontrado")
    elif expected != len(accounts):
        errors.append(f"contador indica {expected}, mas {len(accounts)} cartões foram lidos")
    if not accounts:
        errors.append("nenhuma conta foi identificada")
    if any(not username for username in usernames):
        errors.append("existe conta sem username")
    if len(usernames) != len(set(usernames)):
        errors.append("existem usernames duplicados")
    for account in accounts:
        status = account.get("status")
        if status in {"complete", "pending"}:
            continue
        username = str(account.get("username", "")).strip().lstrip("@")
        normalized_username = username.casefold()
        if status != "unknown":
            errors.append(f"estado inválido para {username}: {status!r}")
        elif account.get("status_evidence") == "conflicting_badges":
            errors.append(f"selos conflitantes para {username}")
        elif account.get("missing"):
            errors.append(f"estado desconhecido com requisitos pendentes para {username}")
        elif normalized_username not in allowed:
            errors.append(f"estado sem evidência explícita: {username}")
        elif account.get("blocked") is not False:
            errors.append(f"perfil local completo apareceu bloqueado: {username}")
        elif account.get("avatar_complete") is not True:
            errors.append(f"perfil local completo sem avatar confirmado na captura: {username}")
        else:
            warnings.append(
                f"estado UIA não exposto para {username}; perfil local completo será apenas preservado"
            )
    return {
        "valid": not errors,
        "expected_account_count": expected,
        "observed_account_count": len(accounts),
        "errors": errors,
        "warnings": warnings,
    }


def inspect_window() -> dict:
    """Export the visible UI Automation tree without clicking or typing."""
    if platform.system() != "Windows":
        raise RuntimeError("A inspeção do VEM ENGAJAR BOT requer execução local no Windows")
    from pywinauto import Desktop

    candidates = []
    for window in Desktop(backend="uia").windows(visible_only=False):
        try:
            title = window.window_text().strip()
            folded = title.casefold()
            if not all(token in folded for token in ("vem", "engajar", "bot")):
                continue
            rectangle = window.rectangle()
            area = max(0, rectangle.width()) * max(0, rectangle.height())
            exact_title = folded in {"vem engajar bot", "bot vem engajar"}
            candidates.append((exact_title, bool(window.is_visible()), area, title, window))
        except Exception:
            continue
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    if not candidates:
        current_user = getpass.getuser()
        session = os.environ.get("SESSIONNAME", "desconhecida")
        raise RuntimeError(
            "Janela do VEM ENGAJAR BOT não encontrada no mesmo desktop do "
            f"usuário {current_user} (sessão {session}). Execute este comando "
            "no PowerShell do mesmo usuário que abriu o VEM."
        )
    window = candidates[0][4]
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
    diagnostic["validation"] = validate_diagnostic(diagnostic)
    return diagnostic
