"""BotCheck API tests — Phase 3: Public API + API key auth"""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tempfile

from fastapi.testclient import TestClient
from api import server as _server_mod
from api.server import app, _api_key_daily_usage

# Point DB to a temp file so tests are isolated
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_server_mod.DB_PATH = _tmp_db.name
_tmp_db.close()

# Module-level client with lifespan
_client_ctx = TestClient(app, raise_server_exceptions=True)
client = _client_ctx.__enter__()


def teardown_module():
    _client_ctx.__exit__(None, None, None)
    try:
        os.unlink(_tmp_db.name)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _api_key_daily_usage.clear()
    yield
    _api_key_daily_usage.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Existing /analyze (no auth)
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_empty_messages(self):
        r = client.post("/analyze", json={"messages": []})
        assert r.status_code == 400

    def test_valid_messages(self):
        msgs = [{"content": f"test message {i}", "created_at": int(time.time()) + i} for i in range(5)]
        r = client.post("/analyze", json={"messages": msgs})
        assert r.status_code == 200
        data = r.json()
        assert "total_score" in data
        assert "timing_score" in data
        assert "message_count" in data


# ---------------------------------------------------------------------------
# Public API v1 — API key auth
# ---------------------------------------------------------------------------

class TestV1Auth:
    def test_missing_key(self):
        r = client.post("/api/v1/check", json={"messages": [{"content": "hi"}]})
        assert r.status_code == 401

    def test_invalid_key(self):
        r = client.post(
            "/api/v1/check",
            json={"messages": [{"content": "hi"}]},
            headers={"X-API-Key": "invalid"},
        )
        assert r.status_code == 403

    def test_generate_and_use_key(self):
        # Generate key
        r = client.post("/api/keys/generate?guild_id=test123&plan=free")
        assert r.status_code == 200
        key = r.json()["key"]
        assert key.startswith("bc_")

        # Use key with /api/v1/check
        msgs = [{"content": f"msg {i}", "created_at": int(time.time()) + i} for i in range(3)]
        r = client.post(
            "/api/v1/check",
            json={"messages": msgs},
            headers={"X-API-Key": key},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_score" in data
        assert "confidence" in data

    def test_v1_check_empty_messages(self):
        # Generate key first
        r = client.post("/api/keys/generate?guild_id=test_empty&plan=free")
        key = r.json()["key"]

        r = client.post(
            "/api/v1/check",
            json={"messages": []},
            headers={"X-API-Key": key},
        )
        assert r.status_code == 400

    def test_v1_user_score_not_found(self):
        r = client.post("/api/keys/generate?guild_id=test_score&plan=free")
        key = r.json()["key"]

        r = client.get(
            "/api/v1/user/nonexistent999/score",
            headers={"X-API-Key": key},
        )
        assert r.status_code == 404

    def test_v1_user_score_found(self):
        """Analyze first, then retrieve score via v1 endpoint."""
        r = client.post("/api/keys/generate?guild_id=g1&plan=free")
        key = r.json()["key"]

        # Insert user row first (FK constraint)
        import aiosqlite, asyncio
        async def _insert_user():
            db = await _server_mod.get_db()
            await db.execute(
                "INSERT OR IGNORE INTO users (id, guild_id, username, is_bot, first_seen_at, last_seen_at) VALUES (?,?,?,0,?,?)",
                ("u_test_v1", "g1", "testuser", int(time.time()), int(time.time())),
            )
            await db.commit()
        asyncio.get_event_loop().run_until_complete(_insert_user())

        # Create a score via /analyze with user_id & guild_id
        msgs = [{"content": f"hello {i}", "created_at": int(time.time()) + i} for i in range(3)]
        client.post("/analyze", json={"messages": msgs, "user_id": "u_test_v1", "guild_id": "g1"})

        r = client.get("/api/v1/user/u_test_v1/score", headers={"X-API-Key": key})
        assert r.status_code == 200
        assert r.json()["user_id"] == "u_test_v1"


# ---------------------------------------------------------------------------
# API Key management
# ---------------------------------------------------------------------------

class TestApiKeyManagement:
    def test_generate_list_revoke(self):
        gid = "mgmt_test"
        # Generate
        r = client.post(f"/api/keys/generate?guild_id={gid}&plan=pro")
        assert r.status_code == 200
        full_key = r.json()["key"]

        # List
        r = client.get(f"/api/keys?guild_id={gid}")
        assert r.status_code == 200
        keys = r.json()
        assert len(keys) >= 1

        # Revoke
        r = client.delete(f"/api/keys/{full_key}")
        assert r.status_code == 200

        # Using revoked key should fail
        r = client.post(
            "/api/v1/check",
            json={"messages": [{"content": "hi"}]},
            headers={"X-API-Key": full_key},
        )
        assert r.status_code == 403

    def test_revoke_nonexistent(self):
        r = client.delete("/api/keys/does_not_exist")
        assert r.status_code == 404

    def test_invalid_plan(self):
        r = client.post("/api/keys/generate?guild_id=x&plan=ultra")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Rate limiting (in-memory per-key daily)
# ---------------------------------------------------------------------------

class TestApiRateLimit:
    def test_free_plan_limit(self):
        r = client.post("/api/keys/generate?guild_id=rl_test&plan=free")
        key = r.json()["key"]
        msgs = [{"content": "x"}]

        # Exhaust 100 requests
        for _ in range(100):
            client.post("/api/v1/check", json={"messages": msgs}, headers={"X-API-Key": key})

        # 101st should be 429
        r = client.post("/api/v1/check", json={"messages": msgs}, headers={"X-API-Key": key})
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# Landing page language routing
# ---------------------------------------------------------------------------

class TestLandingPage:
    def test_ja_landing(self):
        r = client.get("/", headers={"Accept-Language": "ja,en;q=0.9"})
        assert r.status_code == 200
        assert "サーバーに潜むBot" in r.text

    def test_en_landing(self):
        r = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"})
        assert r.status_code == 200
        assert "Find the bots" in r.text

    def test_en_path(self):
        r = client.get("/en/")
        assert r.status_code == 200
        assert "Find the bots" in r.text


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_loads(self):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "BotCheck Dashboard" in r.text
        # Phase 3 additions
        assert "APIキー管理" in r.text
        assert "フィルター" in r.text
