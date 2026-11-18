"""Optional API token and rate-limit tests.

Skipped when fastapi is not installed in the environment. The token check
and rate limit live in app.main; /health always stays open.
"""
import pytest

try:
    from fastapi.testclient import TestClient
    from app import main as main_module
    _HAS_FASTAPI = True
except ImportError:  # pragma: no cover - fastapi optional in this env
    _HAS_FASTAPI = False


@pytest.fixture(autouse=True)
def _reset_auth_state():
    main_module.API_TOKEN = ""
    main_module._rate_windows.clear()
    yield
    main_module.API_TOKEN = ""
    main_module._rate_windows.clear()


@pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")
def test_health_stays_open_without_token():
    main_module.API_TOKEN = "secret"
    client = TestClient(main_module.app)
    assert client.get("/health").status_code == 200


@pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")
def test_token_required_when_set():
    main_module.API_TOKEN = "secret"
    client = TestClient(main_module.app)
    assert client.get("/audit/verify").status_code == 401
    assert client.get(
        "/audit/verify", headers={"X-API-Token": "wrong"}
    ).status_code == 401
    assert client.get(
        "/audit/verify", headers={"X-API-Token": "secret"}
    ).status_code == 200


@pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")
def test_no_token_required_when_unset():
    main_module.API_TOKEN = ""
    client = TestClient(main_module.app)
    assert client.get("/audit/verify").status_code == 200


@pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")
def test_rate_limit_blocks_after_limit():
    main_module.API_TOKEN = ""
    main_module.RATE_LIMIT_PER_MIN = 2
    main_module._rate_windows.clear()
    client = TestClient(main_module.app)
    assert client.get("/audit/verify").status_code == 200
    assert client.get("/audit/verify").status_code == 200
    assert client.get("/audit/verify").status_code == 429
