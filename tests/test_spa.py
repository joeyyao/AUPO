"""The built SPA must be served by FastAPI itself, so `python run.py` is enough.

These checks require a production build (``python run.py --build-only``) and are
skipped when ``frontend/dist`` is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import FRONTEND_DIST_DIR
from app.main import app

pytestmark = pytest.mark.skipif(
    not (FRONTEND_DIST_DIR / "index.html").is_file(),
    reason="run `python run.py --build-only` first to produce frontend/dist",
)

client = TestClient(app)


def test_root_serves_the_built_spa():
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert '<div id="app">' in body
    assert "/assets/" in body


def test_hashed_assets_are_served():
    assets: list[Path] = sorted((FRONTEND_DIST_DIR / "assets").glob("*"))
    assert assets, "no built asset found"
    for asset in assets[:3]:
        response = client.get(f"/assets/{asset.name}")
        assert response.status_code == 200
        assert response.content


def test_client_side_routes_fall_back_to_index():
    response = client.get("/orders/PO-20251130-00072")
    assert response.status_code == 200
    assert '<div id="app">' in response.text


def test_unknown_api_path_is_not_swallowed_by_the_spa():
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_api_still_resolves_under_the_spa_mount():
    response = client.get("/api/orders")
    assert response.status_code == 200
    assert response.json()["count"] >= 2
