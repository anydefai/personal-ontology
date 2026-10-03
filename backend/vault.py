"""本体的整图加密容器（设计见 docs/05 §3）。

一个文件、两个独立加密段（ontology / model_service）；口令经 PBKDF2-HMAC-SHA256
派生密钥，AES-256-GCM 整段加密，写入走"临时文件 + 一次 os.replace"的原子替换。

不变量：
- 磁盘上只有密文与 KDF 参数，没有明文、没有口令、没有独立的验证器；
- 口令正确与否由 GCM 认证标签判定（错口令 → WrongPassword）；
- AAD 绑定段名与头部参数，头部篡改或段间密文互换都会导致认证失败；
- 段的 KDF 参数在首次创建后保持不变，重新封装只换随机 nonce，不重复派生。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_NAME = "personal-ontology-container"
FORMAT_VERSION = 1
KDF_NAME = "pbkdf2-hmac-sha256"
CIPHER_NAME = "AES-256-GCM"
DEFAULT_ITERATIONS = 2_000_000
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
SECTIONS = ("ontology", "model_service")


class VaultError(Exception):
    """容器相关错误的基类。"""


class ContainerMissing(VaultError):
    """容器文件不存在（尚未初始化）。"""


class ContainerCorrupt(VaultError):
    """容器结构、版本或参数不合法。"""


class WrongPassword(VaultError):
    """口令不正确，或内容被篡改（GCM 认证失败）。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: Any, field: str) -> bytes:
    if not isinstance(text, str):
        raise ContainerCorrupt(f"{field} 不是字符串")
    try:
        return base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ContainerCorrupt(f"{field} 不是合法的 base64") from exc


def derive_key(password: str, salt: bytes, iterations: int, dklen: int = KEY_BYTES) -> bytes:
    """PBKDF2-HMAC-SHA256。Python 标准库实现，iOS 侧用 CommonCrypto，两边零第三方依赖。"""
    if not isinstance(password, str) or not password:
        raise VaultError("口令不能为空")
    try:
        rounds = int(iterations)
    except (TypeError, ValueError) as exc:
        raise ContainerCorrupt("KDF 迭代次数不合法") from exc
    if rounds < 1:
        raise ContainerCorrupt("KDF 迭代次数不合法")
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds, dklen=dklen)


def section_aad(section: str, version: int, salt_b64: str, iterations: int, nonce_b64: str) -> bytes:
    """附加认证数据：绑定段名与头部参数。

    精确按固定顺序做 ASCII 拼接（不做"规范化 JSON"，以免跨语言键序歧义）。
    """
    return f"po-container-v1|{section}|{version}|{salt_b64}|{iterations}|{nonce_b64}".encode("ascii")


def _kdf_meta(salt: bytes, iterations: int) -> dict[str, Any]:
    return {"name": KDF_NAME, "salt": _b64e(salt), "iterations": int(iterations), "dklen": KEY_BYTES}


