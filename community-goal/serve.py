#!/usr/bin/env python3
"""Build the site and serve it locally, the same way GitHub Pages will.

    python3 community-goal/serve.py           # http://localhost:8000
    python3 community-goal/serve.py --port 9000 --no-build

Serving over HTTP matters: the page fetches its own API, and browsers block
fetch() against file:// URLs.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

import build as builder

ROOT = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static handler with Pages-like headers and no caching during development."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        # GitHub Pages serves assets with a permissive CORS header; mirror it so
        # anything built against the local server behaves the same in production.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quieter output
        print("  %s" % (fmt % args))


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dist", default=str(ROOT / "dist"))
    parser.add_argument("--no-build", action="store_true", help="serve dist/ as it stands")
    args = parser.parse_args(argv)

    dist = Path(args.dist)
    if not args.no_build:
        builder.build(dist, f"http://localhost:{args.port}")

    handler = functools.partial(Handler, directory=str(dist))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        print(f"serving {dist} at http://localhost:{args.port}  (ctrl-c to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
