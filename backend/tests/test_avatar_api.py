"""头像 API 测试：上传（类型/大小校验）、内置选择、user/info 返回。"""
import io
import random
import string

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _register_and_token(prefix: str = "avt") -> str:
    name = prefix + "_" + "".join(random.choices(string.ascii_lowercase, k=6))
    r = client.post("/register", json={"username": name, "password": "pass123456"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["code"] == 200, data
    return data["token"]


def _tiny_png() -> bytes:
    """1x1 最小合法 PNG。"""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d4944415478da63fcff9f0100060401000ed10b0f0000000049454e44ae426082"
    )


class TestAvatarAPI:
    def test_avatar_requires_auth(self):
        r = client.post("/user/avatar", files={"file": ("x.png", _tiny_png(), "image/png")})
        assert r.status_code == 200 and r.json()["code"] == 401

    def test_upload_png_ok(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/user/avatar",
            files={"file": ("me.png", _tiny_png(), "image/png")},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["code"] == 200 and data["url"].startswith("/uploads/")

        # user/info 返回 avatar
        r2 = client.get("/user/info", headers=headers)
        assert r2.json()["data"]["avatar"] == data["url"]

    def test_upload_bad_type_rejected(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/user/avatar",
            files={"file": ("evil.exe", b"MZ....", "application/octet-stream")},
            headers=headers,
        )
        assert r.json()["code"] == 400
        # 伪装成 png 但内容非法扩展名也被拒
        r2 = client.post(
            "/user/avatar",
            files={"file": ("evil.txt", b"not an image", "text/plain")},
            headers=headers,
        )
        assert r2.json()["code"] == 400

    def test_upload_too_large_rejected(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}
        big = b"\x00" * (2 * 1024 * 1024 + 1)
        r = client.post(
            "/user/avatar",
            files={"file": ("big.png", big, "image/png")},
            headers=headers,
        )
        assert r.json()["code"] == 400

    def test_select_builtin_ok(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/user/avatar/select",
            json={"avatar": "/static/avatars/3.png"},
            headers=headers,
        )
        assert r.json()["code"] == 200
        assert r.json()["url"] == "/static/avatars/3.png"

    def test_select_invalid_path_rejected(self):
        token = _register_and_token()
        headers = {"Authorization": f"Bearer {token}"}
        r = client.post(
            "/user/avatar/select",
            json={"avatar": "/uploads/../../etc/passwd"},
            headers=headers,
        )
        assert r.json()["code"] == 400
