from __future__ import annotations

from pathlib import Path


class FlowConfigurationError(RuntimeError):
    pass


def validate_selectors(selectors: dict[str, str]) -> None:
    required = {"image_mode", "aspect_ratio", "prompt", "generate", "result", "download"}
    missing = sorted(required - selectors.keys())
    if missing:
        raise FlowConfigurationError(
            "Seletores do Google Flow ainda não calibrados neste Chrome: " + ", ".join(missing)
        )


def generate_one(
    *, url: str, selectors: dict[str, str], prompt: str, download_dir: Path,
    chrome_profile: Path, timeout_ms: int = 180_000,
) -> Path:
    """Generate exactly one asset in a dedicated Chrome profile.

    Authentication is performed by the user in this profile. No cookies or tokens
    are read or exported. UI selectors are explicit because Flow changes often.
    """
    validate_selectors(selectors)
    from playwright.sync_api import sync_playwright

    download_dir.mkdir(parents=True, exist_ok=True)
    chrome_profile.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(chrome_profile), channel="chrome", headless=False, accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.locator(selectors["image_mode"]).click()
        page.locator(selectors["aspect_ratio"]).click()
        page.locator(selectors["prompt"]).fill(prompt)
        page.locator(selectors["generate"]).click()
        result = page.locator(selectors["result"]).first
        result.wait_for(state="visible", timeout=timeout_ms)
        with page.expect_download(timeout=timeout_ms) as event:
            page.locator(selectors["download"]).first.click()
        download = event.value
        destination = download_dir / download.suggested_filename
        download.save_as(destination)
        context.close()
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("O download do Google Flow não produziu um arquivo válido")
    return destination
