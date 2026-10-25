import json
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from instagram_automacao.flow import _unique_destination
from instagram_automacao import cli
from instagram_automacao.images import fit_three_by_four
from instagram_automacao.queue import add_task, claim_next, finish, is_paused, set_paused
from instagram_automacao.storage import add_profile, connect, initialize, sync_bot_accounts, update_profile
from instagram_automacao.vem_engajar import parse_accounts, redact, validate_diagnostic


def test_initialize_and_queue_are_idempotent(tmp_path: Path):
    initialize(tmp_path)
    first = add_profile(tmp_path, "perfil_virtual_1")
    second = add_profile(tmp_path)
    initialize(tmp_path)
    assert first["id"] == 1
    assert second["id"] == 2
    assert (tmp_path / "Perfil_01" / "publicacoes").is_dir()
    assert is_paused(tmp_path)
    set_paused(tmp_path, False)
    add_task(tmp_path, 1, "generate", {"prompt": "virtual character"}, "p1-generate-1")
    add_task(tmp_path, 1, "generate", {"prompt": "virtual character"}, "p1-generate-1")
    task = claim_next(tmp_path)
    assert task and task["kind"] == "generate"
    finish(tmp_path, task["id"], {"ok": True})
    assert claim_next(tmp_path) is None
    with connect(tmp_path) as con:
        assert con.execute("select count(*) from tasks").fetchone()[0] == 1


def test_profiles_are_dynamic_without_fixed_limit(tmp_path: Path):
    initialize(tmp_path)
    created = [add_profile(tmp_path) for _ in range(25)]
    assert created[-1]["slot"] == "Perfil_25"
    with connect(tmp_path) as con:
        assert con.execute("select count(*) from profiles").fetchone()[0] == 25
    assert (tmp_path / "Perfil_25" / "avatar").is_dir()


def test_bot_diagnostic_redacts_email_addresses():
    assert redact("conta usuario@example.com ativa") == "conta [email ocultado] ativa"
    assert redact("@perfil_virtual") == "@perfil_virtual"


def test_flow_download_never_overwrites(tmp_path: Path):
    existing = tmp_path / "imagem.png"
    existing.write_bytes(b"existing")
    assert _unique_destination(tmp_path, "imagem.png") == tmp_path / "imagem-1.png"


def test_parse_and_sync_bot_accounts(tmp_path: Path):
    diagnostic = {
        "controls": [
            {"name": "2 contas", "control_type": "Text", "rectangle": {"left": 1, "top": 1, "right": 100, "bottom": 20}},
            {"name": "Conta @pendente", "control_type": "ListItem", "rectangle": {"left": 10, "top": 100, "right": 500, "bottom": 200}},
            {"name": "Falta: Biografia", "control_type": "Text", "rectangle": {"left": 20, "top": 120, "right": 180, "bottom": 135}},
            {"name": "Falta: Publicações no feed (tem 0, mínimo 7)", "control_type": "Text", "rectangle": {"left": 190, "top": 120, "right": 450, "bottom": 135}},
            {"name": "Bloqueada nas tarefas do bot até completar o perfil", "control_type": "Text", "rectangle": {"left": 20, "top": 130, "right": 400, "bottom": 150}},
            {"name": "Abrir navegador da conta @pendente", "control_type": "Button", "rectangle": {"left": 20, "top": 160, "right": 120, "bottom": 180}},
            {"name": "Conta @completo", "control_type": "ListItem", "rectangle": {"left": 10, "top": 200, "right": 500, "bottom": 300}},
            {"name": "Foto de perfil de @completo", "control_type": "Image", "rectangle": {"left": 20, "top": 220, "right": 60, "bottom": 260}},
            {"name": "Perfil completo", "control_type": "Text", "rectangle": {"left": 70, "top": 220, "right": 180, "bottom": 240}},
            {"name": "Verificar o perfil da conta @completo", "control_type": "Button", "rectangle": {"left": 20, "top": 270, "right": 120, "bottom": 290}},
        ]
    }
    accounts = parse_accounts(diagnostic)
    diagnostic["accounts"] = accounts
    assert validate_diagnostic(diagnostic)["valid"]
    assert accounts[0]["status"] == "pending"
    assert accounts[0]["complete"] is False
    assert accounts[0]["avatar_complete"] is None
    assert accounts[0]["biography_complete"] is False
    assert accounts[0]["posts_existing"] == 0
    assert accounts[1]["status"] == "complete"
    assert accounts[1]["complete"] is True
    assert accounts[1]["avatar_complete"] is True
    assert accounts[1]["biography_complete"] is True
    initialize(tmp_path)
    synced = sync_bot_accounts(tmp_path, accounts, 7)
    assert len(synced) == 2
    with connect(tmp_path) as con:
        rows = con.execute("SELECT instagram_username, status, posts_existing FROM profiles ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [("pendente", "pending", 0), ("completo", "complete", 7)]


def test_bot_capture_requires_counter_unique_accounts_and_explicit_status():
    controls = [
        {"name": "3 contas", "control_type": "Text", "rectangle": {}},
        {"name": "Conta @sem_estado", "control_type": "ListItem", "rectangle": {"left": 0, "top": 10, "right": 100, "bottom": 20}},
        {"name": "Conta @sem_estado", "control_type": "ListItem", "rectangle": {"left": 0, "top": 20, "right": 100, "bottom": 30}},
    ]
    diagnostic = {"controls": controls}
    diagnostic["accounts"] = parse_accounts(diagnostic)
    validation = validate_diagnostic(diagnostic)
    assert not validation["valid"]
    assert any("contador indica 3" in error for error in validation["errors"])
    assert any("duplicados" in error for error in validation["errors"])
    assert any("sem evidência" in error for error in validation["errors"])


def test_bot_sync_dry_run_is_read_only_and_complete_profiles_are_preserved(tmp_path: Path):
    initialize(tmp_path)
    complete = add_profile(tmp_path, "ja_completo")
    update_profile(
        tmp_path, complete["id"], username="ja_completo", display_name="Preservar",
        biography="Pronta", avatar_complete=True, biography_complete=True,
        posts_existing=12, complete=True,
    )
    accounts = [
        {
            "username": "ja_completo", "status": "pending", "complete": False,
            "avatar_complete": False, "biography_complete": False, "posts_existing": 0,
        },
        {
            "username": "novo", "status": "pending", "complete": False,
            "avatar_complete": None, "biography_complete": False, "posts_existing": 2,
        },
    ]
    state = tmp_path / "state.sqlite3"
    report = tmp_path / "relatorio.json"
    profile_file = tmp_path / complete["slot"] / "biografia.txt"
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (state, report, profile_file)
    }
    preview = sync_bot_accounts(tmp_path, accounts, 7, dry_run=True)
    assert preview[0]["action"] == "skipped_complete"
    assert preview[1]["action"] == "would_create"
    assert not (tmp_path / "Perfil_02").exists()
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (state, report, profile_file)
    } == before
    with connect(tmp_path) as con:
        rows = con.execute(
            "SELECT instagram_username, status, posts_existing FROM profiles ORDER BY id"
        ).fetchall()
    assert [tuple(row) for row in rows] == [("ja_completo", "complete", 12)]


