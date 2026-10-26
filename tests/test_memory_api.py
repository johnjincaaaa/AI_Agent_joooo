"""记忆 API 与 LLM 配置端点测试。

注意：与 test_api_integration 一致，使用 main.app 的真实 SQLite（app.db），
测试用户以 memtest/iso 前缀注册，便于辨识与清理。
"""
import random
import string

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _register_and_token(prefix: str = "memtest") -> str:
    name = prefix + "_" + "".join(random.choices(string.ascii_lowercase, k=6))
    r = client.post("/register", json={"username": name, "password": "pass123456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == 200, data
    return data["token"]


class TestMemoryAPI:
    def test_memory_requires_auth(self):
        r = client.get("/ai/memories")
        assert r.status_code in (401, 403)

    def test_memory_crud_flow(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}

        # 添加全局记忆
        r = client.post(
            "/ai/memories",
            json={"type": "global", "content": "我叫测试用户，喜欢打游戏", "category": "个人信息"},
            headers=headers,
        )
        assert r.status_code == 200 and r.json()["code"] == 200, r.text
        mem_id = r.json()["id"]

        # 列表包含新记忆
        r = client.get("/ai/memories", headers=headers)
        assert r.status_code == 200
        rows = r.json()["data"]
        assert any(m["id"] == mem_id and m["type"] == "global" for m in rows)

        # 删除后消失
        r = client.delete(f"/ai/memories/{mem_id}", headers=headers)
        assert r.status_code == 200
        r = client.get("/ai/memories", headers=headers)
        assert all(m["id"] != mem_id for m in r.json()["data"])

    def test_memory_isolation_between_users(self):
        t1 = _register_and_token("isoA")
        t2 = _register_and_token("isoB")
        r = client.post(
            "/ai/memories",
            json={"type": "detail", "content": "A用户的私密记忆", "category": "其他"},
            headers={"Authorization": f"Bearer {t1}"},
        )
        assert r.json()["code"] == 200
        r2 = client.get("/ai/memories", headers={"Authorization": f"Bearer {t2}"})
        assert all("私密记忆" not in m["content"] for m in r2.json()["data"])

    def test_llm_test_rejects_empty_key(self):
        r = client.post(
            "/ai/llm/test",
            json={"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "api_key": ""},
        )
        assert r.status_code == 400
