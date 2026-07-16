# -*- coding: utf-8 -*-
"""
生成可分发的干净版本 -> release/ 目录。

自动排除：Git 记录、IDE 配置、虚拟环境、缓存、上传文件、
本地数据库、真实密钥(.env)、个人简历、调试草稿等。
你的当前工作目录不会被改动。
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "release")

# 需要排除的目录名（任意层级匹配）
EXCLUDE_DIRS = {
    ".git", ".idea", ".venv", "__pycache__", "release",
    "uploads", "test",
}

# 需要排除的具体文件（相对根目录的路径，用 / 分隔）
EXCLUDE_FILES = {
    ".env",
    "app.db",
    "make_release.py",
    "make_release.bat",
    "tools/tt.py",
    "tools/ttt.py",
    "欧锦财-Agent开发简历.md",
    "欧锦财-爬虫方向开发 .pdf",
}

# 需要排除的文件后缀
EXCLUDE_SUFFIXES = (".pyc", ".db")


def should_skip_file(rel_path):
    rel_norm = rel_path.replace("\\", "/")
    if rel_norm in EXCLUDE_FILES:
        return True
    if rel_norm.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def main():
    if os.path.exists(DEST):
        print("[提示] 检测到已存在的 release 目录，正在清空重建...")
        shutil.rmtree(DEST)
    os.makedirs(DEST)

    copied = 0
    for cur_dir, dir_names, file_names in os.walk(ROOT):
        # 原地过滤子目录，阻止 os.walk 进入被排除目录
        dir_names[:] = [d for d in dir_names if d not in EXCLUDE_DIRS]

        rel_dir = os.path.relpath(cur_dir, ROOT)
        if rel_dir == ".":
            rel_dir = ""

        for name in file_names:
            rel_path = os.path.join(rel_dir, name) if rel_dir else name
            if should_skip_file(rel_path):
                continue
            src = os.path.join(cur_dir, name)
            dst = os.path.join(DEST, rel_path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1

    # 运行时需要一个空的 uploads 目录
    uploads_dir = os.path.join(DEST, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    # 放一个占位文件，确保空目录能被压缩保留
    keep = os.path.join(uploads_dir, ".gitkeep")
    if not os.path.exists(keep):
        open(keep, "w").close()

    if not os.path.exists(os.path.join(DEST, ".env.example")):
        print("[警告] 未找到 .env.example，请检查。")

    print("")
    print("[完成] 已复制 %d 个文件到 release/ 目录。" % copied)
    print("交付前请再次确认 release/ 中不含任何密钥或个人文件。")
    print("建议将 release/ 目录压缩为 zip 后上传咸鱼。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("[错误] 打包失败：%s" % e)
        sys.exit(1)
