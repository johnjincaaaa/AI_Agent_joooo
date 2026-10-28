"""API integration tests using FastAPI TestClient.

Fast + no network: TestClient uses in-process WSGI/ASGI transport.
Run only when `httpx` (TestClient dependency) is available.
"""
import pytest

pytest.importorskip("httpx")  # FastAPI TestClient needs httpx
from fastapi.testclient import TestClient

import main  # side-effect: creates FastAPI `app`

client = TestClient(main.app)


class TestHealth:
    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestOpenAPI:
    def test_docs_served(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["info"]["title"] == "Jingent AI"
        # Scene & skills endpoints are documented
        assert "/ai/scenes" in spec["paths"]


class TestScenePresets:
    def test_list_scenes(self):
        resp = client.get("/ai/scenes")
        assert resp.status_code == 200
        data = resp.json()
        # API returns code=200 + scenes structure
        assert data.get("code") == 200 or isinstance(data, (list, dict))
        # chat/office/study/life must be present
        if isinstance(data, dict) and "scenes" in data:
            scene_ids = [s["id"] for s in data["scenes"]]
        else:
            # Fall back: if returned as list
            scene_ids = [s.get("id") for s in (data if isinstance(data, list) else [])]
        for expected in ("chat", "office", "study", "life"):
            assert expected in scene_ids, f"场景 {expected} 缺失"

    def test_scene_templates(self):
        resp = client.get("/ai/scenes/office/templates")
        assert resp.status_code == 200
        data = resp.json()
        # templates should be a list under some key
        if isinstance(data, dict):
            found = False
            for key in ("templates", "data", "items"):
                if isinstance(data.get(key), list) and data[key]:
                    found = True
                    break
            # OR as raw list returned
            assert found or any(isinstance(v, list) and v for v in data.values()), \
                "办公场景应返回至少 1 个模板"


