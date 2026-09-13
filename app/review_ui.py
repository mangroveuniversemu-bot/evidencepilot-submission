"""Loopback-only verification workbench. Never calls Bedrock or executes decisions."""

from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
from pathlib import Path

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from agent.schemas import HumanDecisionInput
from app.poc import PocRequest
from app.review_store import DecisionConflict, ReviewError, ReviewStore

STATIC = Path(__file__).parent / "static"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "out" / "reviews"
MAX_BODY_BYTES = 16_384
CASES = [
    {"id": "maya", "name": "Maya's review", "detail": "Find the hidden convention mismatch."},
    {"id": "clean", "name": "Clean replay", "detail": "A consistent package needs no escalation."},
    {
        "id": "missing_evidence",
        "name": "Missing provenance",
        "detail": "Right arithmetic. Incomplete record.",
    },
    {
        "id": "human_decision",
        "name": "The human boundary",
        "detail": "Two valid analyses. No agent preference.",
    },
    {"id": "stale", "name": "Stale artifact", "detail": "Catch mismatched inputs before replay."},
    {
        "id": "injection",
        "name": "Untrusted instructions",
        "detail": "Embedded prose cannot authorize a verdict.",
    },
]


class LocalBoundary:
    """Exact Host/Origin, no CORS, a write token, bounded bodies, and local assets.

    This blocks ordinary drive-by browser requests and DNS rebinding. It is not
    authentication against other programs or users on the same computer.
    """

    def __init__(self, app, *, origin: str, token: str):
        self.app = app
        self.origin = origin
        self.host = origin.removeprefix("http://")
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope["headers"]
        }
        write = scope["method"] not in {"GET", "HEAD"}
        bad_origin = headers.get("origin") not in {None, self.origin}
        forbidden = (
            headers.get("host") != self.host
            or bad_origin
            or headers.get("sec-fetch-site") == "cross-site"
        )
        if write:
            forbidden = (
                forbidden
                or headers.get("origin") != self.origin
                or not secrets.compare_digest(
                    headers.get("x-review-token", "").encode("utf-8"), self.token.encode("ascii")
                )
            )
        if forbidden:
            await JSONResponse({"error": "Local browser request rejected."}, 403)(
                scope, receive, send
            )
            return
        if write:
            if headers.get("content-type", "").split(";")[0] != "application/json":
                await JSONResponse({"error": "JSON required."}, 415)(scope, receive, send)
                return
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    await JSONResponse({"error": "Request too large."}, 413)(scope, receive, send)
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break

            async def buffered_receive():
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            receive = buffered_receive

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-frame-options", b"DENY"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; style-src 'self'; "
                            b"img-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                            b"object-src 'none'; base-uri 'none'; form-action 'self'",
                        ),
                    ]
                )
            await send(message)

        await self.app(scope, receive, secured_send)


def create_app(data_dir: Path = DEFAULT_DATA_DIR, *, port: int = 8765):
    store = ReviewStore(data_dir)
    token = secrets.token_urlsafe(32)

    def index(request: Request):
        return FileResponse(STATIC / "review.html")

    def asset(request: Request):
        name = request.path_params["name"]
        if name not in {"review.css", "review.js"}:
            return Response(status_code=404)
        return FileResponse(STATIC / name)

    def session(request: Request):
        return JSONResponse({"token": token, "cases": CASES, "mode": "verification_only"})

    def history(request: Request):
        return JSONResponse({"runs": store.list_runs(), "limit": 100})

    async def start_run(request: Request):
        from starlette.concurrency import run_in_threadpool

        payload = await request.json()
        parsed = PocRequest.model_validate(payload)
        if parsed.model_fields_set != {"case"}:
            raise ReviewError("Only a bundled case is accepted; model calls are disabled.")
        result = await run_in_threadpool(store.create_run, parsed.case)
        return JSONResponse(result, status_code=201)

    def get_run(request: Request):
        return JSONResponse(store.get_run(request.path_params["certificate_id"]))

    async def record(request: Request):
        from starlette.concurrency import run_in_threadpool

        choice = HumanDecisionInput.model_validate(await request.json())
        result = await run_in_threadpool(
            store.record_decision, request.path_params["certificate_id"], choice
        )
        return JSONResponse(result)

    def export(request: Request):
        run = store.get_run(request.path_params["certificate_id"])
        name = run["certificate"]["certificate_id"]
        return JSONResponse(
            run, headers={"Content-Disposition": f'attachment; filename="{name}-review.json"'}
        )

    async def error(request: Request, exc: Exception):
        if isinstance(exc, KeyError):
            return JSONResponse({"error": "Review run not found."}, status_code=404)
        if isinstance(exc, DecisionConflict):
            return JSONResponse({"error": str(exc)}, status_code=409)
        if isinstance(exc, ReviewError):
            return JSONResponse({"error": str(exc)}, status_code=400)
        if isinstance(exc, sqlite3.Error):
            return JSONResponse(
                {"error": "Local record storage unavailable. Nothing was overwritten."}, 503
            )
        return JSONResponse({"error": "Invalid request or record. No decision was saved."}, 400)

    app = Starlette(
        routes=[
            Route("/", index),
            Route("/static/{name}", asset),
            Route("/api/session", session),
            Route("/api/runs", history),
            Route("/api/runs", start_run, methods=["POST"]),
            Route("/api/runs/{certificate_id}", get_run),
            Route("/api/runs/{certificate_id}/decision", record, methods=["POST"]),
            Route("/api/runs/{certificate_id}/export", export),
        ],
        exception_handlers=dict.fromkeys(
            (ReviewError, KeyError, ValidationError, json.JSONDecodeError, sqlite3.Error), error
        ),
    )
    return LocalBoundary(app, origin=f"http://127.0.0.1:{port}", token=token)


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged local port between 1024 and 65535.")
    print(f"EvidencePilot verification-only UI: http://127.0.0.1:{args.port}")
    print("Synthetic inputs. No model calls. Local, self-reported decision receipts only.")
    uvicorn.run(
        create_app(args.data_dir, port=args.port),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
