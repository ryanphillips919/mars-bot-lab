"""Serve completed Mini Mars replays in a local browser."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "matches"
UI = ROOT / "ui"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def replay_for(run_dir: Path, summary: dict, results: Path = RESULTS) -> Path | None:
    """Accept only a JSON replay inside a direct child of the match directory."""
    results = results.resolve()
    run_dir = run_dir.resolve()
    if run_dir.parent != results:
        return None
    replay_name = summary.get("replay")
    if not isinstance(replay_name, str):
        return None
    replay = Path(replay_name)
    if not replay.is_absolute():
        replay = run_dir / replay
    replay = replay.resolve()
    if replay.name != "replay.json" or replay.parent != run_dir or not replay.is_file():
        return None
    return replay


def discover_matches(results: Path = RESULTS) -> list[dict]:
    matches = []
    for summary_path in results.glob("*/summary.json"):
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            replay = replay_for(summary_path.parent, summary, results)
            if summary.get("game") != "mini-mars" or replay is None:
                continue
            matches.append({
                "id": summary_path.parent.name,
                "seed": summary.get("seed"),
                "bots": summary.get("bots"),
                "scores": summary.get("scores"),
                "winner": summary.get("winner"),
                "turns": summary.get("turns"),
                "replay_file": replay.name,
                "created_ns": summary_path.stat().st_mtime_ns,
            })
        except (OSError, ValueError, TypeError):
            continue
    matches.sort(key=lambda match: match["created_ns"], reverse=True)
    return matches


class ViewerHandler(BaseHTTPRequestHandler):
    results_root = RESULTS
    ui_root = UI

    def send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/matches":
            data = json.dumps({"matches": discover_matches(self.results_root)}).encode("utf-8")
            self.send_bytes(data, "application/json; charset=utf-8")
            return

        if url.path == "/api/replay":
            run_id = parse_qs(url.query).get("id", [None])[0]
            match = next((item for item in discover_matches(self.results_root) if item["id"] == run_id), None)
            if match is None:
                self.send_error(404, "Match not found")
                return
            replay = self.results_root / match["id"] / match["replay_file"]
            try:
                data = replay.read_bytes()
            except OSError:
                self.send_error(404, "Replay not found")
                return
            self.send_bytes(data, "application/json; charset=utf-8")
            return

        asset = ASSETS.get(url.path)
        if asset is None:
            self.send_error(404, "Not found")
            return
        filename, content_type = asset
        try:
            self.send_bytes((self.ui_root / filename).read_bytes(), content_type)
        except OSError:
            self.send_error(404, "Viewer asset not found")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="interface to listen on (default: localhost only)")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ViewerHandler)
    print(f"Mini Mars replay viewer: http://{args.host}:{server.server_port}/", flush=True)
    print("Press Ctrl+C to stop. Run a Mini Mars match in another terminal, then refresh.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
