#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
饭太硬（JPEG + Base64 封装）本地提取脚本
适用于 GitHub Actions 海外节点易返回空响应、需在本地/国内环境提取的场景。
"""
import base64
import json
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(ROOT, "output", "fantaiying.json")

DEFAULT_URLS = [
    "http://www.xn--sss604efuw.net/tv",
]

HEADERS = {
    "User-Agent": "okhttp/4.12.0",
    "Accept": "*/*",
}


def decode_fty_bytes(data: bytes) -> dict:
    eoi = data.rfind(b"\xff\xd9")
    if eoi == -1:
        raise ValueError("未找到 JPEG 结束标记 FFD9")

    payload = data[eoi + 2 :]
    if not payload:
        raise ValueError("JPEG 结束标记后无有效载荷")

    b64_str = re.sub(rb"[^A-Za-z0-9+/=]", b"", payload)
    b64_str += b"=" * ((4 - len(b64_str) % 4) % 4)
    raw = base64.b64decode(b64_str)

    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff").strip()

    idx_spider = text.find('"spider"')
    idx_brace = text.find("{")
    if idx_spider != -1 and (idx_brace == -1 or idx_spider < idx_brace):
        body = text[idx_spider:].strip().rstrip(",")
        if not body.startswith("{"):
            body = "{\n" + body
        if not body.endswith("}"):
            body = body + "\n}"
        text = body
    elif idx_brace != -1:
        text = text[idx_brace:]
    else:
        raise ValueError("解码文本中未找到 JSON 起始位置")

    # 剔除整行 // 注释（保留 http:// / https://）
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
    cleaned = "\n".join(lines)

    # 清理数组/对象闭合前的多余逗号
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

    obj = json.loads(cleaned, strict=False)
    if not isinstance(obj, dict) or not any(k in obj for k in ("sites", "lives", "spider")):
        raise ValueError("解析结果不是合法的 TVBox 配置对象")
    return obj


def fetch_one(url: str, timeout: int = 15) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return decode_fty_bytes(resp.content)


def main() -> int:
    urls = sys.argv[1:] or DEFAULT_URLS
    last_err = None
    for u in urls:
        try:
            data = fetch_one(u)
            os.makedirs(os.path.dirname(DEFAULT_OUT), exist_ok=True)
            with open(DEFAULT_OUT, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(
                f"[OK] {u} -> {DEFAULT_OUT} "
                f"(sites={len(data.get('sites', []))}, lives={len(data.get('lives', []))})"
            )
            return 0
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[FAIL] {u} -> {e}")
    print(f"全部失败：{last_err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
