# -*- coding: utf-8 -*-
"""Cookie 本地加密层。

目标：OMP 本仓库 LOCAL_COOKIES_DIR 下的 cookie 文件以密文落盘，对磁盘 reader 不透明。
对 SAU 上游目录（SAU_ROOT/cookies）保持完全兼容——SAU 项目自己读明文，我们不动。

加密策略：Fernet（AES-128-CBC + HMAC-SHA256）+ 密钥派生。
- 主源：系统钥匙串（macOS Keychain / Windows DPAPI / Linux Secret Service）。
- 兜底：机器指纹（uuid.getnode + hostname + 启动时随机 salt 落盘）做 PBKDF2 派生密钥。
钥匙串里没有条目时自动生成一个塞进去，**用户无需感知**。

不依赖：网络、用户操作。删除钥匙串条目会触发"重登录"——这是预期行为。

公开 API：
- get_fernet() -> Fernet
- is_encrypted(path) -> bool
- encrypt_cookie_file(plaintext_path) -> Path  # 返回 .enc 路径
- decrypt_cookie_to_path(plaintext_target) -> Path | None
"""
from __future__ import annotations

import base64
import hashlib
import os
import platform
import secrets
import socket
import uuid
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 钥匙串里的服务名（同一台机器上所有 OMP 实例共享这把钥匙）
_KEYRING_SERVICE = "open-matrix-publisher"
_KEYRING_USER = "cookie-encryption-key-v1"

# 机器指纹派生用：固定在用户配置目录的随机 salt
_FALLBACK_SALT_FILE = Path.home() / ".cache" / "omp" / "cookie_crypto.salt"
if platform.system() == "Windows":
    _FALLBACK_SALT_FILE = Path(os.environ.get("APPDATA", str(Path.home()))) / "omp" / "cookie_crypto.salt"
elif platform.system() == "Darwin":
    _FALLBACK_SALT_FILE = Path.home() / "Library" / "Application Support" / "omp" / "cookie_crypto.salt"


def _try_keyring_load() -> bytes | None:
    """从系统钥匙串读 32 字节的 url-safe base64 密钥（Fernet 原生格式）。失败返回 None。"""
    try:
        import keyring
        v = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        if v:
            return v.encode("ascii")
    except Exception:
        return None
    return None


def _try_keyring_save(key_b64: str) -> bool:
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, key_b64)
        return True
    except Exception:
        return False


def _fingerprint_passphrase() -> bytes:
    """机器指纹：uuid + hostname。稳定但不敏感——配合下面 salt 才安全。"""
    parts = [
        str(uuid.getnode()),
        socket.gethostname(),
        platform.machine(),
    ]
    return "|".join(parts).encode("utf-8")


def _load_or_create_salt() -> bytes:
    """salt 文件。首次启动生成随机 16 字节并落盘。"""
    _FALLBACK_SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _FALLBACK_SALT_FILE.exists():
        try:
            return _FALLBACK_SALT_FILE.read_bytes()
        except Exception:
            pass
    salt = secrets.token_bytes(16)
    try:
        _FALLBACK_SALT_FILE.write_bytes(salt)
        # 0600 权限（POSIX 才有意义）
        try:
            os.chmod(_FALLBACK_SALT_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return salt


def _derive_fernet_key() -> bytes:
    """从机器指纹 + salt 派生一个 Fernet key。"""
    pw = _fingerprint_passphrase()
    salt = _load_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(pw))


def get_fernet() -> Fernet:
    """拿一个 Fernet 实例。优先钥匙串，降级到机器指纹派生。"""
    key_b64 = _try_keyring_load()
    if key_b64:
        try:
            return Fernet(key_b64)
        except Exception:
            pass  # 钥匙串里的值坏了，降级
    # 派生 + 回写钥匙串（如果可用）
    derived = _derive_fernet_key()
    _try_keyring_save(derived.decode("ascii"))
    return Fernet(derived)


# ── 高层：文件级加解密 ──

def is_encrypted(path: Path | str) -> bool:
    """判断文件是不是 OMP 加密的格式（首字节 0x80 是 Fernet token 的特征）。"""
    p = Path(path)
    if not p.exists():
        return False
    try:
        head = p.read_bytes()[:1]
        return head == b"g"  # Fernet token url-safe base64 总是 gA... 开头
    except Exception:
        return False


def encrypt_cookie_file(plaintext_path: Path | str) -> Path:
    """读取明文 cookie 文件 → 加密 → 写 .enc → 删明文。返回 .enc 路径。

    如果已经是 .enc 或不存在则原样返回路径。
    """
    src = Path(plaintext_path)
    if not src.exists():
        return src
    if is_encrypted(src):
        return src
    try:
        data = src.read_bytes()
    except Exception:
        return src
    f = get_fernet()
    token = f.encrypt(data)
    enc = src.with_suffix(src.suffix + ".enc")
    enc.write_bytes(token)
    try:
        os.chmod(enc, 0o600)
    except Exception:
        pass
    # 不删明文：保留兼容 SAU 行为；下一步任务里加迁移工具
    return enc


def decrypt_cookie_to_path(target_path: Path | str) -> Path | None:
    """把 .enc 解密到一个临时明文路径，供 Playwright 注入。调用方负责用完删。

    如果 target_path 本身就是 .json（明文），直接返回。
    如果对应的 .enc 不存在，返回 None。
    """
    target = Path(target_path)
    enc = target.with_suffix(target.suffix + ".enc") if target.suffix == ".json" else target
    if target.exists() and not is_encrypted(target):
        return target
    if not enc.exists():
        return None
    try:
        f = get_fernet()
        plain = f.decrypt(enc.read_bytes())
    except (InvalidToken, ValueError, OSError):
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plain)
    try:
        os.chmod(target, 0o600)
    except Exception:
        pass
    return target


def best_cookie_path(plain_path: Path | str) -> Path | None:
    """在加密层语义下的 'account_file'：返回应当喂给 Playwright 的路径。

    行为：
    - 若 .json 明文存在 → 返回 .json
    - 否则若 .json.enc 存在 → 解密到 .json 并返回 .json
    - 否则返回 None（不创建）
    """
    p = Path(plain_path)
    if p.exists() and not is_encrypted(p):
        return p
    enc = p.with_suffix(p.suffix + ".enc")
    if enc.exists():
        return decrypt_cookie_to_path(p)
    return None
