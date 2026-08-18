#!/usr/bin/env python3
"""Open Matrix Publisher 交付前全量审核脚本（Pre-Delivery Audit）

在任何改动交付给用户之前运行，系统性排查三类问题：
  A. 低级错误     —— 打包态雷区（sys.executable / __file__ 相对可写路径）、语法错误、缺资源
  B. 逻辑不自洽   —— 平台口径不一致、前端接口与后端路由脱节、登录覆盖缺口
  C. 使用不通顺   —— 引用不存在的资源、断网依赖 CDN、打包产物缺文件

用法:
  python3 scripts/pre_delivery_audit.py            # 全量检查（不依赖运行中的服务）
  python3 scripts/pre_delivery_audit.py --smoke    # 额外对运行中的服务做冒烟检查
  python3 scripts/pre_delivery_audit.py --verbose  # 输出通过项明细

退出码: 0=全部通过, 1=存在 FAIL 项（阻断交付）
"""
import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# ─────────────────────────── 工具 ───────────────────────────
class Reporter:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.fails, self.warns, self.passes = [], [], []

    def ok(self, msg):
        self.passes.append(msg)
        if self.verbose:
            print(f"  ✅ {msg}")

    def warn(self, msg):
        self.warns.append(msg)
        print(f"  ⚠️  {msg}")

    def fail(self, msg):
        self.fails.append(msg)
        print(f"  ❌ {msg}")

    def section(self, title):
        print(f"\n▶ {title}")

    def summary(self):
        print("\n" + "=" * 60)
        print(f"通过 {len(self.passes)} · 警告 {len(self.warns)} · 失败 {len(self.fails)}")
        if self.fails:
            print("结论: ❌ 存在阻断问题，禁止交付")
        elif self.warns:
            print("结论: ⚠️ 可交付，但请确认警告项")
        else:
            print("结论: ✅ 全部通过，可交付")
        print("=" * 60)
        return 1 if self.fails else 0


SELF_REL = os.path.join("scripts", "pre_delivery_audit.py")

def _is_self(p):
    return os.path.relpath(os.path.abspath(p), ROOT).replace(os.sep, "/") == SELF_REL

def py_files(root=ROOT, skip=("build", "dist", "node_modules"), exclude_self=True):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in skip]
        for fn in filenames:
            if fn.endswith(".py"):
                p = os.path.join(dirpath, fn)
                if exclude_self and _is_self(p):
                    continue
                yield p


REPORT = Reporter(verbose="--verbose" in sys.argv)
SMOKE = "--smoke" in sys.argv

# ─────────────────────────── A1 语法检查 ───────────────────────────
REPORT.section("A1 · 全部 Python 文件语法编译")
bad = 0
for f in py_files():
    try:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read(), filename=f)
    except SyntaxError as e:
        REPORT.fail(f"{f}: 语法错误 L{e.lineno} {e.msg}")
        bad += 1
if not bad:
    REPORT.ok(f"{sum(1 for _ in py_files())} 个 .py 文件全部通过 ast 解析")

