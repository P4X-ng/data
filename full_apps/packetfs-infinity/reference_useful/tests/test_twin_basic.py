import re
from fastapi.testclient import TestClient
from app.core.app import create_app

def test_health_and_pages():
    app = create_app()
    c = TestClient(app)
    # health
    r = c.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'ok'
    # static index
    r = c.get('/static/index.html')
    assert r.status_code == 200
    assert re.search(rb'<!doctype html>', r.content, re.I)
    # static twin
    r = c.get('/static/twin.html')
    assert r.status_code == 200
    assert re.search(rb'Twin', r.content, re.I)
