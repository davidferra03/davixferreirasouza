from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .storage import write_report


def serve(root: Path, port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/report":
                data = write_report(root).read_bytes()
                content_type = "application/json; charset=utf-8"
            else:
                data = DASHBOARD.encode("utf-8")
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            return

    address = f"http://127.0.0.1:{port}"
    threading.Timer(0.5, lambda: webbrowser.open(address)).start()
    print(f"Painel local: {address}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


DASHBOARD = """<!doctype html><meta charset=utf-8><title>Instagram Automação</title>
<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;background:#111827;color:#f9fafb}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #374151;text-align:left}.ok{color:#4ade80}.bad{color:#fbbf24}</style>
<h1>Instagram Automação</h1><p id=state></p><table><thead><tr><th>Perfil</th><th>Conta</th><th>Status</th><th>Posts</th><th>Erro</th></tr></thead><tbody id=rows></tbody></table>
<script>async function load(){let r=await(await fetch('/api/report')).json();state.textContent=r.paused?'Fila pausada':'Fila em execução';rows.innerHTML=r.profiles.map(p=>`<tr><td>${p.slot}</td><td>${p.instagram_username||'—'}</td><td class="${p.status==='complete'?'ok':'bad'}">${p.status}</td><td>${p.posts_existing}</td><td>${p.last_error||''}</td></tr>`).join('')}load();setInterval(load,5000)</script>"""
