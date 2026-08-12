"""
Persistent memory store for Jinclaw.

Uses a file-per-fact pattern with a MEMORY.md index file.
Each memory is one markdown file with YAML frontmatter.
"""
from pathlib import Path
from typing import Dict, List, Optional
import os
import logging

logger = logging.getLogger(__name__)


class MemoryStore:
    """File-based persistent memory store."""

    def __init__(self, memory_dir: Optional[str] = None):
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        else:
            # Default: project_root/memory/
            self.memory_dir = self._find_project_root() / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "MEMORY.md"

    def _find_project_root(self) -> Path:
        cwd = Path.cwd()
        for parent in [cwd] + list(cwd.parents):
            if (parent / "AGENTS.md").exists() or (parent / "main.py").exists():
                return parent
        return cwd

    def list_all(self) -> List[Dict[str, str]]:
        """List all memory entries."""
        results = []
        if not self.index_file.exists():
            return results

        content = self.index_file.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("- [") and "](" in line:
                # Format: - [Title](file.md) — description
                title_part = line[3:].split("](")[0]
                file_part = line.split("](")[1].split(")")[0]
                desc = line.split(" — ")[-1] if " — " in line else ""
                results.append({
                    "title": title_part,
                    "file": file_part,
                    "description": desc,
                })
        return results

    def get(self, slug: str) -> Optional[str]:
        """Read a single memory file."""
        mem_file = self.memory_dir / f"{slug}.md"
        if mem_file.exists():
            return mem_file.read_text(encoding="utf-8")
        return None

    def save(self, title: str, content: str, slug: Optional[str] = None,
             description: str = "", metadata_type: str = "reference") -> str:
        """Save a new memory and update the index."""
        if slug is None:
            import re
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:60]

        # Write memory file
        mem_file = self.memory_dir / f"{slug}.md"
        frontmatter = f"""---
name: {slug}
description: {description or title}
metadata:
  type: {metadata_type}
---

{content}
"""
        mem_file.write_text(frontmatter, encoding="utf-8")

        # Update index
        self._update_index(title, slug, description)
        logger.info(f"[Memory] saved: {slug}")
        return slug

    def delete(self, slug: str) -> bool:
        """Delete a memory file and remove from index."""
        mem_file = self.memory_dir / f"{slug}.md"
        deleted = False
        if mem_file.exists():
            os.remove(mem_file)
            deleted = True

        # Remove from index
        if self.index_file.exists():
            lines = self.index_file.read_text(encoding="utf-8").split("\n")
            new_lines = [
                l for l in lines
                if not (l.strip().startswith("- [") and f"]({slug}.md)" in l)
            ]
            self.index_file.write_text("\n".join(new_lines), encoding="utf-8")

        logger.info(f"[Memory] deleted: {slug}")
        return deleted

    def _update_index(self, title: str, slug: str, description: str = ""):
        """Add or update an entry in MEMORY.md."""
        entry = f"- [{title}]({slug}.md)"
        if description:
            entry += f" — {description}"

        if self.index_file.exists():
            content = self.index_file.read_text(encoding="utf-8")
            # Replace existing entry with same slug or append
            if f"]({slug}.md)" in content:
                lines = content.split("\n")
                new_lines = [
                    entry if f"]({slug}.md)" in l else l
                    for l in lines
                ]
                self.index_file.write_text("\n".join(new_lines), encoding="utf-8")
            else:
                self.index_file.write_text(content.rstrip() + "\n" + entry + "\n", encoding="utf-8")
        else:
            self.index_file.write_text(
                "# Jinclaw Memory Index\n\n"
                "This file is an index of all persistent memories.\n"
                "Each entry links to a memory file in this directory.\n\n"
                + entry + "\n",
                encoding="utf-8",
            )

    @property
    def count(self) -> int:
        return len(self.list_all())
