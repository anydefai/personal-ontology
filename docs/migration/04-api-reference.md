# 04 · API 参考

> 自动生成自 `app.routes`（共 104 条 `/v1` 路由，26 组）。
> 后端端口 8766；界面经 manager（8765）的 `/v1/**` 反向代理访问同一套接口。

## 1. 认证

```
POST /v1/setup      首次初始化（设置口令；口令 ≥ 8 位且不在常见密码表）
POST /v1/login      解锁（返回 token，同时写入 data/session-token）
POST /v1/logout     退出登录
POST /v1/lock       立即上锁（清除会话令牌）
```

除 setup/login/health 外，所有 `/v1` 路由都要求：

```
Authorization: Bearer <session-token>
X-Display-Language: zh | en     （可选，决定错误消息与标签语言）
```

未解锁或令牌失效 → `401 {"detail": {"error": "login_required", ...}}`。

## 2. 通用集合接口

五个通配路由存在（**注册顺序在专门路由之后**）：

```
GET    /v1/{collection}          列表
GET    /v1/{collection}/{id}    取一条
POST   /v1/{collection}          新建
PATCH  /v1/{collection}/{id}    局部更新
DELETE /v1/{collection}/{id}    删除
```

`{collection}` 必须是 `model.CLASSES` 里的名字，否则 404 `Unknown collection`。

## 3. 路由陷阱（血泪）

```
✗ 不要给已有路径加"查询参数变体"作为新功能入口
   曾出现 GET /v1/commitments?due_within=30 落到通用路由返回 404 Unknown collection。
   新功能要么用独立路径段，要么在同一个处理函数里做参数分支，不要依赖"带参数就是另一个接口"。

✗ 不要用两段路径去抢通用路由
   /v1/circle-members 这种"集合名"会被 /v1/{collection} 吃掉；
   新功能请用嵌套路径（/v1/circles/{id}/members），或干脆换名字（/v1/contact-records）。

✓ 新接口优先选择：嵌套在父资源下（/v1/profiles/{id}/items）
```

## 4. 关键端点说明

| 端点 | 作用 | 注意 |
|---|---|---|
| `POST /v1/decisions/evaluate` | 授权判定 | 会写一条 `decisions`；`allow` 时若审计写失败会降级为 `pause` |
| `GET /v1/scenario-slices/...` | 切片全生命周期（27 条路由） | 切片的"线格式"文本由 `line_format.py` 生成 |
| `POST /v1/profiles/{id}/items` | 资料项 | 需 `displayNameZh`；ID 必须走 `itemId` |
| `POST /v1/profiles/migrate-items` | 把 `profiles.items` 拆成资料项 | 幂等，可重复跑 |
| `POST /v1/profile-items/{id}/reveal` | 记录一次查看明文 | 记录里**不含明文值** |
| `POST /v1/circles/{id}/members` | 加成员 | 可带 `principal_id`（智能体进圈） |
| `POST /v1/principals/{id}/acts-for` | 设代理 | 只能指向 person/role |
| `POST /v1/contacts/sync` | 从手机同步通讯录 | 后端自己调 adb，按稳定 ID 就地更新 |
| `GET /v1/health` | 健康检查 | 唯一不需要认证的接口之一 |

## 5. 错误格式

```json
{"detail": {"error": "shacl_validation_failed", "message": "数据校验未通过：…"}}
{"detail": {"error": "circle_in_use", "message": "还有 2 条授权规则指向这个圈，请先暂停或删除它们"}}
{"detail": {"error": "phone_sync_failed", "message": "从手机读取失败：…"}}
```

前端 `api()` 会把 `detail.message` 直接展示，因此**后端消息必须是人话**（不要抛技术栈）。

## 6. 全部路由


### `setup`

| 方法 | 路径 |
|---|---|
| POST | `/v1/setup` |

### `login`

| 方法 | 路径 |
|---|---|
| POST | `/v1/login` |

### `logout`

| 方法 | 路径 |
|---|---|
| POST | `/v1/logout` |

### `lock`

| 方法 | 路径 |
|---|---|
| POST | `/v1/lock` |

### `account`

| 方法 | 路径 |
|---|---|
| GET | `/v1/account` |
| PUT | `/v1/account/password` |
| PUT | `/v1/account/session-timeout` |

### `settings`

| 方法 | 路径 |
|---|---|
| GET | `/v1/settings/language` |
| PUT | `/v1/settings/language` |
| GET | `/v1/settings/model-service` |
| PUT | `/v1/settings/model-service` |
| POST | `/v1/settings/model-service/test` |
| GET | `/v1/settings/remote-agents` |
| PUT | `/v1/settings/remote-agents` |

### `agents`

| 方法 | 路径 |
|---|---|
| GET | `/v1/agents` |
| DELETE | `/v1/agents/{key}` |
| POST | `/v1/agents/{key}/approve` |
| POST | `/v1/agents/{key}/deny` |
| POST | `/v1/agents/{key}/revoke` |

### `collections`

| 方法 | 路径 |
|---|---|
| GET | `/v1/collections` |

### `scenario-slices`

