"""Open Matrix Publisher 跨平台路径解析（macOS / Linux / Windows 通用）。

集中处理 SAU_ROOT 定位与 venv 可执行文件路径：
- macOS / Linux 的 venv 可执行目录是 .venv/bin
- Windows 的 venv 可执行目录是 .venv/Scripts（sau.exe / python.exe / biliup.exe）

任何需要定位 SAU 的模块都应从这里取路径，避免各文件各自硬编码分隔符。
"""
import os
import sys


def data_dir():
    """可写数据目录：源码运行态用项目目录（便于本地开发直接查看）；
    PyInstaller 打包态（sys.frozen）下 __file__ 指向临时解压目录 _MEIPASS，
    退出即清空 → 历史记录/上传/封面/Cookie/凭证改存到持久目录。
    """
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
        return os.path.join(base, "OpenMatrixPublisher")
    return os.path.dirname(os.path.abspath(__file__))


def sau_root():
    """SAU 安装根目录。

    解析顺序：
    1. 显式环境变量 SAU_ROOT（用户自定义/调试用）
    2. PyInstaller 打包内嵌 _MEIPASS/social-auto-upload（开箱即用）
    3. 默认 ~/social-auto-upload（开发态：用户手动 git clone 的）
    """
    env = os.environ.get("SAU_ROOT")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "social-auto-upload")
        if os.path.isdir(bundled):
            return bundled
    return os.path.expanduser(env or "~/social-auto-upload")


def venv_bin(root=None):
    """返回 venv 可执行文件目录（Windows 用 Scripts，POSIX 用 bin）。"""
    root = root or sau_root()
    # Windows 优先探测，再探测 POSIX；都未命中时按平台给默认值
    for rel in (".venv", "Scripts"), (".venv", "bin"):
        p = os.path.join(root, *rel)
        if os.path.isdir(p):
            return p
    return os.path.join(root, ".venv", "Scripts" if os.name == "nt" else "bin")


def _exe(name):
    return name + (".exe" if os.name == "nt" else "")


def sau_cli(root=None):
    """SAU CLI 可执行文件（sau / sau.exe）。"""
    return os.path.join(venv_bin(root), _exe("sau"))


def sau_python(root=None):
    """SAU venv 的 Python 解释器（python / python.exe）。"""
    return os.path.join(venv_bin(root), _exe("python"))


def biliup(root=None):
    """SAU venv 的 biliup 可执行文件（B站上传依赖）。"""
    return os.path.join(venv_bin(root), _exe("biliup"))
