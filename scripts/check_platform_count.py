#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI 检查：固化「16 平台口径」。

扫描 README / 执行手册 / 宣传文档（docs/、skills/ 下的所有 Markdown），
若出现 28 / 18 / 15 / 14+ / 7 等旧平台数字（后跟平台语境词）即报错，退出码 1。

设计要点：
- 数字必须紧跟「平台/大/个/国内外/主流」等语境词，避免误报「15 秒」「7 天」等无关数字；
- 清理说明里「28/18/15/14+/7 等旧表述」这类字面量（斜杠列表、后无「平台」）不会被误抓；
- 当前正确口径固定为 16（国内 10 + 海外 6），16 不在检测列表内。

用法：
    python scripts/check_platform_count.py            # 扫描全部目标文档
    python scripts/check_platform_count.py --verbose  # 打印扫描到的文件数
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 待扫描的 Markdown 文档（README / 执行手册 / 宣传文档）
SCAN_PATTERNS = [
    "README.md",
    "执行手册.md",
    "*.md",              # 仓库根目录其他 md（如 GITHUB_OPENSOURCE_STRATEGY.md）
    "docs/**/*.md",
    "skills/**/*.md",
]

# 旧平台数字口径：数字 + 平台语境词
OLD_COUNT_RE = re.compile(
    r"(?:28|18|15)\s*(?:个|大)?\s*(?:国内外|主流)?\s*平台"
    r"|14\s*\+\s*(?:个|大)?\s*平台"
    r"|7\s*(?:个|大)\s*(?:国内外|主流)?\s*平台"
)


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for pat in SCAN_PATTERNS:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p.suffix == ".md":
                files.append(p)
    # 去重并保持稳定顺序
    return sorted(set(files))


def check_file(path: Path) -> list[str]:
    """返回该文件的问题列表；无问题返回空列表。"""
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    rel = path.relative_to(ROOT)
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in OLD_COUNT_RE.finditer(line):
            problems.append(f"  {rel}:{lineno}  旧平台数字「{m.group(0)}」")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 16 平台口径一致性")
    parser.add_argument("--verbose", action="store_true", help="打印扫描文件数")
    args = parser.parse_args()

    files = iter_target_files()
    if args.verbose:
        print(f"扫描 {len(files)} 个文档：")
        for f in files:
            print(f"  - {f.relative_to(ROOT)}")

    problems: list[str] = []
    for f in files:
        problems.extend(check_file(f))

    if problems:
        print("❌ 检测到旧平台口径（当前正确口径：16 平台 = 国内 10 + 海外 6）：")
        print("\n".join(problems))
        print("\n请修正为「16 平台」口径后重新提交。")
        return 1

    print(f"✅ 平台口径检查通过：{len(files)} 个文档，无 28/18/15/14+/7 等旧数字。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
