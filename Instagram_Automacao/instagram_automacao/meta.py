from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


class MetaAPIError(RuntimeError):
    pass


def _request(url: str, data: dict | None = None) -> dict:
    encoded = urllib.parse.urlencode(data).encode() if data else None
    request = urllib.request.Request(url, data=encoded, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def credentials() -> tuple[str, str]:
    account = os.environ.get("META_IG_USER_ID")
    token = os.environ.get("META_ACCESS_TOKEN")
    if not account or not token:
        raise MetaAPIError(
            "Defina META_IG_USER_ID e META_ACCESS_TOKEN nas variáveis do Windows; não coloque segredos em arquivos."
        )
    return account, token


def verify_account(expected_username: str, api_version: str) -> tuple[str, str]:
    account, token = credentials()
    query = urllib.parse.urlencode({"fields": "username", "access_token": token})
    response = _request(f"https://graph.facebook.com/{api_version}/{account}?{query}")
    actual = str(response.get("username", "")).lstrip("@").casefold()
    expected = expected_username.lstrip("@").casefold()
    if not actual or actual != expected:
        raise MetaAPIError(
            f"Conta bloqueada por segurança: esperada @{expected}, API retornou @{actual or 'desconhecida'}"
        )
    return account, actual


def publish_image(image_url: str, caption: str, api_version: str, expected_username: str) -> str:
    """Publish through the official Instagram Graph API; image_url must be public HTTPS."""
    if not image_url.lower().startswith("https://"):
        raise MetaAPIError("A Instagram Graph API exige uma image_url pública em HTTPS")
    account, _ = verify_account(expected_username, api_version)
    _, token = credentials()
    base = f"https://graph.facebook.com/{api_version}/{account}"
    created = _request(f"{base}/media", {"image_url": image_url, "caption": caption, "access_token": token})
    container = created.get("id")
    if not container:
        raise MetaAPIError(f"A API não criou o contêiner: {created}")
    published = _request(f"{base}/media_publish", {"creation_id": container, "access_token": token})
    remote_id = published.get("id")
    if not remote_id:
        raise MetaAPIError(f"A API não confirmou a publicação: {published}")
    return str(remote_id)
