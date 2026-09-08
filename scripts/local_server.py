"""Local development server for the fleet rebalancer API.

Usage:
    conda activate rebalancer
    python scripts/local_server.py
"""

import logging
import os
import sys

# Add the project root and src/ to the path so package-relative imports work.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.approve import handle_approve  # noqa: E402
from api.reject import handle_reject  # noqa: E402
from api.status import handle_status  # noqa: E402
from api.tick import handle_tick  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = FastAPI(title="Fleet Rebalancer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_endpoint():
    return {"status": "ok"}


@app.post("/api/tick")
async def tick_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    return await handle_tick(body, request.headers.get("X-Session-ID", "operator-1"))


@app.post("/api/approve")
async def approve_endpoint(request: Request):
    return await handle_approve(request.headers.get("X-Session-ID", "operator-1"))


@app.post("/api/reject")
async def reject_endpoint(request: Request):
    return await handle_reject(request.headers.get("X-Session-ID", "operator-1"))


@app.get("/api/status")
async def status_endpoint(request: Request):
    return await handle_status(request.headers.get("X-Session-ID", "operator-1"))


@app.get("/api/plans")
async def plans_endpoint(limit: int = 10):
    """Return recent approved plans from Supabase."""
    from rebalancer.config import get_settings

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        return {"plans": []}
    try:
        from rebalancer.data.supabase_client import SupabaseClient

        sb = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
        plans = sb.get_recent_plans(limit=limit)
        return {"plans": plans}
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to fetch plans: %s", exc)
        return {"plans": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
