#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path


def load_local_env() -> None:
    """从项目根目录的 .env.local 读取运行环境变量。"""
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env.local"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
