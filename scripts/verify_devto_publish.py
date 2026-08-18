#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dev.to 真实发布端到端验证。

用法：
    python3 scripts/verify_devto_publish.py <API_KEY>
    # 用真实 key 发布一条测试文章到你的 Dev.to 账号，验证后返回文章链接。

也支持从环境变量读取：DEVTO_API_KEY=xxx python3 scripts/verify_devto_publish.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from omp_paths import data_dir  # noqa: E402

KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DEVTO_API_KEY", "")
if not KEY:
    print("❌ 请提供 Dev.to API Key：python3 scripts/verify_devto_publish.py <API_KEY>")
    sys.exit(1)

# 1. 保存凭据到两处（本地 + SAU）
creds = {"api_key": KEY}
targets = [
    data_dir() / "cookies" / "devto_default.json",
    Path.home() / "social-auto-upload" / "cookies" / "devto_default.json",
]
for t in targets:
    t.parent.mkdir(parents=True, exist_ok=True)
    t.write_text(json.dumps(creds, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 凭据已写入 {t}")

# 2. 真实发布
sys.path.insert(0, str(Path.home() / "social-auto-upload"))
from custom_uploaders.devto_uploader import publish  # noqa: E402

title = f"OMP E2E 验证 {time.strftime('%H%M%S')}"
ok = publish("/tmp/omp_e2e_test.mp4", title, ["test"], "Open Matrix Publisher 端到端验证：一条内容，多域分发。")
print(f"\n{'🎉 真实发布成功！' if ok else '❌ 发布失败'}")
sys.exit(0 if ok else 1)
