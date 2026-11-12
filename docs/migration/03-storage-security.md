# 03 · 存储与安全

## 1. 容器格式（`data/ontology.po.json`）

```
{
  "format":     "personal-ontology-container",
  "version":    1,
  "revision":   1498,              ← 每次成功落盘 +1
  "created_at": "...",  "updated_at": "...",
  "sections": {
    "ontology": {
      "kdf":    { "name": "pbkdf2-hmac-sha256", "salt": "<b64>",
                  "iterations": 2000000, "dklen": 32 },
      "cipher": { "name": "AES-256-GCM", "nonce": "<b64>" },
      "ciphertext": "<b64>"        ← 整段 Turtle
    },
    "model_service": { …同构… },
    "ledger":        { …同构… }
  }
}
```

要点：

| 项 | 值 | 说明 |
|---|---|---|
| KDF | PBKDF2-HMAC-SHA256，2,000,000 次，16 字节盐 | 只依赖标准库；iOS 侧用 CommonCrypto，零第三方依赖 |
| 加密 | AES-256-GCM，12 字节随机 nonce，AAD 绑定段名 | 每段独立 nonce，同一口令也得到不同密文 |
| 落盘 | 写临时文件 → `os.replace()` | 原子替换，中断不会得到半截文件 |
| 兼容 | `format` 不符直接拒绝加载 | 不做"尽力而为"的解析 |

## 2. 三个段的边界（这是本项目最重要的一条设计）

```
ontology        本体与全部业务数据（资料、圈、事、地、财、识、切片、判定…）
model_service   模型服务凭据（单独加密，换机器时可不迁移）
ledger          流水（asset-transactions），体量大、增长快
```

为什么把流水单独放一段：

```
一次写入的成本 = 整段序列化 + 全量 SHACL 校验 + 整段重加密
若流水与本体同段，一年几千条流水会让"记一笔账"越来越慢，还会连带重写全部资料与规则。
分段的代价是实现上多一层，收益是：写流水的前提下，本体段密文【逐字节不变】（已有测试断言）。
```

## 3. 解锁与会话

```
data/ontology.po.json   密文（始终存在）
data/session-token      解锁后写入；上锁/重启后删除
data/api-token          MCP 侧长期令牌（与界面会话分离）
```

- 解锁：`POST /v1/login` 校验口令 → 派生密钥 → 解出 `ontology` 段 → 载入内存 RDF 图 → 写 `session-token`；
- 上锁：`POST /v1/lock` 或进程重启 → 内存图丢弃、`session-token` 删除 → 之后所有接口 401；
- **口令策略**：长度 ≥ 8，且不允许出现在 `assets/common-passwords.txt` 里；
- 口令不可找回。这是设计选择，不是缺陷（否则"只有你能打开"不成立）。

## 4. 写入路径的四种成本

| 操作 | 成本 | 何时用 |
|---|---|---|
| `store.put()` | 整段序列化 + 全量 SHACL + 整段重加密 | 单条增删改 |
| `store.put_many(items, batch_size=200)` | 每 200 条做一次校验与落盘 | 批量导入（必须用这个） |
| `store.put_ledger()` | 只重写 ledger 段 | 流水 |
| `store.delete()` | 同 put + 入边检查 | 单条删除 |

**实测**：250 条走 `put_many` 约 1.0 秒；同样的 877 条若走 `put()` 循环，会把后端锁死（曾真实发生）。

## 5. 敏感度分级（`sensitivity`）

| 级别 | 含义 | 例子 | 对外行为 |
|---|---|---|---|
| `normal` | 一般 | 昵称、头像 | 可授权 |
| `sensitive` | 敏感 | 地址、行程 | 需显式授权，默认不给 |
| `critical` | 关键 | 证件号 | 默认不授权；查看必须二次确认并留痕 |
| `restricted` | 受限 | 通讯录条目、流水、资产掩码 | **永不参与对外授权**，不进契约，导出默认排除 |

红标口径（界面上必须显示）：**"这些值一旦交给智能体，就收不回来了"** —— 因为值进入模型上下文后无法回收。
两处界面都要有：个人资料页、场景的「每次预填」区。

## 6. 查看留痕

```
POST /v1/profile-items/{id}/reveal  → 写 profile-reveals
记录内容：哪一项、属于哪份资料、什么时候、用途、第几次
记录里【不含明文值】（有测试断言）
```

## 7. 通讯录数据的位置与清理

```
从手机同步的联系人 → contact-records 集合（restricted）
  含：姓名、公司、电话、邮箱、地址、备注、分组、设备标签、账户标签、稳定 ID
清理：POST /v1/contacts/purge（可按来源）；圈里的成员不受影响（他们只是关系）
中间文件：data/contacts-raw.txt / data/contacts-import.json（600 权限，导入后可删）
```

## 8. 备份与恢复

```
备份（推荐）
  1) 停后端：launchctl kickstart -k 之前先 bootout，或直接复制（os.replace 保证不会读到半截）
  2) 复制 data/ontology.po.json（以及 settings.json，可选）
  3) 校验：python3 -c "import json;print(json.load(open('…po.json'))['revision'])"

恢复
  1) 把容器放回 data/（先删旧文件，或改名备份）
  2) 启动后端 → 用【当时的口令】登录（口令不对就永远打不开，没有任何后门）
  3) 验证：GET /v1/collections 计数、随便读一条资料、看 revision 是否等于备份时

不要
  · 不要只备份部分段（容器是一体的）
  · 不要把容器提交进 git（.gitignore 已排除 data/、*.po.json、*.key、*.log、backup/）
  · 不要用文本编辑器修改容器（会破坏 base64/GCM 校验）
```

## 9. 威胁模型（写到什么程度就说清楚）

```
能防
  ✓ 拿到文件但不知道口令 → 打不开（PBKDF2 2e6 次 + AES-GCM）
  ✓ 硬盘丢失 → 同上
  ✓ 篡改密文 → GCM 校验失败，拒绝加载
  ✓ 误删引用 → 存储层拒绝删除
  ✓ 明文泄露给智能体后无法回收 → 我们承认，用"最小授权 + 留痕"缓解

防不住（必须如实告知用户）
  ✗ 用户口令太弱（只能做长度与常见密码检查）
  ✗ 本机被完全控制（内存里的图是明文）
  ✗ 智能体把值写进自己的记忆（只能标注"不得留存"并留痕）
  ✗ 手机通讯录本身的隐私（导入即承担；标注 restricted + 可一键清除）
```
