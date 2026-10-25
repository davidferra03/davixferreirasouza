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


def test_real_uia_shape_uses_tab_counter_and_preserves_local_complete_unknown():
    controls = [
        {"name": "Todas as contas 2", "control_type": "TabItem", "rectangle": {"left": 313, "top": 345, "right": 475, "bottom": 383}},
        {"name": "Conta @pendente", "control_type": "ListItem", "rectangle": {"left": 313, "top": 463, "right": 1368, "bottom": 568}},
        {"name": "Perfil verificado em", "control_type": "Text", "rectangle": {"left": 622, "top": 507, "right": 745, "bottom": 526}},
        {"name": "Bloqueada nas tarefas do bot até completar o perfil no Instagram.", "control_type": "Text", "rectangle": {"left": 369, "top": 531, "right": 789, "bottom": 550}},
        {"name": "Verificar o perfil da conta @pendente", "control_type": "Button", "rectangle": {"left": 972, "top": 499, "right": 1086, "bottom": 531}},
        {"name": "Abrir navegador da conta @pendente", "control_type": "Button", "rectangle": {"left": 1093, "top": 499, "right": 1223, "bottom": 531}},
        {"name": "Fechar navegador da conta @pendente", "control_type": "Button", "rectangle": {"left": 1230, "top": 499, "right": 1368, "bottom": 531}},
        {"name": "Conta @completo", "control_type": "ListItem", "rectangle": {"left": 313, "top": 568, "right": 1368, "bottom": 649}},
        {"name": "Foto de perfil de @completo", "control_type": "Image", "rectangle": {"left": 313, "top": 586, "right": 357, "bottom": 630}},
        {"name": "Perfil verificado em", "control_type": "Text", "rectangle": {"left": 622, "top": 612, "right": 745, "bottom": 631}},
        {"name": "Verificar o perfil da conta @completo", "control_type": "Button", "rectangle": {"left": 972, "top": 592, "right": 1086, "bottom": 624}},
        {"name": "Abrir navegador da conta @completo", "control_type": "Button", "rectangle": {"left": 1093, "top": 592, "right": 1223, "bottom": 624}},
        {"name": "Fechar navegador da conta @completo", "control_type": "Button", "rectangle": {"left": 1230, "top": 592, "right": 1368, "bottom": 624}},
    ]
    diagnostic = {"controls": controls}
    accounts = parse_accounts(diagnostic)
    diagnostic["accounts"] = accounts
    strict_validation = validate_diagnostic(diagnostic)
    assert not strict_validation["valid"]
    assert strict_validation["errors"] == ["estado sem evidência explícita: completo"]
    validation = validate_diagnostic(diagnostic, allowed_unknown_usernames={"completo"})
    assert validation == {
        "valid": True,
        "expected_account_count": 2,
        "observed_account_count": 2,
        "errors": [],
        "warnings": [
            "estado UIA não exposto para completo; perfil local completo será apenas preservado"
        ],
    }
    assert accounts[0]["status"] == "pending"
    assert accounts[0]["status_evidence"] == "explicit_pending_warning"
    assert accounts[1]["status"] == "unknown"
    assert accounts[1]["status_evidence"] == "insufficient_evidence"


def test_avatar_and_actions_without_explicit_badge_remain_unknown():
    controls = [
        {"name": "1 contas", "control_type": "Text", "rectangle": {"left": 0, "top": 0, "right": 50, "bottom": 10}},
        {"name": "Conta @duvidoso", "control_type": "ListItem", "rectangle": {"left": 10, "top": 100, "right": 500, "bottom": 220}},
        {"name": "Foto de perfil de @duvidoso", "control_type": "Image", "rectangle": {"left": 20, "top": 120, "right": 60, "bottom": 160}},
        {"name": "Perfil verificado em", "control_type": "Text", "rectangle": {"left": 100, "top": 130, "right": 220, "bottom": 150}},
        {"name": "Verificar o perfil da conta @duvidoso", "control_type": "Button", "rectangle": {"left": 300, "top": 180, "right": 400, "bottom": 210}},
        {"name": "Abrir navegador da conta @duvidoso", "control_type": "Button", "rectangle": {"left": 200, "top": 180, "right": 290, "bottom": 210}},
        {"name": "Fechar navegador da conta @duvidoso", "control_type": "Button", "rectangle": {"left": 100, "top": 180, "right": 190, "bottom": 210}},
    ]
    account = parse_accounts({"controls": controls})[0]
    assert account["status"] == "unknown"
    assert account["status_evidence"] == "insufficient_evidence"


