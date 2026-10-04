"""输入适配器协议：每种材料来源一个 adapter，统一输出结构化 Markdown。

约定：Markdown 中用 <!-- pN --> 作为页码锚点，供 source_page / source_span 溯源。
自学模式（v0.5）= 新增 epub/web 等 adapter，下游零改动。
"""
from pathlib import Path
from typing import Protocol


class Adapter(Protocol):
    def supports(self, path: Path) -> bool: ...

    def extract(self, path: Path) -> str:
        """返回带页码锚点的 Markdown 中间产物。"""
        ...
