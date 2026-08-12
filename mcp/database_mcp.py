"""
Database MCP：数据库操作工具
支持：MySQL、SQLite、Redis
"""
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


def register_database_tools(manager):
    """注册数据库相关工具。"""

    manager.register_tool(
        name="mcp_db_query",
        func=db_query,
        description="执行数据库查询（SQL / Redis 命令）。",
        parameters={
            "db_type": "数据库类型：sqlite / mysql / redis",
            "connection": "连接字符串（SQLite 为文件路径）",
            "query": "SQL 查询语句或 Redis 命令",
        },
    )

    manager.register_tool(
        name="mcp_db_execute",
        func=db_execute,
        description="执行数据库写操作（INSERT/UPDATE/DELETE）。",
        parameters={
            "db_type": "数据库类型：sqlite / mysql",
            "connection": "连接字符串",
            "query": "SQL 语句",
        },
    )

    manager.register_tool(
        name="mcp_db_tables",
        func=db_tables,
        description="列出数据库中的所有表。",
        parameters={"db_type": "数据库类型", "connection": "连接字符串"},
    )


def db_query(db_type: str = "sqlite", connection: str = "", query: str = "") -> str:
    """执行数据库查询。"""
    try:
        if not query:
            return "错误：请提供查询语句"

        db_type = db_type.lower()

        if db_type == "sqlite":
            return _sqlite_query(connection, query)
        elif db_type == "mysql":
            return _mysql_query(connection, query)
        elif db_type == "redis":
            return _redis_command(connection, query)
        else:
            return f"错误：不支持的数据库类型 - {db_type}"

    except Exception as e:
        return f"数据库查询失败: {str(e)}"


def db_execute(db_type: str = "sqlite", connection: str = "", query: str = "") -> str:
    """执行数据库写操作。"""
    try:
        if not query:
            return "错误：请提供 SQL 语句"

        db_type = db_type.lower()

        if db_type == "sqlite":
            return _sqlite_execute(connection, query)
        elif db_type == "mysql":
            return _mysql_execute(connection, query)
        else:
            return f"错误：不支持的数据库类型 - {db_type}"

    except Exception as e:
        return f"数据库操作失败: {str(e)}"


def db_tables(db_type: str = "sqlite", connection: str = "") -> str:
    """列出数据库中的表。"""
    try:
        db_type = db_type.lower()

        if db_type == "sqlite":
            return _sqlite_query(connection, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        elif db_type == "mysql":
            return _mysql_query(connection, "SHOW TABLES;")
        else:
            return f"错误：不支持的数据库类型 - {db_type}"

    except Exception as e:
        return f"获取表列表失败: {str(e)}"


def _sqlite_query(db_path: str, query: str) -> str:
    """SQLite 查询。"""
    import sqlite3

    if not db_path:
        return "错误：请提供 SQLite 数据库文件路径"

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        if not rows:
            return "查询成功，无结果返回。"

        # 格式化输出
        output = f"查询成功，共 {len(rows)} 行结果：\n\n"
        output += " | ".join(columns) + "\n"
        output += "-" * (len(columns) * 15) + "\n"
        for row in rows[:50]:  # 限制显示 50 行
            output += " | ".join(str(v) for v in row) + "\n"
        if len(rows) > 50:
            output += f"\n... 还有 {len(rows) - 50} 行未显示"
        return output.strip()
    finally:
        conn.close()


def _sqlite_execute(db_path: str, query: str) -> str:
    """SQLite 写操作。"""
    import sqlite3

    if not db_path:
        return "错误：请提供 SQLite 数据库文件路径"

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        return f"执行成功，影响行数：{cursor.rowcount}"
    finally:
        conn.close()


def _mysql_query(connection_str: str, query: str) -> str:
    """MySQL 查询。"""
    try:
        import pymysql
    except ImportError:
        return "错误：pymysql 未安装，请运行: pip install pymysql"

    if not connection_str:
        return "错误：请提供 MySQL 连接字符串（格式：host:port:user:password:database）"

    parts = connection_str.split(":")
    if len(parts) < 5:
        return "错误：连接字符串格式应为 host:port:user:password:database"

    host, port, user, password, database = parts[0], int(parts[1]), parts[2], parts[3], parts[4]

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        if not rows:
            return "查询成功，无结果返回。"

        output = f"查询成功，共 {len(rows)} 行结果：\n\n"
        output += " | ".join(columns) + "\n"
        output += "-" * (len(columns) * 15) + "\n"
        for row in rows[:50]:
            output += " | ".join(str(v) for v in row) + "\n"
        if len(rows) > 50:
            output += f"\n... 还有 {len(rows) - 50} 行未显示"
        return output.strip()
    finally:
        conn.close()


def _mysql_execute(connection_str: str, query: str) -> str:
    """MySQL 写操作。"""
    try:
        import pymysql
    except ImportError:
        return "错误：pymysql 未安装，请运行: pip install pymysql"

    if not connection_str:
        return "错误：请提供 MySQL 连接字符串"

    parts = connection_str.split(":")
    if len(parts) < 5:
        return "错误：连接字符串格式应为 host:port:user:password:database"

    host, port, user, password, database = parts[0], int(parts[1]), parts[2], parts[3], parts[4]

    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        return f"执行成功，影响行数：{cursor.rowcount}"
    finally:
        conn.close()


def _redis_command(connection_str: str, command: str) -> str:
    """Redis 命令执行。"""
    try:
        import redis
    except ImportError:
        return "错误：redis 库未安装，请运行: pip install redis"

    if not connection_str:
        return "错误：请提供 Redis 连接字符串（格式：host:port:db:password）"

    parts = connection_str.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else 6379
    db = int(parts[2]) if len(parts) > 2 else 0
    password = parts[3] if len(parts) > 3 else None

    r = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
    try:
        # 解析并执行命令
        parts = command.split()
        if not parts:
            return "错误：请提供 Redis 命令"

        cmd = parts[0].lower()
        args = parts[1:]

        result = getattr(r, cmd)(*args)
        if isinstance(result, list):
            return f"命令执行成功：\n" + "\n".join(str(v) for v in result[:100])
        elif isinstance(result, dict):
            return f"命令执行成功：\n{json.dumps(result, indent=2, ensure_ascii=False)}"
        else:
            return f"命令执行成功：{result}"
    except AttributeError:
        return f"错误：不支持的 Redis 命令 - {parts[0]}"
    except Exception as e:
        return f"Redis 命令执行失败: {str(e)}"
