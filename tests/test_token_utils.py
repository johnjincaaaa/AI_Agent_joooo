"""Tests for token_utils — JWT create/verify for user + admin tokens."""
import time
import pytest
from jose import jwt
from fastapi import HTTPException

import token_utils


class TestCreateAccessToken:
    def test_contains_user_id(self):
        token = token_utils.create_access_token({"user_id": 42})
        payload = jwt.decode(token, "test-secret-key-for-pytest-only-12345", algorithms=["HS256"])
        assert payload["user_id"] == 42

    def test_contains_expiry(self):
        token = token_utils.create_access_token({"user_id": 1})
        payload = jwt.decode(token, "test-secret-key-for-pytest-only-12345", algorithms=["HS256"])
        assert "exp" in payload
        # default = 60min — check it's roughly in that range
        assert payload["exp"] > time.time() + 50 * 60


class TestDecodeUserId:
    def test_roundtrip(self):
        token = token_utils.create_access_token({"user_id": 7})
        assert token_utils.decode_user_id(token) == 7

    def test_missing_user_id_raises_401(self):
        # Token signed with unrelated data (no user_id)
        token = jwt.encode({"foo": "bar"}, "test-secret-key-for-pytest-only-12345", algorithm="HS256")
        with pytest.raises(HTTPException) as exc:
            token_utils.decode_user_id(token)
        assert exc.value.status_code == 401

    def test_wrong_secret_raises(self):
        token = jwt.encode({"user_id": 3}, "some-other-key", algorithm="HS256")
        with pytest.raises(Exception):  # JWTError via verify_token
            token_utils.verify_token(token)


class TestVerifyToken:
    def test_ok(self):
        token = token_utils.create_access_token({"user_id": 55})
        assert token_utils.verify_token(token) == 55

    def test_bad_token_raises_401_dict(self):
        with pytest.raises(HTTPException) as exc:
            token_utils.verify_token("not-a-real-jwt")
        assert exc.value.status_code == 401
        # detail must be a dict per frontend expectation
        detail = exc.value.detail
        assert isinstance(detail, dict)
        assert detail.get("code") == 401


class TestOptionalUserId:
    def test_none_when_missing(self):
        assert token_utils.get_optional_user_id(None) is None

    def test_returns_id_when_valid(self):
        token = token_utils.create_access_token({"user_id": 99})
        assert token_utils.get_optional_user_id(token) == 99

    def test_invalid_token_gracefully_returns_none(self):
        assert token_utils.get_optional_user_id("garbage-token") is None


class TestAdminToken:
    def test_create_and_verify(self):
        tok = token_utils.create_admin_token()
        assert token_utils.verify_admin_token(tok) is True

    def test_missing_token_raises(self):
        with pytest.raises(HTTPException) as exc:
            token_utils.verify_admin_token(None)
        assert exc.value.status_code == 401
        assert "未登录后台" in exc.value.detail["msg"]

    def test_user_token_not_admin(self):
        user_tok = token_utils.create_access_token({"user_id": 1})
        with pytest.raises(HTTPException) as exc:
            token_utils.verify_admin_token(user_tok)
        assert "无后台权限" in exc.value.detail["msg"]

    def test_bad_admin_token(self):
        with pytest.raises(HTTPException) as exc:
            token_utils.verify_admin_token("not-a-token")
        assert "令牌无效或已过期" in exc.value.detail["msg"]
