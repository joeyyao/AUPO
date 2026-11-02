"""FastAPI application entry point.

Serves the JSON API under ``/api`` and, when a frontend build exists, the built
Vue single page app from ``frontend/dist`` (with SPA history fallback).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST_DIR, settings
from .data_store import DataFileError
from .routers import meta, orders, products

app = FastAPI(
    title="Order Details, Tracking and Shipping Estimate",
    description=(
        "Data-driven order management API for an Australian pharmacy scenario: "
        "SKU matching, GST calculations, shipment-fee estimation and courier tracking."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(orders.router)
app.include_router(products.router)


@app.exception_handler(DataFileError)
async def data_file_error_handler(_, exc: DataFileError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc), "kind": "data_file_error"})


if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Serve the built SPA and its static files; unknown /api paths stay 404 JSON."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Unknown API endpoint.")

    if full_path:
        candidate = (FRONTEND_DIST_DIR / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found.")
        if candidate.is_file():
            return FileResponse(candidate)

    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Frontend build not found.",
            "hint": "Run `python run.py` to install, build and serve the Vue frontend, "
            "or `python run.py --dev` for the Vite dev server.",
            "api_docs": "/docs",
        },
    )


def create_app() -> FastAPI:
    return app


__all__ = ["app", "create_app", "settings"]
