from pathlib import Path

from PIL import Image

from instagram_automacao.images import fit_three_by_four
from instagram_automacao.queue import add_task, claim_next, finish, is_paused, set_paused
from instagram_automacao.storage import add_profile, connect, initialize, sync_bot_accounts
from instagram_automacao.vem_engajar import parse_accounts, redact


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


def test_parse_and_sync_bot_accounts(tmp_path: Path):
    diagnostic = {
        "controls": [
            {"name": "Conta @pendente", "control_type": "ListItem", "rectangle": {"left": 10, "top": 100, "right": 500, "bottom": 200}},
            {"name": "Bloqueada nas tarefas do bot até completar o perfil", "control_type": "Text", "rectangle": {"left": 20, "top": 130, "right": 400, "bottom": 150}},
            {"name": "Abrir navegador da conta @pendente", "control_type": "Button", "rectangle": {"left": 20, "top": 160, "right": 120, "bottom": 180}},
            {"name": "Conta @completo", "control_type": "ListItem", "rectangle": {"left": 10, "top": 200, "right": 500, "bottom": 300}},
            {"name": "Foto de perfil de @completo", "control_type": "Image", "rectangle": {"left": 20, "top": 220, "right": 60, "bottom": 260}},
            {"name": "Verificar o perfil da conta @completo", "control_type": "Button", "rectangle": {"left": 20, "top": 270, "right": 120, "bottom": 290}},
        ]
    }
    accounts = parse_accounts(diagnostic)
    assert accounts == [
        {"username": "pendente", "complete": False, "blocked": True, "avatar_complete": False, "can_verify": False, "can_open_browser": True, "can_close_browser": False},
        {"username": "completo", "complete": True, "blocked": False, "avatar_complete": True, "can_verify": True, "can_open_browser": False, "can_close_browser": False},
    ]
    initialize(tmp_path)
    synced = sync_bot_accounts(tmp_path, accounts, 7)
    assert len(synced) == 2
    with connect(tmp_path) as con:
        rows = con.execute("SELECT instagram_username, status, posts_existing FROM profiles ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [("pendente", "pending", 0), ("completo", "complete", 7)]


def test_fit_three_by_four_without_stretching(tmp_path: Path):
    source = tmp_path / "wide.png"
    output = tmp_path / "output.jpg"
    Image.new("RGB", (1200, 600), "red").save(source)
    fit_three_by_four(source, output)
    with Image.open(output) as image:
        assert image.width * 4 == image.height * 3
