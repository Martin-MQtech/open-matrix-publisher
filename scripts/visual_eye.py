#!/usr/bin/env python3
"""视觉之眼 (Visual Eye) — 给 Agent 一双"眼睛"

把屏幕/网页/图片转成 Agent 可读的结构化描述：
  1. 截图（网页 via Chrome headless / 屏幕 via screencapture / 指定窗口）
  2. OCR（Apple Vision 框架，中英文，Swift 编译助手）
  3. 颜色与布局分析（PIL）：主色、对比度、文本块阅读顺序

用法:
  python3 scripts/visual_eye.py see <image.png>        # 分析一张已有图片
  python3 scripts/visual_eye.py page <url>             # 截图网页并分析
  python3 scripts/visual_eye.py screen                 # 截全屏并分析
  python3 scripts/visual_eye.py window <标题子串>       # 截取指定窗口并分析
  python3 scripts/visual_eye.py page <url> --save <out.png>  # 只截图保存

输出: 文本块（按阅读顺序）+ 主色板 + 对比度提示。
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWIFT_SRC = os.path.join(ROOT, "scripts", "ocr_vision.swift")
OCR_BIN = os.path.join(ROOT, "scripts", ".ocr_vision")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# ─────────────────────────── OCR 助手（编译缓存） ───────────────────────────
def ensure_ocr_bin():
    if not os.path.exists(SWIFT_SRC):
        raise RuntimeError(f"缺少 {SWIFT_SRC}")
    need_build = (not os.path.exists(OCR_BIN)
                  or os.path.getmtime(SWIFT_SRC) > os.path.getmtime(OCR_BIN))
    if need_build:
        subprocess.run(["swiftc", "-O", SWIFT_SRC, "-o", OCR_BIN],
                       check=True, capture_output=True)
    return OCR_BIN


def ocr(image_path, sort=False):
    bin_path = ensure_ocr_bin()
    cmd = [bin_path, image_path] + (["--sort"] if sort else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    blocks = []
    for line in r.stdout.splitlines():
        m = re.match(r"([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)\t(.*)", line)
        if m:
            x, y, w, h = map(float, m.groups()[:4])
            blocks.append({"x": x, "y": y, "w": w, "h": h, "text": m.group(5)})
    return blocks


# ─────────────────────────── 截图 ───────────────────────────
def capture_page(url, out):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--virtual-time-budget=3000", "--force-device-scale-factor=1",
                    "--window-size=1440,1000", f"--screenshot={out}", url],
                   capture_output=True)
    return out


def capture_screen(out):
    subprocess.run(["screencapture", "-x", out], check=True)
    return out


def capture_window(title_substr, out):
    # 用 CGWindowList 找窗口 ID（Swift 助手），再 screencapture -l 截取
    swift = r"""
import Foundation
import CoreGraphics
let sub = CommandLine.arguments[1]
guard let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] else { exit(1) }
for w in list {
    if let name = w[kCGWindowName as String] as? String, name.contains(sub),
       let num = w[kCGWindowNumber as String] as? Int, num > 0 {
        print(num)
        exit(0)
    }
}
exit(2)
"""
    tmp = os.path.join(tempfile.gettempdir(), "find_win.swift")
    with open(tmp, "w") as f:
        f.write(swift)
    bin_tmp = os.path.join(tempfile.gettempdir(), "find_win")
    subprocess.run(["swiftc", "-O", tmp, "-o", bin_tmp], check=True, capture_output=True)
    r = subprocess.run([bin_tmp, title_substr], capture_output=True, text=True)
    wid = r.stdout.strip()
    if not wid:
        raise RuntimeError(f"找不到标题含『{title_substr}』的窗口")
    subprocess.run(["screencapture", "-x", "-l", wid, out], check=True)
    return out


# ─────────────────────────── 颜色/布局分析 ───────────────────────────
def color_analysis(image_path):
    try:
        from PIL import Image
        from collections import Counter
    except ImportError:
        return []
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    small = img.resize((max(1, w // 24), max(1, h // 24)))
    cnt = Counter(small.getdata())
    total = sum(cnt.values())
    palette = []
    for (r, g, b), c in cnt.most_common(6):
        pct = c / total * 100
        if pct < 1.5:
            continue
        palette.append(f"rgb({r},{g},{b}) {pct:.0f}%")
    return palette


def read_order(blocks, image_size):
    """把 OCR 块按阅读顺序输出为文本（Vision 坐标原点在左下，y 高=上）"""
    if not blocks:
        return "(未识别到文字)"
    lines = sorted(blocks, key=lambda b: (-round(b["y"] / 0.05), b["x"]))
    return "\n".join(f"  [{b['x']:.2f},{b['y']:.2f}] {b['text']}" for b in lines)


# ─────────────────────────── 主流程 ───────────────────────────
def main():
    args = sys.argv[1:]
    if len(args) < 1:
        print(__doc__)
        sys.exit(1)
    cmd, rest = args[0], args[1:]
    save_only = "--save" in rest
    out_path = None
    if "--save" in rest:
        i = rest.index("--save")
        out_path = rest[i + 1]
        rest = rest[:i]

    tmp = out_path or os.path.join(tempfile.gettempdir(), f"visual_eye_{os.getpid()}.png")

    if cmd == "see":
        if not rest:
            print("用法: visual_eye.py see <image.png>")
            sys.exit(1)
        tmp = rest[0]
    elif cmd == "page":
        if not rest:
            print("用法: visual_eye.py page <url>")
            sys.exit(1)
        capture_page(rest[0], tmp)
    elif cmd == "screen":
        capture_screen(tmp)
    elif cmd == "window":
        if not rest:
            print("用法: visual_eye.py window <标题子串>")
            sys.exit(1)
        capture_window(rest[0], tmp)
    else:
        print(__doc__)
        sys.exit(1)

    if not os.path.exists(tmp):
        print(f"❌ 截图失败: {tmp}")
        sys.exit(1)

    print(f"📷 图像: {tmp}")
    print("\n📝 OCR 文本（阅读顺序）:")
    blocks = ocr(tmp, sort=True)
    print(read_order(blocks, None))
    print("\n🎨 主色板:")
    for c in color_analysis(tmp):
        print(f"  {c}")
    if not save_only:
        os.remove(tmp)


if __name__ == "__main__":
    main()
