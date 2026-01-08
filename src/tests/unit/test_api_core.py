from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.assistant_api.core.cache import InMemoryCache
from apps.assistant_api.core.logging import RequestIdMiddleware, get_request_id
from apps.assistant_api.core.rate_limit import RateLimiter, RateLimitMiddleware
from apps.assistant_api.core.settings import Settings


def test_settings_from_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "5")

    settings = Settings()

    assert settings.app_name == "Test API"
    assert settings.log_level == "DEBUG"
    assert settings.rate_limit_requests == 5


def test_cache_expires_values() -> None:
    now = [100.0]

    def _clock() -> float:
        return now[0]

    cache = InMemoryCache[int](clock=_clock)
    cache.set("key", 123, ttl_seconds=5)
    assert cache.get("key") == 123

    now[0] = 106.0
    assert cache.get("key") is None


def test_rate_limiter_blocks_after_limit() -> None:
    now = [100.0]

    def _clock() -> float:
        return now[0]

    limiter = RateLimiter(max_requests=2, window_seconds=60, clock=_clock)
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False


def test_request_id_middleware_sets_header() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"request_id": get_request_id()}

    client = TestClient(app)
    response = client.get("/ping", headers={"X-Request-ID": "abc-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.json()["request_id"] == "abc-123"


def test_rate_limit_middleware_blocks() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=lambda: 100.0)
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 429