def _section_parts(section: str, blob: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(blob, dict):
        raise ContainerCorrupt(f"缺少 {section} 段")
    kdf, cipher = blob.get("kdf"), blob.get("cipher")
    if not isinstance(kdf, dict) or not isinstance(cipher, dict):
        raise ContainerCorrupt(f"{section} 段缺少 kdf/cipher")
    if kdf.get("name") != KDF_NAME or cipher.get("name") != CIPHER_NAME:
        raise ContainerCorrupt(f"{section} 段使用了不支持的算法")
    if not isinstance(kdf.get("salt"), str) or not isinstance(cipher.get("nonce"), str):
        raise ContainerCorrupt(f"{section} 段缺少 salt/nonce")
    try:
        int(kdf["iterations"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContainerCorrupt(f"{section} 段的迭代次数不合法") from exc
    return kdf, cipher


def _seal(section: str, plaintext: bytes, key: bytes, kdf: dict[str, Any], version: int,
          nonce: bytes | None = None) -> dict[str, Any]:
    """用已派生的密钥封装一段；默认每次使用新的随机 nonce（测试向量可显式指定）。"""
    nonce = nonce if nonce is not None else os.urandom(NONCE_BYTES)
    nonce_b64 = _b64e(nonce)
    iterations = int(kdf["iterations"])
    aad = section_aad(section, version, str(kdf["salt"]), iterations, nonce_b64)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    return {"kdf": dict(kdf), "cipher": {"name": CIPHER_NAME, "nonce": nonce_b64}, "ciphertext": _b64e(ciphertext)}


def build_section(section: str, plaintext: bytes, password: str, salt: bytes, iterations: int,
                  nonce: bytes, version: int = FORMAT_VERSION) -> dict[str, Any]:
    """确定性地构造一个加密段——用于生成/校验跨语言实现的测试向量（docs/05 §3.5）。

    除测试向量外不要使用它：生产路径必须用随机 salt 与随机 nonce。
    """
    kdf = _kdf_meta(salt, iterations)
    return _seal(section, plaintext, derive_key(password, salt, iterations), kdf, version, nonce=nonce)


def _open_with_key(section: str, blob: dict[str, Any], key: bytes, version: int) -> bytes:
    kdf, cipher = _section_parts(section, blob)
    nonce = _b64d(cipher["nonce"], f"{section}.nonce")
    ciphertext = _b64d(blob.get("ciphertext"), f"{section}.ciphertext")
    aad = section_aad(section, version, str(kdf["salt"]), int(kdf["iterations"]), str(cipher["nonce"]))
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise WrongPassword("口令不正确，或容器已被篡改。") from exc


def _derive_for(section: str, blob: dict[str, Any], password: str, version: int) -> bytes:
    del version  # 段密钥只依赖该段自己的 salt / iterations
    kdf, _ = _section_parts(section, blob)
    salt = _b64d(kdf["salt"], f"{section}.salt")
    return derive_key(password, salt, int(kdf["iterations"]), int(kdf.get("dklen", KEY_BYTES)))


def _atomic_write(path: Path, payload: bytes) -> None:
    """同目录写临时文件 → fsync → 一次 os.replace。崩溃时旧文件完好。"""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


class Container:
    """本体加密容器。锁定态不持有任何密钥或明文。"""

    def __init__(self, path: Path | str, *, iterations: int = DEFAULT_ITERATIONS) -> None:
        self.path = Path(path)
        self.iterations = int(iterations)
        self._doc: dict[str, Any] | None = None
        self._keys: dict[str, bytes] = {}
        self._plain: dict[str, bytes] = {}

    # ---------- 状态 ----------
    @property
    def exists(self) -> bool:
        return self.path.exists()

    @property
    def unlocked(self) -> bool:
        return self._doc is not None

    @property
    def revision(self) -> int:
        return int((self._doc or {}).get("revision", 0))

    def read_document(self) -> dict[str, Any]:
        """只读容器头部。锁定态也可调用（用于呈现状态）。"""
        if not self.exists:
            raise ContainerMissing("尚未创建本体容器。")
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise VaultError("容器文件无法读取。") from exc
        except ValueError as exc:
            raise ContainerCorrupt("容器不是合法的 JSON。") from exc
        if not isinstance(doc, dict) or doc.get("format") != FORMAT_NAME:
            raise ContainerCorrupt("这不是本体容器文件。")
        try:
            version = int(doc.get("version"))
        except (TypeError, ValueError) as exc:
            raise ContainerCorrupt("容器缺少版本号。") from exc
        if version != FORMAT_VERSION:
            raise ContainerCorrupt(f"不支持的容器版本：{version}")
        if not isinstance(doc.get("sections"), dict):
            raise ContainerCorrupt("容器缺少 sections。")
        return doc

    # ---------- 生命周期 ----------
    def create(self, password: str, sections: dict[str, bytes]) -> None:
        """创建容器并写入各段。成功后容器处于已解锁态（派生密钥已缓存，无需再解锁）。"""
        if self.exists:
            raise VaultError("容器已存在，不能重复创建。")
        unknown = set(sections) - set(SECTIONS)
        if unknown:
            raise VaultError("未知的段：" + "、".join(sorted(unknown)))
        if "ontology" not in sections:
            raise VaultError("创建容器必须提供 ontology 段。")
        derive_key(password, os.urandom(SALT_BYTES), 1)  # 提前校验口令非空
        sealed: dict[str, Any] = {}
        keys: dict[str, bytes] = {}
        for name, plaintext in sections.items():
            salt = os.urandom(SALT_BYTES)
            kdf = _kdf_meta(salt, self.iterations)
            key = derive_key(password, salt, self.iterations)
            sealed[name] = _seal(name, plaintext, key, kdf, FORMAT_VERSION)
            keys[name] = key
        now = _now()
        doc = {"format": FORMAT_NAME, "version": FORMAT_VERSION, "revision": 1,
               "created_at": now, "updated_at": now, "sections": sealed}
        _atomic_write(self.path, json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8"))
        self._doc, self._keys, self._plain = doc, keys, dict(sections)

    def unlock(self, password: str) -> None:
        """校验口令并载入内存。错口令抛 WrongPassword，此时不改变锁定态。"""
        doc = self.read_document()
        sections = doc["sections"]
        if "ontology" not in sections:
            raise ContainerCorrupt("容器缺少 ontology 段")
        keys: dict[str, bytes] = {}
        for name in SECTIONS:
            blob = sections.get(name)
            if blob is not None:
                keys[name] = _derive_for(name, blob, password, FORMAT_VERSION)
        plain = {"ontology": _open_with_key("ontology", sections["ontology"], keys["ontology"], FORMAT_VERSION)}
        self._doc, self._keys, self._plain = doc, keys, plain

    def lock(self) -> None:
        """丢弃密钥与明文（尽力清零）。"""
        for key in list(self._keys.values()):
            buffer = bytearray(key)
            buffer[:] = b"\x00" * len(buffer)
            del buffer
        self._keys, self._plain, self._doc = {}, {}, None

    # ---------- 段读写 ----------
    def get_section(self, name: str) -> bytes:
        """按需解密某一段。"""
        self._require_unlocked()
        if name in self._plain:
            return self._plain[name]
        blob = self._doc["sections"].get(name)
        if blob is None:
            raise VaultError(f"容器中没有 {name} 段。")
        plain = _open_with_key(name, blob, self._keys[name], FORMAT_VERSION)
        self._plain[name] = plain
        return plain

    def put_section(self, name: str, plaintext: bytes) -> None:
        """重新封装某一段并原子写回（段密钥不变，只换 nonce）。"""
        self._require_unlocked()
        if name not in self._keys:
            raise VaultError(f"容器中没有 {name} 段，请重新登录后再试。")
        blob = self._doc["sections"][name]
        kdf, _ = _section_parts(name, blob)
        self._doc["sections"][name] = _seal(name, plaintext, self._keys[name], kdf, FORMAT_VERSION)
        self._plain[name] = plaintext
        self._commit()

    def change_password(self, current: str, new: str) -> None:
        """改口令：两段都用新 salt 重新派生并原子替换（docs/05 §4.5）。"""
        doc = self.read_document()
        contents: dict[str, bytes] = {}
        for name in SECTIONS:
            blob = doc["sections"].get(name)
            if blob is None:
                continue
            key = _derive_for(name, blob, current, FORMAT_VERSION)
            contents[name] = _open_with_key(name, blob, key, FORMAT_VERSION)
        derive_key(new, os.urandom(SALT_BYTES), 1)  # 校验新口令非空
        resealed: dict[str, Any] = {}
        for name, plaintext in contents.items():
            salt = os.urandom(SALT_BYTES)
            kdf = _kdf_meta(salt, self.iterations)
            resealed[name] = _seal(name, plaintext, derive_key(new, salt, self.iterations), kdf, FORMAT_VERSION)
        doc["sections"] = resealed
        doc["revision"] = int(doc.get("revision", 0)) + 1
        doc["updated_at"] = _now()
        _atomic_write(self.path, json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8"))
        self._doc, self._keys, self._plain = doc, {}, {}
        self.unlock(new)

    # ---------- 内部 ----------
    def _require_unlocked(self) -> None:
        if self._doc is None:
            raise VaultError("容器处于锁定状态。")

    def _commit(self) -> None:
        self._doc["revision"] = int(self._doc.get("revision", 0)) + 1
        self._doc["updated_at"] = _now()
        _atomic_write(self.path, json.dumps(self._doc, ensure_ascii=False, indent=2).encode("utf-8"))