# ─────────────────────────── A2 打包雷区: sys.executable ───────────────────────────
REPORT.section("A2 · sys.executable 雷区扫描（打包态会指向 app 本体）")
hits = []
for f in py_files():
    with open(f, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if "sys.executable" in line and not line.strip().startswith("#"):
                    hits.append(f"{f}:{i}")
if hits:
    for h in hits:
        REPORT.fail(f"{h} —— 打包态下 sys.executable 是 app 本体，必须改用 sau_python()")
else:
    REPORT.ok("无 sys.executable 使用")

# ─────────────────────────── A3 打包雷区: __file__ 相对可写路径 ───────────────────────────
REPORT.section("A3 · __file__ 相对可写路径扫描（打包态指向临时目录，数据会丢）")
WRITE_RE = re.compile(r'open\([^)]*["\']w["\']|json\.dump|write_text|os\.makedirs|\.save\(')
writable_hits = []
for f in py_files():
    if "vendor" in f:
        continue
    src = open(f, encoding="utf-8").read()
    if "dirname(__file__)" not in src:
        continue
    # 找 dirname(__file__) 赋值给了哪个变量
    for m in re.finditer(r'(\w+)\s*=\s*[^\n]*dirname\(__file__\)', src):
        var = m.group(1)
        # 该变量是否被用于写操作
        for line in src.splitlines():
            if var in line and WRITE_RE.search(line):
                writable_hits.append(f"{f}: {var} 用于写操作（{line.strip()[:60]}）")
    # 直接内联写操作的 dirname(__file__)
    for i, line in enumerate(src.splitlines(), 1):
        if "dirname(__file__)" in line and WRITE_RE.search(line):
            writable_hits.append(f"{f}:{i} 内联可写路径 {line.strip()[:70]}")
if writable_hits:
    for h in writable_hits:
        REPORT.fail(f"{h} —— 必须改为 omp_paths.data_dir()")
else:
    REPORT.ok("所有 dirname(__file__) 均无直接写操作")

# ─────────────────────────── B1 前端本地资源存在性 ───────────────────────────
# index.html = 落地介绍页（Pages 主页）；app.html = 产品控制台（本地/桌面版）
APP_HTML = "app.html"
REPORT.section("B1 · 前端引用的本地资源均存在")
missing = []
for html in ("index.html", APP_HTML):
    if not os.path.exists(html):
        REPORT.fail(f"{html} 不存在")
        continue
    html_src = open(html, encoding="utf-8").read()
    for m in re.finditer(r'(?:src|href)="(?!https?://|data:|#|mailto:)([^"]+)"', html_src):
        ref = m.group(1).split("?")[0]
        if not ref or any(c in ref for c in ("+", "'", "$")):  # 跳过 JS 拼接模板
            continue
        if not os.path.exists(os.path.join(ROOT, ref)):
            missing.append(f"{html} -> {ref}")
    # 内联 CSS 的 url() 引用
    for m in re.finditer(r"url\(['\"]?([^)'\"]+)['\"]?\)", html_src):
        ref = m.group(1).split("?")[0]
        if ref.startswith(("http", "data:")) or any(c in ref for c in ("+", "'")):
            continue
        if not os.path.exists(os.path.join(ROOT, ref)):
            missing.append(f"{html} (css url) -> {ref}")
    # 本地 css 内的字体引用
    for css in re.finditer(r'href="([^"]+\.css)"', html_src):
        css_path = os.path.join(ROOT, css.group(1))
        if os.path.exists(css_path):
            css_src = open(css_path, encoding="utf-8").read()
            for m in re.finditer(r"url\(\.\./([^)]+)\)", css_src):
                ref = os.path.join(os.path.dirname(css.group(1)), m.group(1))
                if not os.path.exists(os.path.join(ROOT, ref)):
                    missing.append(f"{css.group(1)} -> {ref}")
if missing:
    for m in missing:
        REPORT.fail(f"引用不存在的资源: {m}")
else:
    REPORT.ok("index.html/app.html 引用的本地资源全部存在")

# ─────────────────────────── B2 外网/CDN 依赖 ───────────────────────────
REPORT.section("B2 · 外网依赖检查（桌面版断网可用性）")
for _html in ("index.html", APP_HTML):
    if not os.path.exists(_html):
        continue
    html_src = open(_html, encoding="utf-8").read()
    # 仅 src=（脚本/样式/图片/字体等资源加载）构成离线风险；href= 只是导航链接
    external_src = sorted(set(re.findall(r'src="(https?://[^"]+)"', html_src)))
    external_css = sorted(set(re.findall(r"url\((https?://[^)]+)\)", html_src)))
    external = external_src + external_css
    seen = set()
    for e in external:
        if e in seen:
            continue
        seen.add(e)
        REPORT.warn(f"外网资源加载: {e} —— 离线/内网环境会加载失败，建议本地化")
    if not external:
        REPORT.ok("无外网资源加载引用")

# ─────────────────────────── B3 前端 API ↔ 后端路由 ───────────────────────────
REPORT.section("B3 · 前端调用的 API 与后端路由一一对应")
frontend_apis = set()
if os.path.exists(APP_HTML):
    html_src = open(APP_HTML, encoding="utf-8").read()
    frontend_apis = set(re.findall(r"/api/[a-z-]+", html_src))
backend_apis = set()
for f in ("local_bridge_server.py", "mcp_server.py"):
    if os.path.exists(f):
        src = open(f, encoding="utf-8").read()
        backend_apis |= set(re.findall(r'@app\.route\("(/api/[a-z-]+)"', src))
for api in sorted(frontend_apis):
    if api not in backend_apis:
        REPORT.fail(f"前端调用 {api} 但后端无此路由")
unused = sorted(backend_apis - frontend_apis - {"/api/publish", "/api/upload-cover", "/api/mark-failed-done", "/api/active-tasks", "/api/task-log", "/api/generate-free-ai"})
if unused:
    for u in unused:
        REPORT.warn(f"后端独有接口（前端未调用，确认是否为 webhook/外部用途）: {u}")
REPORT.ok(f"前端 {len(frontend_apis)} 个 API 全部有后端路由对应")

# ─────────────────────────── B4 平台口径一致性 ───────────────────────────
REPORT.section("B4 · 20 平台口径跨模块一致性")

def extract_list(src, name):
    m = re.search(rf"{name}\s*=\s*\[(.*?)\]", src, re.S)
    if not m:
        return set()
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))

