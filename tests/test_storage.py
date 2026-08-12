"""Tests for JingentStorage — projects, tasks, diffs, chat persistence."""
import json
import pytest
from pathlib import Path


@pytest.fixture()
def storage(tmp_home: Path):
    """Each test gets an isolated JingentStorage bound to a temp HOME."""
    # Import fresh after HOME is patched by tmp_home
    from jinclaw.storage import JingentStorage
    return JingentStorage()


class TestProjectCRUD:
    def test_create_and_list(self, storage):
        p = storage.create_project("Demo", "/tmp/ws-1")
        assert p["id"]
        assert p["name"] == "Demo"
        assert p["workspace_path"] == "/tmp/ws-1"
        assert len(storage.list_projects()) == 1

    def test_same_workspace_deduped(self, storage):
        p1 = storage.create_project("A", "/ws-2")
        p2 = storage.create_project("B", "/ws-2")
        assert p1["id"] == p2["id"], "同一路径应返回已有项目，不创建新记录"
        assert len(storage.list_projects()) == 1

    def test_get_by_id(self, storage):
        p = storage.create_project("X", "/ws-3")
        got = storage.get_project(p["id"])
        assert got is not None
        assert got["name"] == "X"

    def test_get_missing_returns_none(self, storage):
        assert storage.get_project("does-not-exist") is None

    def test_find_by_workspace(self, storage):
        storage.create_project("P", "/ws-4")
        found = storage.find_project_by_workspace("/ws-4")
        assert found and found["name"] == "P"
        assert storage.find_project_by_workspace("/ws-missing") is None

    def test_delete_project_also_deletes_tasks(self, storage):
        p = storage.create_project("Pr", "/ws-5")
        t = storage.create_task(p["id"], "Task 1")
        # Sanity
        assert len(storage.list_tasks(p["id"])) == 1
        storage.delete_project(p["id"])
        assert storage.get_project(p["id"]) is None
        assert len(storage.list_tasks(p["id"])) == 0
        # Task directory must be gone too
        assert not (storage.tasks_dir / t["id"]).exists()


class TestTaskCRUD:
    def test_create_bumps_project_updated_at(self, storage):
        p = storage.create_project("Pr", "/ws-6")
        first_updated = p["updated_at"]
        # Force a tiny wait because isoformat() only has seconds resolution on some platforms
        import time; time.sleep(0.01)
        t = storage.create_task(p["id"], "New Task")
        p2 = storage.get_project(p["id"])
        assert p2["updated_at"] >= first_updated
        assert t["project_id"] == p["id"]

    def test_delete_task_existing(self, storage):
        p = storage.create_project("Pr", "/ws-7")
        t = storage.create_task(p["id"])
        assert storage.delete_task(t["id"]) is True
        assert storage.get_task(t["id"]) is None

    def test_delete_task_missing(self, storage):
        assert storage.delete_task("no-such-task") is False

    def test_rename_task(self, storage):
        p = storage.create_project("Pr", "/ws-8")
        t = storage.create_task(p["id"], "old")
        storage.rename_task(t["id"], "new")
        assert storage.get_task(t["id"])["name"] == "new"

    def test_list_tasks_filtered(self, storage):
        p1 = storage.create_project("P1", "/ws-a")
        p2 = storage.create_project("P2", "/ws-b")
        storage.create_task(p1["id"], "t1")
        storage.create_task(p1["id"], "t2")
        storage.create_task(p2["id"], "t3")
        assert len(storage.list_tasks(p1["id"])) == 2
        assert len(storage.list_tasks(p2["id"])) == 1
        assert len(storage.list_tasks(None)) == 3


class TestChatAndDiffs:
    def test_chat_roundtrip(self, storage):
        p = storage.create_project("Pr", "/ws-9")
        t = storage.create_task(p["id"])
        storage.save_chat_line(t["id"], {"type": "user", "message": "hello"})
        storage.save_chat_line(t["id"], {"type": "assistant", "message": "hi"})
        events = storage.load_chat_history(t["id"])
        assert len(events) == 2
        assert events[0]["message"] == "hello"

    def test_chat_missing_task_returns_empty(self, storage):
        assert storage.load_chat_history("nope") == []

    def test_chat_corrupt_line_skipped(self, storage):
        p = storage.create_project("Pr", "/ws-10")
        t = storage.create_task(p["id"])
        # Write a malformed line followed by a valid one
        p = storage.tasks_dir / t["id"] / "chat.jsonl"
        p.write_text("{not valid json}\n{\"type\":\"user\"}\n", encoding="utf-8")
        events = storage.load_chat_history(t["id"])
        assert len(events) == 1
        assert events[0]["type"] == "user"

    def test_diff_crud(self, storage):
        p = storage.create_project("Pr", "/ws-11")
        t = storage.create_task(p["id"])
        did = storage.save_diff(t["id"], "a.py", "@@ -1,1 +1,2 @@\n a\n+b\n")
        assert storage.get_diff(did) is not None
        assert len(storage.list_diffs(t["id"])) == 1
        storage.mark_diff_applied(did, True)
        assert storage.get_diff(did)["applied"] == 1
        storage.mark_diff_applied(did, False)
        assert storage.get_diff(did)["applied"] == 0
