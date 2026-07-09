"""
Main FastAPI application entry point for Vercel serverless deployment.
"""
import os
import sys

# ── macOS: ensure Homebrew libs are discoverable by WeasyPrint ───────────────
# libgobject-2.0 and friends live in /opt/homebrew/lib on Apple Silicon macs.
# ctypes.util.find_library() only searches DYLD_LIBRARY_PATH, so we inject
# it here at import time (before WeasyPrint is first imported anywhere).
if sys.platform == "darwin":
    homebrew_lib = "/opt/homebrew/lib"
    current = os.environ.get("DYLD_LIBRARY_PATH", "")
    if homebrew_lib not in current:
        os.environ["DYLD_LIBRARY_PATH"] = f"{homebrew_lib}:{current}".strip(":")

# ── Linux (Railway/Nixpacks): patch find_library for WeasyPrint deps ─────────
# Nix-managed Python's ldconfig cache doesn't include apt-installed .so files
# in /usr/lib/x86_64-linux-gnu, so ctypes.util.find_library('gobject-2.0')
# returns None and WeasyPrint falls back to the bare name 'libgobject-2.0-0'
# which doesn't match any actual file. We patch find_library to do a direct
# filesystem lookup as a fallback, which works regardless of ldconfig state.
if sys.platform == "linux":
    import ctypes.util as _cu

    _LINUX_LIB_SONAMES = {
        "gobject-2.0":   "libgobject-2.0.so.0",
        "glib-2.0":      "libglib-2.0.so.0",
        "gio-2.0":       "libgio-2.0.so.0",
        "pango-1.0":     "libpango-1.0.so.0",
        "pangoft2-1.0":  "libpangoft2-1.0.so.0",
        "pangocairo-1.0":"libpangocairo-1.0.so.0",
        "cairo":         "libcairo.so.2",
        "harfbuzz":      "libharfbuzz.so.0",
        "fontconfig":    "libfontconfig.so.1",
        "freetype":      "libfreetype.so.6",
    }
    _LINUX_LIB_DIRS = [
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",  # ARM64 hosts
        "/usr/lib",
        "/usr/local/lib",
    ]
    _orig_find_library = _cu.find_library

    def _weasyprint_find_library(name):
        result = _orig_find_library(name)
        if result is None and name in _LINUX_LIB_SONAMES:
            soname = _LINUX_LIB_SONAMES[name]
            for d in _LINUX_LIB_DIRS:
                p = os.path.join(d, soname)
                if os.path.exists(p):
                    return p
        return result

    _cu.find_library = _weasyprint_find_library

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from mangum import Mangum
import logging

from api.routes import analyze, runs, health, reports, watchlist, admin, webhook, auth, stripe, position_sizing
from api.routes import billing
from api.routes import entitlements as entitlements_route
from api.routes import deployment as deployment_route
from api.routes import portfolio as portfolio_route
from api.routes import portfolio_actions as portfolio_actions_route
from api.routes import weekly_signals as weekly_signals_route
from api.routes import autopilot as autopilot_route
from api.lib.db import connect_db, disconnect_db
from api.services.cron_scheduler import start_scheduler, stop_scheduler

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s'
)

_startup_logger = logging.getLogger("api.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start DB connection in the background so /api/health can respond immediately.

    Neon serverless cold-starts can take 30-60s.  Awaiting connect_db() in the
    lifespan startup blocks ALL HTTP traffic (ASGI spec) — including /api/health —
    until the connection completes, causing Railway healthcheck failures.

    Routes use get_db() which lazy-connects if the background task hasn't finished.
    """
    try:
        from urllib.parse import urlparse
        _p = urlparse(os.getenv("DATABASE_URL", ""))
        _db_name = _p.path.lstrip("/") or "(unknown)"
        _startup_logger.info("DB target: %s/%s", _p.hostname or "(unknown)", _db_name)
    except Exception:
        _startup_logger.info("DB target: (could not parse DATABASE_URL)")

    # Fire-and-forget: connect in background, don't block startup.
    asyncio.create_task(connect_db())
    asyncio.create_task(start_scheduler())
    yield
    await stop_scheduler()
    await disconnect_db()


# Initialize FastAPI app
app = FastAPI(
    title="Research Swarm API",
    description="Multi-agent stock analysis system with serverless architecture",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
_default_origins = "https://www.dvrg.io,https://dvrg.io,https://research-swarm-frontend.vercel.app"
if os.getenv("ENVIRONMENT", "development").lower() not in ("production", "prod"):
    _default_origins += ",http://localhost:3000,http://localhost:3001"
allowed_origins = os.getenv("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Device-ID", "X-Requested-With"],
    expose_headers=["Content-Type"],
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Register routes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])
app.include_router(runs.router, prefix="/api", tags=["Runs"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])
app.include_router(watchlist.router, prefix="/api", tags=["Watchlist"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(stripe.router, prefix="/api", tags=["Stripe"])
app.include_router(position_sizing.router, prefix="/api", tags=["Position Sizing"])
app.include_router(billing.router, prefix="/api", tags=["Billing"])
app.include_router(entitlements_route.router, prefix="/api", tags=["Entitlements"])
app.include_router(deployment_route.router, prefix="/api", tags=["Deployment"])
app.include_router(portfolio_route.router, prefix="/api", tags=["Portfolio"])
app.include_router(portfolio_actions_route.router, prefix="/api", tags=["Portfolio Actions"])
app.include_router(weekly_signals_route.router, prefix="/api", tags=["Weekly Signals"])
app.include_router(autopilot_route.router, prefix="/api", tags=["Autopilot"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhooks"])

# ── Inngest handler mount (guarded) ──────────────────────────────────────────
# Serves registered Inngest functions at /api/inngest (SDK default path).
# Wrapped so a missing/broken inngest SDK can never take down the API.
try:
    import inngest.fast_api  # pip SDK (the local package is inngest_app)

    from inngest_app.index import ACTIVE_FUNCTIONS, inngest_client

    if inngest_client is not None and ACTIVE_FUNCTIONS:
        inngest.fast_api.serve(app, inngest_client, ACTIVE_FUNCTIONS)
        _startup_logger.info(
            "Inngest handler mounted at /api/inngest with %d function(s)",
            len(ACTIVE_FUNCTIONS),
        )
    else:
        _startup_logger.warning(
            "Inngest handler NOT mounted (client=%s, active_functions=%d)",
            "ok" if inngest_client is not None else "unavailable",
            len(ACTIVE_FUNCTIONS) if ACTIVE_FUNCTIONS else 0,
        )
except Exception as _inngest_exc:  # pragma: no cover — env-dependent
    _startup_logger.warning(
        "Inngest handler NOT mounted — SDK unavailable or serve failed: %s",
        _inngest_exc,
    )

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Research Swarm API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs"
    }

# Serverless/ASGI adapter — lifespan="on" so startup/shutdown hooks fire
handler = Mangum(app, lifespan="on")
