"""全栈中英双语覆盖率盘点（第一性原则的可执行防线）。

    ~/personal-ontology/.venv/bin/python tests/test_bilingual_coverage.py

对应 docs/00-first-principle-bilingual.md。逐层统计"缺英文版"的数量，并给出总缺口。
**基线只允许下降**：新增产出若缺另一语言，缺口上升 → 测试失败。

英文版命名约定（两者任一即可）：
  - 同目录兄弟文件：`docs/03-xxx.en.md`
  - 或成对后缀：`docs/03-xxx.zh.md` + `docs/03-xxx.en.md`
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = 0        # 2026-10-02 第 18 轮：全栈双语缺口归零（达标）

# 豁免：工具产出的清单/索引，不面向读者，翻译它反而失去意义（与"用户自撰内容不翻译"同类）。
EXEMPT_DOCS = {"i18n-pending.md"}

CJK = re.compile(r"[\u4e00-\u9fff]")

def backend_messages() -> int:
    """backend/*.py 里含中文的 detail=/message= 提示（英文界面下会显示中文）。"""
    total = 0
    for path in sorted((ROOT / "backend").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        total += len(re.findall(r'(?:detail|message)\s*=\s*f?["\'][^"\']*[\u4e00-\u9fff]', text))
    return total


def contract_notes_messages() -> int:
    """analysis_contract.py 里**硬编码中文的用户可见消息**（应全部走消息目录）。

    早期实现用"note(...) 后跟中文字面量"来数，会把文档字符串也算进去；
    现在直接数 `"message": "……中文……"` 这种真正会显示给用户的形态。
    """
    path = ROOT / "backend" / "analysis_contract.py"
    if not path.exists(): return 0
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = "\n".join(line.split("#", 1)[0] for line in text.split("\n"))
    return len(re.findall(r'"message"\s*:\s*"[^"]*[\u4e00-\u9fff]', text))


# 部分翻译标记：长文档可分轮翻译，但只要标了它就不算已覆盖——
# 避免"文件存在、内容不全"却把缺口刷掉。
PARTIAL_MARKER = "BILINGUAL-PARTIAL"


def is_partial(path: pathlib.Path) -> bool:
    """该英文文件是否只是部分翻译。

    必须匹配**文件头部的 HTML 注释行**（`<!-- BILINGUAL-PARTIAL ...`）。
    只在全文里搜标记字符串会把"在正文里解释这个约定"也误判为部分翻译。
    """
    try:
        head = path.read_text(encoding="utf-8", errors="ignore").split("\n")[:10]
    except OSError:
        return False
    return any(line.lstrip().startswith("<!-- " + PARTIAL_MARKER) for line in head)


def stale_translations() -> list[str]:
    """英文版落后于中文版的文件（中文改完未同步英文）。

    只告警不失败：翻译合法地滞后于原文。但它把"漂移"变成可见的，
    避免出现"英文版看起来存在、内容却对不上"。
    """
    stale = []
    for path in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md", ROOT / "CHANGELOG.md"]:
        if not path.exists() or path.name.endswith(".en.md"): continue
        if path.name in EXEMPT_DOCS: continue
        stem = path.name[:-3]
        twin = path.with_name(stem + ".en.md")
        if not twin.exists(): continue
        if is_partial(twin): continue
        if path.stat().st_mtime > twin.stat().st_mtime + 1:
            stale.append(path.name)
    return stale


def has_english(path: pathlib.Path) -> bool:
    stem = path.name[:-3] if path.name.endswith(".md") else path.name
    twin = path.with_name(stem[:-3] + ".en.md") if stem.endswith(".zh") else path.with_name(stem + ".en.md")
    if not twin.exists():
        return False
    return not is_partial(twin)

def docs_missing() -> list[str]:
    out = []
    for path in sorted((ROOT / "docs").glob("*.md")):
        if path.name.endswith(".en.md") or path.name in EXEMPT_DOCS: continue
        if not has_english(path): out.append(path.name)
    return out

def manuals_missing() -> list[str]:
    out = []
    for name in ("README.md",):
        path = ROOT / name
        if path.exists() and not has_english(path): out.append(name)
    return out

def changelog_missing() -> int:
    path = ROOT / "CHANGELOG.md"
    if not path.exists(): return 0
    return 0 if has_english(path) or (ROOT / "CHANGELOG.en.md").exists() else 1

messages = backend_messages()
contract_messages = contract_notes_messages()
docs = docs_missing()
manuals = manuals_missing()
changelog = changelog_missing()
gap = messages + contract_messages + len(docs) + len(manuals) + changelog

print("  全栈中英双语盘点（缺英文版的数量）")
print(f"    后端消息（含中文的 detail/message）: {messages} 处")
print(f"    契约提醒消息（硬编码中文，应为 0）: {contract_messages} 处")
print(f"    设计文档: {len(docs)} 份{(' → ' + ', '.join(docs[:3]) + ('…' if len(docs) > 3 else '')) if docs else ''}")
print(f"    README/手册: {len(manuals)} 份{(' → ' + ', '.join(manuals)) if manuals else ''}")
print(f"    CHANGELOG: {changelog}")
print(f"    界面文案与数据标签: 见 tests/test_i18n_coverage.py 与 tests/test_label_localization.py")
stale = stale_translations()
if stale:
    print(f"  ⚠ 英文版落后于中文版（{len(stale)} 份）：{', '.join(stale[:4])}")
else:
    print("  ✔ 英文版与中文版同步（无落后的文件）")
print(f"  ── 总缺口: {gap}（基线 {BASELINE}）")

if BASELINE == 0:
    # 达标后：缺口必须为 0，任何新增都会失败。
    if gap == 0:
        print("  ✔ 全栈双语缺口为 0（已达标）")
        sys.exit(0)
    print(f"  ✗ 已达标状态下出现 {gap} 项缺口")
    sys.exit(1)
if gap <= BASELINE:
    print(f"  ✔ 未超出基线" + (f"（较基线减少 {BASELINE - gap}）" if gap < BASELINE else ""))
    sys.exit(0)
print(f"  ✗ 总缺口较基线增加 {gap - BASELINE} —— 新增产出缺另一语言版本")
sys.exit(1)
