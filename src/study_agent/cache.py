"""内容哈希缓存（P0）：输入内容不变就直接命中，改哪页只重跑哪页的下游。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class Cache:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _path(self, namespace: str, content: str) -> Path:
        d = self.root / namespace
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.key(content)}.json"

    def get(self, namespace: str, content: str):
        p = self._path(namespace, content)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def set(self, namespace: str, content: str, data) -> None:
        self._path(namespace, content).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
