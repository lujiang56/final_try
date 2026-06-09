"""
LLM API 配置管理 — API Key 的加密存储、读取、验证

安全设计:
  - API Key 使用 AES-256-GCM 加密后存入 SQLite
  - 加密密钥派生自 Flask app.secret_key (SHA-256)
  - 前端永远不返回完整 Key，只返回掩码 (sk-****xxxx)
  - 所有 LLM 调用 100% 在服务端完成
"""

import os
import hashlib
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 缓存加密密钥，避免在 SSE 生成器等失去 Flask context 的场景下
# 回退到错误的 fallback 密钥导致解密失败。
_encryption_key_cache: bytes | None = None


def _get_encryption_key() -> bytes:
    """
    从 Flask app.secret_key 派生出 32 字节 AES-256 密钥。

    首次调用时计算并缓存密钥。这样即使在 SSE generator 等失去
    Flask application context 的场景下，也能用正确的密钥解密。
    """
    global _encryption_key_cache
    if _encryption_key_cache is not None:
        return _encryption_key_cache

    try:
        from flask import current_app
        secret = current_app.secret_key
    except (ImportError, RuntimeError):
        secret = None

    if not secret:
        # fallback: 从环境变量获取，或使用机器特征哈希（比 COMPUTERNAME 更安全）
        import platform, hashlib as _hl
        secret = os.environ.get(
            'FINAL_TRY_SECRET',
            _hl.sha256(
                f"{platform.node()}-{platform.machine()}-{os.getuid() if hasattr(os, 'getuid') else os.getlogin()}"
                .encode()
            ).hexdigest()
        )

    if isinstance(secret, str):
        secret = secret.encode('utf-8')

    _encryption_key_cache = hashlib.sha256(secret).digest()
    return _encryption_key_cache


def encrypt_api_key(api_key: str) -> str:
    """
    使用 AES-256-GCM 加密 API Key。

    Args:
        api_key: 用户的明文 API Key

    Returns:
        Base64 编码的密文 (nonce + ciphertext 拼接)
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, api_key.encode('utf-8'), None)
    # nonce (12 bytes) + ciphertext → base64
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('ascii')


def decrypt_api_key(encrypted: str) -> str:
    """
    解密 AES-256-GCM 加密的 API Key。

    Args:
        encrypted: Base64 编码的密文

    Returns:
        明文 API Key，解密失败返回空字符串
    """
    if not encrypted:
        return ''
    try:
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        combined = base64.b64decode(encrypted)
        nonce = combined[:12]
        ciphertext = combined[12:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception as e:
        import logging
        logging.warning(f"API Key 解密失败: {e}")
        return ''


def mask_api_key(api_key: str) -> str:
    """
    对 API Key 进行掩码处理，仅用于前端显示。

    规则:
      - sk-* 开头: 保留前 7 个字符 + 最后 4 个字符
      - 其他: 保留前 4 个字符 + 最后 4 个字符
      - 长度不足: 全部替换为 *
    """
    if not api_key:
        return ''
    if len(api_key) <= 8:
        return '*' * len(api_key)
    if api_key.startswith('sk-'):
        return api_key[:7] + '*' * (len(api_key) - 11) + api_key[-4:]
    return api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]


def get_default_model(provider: str) -> str:
    """根据 Provider 返回默认模型名"""
    defaults = {
        'anthropic': 'claude-sonnet-4-6',
        'openai': 'gpt-4o',
        'custom': '',
    }
    return defaults.get(provider, '')
