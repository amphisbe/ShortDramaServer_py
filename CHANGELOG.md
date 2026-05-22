# 修改需求文档 (CHANGELOG)

> 基于 2026-05-22 代码审查结果，按优先级排序的修改计划和实施记录。

---

## 修改记录概览

| 序号 | 类型 | 文件 | 描述 | 提交 SHA | 状态 |
|------|------|------|------|----------|------|
| F01 | Bug | `app/core/logging.py`, `app/main.py`, `app/db/database.py` | 日志配置重复覆盖，文件 Handler 被静默移除 | - | 待修复 |
| F02 | Perf | `app/services/play_service.py` | N+1 查询：批量预取统计数据和 viewer 状态 | - | 待修复 |
| F03 | Refactor | `app/db/seed.py`, `app/db/test_data.py` | `_save_model` 重复定义，提取到公共模块 | - | 待修复 |
| F04 | Enhancement | `app/schemas/` | 添加 Pydantic Schema 替代 `dict[str, Any]` | - | 待修复 |
| F05 | Bug | `app/models/drama.py` 及相关 | `datetime.utcnow()` 在 Python 3.12+ 已废弃；`total_episodes=0` 边界文案 | - | 待修复 |
| F06 | Enhancement | `app/main.py` | 模块级代码（`settings`、`_setup_logging`）延迟到 lifespan 中执行 | - | 待修复 |
| F07 | Enhancement | `app/db/database.py:91` | `ensure_demo_schema_compatibility()` 缺少 `close_database()` 配对 | - | 待修复 |

---

## 修改详情

### F01 — 日志配置重复覆盖

**问题描述**：
`app/main.py` 的 `_setup_logging()` 配置了控制台+文件双 Handler（`drama.log`，10MB 轮转）。但 `app/db/database.py:146` 的 `initialize_runtime()` 调用 `app/core/logging.py:setup_logging(level)`，其内部使用 `logging.basicConfig(force=True)` 仅配置 stdout Handler，导致文件 Handler 被移除。

**修复方案**：
1. 合并两套日志配置到 `app/core/logging.py`，支持同时输出到控制台和文件
2. `app/main.py` 移除内部 `_setup_logging()`，改为从 `app/core/logging.py` 导入
3. `initialize_runtime()` 不再重置日志配置；日志初始化由 `app/main.py` 入口负责

---

### F02 — N+1 查询

**问题描述**：
`build_play_item()` 对每个 episode 独立查询：
- 1 次 DramaEpisodeStat 查询
- 若有 viewer：1 次 UserFollow + 1 次 UserEpisodeLike + 1 次 UserEpisodeProgress
- 20 集 + viewer → 81 次查询

**修复方案**：
- 在 `list_play_items()` 中收集所有 episode ID，用 `IN` 子句批量查询统计数据
- viewer 状态查询也使用 `IN` 预取，构建 `{(user_id, episode_id): value}` 字典

---

### F03 — _save_model 重复定义

**问题描述**：
`app/db/seed.py:146` 和 `app/db/test_data.py:55` 定义了完全相同的 `_save_model(instance, values)` 辅助函数。

**修复方案**：
- 新建 `app/db/helpers.py`，将 `_save_model` 提取为公共函数
- `seed.py` 和 `test_data.py` 改为从 `helpers.py` 导入

---

### F04 — Pydantic Schema

**问题描述**：
所有 API 路由返回类型为 `dict[str, Any]`，无请求/响应模型验证，不支持 FastAPI 自动生成文档。

**修复方案**：
- 在 `app/schemas/` 中定义对应的 Pydantic model
- 路由函数使用 `response_model` 注解
- 至少覆盖：`PlayItemResponse`、`PlayListResponse`、`AdminDramaResponse`

---

### F05 — 废弃 API 和边界问题

**问题描述**：
1. `datetime.utcnow()` 在 Python 3.12+ 已废弃，应替换为 `datetime.now(timezone.utc)`
2. 当 `drama.total_episodes = 0` 时，文案显示"全0集"

**修复方案**：
1. 全局查找替换 `datetime.utcnow()` 为 `datetime.now(timezone.utc)`；在 `TimestampMixin.save()` 中同样处理
2. `play_service.py:87-88` 对 `total_episodes` 做防御性判断

---

### F06 — 模块级代码延迟执行

**问题描述**：
`app/main.py` 在模块级别执行 `settings = get_settings()` 和 `_setup_logging()`，在 import 时即运行，不利于测试和配置动态加载。

**修复方案**：
- 将 `settings` 初始化移入 `start()` 函数或 `lifespan`
- 日志初始化由 `lifespan` 统一调用

---

### F07 — ensure_demo_schema_compatibility 缺少 close_database

**问题描述**：
`ensure_demo_schema_compatibility()` 开头调用 `connect_database()` 但函数结束没有 `close_database()`，连接仅在应用关闭时释放。

**修复方案**：
- 函数结束前调用 `close_database()`；或者用 `try/finally` 保证释放
