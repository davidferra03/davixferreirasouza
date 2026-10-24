from pathlib import Path

from PIL import Image

from instagram_automacao.images import fit_three_by_four
from instagram_automacao.queue import add_task, claim_next, finish, is_paused, set_paused
from instagram_automacao.storage import connect, initialize


def test_initialize_and_queue_are_idempotent(tmp_path: Path):
    initialize(tmp_path, 2)
    initialize(tmp_path, 2)
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


def test_fit_three_by_four_without_stretching(tmp_path: Path):
    source = tmp_path / "wide.png"
    output = tmp_path / "output.jpg"
    Image.new("RGB", (1200, 600), "red").save(source)
    fit_three_by_four(source, output)
    with Image.open(output) as image:
        assert image.width * 4 == image.height * 3
