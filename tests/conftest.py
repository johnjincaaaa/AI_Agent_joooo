"""
Shared pytest fixtures for Jingent AI tests.

CRITICAL: SECRET_KEY must be patched BEFORE `import config` happens,
because config reads SECRET_KEY at module-import time.  We use the
`session`-scoped pytest_configure hook + monkeypatch via the
`importmode=importlib` mechanism: the env gets set once before any
test module is imported, and autouse fixtures on top guarantee a
test-level override.
"""
import os
import sys
from pathlib import Path
import pytest


# Force the test secret key into the OS environment immediately
# (before conftest.py finishes loading = before ANY user test import).
_TEST_SECRET = "test-secret-key-for-pytest-only-12345"
os.environ["SECRET_KEY"] = _TEST_SECRET
os.environ.setdefault("LLM_API_KEY", "test-fake-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pass")


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """Per-test guard: ensure tests never share real config state from .env."""
    monkeypatch.setenv("SECRET_KEY", _TEST_SECRET)
    monkeypatch.setenv("LLM_API_KEY", "test-fake-key")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-pass")

    # Now that env is patched, force config to re-read SECRET_KEY (it was imported with
    # the session value above; but for safety, also reset the module-level variable
    # so any tests that read config.SECRET_KEY directly see the test value.)
    import config as _cfg
    import token_utils as _tu

    orig_secret = _cfg.SECRET_KEY
    orig_algorithm = _cfg.ALGORITHM
    _cfg.SECRET_KEY = _TEST_SECRET
    _tu.SECRET_KEY = _TEST_SECRET
    yield
    _cfg.SECRET_KEY = orig_secret
    _tu.SECRET_KEY = orig_secret


@pytest.fixture()
def tmp_home(monkeypatch, tmp_path: Path) -> Path:
    """Redirect Path.home() to a temp dir for isolated storage tests."""
    home = tmp_path / "fake_home"
    home.mkdir(parents=True, exist_ok=True)
    # Path.home() on Windows reads USERPROFILE first, then HOME.
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    return home
