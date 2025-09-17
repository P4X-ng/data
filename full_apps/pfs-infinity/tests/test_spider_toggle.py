from fastapi.testclient import TestClient

from app.core.app import create_app


def test_spider_disabled_by_default():
    app = create_app(enable_spider=False)
    c = TestClient(app)
    r = c.get("/spider/metrics")
    assert r.status_code in (404, 405)


def test_spider_enabled_when_requested():
    app = create_app(enable_spider=True)
    c = TestClient(app)
    r = c.get("/spider/metrics")
    assert r.status_code in (200, 503, 500)  # may error if backend deps missing, but route exists
