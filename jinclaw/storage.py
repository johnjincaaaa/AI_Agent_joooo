"""
JingentStorage — manages ~/.jingent/ directory for Jinclaw Agent.

Data model (per-user isolated, user_id=NULL for anonymous legacy users):
    Project = workspace folder (1:1 binding)
    Task = conversation within a project, with AI-generated nickname

Directory:
    ~/.jingent/
    ├── jingent.db
    └── tasks/{task_id}/
        ├── chat.jsonl
        ├── diffs/
        └── meta.json
"""
import json
import sqlite3
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_uid(user_id: Optional[int]) -> Optional[int]:
    """统一 user_id 格式：匿名传 0/None/false -> 统一存 None（legacy），其它必须是 int。"""
    if user_id is None:
        return None
    try:
        i = int(user_id)
        if i <= 0:
            return None
        return i
    except Exception:
        return None


class JingentStorage:
    def __init__(self):
        self.home = Path.home() / ".jingent"
        self.db_path = self.home / "jingent.db"
        self.tasks_dir = self.home / "tasks"
        self._init_dirs()
        self._init_db()

    def _init_dirs(self):
        self.home.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        # ── v1 原始表（无 user_id）：用 CREATE … IF NOT EXISTS 保证不报错 ──
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_path TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS diffs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                patch TEXT NOT NULL,
                applied INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        # ── v2 迁移：给每张表加 user_id 列 + 重建索引（无则加，已有列 ALTER 不会重复）──
        try:
            conn.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE diffs ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass
        # workspace_path 原本是 UNIQUE，这会导致不同用户不能绑同一个文件夹
        # 改为 (workspace_path, user_id) 联合唯一：先删旧 UNIQUE（SQLite 只能重建表），再建索引
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
            idx_list_rows = list(conn.execute("PRAGMA index_list(projects)").fetchall())
            # PRAGMA index_list 的列顺序：seq, name, unique, origin, partial。用 dict(row) 不依赖位置
            has_ws_only_uniq = False
            for row in idx_list_rows:
                rowd = dict(zip([d[0] for d in row.keys()], row)) if hasattr(row, "keys") else None
                if rowd is None:
                    # sqlite3.Row 支持按字段名访问
                    try:
                        idx_name = row["name"]
                        is_unique = bool(row["unique"])
                    except Exception:
                        # 兜底按常见位置 1=name, 2=unique
                        idx_name = row[1]
                        is_unique = bool(row[2])
                else:
                    idx_name = rowd.get("name")
                    is_unique = bool(rowd.get("unique"))
                cols_in_idx = [
                    r["name"] if hasattr(r, "keys") else r[2]
                    for r in conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
                ]
                if cols_in_idx == ["workspace_path"] and is_unique:
                    has_ws_only_uniq = True
                    break
            if has_ws_only_uniq:
                # SQLite 无法 DROP UNIQUE，只能重建表。使用保守的 RENAME + 回填方案
                import random as _r
                suffix = _r.randint(1000, 9999)
                conn.execute(f"ALTER TABLE projects RENAME TO projects_old_{suffix}")
                pk_line = "id TEXT PRIMARY KEY"
                col_line = ", ".join([
                    "id TEXT PRIMARY KEY",
                    "name TEXT NOT NULL",
                    "workspace_path TEXT NOT NULL",
                    "created_at TEXT NOT NULL",
                    "updated_at TEXT NOT NULL",
                    "user_id INTEGER",
                ])
                conn.execute(f"CREATE TABLE projects ({col_line})")
                conn.execute(
                    f"INSERT INTO projects ({','.join(cols)}) "
                    f"SELECT {','.join(cols)} FROM projects_old_{suffix}"
                )
                conn.execute(f"DROP TABLE projects_old_{suffix}")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_ws_uid "
                "ON projects(workspace_path, COALESCE(user_id, -1))")
        except Exception as _e:
            import logging as _lg
            _lg.getLogger(__name__).warning("projects UNIQUE migration skipped: %s", _e)
        # 普通索引：按 user_id 查询是高频
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_uid ON projects(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_uid ON tasks(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_pid ON tasks(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_diffs_uid ON diffs(user_id)")
        conn.commit()
        conn.close()

    def _conn(self):
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    # ── 内部帮助：拼接 (user_id IS ?) 条件，保证匿名 user_id=NULL 也能被正确过滤 ──
    @staticmethod
    def _uid_cond(col: str, uid: Optional[int]) -> Tuple[str, Tuple]:
        """返回 (sql_where_fragment, params_tuple)，匿名/空 uid 默认走 user_id IS NULL。"""
        n = _norm_uid(uid)
        if n is None:
            return f"({col} IS NULL)", ()
        return f"({col} = ?)", (n,)

    # ── Project CRUD ────────────────────────────────

    def list_projects(self, user_id: Optional[int] = None) -> List[Dict]:
        c = self._conn()
        cond, params = self._uid_cond("user_id", user_id)
        rows = c.execute(
            f"SELECT * FROM projects WHERE {cond} ORDER BY updated_at DESC", params
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_project(self, pid: str, user_id: Optional[int] = None) -> Optional[Dict]:
        c = self._conn()
        cond, params = self._uid_cond("user_id", user_id)
        r = c.execute(
            f"SELECT * FROM projects WHERE id = ? AND {cond}", (pid,) + params
        ).fetchone()
        c.close()
        return dict(r) if r else None

    def find_project_by_workspace(self, ws: str, user_id: Optional[int] = None) -> Optional[Dict]:
        c = self._conn()
        cond, params = self._uid_cond("user_id", user_id)
        r = c.execute(
            f"SELECT * FROM projects WHERE workspace_path = ? AND {cond}",
            (ws,) + params,
        ).fetchone()
        c.close()
        return dict(r) if r else None

    def create_project(self, name: str, workspace_path: str, user_id: Optional[int] = None) -> Dict:
        uid = _norm_uid(user_id)
        # If a project with this workspace already exists for THIS user, return it
        existing = self.find_project_by_workspace(workspace_path, uid)
        if existing:
            return existing
        pid = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        c = self._conn()
        c.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?)",
            (pid, name, workspace_path, now, now, uid),
        )
        c.commit()
        c.close()
        self._touch_project_meta(pid, name, workspace_path, now)
        return {
            "id": pid, "name": name, "workspace_path": workspace_path,
            "created_at": now, "updated_at": now, "user_id": uid,
        }

    def delete_project(self, pid: str, user_id: Optional[int] = None) -> bool:
        uid = _norm_uid(user_id)
        # 先按 (id, user_id) 确认归属，再删所有 tasks 目录 + 行
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        pid_row = c.execute(
            f"SELECT id FROM projects WHERE id = ? AND {cond}", (pid,) + params
        ).fetchone()
        if not pid_row:
            c.close()
            return False
        for t in c.execute(
            f"SELECT id FROM tasks WHERE project_id = ? AND "
            f"{self._uid_cond('user_id', uid)[0]}",
            (pid,) + self._uid_cond("user_id", uid)[1],
        ).fetchall():
            self._rm_task_dir(t["id"])
        c.execute(
            f"DELETE FROM tasks WHERE project_id = ? AND "
            f"{self._uid_cond('user_id', uid)[0]}",
            (pid,) + self._uid_cond("user_id", uid)[1],
        )
        c.execute(f"DELETE FROM projects WHERE id = ? AND {cond}", (pid,) + params)
        c.commit()
        c.close()
        return True

    def update_project_name(self, pid: str, name: str, user_id: Optional[int] = None):
        uid = _norm_uid(user_id)
        now = datetime.now().isoformat()
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        c.execute(
            f"UPDATE projects SET name = ?, updated_at = ? WHERE id = ? AND {cond}",
            (name, now, pid) + params,
        )
        c.commit()
        c.close()

    def _touch_project_meta(self, pid, name, ws, now):
        pass  # meta managed by DB

    # ── Task CRUD ───────────────────────────────────

    def list_tasks(self, project_id: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict]:
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        if project_id:
            rows = c.execute(
                f"SELECT * FROM tasks WHERE project_id = ? AND {cond} "
                f"ORDER BY updated_at DESC",
                (project_id,) + params,
            ).fetchall()
        else:
            rows = c.execute(
                f"SELECT * FROM tasks WHERE {cond} ORDER BY updated_at DESC", params
            ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_task(self, tid: str, user_id: Optional[int] = None) -> Optional[Dict]:
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        r = c.execute(
            f"SELECT * FROM tasks WHERE id = ? AND {cond}", (tid,) + params
        ).fetchone()
        c.close()
        return dict(r) if r else None

    def create_task(self, project_id: str, name: str = "新任务", user_id: Optional[int] = None) -> Dict:
        uid = _norm_uid(user_id)
        # 确认 project 属于该 user
        if not self.get_project(project_id, uid):
            raise ValueError(f"project {project_id} not found for user {uid}")
        tid = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        c = self._conn()
        c.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?)",
            (tid, project_id, name, now, now, uid),
        )
        c.execute(
            f"UPDATE projects SET updated_at = ? WHERE id = ? AND "
            f"{self._uid_cond('user_id', uid)[0]}",
            (now, project_id) + self._uid_cond("user_id", uid)[1],
        )
        c.commit()
        c.close()
        tdir = self.tasks_dir / tid
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "diffs").mkdir(exist_ok=True)
        (tdir / "meta.json").write_text(
            json.dumps(
                {"name": name, "project_id": project_id, "user_id": uid,
                 "created_at": now, "updated_at": now},
                ensure_ascii=False, indent=2,
            ), encoding="utf-8",
        )
        return {
            "id": tid, "project_id": project_id, "name": name,
            "created_at": now, "updated_at": now, "user_id": uid,
        }

    def delete_task(self, tid: str, user_id: Optional[int] = None) -> bool:
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        c.execute(
            f"DELETE FROM diffs WHERE task_id IN "
            f"(SELECT id FROM tasks WHERE id = ? AND {cond})",
            (tid,) + params,
        )
        cur = c.execute(f"DELETE FROM tasks WHERE id = ? AND {cond}", (tid,) + params)
        c.commit()
        c.close()
        deleted = cur.rowcount > 0
        if deleted:
            self._rm_task_dir(tid)
        return deleted

    def rename_task(self, tid: str, name: str, user_id: Optional[int] = None):
        uid = _norm_uid(user_id)
        now = datetime.now().isoformat()
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        c.execute(
            f"UPDATE tasks SET name = ?, updated_at = ? WHERE id = ? AND {cond}",
            (name, now, tid) + params,
        )
        c.commit()
        c.close()

    def _rm_task_dir(self, tid):
        d = self.tasks_dir / tid
        if d.exists():
            shutil.rmtree(d)

    # ── Chat ────────────────────────────────────────

    def save_chat_line(self, task_id: str, event: dict, user_id: Optional[int] = None) -> bool:
        # 归属校验：task 必须归属于该 user
        if not self.get_task(task_id, user_id):
            return False
        p = self.tasks_dir / task_id / "chat.jsonl"
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True

    def load_chat_history(self, task_id: str, user_id: Optional[int] = None) -> List[dict]:
        # 归属校验：task 必须归属于该 user，否则返回空（防越权）
        if not self.get_task(task_id, user_id):
            return []
        p = self.tasks_dir / task_id / "chat.jsonl"
        if not p.exists():
            return []
        events = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return events

    # ── Diffs ───────────────────────────────────────

    def save_diff(self, task_id: str, file_path: str, patch: str, user_id: Optional[int] = None) -> Optional[str]:
        uid = _norm_uid(user_id)
        if not self.get_task(task_id, uid):
            return None
        did = uuid.uuid4().hex[:8]
        now = datetime.now().isoformat()
        c = self._conn()
        c.execute(
            "INSERT INTO diffs VALUES (?,?,?,?,?,?,?)",
            (did, task_id, file_path, patch, 0, now, uid),
        )
        c.commit(); c.close()
        tdir = self.tasks_dir / task_id
        if tdir.exists():
            (tdir / "diffs").mkdir(exist_ok=True)
            (tdir / "diffs" / f"{did}.patch").write_text(patch, encoding="utf-8")
        return did

    def list_diffs(self, task_id: str, user_id: Optional[int] = None) -> List[Dict]:
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        rows = c.execute(
            f"SELECT * FROM diffs WHERE task_id = ? AND {cond} ORDER BY created_at DESC",
            (task_id,) + params,
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]

    def get_diff(self, did: str, user_id: Optional[int] = None) -> Optional[Dict]:
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        r = c.execute(
            f"SELECT * FROM diffs WHERE id = ? AND {cond}", (did,) + params
        ).fetchone()
        c.close()
        return dict(r) if r else None

    def mark_diff_applied(self, did: str, applied: bool = True, user_id: Optional[int] = None):
        uid = _norm_uid(user_id)
        c = self._conn()
        cond, params = self._uid_cond("user_id", uid)
        c.execute(
            f"UPDATE diffs SET applied = ? WHERE id = ? AND {cond}",
            (1 if applied else 0, did) + params,
        )
        c.commit(); c.close()
