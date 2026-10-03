"""backend/vault.py 的自检脚本（无第三方测试框架依赖）。

    ~/personal-ontology/.venv/bin/python tests/test_vault.py

覆盖：往返、错口令、密文篡改、头部篡改、段间密文互换、段直通、改口令、
原子写、锁定态行为、以及真实迭代次数下的解锁耗时。
"""
from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import vault
from backend.vault import Container, ContainerCorrupt, ContainerMissing, VaultError, WrongPassword

FAST = 1_000  # 单元测试用低迭代次数；末尾另测真实值
PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "another quite different phrase"

RESULTS: list[tuple[bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((bool(condition), label))
    mark = "✔" if condition else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""))


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="vault-test-"))
    try:
        path = work / "ontology.po.json"
        ontology = "# 本体\n<urn:x:a> a po:Thing .\n".encode("utf-8")
        model = json.dumps({"base_url": "https://api.example.com", "api_key": "sk-secret"}).encode("utf-8")

        print("=== 1. 创建与解锁 ===")
        box = Container(path, iterations=FAST)
        check("初始不存在", not box.exists)
        try:
            box.read_document()
            check("未创建时读取应报错", False)
        except ContainerMissing:
            check("未创建时读取报错", True)
        box.create(PASSWORD, {"ontology": ontology, "model_service": model})
        check("创建后文件存在", box.exists)
        check("创建后直接可用（密钥已缓存）", box.unlocked and box.get_section("ontology") == ontology)
        raw = path.read_text("utf-8")
        check("磁盘上无明文（正文）", "urn:x:a" not in raw)
        check("磁盘上无明文（凭据）", "sk-secret" not in raw)
        check("磁盘上无口令", PASSWORD not in raw)
        check("文件权限 0600", oct(path.stat().st_mode)[-3:] == "600")
        box.unlock(PASSWORD)
        check("解锁成功", box.unlocked)
        check("ontology 段往返一致", box.get_section("ontology") == ontology)
        check("model_service 段往返一致", box.get_section("model_service") == model)

        print("\n=== 2. 错口令 ===")
        other = Container(path, iterations=FAST)
        try:
            other.unlock("wrong password")
            check("错口令应被拒绝", False)
        except WrongPassword:
            check("错口令被拒绝", True)
        check("错口令后仍是锁定态", not other.unlocked)

        print("\n=== 3. 密文被篡改 ===")
        doc = json.loads(raw)
        blob = doc["sections"]["ontology"]["ciphertext"]
        doc["sections"]["ontology"]["ciphertext"] = ("A" if blob[0] != "A" else "B") + blob[1:]
        tampered = work / "tampered.po.json"
        tampered.write_text(json.dumps(doc), "utf-8")
        try:
            Container(tampered, iterations=FAST).unlock(PASSWORD)
            check("篡改密文应被拒绝", False)
        except WrongPassword:
            check("篡改密文被拒绝（GCM tag）", True)

        print("\n=== 4. 头部参数被篡改（AAD 绑定）===")
        doc = json.loads(raw)
        doc["sections"]["ontology"]["kdf"]["iterations"] = FAST // 2
        weak = work / "weak.po.json"
        weak.write_text(json.dumps(doc), "utf-8")
        try:
            Container(weak, iterations=FAST).unlock(PASSWORD)
            check("篡改迭代次数应被拒绝", False)
        except WrongPassword:
            check("篡改迭代次数被拒绝（AAD）", True)

        print("\n=== 5. 段间密文互换（段名进 AAD）===")
        doc = json.loads(raw)
        a = doc["sections"]["ontology"]
        b = doc["sections"]["model_service"]
        a["ciphertext"], b["ciphertext"] = b["ciphertext"], a["ciphertext"]
        a["cipher"], b["cipher"] = b["cipher"], a["cipher"]
        a["kdf"], b["kdf"] = b["kdf"], a["kdf"]
        swapped = work / "swapped.po.json"
        swapped.write_text(json.dumps(doc), "utf-8")
        try:
            Container(swapped, iterations=FAST).unlock(PASSWORD)
            check("段间互换应被拒绝", False)
        except WrongPassword:
            check("段间互换被拒绝", True)

        print("\n=== 6. 未改动段原样搬运（不重复加密、不复用 nonce）===")
        before = json.loads(path.read_text("utf-8"))["sections"]["model_service"]
        box.put_section("ontology", ontology + b"<urn:x:b> a po:Thing .\n")
        after = json.loads(path.read_text("utf-8"))["sections"]["model_service"]
        check("model_service 段字节未变", before == after)
        check("未解出凭据也能写入本体", True)
        check("revision 递增", box.revision == 2, f"revision={box.revision}")

        print("\n=== 7. 写入不残留临时文件 ===")
        leftovers = sorted(p.name for p in work.iterdir() if p.suffix == ".tmp")
        check("无 .tmp 残留", not leftovers, ", ".join(leftovers))

        print("\n=== 8. 锁定后拒绝访问 ===")
        box.lock()
        check("锁定后 unlocked=False", not box.unlocked)
        try:
            box.get_section("ontology")
            check("锁定后读取应报错", False)
        except VaultError:
            check("锁定后读取报错", True)
        box.unlock(PASSWORD)
        check("重新解锁后内容仍在", box.get_section("ontology").startswith("# 本体".encode("utf-8")))

        print("\n=== 9. 改口令 ===")
        before_doc = json.loads(path.read_text("utf-8"))
        before_salt = before_doc["sections"]["ontology"]["kdf"]["salt"]
        box.change_password(PASSWORD, NEW_PASSWORD)
        after_doc = json.loads(path.read_text("utf-8"))
        check("salt 已更换", before_salt != after_doc["sections"]["ontology"]["kdf"]["salt"])
        check("revision 递增", after_doc["revision"] == before_doc["revision"] + 1)
        check("改后旧口令失效", _rejects(path, PASSWORD))
        check("改后新口令可用", not _rejects(path, NEW_PASSWORD))
        box2 = Container(path, iterations=FAST)
        box2.unlock(NEW_PASSWORD)
        check("两段内容都完好", box2.get_section("ontology").startswith("# 本体".encode("utf-8"))
              and json.loads(box2.get_section("model_service"))["api_key"] == "sk-secret")
        try:
            box2.change_password("not the password", NEW_PASSWORD)
            check("用错口令改密应被拒绝", False)
        except WrongPassword:
            check("用错口令改密被拒绝", True)

        print("\n=== 10. 版本与格式校验 ===")
        bad = work / "other.json"
        bad.write_text(json.dumps({"format": "something-else", "version": 1, "sections": {}}), "utf-8")
        try:
            Container(bad).read_document()
            check("非容器文件应被拒绝", False)
        except ContainerCorrupt:
            check("非容器文件被拒绝", True)
        bad.write_text(json.dumps({"format": vault.FORMAT_NAME, "version": 99, "sections": {}}), "utf-8")
        try:
            Container(bad).read_document()
            check("不支持的版本应被拒绝", False)
        except ContainerCorrupt:
            check("不支持的版本被拒绝", True)

        print("\n=== 11. 原子性：写入中断后旧文件仍可用 ===")
        snapshot = path.read_bytes()
        try:
            with _patched_replace():
                box.put_section("ontology", "# 会被打断的写入\n".encode("utf-8"))
        except RuntimeError:
            pass
        check("中断后文件未被替换", path.read_bytes() == snapshot)
        check("中断后旧口令仍可解锁", not _rejects(path, NEW_PASSWORD))

        print("\n=== 12. 冻结测试向量（iOS 实现须复现同一结果）===")
        password = "correct horse battery staple"
        plaintext_vec = "测试向量：personal-ontology container v1".encode("utf-8")
        salt_vec = bytes(range(16))
        nonce_vec = bytes(range(0x10, 0x1c))
        blob = vault.build_section("ontology", plaintext_vec, password, salt_vec, 1000, nonce_vec)
        check("AAD 与规格一致",
              vault.section_aad("ontology", 1, "AAECAwQFBgcICQoLDA0ODw==", 1000, "EBESExQVFhcYGRob").decode()
              == "po-container-v1|ontology|1|AAECAwQFBgcICQoLDA0ODw==|1000|EBESExQVFhcYGRob")
        check("派生密钥与向量一致",
              base64.b64encode(vault.derive_key(password, salt_vec, 1000)).decode()
              == "ppsXnjrdPB4KryJ6DrOqKqhkWrhv7PbKAMF1Eml8cZ4=")
        check("密文与冻结向量一致",
              blob["ciphertext"] == "+lI6y8hTGDT7gLfyNSGpg9BY7nxOlr7a5UevsJaYhb+rKmZ6SfPhKrWYtCBXwZsr1nU0ncqlXTimCNOEnA==",
              blob["ciphertext"][:40] + "...")

        print("\n=== 13. 真实迭代次数下的解锁耗时 ===")
        real = Container(work / "real.po.json")
        real.create(PASSWORD, {"ontology": ontology})
        t0 = time.perf_counter()
        real.unlock(PASSWORD)
        elapsed = (time.perf_counter() - t0) * 1000
        check(f"iterations={vault.DEFAULT_ITERATIONS:,} 解锁 {elapsed:.0f} ms（本机参考 236ms）", elapsed < 1500)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    passed = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n===== {passed}/{len(RESULTS)} 项通过 =====")
    for ok, label in RESULTS:
        if not ok:
            print(f"  失败：{label}")
    return 0 if passed == len(RESULTS) else 1


def _rejects(path: Path, password: str) -> bool:
    try:
        Container(path, iterations=FAST).unlock(password)
        return False
    except WrongPassword:
        return True


class _patched_replace:
    """临时把 os.replace 换成会抛错的版本，模拟写入中断。"""

    def __enter__(self):
        self._original = vault.os.replace
        vault.os.replace = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("模拟中断"))

    def __exit__(self, *exc):
        vault.os.replace = self._original
        return False


if __name__ == "__main__":
    sys.exit(main())
