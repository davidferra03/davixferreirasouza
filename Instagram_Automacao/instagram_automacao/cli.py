from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import Settings
from .dashboard import serve
from .flow import download_latest
from .images import fit_three_by_four
from .queue import set_paused
from .queue import add_task
from .storage import (
    add_profile, confirmed_complete_usernames, connect, initialize, register_asset,
    sync_bot_accounts, update_profile, write_report,
)
from .vem_engajar import inspect_window, validate_diagnostic
from .worker import execute, run


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
    inspect = sub.add_parser("inspect-bot")
    inspect.add_argument("--output", type=Path)
    sync = sub.add_parser("sync-bot")
    sync.add_argument("--dry-run", action="store_true")
    flow_test = sub.add_parser("flow-test")
    flow_test.add_argument("profile_id", type=int)
    flow_test.add_argument("--prompt", required=True)
    recover_flow = sub.add_parser("flow-download-latest")
    recover_flow.add_argument("profile_id", type=int)
    add = sub.add_parser("add-profile")
    add.add_argument("--username")
    add.add_argument("--count", type=int, default=1)
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
        initialize(settings.root, settings.initial_profiles)
        print(f"Estrutura criada em {settings.root}")
    elif args.command == "status":
        initialize(settings.root, settings.initial_profiles)
        print(write_report(settings.root).read_text(encoding="utf-8"))
    elif args.command in ("pause", "resume"):
        initialize(settings.root, settings.initial_profiles)
        set_paused(settings.root, args.command == "pause")
        print("Fila pausada" if args.command == "pause" else "Fila liberada")
    elif args.command == "dashboard":
        initialize(settings.root, settings.initial_profiles)
        serve(settings.root, args.port)
    elif args.command == "fit-image":
        print(fit_three_by_four(args.source, args.destination, args.mode))
    elif args.command == "inspect-bot":
        result = inspect_window()
        validation = validate_diagnostic(
            result, allowed_unknown_usernames=confirmed_complete_usernames(settings.root),
        )
        result["validation"] = validation
        output = args.output or settings.root / "logs" / "vem_engajar_uia.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Diagnóstico somente leitura salvo em: {output}")
        print(f"Controles encontrados: {result['control_count']}")
        print(f"Contas identificadas: {len(result['accounts'])}")
        print(f"Captura válida para sincronização: {'sim' if validation['valid'] else 'não'}")
        if validation["errors"]:
            print("Motivos: " + "; ".join(validation["errors"]))
        if validation["warnings"]:
            print("Avisos: " + "; ".join(validation["warnings"]))
    elif args.command == "sync-bot":
        result = inspect_window()
        validation = validate_diagnostic(
            result, allowed_unknown_usernames=confirmed_complete_usernames(settings.root),
        )
        result["validation"] = validation
        output = settings.root / "logs" / "vem_engajar_uia.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        if not validation["valid"]:
            raise RuntimeError("Captura insegura para sincronização: " + "; ".join(validation["errors"]))
        if not args.dry_run:
            initialize(settings.root, settings.initial_profiles)
        synced = sync_bot_accounts(
            settings.root, result["accounts"], settings.target_posts, dry_run=args.dry_run,
        )
        print(json.dumps(synced, ensure_ascii=False, indent=2))
        if args.dry_run:
            print("Simulação concluída; banco e VEM ENGAJAR não foram alterados.")
        else:
            print("Sincronização local concluída; nenhum botão do VEM ENGAJAR foi acionado.")
    elif args.command == "flow-test":
        initialize(settings.root, settings.initial_profiles)
        result = execute(settings, {
            "profile_id": args.profile_id,
            "kind": "generate",
            "payload_json": json.dumps({"prompt": args.prompt}, ensure_ascii=False),
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "flow-download-latest":
        initialize(settings.root, settings.initial_profiles)
        with connect(settings.root) as con:
            profile = con.execute("SELECT * FROM profiles WHERE id=?", (args.profile_id,)).fetchone()
        if profile is None:
            raise SystemExit(f"Perfil inexistente: {args.profile_id}")
        if not settings.flow_cdp_url:
            raise SystemExit("google_flow.cdp_url não está configurado")
        target = settings.root / profile["slot"] / "publicacoes"
        downloaded = download_latest(cdp_url=settings.flow_cdp_url, download_dir=target)
        asset_id = register_asset(settings.root, profile["id"], "publication", downloaded, "Resultado recuperado do Flow")
        print(json.dumps({"asset_id": asset_id, "path": str(downloaded)}, ensure_ascii=False, indent=2))
    elif args.command == "add-profile":
        initialize(settings.root, settings.initial_profiles)
        if args.count < 1:
            raise SystemExit("--count deve ser pelo menos 1")
        if args.username and args.count != 1:
            raise SystemExit("--username só pode ser usado quando --count=1")
        created = [add_profile(settings.root, args.username) for _ in range(args.count)]
        print(json.dumps(created, ensure_ascii=False, indent=2))
    elif args.command == "run":
        initialize(settings.root, settings.initial_profiles)
        print(f"Tarefas concluídas: {run(settings, args.once)}")
    elif args.command == "set-profile":
        initialize(settings.root, settings.initial_profiles)
        update_profile(
            settings.root, args.profile_id, username=args.username,
            display_name=args.display_name, biography=args.biography,
            avatar_complete=args.avatar_complete,
            biography_complete=args.biography_complete,
            posts_existing=args.posts, complete=args.complete,
        )
        print("Perfil atualizado")
    elif args.command == "enqueue":
        initialize(settings.root, settings.initial_profiles)
        add_task(settings.root, args.profile_id, args.kind, json.loads(args.payload_json), args.idempotency_key)
        print("Tarefa enfileirada (ou já existente)")
    elif args.command == "register-asset":
        initialize(settings.root, settings.initial_profiles)
        print(register_asset(settings.root, args.profile_id, args.kind, args.path, args.prompt))


if __name__ == "__main__":
    main()
