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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from mangum import Mangum
import logging

from api.routes import analyze, runs, health, reports, watchlist, admin, webhook, auth, stripe, position_sizing
from api.routes import billing
from api.routes import entitlements as entitlements_route

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s'
)

# Initialize FastAPI app
app = FastAPI(
    title="Research Swarm API",
    description="Multi-agent stock analysis system with serverless architecture",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
app.include_router(webhook.router, prefix="/api/webhook", tags=["Webhooks"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Research Swarm API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/api/docs"
    }

# Vercel serverless function handler
handler = Mangum(app, lifespan="off")
