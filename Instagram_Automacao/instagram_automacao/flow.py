from __future__ import annotations

import os
import re
import time
from pathlib import Path


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    counter = 1
    while candidate.exists():
        candidate = directory / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
        counter += 1
    return candidate


def _save_latest_result(page, download_dir: Path, timeout_ms: int) -> Path:
    more_options = page.get_by_role("button", name="Mais opções", description="Mais", exact=True)
    count = more_options.count()
    if count < 1:
        raise RuntimeError("Nenhum resultado do Google Flow está disponível para download")
    # The image overlay intercepts normal pointer clicks in the current Flow UI.
    # Activating the already-resolved button through the DOM opens the same menu.
    more_options.nth(count - 1).evaluate("element => element.click()")
    menu_item = page.get_by_role("menuitem", name="2K Aprimorada")
    menu_item.wait_for(state="visible", timeout=30_000)
    with page.expect_download(timeout=timeout_ms) as event:
        menu_item.click()
    download = event.value
    destination = _unique_destination(download_dir, download.suggested_filename)
    download.save_as(destination)
    return destination


def download_latest(*, cdp_url: str, download_dir: Path, timeout_ms: int = 180_000) -> Path:
    """Download the newest existing Flow result without starting a generation."""
    os.environ.pop("PWDEBUG", None)
    from playwright.sync_api import sync_playwright

    download_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        pages = [page for context in browser.contexts for page in context.pages if "flow.google.com" in page.url]
        if not pages:
            raise RuntimeError("Nenhuma aba do Google Flow foi encontrada no Chrome conectado")
        destination = _save_latest_result(pages[-1], download_dir, timeout_ms)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("O download do Google Flow não produziu um arquivo válido")
    return destination


def generate_one(
    *, url: str, cdp_url: str | None, prompt: str, download_dir: Path,
    chrome_profile: Path, timeout_ms: int = 180_000,
) -> Path:
    """Generate and download one image using the calibrated Portuguese Flow UI."""
    # Calibration may leave this variable set in the parent PowerShell. Production
    # runs must not pause and open Inspector unexpectedly.
    os.environ.pop("PWDEBUG", None)
    from playwright.sync_api import sync_playwright

    download_dir.mkdir(parents=True, exist_ok=True)
    chrome_profile.mkdir(parents=True, exist_ok=True)
    attached = False
    with sync_playwright() as pw:
        if cdp_url:
            try:
                browser = pw.chromium.connect_over_cdp(cdp_url)
            except Exception as error:
                raise RuntimeError(
                    f"Chrome de automação indisponível em {cdp_url}. Inicie-o com depuração local antes de gerar."
                ) from error
            if not browser.contexts:
                raise RuntimeError("O Chrome conectado não expôs nenhum contexto de navegação")
            context = browser.contexts[0]
            attached = True
        else:
            context = pw.chromium.launch_persistent_context(
                str(chrome_profile), channel="chrome", headless=False, accept_downloads=True,
            )

        flow_pages = [page for page in context.pages if "flow.google.com" in page.url]
        page = None
        for candidate in reversed(flow_pages):
            has_prompt = candidate.get_by_role("textbox", name="O que você quer criar?").count() > 0
            has_new_project = candidate.get_by_role("button", name="Novo projeto").count() > 0
            if has_prompt or has_new_project:
                page = candidate
                break
        page = page or (flow_pages[-1] if flow_pages else (context.pages[-1] if context.pages else context.new_page()))
        if "flow.google.com" not in page.url:
            page.goto(url, wait_until="domcontentloaded")

        prompt_box = page.get_by_role("textbox", name="O que você quer criar?")
        new_project = page.get_by_role("button", name="Novo projeto")
        if prompt_box.count() == 0 and new_project.count() == 0:
            page.goto(url, wait_until="domcontentloaded")
            prompt_box = page.get_by_role("textbox", name="O que você quer criar?")
            new_project = page.get_by_role("button", name="Novo projeto")
        if prompt_box.count() == 0:
            new_project.wait_for(state="visible", timeout=30_000)
            new_project.click()
        prompt_box.wait_for(state="visible", timeout=timeout_ms)
        settings = page.locator("flow-base-prompt-box").get_by_role("button", name="Configurações")
        settings.click()
        page.get_by_role("radio", name=re.compile(r"^3?:4$")).click()
        page.get_by_label("Quantidade padrão de imagens").get_by_role("radio", name="x1").click()
        page.get_by_role("button", name="Salvar").click()
        prompt_box.fill(prompt)

        more_options = page.get_by_role("button", name="Mais opções", description="Mais", exact=True)
        previous_results = more_options.count()
        page.get_by_role("button", name="Iniciar geração").click()

        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if more_options.count() > previous_results:
                break
            page.wait_for_timeout(1000)
        else:
            raise TimeoutError("O Google Flow não apresentou um novo resultado dentro do prazo")

        destination = _save_latest_result(page, download_dir, timeout_ms)
        if not attached:
            context.close()

    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("O download do Google Flow não produziu um arquivo válido")
    return destination
