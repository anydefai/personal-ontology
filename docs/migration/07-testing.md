# 07 · 测试与闸门

## 1. 总览

```
tests/            68 个测试文件（每个都是可独立运行的脚本，不是 pytest）
运行方式          python tests/test_xxx.py  → 末尾打印 "===== N/N 项通过 ====="，退出码 0/1
测试隔离          每个文件开头设 PERSONAL_ONTOLOGY_DATA=临时目录（互不污染真实数据）
```

## 2. 闸门（每次部署前必须全绿）

```bash
cd /Users/Apple/Documents/personal-ontology
PY=$HOME/personal-ontology/.venv/bin/python
PASS=1
for t in test_<改动涉及的所有套件> …; do
  R=$($PY tests/$t.py 2>&1 | grep "项通过" | tail -1)
  case "$R" in
    *"项通过"*) A=$(echo "$R"|grep -oE "[0-9]+/"|tr -d /); B=$(echo "$R"|grep -oE "/[0-9]+"|tr -d /)
                [ "$A" != "$B" ] && { echo "X $t $R"; PASS=0; } ;;
    *)          echo "X $t 异常"; PASS=0 ;;
  esac
done
node tests/test_ui_behavior.js      >/tmp/ui.txt 2>&1; grep -q "26/26 项通过" /tmp/ui.txt || PASS=0
$PY tests/test_frontend_syntax.py   | grep -q "10/10" || PASS=0
echo "闸门: $([ $PASS = 1 ] && echo 全绿 || echo 有红)"
[ $PASS = 1 ] || exit 1
```

**为什么逐套跑而不是跑一个大套件**：每个文件自建临时库，互不影响；也便于只跑受影响的。

## 3. 现有测试分组

### 认证 / 安全（6）
```
test_api_auth            test_vault              test_origin_policy
test_requirements_model  test_temporal           test_refusal_audit
```

### 数据模型 / 存储（8）
```
test_engine_models   test_model_policies   test_rule_layer      test_multi_resource
test_policy_actions  test_principal_types   test_both_tier       test_caller_tiers
```

### 业务集合（18）
```
test_profiles / test_profile_items / test_profile_reveals
test_circles_api / test_circle_grants / test_circle_changes / test_circle_agent_member
test_acting_for / test_commitments_api / test_places_api / test_assets_api
test_transactions_api / test_ledger_section / test_devices_sync
test_contacts_import / test_contacts_bulk / test_contacts_purge / test_contacts_sync / test_contacts_devices
```

### 场景 / 专业判断（16）
```
test_slice_api / test_slice_contract / test_slice_duplicate / test_slice_framework
test_slice_readiness / test_slice_validity / test_line_format / test_line_document / test_line_import
test_professional_model / test_professional_render / test_professional_ui
test_skill_draft / test_skill_evaluate_api / test_skill_framework / test_skill_backtest
test_analysis_contract / test_formula_model / test_judge_api / test_hotel_fallback
```

### MCP（4）
```
test_mcp_e2e / test_mcp_catalog_behavior / test_mcp_professional / test_sample_selfsufficient
```

### 双语 / 文案（5）
```
test_bilingual_coverage / test_i18n_coverage / test_i18n_rules / test_i18n_text
test_label_localization / test_messages_bilingual
```

### 前端（2，Node）
```
test_ui_behavior.js     26 项：无原生 confirm/alert、弹窗存在、关键交互约定
test_frontend_syntax.py 10 项：node --check 全部 js + 关键字符串存在
```

### 运维（1）
```
test_manager_endpoints   界面服务的静态资源与 /v1 代理
```

## 4. 写测试的模板

```python
"""一句话说明这测的是什么。"""
import asyncio, os, sys, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
os.environ["PERSONAL_ONTOLOGY_DATA"] = tempfile.mkdtemp()     # 必须：隔离
from test_api_auth import call                                 # 复用的 HTTP 辅助
R = []
def check(name, ok, detail=""):
    R.append(ok); print(("  ✓ " if ok else "  ✗ ") + name + ((" — " + str(detail)[:160]) if detail and not ok else ""))
async def main():
    st, pl = await call("POST", "/v1/setup", body={"password": "Test-Pass-123!"})  # ≥8 位，别用常见密码
    tk = pl["token"]
    ...
asyncio.run(main())
ok = sum(1 for x in R if x); print("\n===== %d/%d 项通过 =====" % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
```

## 5. 四个已经被踩过的坑（写测试时避开）

```
① password 太短 → setup 返回 422，后续 KeyError: 'token'
   口令至少 8 位，且不在 assets/common-passwords.txt 里。

② grep -c 返回 0 时退出码是 1，会把 && 链整条短路
   曾导致"部署成功但没提交、没推送"。
   写法：grep -c ... || true   或先存变量再判断。

③ 断言写错比代码错更常见
   例如期望 matched_via == "acting_for"，实际是 "circle"（因为规则给的是圈，代理只是让圈生效）。
   遇到失败先问"是我的期望错了吗"，再改代码。

④ 前端改动先写盘后编译 → 坏代码进了仓库
   正确顺序：写 /tmp/app_check.js → node --check → 通过才覆盖 web/app.js。
```

## 6. 性能基线（迁移后用来对比是否退化）

| 场景 | 基线 |
|---|---|
| 250 条 `put_many` 导入 | ≈ 1.0 s |
| 877 条同上 | ≈ 5.7 s |
| 单条 `put()` | 数十毫秒（随库大小线性增长） |
| 解锁（PBKDF2 2e6） | 数百毫秒 ~ 1 s |
| 一次 `evaluate` | 数毫秒（规则数量级百条内） |

若迁移后 877 条导入超过 30 秒，先检查是不是退化成了逐条 `put()`。
