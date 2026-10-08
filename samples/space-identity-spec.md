# 智能体看到什么：空间名 + 一一对应的主体 + 提供哪些服务

> 用户决定：① 不同场景绑定到不同主体时【全部显示、一一对应】；② 主体名默认用 **full（真名）**。
> 状态：**规格（未实现）** —— 实现按下面四步走，每步都可单独验收。

## 一、要达成的效果（智能体读目录时的观感）

```json
{
  "space": "个人可信数据空间",
  "owners": [
    {"id": "principal_f6dad3b41dba", "display": "张律师", "display_mode": "full",
     "scenarios": ["scene_fc45a897017a", "scenario_slice_d5fd9706c172"]}
  ],
  "resources": ["酒店", "机票", "专业判断调用", "…"],
  "services": ["读取可信数据空间目录", "授权检查", "场景预演", "场景反馈",
               "按专业切片给出判断（1 条已启用）"],
  "scenario_instances": [
    {"id": "scene_fc45a897017a", "name": "预订酒店", "owner": {"id": "principal_…", "display": "张律师"}},
    {"id": "scenario_slice_d5fd9706c172", "name": "并购估值", "owner": {"id": "principal_…", "display": "张律师"}}
  ]
}
```

## 二、四步实现

### 第 1 步：目录里加上下文（backend/api.py 的目录接口 · 需要重启后端）

- `space`：固定串 **「个人可信数据空间」**（不再用「本机个人本体」）
- `owners`：把当前库里的 person 主体列出来；每个主体带上**它绑定的场景/切片 id**
  - 绑定来源：`authorization_rules[].grantor_id`（该场景的授权方）→ 没有规则的场景则用它的所有者
  - 一个主体可对应多个场景；一个场景只归一个主体 → **一一对应** ✓
- `services`：由现成能力拼出（不算新东西）
  - 固定四项：读取可信数据空间目录 · 授权检查 · 场景预演 · 场景反馈
  - 动态一项：按专业切片给出判断（N 条**已启用**的切片）

### 第 2 步：主体名默认 full（backend/ + 管理端）

- `principal_display_mode` 的**默认值**从 `neutral` 改为 `full`
- 保留三个档位不删：`full` 真名 / `neutral` 中性名 / `id_only` 仅 ID（用户可在控制台改回）
- 目录里每个 owner 都带 `display_mode`，智能体可据此决定怎么称呼

### 第 3 步：文案统一（backend/mcp_server.py + backend/scenario_llm.py）

- mcp_server.py：静态说明里的「本机个人本体」「治理目录」「本体已锁定」「本机治理服务」→
  统一改为「个人可信数据空间」/「可信数据空间目录」/「数据空间已锁定」/「可信数据空间服务」
- scenario_llm.py 提示词首句：`你是个人本体治理系统的场景分析器` →
  `你是「个人可信数据空间」的场景分析器`
- **不动**：MCP 服务名 `personal-ontology`、工具名 `get_governance_catalog` 等、
  集合名与字段名（改了会连带动配置与数据）

### 第 4 步：验收

- tests/test_mcp_catalog_behavior.py 补：`space` 存在且为新名 ✓ `owners` 里的场景与
  `scenario_instances` **一一对应** ✓ `services` 非空 ✓
- 多主体用例：两个场景绑不同主体 → `owners` 两条、各自 `scenarios` 正确 ✓
- 隐私：把 `display_mode` 改成 `neutral` → 目录里 `display` 随之变化 ✓
- 跑 tests/test_mcp_e2e.py（真实 MCP 通道）确认智能体读到的是新名字 ✓

## 三、代价与提醒

- 改 `api.py` / `scenario_llm.py` 后**必须重启后端** → 重启后请让 WorkBuddy **先跑一次 MCP 动作**（第一次可能失败，第二次必好）
- 改 `mcp_server.py` 的说明：WorkBuddy 下次重新拉起 MCP 子进程即生效
- 批准记录不受影响（按进程身份记的，命令行没变）