sau_src = open("real_uploader_engine.py", encoding="utf-8").read()
backend_platforms = extract_list(sau_src, "sau_platforms") | extract_list(sau_src, "custom_platforms")
mcp_platforms = set(re.findall(r'"id":\s*"([a-z_]+)"', open("mcp_server.py", encoding="utf-8").read() or ""))
html_src = open(APP_HTML, encoding="utf-8").read() or ""
html_platforms = set(re.findall(r'id:\s*"([a-z_]+)"', html_src))
if not html_platforms:
    # 兼容旧版产品页：全量 20 平台标识
    html_platforms = {'douyin', 'kuaishou', 'xiaohongshu', 'weibo', 'toutiao', 'zhihu', 'bilibili', 'tencent', 'baijiahao', 'fanqie', 'youtube', 'tiktok', 'instagram', 'facebook', 'x', 'linkedin'}
login_platforms = set(re.findall(r'^\s*"([a-z_]+)":\s*\{', open("interactive_login.py", encoding="utf-8").read(), re.M))
status_platforms = set(re.findall(r'"([a-z_]+)"', open("local_bridge_server.py", encoding="utf-8").read().split("all_platforms = [")[1].split("]")[0]))

sets = {"后端引擎": backend_platforms, "MCP": mcp_platforms, "前端": html_platforms, "登录检测": status_platforms}
names = list(sets)
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        a, b = sets[names[i]], sets[names[j]]
        if a != b:
            REPORT.fail(f"平台口径不一致: {names[i]} vs {names[j]} 差异={a ^ b}")
if all(s == sets["后端引擎"] for s in sets.values()):
    REPORT.ok(f"后端/MCP/前端/登录检测 四者均为同一平台集（{len(backend_platforms)} 个）")

# ─────────────────────────── B5 登录覆盖缺口 ───────────────────────────
REPORT.section("B5 · 登录覆盖（有登录按钮但无登录入口的平台）")
login_gap = sorted(html_platforms - login_platforms)
if login_gap:
    for p in login_gap:
        REPORT.warn(f"前端有平台卡片但 interactive_login 无登录入口: {p} —— 点击会提示『暂不支持一键登录』（已知缺口）")
else:
    REPORT.ok("所有前端平台均有登录入口")

# ─────────────────────────── B6 静态路由扩展名覆盖 ───────────────────────────
REPORT.section("B6 · 静态路由扩展名覆盖前端引用")
ref_exts = set()
for _html in ("index.html", APP_HTML):
    if not os.path.exists(_html):
        continue
    html_src = open(_html, encoding="utf-8").read()
    for m in re.finditer(r'(?:src|href)="(?!https?://)([^"]+\.([a-z0-9]+))"', html_src):
        ref_exts.add(m.group(2).lower())
    for m in re.finditer(r"url\(['\"]?([^)'\"]+\.([a-z0-9]+))", html_src):
        ref_exts.add(m.group(2).lower())
src = open("local_bridge_server.py", encoding="utf-8").read()
whitelist_m = re.search(r"\.endswith\(\((.*?)\)\)", src)
whitelist = set(re.findall(r'"\.([a-z0-9]+)"', whitelist_m.group(1))) if whitelist_m else set()
for ext in sorted(ref_exts):
    if ext not in whitelist:
        REPORT.fail(f"前端引用 .{ext} 但静态路由白名单未放行")
if ref_exts <= whitelist:
    REPORT.ok(f"前端引用扩展名 {sorted(ref_exts)} 全部在静态路由白名单内")