| 方法 | 路径 |
|---|---|
| POST | `/v1/scenario-slices/analyze` |
| POST | `/v1/scenario-slices/confirm` |
| POST | `/v1/scenario-slices/migrate-from-definitions` |
| GET | `/v1/scenario-slices/provider` |
| DELETE | `/v1/scenario-slices/{scenario_id}` |
| POST | `/v1/scenario-slices/{scenario_id}/activate` |
| POST | `/v1/scenario-slices/{scenario_id}/compile` |
| POST | `/v1/scenario-slices/{scenario_id}/duplicate` |
| POST | `/v1/scenario-slices/{scenario_id}/feedback` |
| PATCH | `/v1/scenario-slices/{scenario_id}/instance` |
| GET | `/v1/scenario-slices/{scenario_id}/policies` |
| POST | `/v1/scenario-slices/{scenario_id}/policies` |
| DELETE | `/v1/scenario-slices/{scenario_id}/policies/{rule_id}` |
| PATCH | `/v1/scenario-slices/{scenario_id}/policies/{rule_id}` |
| POST | `/v1/scenario-slices/{scenario_id}/preview` |
| POST | `/v1/scenario-slices/{scenario_id}/suspend` |
| POST | `/v1/scenario-slices/{slice_id}/authorize` |
| POST | `/v1/scenario-slices/{slice_id}/backtest` |
| GET | `/v1/scenario-slices/{slice_id}/contract` |
| POST | `/v1/scenario-slices/{slice_id}/deliver` |
| POST | `/v1/scenario-slices/{slice_id}/disable` |
| POST | `/v1/scenario-slices/{slice_id}/draft` |
| POST | `/v1/scenario-slices/{slice_id}/enable` |
| POST | `/v1/scenario-slices/{slice_id}/evaluate` |
| POST | `/v1/scenario-slices/{slice_id}/import-lines` |
| POST | `/v1/scenario-slices/{slice_id}/judge` |
| POST | `/v1/scenario-slices/{slice_id}/judgment-feedback` |

### `asset-transactions`

| 方法 | 路径 |
|---|---|
| GET | `/v1/asset-transactions` |
| POST | `/v1/asset-transactions` |
| DELETE | `/v1/asset-transactions/{transaction_id}` |

### `contacts`

| 方法 | 路径 |
|---|---|
| GET | `/v1/contacts/devices` |
| POST | `/v1/contacts/devices/alias` |
| POST | `/v1/contacts/import-file` |
| POST | `/v1/contacts/purge` |
| POST | `/v1/contacts/sync` |

### `principals`

| 方法 | 路径 |
|---|---|
| POST | `/v1/principals/{principal_id}/acts-for` |

### `contact-records`

| 方法 | 路径 |
|---|---|
| GET | `/v1/contact-records` |

### `profile-items`

| 方法 | 路径 |
|---|---|
| DELETE | `/v1/profile-items/{item_id}` |
| PATCH | `/v1/profile-items/{item_id}` |
| POST | `/v1/profile-items/{item_id}/reveal` |
| GET | `/v1/profile-items/{item_id}/reveals` |

### `assets`

| 方法 | 路径 |
|---|---|
| GET | `/v1/assets` |
| POST | `/v1/assets` |
| DELETE | `/v1/assets/{asset_id}` |
| PATCH | `/v1/assets/{asset_id}` |

### `commitments`

| 方法 | 路径 |
|---|---|
| GET | `/v1/commitments` |
| POST | `/v1/commitments` |
| DELETE | `/v1/commitments/{commitment_id}` |
| PATCH | `/v1/commitments/{commitment_id}` |

### `places`

| 方法 | 路径 |
|---|---|
| GET | `/v1/places` |
| POST | `/v1/places` |
| DELETE | `/v1/places/{place_id}` |
| PATCH | `/v1/places/{place_id}` |

### `profiles`

| 方法 | 路径 |
|---|---|
| GET | `/v1/profiles` |
| POST | `/v1/profiles` |
| POST | `/v1/profiles/migrate-items` |
| GET | `/v1/profiles/usage` |
| DELETE | `/v1/profiles/{profile_id}` |
| PATCH | `/v1/profiles/{profile_id}` |
| GET | `/v1/profiles/{profile_id}/items` |
| POST | `/v1/profiles/{profile_id}/items` |

### `circles`

| 方法 | 路径 |
|---|---|
| GET | `/v1/circles` |
| POST | `/v1/circles` |
| DELETE | `/v1/circles/{circle_id}` |
| PATCH | `/v1/circles/{circle_id}` |
| GET | `/v1/circles/{circle_id}/changes` |
| GET | `/v1/circles/{circle_id}/members` |
| POST | `/v1/circles/{circle_id}/members` |

### `devices`

| 方法 | 路径 |
|---|---|
| GET | `/v1/devices` |
| POST | `/v1/devices/sync` |

### `circle-members`

| 方法 | 路径 |
|---|---|
| DELETE | `/v1/circle-members/{member_id}` |

### `scenario-definitions`

| 方法 | 路径 |
|---|---|
| POST | `/v1/scenario-definitions/{definition_id}/authorize` |
| POST | `/v1/scenario-definitions/{definition_id}/backtest` |
| POST | `/v1/scenario-definitions/{definition_id}/draft` |
| POST | `/v1/scenario-definitions/{definition_id}/evaluate` |
| POST | `/v1/scenario-definitions/{definition_id}/feedback` |

### `{collection}`

| 方法 | 路径 |
|---|---|
| GET | `/v1/{collection}` |
| POST | `/v1/{collection}` |
| DELETE | `/v1/{collection}/{item_id}` |
| GET | `/v1/{collection}/{item_id}` |
| PATCH | `/v1/{collection}/{item_id}` |

### `decisions`

| 方法 | 路径 |
|---|---|
| POST | `/v1/decisions/evaluate` |

### `openapi.json`

| 方法 | 路径 |
|---|---|
| GET | `/v1/openapi.json` |

### `judgment-models`

| 方法 | 路径 |
|---|---|
| GET | `/v1/judgment-models` |
