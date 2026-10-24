from __future__ import annotations

import json
from pathlib import Path

from .config import Settings
from .flow import generate_one
from .images import fit_three_by_four
from .meta import publish_image
from .queue import claim_next, fail, finish, is_paused, stable_delay
from .storage import connect, register_asset


def _profile(root: Path, profile_id: int) -> dict:
    with connect(root) as con:
        row = con.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
    if row is None:
        raise ValueError(f"Perfil inexistente: {profile_id}")
    return dict(row)


def execute(settings: Settings, task: dict) -> dict:
    payload = json.loads(task["payload_json"])
    profile = _profile(settings.root, task["profile_id"])
    if profile["status"] == "complete":
        return {"skipped": "perfil já estava completo"}
    if task["kind"] == "generate":
        target = settings.root / profile["slot"] / "publicacoes"
        downloaded = generate_one(
            url=settings.flow_url,
            cdp_url=settings.flow_cdp_url,
            prompt=payload["prompt"],
            download_dir=target,
            chrome_profile=settings.root / ".chrome-flow",
        )
        asset_id = register_asset(settings.root, profile["id"], "publication", downloaded, payload["prompt"])
        return {"asset_id": asset_id, "path": str(downloaded)}
    if task["kind"] == "fit_image":
        output = fit_three_by_four(Path(payload["source"]), Path(payload["destination"]), payload.get("mode", "pad"))
        asset_id = register_asset(settings.root, profile["id"], payload.get("asset_kind", "publication"), output)
        return {"asset_id": asset_id, "path": str(output)}
    if task["kind"] == "publish":
        if not profile["instagram_username"]:
            raise RuntimeError("Perfil sem username confirmado")
        with connect(settings.root) as con:
            already = con.execute(
                "SELECT id FROM publications WHERE idempotency_key=? AND status='published'",
                (task["idempotency_key"],),
            ).fetchone()
        if already:
            return {"skipped": "publicação já confirmada"}
        remote_id = publish_image(
            payload["image_url"], payload.get("caption", ""), settings.instagram_api_version,
            profile["instagram_username"],
        )
        with connect(settings.root) as con:
            con.execute(
                "INSERT INTO publications(profile_id, asset_id, remote_id, status, idempotency_key, published_at) VALUES (?, ?, ?, 'published', ?, datetime('now'))",
                (profile["id"], payload["asset_id"], remote_id, task["idempotency_key"]),
            )
            con.execute("UPDATE profiles SET posts_existing=posts_existing+1 WHERE id=?", (profile["id"],))
        return {"remote_id": remote_id}
    raise ValueError(f"Tipo de tarefa não suportado: {task['kind']}")


def run(settings: Settings, once: bool = False) -> int:
    completed = 0
    while not is_paused(settings.root):
        task = claim_next(settings.root)
        if task is None:
            break
        try:
            finish(settings.root, task["id"], execute(settings, task))
            completed += 1
        except Exception as error:
            # External UI/login/security failures need review, not blind retries.
            fail(settings.root, task["id"], error, retry=False)
        if once:
            break
        if not is_paused(settings.root):
            stable_delay(settings.min_delay_seconds, settings.max_delay_seconds)
    return completed
