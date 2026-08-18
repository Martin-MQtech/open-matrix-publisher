"""Open Matrix Publisher 跨平台路径解析（macOS / Linux / Windows 通用）。

集中处理 SAU_ROOT 定位与 venv 可执行文件路径：
- macOS / Linux 的 venv 可执行目录是 .venv/bin
- Windows 的 venv 可执行目录是 .venv/Scripts（sau.exe / python.exe / biliup.exe）

任何需要定位 SAU 的模块都应从这里取路径，避免各文件各自硬编码分隔符。
"""
import os


def sau_root():
    """SAU 安装根目录：优先环境变量 SAU_ROOT，默认 ~/social-auto-upload（自动展开用户主目录）。"""
    return os.path.expanduser(os.environ.get("SAU_ROOT", "~/social-auto-upload"))


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
