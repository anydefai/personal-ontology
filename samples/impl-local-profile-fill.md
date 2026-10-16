# 实现说明：运行时「本机资料」补齐（下一步做）

> 前置已完成：分节「本场景会用到的本机资料」→ `framework.profile_inputs = [{name, purpose}]`
> 本文件描述「执行时由本机取出资料补齐」的实现位置与顺序，按此逐条做即可。

## 一、要达成的行为

1. 调用方**不必提交** `profile_inputs` 里的字段，契约里也不列它们为必填。
2. 判定/预演执行时，本机从 `profiles` 取出对应字段的值，**补进本次请求**。
3. 补齐的值**不回显**给调用方：报告里只写「已由本机资料提供 N 项：<字段名>（值不外发）」。
4. 每次补齐写一条审计记录（哪份资料、哪几项、哪个切片、时间、用途、有效期）。
5. 找不到对应资料时不报错、不阻断：只记「未提供」，需要时在返回里提示「本机缺少：<字段名>」。

## 二、改哪里（顺序即执行顺序）

### 第 1 处：`backend/api.py` 的 `/judge`（以及 `/preview` 若有同路径）

在 `pkg = skill_framework.judge(item["framework"], (body or {}).get("data") or {}, …)` **之前**插入补齐：

```python
data = dict((body or {}).get("data") or {})
provided, missing_local = _fill_from_profiles(item, data)   # 见下
```

补齐函数（建议放在 `_caller_tier` 附近，便于一起阅读）：

```python
def _fill_from_profiles(item: dict[str, Any], data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """把切片声明的本机资料字段补进 data。返回 (补了哪些字段名, 本机缺哪些)。"""
    fw = item.get("framework") or {}
    want = [x for x in (fw.get("profile_inputs") or []) if isinstance(x, dict) and x.get("name")]
    if not want:
        return [], []
    # 取本机资料（可指定 profile_id；否则取第一份）
    profiles = store.list("profiles")
    bag: dict[str, Any] = {}
    for p in profiles:
        for it in (p.get("items") or []):
            if not isinstance(it, dict):
                continue
            for key in (it.get("label"), it.get("key")):
                if key and str(key) not in bag:
                    bag[str(key)] = it.get("value")
    filled, missing = [], []
    for w in want:
        name = str(w.get("name"))
        if name in data and data[name] not in (None, ""):
            continue                     # 调用方已给就不覆盖
        if name in bag:
            data[name] = bag[name]
            filled.append(name)
        else:
            missing.append(name)
    return filled, missing
```

### 第 2 处：把补齐结果带进返回（但**不回显值**）

```python
result = {"slice_id": slice_id, "caller": who, "authorize": authz,
          "judgment": skill_framework.for_caller(pkg, _caller_tier(item, body)),
          "decision_id": decision_id}
if filled:
    result["local_profile_provided"] = {"count": len(filled), "fields": filled,
                                        "note": "这些字段由本机资料提供，值不对外发送"}
if missing_local:
    result["local_profile_missing"] = missing_local
```

### 第 3 处：缺项判定要认这些字段

`_slice_readiness` / 引擎的 missing_inputs 只认 `framework.inputs`。需要把 `profile_inputs`
视为**已由本机负责**，不能再算「调用方缺项」。做法：在算缺项时，把
`[x["name"] for x in fw.get("profile_inputs") or []]` 也加入「已提供」集合。

### 第 4 处：契约要说明（`/contract`）

- `fields` 里**不列** `profile_inputs`（调用方不必提交）；
- 新增一段 `provided_locally: [{"name": "身份证号", "purpose": "用于实名登记"}]`，
  并附一句 `provided_locally_note: "这些字段由数据空间所有者在本机提供，调用方无需提交，也不会收到其值。"`

### 第 5 处：审计

在写 `decisions` 记录的地方，`filled` 非空时补一条：
`reason_key = "skill.profile_used"`，`reason_params = {slice_id, fields, count, caller}`。

## 三、验收（每次都要）：

- 临时库 + 真实接口：先建一份含「姓名/身份证号」的 profiles，再建一条声明了这两项
  `profile_inputs` 的切片，然后 `/judge`：
  - 不传这两项也能给出结论（不再报缺项）；
  - 返回里出现 `local_profile_provided`，且**不含**任何真实值；
  - `decisions` 里出现 `skill.profile_used` 记录。
- 闸门：`test_judge_api`、`test_refusal_audit`、`test_slice_readiness`、`test_caller_tiers`、
  `test_line_format`、`test_sample_selfsufficient` + 界面 26/26 + 前端语法 10/10 全绿才部署。

## 四、注意事项（本次踩过的坑）

1. **任何 store.put 的记录都要过 SHACL**：新集合/新字段前先看 `ontology/shapes.ttl` 的必填形状，
   并注意属性上的 `rdfs:domain` 会被 RDFS 推理用来给节点定型（`po:updatedAt` 属于 ScenarioSlice，
   用它会把自己的节点误判成场景切片）。
2. 改动按「先写临时文件 → 编译通过 → 才覆盖真文件」的顺序，不要先写盘再校验。
3. 不要删含 `try/except` 管辖范围的代码块。
