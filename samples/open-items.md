# 收尾清单（截至 2026-10-10）

## 已交付并自测通过

| 项 | 状态 | 证据 |
|---|---|---|
| 调用方返回按档位分层 basic/standard/professional/audit | ✓ | MCP 真调四档：5 / 8 / 12 字段；audit 因切片档位上限（professional）被正确压回 |
| 档位覆盖只降不升（测试期便利 `request.tier`） | ✓ | 同上；切片的 default_tier 是上限 |
| 被拒绝的调用也写审计记录 | ✓ | 未启用/未授权/边界不过/过期 四条拒绝路径均写 `skill.refused.*` |
| 契约接口 HTTP 500（naive 与 aware 时间比较） | ✓ | 后端日志 traceback 定位；修后专业切片 `professional` 返回完整契约 |
| 个人可信数据空间：space / services / owners | ✓ | `space=个人可信数据空间`；services 5 条；owners 列出主体与所属场景 |
| services 计数口径（只数专业切片） | ✓ | 由「2 条」改为「1 条已启用」 |
| 行业侧重写法乙：`归类 X ← A、B` / `权重 X ← 维 值` | ✓ | 旧写法仍兼容；样例端到端 8/8 |
| 「不同行业的侧重」面板：类别措辞、映射区不再折叠 | ✓ | 列头「类别（行业组）」；映射区为普通可见字段并标必填 |
| 「第三步 · 核对与微调」独立保存按钮 | ✓ | `data-save-review`「保存这次微调」，与方式三的保存互不影响 |
| 启用按钮跨作用域引用（点击无反应） | ✓ | `approvedAgents` → `window.poApprovedAgents` |
| 列表读失败不再伪装成空列表 | ✓ | `/v1/agents` 读失败时显式提示原因 |

## 未完成（明确、可接手）

1. **目录里专业切片的授权状态统计不准**：实测该切片已启用且授权成功（四次判定全部通过、无 403），
   但目录仍显示 `authorization_state=none` / `rules_total=0`。
   原因：目录沿用了生活场景那套按 `policies` 统计的口径，而专业切片的授权写在 `authorizations`
   表里、`source = skill-slice:<id>`。
   修法：在切片列表/目录里，对 `scenario_profile.kind == "professional"` 的项改用
   `authorizations` 表统计（该改动在 `backend/api.py`，**需要重启后端**，重启会把数据空间锁上，
   须先与用户确认时机）。

2. **主体真名的显示**：`owners[].display_mode = full`，但 `display` 仍是 `principal_...` ID。
   原因：取名字走 `/v1/principals`，受 `include_principals` 开关（管理端「允许向智能体提供主体目录」）控制。
   要么用户打开该开关（立刻显示真名），要么把 `display_mode` 老实写成 `id_only`。

3. **每个场景实例上的 `owner` 字段**：给酒店场景加的 `_it["owner"]` 被外层 `except Exception: pass` 吞掉，
   尚未生效（`owners` 汇总本身是好的）。修法：打开该 except，跑一次看报错再改。

4. **保存会写入空值**：把用途/金额上限/有效期留空后保存，会把它们写成空（实测 `valid_days` 从 1 变成 null，
   边界曾一度为空导致一律被拒）。应在保存前对这几项做空值提示。

5. **业务内容待用户核对**：`标的为国资背景 = 否` 时结论仍为「需国资审批」，请核对「例外情况」那一行的写法。

## 操作约束（重要）

- 后端**一重启就上锁**（密钥只在内存里），智能体、脚本、控制台全读不到，直到用户重新解锁。
  改后端代码需重启时，先告知用户时机。
- 前端改动**不需要**重启，只需重新加载页面。
