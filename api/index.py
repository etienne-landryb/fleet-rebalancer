"""Single FastAPI entrypoint for deployment."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.approve import handle_approve
from api.reject import handle_reject
from api.status import handle_status
from api.tick import handle_tick

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = FastAPI(title="Fleet Rebalancer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/tick")
async def tick(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    return await handle_tick(body, request.headers.get("X-Session-ID", "operator-1"))


@app.post("/api/approve")
async def approve(request: Request):
    return await handle_approve(request.headers.get("X-Session-ID", "operator-1"))


@app.post("/api/reject")
async def reject(request: Request):
    return await handle_reject(request.headers.get("X-Session-ID", "operator-1"))


@app.get("/api/status")
async def status(request: Request):
    return await handle_status(request.headers.get("X-Session-ID", "operator-1"))


@app.get("/api/plans")
async def plans(limit: int = 10):
    """Return recent approved plans from Supabase."""
    from rebalancer.config import get_settings

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        return {"plans": []}
    try:
        from rebalancer.data.supabase_client import SupabaseClient

        sb = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
        plans_data = sb.get_recent_plans(limit=limit)
        return {"plans": plans_data}
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to fetch plans: %s", exc)
        return {"plans": []}
