# 多语言标签模块

本轮实现统一采用英文编码，如 `ROMANCE`、`TIME_TRAVEL`。代码、短剧标签权重和个人画像不存储翻译名称作为计算标识。展示名称按 `locale` 查询，内容语言仍由 `Drama.lang` 表示。

## 数据结构

- `tags`：唯一英文 `code`、`status`（1 启用 / 0 停用）。不提供修改编码和物理删除接口。
- `tag_translations`：`tag_id / locale / name / description`，标签和语言联合唯一。
- `tag_aliases`：`tag_id / locale / alias`，语言和别名联合唯一。
- `user_tag_weights`：`user_id / tag_code / weight / weight_updated_at`，用户和编码联合唯一，编码外键关联 `tags.code`。
- `dramas` 新增 `tag_weights / tag_status / tag_source / tag_version`。权重为 JSON 对象，标签状态初始 `pending`；成功后为 `done`，版本递增。

旧 `dramas.tags` 和旧接口结构保留。管理员更新短剧标签时，将兼容字段同步为英文展示名称数组；旧数据转换脚本保留原有展示数组。新客户端通过短剧标签接口获得英文编码和本地化名称。

现有 MySQL 的 `users.id` 实际为 INT，当前 ORM 却声明 BIGINT；因此画像保留用户 ORM 关联和联合唯一索引，但不创建用户物理外键，避免新建表因类型不一致失败。接口在访问画像前校验用户存在且启用。标签编码仍有物理外键。未来如引入用户删除任务，应同步清理画像记录。

本模块为已确认方案的实现依据；旧 tag-module-multilang-design.md 中的关联表、全球热度公式、UGC、合并标签不在本次实现范围。For You 后续按观看贡献更新画像，本轮不产生虚构的兴趣权重，也不把收藏和播放位置换算为观看时间。

## 部署和数据转换

在已有项目数据库上、部署新版应用之前执行：

```powershell
python -m scripts.migrate_tags --seed
python -m scripts.backfill_drama_tags
```

第一条增加四张表、补齐四个短剧字段，初始化十个基础标签；重复运行不会覆盖已有翻译、别名归属和停用状态。MySQL DDL 不保证事务回滚，建议维护窗口单进程执行；每列检查后再迁移，可重复执行。

第二条只预览，输出可转换数量、跳过数量和未知/歧义标签列表。确认映射后执行：

```powershell
python -m scripts.backfill_drama_tags --apply
```

转换兼容 JSON 数组及现有数据库的逗号分隔文本，按所有语言的名称和别名映射，编码本身也可识别；去重后等权归一化。任一标签未知、歧义、数据格式非法或超过五个标签时，整部短剧保留原值，不自动创建新编码。已完成、已有权重或人工维护的记录不覆盖。转换结果来源为 `auto`，避免假定旧标签已经人工审核。预览批量读取数据，不逐部开启事务；实际写入时才逐部加锁并重新校验人工维护状态。

项目原有启动流程会自动建表和执行兼容性迁移，本模块沿用该机制补字段，但启动不会初始化词表、转换旧标签或修改画像。生产部署仍建议先执行显式迁移。

## 接口

响应沿用项目格式：`{code, message, data}`。业务错误使用 HTTP 200 和业务码；Pydantic 请求结构错误仍为 HTTP 422。新接口未改动旧鉴权和推荐接口。

| 方法 | 路径 | 权限 / 用途 |
|---|---|---|
| GET | `/api/v1/tags?locale=zh-CN` | 公共启用标签字典 |
| GET | `/api/v1/dramas/{drama_id}/tags?locale=zh-CN` | 已上架短剧的本地化标签和权重，drama_id 为外部 ID |
| GET | `/api/v1/admin/tags` | `X-Admin-Token`，包含停用标签、所有翻译和别名 |
| POST | `/api/v1/admin/tags` | 新建编码，必须提供英文名称 |
| PUT | `/api/v1/admin/tags/{code}` | 维护翻译、别名及启用状态，禁止传入新 code |
| GET | `/api/v1/admin/dramas/{drama_id}/tags` | 查看权重、来源、状态和版本 |
| PUT | `/api/v1/admin/dramas/{drama_id}/tags` | 设置 1～5 个标签的正数权重 |
| GET | `/api/v1/me/interests?locale=zh-CN` | Bearer JWT，仅查询当前用户 |
| DELETE | `/api/v1/me/interests` | Bearer JWT，仅重置当前用户画像 |

公共展示接口可以省略 `locale`，按 `Accept-Language` 权重选取首选语言；无有效首选时默认 `en`。回退顺序为精确语言、基础语言、`en`、`en-US`、`en-GB`、其余已有英文区域翻译（按语言代码排序）、英文编码。`ind`、`vie` 作为界面语言兼容值分别映射到 `id`、`vi`，不会修改视频内容语言。

创建标签：

```json
{
  "code": "ROMANCE",
  "translations": {"en": "Romance", "zh-CN": "爱情", "zh-TW": "愛情"},
  "aliases": {"zh-CN": ["言情"]}
}
```

维护时，传入的翻译按语言更新；传入的别名替换对应语言下的别名，空数组用于清空该语言别名。未传入的语言保留。停用标签不会删除历史权重，公共标签、短剧展示和兴趣查询均不再展示它；重新启用后可恢复。

设置短剧权重：

```json
{
  "weights": {"ROMANCE": 7, "URBAN": 3},
  "source": "manual"
}
```

保存为 `{"ROMANCE":0.7,"URBAN":0.3}`。拒绝不存在、已停用编码及非有限正数；来源为 `manual` 或 `auto`。自动更新人工结果返回 409；管理员明确提供 `replace_manual: true` 可重新提交。此开关仍受管理员鉴权保护。

个人兴趣返回 `[{code,name,weight}]`，使用 `weight × 0.95 ^ 间隔天数` 计算当前值，按权重降序；读取不会写库。重置仅清除画像，不删除播放历史和每日贡献上限。后续新观看仍可重新建立画像。

## 验证

隔离 SQLite 功能及回归测试：

```powershell
python -m pytest tests test_database_connections.py test_auth_google.py -q
```

MySQL 可选集成测试使用配置的账号创建并删除 `codex_tag_test_<随机UUID>` 独立测试库，要求账号有创建/删除该测试库的权限，不会对业务库迁移：

```powershell
$env:TAG_TEST_MYSQL = '1'
python -m pytest tests/test_tags_mysql.py -q
Remove-Item Env:TAG_TEST_MYSQL
```

不要直接执行无路径的全库 pytest：项目原有 `test_progress.py` 在收集时初始化默认数据库并插入数据，与本模块隔离测试不同。

## 2026-10-18 本地数据库执行记录

根据用户指示直接使用 `.env` 配置连接现有 MySQL `drama` 库，已成功执行 `python -m scripts.migrate_tags --seed`。四张标签表和四个短剧字段均已创建，字段非空约束核验正常；初始数据为 10 个标签、32 条翻译、1 条别名，个人画像为 0 条。公共字典接口已在实际数据库上验证英文、简体中文、越南语展示；未登录兴趣查询返回业务码 401。

旧标签转换预览结果：101 部短剧均待处理，可安全自动转换 0 部；未改动旧标签，也未生成短剧权重。原因包括未知标签、超过五个概念及空标签。详细列表保存在本地 `runtime/tag-backfill-preview.json`（不纳入 Git）。应先通过管理接口补充经过确认的编码、翻译和别名，并对超过五个标签的短剧人工选取主要题材，再执行回填。

原独立 MySQL 测试库仍受 CREATE DATABASE 权限限制；该限制不影响直接迁移当前有权限的数据库。
