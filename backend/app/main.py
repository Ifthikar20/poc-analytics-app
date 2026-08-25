"""FastAPI app: thin polling proxy + SSE fan-out + static hosting.

Route registration order matters — the catch-all static mount for the built
dashboard must come last so it can never swallow /api/*.

There is deliberately NO GZip middleware: compression would buffer the SSE
stream and kill realtime delivery.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .bus import SnapshotBus
from .config import FRONTEND_DIST, STATIC_DIR, load_settings, validate
from .poller import PollerState, run_poller
from .providers import make_provider
from .providers.mock import run_simulator, store as demo_store
from .schema import Snapshot

logging.basicConfig(level=logging.INFO)

settings = load_settings()
validate(settings)
provider = make_provider(settings)
bus = SnapshotBus()
poller_state = PollerState()
started_at = datetime.now(timezone.utc)
simulator_enabled = settings.provider == "mock" and settings.simulate_traffic

DEMO_DIR = STATIC_DIR / "demo"
DEMO_PAGES = {"": "index.html", "pricing": "pricing.html", "about": "about.html"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(run_poller(provider, bus, settings.poll_interval, poller_state))
    ]
    if simulator_enabled:
        tasks.append(asyncio.create_task(run_simulator(demo_store)))
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Realtime Traffic Tracker PoC", lifespan=lifespan)

# CORS is only needed when tracker.js is embedded on an external client site.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"]
)


@app.get("/api/snapshot")
async def get_snapshot() -> Snapshot:
    snapshot = bus.latest()
    if snapshot is None:
        raise HTTPException(status_code=503, detail="no snapshot yet — first poll still running")
    return snapshot


def _sse_event(snapshot: Snapshot) -> str:
    return f"event: snapshot\ndata: {snapshot.model_dump_json()}\n\n"


async def _sse_gen(request: Request):
    queue = bus.subscribe()
    try:
        yield "retry: 3000\n\n"
        if (snapshot := bus.latest()) is not None:
            yield _sse_event(snapshot)  # immediate paint on connect
        while True:
            try:
                yield _sse_event(await asyncio.wait_for(queue.get(), timeout=15.0))
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
    finally:
        bus.unsubscribe(queue)


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _sse_gen(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/track", status_code=204)
async def track(request: Request) -> Response:
    # tracker.js sends a plain-text body (a CORS "simple request" — no preflight).
    try:
        data = json.loads((await request.body()) or b"{}")
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    # Beacons always land in the demo store; only the demo provider surfaces
    # them, but this keeps the demo site working in every mode.
    demo_store.record(
        visitor_id=str(data.get("visitor_id") or "anon")[:64],
        path=str(data.get("path") or "/")[:200],
        country="Local",
    )
    return Response(status_code=204)


@app.get("/api/status")
async def status() -> dict:
    mode_label = {"mock": "DEMO", "ga4": "GA4", "cloudflare": "CLOUDFLARE"}[settings.provider]
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {
        "provider": provider.name,
        "mode_label": mode_label,
        "poll_interval_seconds": settings.poll_interval,
        "simulator_running": simulator_enabled,
        "sse_clients": bus.subscriber_count,
        "last_poll_ok_at": poller_state.last_ok_at.strftime(fmt) if poller_state.last_ok_at else None,
        "last_poll_error": poller_state.last_error,
        "poll_ticks": poller_state.ticks,
        "ga4_configured": bool(settings.ga4_property_id and settings.google_credentials_path),
        "cloudflare_configured": bool(settings.cf_api_token and settings.cf_zone_id),
        "started_at": started_at.strftime(fmt),
    }


@app.get("/tracker.js")
async def tracker_js() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "tracker.js",
        media_type="text/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/demo")
@app.get("/demo/{page}")
async def demo_site(page: str = "") -> HTMLResponse:
    filename = DEMO_PAGES.get(page)
    if filename is None:
        raise HTTPException(status_code=404, detail="no such demo page")
    html = (DEMO_DIR / filename).read_text(encoding="utf-8")
    # When a GA4 measurement id is configured, the demo site dual-sends: the
    # same tracker.js tag also loads real gtag pointed at your GA4 property.
    ga4_attr = f' data-ga4="{settings.ga4_measurement_id}"' if settings.ga4_measurement_id else ""
    return HTMLResponse(html.replace("__GA4_ATTR__", ga4_attr))


if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True))
else:

    @app.get("/")
    async def missing_dist() -> HTMLResponse:
        return HTMLResponse(
            "<h1>Dashboard not built yet</h1>"
            "<p>Run <code>make build</code> (or just <code>make run</code>) once, "
            "or use <code>make dev</code> and open "
            "<a href='http://localhost:5173'>localhost:5173</a>.</p>"
        )
