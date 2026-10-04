"""DeepSeek API 客户端（OpenAI 兼容协议）。

密钥读环境变量 DEEPSEEK_API_KEY；未设置直接报错，不静默降级。
"""
from __future__ import annotations

import os

import httpx

API_URL = "https://api.deepseek.com/v1/chat/completions"


def chat(
    system: str,
    user: str,
    model: str = "deepseek-chat",
    temperature: float = 0.2,
    retries: int = 3,
) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError(
            "未设置 DEEPSEEK_API_KEY。本机禁 cmd/注册表，"
            "请走 系统设置 → 高级 → 环境变量 GUI 添加用户变量，"
            "或在 PyCharm Run Configuration 里配置。"
        )
    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            r = httpx.post(
                API_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            last_err = e
    raise RuntimeError(f"DeepSeek API 调用失败（重试 {retries} 次）: {last_err}")
