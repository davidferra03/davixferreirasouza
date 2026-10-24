from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .dashboard import serve
from .images import fit_three_by_four
from .queue import set_paused
from .queue import add_task
from .storage import initialize, register_asset, update_profile, write_report
from .vem_engajar import inspect_window
from .worker import run


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="instagram-automacao")
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("dashboard").add_argument("--port", type=int, default=8765)
    image = sub.add_parser("fit-image")
    image.add_argument("source", type=Path)
    image.add_argument("destination", type=Path)
    image.add_argument("--mode", choices=("pad", "crop"), default="pad")
    sub.add_parser("inspect-bot")
    worker = sub.add_parser("run")
    worker.add_argument("--once", action="store_true")
    profile = sub.add_parser("set-profile")
    profile.add_argument("profile_id", type=int)
    profile.add_argument("username")
    profile.add_argument("--display-name")
    profile.add_argument("--biography")
    profile.add_argument("--avatar-complete", action="store_true")
    profile.add_argument("--biography-complete", action="store_true")
    profile.add_argument("--posts", type=int, default=0)
    profile.add_argument("--complete", action="store_true")
    task = sub.add_parser("enqueue")
    task.add_argument("profile_id", type=int)
    task.add_argument("kind", choices=("generate", "fit_image", "publish"))
    task.add_argument("payload_json")
    task.add_argument("idempotency_key")
    asset = sub.add_parser("register-asset")
    asset.add_argument("profile_id", type=int)
    asset.add_argument("kind", choices=("avatar", "publication"))
    asset.add_argument("path", type=Path)
    asset.add_argument("--prompt")
    return p


def main() -> None:
    args = parser().parse_args()
    settings = Settings.load(args.config)
    if args.command == "init":
        initialize(settings.root, settings.profiles)
        print(f"Estrutura criada em {settings.root}")
    elif args.command == "status":
        initialize(settings.root, settings.profiles)
        print(write_report(settings.root).read_text(encoding="utf-8"))
    elif args.command in ("pause", "resume"):
        initialize(settings.root, settings.profiles)
        set_paused(settings.root, args.command == "pause")
        print("Fila pausada" if args.command == "pause" else "Fila liberada")
    elif args.command == "dashboard":
        initialize(settings.root, settings.profiles)
        serve(settings.root, args.port)
    elif args.command == "fit-image":
        print(fit_three_by_four(args.source, args.destination, args.mode))
    elif args.command == "inspect-bot":
        print(json.dumps([x.__dict__ for x in inspect_window()], ensure_ascii=False, indent=2))
    elif args.command == "run":
        initialize(settings.root, settings.profiles)
        print(f"Tarefas concluídas: {run(settings, args.once)}")
    elif args.command == "set-profile":
        initialize(settings.root, settings.profiles)
        update_profile(
            settings.root, args.profile_id, username=args.username,
            display_name=args.display_name, biography=args.biography,
            avatar_complete=args.avatar_complete,
            biography_complete=args.biography_complete,
            posts_existing=args.posts, complete=args.complete,
        )
        print("Perfil atualizado")
    elif args.command == "enqueue":
        initialize(settings.root, settings.profiles)
        add_task(settings.root, args.profile_id, args.kind, json.loads(args.payload_json), args.idempotency_key)
        print("Tarefa enfileirada (ou já existente)")
    elif args.command == "register-asset":
        initialize(settings.root, settings.profiles)
        print(register_asset(settings.root, args.profile_id, args.kind, args.path, args.prompt))


if __name__ == "__main__":
    main()