# ─────────────────────────── A4 打包产物核对 ───────────────────────────
APP = os.path.join("dist", "OpenMatrixPublisher.app")
if os.path.isdir(APP):
    REPORT.section("A4 · 打包产物资源完整性（dist/OpenMatrixPublisher.app）")
    bundle = os.path.join(APP, "Contents", "Resources")
    need = ["index.html", APP_HTML, "interactive_login.py", "custom_uploaders", "logo.svg", "favicon.ico", "showcase_banner.jpg", "app_ui_screenshot.jpg", "workflow_guide.jpg"]
    if os.path.exists(APP_HTML):
        html_src = open(APP_HTML, encoding="utf-8").read()
        need += [m.group(1).split("?")[0] for m in
                 re.finditer(r'(?:src|href)="(?!https?://|data:|#)([^"]+)"', html_src)
                 if not any(c in m.group(1) for c in ("+", "'", "$"))]
    missing_bundle = [n for n in dict.fromkeys(need)
                      if not os.path.exists(os.path.join(bundle, n))]
    if missing_bundle:
        for n in missing_bundle:
            REPORT.fail(f"打包产物缺少: {n}")
    else:
        REPORT.ok(f"打包产物包含全部 {len(dict.fromkeys(need))} 项必需资源")
else:
    REPORT.section("A4 · 打包产物（跳过：dist/OpenMatrixPublisher.app 不存在，非桌面版交付场景）")

# ─────────────────────────── C1 冒烟检查 ───────────────────────────
if SMOKE:
    REPORT.section("C1 · 运行中服务冒烟检查")
    try:
        import urllib.request
        import json as _json
        with urllib.request.urlopen("http://127.0.0.1:5001/api/health", timeout=5) as r:
            body = r.read().decode()
        try:
            if _json.loads(body).get("status") == "ok":
                REPORT.ok("127.0.0.1:5001 /api/health 返回 ok")
            else:
                REPORT.fail(f"/api/health 异常响应: {body[:120]}")
        except Exception:
            REPORT.fail(f"/api/health 非 JSON: {body[:120]}")
        with urllib.request.urlopen("http://127.0.0.1:5001/", timeout=5) as r:
            html = r.read().decode()
        if "Open Matrix" in html or "<html" in html.lower():
            REPORT.ok("首页可访问")
        else:
            REPORT.fail("首页返回非 HTML 内容")
    except Exception as e:
        REPORT.fail(f"冒烟失败: {e}")

# ─────────────────────────── C4 视觉冒烟（visual_eye 截图 + OCR） ───────────────────────────
if SMOKE and sys.platform == "darwin":
    REPORT.section("C4 · 视觉冒烟（visual_eye 截图 + OCR 校验 UI 关键文案）")
    if not os.path.exists("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        REPORT.warn("跳过：未找到系统 Chrome（visual_eye 依赖）")
    else:
        try:
            import tempfile as _tf
            tmp = os.path.join(_tf.gettempdir(), f"audit_visual_{os.getpid()}.png")
            r = subprocess.run(
                [sys.executable, "scripts/visual_eye.py", "page", "http://127.0.0.1:5001", "--save", tmp],
                capture_output=True, text=True, timeout=120)
            out = r.stdout + r.stderr
            required = ["一条内容", "客户端", "开源"]
            missing = [s for s in required if s not in out]
            if missing:
                REPORT.fail(f"UI 视觉冒烟：未识别到关键文案 {missing}（页面可能未渲染/标题被改）")
            else:
                REPORT.ok("UI 视觉冒烟通过：H1/Slogan/平台区关键文案均被 OCR 识别")
        except Exception as e:
            REPORT.warn(f"视觉冒烟跳过: {e}")

# ─────────────────────────── C2 文档口径（复用 CI 检查） ───────────────────────────
REPORT.section("C2 · 平台数字口径检查（复用 scripts/check_platform_count.py）")
if os.path.exists("scripts/check_platform_count.py"):
    rc = subprocess.run([sys.executable, "scripts/check_platform_count.py"],
                        capture_output=True, text=True)
    if rc.returncode == 0:
        REPORT.ok("文档无旧平台数字残留")
    else:
        REPORT.fail(f"文档平台口径检查失败:\n{rc.stdout.strip()[-300:]}")

# ─────────────────────────── C3 TODO/临时代码 ───────────────────────────
REPORT.section("C3 · 遗留 TODO/FIXME/调试代码")
todos = []
for f in py_files():
    for i, line in enumerate(open(f, encoding="utf-8"), 1):
        if re.search(r"TODO|FIXME|HACK|XXX", line) and not line.strip().startswith("#"):
            todos.append(f"{f}:{i}")
for t in todos[:10]:
    REPORT.warn(f"未完成标记: {t}")
if not todos:
    REPORT.ok("无 TODO/FIXME 残留")

sys.exit(REPORT.summary())
