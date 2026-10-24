from pathlib import Path

from PIL import Image

from instagram_automacao.images import fit_three_by_four
from instagram_automacao.queue import add_task, claim_next, finish, is_paused, set_paused
from instagram_automacao.storage import add_profile, connect, initialize


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


def test_fit_three_by_four_without_stretching(tmp_path: Path):
    source = tmp_path / "wide.png"
    output = tmp_path / "output.jpg"
    Image.new("RGB", (1200, 600), "red").save(source)
    fit_three_by_four(source, output)
    with Image.open(output) as image:
        assert image.width * 4 == image.height * 3
