#!/usr/bin/env python3
"""把加密容器里本体的 RDF 命名空间整体改名（用于去掉旧域名标识）。

    ~/personal-ontology/.venv/bin/python scripts/rename-namespace.py            # 干跑，只报告
    ~/personal-ontology/.venv/bin/python scripts/rename-namespace.py --apply    # 实际写入

为什么需要它：命名空间会被烧进**每一条已存三元组**。只改代码不改数据，界面会看起来
"本体空了"——因为按新命名空间查不到任何东西。

安全性：
  * 只重写 `ontology` 段的 Turtle 文本；`model_service` 段的字节原样保留（不重复加密、不复用 nonce）；
  * 写入走容器自身的"临时文件 + 原子替换"；
  * 写后**重新解密核对**：三元组数量一致、旧命名空间已消失、`model_service` 字节未变；
  * 可重复执行：已是新命名空间时直接报告并退出。
"""
from __future__ import annotations

import argparse
import getpass
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# 旧命名空间不写死：运行时从容器内容里识别（仓库里因此不留任何旧域名痕迹）
NEW = "urn:personalontology:ontology#"
CONTAINER = pathlib.Path.home() / "personal-ontology" / "data" / "ontology.po.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际写入（默认只干跑）")
    ap.add_argument("--container", default=str(CONTAINER))
    ap.add_argument("--old", default="", help="留空则自动从容器内容识别")
    ap.add_argument("--new", default=NEW)
    ap.add_argument("--password-stdin", action="store_true",
                    help="从标准输入读口令（供自动化/演练；交互使用请省略）")
    args = ap.parse_args()

    path = pathlib.Path(args.container)
    if not path.exists():
        print(f"找不到容器：{path}"); return 2

    from backend.vault import Container
    from rdflib import Graph

    password = sys.stdin.readline().rstrip("\n") if args.password_stdin else getpass.getpass("容器口令：")
    box = Container(path)
    try:
        box.unlock(password)
    except Exception as exc:
        print(f"解锁失败：{exc}"); return 2

    before_bytes = box.get_section("ontology")
    before_doc = box.read_document()
    before_model_service = before_doc["sections"].get("model_service")
    text = before_bytes.decode("utf-8")

    old_ns = args.old
    if not old_ns:
        # 从 `@prefix po: <…>` 里读出当前命名空间
        m = re.search(r"@prefix\s+po:\s*<([^>]+)>", text)
        if not m:
            print("无法从容器内容识别当前命名空间（未找到 `@prefix po: <…>`），请用 --old 指定。"); return 2
        old_ns = m.group(1)
    if args.new in text and old_ns not in text:
        print("已是新命名空间，无需迁移。"); return 0
    if old_ns not in text:
        print(f"文本中未找到命名空间 {old_ns}，请人工检查：{path}"); return 2

    old_graph = Graph(); old_graph.parse(data=text, format="turtle")
    new_text = text.replace(old_ns, args.new)
    new_graph = Graph(); new_graph.parse(data=new_text, format="turtle")

    print(f"  识别到旧命名空间：{old_ns}（出现 {text.count(old_ns)} 处）")
    print(f"  三元组：迁移前 {len(old_graph)} → 迁移后 {len(new_graph)}")
    if len(old_graph) != len(new_graph):
        print("  ✗ 三元组数量不一致，已中止（未写入）"); return 2
    if old_ns in new_text:
        print("  ✗ 仍有旧命名空间残留，已中止（未写入）"); return 2
    if not args.apply:
        print("  干跑结束（未写入）。加 --apply 实际执行。"); return 0

    box.put_section("ontology", new_text.encode("utf-8"))
    box.lock()

    # 重新解密核对
    check = Container(path)
    check.unlock(password)
    after_doc = check.read_document()
    back = check.get_section("ontology").decode("utf-8")
    ok = True
    if old_ns in back:
        print("  ✗ 复读仍有旧命名空间"); ok = False
    if args.new not in back:
        print("  ✗ 复读未见新命名空间"); ok = False
    back_graph = Graph(); back_graph.parse(data=back, format="turtle")
    if len(back_graph) != len(old_graph):
        print(f"  ✗ 复读三元组数量不符：{len(back_graph)} vs {len(old_graph)}"); ok = False
    if after_doc["sections"].get("model_service") != before_model_service:
        print("  ✗ model_service 段被改动了（不应发生）"); ok = False
    check.lock()

    print(f"  复读：三元组 {len(back_graph)}，旧命名空间残留 {'有' if old_ns in back else '无'}")
    print("  ✔ 迁移完成并核对通过" if ok else "  ✗ 核对未通过，请从备份恢复")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