def test_inspect_cli_only_writes_requested_diagnostic(tmp_path: Path, monkeypatch):
    diagnostic = {
        "captured_at": "2026-10-25T00:00:00+00:00",
        "window_title": "BOT VEM ENGAJAR",
        "read_only": True,
        "control_count": 1,
        "controls": [],
        "accounts": [],
        "validation": {
            "valid": False, "expected_account_count": None,
            "observed_account_count": 0, "errors": ["captura vazia"],
        },
    }
    monkeypatch.setattr(cli.Settings, "load", lambda _: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr(cli, "inspect_window", lambda: diagnostic)
    monkeypatch.setattr(sys, "argv", ["instagram-automacao", "inspect-bot"])
    cli.main()
    output = tmp_path / "logs" / "vem_engajar_uia.json"
    assert json.loads(output.read_text(encoding="utf-8")) == diagnostic
    assert sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")) == [
        "logs", "logs/vem_engajar_uia.json",
    ]


def test_sync_cli_dry_run_does_not_initialize_or_rewrite_state(tmp_path: Path, monkeypatch):
    initialize(tmp_path)
    profile = add_profile(tmp_path, "existente")
    state = tmp_path / "state.sqlite3"
    report = tmp_path / "relatorio.json"
    profile_file = tmp_path / profile["slot"] / "biografia.txt"
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (state, report, profile_file)
    }
    account = {
        "username": "existente", "status": "pending", "complete": False,
        "avatar_complete": None, "biography_complete": False, "posts_existing": 0,
    }
    diagnostic = {
        "captured_at": "2026-10-25T00:00:00+00:00",
        "window_title": "VEM ENGAJAR BOT", "read_only": True,
        "control_count": 3, "controls": [], "accounts": [account],
        "validation": {
            "valid": True, "expected_account_count": 1,
            "observed_account_count": 1, "errors": [],
        },
    }
    settings = SimpleNamespace(root=tmp_path, target_posts=7, initial_profiles=99)
    monkeypatch.setattr(cli.Settings, "load", lambda _: settings)
    monkeypatch.setattr(cli, "inspect_window", lambda: diagnostic)
    monkeypatch.setattr(sys, "argv", ["instagram-automacao", "sync-bot", "--dry-run"])
    cli.main()
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (state, report, profile_file)
    } == before
    assert not (tmp_path / "Perfil_02").exists()
    assert (tmp_path / "logs" / "vem_engajar_uia.json").is_file()


def test_bot_sync_rejects_unknown_state_without_writing(tmp_path: Path):
    initialize(tmp_path)
    try:
        sync_bot_accounts(tmp_path, [{"username": "duvidoso", "status": "unknown"}], 7)
    except ValueError as error:
        assert "sem estado explícito" in str(error)
    else:
        raise AssertionError("estado desconhecido deveria impedir sincronização")
    with connect(tmp_path) as con:
        assert con.execute("SELECT count(*) FROM profiles").fetchone()[0] == 0


def test_fit_three_by_four_without_stretching(tmp_path: Path):
    source = tmp_path / "wide.png"
    output = tmp_path / "output.jpg"
    Image.new("RGB", (1200, 600), "red").save(source)
    fit_three_by_four(source, output)
    with Image.open(output) as image:
        assert image.width * 4 == image.height * 3