def test_allowed_unknown_still_requires_unblocked_avatar_evidence():
    base = {
        "controls": [{"name": "1 contas", "control_type": "Text", "rectangle": {}}],
    }
    blocked = {
        **base,
        "accounts": [{
            "username": "local_complete", "status": "unknown",
            "blocked": True, "avatar_complete": True,
        }],
    }
    blocked_validation = validate_diagnostic(
        blocked, allowed_unknown_usernames={"local_complete"},
    )
    assert not blocked_validation["valid"]
    assert blocked_validation["errors"] == [
        "perfil local completo apareceu bloqueado: local_complete"
    ]

    avatar_missing = {
        **base,
        "accounts": [{
            "username": "local_complete", "status": "unknown",
            "blocked": False, "avatar_complete": None,
        }],
    }
    avatar_validation = validate_diagnostic(
        avatar_missing, allowed_unknown_usernames={"local_complete"},
    )
    assert not avatar_validation["valid"]
    assert avatar_validation["errors"] == [
        "perfil local completo sem avatar confirmado na captura: local_complete"
    ]

    conflicting = {
        **base,
        "accounts": [{
            "username": "local_complete", "status": "unknown",
            "status_evidence": "conflicting_badges", "missing": [],
            "blocked": False, "avatar_complete": True,
        }],
    }
    conflicting_validation = validate_diagnostic(
        conflicting, allowed_unknown_usernames={"local_complete"},
    )
    assert conflicting_validation["errors"] == ["selos conflitantes para local_complete"]

    missing = {
        **base,
        "accounts": [{
            "username": "local_complete", "status": "unknown",
            "status_evidence": "insufficient_evidence", "missing": ["Falta: Biografia"],
            "blocked": False, "avatar_complete": True,
        }],
    }
    missing_validation = validate_diagnostic(
        missing, allowed_unknown_usernames={"local_complete"},
    )
    assert missing_validation["errors"] == [
        "estado desconhecido com requisitos pendentes para local_complete"
    ]

    invalid = {
        **base,
        "accounts": [{
            "username": "local_complete", "status": "surpresa",
            "blocked": False, "avatar_complete": True,
        }],
    }
    invalid_validation = validate_diagnostic(
        invalid, allowed_unknown_usernames={"local_complete"},
    )
    assert invalid_validation["errors"] == [
        "estado inválido para local_complete: 'surpresa'"
    ]


def test_conflicting_account_counters_are_fatal():
    diagnostic = {
        "controls": [
            {"name": "9 contas", "control_type": "Text", "rectangle": {}},
            {"name": "Todas as contas 8", "control_type": "TabItem", "rectangle": {}},
        ],
        "accounts": [],
    }
    validation = validate_diagnostic(diagnostic)
    assert not validation["valid"]
    assert validation["expected_account_count"] is None
    assert any("contadores totais conflitantes" in error for error in validation["errors"])


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
            "username": "ja_completo", "status": "unknown", "complete": None,
            "blocked": False, "avatar_complete": True,
            "biography_complete": None, "posts_existing": None,
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
    assert preview[0]["action"] == "skipped_complete_unconfirmed"
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


def test_bot_sync_reinforces_unknown_preservation_evidence(tmp_path: Path):
    initialize(tmp_path)
    complete = add_profile(tmp_path, "ja_completo")
    update_profile(
        tmp_path, complete["id"], username="ja_completo", display_name=None,
        biography=None, avatar_complete=True, biography_complete=True,
        posts_existing=7, complete=True,
    )
    state = tmp_path / "state.sqlite3"
    before = state.read_bytes()
    account = {
        "username": "ja_completo", "status": "unknown", "complete": None,
        "blocked": True, "avatar_complete": True,
        "biography_complete": None, "posts_existing": None,
    }
    try:
        sync_bot_accounts(tmp_path, [account], 7, dry_run=True)
    except ValueError as error:
        assert "Evidência insuficiente" in str(error)
    else:
        raise AssertionError("unknown bloqueado deveria impedir até a simulação")
    assert state.read_bytes() == before

    for unsafe in (
        {
            **account, "blocked": False,
            "status_evidence": "conflicting_badges", "missing": [],
        },
        {
            **account, "blocked": False,
            "status_evidence": "insufficient_evidence", "missing": ["Falta: Biografia"],
        },
    ):
        try:
            sync_bot_accounts(tmp_path, [unsafe], 7, dry_run=True)
        except ValueError as error:
            assert "evidência conflitante ou pendente" in str(error)
        else:
            raise AssertionError("unknown conflitante/pendente deveria ser rejeitado")
        assert state.read_bytes() == before


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
        "control_count": 3,
        "controls": [
            {"name": "1 contas", "control_type": "Text", "rectangle": {}},
        ],
        "accounts": [account],
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
        assert "Estado desconhecido" in str(error)
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
